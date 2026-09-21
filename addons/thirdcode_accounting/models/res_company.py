from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class ResCompany(models.Model):
    _inherit = "res.company"

    thirdcode_bir_ack_control_number = fields.Char(
        string="BIR Acknowledgement Certificate control number",
        copy=False,
        help="Enter the accountant/client-owned value only after the certificate is issued.",
    )
    thirdcode_bir_ack_approved = fields.Boolean(
        string="BIR control number approved",
        copy=False,
    )
    thirdcode_eis_status = fields.Selection(
        [
            ("assessment_required", "Coverage assessment required"),
            ("not_in_scope", "Confirmed not in scope"),
            ("implementation_pending", "Implementation pending"),
            ("configured", "Configured; accountant sign-off pending"),
        ],
        string="EIS status",
        default="assessment_required",
        required=True,
        copy=False,
    )
    thirdcode_report_samples_approved = fields.Boolean(
        string="Client report samples approved",
        copy=False,
        help="False keeps custom output visibly marked as draft/provisional.",
    )
    thirdcode_invoice_layout_revision = fields.Char(copy=False)
    thirdcode_statement_layout_revision = fields.Char(copy=False)
    thirdcode_financial_statement_layout_revision = fields.Char(copy=False)
    thirdcode_receipt_layout_revision = fields.Char(copy=False)
    thirdcode_receipt_signatory_name = fields.Char(copy=False)
    thirdcode_receipt_signatory_title = fields.Char(copy=False)
    thirdcode_reconciliation_layout_revision = fields.Char(copy=False)
    thirdcode_numbering_owner = fields.Char(copy=False)
    thirdcode_retained_earnings_account_id = fields.Many2one(
        "account.account",
        string="Retained earnings account",
        domain="[(\"company_ids\", \"in\", [id]), (\"account_type\", \"=\", \"equity\")]",
        copy=False,
    )
    thirdcode_year_end_journal_id = fields.Many2one(
        "account.journal",
        string="Year-end journal",
        domain="[(\"company_id\", \"=\", id), (\"type\", \"=\", \"general\")]",
        copy=False,
    )
    thirdcode_reconciliation_definition = fields.Text(
        string="Monthly reconciliation definition",
        copy=False,
    )
    thirdcode_live_history_policy = fields.Selection(
        [
            ("open_current_prior", "Open items plus current and prior fiscal year"),
            ("full_history", "Full transaction history in live database"),
            ("archive_only", "Open items only; older history archived"),
        ],
        string="Live history policy",
        default="open_current_prior",
        required=True,
        copy=False,
    )
    thirdcode_payment_approval_enabled = fields.Boolean(
        string="Payment approval enabled",
        copy=False,
        help="Optional PRD feature. Disabled until the client approves the workflow.",
    )
    thirdcode_payment_approval_threshold = fields.Monetary(
        string="Payment approval threshold",
        currency_field="currency_id",
        copy=False,
    )
    thirdcode_backup_owner = fields.Char(copy=False)
    thirdcode_restore_owner = fields.Char(copy=False)
    thirdcode_statutory_retention_years = fields.Integer(
        string="Statutory retention years",
        default=10,
        copy=False,
    )
    thirdcode_tax_profile_ids = fields.One2many("thirdcode.tax.profile", "company_id")
    thirdcode_report_sample_ids = fields.One2many("thirdcode.report.sample", "company_id")
    thirdcode_bank_reconciliation_ids = fields.One2many(
        "thirdcode.bank.reconciliation", "company_id"
    )

    @api.constrains("thirdcode_bir_ack_approved", "thirdcode_bir_ack_control_number")
    def _check_bir_control_number(self):
        for company in self:
            if company.thirdcode_bir_ack_approved and not company.thirdcode_bir_ack_control_number:
                raise UserError(
                    _(
                        "A BIR acknowledgement control number is required before marking the certificate approved."
                    )
                )

    def action_validate_thirdcode_configuration(self):
        if not (
            self.env.user.has_group("thirdcode_accounting.group_thirdcode_accountant")
            or self.env.user.has_group("thirdcode_accounting.group_thirdcode_administrator")
        ):
            raise AccessError(
                _("Only an Accountant or Administrator may validate company accounting configuration.")
            )
        for company in self:
            if company.thirdcode_bir_ack_approved and not company.thirdcode_bir_ack_control_number:
                raise UserError(_("Configure the approved BIR acknowledgement control number first."))
            if company.thirdcode_payment_approval_enabled and company.thirdcode_payment_approval_threshold <= 0:
                raise UserError(_("Payment approval requires a positive threshold."))
            if company.thirdcode_statutory_retention_years <= 0:
                raise UserError(_("Statutory retention years must be positive."))
        return True
