from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class RecurringJournal(models.Model):
    _name = "thirdcode.recurring.journal"
    _description = "Third Code Recurring Journal"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "next_run, id"

    name = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    journal_id = fields.Many2one(
        "account.journal",
        required=True,
        domain="[(\"company_id\", \"=\", company_id)]",
        tracking=True,
    )
    reference = fields.Char(required=True, copy=False)
    narration = fields.Text()
    date_start = fields.Date(required=True, default=fields.Date.context_today)
    next_run = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    interval_number = fields.Integer(required=True, default=1)
    interval_type = fields.Selection(
        [
            ("days", "Days"),
            ("weeks", "Weeks"),
            ("months", "Months"),
            ("years", "Years"),
        ],
        required=True,
        default="months",
    )
    active = fields.Boolean(default=True, tracking=True)
    line_ids = fields.One2many("thirdcode.recurring.journal.line", "recurring_id")
    last_run = fields.Date(readonly=True, copy=False, tracking=True)
    generated_move_ids = fields.One2many(
        "account.move", "thirdcode_recurring_journal_id", readonly=True
    )

    _sql_constraints = [
        (
            "thirdcode_recurring_reference_company_unique",
            "unique(company_id, reference)",
            "Recurring journal references must be unique per company.",
        ),
    ]

    @api.constrains("interval_number")
    def _check_interval(self):
        for record in self:
            if record.interval_number <= 0:
                raise ValidationError(_("The recurring interval must be positive."))

    @api.constrains("line_ids")
    def _check_lines_balanced(self):
        for record in self:
            if not record.line_ids:
                continue
            debit = sum(record.line_ids.mapped("debit"))
            credit = sum(record.line_ids.mapped("credit"))
            if record.company_id.currency_id.compare_amounts(debit, credit) != 0:
                raise ValidationError(
                    _(
                        "Recurring journal %(name)s is not balanced: debit %(debit)s, credit %(credit)s.",
                        name=record.name,
                        debit=debit,
                        credit=credit,
                    )
                )

    def _next_date(self, run_date):
        self.ensure_one()
        delta = {
            "days": relativedelta(days=self.interval_number),
            "weeks": relativedelta(weeks=self.interval_number),
            "months": relativedelta(months=self.interval_number),
            "years": relativedelta(years=self.interval_number),
        }[self.interval_type]
        return run_date + delta

    def _check_run_access(self):
        if not (
            self.env.user.has_group("thirdcode_accounting.group_thirdcode_accountant")
            or self.env.user.has_group("thirdcode_accounting.group_thirdcode_administrator")
        ):
            raise AccessError(_("Only an Accountant or Administrator may run recurring journals."))

    def _prepare_move_values(self, run_date):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Recurring journal %(name)s has no lines.", name=self.name))
        debit = sum(self.line_ids.mapped("debit"))
        credit = sum(self.line_ids.mapped("credit"))
        if self.company_id.currency_id.compare_amounts(debit, credit) != 0:
            raise UserError(_("Recurring journal %(name)s is not balanced.", name=self.name))
        return {
            "company_id": self.company_id.id,
            "journal_id": self.journal_id.id,
            "date": run_date,
            "ref": f"{self.reference}/{run_date}",
            "narration": self.narration,
            "move_type": "entry",
            "thirdcode_recurring_journal_id": self.id,
            "thirdcode_recurring_run_date": run_date,
            "line_ids": [
                [
                    0,
                    0,
                    {
                        "name": line.name or self.name,
                        "account_id": line.account_id.id,
                        "partner_id": line.partner_id.id or False,
                        "debit": line.debit,
                        "credit": line.credit,
                        "analytic_distribution": line.analytic_distribution or False,
                    },
                ]
                for line in self.line_ids
            ],
        }

    def _run_one(self, run_date):
        self.ensure_one()
        self._lock_for_run()
        existing = self.env["account.move"].search(
            [
                ("thirdcode_recurring_journal_id", "=", self.id),
                ("thirdcode_recurring_run_date", "=", run_date),
            ],
            limit=1,
        )
        move = existing or self.env["account.move"].create(self._prepare_move_values(run_date))
        if move.state == "draft":
            move.action_post()
        if move.state != "posted":
            raise UserError(_("Recurring journal entry was not posted."))
        self.write({"last_run": run_date, "next_run": self._next_date(run_date)})
        return move

    def _lock_for_run(self):
        """Serialize a recurring definition before its run-key lookup."""
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT id FROM thirdcode_recurring_journal WHERE id = %s FOR UPDATE",
            [self.id],
        )
        self.invalidate_recordset()

    def action_run_now(self):
        self._check_run_access()
        for record in self:
            run_date = fields.Date.context_today(record)
            record._run_one(run_date)
        return True

    def action_run_due(self):
        self._check_run_access()
        today = fields.Date.context_today(self)
        for record in self.filtered(lambda item: item.active):
            runs = 0
            while record.next_run and record.next_run <= today:
                record._run_one(record.next_run)
                runs += 1
                if runs > 120:
                    raise UserError(_("Recurring journal catch-up exceeded 120 periods."))
        return True

    @api.model
    def _cron_run_due(self):
        records = self.search([("active", "=", True), ("next_run", "<=", fields.Date.today())])
        for record in records:
            record.action_run_due()
        return True


class RecurringJournalLine(models.Model):
    _name = "thirdcode.recurring.journal.line"
    _description = "Third Code Recurring Journal Line"
    _order = "sequence, id"

    recurring_id = fields.Many2one("thirdcode.recurring.journal", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    name = fields.Char()
    account_id = fields.Many2one("account.account", required=True)
    partner_id = fields.Many2one("res.partner")
    debit = fields.Monetary(currency_field="currency_id")
    credit = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(related="recurring_id.company_id.currency_id", store=True)
    analytic_distribution = fields.Json()

    @api.constrains("debit", "credit")
    def _check_debit_credit(self):
        for line in self:
            if line.debit and line.credit:
                raise ValidationError(_("A recurring journal line cannot have both debit and credit."))
            if line.debit < 0 or line.credit < 0:
                raise ValidationError(_("Recurring journal amounts cannot be negative."))
