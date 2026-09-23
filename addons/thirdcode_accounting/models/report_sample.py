from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class ReportSample(models.Model):
    _name = "thirdcode.report.sample"
    _description = "Third Code Client Report Sample Approval"
    _inherit = ["mail.thread", "mail.activity.mixin", "thirdcode.workflow.guard.mixin"]
    _order = "sample_type, id"
    _workflow_state_field = "state"
    _workflow_initial_state = "pending"
    _workflow_protected_fields = frozenset(
        {"state", "approved_by", "approved_at"}
    )

    name = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    sample_type = fields.Selection(
        [
            ("statement", "Statement of account"),
            ("financial", "Financial statements"),
            ("receipt", "Official receipt"),
            ("reconciliation", "Monthly reconciliation"),
            ("invoice", "Invoice"),
        ],
        required=True,
        tracking=True,
    )
    revision = fields.Char(required=True)
    source_file = fields.Binary(required=True, attachment=True)
    source_filename = fields.Char(required=True)
    state = fields.Selection(
        [("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")],
        default="pending",
        required=True,
        tracking=True,
    )
    approved_by = fields.Many2one("res.users", readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    notes = fields.Text(copy=False)

    def _check_approver(self):
        if not self.env.user.has_group("thirdcode_accounting.group_thirdcode_administrator"):
            raise AccessError(_("Only a Third Code Administrator may approve report samples."))

    def action_approve(self):
        self._check_approver()
        self.check_access("write")
        for sample in self:
            if sample.state == "approved":
                raise UserError(_("This report sample is already approved."))
            if not sample.source_file or not sample.revision:
                raise UserError(_("An attached source file and revision are required."))
            sample.sudo().write(
                {
                    "state": "approved",
                    "approved_by": self.env.user.id,
                    "approved_at": fields.Datetime.now(),
                }
            )
        return True

    def action_reject(self):
        self._check_approver()
        self.check_access("write")
        if any(sample.state == "rejected" for sample in self):
            raise UserError(_("Only pending or approved report samples may be rejected."))
        self.sudo().write(
            {"state": "rejected", "approved_by": False, "approved_at": False}
        )
        return True

    def write(self, vals):
        approved_content = {"company_id", "sample_type", "revision", "source_file", "source_filename"}
        if not self.env.su and approved_content.intersection(vals) and any(
            sample.state == "approved" for sample in self
        ):
            raise UserError(
                _("An approved report sample is immutable. Create a new revision instead.")
            )
        return super().write(vals)
