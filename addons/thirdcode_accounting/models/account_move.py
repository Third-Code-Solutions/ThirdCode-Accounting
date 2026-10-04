from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .write_tokens import BANK_STATEMENT_SYNC_TOKEN


_RECONCILIATION_METADATA_TOKEN = object()
_REVERSAL_METADATA_TOKEN = object()
_STATE_TRANSITION_TOKEN = object()


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
        reconciliation_metadata_write = (
            self._name == "account.move"
            and self.env.context.get("thirdcode_reconciliation_metadata_token")
            is _RECONCILIATION_METADATA_TOKEN
            and protected_fields <= {"matched_payment_ids"}
        )
        reversal_metadata_write = (
            self._name == "account.move"
            and self.env.context.get("thirdcode_reversal_metadata_token")
            is _REVERSAL_METADATA_TOKEN
            and protected_fields <= {"partner_bank_id"}
        )
        bank_statement_sync_write = (
            self.env.context.get("thirdcode_bank_statement_sync_token")
            is BANK_STATEMENT_SYNC_TOKEN
            and protected_fields <= {"currency_id", "journal_id", "line_ids", "partner_id"}
            and all(move.sudo().statement_line_ids for move in self)
        )
        state_transition_write = (
            self.env.context.get("thirdcode_state_transition_token")
            is _STATE_TRANSITION_TOKEN
            and protected_fields <= {"state", "auto_post", "sending_data"}
        )
        if (
            protected_fields
            and any(move.state == "posted" for move in self)
            and not self.env.su
            and not reconciliation_metadata_write
            and not reversal_metadata_write
            and not bank_statement_sync_write
            and not state_transition_write
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
            self.with_context(thirdcode_reversal_metadata_token=_REVERSAL_METADATA_TOKEN),
        )._reverse_moves(default_values_list=default_values_list, cancel=cancel)

    def unlink(self):
        if any(move.state == "posted" for move in self):
            raise UserError(
                _(
                    "Posted accounting entries cannot be deleted. Cancel the entry "
                    "or use a supported reversal instead."
                )
            )
        return super().unlink()

    def button_draft(self):
        # Reset-to-draft and cancellation are the sanctioned ways out of
        # posted (cancel runs through reset-to-draft first internally). The
        # token lets exactly those state transitions through the
        # posted-immutability guard without opening direct field edits.
        return super(
            AccountMove,
            self.with_context(thirdcode_state_transition_token=_STATE_TRANSITION_TOKEN),
        ).button_draft()

    def button_cancel(self):
        return super(
            AccountMove,
            self.with_context(thirdcode_state_transition_token=_STATE_TRANSITION_TOKEN),
        ).button_cancel()

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
                move.company_id.thirdcode_trial_mode
                or (
                    move.company_id.thirdcode_bir_ack_approved
                    and move.company_id.thirdcode_bir_ack_control_number
                )
            ):
                raise UserError(
                    _(
                        "Configure and approve the accountant-owned BIR acknowledgement control number before printing a Third Code invoice."
                    )
                )
        return self.env.ref("thirdcode_accounting.action_report_thirdcode_invoice").report_action(self)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def write(self, vals):
        # The move-level guard does not cover direct writes on move lines
        # (self._name is "account.move.line" there), which let API clients
        # reclassify posted amounts between accounts while keeping the entry
        # balanced. Block the accounting-relevant fields for non-superuser
        # writes on posted lines; drafts are unaffected.
        blocked_fields = {
            "account_id",
            "amount_currency",
            "credit",
            "date",
            "debit",
            "name",
            "price_unit",
            "product_id",
            "quantity",
            "ref",
            "tax_ids",
        }
        if (
            blocked_fields.intersection(vals)
            and not self.env.su
            and any(line.move_id.state == "posted" for line in self)
            and self.env.context.get("thirdcode_bank_statement_sync_token")
            is not BANK_STATEMENT_SYNC_TOKEN
            and self.env.context.get("thirdcode_reconciliation_metadata_token")
            is not _RECONCILIATION_METADATA_TOKEN
        ):
            raise UserError(
                _(
                    "Posted accounting entries are immutable. Use a supported reversal or correction document."
                )
            )
        return super().write(vals)
