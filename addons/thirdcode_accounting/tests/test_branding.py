import re

from lxml import etree

from odoo.tests import TransactionCase, tagged
from odoo.tools import file_open


@tagged("post_install", "-at_install")
class TestChatBranding(TransactionCase):
    """Every stored message body must be free of the old brand at create time."""

    def _post(self, body):
        return self.env["mail.message"].create({
            "body": body,
            "message_type": "comment",
            "subtype_id": self.env.ref("mail.mt_note").id,
            "model": "res.partner",
            "res_id": self.env.user.partner_id.id,
        })

    def test_welcome_copy_is_rebranded_at_create(self):
        message = self._post(
            "<p>Hello,<br>Odoo's chat helps employees collaborate efficiently. "
            "I'm here to help you discover its features.</p>"
        )
        self.assertIn("TCSI's chat helps employees collaborate efficiently.", message.body)
        self.assertNotIn("Odoo", message.body)

    def test_bot_references_and_links_are_rebranded(self):
        message = self._post(
            "<p>The bot used to be OdooBot — check "
            '<a href="https://www.odoo.com/documentation/18.0">our docs</a>.</p>'
        )
        self.assertIn("TCSI Workspace Assistant", message.body)
        self.assertIn("https://www.thirdcodesolutions.com", message.body)
        self.assertNotIn("OdooBot", message.body)
        self.assertNotIn("odoo.com", message.body)

    def test_link_text_and_lowercase_brand_are_rebranded(self):
        message = self._post(
            '<p>Welcome to odoo. See <a href="https://thirdcodesolutions.com">odoo.com</a>.</p>'
        )
        self.assertNotIn("odoo", message.body.lower())
        self.assertIn("thirdcodesolutions.com", message.body)

    def test_subject_is_rebranded_at_create(self):
        message = self.env["mail.message"].create({
            "subject": "Welcome to Odoo!",
            "body": "<p>hello</p>",
            "message_type": "comment",
            "subtype_id": self.env.ref("mail.mt_note").id,
            "model": "res.partner",
            "res_id": self.env.user.partner_id.id,
        })
        self.assertEqual(message.subject, "Welcome to TCSI!")

    def test_clickable_command_hook_survives_branding(self):
        # `o_odoobot_command` is invisible client plumbing, not brand: the
        # sanitizer must leave it alone or the emoji-command links break.
        message = self._post('<p>Try <span class="o_odoobot_command">:)</span> today.</p>')
        self.assertIn('class="o_odoobot_command"', message.body)
        self.assertIn(":)", message.body)

    def test_unrelated_bodies_are_untouched(self):
        body = "<p>Receipt RCPT/2026/0001 was paid in full.</p>"
        self.assertEqual(self._post(body).body, body)


@tagged("post_install", "-at_install")
class TestThemeBeforePaint(TransactionCase):
    def test_layout_head_applies_the_theme_key_used_by_the_toggle(self):
        with file_open("thirdcode_accounting/static/src/js/tcsi_theme.js") as script:
            key = re.search(r'STORAGE_KEY = "([^"]+)"', script.read()).group(1)
        arch = self.env.ref("web.layout")._get_combined_arch()
        head = etree.tostring(arch.find(".//head"), encoding="unicode")
        self.assertIn(f'localStorage.getItem("{key}")', head)
        self.assertIn("dataset.tcsiTheme = tcsiTheme", head)
