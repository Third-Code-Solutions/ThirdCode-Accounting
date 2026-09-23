from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class BankReconciliation(models.Model):
    _name = "thirdcode.bank.reconciliation"
    _description = "Third Code Manual Bank Reconciliation"
    _inherit = ["mail.thread", "mail.activity.mixin", "thirdcode.workflow.guard.mixin"]
    _order = "date_end desc, id desc"
    _check_company_auto = True
    _workflow_state_field = "state"
    _workflow_initial_state = "draft"
    _workflow_protected_fields = frozenset(
        {"state", "reconciled_by", "reconciled_at"}
    )

    name = fields.Char(required=True, copy=False, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    journal_id = fields.Many2one(
        "account.journal",
        required=True,
        check_company=True,
        domain="[(\"company_id\", \"=\", company_id), (\"type\", \"in\", [\"bank\", \"cash\"])]",
    )
    statement_reference = fields.Char(required=True, tracking=True)
    date_start = fields.Date(required=True)
    date_end = fields.Date(required=True)
    opening_balance = fields.Monetary(currency_field="currency_id")
    closing_balance = fields.Monetary(currency_field="currency_id", required=True)
    ledger_balance = fields.Monetary(currency_field="currency_id", readonly=True)
    outstanding_deposits = fields.Monetary(
        string="Deposits in transit",
        currency_field="currency_id",
        help="Receipts already recorded in the ledger but not yet on the bank statement. Subtract these when deriving the expected statement balance from the book balance.",
    )
    outstanding_payments = fields.Monetary(
        string="Outstanding payments",
        currency_field="currency_id",
        help="Payments already recorded in the ledger but not yet cleared by the bank. Add these when deriving the expected statement balance from the book balance.",
    )
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

    def write(self, vals):
        protected = {
            "company_id",
            "journal_id",
            "statement_reference",
            "date_start",
            "date_end",
            "opening_balance",
            "closing_balance",
            "ledger_balance",
            "outstanding_deposits",
            "outstanding_payments",
            "evidence_file",
            "evidence_filename",
            "definition",
            "owner_id",
            "bank_statement_line_ids",
        }
        if not self.env.su and protected.intersection(vals) and any(
            record.state == "reconciled" for record in self
        ):
            raise UserError(
                _("A signed-off reconciliation cannot be edited. Reopen it first.")
            )
        return super().write(vals)

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for record in self:
            if record.date_start > record.date_end:
                raise ValidationError(_("A reconciliation period must start before it ends."))

    @api.constrains("company_id", "journal_id")
    def _check_journal_company(self):
        for record in self:
            if record.journal_id.company_id != record.company_id:
                raise ValidationError(
                    _("The reconciliation journal must belong to the selected company.")
                )

    @api.depends("closing_balance", "ledger_balance", "outstanding_deposits", "outstanding_payments")
    def _compute_difference(self):
        for record in self:
            record.expected_bank_balance = (
                record.ledger_balance
                - record.outstanding_deposits
                + record.outstanding_payments
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
        self.check_access("write")
        for record in self:
            if record.state == "reconciled":
                raise UserError(_("Reopen a signed-off reconciliation before recomputing it."))
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
        self.check_access("write")
        for record in self:
            if record.state == "reconciled":
                raise UserError(_("This reconciliation has already been signed off."))
            if not record.evidence_file or not record.evidence_filename:
                raise UserError(_("Attach the paper/PDF statement before sign-off."))
            if not record.definition and not record.company_id.thirdcode_reconciliation_definition:
                raise UserError(_("Define the approved monthly reconciliation procedure before sign-off."))
            if record.currency_id.compare_amounts(record.difference, 0) != 0:
                raise UserError(
                    _("The reconciliation difference must be zero before sign-off; current difference is %(difference)s.", difference=record.difference)
                )
            record.sudo().write(
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
        self.check_access("write")
        if any(record.state != "reconciled" for record in self):
            raise UserError(_("Only a signed-off reconciliation may be reopened."))
        self.sudo().write(
            {"state": "reopened", "reconciled_by": False, "reconciled_at": False}
        )
        return True
