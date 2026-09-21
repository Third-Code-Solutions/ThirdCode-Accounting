from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class PaymentBatch(models.Model):
    _name = "thirdcode.payment.batch"
    _description = "Third Code Manual Payment Batch"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(required=True, copy=False, default="New", tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    journal_id = fields.Many2one(
        "account.journal",
        required=True,
        domain="[(\"company_id\", \"=\", company_id), (\"type\", \"in\", [\"bank\", \"cash\"])]",
    )
    date = fields.Date(required=True, default=fields.Date.context_today)
    payment_type = fields.Selection(
        [("inbound", "Inbound"), ("outbound", "Outbound")], required=True, default="outbound"
    )
    partner_type = fields.Selection(
        [("customer", "Customer"), ("supplier", "Supplier")], required=True, default="supplier"
    )
    payment_instrument = fields.Selection(
        [("cash", "Cash"), ("cheque", "Cheque"), ("bank_transfer", "Bank transfer")],
        required=True,
        default="bank_transfer",
    )
    instrument_reference = fields.Char(
        help="Cheque number, transfer reference, or cash voucher number."
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending_approval", "Pending approval"),
            ("approved", "Approved"),
            ("posted", "Posted"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    line_ids = fields.One2many("thirdcode.payment.batch.line", "batch_id")
    total_amount = fields.Monetary(compute="_compute_total_amount", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    requires_approval = fields.Boolean(compute="_compute_requires_approval")
    approved_by = fields.Many2one("res.users", readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("thirdcode.payment.batch") or "New"
        return super().create(vals_list)

    @api.depends("line_ids.amount")
    def _compute_total_amount(self):
        for batch in self:
            batch.total_amount = sum(batch.line_ids.mapped("amount"))

    @api.depends("total_amount", "company_id.thirdcode_payment_approval_enabled", "company_id.thirdcode_payment_approval_threshold")
    def _compute_requires_approval(self):
        for batch in self:
            batch.requires_approval = bool(
                batch.company_id.thirdcode_payment_approval_enabled
                and batch.total_amount > batch.company_id.thirdcode_payment_approval_threshold
            )

    def action_submit(self):
        for batch in self:
            if not batch.line_ids:
                raise UserError(_("A payment batch must contain at least one line."))
            if batch.payment_instrument in ("cheque", "bank_transfer") and not batch.instrument_reference:
                raise UserError(_("A cheque or bank transfer requires an instrument reference."))
            batch.state = "pending_approval" if batch.requires_approval else "approved"
        return True

    def action_approve(self):
        if not self.env.user.has_group("thirdcode_accounting.group_thirdcode_administrator"):
            raise AccessError(_("Only an Administrator may approve threshold payments."))
        self.write(
            {
                "state": "approved",
                "approved_by": self.env.user.id,
                "approved_at": fields.Datetime.now(),
            }
        )
        return True

    def _post_line(self, line):
        if line.move_id:
            context = {
                "active_model": "account.move",
                "active_ids": [line.move_id.id],
                "active_id": line.move_id.id,
            }
            wizard = self.env["account.payment.register"].with_context(**context).create(
                {
                    "amount": line.amount or line.move_id.amount_residual,
                    "journal_id": self.journal_id.id,
                    "payment_date": self.date,
                    "communication": line.communication or self.name,
                }
            )
            wizard.action_create_payments()
            payment = self.env["account.payment"].search(
                [
                    ("memo", "=", line.communication or self.name),
                    ("state", "in", ["in_process", "paid", "reconciled"]),
                ],
                order="id desc",
                limit=1,
            )
            if payment:
                payment.with_context(thirdcode_allow_payment_metadata=True).write(
                    {
                        "thirdcode_payment_instrument": line.payment_instrument
                        or self.payment_instrument,
                        "thirdcode_instrument_reference": line.instrument_reference
                        or self.instrument_reference,
                    }
                )
        else:
            if not line.partner_id or not line.amount:
                raise UserError(_("An advance payment requires a partner and a positive amount."))
            payment = self.env["account.payment"].create(
                {
                    "date": self.date,
                    "amount": line.amount,
                    "payment_type": self.payment_type,
                    "partner_type": self.partner_type,
                    "partner_id": line.partner_id.id,
                    "journal_id": self.journal_id.id,
                    "memo": line.communication or self.name,
                    "thirdcode_payment_instrument": line.payment_instrument
                    or self.payment_instrument,
                    "thirdcode_instrument_reference": line.instrument_reference
                    or self.instrument_reference,
                }
            )
            payment.action_post()
        if not payment:
            raise UserError(_("The payment batch line did not produce a posted payment."))
        line.payment_id = payment.id

    def action_post(self):
        if not (
            self.env.user.has_group("thirdcode_accounting.group_thirdcode_accountant")
            or self.env.user.has_group("thirdcode_accounting.group_thirdcode_administrator")
        ):
            raise AccessError(_("Only an Accountant or Administrator may post a payment batch."))
        self._lock_for_posting()
        for batch in self:
            if batch.state == "pending_approval":
                raise UserError(_("This payment batch requires Administrator approval first."))
            if batch.state not in ("approved", "draft"):
                continue
            if batch.state == "draft":
                batch.action_submit()
            if batch.state == "pending_approval":
                raise UserError(_("This payment batch requires Administrator approval first."))
            for line in batch.line_ids.filtered(lambda item: not item.payment_id):
                batch._post_line(line)
            batch.state = "posted"
        return True

    def _lock_for_posting(self):
        """Serialize batch posting before checking state or creating payments.

        The lock is on the custom batch record, not an accounting table. It
        closes the race where two HTTP requests both observe an approved batch
        with unposted lines and each creates a native payment.
        """
        if not self.ids:
            return
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT id FROM thirdcode_payment_batch WHERE id IN %s FOR UPDATE",
            [tuple(self.ids)],
        )
        self.invalidate_recordset()

    def action_cancel(self):
        self.filtered(lambda batch: batch.state not in ("posted", "cancelled")).write(
            {"state": "cancelled"}
        )
        return True


class PaymentBatchLine(models.Model):
    _name = "thirdcode.payment.batch.line"
    _description = "Third Code Manual Payment Batch Line"

    batch_id = fields.Many2one("thirdcode.payment.batch", required=True, ondelete="cascade")
    move_id = fields.Many2one("account.move", domain="[(\"state\", \"=\", \"posted\")]" )
    partner_id = fields.Many2one("res.partner", required=True)
    amount = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(related="batch_id.currency_id", store=True)
    communication = fields.Char()
    payment_instrument = fields.Selection(
        [("cash", "Cash"), ("cheque", "Cheque"), ("bank_transfer", "Bank transfer")]
    )
    instrument_reference = fields.Char()
    payment_id = fields.Many2one("account.payment", readonly=True, copy=False)

    @api.constrains("amount")
    def _check_amount(self):
        for line in self:
            if line.amount < 0:
                raise UserError(_("Payment batch amounts cannot be negative."))

    @api.onchange("move_id")
    def _onchange_move_id(self):
        for line in self:
            if line.move_id:
                line.partner_id = line.move_id.partner_id
                if not line.amount:
                    line.amount = line.move_id.amount_residual
