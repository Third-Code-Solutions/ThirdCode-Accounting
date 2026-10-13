from lxml import etree
from odoo.tests import TransactionCase, tagged

from ..models.settings import tcsi_settings_arch


@tagged("post_install", "-at_install")
class TestTcsiSettings(TransactionCase):
    def test_native_settings_keep_essential_controls_without_promotions(self):
        result = self.env["res.config.settings"].get_view(view_type="form")
        arch = etree.fromstring(result["arch"])
        app = arch.xpath("//app[@name='general_settings']")[0]
        self.assertEqual(app.get("string"), "TCSI Settings")
        fields = set(app.xpath(".//field/@name"))
        self.assertTrue({"company_id", "active_user_count", "language_count",
                         "external_email_server_default", "auth_signup_reset_password",
                         "user_default_rights", "restrict_template_rendering",
                         "module_auth_oauth", "module_auth_ldap",
                         "module_google_recaptcha", "module_website_cf_turnstile"} <= fields)
        self.assertFalse({"digest_id", "digest_emails", "tenor_api_key",
                          "sfu_server_key", "module_web_unsplash",
                          "module_base_geolocalize", "module_product_images",
                          "module_partner_autocomplete", "product_weight_in_lbs"} & fields)
        self.assertTrue(app.xpath(".//setting[@id='document_layout_setting']//button"))
        self.assertTrue(app.xpath(".//setting[@id='activities_setting']//button"))
        self.assertTrue(app.xpath(".//setting[@id='tcsi_about']"))
        self.assertFalse(app.xpath(".//widget[@name='res_config_dev_tool' or @name='res_config_edition']"))
        self.assertNotIn("odoo", etree.tostring(app).decode().lower())

    def test_curation_preserves_other_apps_modifiers_and_source_tree(self):
        arch = etree.fromstring('''<form><app name="general_settings">
            <block id="emails"><setting id="email_servers_setting" invisible="not allowed" groups="base.group_system">
                <field name="external_email_server_default"/><button name="existing" type="object"/>
            </setting><setting id="digest"><field name="digest_id"/></setting></block>
            </app><app name="account"><block><setting id="essential_accounting"><field name="tax_id"/></setting></block></app></form>''')
        before = etree.tostring(arch)
        result = tcsi_settings_arch(arch)
        self.assertEqual(etree.tostring(arch), before)
        self.assertEqual(etree.tostring(result.xpath("//app[@name='account']")[0]),
                         etree.tostring(arch.xpath("//app[@name='account']")[0]))
        self.assertEqual(result.xpath("//setting[@id='email_servers_setting']")[0].attrib,
                         dict(arch.xpath("//setting[@id='email_servers_setting']")[0].attrib,
                              title="Configure email delivery and receiving for TCSI Accounting."))
        self.assertEqual(result.xpath("//button/@name"), ["existing"])
        self.assertEqual(etree.tostring(tcsi_settings_arch(result)), etree.tostring(result))
