import base64
import re

from odoo import api, fields, models
from odoo.tools import file_open


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
    body = re.sub(r"\bodoo\.com\b", "thirdcodesolutions.com", body, flags=re.IGNORECASE)
    return re.sub(r"\bodoo\b", "TCSI", body, flags=re.IGNORECASE)


def brand_chat_body(body):
    """Rebrand Odoo references inside stored message text — bodies, subjects,
    bot welcome texts, fallback replies, and their links — so no future chat,
    preview, or notification can surface the old brand again.

    The word-boundary rules deliberately leave `o_odoobot_command` alone: that
    class is invisible styling plumbing (the client draws the emoji command
    chip with it), so renaming it in a body would break the chip, not the brand.
    """
    if not body or "odoo" not in body.lower():
        return body
    body = re.sub(r"https?://(?:www\.)?odoo\.com[^\s\"'<]*", "https://www.thirdcodesolutions.com", body)
    body = re.sub(r"\bodoo\.com\b", "thirdcodesolutions.com", body, flags=re.IGNORECASE)
    body = body.replace("OdooBot", "TCSI Workspace Assistant")
    return re.sub(r"\bodoo\b", "TCSI", body, flags=re.IGNORECASE)


class CompanyBranding(models.Model):
    _inherit = "res.company"

    @api.model
    def _apply_tcsi_invitation_branding(self):
        # Private migration entry point: not callable through external RPC.
        with file_open("thirdcode_accounting/static/src/img/orvexa-avatar.png", "rb") as avatar:
            self.env.ref("base.partner_root").write({
                "name": "TCSI Workspace Assistant",
                "image_1920": base64.b64encode(avatar.read()),
            })
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


class UserBranding(models.Model):
    _inherit = "res.users"

    notification_type = fields.Selection(
        selection_add=[("inbox", "Handle in TCSI")],
        help="Choose email delivery or notifications in your TCSI workspace inbox.",
    )
    odoobot_state = fields.Selection(string="Workspace Assistant Status")


class MailMessageBranding(models.Model):
    _inherit = "mail.message"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("body"):
                vals["body"] = brand_chat_body(vals["body"])
            if vals.get("subject"):
                vals["subject"] = brand_chat_body(vals["subject"])
        return super().create(vals_list)
