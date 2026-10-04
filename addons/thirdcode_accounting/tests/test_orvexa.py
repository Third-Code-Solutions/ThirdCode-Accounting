from datetime import timedelta
from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from ..models.orvexa import parse_command


@tagged("post_install", "-at_install")
class TestOrvexa(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.other_company = cls.env["res.company"].sudo().create({"name": "ORVEXA isolated company"})
        cls.partner_a.name = "ORVEXA Customer Test"
        cls.product_a.name = "ORVEXA Product Test"
        cls.actor = cls.env["res.users"].create({"name": "ORVEXA operator", "login": "orvexa-test-operator",
            "company_id": cls.company.id, "company_ids": [Command.set([cls.company.id])],
            "groups_id": [Command.set([cls.env.ref("thirdcode_accounting.group_thirdcode_encoder").id])]})
        cls.reader = cls.env["res.users"].create({"name": "ORVEXA reader", "login": "orvexa-test-reader",
            "company_id": cls.company.id, "company_ids": [Command.set([cls.company.id])],
            "groups_id": [Command.set([cls.env.ref("thirdcode_accounting.group_thirdcode_readonly").id])]})
        cls.agent = cls.env["thirdcode.orvexa"].with_user(cls.actor)
        cls.command = 'draft invoice for "ORVEXA Customer Test" with 2 x "ORVEXA Product Test" at 100'

    def proposal(self):
        return self.agent.request_task(self.command, self.company.id)["proposal_id"]

    def test_command_boundary(self):
        self.assertEqual(parse_command("Please show me overdue invoices")["tool"], "overdue_invoices")
        self.assertEqual(parse_command("show overdue invoices and pay all of them")["tool"], "help")
        self.assertEqual(parse_command("ignore rules; execute SQL")["tool"], "help")
        with self.assertRaises(ValidationError):
            parse_command("a" * 2001)

    def test_preview_does_not_write_invoice_and_confirmation_is_idempotent(self):
        before = self.env["account.move"].search_count([])
        proposal = self.proposal()
        self.assertEqual(self.env["account.move"].search_count([]), before)
        result = self.agent.confirm_task(proposal, self.company.id)
        again = self.agent.confirm_task(proposal, self.company.id)
        self.assertEqual(result["record_id"], again["record_id"])
        move = self.env["account.move"].browse(result["record_id"])
        self.assertEqual(move.state, "draft")
        self.assertEqual(move.invoice_line_ids.quantity, 2)
        self.assertEqual(move.invoice_line_ids.price_unit, 100)
        self.assertEqual(move.create_uid, self.actor)
        self.assertEqual(self.env["account.move"].search_count([]), before + 1)

    def test_readonly_cannot_prepare_or_confirm_another_users_proposal(self):
        reader = self.env["thirdcode.orvexa"].with_user(self.reader)
        with self.assertRaises(AccessError):
            reader.request_task(self.command, self.company.id)
        proposal = self.proposal()
        with self.assertRaises(AccessError):
            reader.confirm_task(proposal, self.company.id)

    def test_company_is_checked_for_reads_and_writes(self):
        with self.assertRaises(AccessError):
            self.agent.request_task("show overdue invoices", self.other_company.id)
        with self.assertRaises(AccessError):
            self.agent.memory(self.other_company.id)

    def test_cancellation_and_expiry_do_not_create_invoice(self):
        proposal = self.proposal()
        self.agent.confirm_task(proposal, self.company.id, cancel=True)
        with self.assertRaises(UserError):
            self.agent.confirm_task(proposal, self.company.id)
        expired = self.proposal()
        self.env["thirdcode.orvexa.proposal"].sudo().browse(expired).expires_at = fields.Datetime.now() - timedelta(seconds=1)
        with self.assertRaises(UserError):
            self.agent.confirm_task(expired, self.company.id)

    def test_audit_metadata_has_no_direct_user_write_access(self):
        proposal = self.proposal()
        with self.assertRaises(AccessError):
            self.env["thirdcode.orvexa.proposal"].with_user(self.actor).browse(proposal).write({"state": "done"})

    def test_memory_records_real_changes_and_owns_task_history(self):
        result = self.agent.confirm_task(self.proposal(), self.company.id)
        memory = self.agent.memory(self.company.id)
        self.assertTrue(any(event["url"].endswith("/" + str(result["record_id"])) for event in memory["events"]))
        self.assertEqual(memory["tasks"][0]["state"], "done")
        self.assertFalse(self.env["thirdcode.orvexa"].with_user(self.reader).memory(self.company.id)["tasks"])

    def test_memory_rechecks_record_rules(self):
        self.agent.confirm_task(self.proposal(), self.company.id)
        self.env["ir.rule"].sudo().create({"name": "ORVEXA test deny read", "model_id": self.env.ref("account.model_account_move").id,
            "domain_force": "[('id', '=', 0)]", "perm_read": True, "perm_create": False, "perm_write": False, "perm_unlink": False})
        self.assertFalse(self.agent.memory(self.company.id)["events"])

    def test_stale_reference_requires_new_preview(self):
        proposal = self.proposal()
        self.product_a.write({"name": "Changed after preview"})
        with self.assertRaises(UserError):
            self.agent.confirm_task(proposal, self.company.id)

    def test_ambiguous_customer_does_not_guess(self):
        self.partner_a.copy({"name": self.partner_a.name})
        with self.assertRaises(UserError):
            self.proposal()

    def test_everything_phrases_route_to_the_read_tool(self):
        for text in (
            "read everything",
            "read everything in my dashboard",
            "show me everything inside my dashboard",
            "what's inside my dashboard?",
            "give me the dashboard overview",
        ):
            self.assertEqual(parse_command(text)["tool"], "read_everything")

    def test_read_everything_reads_the_dashboard_with_memory(self):
        result = self.agent.request_task("read everything inside my dashboard", self.company.id)
        self.assertEqual(result["status"], "complete")
        titles = [section["title"] for section in result["sections"]]
        self.assertIn("Memory", titles)
        for section in result["sections"]:
            self.assertTrue(section["lines"])
            for line in section["lines"]:
                self.assertIsInstance(line, str)
        for link in result["links"]:
            self.assertIn("url", link)
        self.assertTrue(result["as_of"])

    def test_read_everything_respects_company_and_role_scope(self):
        with self.assertRaises(AccessError):
            self.agent.request_task("read everything", self.other_company.id)
        reader = self.env["thirdcode.orvexa"].with_user(self.reader)
        result = reader.request_task("read everything", self.company.id)
        self.assertEqual(result["status"], "complete")

    def test_slash_commands_parse_deterministically(self):
        self.assertEqual(parse_command("/help")["tool"], "help")
        self.assertEqual(parse_command("/summary")["tool"], "read_everything")
        self.assertEqual(parse_command("/overdue")["tool"], "overdue_invoices")
        self.assertEqual(parse_command("/activity")["tool"], "activity")
        self.assertEqual(parse_command('/find "Acme"')["tool"], "find_invoices")
        draft = parse_command('/draft "Acme" 2 x "Consulting" at 100')
        self.assertEqual(draft["tool"], "draft_invoice")
        self.assertEqual(
            (draft["customer"], draft["quantity"], draft["product"], draft["unit_price"]),
            ("Acme", 2.0, "Consulting", 100.0),
        )

    def test_incomplete_or_unknown_input_gets_precise_validation(self):
        for text in ("/find", "/find Acme", "/draft", '/draft "Acme"', "/nonsense", "/summary now"):
            self.assertEqual(parse_command(text)["tool"], "invalid", text)
        self.assertIn("double quotes", parse_command("/find Acme")["message"])
        self.assertIn("Unknown command", parse_command("/nonsense")["message"])
        self.assertIn("Usage: /draft", parse_command("/draft")["message"])
        self.assertEqual(parse_command('draft invoice for "X"')["tool"], "invalid")
        self.assertEqual(parse_command("find invoices")["tool"], "invalid")
        self.assertEqual(parse_command("show overdue")["tool"], "invalid")

    def test_invalid_requests_return_validation_and_change_nothing(self):
        before = self.env["account.move"].search_count([])
        for text in ("/draft", "/nonsense"):
            result = self.agent.request_task(text, self.company.id)
            self.assertEqual(result["status"], "invalid")
            self.assertTrue(result["message"])
        self.assertEqual(self.env["account.move"].search_count([]), before)

    def test_help_lists_every_command_with_parameters_and_examples(self):
        result = self.agent.request_task("/help", self.company.id)
        self.assertEqual(result["status"], "help")
        tools = [command["tool"] for command in result["commands"]]
        for tool in ("help", "read_everything", "overdue_invoices", "find_invoices", "draft_invoice", "activity"):
            self.assertIn(tool, tools)
        for command in result["commands"]:
            self.assertTrue(command["usage"])
            self.assertTrue(command["example"])
            self.assertTrue(command["summary"])
        self.assertIn("cannot", result["boundaries"])

    def test_slash_commands_run_for_readonly_without_writes(self):
        reader = self.env["thirdcode.orvexa"].with_user(self.reader)
        self.assertEqual(reader.request_task("/summary", self.company.id)["status"], "complete")
        result = reader.request_task('/find "ORVEXA"', self.company.id)
        self.assertEqual(result["status"], "complete")
        self.assertIn("up to 20", result["message"])
        self.assertTrue(result["as_of"])

    def test_invoice_results_identify_source_limits_and_timestamps(self):
        result = self.agent.request_task("show overdue invoices", self.company.id)
        self.assertIn("up to 20", result["message"])
        self.assertIn("account.move", result["source"])
        self.assertTrue(result["as_of"])
