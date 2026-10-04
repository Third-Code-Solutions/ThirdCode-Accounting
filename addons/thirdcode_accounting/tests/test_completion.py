import base64
import hashlib
from decimal import Decimal
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon



@tagged("post_install", "-at_install")
class TestAccountingCompletion(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.admin = cls.env["res.users"].create({"name": "Completion administrator", "login": "completion-admin",
            "company_id": cls.company.id, "company_ids": [Command.set(cls.company.ids)],
            "groups_id": [Command.set(cls.env.ref("thirdcode_accounting.group_thirdcode_administrator").ids)]})

    def _entry(self, amount=100, day=None, journal=None):
        return self.env["account.move"].create({"company_id": self.company.id,
            "journal_id": (journal or self.company_data["default_journal_misc"]).id,
            "date": day or fields.Date.today(), "line_ids": [
                Command.create({"account_id": self.company_data["default_account_assets"].id, "debit": amount, "name": "Asset"}),
                Command.create({"account_id": self.company_data["default_account_revenue"].id, "credit": amount, "name": "Income"}),
            ]})

    def test_continuous_numbering_year_boundary_failure_and_reversal(self):
        first = self._entry(day="2034-12-31"); first.action_post()
        original = first.name
        with self.assertRaises(UserError), self.cr.savepoint():
            failed = self._entry(day="2035-01-01"); failed.action_post()
            raise UserError("Force transaction rollback after numbering")
        second = self._entry(day="2035-01-01"); second.action_post()
        self.assertEqual(second.sequence_number, first.sequence_number + 1)
        self.assertEqual(first.name, original)
        reversal = first._reverse_moves([{"date": "2035-01-02"}], cancel=True)
        self.assertEqual(reversal.sequence_number, second.sequence_number + 1)
        self.assertEqual(first.state, "posted")
        for values in ({"name": "FAKE/000001"}, {"sequence_number": 1}, {"sequence_prefix": "RESET/"}):
            with self.assertRaises(UserError), self.cr.savepoint():
                second.sudo().write(values)
        with self.assertRaises(UserError), self.cr.savepoint():
            first.journal_id.write({"code": "RESET"})
        with self.assertRaises(UserError), self.cr.savepoint():
            self.env["account.move"].with_context(default_name="FORGED/1").create({"journal_id": first.journal_id.id})

    def test_audit_credentials_excluded_and_attachment_digest_retained(self):
        move = self._entry()
        attachment = self.env["ir.attachment"].with_user(self.admin).create({"name": "Source document", "res_model": "account.move",
            "res_id": move.id, "datas": base64.b64encode(b"Original synthetic evidence")})
        before = hashlib.sha256(b"Original synthetic evidence").hexdigest()
        attachment.write({"datas": base64.b64encode(b"Revised synthetic evidence")})
        after = hashlib.sha256(b"Revised synthetic evidence").hexdigest()
        logs = self.env["auditlog.log"].sudo().search([("model_model", "=", "ir.attachment"), ("res_id", "=", attachment.id), ("method", "=", "write")])
        changes = logs.line_ids.filtered(lambda row: row.field_name == "thirdcode_content_sha256")
        changes = changes.filtered(lambda row: before in (row.old_value or "") and after in (row.new_value or ""))
        self.assertTrue(changes, "The actual replacement must retain both content digests")
        self.assertEqual(changes[0].log_id.user_id, self.admin)
        self.assertIn(self.company, changes[0].log_id.thirdcode_company_ids)
        self.assertFalse(logs.line_ids.filtered(lambda row: row.field_name in {"datas", "raw", "db_datas", "access_token"}))
        self.admin.with_user(self.admin).sudo().write({"password": "Synthetic-credential-not-to-log-2026!"})
        user_logs = self.env["auditlog.log"].sudo().search([("model_model", "=", "res.users"), ("res_id", "=", self.admin.id)])
        self.assertFalse(user_logs.line_ids.filtered(lambda row: "password" in row.field_name or "secret" in row.field_name))
        rule = self.env.ref("thirdcode_accounting.auditlog_rule_account_move")
        for values in ({"state": "draft"}, {"log_write": False}, {"users_to_exclude_ids": [Command.link(self.admin.id)]}):
            with self.assertRaises(AccessError), self.cr.savepoint():
                rule.sudo().write(values)
        with self.assertRaises(AccessError):
            rule.sudo().unsubscribe()
        self.assertTrue(hasattr(self.env["account.move"], "auditlog_ruled_write"))
        with self.assertRaises(AccessError):
            rule.sudo().unlink()
        attachment.unlink()
        self.assertTrue(self.env["auditlog.log"].sudo().search([("model_model", "=", "ir.attachment"), ("res_id", "=", attachment.id), ("method", "=", "unlink")]))
