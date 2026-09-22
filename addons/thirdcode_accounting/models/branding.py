import re

from odoo import api, models


def brand_invitation(body):
    """Brand only the three bundled invitation templates, never sent messages."""
    body = re.sub(
        r"Never heard of Odoo\?.*?productivity\.",
        "TCSI Accounting is your team's workspace for accounting and financial control.",
        body, flags=re.DOTALL,
    )
    body = re.sub(r"https?://(?:www\.)?odoo\.com[^\s\"<]*", "https://www.thirdcodesolutions.com", body)
    body = body.replace("http://yourcompany.odoo.com", "https://your-workspace.example")
    body = body.replace("OdooBot", "TCSI Workspace Assistant")
    return re.sub(r"\bOdoo\b", "TCSI", body)


class CompanyBranding(models.Model):
    _inherit = "res.company"

    @api.model
    def _apply_tcsi_invitation_branding(self):
        # Private migration entry point: not callable through external RPC.
        for xmlid in (
            "auth_signup.set_password_email",
            "auth_signup.mail_template_user_signup_account_created",
            "portal.mail_template_data_portal_welcome",
        ):
            template = self.env.ref(xmlid)
            body = template.with_context(lang="en_US").body_html or ""
            branded = brand_invitation(body)
            if branded != body:
                template.with_context(lang="en_US").write({"body_html": branded})
