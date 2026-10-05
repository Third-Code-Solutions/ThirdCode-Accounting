import json

from dateutil.relativedelta import relativedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPlatformConsole(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.console = cls.env["thirdcode.platform.console"]
        cls.main_company = cls.env.company
        cls.owner = cls.env["res.users"].sudo().create(
            {
                "name": "Console Owner",
                "login": "console-owner",
                "thirdcode_platform_owner": True,
                "company_id": cls.env.ref("thirdcode_accounting.company_platform").id,
                "company_ids": [Command.set(cls.env.ref("thirdcode_accounting.company_platform").ids)],
                "groups_id": [
                    Command.set(
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("base.group_system").id,
                            cls.env.ref("thirdcode_accounting.group_thirdcode_platform_console").id,
                        ]
                    )
                ],
            }
        )
        cls.company_a = cls.env["res.company"].sudo().create({"name": "Console Tenant A"})
        cls.company_b = cls.env["res.company"].sudo().create({"name": "Console Tenant B"})
        cls.tenant_admin = cls.env["res.users"].sudo().create(
            {
                "name": "Console Tenant Admin",
                "login": "console-tenant-admin",
                "company_id": cls.company_b.id,
                "company_ids": [Command.set([cls.company_b.id])],
                "groups_id": [Command.set([cls.env.ref("thirdcode_accounting.group_thirdcode_administrator").id])],
            }
        )
        cls.staff_b = cls.env["res.users"].sudo().create(
            {
                "name": "Console Tenant B Staff",
                "login": "console-staff-b",
                "company_id": cls.company_b.id,
                "company_ids": [Command.set([cls.company_b.id])],
                "groups_id": [Command.set([cls.env.ref("thirdcode_accounting.group_thirdcode_encoder").id])],
            }
        )
        cls.never_user = cls.env["res.users"].sudo().create(
            {
                "name": "Console Never Signed",
                "login": "console-never-signed",
                "company_id": cls.company_a.id,
                "company_ids": [Command.set([cls.company_a.id])],
                "groups_id": [Command.set([cls.env.ref("thirdcode_accounting.group_thirdcode_readonly").id])],
            }
        )
        partner = cls.env["res.partner"].sudo().create({"name": "Console Test Customer"})
        cls.move = cls.env["account.move"].sudo().create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_line_ids": [Command.create({"name": "Console line", "quantity": 1, "price_unit": 250.0})],
            }
        )
        cls.move.action_post()

    def _data(self, user=None):
        return self.console.with_user(user or self.owner).get_console_data()

    def test_access_is_restricted_to_platform_owners(self):
        with self.assertRaises(AccessError):
            self.console.with_user(self.tenant_admin).get_console_data()
        with self.assertRaises(AccessError):
            self.console.with_user(self.tenant_admin).extend_trial(self.company_b.id, 7)
        data = self._data()
        for key in ("kpis", "trend", "alerts", "organizations", "activity", "system", "generated_at"):
            self.assertIn(key, data)
        self.assertEqual(len(data["trend"]), 14)

    def test_menu_and_action_are_gated(self):
        action = self.env.ref("thirdcode_accounting.action_thirdcode_platform_console")
        self.assertEqual(action.tag, "tcsi_platform_console")
        self.assertEqual(action.path, "console")
        menu = self.env.ref("thirdcode_accounting.menu_thirdcode_platform_console")
        visible = self.env["ir.ui.menu"].with_user(self.owner)._visible_menu_ids()
        self.assertIn(menu.id, visible)
        hidden = self.env["ir.ui.menu"].with_user(self.tenant_admin)._visible_menu_ids()
        self.assertNotIn(menu.id, hidden)

    def test_company_metrics_and_alerts(self):
        data = self._data()
        rows = {row["id"]: row for row in data["organizations"]}
        main = rows[self.main_company.id]
        self.assertGreaterEqual(main["docs"], 1)
        self.assertGreaterEqual(main["docs_week"], 1)
        self.assertGreaterEqual(main["users"], 1)
        row_a = rows[self.company_a.id]
        self.assertEqual(row_a["users"], 1)
        self.assertEqual(row_a["never_signed"], 1)
        self.assertFalse(row_a["baseline_ready"])
        alerts_a = [alert["title"] for alert in data["alerts"] if alert["company_id"] == self.company_a.id]
        self.assertTrue(any("Baseline incomplete" in title for title in alerts_a))
        self.assertTrue(any("never signed in" in title for title in alerts_a))
        documents = data["activity"]["documents"]
        self.assertTrue(any(doc["ref"] == self.move.name for doc in documents))

    def test_trial_lifecycle_actions(self):
        today = fields.Date.context_today(self.console)
        self.company_a.write(
            {
                "thirdcode_platform_status": "trial",
                "thirdcode_trial_start": today - relativedelta(days=32),
                "thirdcode_trial_end": today - relativedelta(days=2),
            }
        )
        data = self._data()
        alerts_a = [alert["title"] for alert in data["alerts"] if alert["company_id"] == self.company_a.id]
        self.assertTrue(any("Trial expired" in title for title in alerts_a))
        result = self.console.with_user(self.owner).extend_trial(self.company_a.id, 7)
        self.assertEqual(result["days_left"], 7)
        self.assertEqual(self.company_a.thirdcode_trial_end, today + relativedelta(days=7))
        self.console.with_user(self.owner).convert_to_active(self.company_a.id)
        self.assertEqual(self.company_a.thirdcode_platform_status, "active")
        self.assertFalse(self.company_a.thirdcode_trial_mode)
        data = self._data()
        alerts_a = [alert["title"] for alert in data["alerts"] if alert["company_id"] == self.company_a.id]
        self.assertFalse(any("Trial" in title for title in alerts_a))
        self.console.with_user(self.owner).mark_trial(self.company_a.id, 30)
        self.company_a.invalidate_recordset()
        self.assertEqual(self.company_a.thirdcode_platform_status, "trial")
        self.assertTrue(self.company_a.thirdcode_trial_mode)
        self.assertEqual(
            (self.company_a.thirdcode_trial_end - fields.Date.context_today(self.console)).days, 30
        )
        with self.assertRaises(UserError):
            self.console.with_user(self.owner).extend_trial(self.company_a.id, 0)

    def test_suspend_and_resume(self):
        result = self.console.with_user(self.owner).suspend_company(self.company_b.id)
        suspended = json.loads(self.company_b.thirdcode_suspended_user_ids)
        self.assertEqual(result["deactivated"], len(suspended))
        self.assertIn(self.tenant_admin.id, suspended)
        self.assertIn(self.staff_b.id, suspended)
        self.assertNotIn(self.owner.id, suspended)
        self.assertFalse(self.tenant_admin.active)
        self.assertFalse(self.staff_b.active)
        self.assertTrue(self.owner.active)
        self.assertEqual(self.company_b.thirdcode_platform_status, "suspended")
        result = self.console.with_user(self.owner).resume_company(self.company_b.id)
        self.assertEqual(result["restored"], len(suspended))
        self.assertTrue(self.tenant_admin.active)
        self.assertTrue(self.staff_b.active)
        self.assertEqual(self.company_b.thirdcode_platform_status, "trial")
        self.assertFalse(self.company_b.thirdcode_suspended_user_ids)

    def test_open_company_actions(self):
        action = self.console.with_user(self.owner).open_organization(self.company_a.id)
        self.assertEqual(action["tag"], "tcsi_platform_console")
        self.assertEqual(action["params"]["company_id"], self.company_a.id)
        users_action = self.console.with_user(self.owner).open_company_users(self.company_a.id)
        self.assertEqual(users_action["params"]["tab"], "people")

    def test_provisioning_grants_console_group_to_platform_owners(self):
        self.env["thirdcode.setup.service"].sudo()._provision_user(
            login="console-provisioned-owner",
            name="Provisioned Owner",
            password="Console-Owner-Pass1",
            company=self.main_company,
            role="administrator",
            extra_group_xmlids=["base.group_system"],
            all_companies=True,
            regroup=True,
        )
        user = self.env["res.users"].sudo().search([("login", "=", "console-provisioned-owner")])
        self.assertTrue(user.has_group("thirdcode_accounting.group_thirdcode_platform_console"))
        self.assertTrue(user.thirdcode_platform_owner)
