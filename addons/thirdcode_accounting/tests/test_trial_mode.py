from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestTrialMode(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        # A report layout must be selected, otherwise report_action() returns
        # the document-layout configurator action instead of the report.
        cls.company.sudo().write(
            {
                "thirdcode_trial_mode": True,
                "external_report_layout_id": cls.env.ref("web.report_layout_standard").id,
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
        service = self.env["thirdcode.setup.service"]

        with self.assertRaises(AccessError):
            service.dispatch("status", {})

        result = service.with_context(tcsi_setup_token_ok=True).dispatch("status", {})
        self.assertIn("companies", result)
        self.assertIn("users", result)

        with self.assertRaises(UserError):
            service.with_context(tcsi_setup_token_ok=True).dispatch("not-an-action", {})

    def test_setup_service_create_user_and_batch(self):
        company = self.env["res.company"].sudo().create({"name": "Trial service company"})
        service = self.env["thirdcode.setup.service"].with_context(tcsi_setup_token_ok=True)

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
        service = self.env["thirdcode.setup.service"].with_context(tcsi_setup_token_ok=True)

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

    def test_receipt_sequence_is_per_company(self):
        company_b = self.env["res.company"].sudo().create({"name": "Second Trial Company"})
        sequence = company_b._thirdcode_receipt_sequence()
        self.assertEqual(sequence.company_id, company_b)
        self.assertEqual(sequence.next_by_id(), "OR/00000001")
        self.assertEqual(company_b._thirdcode_receipt_sequence(), sequence)  # idempotent

        # the original company keeps its own sequence, independent numbering
        sequence_a = self.company._thirdcode_receipt_sequence()
        self.assertNotEqual(sequence_a, sequence)
        self.assertTrue(sequence_a.next_by_id().startswith("OR/"))
