from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class RecurringInvoice(models.Model):
    _name = "thirdcode.recurring.invoice"
    _description = "Third Code Recurring Invoice or Supplier Bill"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "next_run, id"

    name = fields.Char(required=True, copy=False, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    move_type = fields.Selection(
        [("out_invoice", "Customer invoice"), ("in_invoice", "Supplier bill")],
        required=True,
        default="out_invoice",
        tracking=True,
    )
    partner_id = fields.Many2one("res.partner", required=True, tracking=True)
    journal_id = fields.Many2one(
        "account.journal",
        required=True,
        domain="[(\"company_id\", \"=\", company_id), (\"type\", \"in\", [\"sale\", \"purchase\"])]",
    )
    payment_term_id = fields.Many2one("account.payment.term")
    reference = fields.Char(required=True, copy=False)
    narration = fields.Text()
    date_start = fields.Date(required=True, default=fields.Date.context_today)
    next_run = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    interval_number = fields.Integer(required=True, default=1)
    interval_type = fields.Selection(
        [("days", "Days"), ("weeks", "Weeks"), ("months", "Months"), ("years", "Years")],
        required=True,
        default="months",
    )
    active = fields.Boolean(default=True, tracking=True)
    line_ids = fields.One2many("thirdcode.recurring.invoice.line", "recurring_id")
    last_run = fields.Date(readonly=True, copy=False, tracking=True)
    generated_move_ids = fields.One2many(
        "account.move", "thirdcode_recurring_invoice_id", readonly=True
    )

    _sql_constraints = [
        (
            "thirdcode_recurring_invoice_reference_company_unique",
            "unique(company_id, reference)",
            "Recurring invoice references must be unique per company.",
        ),
    ]

    @api.constrains("move_type", "journal_id")
    def _check_journal_type(self):
        for record in self:
            expected = "sale" if record.move_type == "out_invoice" else "purchase"
            if record.journal_id and record.journal_id.type != expected:
                raise ValidationError(
                    _("The selected journal must be a %(type)s journal.", type=expected)
                )

    @api.constrains("interval_number")
    def _check_interval(self):
        for record in self:
            if record.interval_number <= 0:
                raise ValidationError(_("The recurring invoice interval must be positive."))

    @api.constrains("line_ids")
    def _check_lines(self):
        for record in self:
            if not record.line_ids:
                continue
            for line in record.line_ids:
                if line.quantity <= 0:
                    raise ValidationError(_("Recurring invoice quantities must be positive."))
                if line.price_unit < 0:
                    raise ValidationError(_("Recurring invoice prices cannot be negative."))

    def _check_run_access(self):
        if not (
            self.env.user.has_group("thirdcode_accounting.group_thirdcode_accountant")
            or self.env.user.has_group("thirdcode_accounting.group_thirdcode_administrator")
        ):
            raise AccessError(_("Only an Accountant or Administrator may run recurring invoices."))

    def _next_date(self, run_date):
        self.ensure_one()
        delta = {
            "days": relativedelta(days=self.interval_number),
            "weeks": relativedelta(weeks=self.interval_number),
            "months": relativedelta(months=self.interval_number),
            "years": relativedelta(years=self.interval_number),
        }[self.interval_type]
        return run_date + delta

    def _prepare_move_values(self, run_date):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Recurring invoice %(name)s has no invoice lines.", name=self.name))
        return {
            "company_id": self.company_id.id,
            "move_type": self.move_type,
            "partner_id": self.partner_id.id,
            "journal_id": self.journal_id.id,
            "invoice_date": run_date,
            "ref": self.reference,
            "narration": self.narration,
            "invoice_payment_term_id": self.payment_term_id.id or False,
            "thirdcode_recurring_invoice_id": self.id,
            "thirdcode_recurring_invoice_run_date": run_date,
            "invoice_line_ids": [
                [
                    0,
                    0,
                    {
                        "name": line.name or self.name,
                        "account_id": line.account_id.id,
                        "quantity": line.quantity,
                        "price_unit": line.price_unit,
                        "tax_ids": [(6, 0, line.tax_ids.ids)],
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
                ("thirdcode_recurring_invoice_id", "=", self.id),
                ("thirdcode_recurring_invoice_run_date", "=", run_date),
            ],
            limit=1,
        )
        move = existing or self.env["account.move"].create(self._prepare_move_values(run_date))
        if move.state == "draft":
            move.action_post()
        if move.state != "posted":
            raise UserError(_("Recurring invoice was not posted."))
        self.write({"last_run": run_date, "next_run": self._next_date(run_date)})
        return move

    def _lock_for_run(self):
        """Serialize a recurring definition before its run-key lookup."""
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT id FROM thirdcode_recurring_invoice WHERE id = %s FOR UPDATE",
            [self.id],
        )
        self.invalidate_recordset()

    def action_run_now(self):
        self._check_run_access()
        for record in self:
            record._run_one(fields.Date.context_today(record))
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
                    raise UserError(_("Recurring invoice catch-up exceeded 120 periods."))
        return True

    @api.model
    def _cron_run_due(self):
        records = self.search([("active", "=", True), ("next_run", "<=", fields.Date.today())])
        for record in records:
            record.action_run_due()
        return True


class RecurringInvoiceLine(models.Model):
    _name = "thirdcode.recurring.invoice.line"
    _description = "Third Code Recurring Invoice Line"
    _order = "sequence, id"

    recurring_id = fields.Many2one("thirdcode.recurring.invoice", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    name = fields.Char()
    account_id = fields.Many2one("account.account", required=True)
    quantity = fields.Float(default=1.0, required=True)
    price_unit = fields.Monetary(currency_field="currency_id", required=True)
    tax_ids = fields.Many2many("account.tax", string="Taxes")
    currency_id = fields.Many2one(related="recurring_id.company_id.currency_id", store=True)
    analytic_distribution = fields.Json()
