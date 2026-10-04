from odoo import _, SUPERUSER_ID, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


_PERIOD_TRANSITION_TOKEN = object()


class AccountingPeriod(models.Model):
    _name = "thirdcode.accounting.period"
    _description = "Third Code Accounting Period"
    _inherit = ["mail.thread", "mail.activity.mixin", "thirdcode.workflow.guard.mixin"]
    _order = "date_start desc, id desc"
    _workflow_state_field = "state"
    _workflow_initial_state = "open"
    _workflow_protected_fields = frozenset(
        {"state", "closed_by", "closed_at", "reopened_by", "reopened_at"}
    )

    name = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    date_start = fields.Date(required=True, tracking=True)
    date_end = fields.Date(required=True, tracking=True)
    state = fields.Selection(
        [("open", "Open"), ("closed", "Closed")],
        required=True,
        default="open",
        tracking=True,
    )
    closed_by = fields.Many2one("res.users", readonly=True, copy=False)
    closed_at = fields.Datetime(readonly=True, copy=False)
    reopened_by = fields.Many2one("res.users", readonly=True, copy=False)
    reopened_at = fields.Datetime(readonly=True, copy=False)
    close_note = fields.Text(copy=False)

    _sql_constraints = [
        (
            "thirdcode_period_name_company_unique",
            "unique(company_id, name)",
            "Period names must be unique per company.",
        ),
        (
            "thirdcode_period_dates_valid",
            "check(date_start <= date_end)",
            "The period start date must be on or before its end date.",
        ),
    ]

    @api.constrains("company_id", "date_start", "date_end")
    def _check_overlap(self):
        for period in self:
            overlap = self.search(
                [
                    ("id", "!=", period.id),
                    ("company_id", "=", period.company_id.id),
                    ("date_start", "<=", period.date_end),
                    ("date_end", ">=", period.date_start),
                ],
                limit=1,
            )
            if overlap:
                raise ValidationError(
                    _("Period %(period)s overlaps %(overlap)s.", period=period.name, overlap=overlap.name)
                )

    def _check_close_operator(self):
        if not (
            self.env.user.has_group("thirdcode_accounting.group_thirdcode_accountant")
            or self.env.user.has_group("thirdcode_accounting.group_thirdcode_administrator")
        ):
            raise AccessError(_("Only an Accountant or Administrator may close periods."))

    def _check_administrator(self):
        if not self.env.user.has_group("thirdcode_accounting.group_thirdcode_administrator"):
            raise AccessError(_("Only the Third Code Administrator may reopen periods."))

    def action_close(self):
        self._check_close_operator()
        self.check_access("read")
        self.company_id._thirdcode_lock_period_state(exclusive=True)
        for period in self:
            if period.state != "open":
                raise UserError(_("Only an open period may be closed."))
            domain = [
                ("company_id", "=", period.company_id.id), ("date", ">=", period.date_start),
                ("date", "<=", period.date_end), ("state", "=", "draft"),
            ]
            # Include both this transaction's own changes and commits that
            # completed while close waited for shared accounting writers.
            draft = self.env["account.move"].sudo().search(domain, limit=1)
            with self.env.registry.cursor() as cursor:
                latest = api.Environment(cursor, SUPERUSER_ID, {})["account.move"].search(domain, limit=1)
                latest_draft_name = latest.display_name if latest else False
            if draft or latest_draft_name:
                raise UserError(
                    _(
                        "Cannot close %(period)s while draft entry %(move)s remains in the period.",
                        period=period.name,
                        move=draft.display_name if draft else latest_draft_name,
                    )
                )
            period.sudo().with_context(thirdcode_period_transition_token=_PERIOD_TRANSITION_TOKEN).write(
                {
                    "state": "closed",
                    "closed_by": self.env.user.id,
                    "closed_at": fields.Datetime.now(),
                    "reopened_by": False,
                    "reopened_at": False,
                }
            )
        return True

    def action_reopen(self):
        self._check_administrator()
        self.check_access("read")
        self.company_id._thirdcode_lock_period_state(exclusive=True)
        if any(period.state != "closed" for period in self):
            raise UserError(_("Only a closed period may be reopened."))
        self.sudo().with_context(thirdcode_period_transition_token=_PERIOD_TRANSITION_TOKEN).write(
            {
                "state": "open",
                "reopened_by": self.env.user.id,
                "reopened_at": fields.Datetime.now(),
            }
        )
        return True

    @api.model_create_multi
    def create(self, vals_list):
        if any(values.get("state", self.env.context.get("default_state", "open")) != "open" for values in vals_list):
            raise UserError(_("Periods must be created open and closed through the authorized action."))
        metadata = self._workflow_protected_fields - {"state"}
        if any(values.get(field, self.env.context.get("default_" + field)) for values in vals_list for field in metadata):
            raise AccessError(_("Closure history can only be recorded by the authorized action."))
        return super().create(vals_list)

    def write(self, vals):
        if self._workflow_protected_fields.intersection(vals) and self.env.context.get("thirdcode_period_transition_token") is not _PERIOD_TRANSITION_TOKEN:
            raise AccessError(_("Period state and closure history require the authorized close/reopen action."))
        period_fields = {"name", "company_id", "date_start", "date_end", "close_note"}
        if period_fields.intersection(vals) and any(
            period.state == "closed" for period in self
        ):
            raise UserError(_("A closed period cannot be changed. Reopen it first."))
        return super().write(vals)

    def unlink(self):
        if any(period.state == "closed" for period in self):
            raise UserError(_("A closed period cannot be deleted. Only an Administrator may reopen it."))
        return super().unlink()

    @api.model
    def _check_date_allowed(self, company, accounting_date):
        if not company or not accounting_date:
            return True
        company._thirdcode_lock_period_state()
        period = self.sudo().search([
            ("company_id", "=", company.id), ("state", "=", "closed"),
            ("date_start", "<=", accounting_date), ("date_end", ">=", accounting_date),
        ], limit=1)
        if period:
            raise UserError(_("Accounting effects dated in closed period %(period)s are prohibited. Only an Administrator may reopen it.", period=period.name))
        return True

    @api.model
    def _check_move_post_allowed(self, moves):
        for move in moves:
            self._check_date_allowed(move.company_id, move.date)
        return True
