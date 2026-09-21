from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class TaxProfile(models.Model):
    _name = "thirdcode.tax.profile"
    _description = "Third Code Tax Configuration Profile"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "effective_date desc, id desc"

    name = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    status = fields.Selection(
        [("assessment_required", "Assessment required"), ("configured", "Configured")],
        default="assessment_required",
        required=True,
        tracking=True,
    )
    vat_registered = fields.Boolean(string="VAT registered")
    output_vat_tax_id = fields.Many2one("account.tax", string="Output VAT tax")
    input_vat_tax_id = fields.Many2one("account.tax", string="Input VAT tax")
    withholding_tax_ids = fields.Many2many("account.tax", string="Withholding taxes")
    effective_date = fields.Date(required=True, default=fields.Date.context_today)
    accountant_owner = fields.Char(required=True)
    notes = fields.Text(help="Record the approved tax basis; do not infer statutory rates here.")
    approved_by = fields.Many2one("res.users", readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)

    @api.constrains("vat_registered", "output_vat_tax_id", "input_vat_tax_id")
    def _check_vat_mapping(self):
        for profile in self:
            if profile.vat_registered and (
                not profile.output_vat_tax_id or not profile.input_vat_tax_id
            ):
                raise ValidationError(
                    _("A VAT-registered profile requires explicit approved input and output tax mappings.")
                )

    def action_configure(self):
        if not (
            self.env.user.has_group("thirdcode_accounting.group_thirdcode_accountant")
            or self.env.user.has_group("thirdcode_accounting.group_thirdcode_administrator")
        ):
            raise AccessError(_("Only an Accountant or Administrator may configure tax profiles."))
        for profile in self:
            if not profile.accountant_owner or not profile.notes:
                raise UserError(_("Tax configuration requires an owner and an approved basis note."))
            profile.write(
                {
                    "status": "configured",
                    "approved_by": self.env.user.id,
                    "approved_at": fields.Datetime.now(),
                }
            )
        return True

    def action_reset_to_assessment(self):
        if not self.env.user.has_group("thirdcode_accounting.group_thirdcode_administrator"):
            raise AccessError(_("Only an Administrator may reset tax assessment status."))
        self.write({"status": "assessment_required", "approved_by": False, "approved_at": False})
        return True
