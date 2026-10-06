from num2words import num2words

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .write_tokens import PAYMENT_APPROVAL_TOKEN, RECEIPT_NUMBER_TOKEN


class AccountPayment(models.Model):
    _inherit = "account.payment"

    _sql_constraints = [
        ("thirdcode_receipt_number_unique", "unique(company_id, thirdcode_receipt_number)",
         "Receipt numbers must be unique within a company."),
    ]

    thirdcode_receipt_number = fields.Char(
        string="Official receipt number",
        readonly=True,
        copy=False,
        index=True,
    )
    thirdcode_receipt_issued_at = fields.Datetime(readonly=True, copy=False)
    thirdcode_receipt_control_number = fields.Char(
        related="company_id.thirdcode_bir_ack_control_number",
        string="BIR acknowledgement control number",
        readonly=True,
    )
    thirdcode_amount_in_words = fields.Char(
        compute="_compute_thirdcode_amount_in_words",
        string="Amount in words",
    )
    thirdcode_receipt_vat_amount = fields.Monetary(
        compute="_compute_thirdcode_receipt_vat_amount",
        currency_field="currency_id",
        string="VAT amount derived from invoices",
    )
    thirdcode_receipt_vat_breakdown = fields.Text(
        compute="_compute_thirdcode_receipt_vat_breakdown",
        string="VAT breakdown derived from invoices",
    )
    thirdcode_receipt_customer_tin = fields.Char(
        related="partner_id.vat",
        string="Customer TIN",
        readonly=True,
    )
    thirdcode_report_status = fields.Selection(
        compute="_compute_thirdcode_report_status",
        selection=[("draft", "Draft layout"), ("approved", "Approved layout")],
    )
    thirdcode_payment_instrument = fields.Selection(
        [("cash", "Cash"), ("cheque", "Cheque"), ("bank_transfer", "Bank transfer")],
        string="Payment instrument",
        copy=False,
    )
    thirdcode_instrument_reference = fields.Char(
        string="Instrument reference", copy=False
    )

    @api.depends("amount", "currency_id")
    def _compute_thirdcode_amount_in_words(self):
        for payment in self:
            if not payment.currency_id:
                payment.thirdcode_amount_in_words = ""
                continue
            amount = num2words(payment.amount, lang="en")
            payment.thirdcode_amount_in_words = f"{amount.title()} {payment.currency_id.name}"

    @api.depends(
        "payment_type",
        "partner_type",
        "move_id.line_ids.matched_debit_ids.debit_amount_currency",
        "move_id.line_ids.matched_debit_ids.credit_amount_currency",
        "move_id.line_ids.matched_credit_ids.debit_amount_currency",
        "move_id.line_ids.matched_credit_ids.credit_amount_currency",
        "move_id.line_ids.matched_debit_ids.debit_move_id.move_id.amount_total",
        "move_id.line_ids.matched_debit_ids.debit_move_id.move_id.amount_tax",
        "move_id.line_ids.matched_debit_ids.credit_move_id.move_id.amount_total",
        "move_id.line_ids.matched_debit_ids.credit_move_id.move_id.amount_tax",
        "move_id.line_ids.matched_credit_ids.debit_move_id.move_id.amount_total",
        "move_id.line_ids.matched_credit_ids.debit_move_id.move_id.amount_tax",
        "move_id.line_ids.matched_credit_ids.credit_move_id.move_id.amount_total",
        "move_id.line_ids.matched_credit_ids.credit_move_id.move_id.amount_tax",
        "currency_id",
        "date",
    )
    def _compute_thirdcode_receipt_vat_amount(self):
        for payment in self:
            vat_amount = 0.0
            for invoice, applied_amount in payment._thirdcode_receipt_allocations().items():
                invoice_currency = invoice.currency_id
                if invoice_currency.is_zero(invoice.amount_total):
                    continue
                allocation = min(applied_amount / abs(invoice.amount_total), 1.0)
                allocated_tax = invoice.amount_tax * allocation
                vat_amount += invoice_currency._convert(
                    allocated_tax,
                    payment.currency_id,
                    payment.company_id,
                    payment.date,
                )
            payment.thirdcode_receipt_vat_amount = vat_amount

    @api.depends(
        "thirdcode_receipt_vat_amount",
        "move_id.line_ids.matched_debit_ids",
        "move_id.line_ids.matched_credit_ids",
    )
    def _compute_thirdcode_receipt_vat_breakdown(self):
        for payment in self:
            lines = []
            for invoice, applied_amount in payment._thirdcode_receipt_allocations().items():
                if invoice.currency_id.is_zero(invoice.amount_total):
                    continue
                allocation = min(applied_amount / abs(invoice.amount_total), 1.0)
                tax_totals = invoice.tax_totals or {}
                groups_by_subtotal = tax_totals.get("groups_by_subtotal") or {}
                groups = [
                    group
                    for subtotal_groups in groups_by_subtotal.values()
                    for group in subtotal_groups
                ]
                if groups:
                    for group in groups:
                        group_name = group.get("tax_group_name") or "Tax"
                        group_amount = invoice.currency_id._convert(
                            float(group.get("tax_group_amount") or 0.0) * allocation,
                            payment.currency_id,
                            payment.company_id,
                            payment.date,
                        )
                        lines.append(
                            f"{invoice.name or invoice.ref or 'Invoice'} — {group_name}: "
                            f"{group_amount:.2f} {payment.currency_id.name}"
                        )
                elif invoice.amount_tax:
                    group_amount = invoice.currency_id._convert(
                        invoice.amount_tax * allocation,
                        payment.currency_id,
                        payment.company_id,
                        payment.date,
                    )
                    lines.append(
                        f"{invoice.name or invoice.ref or 'Invoice'} — tax total: "
                        f"{group_amount:.2f} {payment.currency_id.name}"
                    )
            payment.thirdcode_receipt_vat_breakdown = "\n".join(lines) or "No configured invoice tax lines."

    def _thirdcode_receipt_allocations(self):
        """Return each customer invoice's actually reconciled amount in its currency."""
        self.ensure_one()
        if (
            self.payment_type != "inbound"
            or self.partner_type != "customer"
            or not self.move_id
        ):
            return {}

        allocations = {}
        sale_document_types = {"out_invoice", "out_refund", "out_receipt"}
        for payment_line in self.move_id.line_ids.filtered(
            lambda line: line.account_id.account_type
            in {"asset_receivable", "liability_payable"}
        ):
            partials = payment_line.matched_debit_ids | payment_line.matched_credit_ids
            for partial in partials:
                if partial.debit_move_id == payment_line:
                    invoice_line = partial.credit_move_id
                else:
                    invoice_line = partial.debit_move_id
                invoice = invoice_line.move_id
                if invoice.move_type not in sale_document_types:
                    continue
                amount = (
                    partial.debit_amount_currency
                    if invoice_line == partial.debit_move_id
                    else partial.credit_amount_currency
                )
                allocations[invoice] = allocations.get(invoice, 0.0) + amount
        return allocations

    @api.depends("company_id.thirdcode_report_samples_approved")
    def _compute_thirdcode_report_status(self):
        for payment in self:
            payment.thirdcode_report_status = (
                "approved"
                if payment.company_id._thirdcode_approved_sample("receipt")
                else "draft"
            )

    @api.model_create_multi
    def create(self, vals_list):
        if any(values.get("thirdcode_receipt_number", self.env.context.get("default_thirdcode_receipt_number")) or values.get("thirdcode_receipt_issued_at", self.env.context.get("default_thirdcode_receipt_issued_at")) for values in vals_list):
            raise UserError(_("Receipt numbers are assigned only by native posting."))
        return super().create(vals_list)

    def write(self, vals):
        if {"thirdcode_receipt_number", "thirdcode_receipt_issued_at"}.intersection(vals):
            if self.env.context.get("thirdcode_receipt_number_token") is not RECEIPT_NUMBER_TOKEN:
                raise UserError(_("Receipt numbers and issue timestamps cannot be edited."))
            if any(payment.thirdcode_receipt_number for payment in self):
                raise UserError(_("An issued receipt cannot be renumbered."))
        if {"state", "amount", "date", "partner_id", "payment_type", "partner_type", "journal_id", "company_id", "currency_id", "move_id"}.intersection(vals):
            for payment in self.filtered(lambda item: item.move_id._thirdcode_ever_posted()):
                economic = set(vals) - {"state"}
                if vals.get("state", payment.state) in {"draft", "canceled", "cancel"} or any(
                    self.env["account.move"]._field_will_change(payment, vals, field) for field in economic
                ):
                    raise UserError(_("Posted payments require reversal; their accounting details cannot be changed."))
        return super().write(vals)

    def _assign_thirdcode_receipt_number(self):
        self.check_access("write")
        for payment in self.sorted("id"):
            if payment.company_id not in self.env.companies:
                raise UserError(_("Receipts may only be numbered in an active company."))
            payment.flush_recordset()
            self.env.cr.execute("SELECT id FROM account_payment WHERE id = %s FOR UPDATE", [payment.id])
            payment.invalidate_recordset()
            if (payment.move_id.state == "posted" and payment.payment_type == "inbound"
                    and payment.partner_type == "customer" and not payment.thirdcode_receipt_number):
                sequence = payment.company_id._thirdcode_receipt_sequence()
                number = sequence.with_context(thirdcode_receipt_number_token=RECEIPT_NUMBER_TOKEN).next_by_id()
                payment.with_context(thirdcode_receipt_number_token=RECEIPT_NUMBER_TOKEN).write({
                    "thirdcode_receipt_number": number,
                    "thirdcode_receipt_issued_at": fields.Datetime.now(),
                })
        return True

    def _thirdcode_check_payment_controls(self):
        """Server-side controls that must hold for every payment posting path.

        * A payment above the company approval threshold only passes through a
          batch an administrator approved (finding H3); the batch enters with
          an unforgeable in-process token.
        * An outbound bank payment may only reach a bank account an
          administrator has verified (``allow_out_payment``), so changing a
          vendor's bank details alone can no longer divert a payment
          (finding H2).
        """
        if self.env.su:
            return
        for payment in self:
            company = payment.company_id
            if company.thirdcode_payment_approval_enabled:
                amount = abs(payment.amount)
                if payment.currency_id and payment.currency_id != company.currency_id:
                    amount = payment.currency_id._convert(
                        amount,
                        company.currency_id,
                        company,
                        payment.date or fields.Date.context_today(payment),
                    )
                if (
                    amount > company.thirdcode_payment_approval_threshold
                    and self.env.context.get("thirdcode_payment_approval_token")
                    is not PAYMENT_APPROVAL_TOKEN
                ):
                    raise UserError(
                        _(
                            "A payment above the %(threshold)s %(currency)s approval threshold must be posted through a payment batch an administrator approved.",
                            threshold=company.thirdcode_payment_approval_threshold,
                            currency=company.currency_id.name,
                        )
                    )
            bank = payment.partner_bank_id
            if (
                payment.payment_type == "outbound"
                and payment.journal_id.type == "bank"
                and bank
                and not bank.allow_out_payment
            ):
                raise UserError(
                    _(
                        "Payments may only be sent to a bank account an administrator has verified (marked Trusted). Review the bank account of %(partner)s before paying.",
                        partner=payment.partner_id.display_name,
                    )
                )

    def action_post(self):
        self._thirdcode_check_payment_controls()
        result = super().action_post()
        self._assign_thirdcode_receipt_number()
        return result

    def action_print_thirdcode_receipt(self):
        for payment in self:
            if (
                payment.state not in ("in_process", "paid", "reconciled")
                or not payment.move_id
                or payment.move_id.state != "posted"
            ):
                raise UserError(_("Only posted payments may print an Official Receipt."))
            if payment.payment_type != "inbound" or payment.partner_type != "customer":
                raise UserError(_("Official Receipts are only for incoming customer payments."))
            if not (
                payment.company_id.thirdcode_trial_mode
                or (
                    payment.company_id.thirdcode_bir_ack_approved
                    and payment.company_id.thirdcode_bir_ack_control_number
                )
            ):
                raise UserError(
                    _(
                        "Configure and approve the accountant-owned BIR acknowledgement control number before printing an Official Receipt."
                    )
                )
        return self.env.ref("thirdcode_accounting.action_report_thirdcode_receipt").report_action(self)

    def action_assign_thirdcode_receipt_number(self):
        self._assign_thirdcode_receipt_number()
        return True
