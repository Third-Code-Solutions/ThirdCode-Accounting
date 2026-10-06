import base64
import hashlib
from decimal import Decimal
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from .common import AccountTestInvoicingCommon

from ..models.cutover_math import build_cutover_plan, CutoverPolicyError


@tagged("post_install", "-at_install")
class TestAccountingCompletion(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (cls.partner_a | cls.partner_b).write({"company_id": cls.env.company.id})
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

    def test_statement_matching_preserves_posted_economics(self):
        bank = self.company_data["default_journal_bank"]
        bank.suspense_account_id.reconcile = True
        outstanding = self.env["account.account"].create({"name": "Synthetic outstanding receipt", "code": "COMPOUT", "account_type": "asset_current", "reconcile": True, "company_ids": [Command.set(self.company.ids)]})
        source = self.env["account.move"].create({"company_id": self.company.id, "journal_id": self.company_data["default_journal_misc"].id,
            "line_ids": [Command.create({"account_id": outstanding.id, "debit": 150, "name": "Receipt pending deposit"}),
                         Command.create({"account_id": self.company_data["default_account_revenue"].id, "credit": 150, "name": "Income"})]})
        source.action_post()
        target = source.line_ids.filtered(lambda line: line.account_id == outstanding)
        statement = self.env["account.bank.statement.line"].with_user(self.admin).create({"journal_id": bank.id, "date": fields.Date.today(), "amount": 100, "payment_ref": "Statement deposit"})
        original = [(line.id, line.account_id.id, line.balance) for line in statement.move_id.line_ids]
        values = [{"line_id": target.id, "amount": 100}]
        adjustment_id = statement.action_match_thirdcode_items(values, self.company_data["default_journal_misc"].id, str(fields.Date.today()))
        self.assertTrue(statement.is_reconciled)
        self.assertEqual(target.amount_residual, 50)
        self.assertEqual(original, [(line.id, line.account_id.id, line.balance) for line in statement.move_id.line_ids])
        self.assertEqual(statement.action_match_thirdcode_items(values, self.company_data["default_journal_misc"].id, str(fields.Date.today())), adjustment_id)
        adjustment = self.env["account.move"].browse(adjustment_id)
        self.assertEqual(adjustment.state, "posted")
        self.assertEqual(sum((source | statement.move_id | adjustment).line_ids.filtered(lambda line: line.account_id == bank.default_account_id).mapped("balance")), 100)
        reversal_id = statement.action_reverse_thirdcode_match(str(fields.Date.today()))
        self.assertEqual(statement.action_reverse_thirdcode_match(str(fields.Date.today())), reversal_id)
        self.assertFalse(statement.is_reconciled)
        self.assertEqual(target.amount_residual, 150)
        self.assertEqual(adjustment.state, "posted")
        new_match = statement.action_match_thirdcode_items(values, self.company_data["default_journal_misc"].id, str(fields.Date.today()))
        self.assertNotEqual(new_match, adjustment_id)
        self.assertEqual(set(statement.thirdcode_match_history_ids.ids), {new_match, adjustment_id})
        self.assertTrue(statement.is_reconciled)
        self.assertEqual(target.amount_residual, 50)
        self.assertEqual(original, [(line.id, line.account_id.id, line.balance) for line in statement.move_id.line_ids])

    def _cutover_batch(self):
        self.company.thirdcode_live_history_policy = "archive_only"
        assets = self.company_data["default_account_assets"]
        ar = self.company_data["default_account_receivable"]
        ap = self.company_data["default_account_payable"]
        equity = self.env["account.account"].create({"name": "Source equity", "code": "COMEQ", "account_type": "equity", "company_ids": [Command.set(self.company.ids)]})
        clearing = self.env["account.account"].create({"name": "Opening clearing", "code": "COMCLR", "account_type": "equity", "company_ids": [Command.set(self.company.ids)]})
        undeposited = self.env["account.account"].create({"name": "Undeposited receipts", "code": "COMUND", "account_type": "asset_current", "reconcile": True, "company_ids": [Command.set(self.company.ids)]})
        payload = {"policy": "residual_cutover_v1", "journal_id": self.company_data["default_journal_misc"].id, "clearing_account_id": clearing.id,
            "trial_balance": [{"account_id": assets.id, "debit": "100", "credit": "0"}, {"account_id": ar.id, "debit": "50", "credit": "0"},
                {"account_id": ap.id, "debit": "0", "credit": "30"}, {"account_id": undeposited.id, "debit": "50", "credit": "0"}, {"account_id": equity.id, "debit": "0", "credit": "170"}],
            "open_items": [{"source_id": "INV-1", "account_id": ar.id, "partner_id": self.partner_a.id, "move_type": "out_invoice", "residual": "60", "document_date": "2024-12-01", "due_date": "2025-01-15"},
                {"source_id": "BILL-1", "account_id": ap.id, "partner_id": self.partner_b.id, "move_type": "in_invoice", "residual": "30", "document_date": "2024-12-02"}],
            "undeposited_receipts": [{"source_id": "RCPT-1", "cash_account_id": undeposited.id, "partner_id": self.partner_a.id, "amount": "40", "document_date": "2024-12-03", "disposition": "already_allocated", "source_allocation_reference": "MYOB allocation INV-1 already deducted from residual60"},
                {"source_id": "RCPT-2", "cash_account_id": undeposited.id, "partner_id": self.partner_a.id, "amount": "10", "document_date": "2024-12-04", "disposition": "unallocated", "receivable_account_id": ar.id}]}
        archive = b"Synthetic MYOB source archive; no real client data"
        batch = self.env["thirdcode.migration.batch"].with_user(self.admin).create({"company_id": self.company.id, "cutover_date": "2024-12-31", "opening_balance_owner": "Synthetic finance fixture",
            "source_system": "csv", "source_archive": base64.b64encode(archive), "source_archive_filename": "synthetic-source.txt", "source_file_hash": hashlib.sha256(archive).hexdigest(), "cutover_payload": payload})
        return batch, payload, undeposited, clearing

    def test_cutover_residuals_receipts_retry_and_retained_archive(self):
        batch, payload, cash, clearing = self._cutover_batch()
        result = batch.action_apply_cutover()
        self.assertTrue(result["line_by_line_equal"])
        self.assertEqual(batch.state, "loaded")
        self.assertEqual(result, batch.action_apply_cutover())
        self.assertEqual(sum(batch.cutover_move_ids.line_ids.filtered(lambda line: line.account_id == clearing).mapped("balance")), 0)
        ar = batch.cutover_move_ids.line_ids.filtered(lambda line: line.account_id.account_type == "asset_receivable")
        self.assertEqual(sum(ar.mapped("amount_residual")), 50)
        self.assertEqual(sum(batch.cutover_move_ids.line_ids.filtered(lambda line: line.account_id == cash).mapped("balance")), 50)
        self.assertFalse(batch.cutover_move_ids.line_ids.filtered(lambda line: line.account_id.internal_group in {"income", "expense"}))
        self.assertEqual(hashlib.sha256(base64.b64decode(batch.source_archive)).hexdigest(), batch.source_file_hash)
        attachment = self.env["ir.attachment"].sudo().search([("res_model", "=", batch._name), ("res_id", "=", batch.id), ("res_field", "=", "source_archive")])
        with self.assertRaises(UserError), self.cr.savepoint():
            attachment.write({"datas": base64.b64encode(b"tampered")})
        with self.assertRaises(UserError), self.cr.savepoint():
            batch.sudo().write({"cutover_payload": {}})
        with self.assertRaises(UserError), self.cr.savepoint():
            batch.row_ids.sudo().write({"source_debit": 999})
        # Source receipt40 was already allocated: no second credit to AR.
        unallocated = ar.filtered(lambda line: line.balance < 0)
        invoice = ar.filtered(lambda line: line.balance > 0)
        (unallocated | invoice).reconcile()
        self.assertEqual(invoice.amount_residual, 50)
        deposit = self.env["account.move"].create({"company_id": self.company.id, "journal_id": self.company_data["default_journal_misc"].id, "date": "2025-01-01",
            "line_ids": [Command.create({"account_id": cash.id, "credit": 50}), Command.create({"account_id": self.company_data["default_journal_bank"].default_account_id.id, "debit": 50})]})
        deposit.action_post()
        self.assertEqual(sum((batch.cutover_move_ids | deposit).line_ids.filtered(lambda line: line.account_id == cash).mapped("balance")), 0)

    def test_cutover_rejects_control_mismatch_history_and_existing_books(self):
        batch, payload, _cash, _clearing = self._cutover_batch()
        types = {account.id: account.account_type for account in self.env["account.account"].search([("company_ids", "in", self.company.ids)])}
        with self.assertRaises(CutoverPolicyError):
            build_cutover_plan(dict(payload, history=[{"entry": "duplicate"}]), types)
        bad = dict(payload, open_items=payload["open_items"][:1])
        with self.assertRaises(CutoverPolicyError):
            build_cutover_plan(bad, types)
        self.company.thirdcode_live_history_policy = "full_history"
        with self.assertRaises(UserError), self.cr.savepoint():
            batch.action_preview_cutover()
        self.company.thirdcode_live_history_policy = "archive_only"
        self._entry().action_post()
        with self.assertRaises(UserError), self.cr.savepoint():
            batch.action_apply_cutover()
        self.assertFalse(batch.cutover_move_ids)

    def test_mixed_cash_allocation_must_reconcile_and_is_audited(self):
        bank = self.company_data["default_journal_bank"].default_account_id
        income = self.company_data["default_account_revenue"]
        loan = self.company_data["default_account_payable"]
        income.thirdcode_cash_flow_category = "operating"
        loan.thirdcode_cash_flow_category = "financing"
        move = self.env["account.move"].create({"company_id": self.company.id, "journal_id": self.company_data["default_journal_misc"].id,
            "line_ids": [Command.create({"account_id": bank.id, "debit": 120}), Command.create({"account_id": income.id, "credit": 80}),
                Command.create({"account_id": loan.id, "partner_id": self.partner_b.id, "credit": 40, "date_maturity": fields.Date.today()})]})
        move.action_post()
        wizard = self.env["thirdcode.financial.report.wizard"].with_user(self.admin).create({"company_id": self.company.id,
            "report_type": "cash_flow", "date_from": move.date, "date_to": move.date})
        self.assertFalse(wizard.get_report_data()["classification_complete"])
        allocations = self.env["thirdcode.cash.flow.allocation"].with_user(self.admin).create([
            {"move_id": move.id, "category": "operating", "amount": 80, "explanation": "Reviewed cash sale"},
            {"move_id": move.id, "category": "financing", "amount": 40, "explanation": "Reviewed borrowing"},
        ])
        data = wizard.get_report_data()
        self.assertTrue(data["classification_complete"])
        self.assertEqual(data["cash_reconciliation_difference"], "0.00")
        self.assertEqual(data["sections"][0]["total"], "80.00")
        self.assertEqual(data["sections"][2]["total"], "40.00")
        allocations[0].amount = 70
        self.assertFalse(wizard.get_report_data()["classification_complete"])
        self.assertTrue(self.env["auditlog.log"].sudo().search([("model_model", "=", allocations._name), ("res_id", "=", allocations[0].id), ("method", "=", "write")]))

    def test_vat_withholding_summary_uses_posted_ledger_and_refunds(self):
        taxes = self.env["account.tax"].create([
            {"name": "Synthetic VAT", "amount": 12, "amount_type": "percent", "type_tax_use": "sale", "company_id": self.company.id, "thirdcode_summary_kind": "vat"},
            {"name": "Synthetic withholding", "amount": -2, "amount_type": "percent", "type_tax_use": "sale", "company_id": self.company.id, "thirdcode_summary_kind": "withholding"},
        ])
        invoice = self.env["account.move"].create({"company_id": self.company.id, "journal_id": self.company_data["default_journal_sale"].id,
            "move_type": "out_invoice", "partner_id": self.partner_a.id, "invoice_date": fields.Date.today(),
            "invoice_line_ids": [Command.create({"name": "Synthetic taxable service", "account_id": self.company_data["default_account_revenue"].id,
                "price_unit": 100, "tax_ids": [Command.set(taxes.ids)]})]})
        invoice.action_post()
        wizard = self.env["thirdcode.tax.summary.wizard"].with_user(self.admin).create({"company_id": self.company.id,
            "date_from": invoice.date, "date_to": invoice.date, "summary_kind": "vat"})
        self.assertEqual(wizard.get_report_data()["tax_total"], "12.00")
        self.assertEqual(wizard.get_report_data()["rows"][0]["base"], "100.00")
        wizard.summary_kind = "withholding"
        self.assertEqual(wizard.get_report_data()["tax_total"], "-2.00")
        html, _ = self.env["ir.actions.report"].with_user(self.admin)._render_qweb_html("thirdcode_accounting.action_report_thirdcode_tax_summary", wizard.ids)
        self.assertIn(b"-2.00", html)
        invoice._reverse_moves([{"date": invoice.date}], cancel=True)
        self.assertEqual(wizard.get_report_data()["tax_total"], "0.00")

    def test_standard_bank_summary_has_evidence_and_detects_stale_ledger(self):
        bank = self.company_data["default_journal_bank"]
        record = self.env["thirdcode.bank.reconciliation"].with_user(self.admin).create({"name": "Synthetic bank review", "company_id": self.company.id,
            "journal_id": bank.id, "statement_reference": "BANK-TEST", "date_start": fields.Date.today(), "date_end": fields.Date.today(),
            "closing_balance": 0, "evidence_file": base64.b64encode(b"Synthetic bank statement"), "evidence_filename": "statement.txt", "definition": "Synthetic fixture"})
        record.action_compute_ledger_balance()
        self.assertFalse(record.get_summary_data()["ledger_changed"])
        record.action_reconcile()
        html, _ = self.env["ir.actions.report"].with_user(self.admin)._render_qweb_html("thirdcode_accounting.action_report_thirdcode_bank_summary", record.ids)
        self.assertIn(b"BANK-TEST", html)
        self.assertIn(b"statement.txt", html)
        entry = self.env["account.move"].create({"company_id": self.company.id, "journal_id": self.company_data["default_journal_misc"].id,
            "line_ids": [Command.create({"account_id": bank.default_account_id.id, "debit": 10}),
                Command.create({"account_id": self.company_data["default_account_revenue"].id, "credit": 10})]})
        entry.action_post()
        self.assertTrue(record.get_summary_data()["ledger_changed"])

    def test_supplier_credit_refund_and_additional_debit_reconcile(self):
        bill = self.env["account.move"].create({"company_id": self.company.id, "move_type": "in_invoice",
            "journal_id": self.company_data["default_journal_purchase"].id, "partner_id": self.partner_b.id,
            "invoice_date": fields.Date.today(), "invoice_line_ids": [Command.create({"name": "Synthetic supplies",
                "account_id": self.company_data["default_account_expense"].id, "price_unit": 90, "tax_ids": [Command.clear()]})]})
        bill.action_post()
        bank = self.company_data["default_journal_bank"]
        payment = self.env["account.payment.register"].with_context(active_model="account.move", active_ids=bill.ids).create({"journal_id": bank.id, "amount": 90})._create_payments()
        self.assertEqual(bill.amount_residual, 0)
        credit = bill._reverse_moves([{"date": bill.date}], cancel=False)
        credit.action_post()
        refund = self.env["account.payment.register"].with_context(active_model="account.move", active_ids=credit.ids).create({"journal_id": bank.id, "amount": 90})._create_payments()
        self.assertEqual(credit.amount_residual, 0)
        self.assertEqual(refund.payment_type, "inbound")
        self.assertAlmostEqual(sum((bill | payment.move_id | credit | refund.move_id).line_ids.filtered(lambda line: line.account_id.account_type == "liability_payable").mapped("balance")), 0)
        # Native reversal of the supplier credit reinstates a payable debit
        # adjustment without editing either original posted source document.
        debit = credit._reverse_moves([{"date": credit.date}], cancel=False)
        debit.action_post()
        self.assertEqual(debit.move_type, "in_invoice")
        self.assertEqual(debit.amount_residual, 90)
        self.assertTrue(all(move.state == "posted" for move in bill | credit | debit))

    def test_cash_cheque_transfer_and_petty_cash_use_native_accounts(self):
        cash = self.env["account.journal"].create({"name": "Synthetic petty cash", "code": "PCT", "type": "cash", "company_id": self.company.id})
        for method in cash.inbound_payment_method_line_ids | cash.outbound_payment_method_line_ids:
            method.payment_account_id = cash.default_account_id
        bank = self.company_data["default_journal_bank"]
        payments = self.env["account.payment"]
        for instrument, journal in (("cash", cash), ("cheque", bank), ("bank_transfer", bank)):
            payment = self.env["account.payment"].with_user(self.admin).create({"company_id": self.company.id, "journal_id": journal.id,
                "partner_id": self.partner_b.id, "payment_type": "outbound", "partner_type": "supplier", "amount": 25,
                "thirdcode_payment_instrument": instrument, "thirdcode_instrument_reference": "Synthetic " + instrument})
            payment.action_post()
            self.assertEqual(payment.move_id.state, "posted")
            self.assertEqual(payment.thirdcode_payment_instrument, instrument)
            payments |= payment
        self.assertEqual(sum(payments.move_id.line_ids.filtered(lambda line: line.account_id == cash.default_account_id).mapped("balance")), -25)
        self.assertEqual(sum(payments.move_id.line_ids.filtered(lambda line: line.account_id.account_type == "liability_payable").mapped("balance")), 75)

    def test_completion_role_and_company_boundaries(self):
        accountant, readonly = [self.env["res.users"].create({"name": role, "login": "completion-" + role,
            "company_id": self.company.id, "company_ids": [Command.set(self.company.ids)],
            "groups_id": [Command.set(self.env.ref("thirdcode_accounting.group_thirdcode_" + role).ids)]}) for role in ("accountant", "readonly")]
        batch, _payload, _cash, _clearing = self._cutover_batch()
        with self.assertRaises(AccessError), self.cr.savepoint():
            batch.with_user(accountant).action_apply_cutover()
        move = self._entry(); move.action_post()
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env["thirdcode.cash.flow.allocation"].with_user(readonly).create({"move_id": move.id, "category": "operating", "amount": 1, "explanation": "Forbidden"})
        other = self.env["res.company"].sudo().create({"name": "Other synthetic report company"})
        with self.assertRaises(AccessError), self.cr.savepoint():
            wizard = self.env["thirdcode.tax.summary.wizard"].with_user(readonly).create({"company_id": other.id})
            wizard.get_report_data()
        statement = self.env["account.bank.statement.line"].with_user(self.admin).create({"journal_id": self.company_data["default_journal_bank"].id, "date": fields.Date.today(), "amount": 10, "payment_ref": "Role test"})
        with self.assertRaises(AccessError), self.cr.savepoint():
            statement.with_user(readonly).action_reverse_thirdcode_match(str(fields.Date.today()))

    def test_soa_opening_activity_running_balance_and_ageing(self):
        invoices = self.env["account.move"]
        for day, amount in (("2034-12-01", 40), ("2035-01-10", 100)):
            invoice = self.env["account.move"].create({"company_id": self.company.id, "move_type": "out_invoice",
                "journal_id": self.company_data["default_journal_sale"].id, "partner_id": self.partner_a.id,
                "invoice_date": day, "invoice_date_due": day, "date": day, "invoice_line_ids": [Command.create({"name": "Synthetic SOA service",
                    "account_id": self.company_data["default_account_revenue"].id, "price_unit": amount, "tax_ids": [Command.clear()]})]})
            invoice.action_post(); invoices |= invoice
        payment = self.env["account.payment"].create({"company_id": self.company.id, "journal_id": self.company_data["default_journal_bank"].id,
            "partner_id": self.partner_a.id, "payment_type": "inbound", "partner_type": "customer", "amount": 50, "date": "2035-01-20"})
        payment.action_post()
        (invoices.line_ids | payment.move_id.line_ids).filtered(lambda line: line.account_id.account_type == "asset_receivable").reconcile()
        wizard = self.env["activity.statement.wizard"].with_user(self.admin).with_context(active_ids=self.partner_a.ids).create({
            "company_id": self.company.id, "date_start": "2035-01-01", "date_end": "2035-01-31", "show_aging_buckets": True,
            "filter_partners_non_due": False, "filter_negative_balances": False})
        payload = wizard._prepare_statement()
        report = self.env["report.partner_statement.activity_statement"].with_user(self.admin)._get_report_values(self.partner_a.ids, payload)
        currency = report["data"][self.partner_a.id]["currencies"][self.company.currency_id.id]
        self.assertEqual(currency["balance_forward"], 40)
        self.assertEqual([line["thirdcode_running_balance"] for line in currency["lines"]], [140, 90])
        self.assertEqual(currency["amount_due"], 90)
        self.assertEqual(currency["buckets"]["balance"], 90)
        self.assertEqual(currency["buckets"]["b_1_30"], 90)
        html, _ = self.env["ir.actions.report"].with_user(self.admin)._render_qweb_html("partner_statement.activity_statement", self.partner_a.ids, data=payload)
        self.assertIn(b"Running balance", html)
        self.assertIn(b"Ending Balance", html)


    def test_cutover_interruption_rolls_back_all_components_then_retry_succeeds(self):
        batch, _payload, _cash, _clearing = self._cutover_batch()
        move_class = type(self.env["account.move"])
        original = move_class.action_post
        calls = []
        def interrupted(records):
            result = original(records)
            calls.append(records.id)
            if len(calls) == 2:
                raise UserError("Simulated interruption after two posted components")
            return result
        with self.assertRaises(UserError), self.cr.savepoint(), patch.object(move_class, "action_post", interrupted):
            batch.action_apply_cutover()
        self.assertFalse(batch.cutover_move_ids)
        self.assertFalse(batch.cutover_fingerprint)
        self.assertTrue(batch.action_apply_cutover()["line_by_line_equal"])

    def test_source_history_archive_is_queryable_immutable_and_never_posts(self):
        batch, _payload, _cash, _clearing = self._cutover_batch()
        batch.action_apply_cutover()
        count = self.env["account.move"].search_count([("company_id", "=", self.company.id)])
        rows = [
            {"source_entry_id": "HIST-2015", "source_line_id": "1", "date": "2015-01-01", "account_code": "1000", "debit": "12", "credit": "0", "description": "Archived cash"},
            {"source_entry_id": "HIST-2015", "source_line_id": "2", "date": "2015-01-01", "account_code": "3000", "debit": "0", "credit": "12", "description": "Archived equity"},
        ]
        self.assertEqual(batch.action_archive_source_history(rows)["created_lines"], 2)
        self.assertEqual(batch.action_archive_source_history(rows)["created_lines"], 0)
        self.assertEqual(self.env["account.move"].search_count([("company_id", "=", self.company.id)]), count)
        archived = self.env["thirdcode.migration.archive.entry"].with_user(self.admin).search([("batch_id", "=", batch.id), ("account_code", "=", "1000")])
        self.assertEqual(archived.debit, 12)
        with self.assertRaises(AccessError):
            archived.sudo().write({"debit": 999})
        with self.assertRaises(AccessError):
            archived.sudo().unlink()
        changed = [dict(row, description="Changed extraction") for row in rows]
        with self.assertRaises(UserError):
            batch.action_archive_source_history(changed)
