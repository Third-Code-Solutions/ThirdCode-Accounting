from odoo.tests import TransactionCase, tagged


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

    def test_clickable_command_hook_survives_branding(self):
        # `o_odoobot_command` is invisible client plumbing, not brand: the
        # sanitizer must leave it alone or the emoji-command links break.
        message = self._post('<p>Try <span class="o_odoobot_command">:)</span> today.</p>')
        self.assertIn('class="o_odoobot_command"', message.body)
        self.assertIn(":)", message.body)

    def test_unrelated_bodies_are_untouched(self):
        body = "<p>Receipt RCPT/2026/0001 was paid in full.</p>"
        self.assertEqual(self._post(body).body, body)
