from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class AccountingPeriod(models.Model):
    _name = "thirdcode.accounting.period"
    _description = "Third Code Accounting Period"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_start desc, id desc"

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
        for period in self:
            draft = self.env["account.move"].search(
                [
                    ("company_id", "=", period.company_id.id),
                    ("date", ">=", period.date_start),
                    ("date", "<=", period.date_end),
                    ("state", "=", "draft"),
                ],
                limit=1,
            )
            if draft:
                raise UserError(
                    _(
                        "Cannot close %(period)s while draft entry %(move)s remains in the period.",
                        period=period.name,
                        move=draft.display_name,
                    )
                )
            period.sudo().write(
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
        self.sudo().write(
            {
                "state": "open",
                "reopened_by": self.env.user.id,
                "reopened_at": fields.Datetime.now(),
            }
        )
        return True

    @api.model
    def _check_move_post_allowed(self, moves):
        for move in moves:
            period = self.sudo().search(
                [
                    ("company_id", "=", move.company_id.id),
                    ("date_start", "<=", move.date),
                    ("date_end", ">=", move.date),
                ],
                limit=1,
            )
            if period and period.state == "closed":
                raise UserError(
                    _(
                        "Entry %(move)s is dated in closed period %(period)s. "
                        "Only an Administrator may reopen the period.",
                        move=move.display_name,
                        period=period.name,
                    )
                )
        return True
