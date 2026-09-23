from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class PaymentBatch(models.Model):
    _name = "thirdcode.payment.batch"
    _description = "Third Code Manual Payment Batch"
    _inherit = ["mail.thread", "mail.activity.mixin", "thirdcode.workflow.guard.mixin"]
    _order = "date desc, id desc"
    _check_company_auto = True
    _workflow_state_field = "state"
    _workflow_initial_state = "draft"
    _workflow_protected_fields = frozenset(
        {"state", "approved_by", "approved_at"}
    )

    name = fields.Char(required=True, copy=False, default="New", tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    journal_id = fields.Many2one(
        "account.journal",
        required=True,
        check_company=True,
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

    def write(self, vals):
        if self.ids:
            self._lock_for_posting()
        editable_fields = {
            "company_id",
            "journal_id",
            "date",
            "payment_type",
            "partner_type",
            "payment_instrument",
            "instrument_reference",
            "line_ids",
        }
        if not self.env.su and editable_fields.intersection(vals) and any(
            batch.state != "draft" for batch in self
        ):
            raise UserError(
                _("A submitted payment batch cannot be edited. Cancel it and create a new draft.")
            )
        return super().write(vals)

    @api.constrains("company_id", "journal_id")
    def _check_journal_company(self):
        for batch in self:
            if batch.journal_id.company_id != batch.company_id:
                raise ValidationError(
                    _("The payment journal must belong to the batch company.")
                )

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
        self.check_access("write")
        self._lock_for_posting()
        for batch in self:
            if batch.state != "draft":
                raise UserError(_("Only a draft payment batch may be submitted."))
            if not batch.line_ids:
                raise UserError(_("A payment batch must contain at least one line."))
            if batch.payment_instrument in ("cheque", "bank_transfer") and not batch.instrument_reference:
                raise UserError(_("A cheque or bank transfer requires an instrument reference."))
            batch._check_lines_before_submit()
            batch.sudo().write(
                {"state": "pending_approval" if batch.requires_approval else "approved"}
            )
        return True

    def _check_lines_before_submit(self, lines=None):
        self.ensure_one()
        currency = self.company_id.currency_id
        lines_to_check = lines if lines is not None else self.line_ids
        for line in lines_to_check:
            if currency.compare_amounts(line.amount, 0) <= 0:
                raise UserError(
                    _("Every payment batch line must have a positive amount before submission.")
                )
            if line.partner_id.company_id and line.partner_id.company_id != self.company_id:
                raise ValidationError(
                    _("The payment partner must belong to the batch company or be shared.")
                )
            if not line.move_id:
                continue
            move = line.move_id
            if move.state != "posted" or move.company_id != self.company_id:
                raise ValidationError(
                    _("An invoice payment must reference a posted document in the batch company.")
                )
            if move.partner_id != line.partner_id:
                raise ValidationError(
                    _("The payment partner must match the selected invoice or bill.")
                )
            expected = {
                "out_invoice": ("inbound", "customer"),
                "out_receipt": ("inbound", "customer"),
                "out_refund": ("outbound", "customer"),
                "in_invoice": ("outbound", "supplier"),
                "in_receipt": ("outbound", "supplier"),
                "in_refund": ("inbound", "supplier"),
            }.get(move.move_type)
            if expected != (self.payment_type, self.partner_type):
                raise ValidationError(
                    _("The payment direction and partner type must match the selected document.")
                )
            residual_company = move.currency_id._convert(
                move.amount_residual,
                currency,
                self.company_id,
                self.date,
            )
            if currency.compare_amounts(line.amount, residual_company) > 0:
                raise UserError(
                    _("A payment batch line cannot exceed the document's remaining balance.")
                )

    def action_approve(self):
        if not self.env.user.has_group("thirdcode_accounting.group_thirdcode_administrator"):
            raise AccessError(_("Only an Administrator may approve threshold payments."))
        self.check_access("write")
        self._lock_for_posting()
        for batch in self:
            if batch.state != "pending_approval":
                raise UserError(_("Only a batch pending approval may be approved."))
            batch.sudo().write(
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
                    "amount": line.amount,
                    "journal_id": self.journal_id.id,
                    "payment_date": self.date,
                    "communication": line.communication or self.name,
                }
            )
            payment_model = self.env["account.payment"]
            amount = self.company_id.currency_id._convert(
                line.amount,
                wizard.currency_id,
                self.company_id,
                self.date,
            )
            wizard.write({"amount": amount})
            payment_action = wizard.action_create_payments()
            payment = payment_model.browse()
            if (
                isinstance(payment_action, dict)
                and payment_action.get("res_model") == payment_model._name
            ):
                payment_id = payment_action.get("res_id")
                if payment_id:
                    payment = payment_model.browse(payment_id).exists()
                elif payment_action.get("domain"):
                    payment = payment_model.search(payment_action["domain"])
            if len(payment) != 1:
                raise UserError(
                    _("The payment register did not return exactly one payment for this batch line.")
                )
            if (
                payment.company_id != self.company_id
                or payment.state not in ("in_process", "paid", "reconciled")
            ):
                raise UserError(
                    _("The payment register returned a payment outside this batch's company or posting state.")
                )
            if payment:
                payment.sudo().write(
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
            payment_currency = (
                self.journal_id.currency_id or self.company_id.currency_id
            )
            payment = self.env["account.payment"].create(
                {
                    "date": self.date,
                    "amount": self.company_id.currency_id._convert(
                        line.amount,
                        payment_currency,
                        self.company_id,
                        self.date,
                    ),
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
        line.sudo().write({"payment_id": payment.id})

    def action_post(self):
        if not (
            self.env.user.has_group("thirdcode_accounting.group_thirdcode_accountant")
            or self.env.user.has_group("thirdcode_accounting.group_thirdcode_administrator")
        ):
            raise AccessError(_("Only an Accountant or Administrator may post a payment batch."))
        self.check_access("write")
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
            if batch.requires_approval and not batch.approved_by:
                raise UserError(
                    _("This payment batch requires Administrator approval under the current approval policy.")
                )
            batch._check_lines_before_submit(
                batch.line_ids.filtered(lambda item: not item.payment_id)
            )
            for line in batch.line_ids.filtered(lambda item: not item.payment_id):
                batch._post_line(line)
            batch.sudo().write({"state": "posted"})
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
        if not (
            self.env.user.has_group("thirdcode_accounting.group_thirdcode_accountant")
            or self.env.user.has_group("thirdcode_accounting.group_thirdcode_administrator")
        ):
            raise AccessError(_("Only an Accountant or Administrator may cancel a payment batch."))
        self.check_access("write")
        self._lock_for_posting()
        self.filtered(lambda batch: batch.state in ("draft", "pending_approval", "approved")).sudo().write(
            {"state": "cancelled"}
        )
        return True


class PaymentBatchLine(models.Model):
    _name = "thirdcode.payment.batch.line"
    _description = "Third Code Manual Payment Batch Line"
    _check_company_auto = True

    batch_id = fields.Many2one("thirdcode.payment.batch", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="batch_id.company_id", store=True, index=True)
    move_id = fields.Many2one(
        "account.move", check_company=True, domain="[(\"state\", \"=\", \"posted\")]"
    )
    partner_id = fields.Many2one("res.partner", required=True, check_company=True)
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

    @api.model_create_multi
    def create(self, vals_list):
        batch_ids = {vals.get("batch_id") for vals in vals_list if vals.get("batch_id")}
        batches = self.env["thirdcode.payment.batch"].browse(list(batch_ids))
        batches._lock_for_posting()
        if any(batch.state != "draft" for batch in batches):
            raise UserError(_("Payment lines can only be added to a draft batch."))
        return super().create(vals_list)

    def write(self, vals):
        batches = self.mapped("batch_id")
        batches._lock_for_posting()
        if "payment_id" in vals and not self.env.su:
            raise AccessError(_("The posted payment link is system-managed."))
        if not self.env.su and any(batch.state != "draft" for batch in batches):
            raise UserError(
                _("Submitted payment lines cannot be edited. Cancel the batch and create a new draft.")
            )
        return super().write(vals)

    def unlink(self):
        batches = self.mapped("batch_id")
        batches._lock_for_posting()
        if not self.env.su and any(batch.state != "draft" for batch in batches):
            raise UserError(_("Lines can only be removed from a draft payment batch."))
        return super().unlink()

    @api.onchange("move_id")
    def _onchange_move_id(self):
        for line in self:
            if line.move_id:
                line.partner_id = line.move_id.partner_id
                if not line.amount:
                    line.amount = line.move_id.currency_id._convert(
                        line.move_id.amount_residual,
                        line.batch_id.company_id.currency_id,
                        line.batch_id.company_id,
                        line.batch_id.date,
                    )
