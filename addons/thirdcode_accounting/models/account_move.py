from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_RECONCILIATION_METADATA_TOKEN = object()
_REVERSAL_METADATA_TOKEN = object()
_POSTING_TOKEN = object()


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

    def _thirdcode_ever_posted(self):
        return self.filtered(lambda move: move.posted_before or move.state == "posted")

    def _thirdcode_check_immutable(self):
        if self._thirdcode_ever_posted():
            raise UserError(_("Previously posted entries are immutable. Use a reversal, credit note or debit note."))

    def _thirdcode_is_encoder_writer(self):
        return not self.env.su and self.env.user.has_group(
            "thirdcode_accounting.group_thirdcode_encoder"
        )

    def _thirdcode_autopost_values_blocked(self, values, from_context=False):
        """True when create/write values would arm automatic posting.

        Encoders may turn automatic posting off (``no``/``False``) but never
        on, and may not schedule or pre-check a draft for the nightly job.
        """

        def effective(name):
            if name in values:
                return values[name]
            return self.env.context.get("default_" + name) if from_context else None

        if effective("auto_post") not in (None, False, "no"):
            return True
        if effective("auto_post_until"):
            return True
        return bool(effective("checked"))

    @api.model_create_multi
    def create(self, vals_list):
        if any(values.get("state", self.env.context.get("default_state")) == "posted" for values in vals_list):
            raise UserError(_("Create a draft and use the native posting action."))
        if any(values.get("posted_before", self.env.context.get("default_posted_before")) for values in vals_list):
            raise UserError(_("Posting history can only be set by native posting."))
        if self._thirdcode_is_encoder_writer() and any(
            self._thirdcode_autopost_values_blocked(values, from_context=True)
            for values in vals_list
        ):
            raise AccessError(
                _("Encoder users may prepare drafts, but may not enable or schedule automatic posting.")
            )
        moves = super().create(vals_list)
        self.env["thirdcode.accounting.period"]._check_move_post_allowed(moves)
        return moves

    def write(self, vals):
        posting = self.env.context.get("thirdcode_posting_token") is _POSTING_TOKEN
        if self._thirdcode_is_encoder_writer() and self._thirdcode_autopost_values_blocked(vals):
            raise AccessError(
                _("Encoder users may prepare drafts, but may not enable or schedule automatic posting.")
            )
        if {"sequence_number", "sequence_prefix"}.intersection(vals) and not posting:
            raise UserError(_("Sequence counters are managed by native posting."))
        if vals.get("name") and vals["name"] != "/" and not posting and any(
            move.name != vals["name"] for move in self
        ):
            raise UserError(_("Document numbers are assigned by posting and cannot be supplied or changed."))
        if "posted_before" in vals and not (
            posting and vals["posted_before"] is True and vals.get("state") == "posted"
        ):
            raise UserError(_("Permanent posting history cannot be changed."))
        if vals.get("state") == "posted" and not posting:
            raise UserError(_("Use the native posting action to post accounting entries."))
        safe_fields = {
            "checked", "is_manually_modified", "message_main_attachment_id",
            "message_follower_ids", "message_partner_ids", "made_sequence_gap",
            "needed_terms_dirty",
        }
        if self.env.context.get("thirdcode_reconciliation_metadata_token") is _RECONCILIATION_METADATA_TOKEN:
            safe_fields.add("matched_payment_ids")
        if self.env.context.get("thirdcode_reversal_metadata_token") is _REVERSAL_METADATA_TOKEN:
            safe_fields.add("partner_bank_id")
        for move in self._thirdcode_ever_posted():
            changed = set(vals) - safe_fields
            # A native no-op synchronization does not change accounting effects.
            if any(move._field_will_change(move, vals, name) for name in changed):
                move._thirdcode_check_immutable()
        if {"date", "company_id", "state", "line_ids", "invoice_line_ids"}.intersection(vals):
            self.env["thirdcode.accounting.period"]._check_move_post_allowed(self)
        result = super().write(vals)
        if {"date", "company_id", "state", "line_ids", "invoice_line_ids"}.intersection(vals):
            self.env["thirdcode.accounting.period"]._check_move_post_allowed(self)
        return result

    def _reverse_moves(self, default_values_list=None, cancel=False):
        defaults = [dict(values) for values in (default_values_list or [{} for move in self])]
        for move, values in zip(self, defaults):
            if move.is_invoice(include_receipts=True) and not values.get("invoice_date"):
                values["invoice_date"] = values.get("date") or fields.Date.context_today(move)
        return super(
            AccountMove,
            self.with_context(thirdcode_reversal_metadata_token=_REVERSAL_METADATA_TOKEN),
        )._reverse_moves(default_values_list=defaults, cancel=cancel)

    def unlink(self):
        self._thirdcode_check_immutable()
        self.env["thirdcode.accounting.period"]._check_move_post_allowed(self)
        return super().unlink()

    def button_draft(self):
        self._thirdcode_check_immutable()
        self.env["thirdcode.accounting.period"]._check_move_post_allowed(self)
        return super().button_draft()

    def button_cancel(self):
        self._thirdcode_check_immutable()
        self.env["thirdcode.accounting.period"]._check_move_post_allowed(self)
        return super().button_cancel()

    def _post(self, soft=True):
        # Payments, reversals, native auto-post and year-end workflows all reach
        # this method, including paths which do not call action_post.
        if self.env.user.has_group("thirdcode_accounting.group_thirdcode_encoder"):
            raise AccessError(_("Encoder users may prepare drafts, but may not post accounting entries."))
        self.env["thirdcode.accounting.period"]._check_move_post_allowed(self)
        return super(
            AccountMove, self.with_context(thirdcode_posting_token=_POSTING_TOKEN)
        )._post(soft=soft)

    def _autopost_draft_entries(self):
        # The nightly job runs as the root user; an Encoder must never cause a
        # posting through it. Drafts last written by an Encoder account are
        # demoted instead of posted, including drafts armed before the write
        # guard existed.
        encoder_group = self.env.ref(
            "thirdcode_accounting.group_thirdcode_encoder", raise_if_not_found=False
        )
        drafts = self.browse()
        if encoder_group:
            encoder_ids = (
                self.env["res.users"]
                .sudo()
                .with_context(active_test=False)
                .search([("groups_id", "in", encoder_group.ids)])
                .ids
            )
            if encoder_ids:
                drafts = self.sudo().search(
                    [
                        ("state", "=", "draft"),
                        ("auto_post", "!=", "no"),
                        ("write_uid", "in", encoder_ids),
                    ]
                )
        for move in drafts:
            move.write({"auto_post": "no", "checked": False})
            move.message_post(
                body=_("Automatic posting was disabled because this draft was last edited by an Encoder account.")
            )
        return super()._autopost_draft_entries()

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

    @api.model_create_multi
    def create(self, vals_list):
        moves = self.env["account.move"].browse({
            values.get("move_id", self.env.context.get("default_move_id"))
            for values in vals_list
            if values.get("move_id", self.env.context.get("default_move_id"))
        })
        moves._thirdcode_check_immutable()
        self.env["thirdcode.accounting.period"]._check_move_post_allowed(moves)
        return super().create(vals_list)

    def write(self, vals):
        # Enumerate metadata instead of exempting sudo, a whole workflow, or
        # all computed fields. Economic fields remain immutable in every path.
        safe_fields = {"epd_dirty", "discount_allocation_dirty"}
        if self.env.context.get("thirdcode_reconciliation_metadata_token") is _RECONCILIATION_METADATA_TOKEN:
            safe_fields.add("matching_number")
        for line in self:
            if line.move_id._thirdcode_ever_posted() and any(
                self.env["account.move"]._field_will_change(line, vals, name)
                for name in set(vals) - safe_fields
            ):
                line.move_id._thirdcode_check_immutable()
        if "move_id" in vals:
            target = self.env["account.move"].browse(vals["move_id"])
            target._thirdcode_check_immutable()
            self.env["thirdcode.accounting.period"]._check_move_post_allowed(target)
        if set(vals) - safe_fields:
            self.env["thirdcode.accounting.period"]._check_move_post_allowed(self.move_id)
        return super().write(vals)

    def unlink(self):
        self.move_id._thirdcode_check_immutable()
        self.env["thirdcode.accounting.period"]._check_move_post_allowed(self.move_id)
        return super().unlink()
