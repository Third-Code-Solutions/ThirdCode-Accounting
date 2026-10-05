from odoo import SUPERUSER_ID, Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestTrialMode(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        # A report layout view must be selected, otherwise report_action()
        # returns the document-layout configurator action instead of the report.
        cls.company.sudo().write(
            {
                "thirdcode_trial_mode": True,
                "external_report_layout_id": cls.env.ref("web.external_layout_standard").id,
            }
        )

    def _posted_invoice(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "company_id": self.company.id,
                "journal_id": self.company_data["default_journal_sale"].id,
                "partner_id": self.partner_a.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Trial mode test item",
                            "quantity": 1,
                            "price_unit": 100,
                            "account_id": self.company_data["default_account_revenue"].id,
                        }
                    )
                ],
            }
        )
        invoice.action_post()
        return invoice

    def test_invoice_print_allowed_in_trial_mode_and_blocked_without(self):
        invoice = self._posted_invoice()

        action = invoice.action_print_thirdcode_invoice()
        self.assertEqual(action["type"], "ir.actions.report")

        self.company.sudo().write({"thirdcode_trial_mode": False})
        with self.assertRaises(UserError):
            invoice.action_print_thirdcode_invoice()

    def test_receipt_print_allowed_in_trial_mode_and_blocked_without(self):
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner_a.id,
                "amount": 50,
                "journal_id": self.company_data["default_journal_bank"].id,
                "company_id": self.company.id,
            }
        )
        payment.action_post()

        action = payment.action_print_thirdcode_receipt()
        self.assertEqual(action["type"], "ir.actions.report")

        self.company.sudo().write({"thirdcode_trial_mode": False})
        with self.assertRaises(UserError):
            payment.action_print_thirdcode_receipt()

    def test_financial_report_layout_status_follows_trial_mode(self):
        def wizard():
            return self.env["thirdcode.financial.report.wizard"].create(
                {
                    "report_type": "balance_sheet",
                    "company_id": self.company.id,
                    "date_from": fields.Date.today().replace(month=1, day=1),
                    "date_to": fields.Date.today(),
                }
            )

        self.assertEqual(wizard().report_status, "trial")
        self.assertIn("TRIAL COPY", wizard().get_report_data()["layout_status"])

        self.company.sudo().write({"thirdcode_trial_mode": False})
        self.assertEqual(wizard().report_status, "draft")
        self.assertIn("DRAFT LAYOUT", wizard().get_report_data()["layout_status"])

    def test_setup_service_requires_token_context(self):
        service = self.env["thirdcode.setup.service"].with_user(SUPERUSER_ID)

        with self.assertRaises(AccessError):
            service.dispatch("status", {})

        result = service.with_context(tcsi_setup_token_ok=True).dispatch("status", {})
        self.assertIn("companies", result)
        self.assertIn("users", result)

        with self.assertRaises(UserError):
            service.with_context(tcsi_setup_token_ok=True).dispatch("not-an-action", {})

    def test_setup_service_create_user_and_batch(self):
        company = self.env["res.company"].sudo().create({"name": "Trial service company"})
        service = self.env["thirdcode.setup.service"].with_user(SUPERUSER_ID).with_context(tcsi_setup_token_ok=True)

        result = service.dispatch(
            "create_user",
            {
                "login": "trial-service-admin@example.invalid",
                "name": "Trial service admin",
                "password": "trial-service-secret",
                "company_id": company.id,
                "role": "administrator",
            },
        )
        self.assertEqual(result["action"], "created")
        user = self.env["res.users"].browse(result["uid"])
        self.assertIn(
            self.env.ref("thirdcode_accounting.group_thirdcode_administrator"),
            user.groups_id,
        )
        self.assertEqual(user.company_ids, company)

        rerun = service.dispatch(
            "create_user",
            {
                "login": "trial-service-admin@example.invalid",
                "name": "Trial service admin",
                "company_id": company.id,
                "role": "administrator",
            },
        )
        self.assertEqual(rerun["action"], "updated")
        self.assertEqual(rerun["uid"], result["uid"])

        batch = service.dispatch(
            "batch",
            {
                "actions": [
                    {"action": "ping"},
                    {"action": "unknown-action"},
                ]
            },
        )
        outcomes = batch["results"]
        self.assertTrue(outcomes[0]["ok"])
        self.assertFalse(outcomes[1]["ok"])

    def test_setup_service_period_and_journal_helpers(self):
        company = self.env["res.company"].sudo().create({"name": "Trial period company"})
        service = self.env["thirdcode.setup.service"].with_user(SUPERUSER_ID).with_context(tcsi_setup_token_ok=True)

        journal_steps = service._ensure_journals(company)
        self.assertTrue(any("journals created" in step for step in journal_steps))
        self.assertEqual(
            self.env["account.journal"].sudo().search_count([("company_id", "=", company.id)]),
            5,
        )

        period_steps = service._ensure_period(company, {})
        self.assertTrue(any("created open period" in step for step in period_steps))
        self.assertEqual(
            self.env["thirdcode.accounting.period"].sudo().search_count(
                [("company_id", "=", company.id), ("state", "=", "open")]
            ),
            1,
        )

        rerun_steps = service._ensure_period(company, {})
        self.assertTrue(any("reused" in step for step in rerun_steps))

    def test_maintenance_locks_reports_backends(self):
        service = self.env["thirdcode.setup.service"].with_user(SUPERUSER_ID).with_context(tcsi_setup_token_ok=True)
        result = service._action_maintenance({"op": "locks"})
        self.assertIn("backends", result)
        self.assertIsInstance(result["backends"], list)

    def test_receipt_sequence_is_per_company(self):
        company_b = self.env["res.company"].sudo().create({"name": "Second Trial Company"})
        sequence = company_b._thirdcode_receipt_sequence()
        self.assertEqual(sequence.company_id, company_b)
        self.assertEqual(sequence.number_next_actual, 1)
        with self.assertRaises(UserError):
            sequence.next_by_id()
        self.assertEqual(company_b._thirdcode_receipt_sequence(), sequence)  # idempotent

        # the original company keeps its own sequence, independent numbering
        sequence_a = self.company._thirdcode_receipt_sequence()
        self.assertNotEqual(sequence_a, sequence)
        self.assertEqual(sequence_a.prefix, "OR/")
        with self.assertRaises(UserError):
            sequence_a.next_by_id()

    def _provision_admin(self, login, company):
        result = (
            self.env["thirdcode.setup.service"]
            .sudo()
            ._action_create_user(
                {
                    "login": login,
                    "name": login,
                    "password": "Passw0rd-%s" % login,
                    "company_id": company.id,
                    "role": "administrator",
                    "regroup": True,
                }
            )
        )
        return self.env["res.users"].sudo().browse(result["uid"])

    def test_organization_administrator_manages_own_company_users(self):
        company_b = self.env["res.company"].sudo().create({"name": "Tenant B"})
        admin_a = self._provision_admin("tenant-a-admin", self.company)
        admin_b = self._provision_admin("tenant-b-admin", company_b)

        # User records are only visible inside the administrator's companies.
        visible_a = self.env["res.users"].with_user(admin_b).search([("id", "=", admin_a.id)])
        self.assertFalse(visible_a)
        own = self.env["res.users"].with_user(admin_b).search([("id", "=", admin_b.id)])
        self.assertEqual(own.ids, [admin_b.id])

        # The administrator creates an employee account through the wizard.
        wizard = (
            self.env["thirdcode.employee.wizard"]
            .with_user(admin_b)
            .create(
                {
                    "name": "Tenant B Staff",
                    "login": "tenant-b-staff",
                    "role": "accountant",
                    "password": "Staff-Passw0rd",
                }
            )
        )
        wizard.action_create_employee()
        staff = self.env["res.users"].sudo().search([("login", "=", "tenant-b-staff")])
        self.assertEqual(staff.company_id, company_b)
        self.assertEqual(staff.company_ids.ids, [company_b.id])
        self.assertTrue(staff.has_group("thirdcode_accounting.group_thirdcode_accountant"))

        # An existing login from another company is never reassigned.
        duplicate = (
            self.env["thirdcode.employee.wizard"]
            .with_user(admin_b)
            .create(
                {
                    "name": "Impostor",
                    "login": admin_a.login,
                    "role": "administrator",
                    "password": "Impostor-Pass1",
                }
            )
        )
        with self.assertRaises(UserError):
            duplicate.action_create_employee()

        # Password resets: own company allowed, other companies denied.
        # res.users.password is write-only in Odoo 18 (reads return ''), so
        # compare the stored hash directly at the database layer.
        def password_hash():
            self.env.cr.execute("SELECT password FROM res_users WHERE id = %s", (staff.id,))
            return self.env.cr.fetchone()[0]

        before = password_hash()
        reset_own = (
            self.env["thirdcode.employee.password.wizard"]
            .with_user(admin_b)
            .create({"user_id": staff.id, "new_password": "Staff-NewPass1"})
        )
        reset_own.action_reset_password()
        self.assertNotEqual(password_hash(), before)
        with self.assertRaises(UserError):
            reset_cross = (
                self.env["thirdcode.employee.password.wizard"]
                .with_user(admin_b)
                .create({"user_id": admin_a.id, "new_password": "Cross-Passw0rd"})
            )
            reset_cross.action_reset_password()

        # Encoders cannot provision accounts.
        encoder = self.env["res.users"].sudo().create(
            {
                "name": "Tenant B Encoder",
                "login": "tenant-b-encoder",
                "company_id": company_b.id,
                "company_ids": [Command.set([company_b.id])],
                "groups_id": [
                    Command.set([self.env.ref("thirdcode_accounting.group_thirdcode_encoder").id])
                ],
            }
        )
        with self.assertRaises(AccessError):
            self.env["thirdcode.employee.wizard"].with_user(encoder).create(
                {
                    "name": "Nope",
                    "login": "nope-login",
                    "role": "encoder",
                    "password": "Nope-Passw0rd",
                }
            )

    def test_platform_owner_wizard_provisions_any_company(self):
        company_c = self.env["res.company"].sudo().create({"name": "Tenant C"})
        owner = self.env["res.users"].sudo().create(
            {
                "name": "Platform Owner",
                "login": "platform-owner-test",
                "company_id": self.company.id,
                "groups_id": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("base.group_system").id,
                        ]
                    )
                ],
            }
        )
        wizard = (
            self.env["thirdcode.employee.wizard"]
            .with_user(owner)
            .create(
                {
                    "name": "Tenant C Admin",
                    "login": "tenant-c-admin",
                    "role": "administrator",
                    "password": "Tenant-C-Pass1",
                    "company_id": company_c.id,
                }
            )
        )
        wizard.action_create_employee()
        admin_c = self.env["res.users"].sudo().search([("login", "=", "tenant-c-admin")])
        self.assertEqual(admin_c.company_ids.ids, [company_c.id])
        self.assertTrue(admin_c.has_group("thirdcode_accounting.group_thirdcode_administrator"))

    def test_platform_owner_accounts_are_hidden_and_protected(self):
        company_d = self.env["res.company"].sudo().create({"name": "Tenant D"})
        admin_d = self._provision_admin("tenant-d-admin", company_d)
        platform = self.env["res.users"].with_user(SUPERUSER_ID).create(
            {
                "name": "Platform Guard",
                "login": "platform-guard-test",
                "company_id": company_d.id,
                "company_ids": [Command.set([company_d.id])],
                "groups_id": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("base.group_system").id,
                        ]
                    )
                ],
                "thirdcode_platform_owner": True,
            }
        )

        # Owner provisioning discards the requested customer membership.
        self.assertEqual(platform.company_ids, self.env.ref("thirdcode_accounting.company_platform"))
        # The platform account is invisible to the tenant.
        self.assertFalse(
            self.env["res.users"].with_user(admin_d).search([("id", "=", platform.id)])
        )

        # Tenant administrators cannot reset its password...
        with self.assertRaises(UserError):
            reset = (
                self.env["thirdcode.employee.password.wizard"]
                .with_user(admin_d)
                .create({"user_id": platform.id, "new_password": "Guard-Passw0rd"})
            )
            reset.action_reset_password()

        # ...and cannot enable or disable it.
        with self.assertRaises(UserError):
            platform.with_user(admin_d).action_thirdcode_toggle_active()
