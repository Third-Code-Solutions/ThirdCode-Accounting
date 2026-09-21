from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class BankReconciliation(models.Model):
    _name = "thirdcode.bank.reconciliation"
    _description = "Third Code Manual Bank Reconciliation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_end desc, id desc"

    name = fields.Char(required=True, copy=False, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    journal_id = fields.Many2one(
        "account.journal",
        required=True,
        domain="[(\"company_id\", \"=\", company_id), (\"type\", \"in\", [\"bank\", \"cash\"])]",
    )
    statement_reference = fields.Char(required=True, tracking=True)
    date_start = fields.Date(required=True)
    date_end = fields.Date(required=True)
    opening_balance = fields.Monetary(currency_field="currency_id")
    closing_balance = fields.Monetary(currency_field="currency_id", required=True)
    ledger_balance = fields.Monetary(currency_field="currency_id", readonly=True)
    outstanding_deposits = fields.Monetary(currency_field="currency_id")
    outstanding_payments = fields.Monetary(currency_field="currency_id")
    expected_bank_balance = fields.Monetary(
        compute="_compute_difference", store=True, currency_field="currency_id"
    )
    difference = fields.Monetary(
        compute="_compute_difference", store=True, currency_field="currency_id"
    )
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    evidence_file = fields.Binary(
        string="Paper/PDF statement evidence", attachment=True, required=True
    )
    evidence_filename = fields.Char(required=True)
    definition = fields.Text(
        help="Describe the approved monthly reconciliation source, owner, cadence, and sign-off."
    )
    owner_id = fields.Many2one("res.users", default=lambda self: self.env.user, required=True)
    state = fields.Selection(
        [("draft", "Draft"), ("reconciled", "Reconciled"), ("reopened", "Reopened")],
        default="draft",
        required=True,
        tracking=True,
    )
    reconciled_by = fields.Many2one("res.users", readonly=True, copy=False)
    reconciled_at = fields.Datetime(readonly=True, copy=False)
    bank_statement_line_ids = fields.One2many(
        "account.bank.statement.line", "thirdcode_reconciliation_id", string="Statement lines"
    )

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for record in self:
            if record.date_start > record.date_end:
                raise ValidationError(_("A reconciliation period must start before it ends."))

    @api.depends("closing_balance", "ledger_balance", "outstanding_deposits", "outstanding_payments")
    def _compute_difference(self):
        for record in self:
            record.expected_bank_balance = (
                record.ledger_balance + record.outstanding_deposits - record.outstanding_payments
            )
            record.difference = record.closing_balance - record.expected_bank_balance

    def _check_operator(self):
        if not (
            self.env.user.has_group("thirdcode_accounting.group_thirdcode_accountant")
            or self.env.user.has_group("thirdcode_accounting.group_thirdcode_administrator")
        ):
            raise AccessError(_("Only an Accountant or Administrator may reconcile bank statements."))

    def action_compute_ledger_balance(self):
        self._check_operator()
        for record in self:
            journal = record.journal_id
            account = journal.default_account_id
            if not account:
                raise UserError(_("Configure a default account on journal %(journal)s first.", journal=journal.display_name))
            lines = self.env["account.move.line"].search(
                [
                    ("company_id", "=", record.company_id.id),
                    ("journal_id", "=", journal.id),
                    ("account_id", "=", account.id),
                    ("date", ">=", record.date_start),
                    ("date", "<=", record.date_end),
                    ("move_id.state", "=", "posted"),
                ]
            )
            record.ledger_balance = record.opening_balance + sum(
                lines.mapped(lambda line: line.debit - line.credit)
            )
        return True

    def action_reconcile(self):
        self._check_operator()
        for record in self:
            if not record.evidence_file or not record.evidence_filename:
                raise UserError(_("Attach the paper/PDF statement before sign-off."))
            if not record.definition and not record.company_id.thirdcode_reconciliation_definition:
                raise UserError(_("Define the approved monthly reconciliation procedure before sign-off."))
            if record.currency_id.compare_amounts(record.difference, 0) != 0:
                raise UserError(
                    _("The reconciliation difference must be zero before sign-off; current difference is %(difference)s.", difference=record.difference)
                )
            record.write(
                {
                    "state": "reconciled",
                    "reconciled_by": self.env.user.id,
                    "reconciled_at": fields.Datetime.now(),
                }
            )
        return True

    def action_reopen(self):
        if not self.env.user.has_group("thirdcode_accounting.group_thirdcode_administrator"):
            raise AccessError(_("Only an Administrator may reopen a reconciled statement."))
        self.write({"state": "reopened", "reconciled_by": False, "reconciled_at": False})
        return True
