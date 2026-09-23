from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class TaxProfile(models.Model):
    _name = "thirdcode.tax.profile"
    _description = "Third Code Tax Configuration Profile"
    _inherit = ["mail.thread", "mail.activity.mixin", "thirdcode.workflow.guard.mixin"]
    _order = "effective_date desc, id desc"
    _check_company_auto = True
    _workflow_state_field = "status"
    _workflow_initial_state = "assessment_required"
    _workflow_protected_fields = frozenset(
        {"status", "approved_by", "approved_at"}
    )

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
    output_vat_tax_id = fields.Many2one(
        "account.tax", string="Output VAT tax", check_company=True
    )
    input_vat_tax_id = fields.Many2one(
        "account.tax", string="Input VAT tax", check_company=True
    )
    withholding_tax_ids = fields.Many2many(
        "account.tax", string="Withholding taxes", check_company=True
    )
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
        self.check_access("write")
        for profile in self:
            if profile.status != "assessment_required":
                raise UserError(
                    _("Reset the configured profile to assessment before approving changes.")
                )
            if not profile.accountant_owner or not profile.notes:
                raise UserError(_("Tax configuration requires an owner and an approved basis note."))
            profile.sudo().write(
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
        self.check_access("write")
        self.sudo().write(
            {
                "status": "assessment_required",
                "approved_by": False,
                "approved_at": False,
            }
        )
        return True

    def write(self, vals):
        approved_fields = {
            "name",
            "company_id",
            "vat_registered",
            "output_vat_tax_id",
            "input_vat_tax_id",
            "withholding_tax_ids",
            "effective_date",
            "accountant_owner",
            "notes",
        }
        if not self.env.su and approved_fields.intersection(vals) and any(
            profile.status == "configured" for profile in self
        ):
            raise UserError(
                _("A configured tax profile is immutable. Reset it to assessment before making changes.")
            )
        return super().write(vals)
