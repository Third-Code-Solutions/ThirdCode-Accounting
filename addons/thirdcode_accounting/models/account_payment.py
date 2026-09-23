from num2words import num2words

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = "account.payment"

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
                if payment.company_id.thirdcode_report_samples_approved
                else "draft"
            )

    def _assign_thirdcode_receipt_number(self):
        for payment in self.filtered(
            lambda item: item.state in ("in_process", "paid", "reconciled")
            and item.payment_type == "inbound"
            and item.partner_type == "customer"
        ):
            if not payment.thirdcode_receipt_number:
                payment.sudo().write(
                    {
                        "thirdcode_receipt_number": self.env["ir.sequence"].next_by_code(
                            "thirdcode.official.receipt"
                        ),
                        "thirdcode_receipt_issued_at": fields.Datetime.now(),
                    }
                )
        return True

    def action_post(self):
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
                payment.company_id.thirdcode_bir_ack_approved
                and payment.company_id.thirdcode_bir_ack_control_number
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
