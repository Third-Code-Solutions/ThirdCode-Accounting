"""Native ledger arithmetic, evidence boundaries and direct-render authorization."""
import base64

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


REPORT = "thirdcode_accounting.action_report_monthly_bank_reconciliation"


@tagged("post_install", "-at_install")
class TestMonthlyBankReconciliation(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.other_data = cls.setup_other_company(name="Other monthly report company")
        cls.other_company = cls.other_data["company"]
        cls.bank = cls.env["account.journal"].create({
            "name": "Monthly review bank", "code": "MRB", "type": "bank", "company_id": cls.company.id,
        })
        cls.roles = {}
        for role in ("administrator", "accountant", "readonly", "encoder"):
            cls.roles[role] = cls.env["res.users"].create({
                "name": "Monthly " + role, "login": "monthly-" + role,
                "company_id": cls.company.id,
                "company_ids": [Command.set((cls.company | cls.other_company).ids)],
                "groups_id": [Command.set(cls.env.ref("thirdcode_accounting.group_thirdcode_" + role).ids)],
            })

    def _record(self, **values):
        return self.env["thirdcode.bank.reconciliation"].with_user(self.roles["administrator"]).with_context(
            allowed_company_ids=self.company.ids,
        ).create({
            "name": "January synthetic review", "company_id": self.company.id, "journal_id": self.bank.id,
            "statement_reference": "SYNTHETIC-MONTH-2035-01", "date_start": "2035-01-01", "date_end": "2035-01-31",
            "opening_balance": 0, "closing_balance": 0,
            "evidence_file": base64.b64encode(b"Synthetic bank statement; not client evidence"),
            "evidence_filename": "synthetic-statement.txt", **values,
        })

    def _entry(self, amount, day, posted=True, data=None, bank=None):
        data = data or self.company_data
        bank = bank or self.bank
        move = self.env["account.move"].with_company(data["company"]).create({
            "company_id": data["company"].id, "journal_id": data["default_journal_misc"].id, "date": day,
            "line_ids": [
                Command.create({"account_id": bank.default_account_id.id, "name": "Synthetic bank movement",
                                "debit": max(amount, 0), "credit": max(-amount, 0)}),
                Command.create({"account_id": data["default_account_revenue"].id,
                                "debit": max(-amount, 0), "credit": max(amount, 0)}),
            ],
        })
        if posted:
            move.action_post()
        return move

    def _statement(self, record, amount=100, day="2035-01-10", **values):
        return self.env["account.bank.statement.line"].with_user(self.roles["administrator"]).with_context(
            allowed_company_ids=self.company.ids,
        ).create({
            "journal_id": self.bank.id, "date": day, "amount": amount,
            "payment_ref": "Synthetic monthly bank transaction", "thirdcode_reconciliation_id": record.id, **values,
        })

    def test_native_monthly_arithmetic_and_unexplained_differences(self):
        self._entry(1000, "2034-12-31")
        self._entry(250, "2035-01-05")
        self._entry(-30, "2035-01-20")
        excluded = self._entry(999, "2035-01-15", posted=False)
        excluded |= self._entry(333, "2035-02-01")
        record = self._record(opening_balance=900, closing_balance=975, outstanding_deposits=400,
                              outstanding_payments=90, ledger_balance=123)
        self._statement(record, 100)
        self._statement(record, -40, "2035-01-11")
        data = record.get_monthly_report_data()
        ledger, statement = data["ledger"], data["statement"]
        self.assertEqual((ledger["opening"], ledger["debit"], ledger["credit"], ledger["closing"]), (1000, 350, 70, 1280))
        self.assertEqual([row["running_balance"] for row in ledger["rows"]], [1250, 1350, 1310, 1280])
        self.assertFalse(any(row["line"].move_id in excluded for row in ledger["rows"]))
        self.assertEqual((statement["receipts"], statement["payments"], statement["calculated_closing"], statement["activity_difference"]), (100, 40, 960, 15))
        self.assertEqual((statement["unmatched_receipts"], statement["unmatched_payments"]), (100, 40))
        self.assertEqual((data["expected_statement_closing"], data["difference"]), (970, 5))
        self.assertTrue(any("stored reconciliation ledger balance" in warning for warning in data["warnings"]))
        self.assertEqual(record.ledger_balance, 123, "Report must not recompute the stored review balance")

    def test_empty_statement_does_not_claim_completeness(self):
        data = self._record().get_monthly_report_data()
        self.assertEqual(data["ledger"]["opening"], 0)
        self.assertEqual(data["difference"], 0)
        self.assertTrue(any("completeness is not established" in warning for warning in data["warnings"]))
        self.assertFalse(data["adjustments"])

    def test_other_statement_rows_disclosed_without_changing_selected_activity(self):
        record = self._record(closing_balance=100)
        selected = self._statement(record)
        other_record = self._record(name="Another selected statement")
        other = self._statement(other_record, 25)
        unassigned = self._statement(record, -5, thirdcode_reconciliation_id=False)
        data = record.get_monthly_report_data()
        self.assertEqual([row["line"].id for row in data["statement"]["rows"]], selected.ids)
        self.assertEqual(set(data["statement"]["other_lines"].ids), set((other | unassigned).ids))
        self.assertEqual(data["statement"]["calculated_closing"], 100)
        self.assertEqual(data["ledger"]["closing"], 120)
        self.assertEqual(data["difference"], -20)

    def test_native_match_and_later_reversal_remain_visible(self):
        self.bank.suspense_account_id.reconcile = True
        outstanding = self.env["account.account"].create({
            "name": "Synthetic monthly outstanding", "code": "MONTHOUT", "account_type": "asset_current",
            "reconcile": True, "company_ids": [Command.set(self.company.ids)],
        })
        source = self.env["account.move"].create({
            "company_id": self.company.id, "journal_id": self.company_data["default_journal_misc"].id, "date": "2035-01-05",
            "line_ids": [Command.create({"account_id": outstanding.id, "debit": 100}),
                         Command.create({"account_id": self.company_data["default_account_revenue"].id, "credit": 100})],
        })
        source.action_post()
        record = self._record(closing_balance=100)
        line = self._statement(record)
        target = source.line_ids.filtered(lambda item: item.account_id == outstanding)
        line.action_match_thirdcode_items([{"line_id": target.id, "amount": 100}],
                                         self.company_data["default_journal_misc"].id, "2035-01-10")
        data = record.get_monthly_report_data()
        self.assertEqual((data["statement"]["matched_count"], data["statement"]["unmatched_count"]), (1, 0))
        self.assertEqual(len(data["adjustments"]), 1)
        self.assertEqual(data["adjustments"][0]["bank_impact"], 0)
        self.assertEqual(data["difference"], 0)
        reversal_id = line.action_reverse_thirdcode_match("2035-02-03")
        data = record.get_monthly_report_data()
        self.assertEqual((data["statement"]["matched_count"], data["statement"]["unmatched_count"]), (0, 1))
        self.assertEqual({row["move"].id for row in data["adjustments"]}, {line.thirdcode_match_move_id.id, reversal_id})
        self.assertFalse(next(row["in_period"] for row in data["adjustments"] if row["move"].id == reversal_id))
        self.assertEqual(data["ledger"]["closing"], 100, "Later matching reversal must not rewrite month-end bank balance")

    def test_company_boundaries_and_no_cross_company_rows(self):
        record = self._record()
        other_bank = self.other_data["default_journal_bank"]
        self._entry(9999, "2035-01-10", data=self.other_data, bank=other_bank)
        self._entry(10, "2035-01-10")
        active_both = record.with_context(allowed_company_ids=(self.company | self.other_company).ids)
        self.assertEqual(active_both.get_monthly_report_data()["ledger"]["closing"], 10)
        inactive = record.with_context(allowed_company_ids=self.other_company.ids)
        for operation in (inactive.get_monthly_report_data, inactive.action_print_monthly_report,
                          lambda: self.env["ir.actions.report"].with_user(self.roles["administrator"]).with_context(
                              allowed_company_ids=self.other_company.ids)._render_qweb_html(REPORT, record.ids)):
            with self.assertRaises(AccessError):
                operation()

    def test_business_roles_rechecked_on_action_data_and_direct_render(self):
        record = self._record()
        for role, user in self.roles.items():
            visible = record.with_user(user)
            reports = self.env["ir.actions.report"].with_user(user).with_context(allowed_company_ids=self.company.ids)
            operations = (visible.get_monthly_report_data, visible.action_print_monthly_report,
                          lambda: reports._render_qweb_html(REPORT, record.ids))
            for operation in operations:
                with self.subTest(role=role):
                    if role == "encoder":
                        with self.assertRaises(AccessError):
                            operation()
                    else:
                        self.assertTrue(operation())
        with self.assertRaises(AccessError):
            self.env["ir.actions.report"].with_user(self.roles["encoder"])._render_qweb_html(REPORT, [])

    def test_scope_validation_rejects_partial_month_wrong_journal_and_foreign_currency(self):
        record = self._record(date_end="2035-01-30")
        with self.assertRaises(UserError):
            record.get_monthly_report_data()
        record.write({"date_start": "2036-02-01", "date_end": "2036-02-29"})
        self.assertTrue(record.get_monthly_report_data(), "Leap-year full February is a valid month")
        record.write({"date_start": "2035-01-01", "date_end": "2035-01-31"})
        wrong_bank = self.env["account.journal"].create({
            "name": "Wrong monthly bank", "code": "MWB", "type": "bank", "company_id": self.company.id,
        })
        self._statement(record, journal_id=wrong_bank.id)
        with self.assertRaises(UserError):
            record.get_monthly_report_data()
        foreign = self.env["res.currency"].with_context(active_test=False).search([
            ("id", "!=", self.company.currency_id.id),
        ], limit=1)
        foreign.active = True
        foreign_bank = self.env["account.journal"].create({
            "name": "Foreign monthly bank", "code": "MFB", "type": "bank", "company_id": self.company.id,
            "currency_id": foreign.id,
        })
        foreign_record = self._record(journal_id=foreign_bank.id)
        with self.assertRaises(UserError):
            foreign_record.get_monthly_report_data()

    def test_out_of_period_linked_statement_rejected(self):
        record = self._record()
        self._statement(record, day="2035-02-01")
        with self.assertRaises(UserError):
            record.get_monthly_report_data()

    def test_render_is_non_mutating_and_states_evidence_limits(self):
        record = self._record(closing_balance=100)
        self._statement(record)
        self.env.flush_all()
        models = ("account.move", "account.move.line", "account.partial.reconcile", "account.full.reconcile",
                  "auditlog.log", "auditlog.log.line", "ir.attachment")
        counts_before = {model: self.env[model].search_count([]) for model in models}
        fields = ["state", "ledger_balance", "opening_balance", "closing_balance", "difference", "reconciled_by", "reconciled_at", "write_date"]
        record_before = record.read(fields)
        posted = self.env["account.move.line"].search([("company_id", "=", self.company.id), ("parent_state", "=", "posted")])
        values_before = posted.read(["move_id", "account_id", "debit", "credit", "balance", "amount_residual"])
        html, _format = self.env["ir.actions.report"].with_user(self.roles["readonly"]).with_context(
            allowed_company_ids=self.company.ids)._render_qweb_html(REPORT, record.ids)
        self.env.flush_all()
        self.assertEqual({model: self.env[model].search_count([]) for model in models}, counts_before)
        self.assertEqual(record.read(fields), record_before)
        self.assertEqual(posted.read(["move_id", "account_id", "debit", "credit", "balance", "amount_residual"]), values_before)
        for text in (b"SYNTHETIC-MONTH-2035-01", b"synthetic-statement.txt", b"client-specific definition",
                     b"not a historical month-end snapshot", b"not independently verified",
                     b"does not prove the external bank statement was imported completely"):
            self.assertIn(text, html)
