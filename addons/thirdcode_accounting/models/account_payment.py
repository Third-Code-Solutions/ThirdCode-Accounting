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

    @api.depends("amount", "invoice_ids.amount_total", "invoice_ids.amount_tax")
    def _compute_thirdcode_receipt_vat_amount(self):
        for payment in self:
            vat_amount = 0.0
            for invoice in payment.invoice_ids.filtered(lambda move: move.amount_total):
                allocation = min(payment.amount / invoice.amount_total, 1.0)
                vat_amount += invoice.amount_tax * allocation
            payment.thirdcode_receipt_vat_amount = vat_amount

    @api.depends("amount", "invoice_ids.amount_total", "invoice_ids.amount_tax", "invoice_ids.tax_totals")
    def _compute_thirdcode_receipt_vat_breakdown(self):
        for payment in self:
            lines = []
            for invoice in payment.invoice_ids.filtered(lambda move: move.amount_total):
                allocation = min(payment.amount / invoice.amount_total, 1.0)
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
                        group_amount = float(group.get("tax_group_amount") or 0.0) * allocation
                        lines.append(
                            f"{invoice.name or invoice.ref or 'Invoice'} — {group_name}: {group_amount:.2f}"
                        )
                elif invoice.amount_tax:
                    lines.append(
                        f"{invoice.name or invoice.ref or 'Invoice'} — tax total: {invoice.amount_tax * allocation:.2f}"
                    )
            payment.thirdcode_receipt_vat_breakdown = "\\n".join(lines) or "No configured invoice tax lines."

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
        ):
            if not payment.thirdcode_receipt_number:
                payment.with_context(thirdcode_allow_payment_metadata=True).write(
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
