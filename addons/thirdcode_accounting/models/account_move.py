from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    thirdcode_document_class = fields.Selection(
        [
            ("sales_invoice", "Sales invoice"),
            ("purchase_bill", "Supplier bill"),
            ("credit_note", "Credit note"),
            ("debit_note", "Debit note"),
            ("journal_entry", "Journal entry"),
            ("opening_balance", "Opening balance"),
            ("recurring_journal", "Recurring journal"),
            ("recurring_invoice", "Recurring invoice"),
        ],
        compute="_compute_thirdcode_document_class",
        store=True,
        readonly=True,
        copy=False,
    )
    thirdcode_source_identifier = fields.Char(
        string="Source identifier",
        index=True,
        copy=False,
        help="Immutable source-system identifier used for migration duplicate detection.",
    )
    thirdcode_is_opening_balance = fields.Boolean(copy=False)
    thirdcode_recurring_journal_id = fields.Many2one(
        "thirdcode.recurring.journal", readonly=True, copy=False, index=True
    )
    thirdcode_recurring_run_date = fields.Date(readonly=True, copy=False, index=True)
    thirdcode_recurring_invoice_id = fields.Many2one(
        "thirdcode.recurring.invoice", readonly=True, copy=False, index=True
    )
    thirdcode_recurring_invoice_run_date = fields.Date(readonly=True, copy=False, index=True)
    thirdcode_bir_ack_control_number = fields.Char(
        related="company_id.thirdcode_bir_ack_control_number",
        string="BIR acknowledgement control number",
        readonly=True,
    )

    _sql_constraints = [
        (
            "thirdcode_source_identifier_unique",
            "unique(company_id, thirdcode_source_identifier)",
            "The source identifier already exists for this company.",
        ),
        (
            "thirdcode_recurring_run_unique",
            "unique(thirdcode_recurring_journal_id, thirdcode_recurring_run_date)",
            "A recurring journal may post only once for a scheduled date.",
        ),
        (
            "thirdcode_recurring_invoice_run_unique",
            "unique(thirdcode_recurring_invoice_id, thirdcode_recurring_invoice_run_date)",
            "A recurring invoice may post only once for a scheduled date.",
        ),
    ]

    @api.depends(
        "move_type",
        "thirdcode_is_opening_balance",
        "thirdcode_recurring_journal_id",
        "thirdcode_recurring_invoice_id",
    )
    def _compute_thirdcode_document_class(self):
        for move in self:
            if move.thirdcode_is_opening_balance:
                move.thirdcode_document_class = "opening_balance"
            elif move.thirdcode_recurring_journal_id:
                move.thirdcode_document_class = "recurring_journal"
            elif move.thirdcode_recurring_invoice_id:
                move.thirdcode_document_class = "recurring_invoice"
            elif move.move_type == "out_invoice":
                move.thirdcode_document_class = "sales_invoice"
            elif move.move_type == "in_invoice":
                move.thirdcode_document_class = "purchase_bill"
            elif move.move_type == "out_refund":
                move.thirdcode_document_class = "credit_note"
            elif move.move_type == "in_refund":
                move.thirdcode_document_class = "debit_note"
            else:
                move.thirdcode_document_class = "journal_entry"

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        return moves

    def write(self, vals):
        safe_posted_fields = {
            "checked",
            "is_manually_modified",
            "message_main_attachment_id",
            "message_follower_ids",
            "message_partner_ids",
        }
        safe_posted_fields.update(
            name
            for name, field in self._fields.items()
            if field.compute and field.readonly and not field.inverse
        )
        protected_fields = set(vals) - safe_posted_fields
        payment_metadata_write = (
            self._name == "account.payment"
            and self.env.context.get("thirdcode_allow_payment_metadata")
            and protected_fields <= {
                "thirdcode_receipt_number",
                "thirdcode_receipt_issued_at",
                "thirdcode_payment_instrument",
                "thirdcode_instrument_reference",
            }
        )
        reconciliation_metadata_write = (
            self._name == "account.move"
            and self.env.context.get("thirdcode_allow_reconciliation_metadata")
            and protected_fields <= {"matched_payment_ids"}
        )
        reversal_metadata_write = (
            self._name == "account.move"
            and self.env.context.get("thirdcode_allow_reversal_metadata")
            and protected_fields <= {"partner_bank_id"}
        )
        if (
            protected_fields
            and any(move.state == "posted" for move in self)
            and not payment_metadata_write
            and not reconciliation_metadata_write
            and not reversal_metadata_write
        ):
            raise UserError(
                _(
                    "Posted accounting entries are immutable. Use a supported reversal or correction document."
                )
            )
        return super().write(vals)

    def _reverse_moves(self, default_values_list=None, cancel=False):
        return super(
            AccountMove,
            self.with_context(thirdcode_allow_reversal_metadata=True),
        )._reverse_moves(default_values_list=default_values_list, cancel=cancel)

    def unlink(self):
        if any(move.state == "posted" for move in self):
            raise UserError(
                _("Posted accounting entries cannot be deleted. Use a supported reversal instead.")
            )
        return super().unlink()

    def action_post(self):
        if self.env.user.has_group("thirdcode_accounting.group_thirdcode_encoder"):
            raise AccessError(
                _(
                    "Encoder users may create and edit drafts, but may not post "
                "accounting entries to the ledger."
                )
            )
        self.env["thirdcode.accounting.period"]._check_move_post_allowed(self)
        return super().action_post()

    def action_print_thirdcode_invoice(self):
        for move in self:
            if move.state != "posted":
                raise UserError(_("Only posted invoices may be printed."))
            if not (
                move.company_id.thirdcode_bir_ack_approved
                and move.company_id.thirdcode_bir_ack_control_number
            ):
                raise UserError(
                    _(
                        "Configure and approve the accountant-owned BIR acknowledgement control number before printing a Third Code invoice."
                    )
                )
        return self.env.ref("thirdcode_accounting.action_report_thirdcode_invoice").report_action(self)
