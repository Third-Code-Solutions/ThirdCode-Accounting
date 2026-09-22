from odoo import Command
from lxml import etree
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAppLauncher(TransactionCase):
    def test_apps_route_is_customer_launcher(self):
        for xmlid in ("account.view_invoice_tree", "account.view_move_tree", "hr_expense.hr_expense_view_expenses_analysis_tree"):
            view = self.env.ref(xmlid)
            arch = self.env[view.model].get_view(view.id, "list")["arch"]
            self.assertEqual(etree.fromstring(arch).get("sample"), "0")
        action = self.env.ref("thirdcode_accounting.action_tcsi_apps")
        self.assertEqual(action.path, "apps")
        self.assertEqual(action.tag, "tcsi_apps")
        self.assertEqual(self.env.ref("base.open_module_tree").path, "technical-modules")
        self.assertEqual(self.env.ref("base.menu_management").action, action)

    def test_business_roles_do_not_gain_system_administration(self):
        for role in ("administrator", "accountant", "encoder", "readonly"):
            user = self.env["res.users"].create({
                "name": f"Launcher {role}", "login": f"launcher-test-{role}",
                "groups_id": [Command.set([self.env.ref(f"thirdcode_accounting.group_thirdcode_{role}").id])],
            })
            self.assertFalse(user.has_group("base.group_system"))
            visible = self.env["ir.ui.menu"].with_user(user)._visible_menu_ids()
            self.assertIn(self.env.ref("base.menu_management").id, visible)
            self.assertNotIn(self.env.ref("base.menu_module_tree").id, visible)

    def test_external_marketplace_entries_are_not_customer_navigation(self):
        for xmlid in ("base.menu_third_party", "base.menu_theme_store", "base.theme_store"):
            self.assertFalse(self.env.ref(xmlid).active)
