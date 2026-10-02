"""Organization and employee account management.

Organization administrators manage the accounts of their own company
(create employees, reset passwords, enable/disable accounts). The
platform owner (``base.group_system``) may manage any organization,
including provisioning new company baselines.
"""
from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError

from .setup_service import TRIAL_ROLE_GROUPS

ADMIN_GROUP = "thirdcode_accounting.group_thirdcode_administrator"
SYSTEM_GROUP = "base.group_system"

ROLE_SELECTION = [
    ("administrator", "Administrator"),
    ("accountant", "Accountant"),
    ("encoder", "Encoder"),
    ("readonly", "Read-only"),
]

MIN_PASSWORD_LENGTH = 8


class ThirdcodeEmployeeWizard(models.TransientModel):
    _name = "thirdcode.employee.wizard"
    _description = "Create an employee account"

    name = fields.Char(string="Full name", required=True)
    login = fields.Char(string="Login (email or username)", required=True)
    role = fields.Selection(ROLE_SELECTION, string="Role", required=True, default="accountant")
    password = fields.Char(string="Initial password", required=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        groups=SYSTEM_GROUP,
        default=lambda self: self.env.company,
    )

    def _target_company(self):
        self.ensure_one()
        if self.env.user.has_group(SYSTEM_GROUP):
            return self.company_id or self.env.company
        return self.env.company

    def action_create_employee(self):
        self.ensure_one()
        if not self.env.user.has_group(SYSTEM_GROUP) and not self.env.user.has_group(ADMIN_GROUP):
            raise AccessError(_("Only company administrators can create employee accounts."))
        if len((self.password or "").strip()) < MIN_PASSWORD_LENGTH:
            raise UserError(_("Use a password with at least %s characters.") % MIN_PASSWORD_LENGTH)
        company = self._target_company()
        if not company:
            raise UserError(_("Choose a company for this account."))
        provisioned = (
            self.env["thirdcode.setup.service"]
            .sudo()
            .provision_user(
                login=self.login,
                name=self.name,
                password=self.password,
                company=company,
                role=self.role,
                require_new=True,
            )
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Employee Accounts"),
            "res_model": "res.users",
            "view_mode": "list",
            "views": [[self.env.ref("thirdcode_accounting.view_thirdcode_employee_list").id, "list"]],
            "domain": [("id", "=", provisioned["uid"])],
            "target": "current",
        }


class ThirdcodeEmployeePasswordWizard(models.TransientModel):
    _name = "thirdcode.employee.password.wizard"
    _description = "Reset an employee password"

    user_id = fields.Many2one("res.users", string="Employee", required=True, ondelete="cascade")
    new_password = fields.Char(string="New password", required=True)

    def action_reset_password(self):
        self.ensure_one()
        target = self.user_id
        if not self.env.user.has_group(SYSTEM_GROUP):
            if not self.env.user.has_group(ADMIN_GROUP):
                raise AccessError(_("Only company administrators can reset passwords."))
            if not (set(target.company_ids.ids) & set(self.env.user.company_ids.ids)):
                raise AccessError(_("You can only manage accounts of your own company."))
        if len((self.new_password or "").strip()) < MIN_PASSWORD_LENGTH:
            raise UserError(_("Use a password with at least %s characters.") % MIN_PASSWORD_LENGTH)
        target.sudo().write({"password": self.new_password})
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "title": _("Password updated"),
                "message": _(
                    "Share the new password with %(name)s directly. The system does not send emails."
                )
                % {"name": target.name},
                "sticky": False,
            },
        }


class ResUsers(models.Model):
    _inherit = "res.users"

    def action_thirdcode_toggle_active(self):
        for user in self:
            if not self.env.user.has_group(SYSTEM_GROUP):
                if not self.env.user.has_group(ADMIN_GROUP):
                    raise AccessError(_("Only company administrators can enable or disable accounts."))
                if user.id == self.env.user.id:
                    raise UserError(_("You cannot disable your own account."))
                if not (set(user.company_ids.ids) & set(self.env.user.company_ids.ids)):
                    raise AccessError(_("You can only manage accounts of your own company."))
            user.sudo().write({"active": not user.active})
        return True


class ResCompany(models.Model):
    _inherit = "res.company"

    def action_thirdcode_provision_baseline(self):
        self.ensure_one()
        if not self.env.user.has_group(SYSTEM_GROUP):
            raise AccessError(_("Only the platform owner can provision an organization baseline."))
        result = (
            self.env["thirdcode.setup.service"]
            .sudo()
            ._action_ensure_baseline({"company_id": self.id})
        )
        steps = "; ".join(result.get("steps") or [])[:400]
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "title": _("Baseline provisioned"),
                "message": _("%(company)s: %(steps)s")
                % {"company": self.name, "steps": steps},
                "sticky": False,
            },
        }
