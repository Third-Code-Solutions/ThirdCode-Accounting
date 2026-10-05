"""One server-side authority check for platform-only operations."""
from odoo import SUPERUSER_ID, _, api, fields, models, Command
from odoo.exceptions import AccessError

OWNER_GROUP = "thirdcode_accounting.group_thirdcode_platform_console"


def is_platform_owner(env):
    # uid=1 is the trusted installer/setup operator, not a company administrator.
    user = env.user
    return env.uid == SUPERUSER_ID or bool(
        user.sudo().thirdcode_platform_owner
        and user.has_group("base.group_system")
        and user.has_group(OWNER_GROUP)
    )


def require_platform_owner(env):
    if not is_platform_owner(env):
        raise AccessError(_("The platform console is reserved to the system owner."))


class PlatformCompany(models.Model):
    _inherit = "res.company"

    thirdcode_is_platform = fields.Boolean(default=False, copy=False, groups="base.group_system")

    thirdcode_provisioning_key = fields.Char(copy=False, index=True, groups="base.group_system")
    _sql_constraints = [("platform_provisioning_key_unique", "unique(thirdcode_provisioning_key)",
                         "Organization request already processed.")]

    @api.model_create_multi
    def create(self, values_list):
        if any(v.get("thirdcode_is_platform", self.env.context.get("default_thirdcode_is_platform")) for v in values_list):
            require_platform_owner(self.env)
        self.check_access("create")
        # Native create links the new company to the acting user before returning.
        # Only an already-authorized owner uses the installer for that native step.
        creator = self.with_user(SUPERUSER_ID) if is_platform_owner(self.env) else self
        companies = super(PlatformCompany, creator).create(values_list)
        home = self.env.ref("thirdcode_accounting.company_platform", raise_if_not_found=False)
        if home:
            # Native company creation can automatically extend system users' scope.
            owners = self.env["res.users"].with_user(SUPERUSER_ID).search([("thirdcode_platform_owner", "=", True)])
            owners.write({"company_id": home.id, "company_ids": [Command.set(home.ids)]})
        return companies

    def write(self, values):
        if "thirdcode_is_platform" in values:
            require_platform_owner(self.env)
        return super().write(values)


class PlatformUser(models.Model):
    _inherit = "res.users"

    @api.model_create_multi
    def create(self, values_list):
        if any(v.get("thirdcode_platform_owner", self.env.context.get("default_thirdcode_platform_owner")) for v in values_list):
            require_platform_owner(self.env)
        home = self.env.ref("thirdcode_accounting.company_platform", raise_if_not_found=False)
        values_list = [dict(values) for values in values_list]
        if home:
            for values in values_list:
                if values.get("thirdcode_platform_owner", self.env.context.get("default_thirdcode_platform_owner")):
                    values.update(company_id=home.id, company_ids=[Command.set(home.ids)])
        return super().create(values_list)

    def write(self, values):
        if "thirdcode_platform_owner" in values or (
            {"groups_id", "company_id", "company_ids", "active", "password"}.intersection(values)
            and self.sudo().filtered("thirdcode_platform_owner")
        ):
            require_platform_owner(self.env)
        home = self.env.ref("thirdcode_accounting.company_platform", raise_if_not_found=False)
        if values.get("thirdcode_platform_owner") and home:
            values = dict(values, company_id=home.id, company_ids=[Command.set(home.ids)])
        result = super().write(values)
        if home and {"company_id", "company_ids"}.intersection(values):
            for user in self.sudo().filtered("thirdcode_platform_owner"):
                if user.company_id != home or user.company_ids != home:
                    raise AccessError(_("Platform owners cannot be members of customer organizations."))
        return result
