import base64

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tools import date_utils
from .common import AccountTestInvoicingCommon
from .common import TestExpenseCommon


@tagged("post_install", "-at_install")
class TestFinancialControls(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (cls.partner_a | cls.partner_b).write({"company_id": cls.env.company.id})
        cls.company = cls.company_data["company"]
        cls.other_company = cls.env["res.company"].sudo().create(
            {"name": "Financial controls isolated company"}
        )
        cls.accountant = cls.env["res.users"].create(
            {
                "name": "Financial controls accountant",
                "login": "financial-controls-accountant",
                "company_id": cls.company.id,
                "company_ids": [Command.set([cls.company.id])],
                "groups_id": [
                    Command.set(
                        [
                            cls.env.ref(
                                "thirdcode_accounting.group_thirdcode_accountant"
                            ).id
                        ]
                    )
                ],
            }
        )

    def _posted_invoice(self, tax=None):
        invoice_line = {
            "name": "Financial control test item",
            "quantity": 1,
            "price_unit": 100,
            "account_id": self.company_data["default_account_revenue"].id,
        }
        if tax:
            invoice_line["tax_ids"] = [Command.set([tax.id])]
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "company_id": self.company.id,
                "journal_id": self.company_data["default_journal_sale"].id,
                "partner_id": self.partner_a.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [Command.create(invoice_line)],
            }
        )
        invoice.action_post()
        return invoice

    def _payment_batch(self, line_values):
        return self.env["thirdcode.payment.batch"].with_user(self.accountant).create(
            {
                "name": "FIN-CONTROL-TEST",
                "company_id": self.company.id,
                "journal_id": self.company_data["default_journal_bank"].id,
                "payment_type": "inbound",
                "partner_type": "customer",
                "payment_instrument": "cash",
                "line_ids": [Command.create(line_values)],
            }
        )

    def test_zero_amount_invoice_line_cannot_submit_or_bypass_approval(self):
        invoice = self._posted_invoice()
        batch = self._payment_batch(
            {
                "move_id": invoice.id,
                "partner_id": invoice.partner_id.id,
                "amount": 0,
            }
        )

        with self.assertRaises(UserError):
            batch.action_submit()

        self.assertEqual(batch.state, "draft")
        self.assertFalse(batch.line_ids.payment_id)

    def test_direct_payment_batch_state_write_is_rejected(self):
        batch = self.env["thirdcode.payment.batch"].with_user(self.accountant).create(
            {
                "name": "FIN-CONTROL-STATE",
                "company_id": self.company.id,
                "journal_id": self.company_data["default_journal_bank"].id,
                "payment_instrument": "cash",
            }
        )

        with self.assertRaises(AccessError):
            batch.write({"state": "posted"})

        self.assertEqual(batch.state, "draft")

    def test_threshold_batch_requires_administrator_approval_before_posting(self):
        self.company.sudo().write(
            {
                "thirdcode_payment_approval_enabled": True,
                "thirdcode_payment_approval_threshold": 10,
            }
        )
        batch = self.env["thirdcode.payment.batch"].with_user(self.accountant).create(
            {
                "name": "FIN-CONTROL-THRESHOLD",
                "company_id": self.company.id,
                "journal_id": self.company_data["default_journal_bank"].id,
                "date": fields.Date.today(),
                "payment_type": "outbound",
                "partner_type": "supplier",
                "payment_instrument": "cash",
                "line_ids": [
                    Command.create(
                        {"partner_id": self.partner_b.id, "amount": 20}
                    )
                ],
            }
        )

        batch.action_submit()
        self.assertEqual(batch.state, "pending_approval")
        with self.assertRaises(UserError):
            batch.action_post()
        self.assertEqual(batch.state, "pending_approval")
        self.assertFalse(batch.line_ids.payment_id)

        with self.assertRaises(AccessError):
            batch.action_approve()
        self.assertEqual(batch.state, "pending_approval")

        administrator = self.env["res.users"].create(
            {
                "name": "Financial controls administrator",
                "login": "financial-controls-administrator",
                "company_id": self.company.id,
                "company_ids": [Command.set([self.company.id])],
                "groups_id": [
                    Command.set(
                        [
                            self.env.ref(
                                "thirdcode_accounting.group_thirdcode_administrator"
                            ).id
                        ]
                    )
                ],
            }
        )
        batch.with_user(administrator).action_approve()
        self.assertEqual(batch.state, "approved")
        self.assertEqual(batch.approved_by, administrator)
        self.assertTrue(batch.approved_at)

        batch.action_post()
        self.assertEqual(batch.state, "posted")
        self.assertTrue(batch.line_ids.payment_id)

    def test_lowered_threshold_requires_approval_before_posting(self):
        self.company.sudo().write(
            {
                "thirdcode_payment_approval_enabled": True,
                "thirdcode_payment_approval_threshold": 100,
            }
        )
        invoice = self._posted_invoice()
        batch = self._payment_batch(
            {
                "move_id": invoice.id,
                "partner_id": invoice.partner_id.id,
                "amount": 20,
            }
        )
        batch.action_submit()

        self.assertEqual(batch.state, "approved")
        self.assertFalse(batch.approved_by)
        self.company.sudo().write(
            {"thirdcode_payment_approval_threshold": 10}
        )

        with self.assertRaises(UserError):
            batch.action_post()

        self.assertFalse(batch.line_ids.payment_id)
        self.assertEqual(batch.state, "approved")

    def test_payment_batch_posts_partial_payment_from_register_result(self):
        invoice = self._posted_invoice()
        amount = invoice.amount_residual / 2
        batch = self._payment_batch(
            {
                "move_id": invoice.id,
                "partner_id": invoice.partner_id.id,
                "amount": amount,
                "communication": "FIN-CONTROL-PARTIAL-BATCH",
            }
        )

        batch.action_post()

        self.assertEqual(batch.state, "posted")
        self.assertTrue(batch.line_ids.payment_id)
        self.assertAlmostEqual(batch.line_ids.payment_id.amount, amount, places=2)
        self.assertAlmostEqual(invoice.amount_residual, amount, places=2)

    def test_bank_reconciliation_uses_standard_book_to_statement_signs(self):
        reconciliation = self.env["thirdcode.bank.reconciliation"].with_user(
            self.accountant
        ).create(
            {
                "name": "FIN-CONTROL-RECONCILIATION",
                "company_id": self.company.id,
                "journal_id": self.company_data["default_journal_bank"].id,
                "statement_reference": "FIN-CONTROL-STATEMENT",
                "date_start": fields.Date.today(),
                "date_end": fields.Date.today(),
                "ledger_balance": 110,
                "closing_balance": 100,
                "outstanding_deposits": 20,
                "outstanding_payments": 10,
                "evidence_file": base64.b64encode(b"synthetic bank statement"),
                "evidence_filename": "synthetic-statement.txt",
                "definition": "Synthetic QA statement; deposits in transit subtract and uncleared payments add.",
            }
        )

        self.assertEqual(reconciliation.expected_bank_balance, 100)
        self.assertEqual(reconciliation.difference, 0)
        statement_line = self.env["account.bank.statement.line"].with_user(
            self.accountant
        ).create(
            {
                "journal_id": self.company_data["default_journal_bank"].id,
                "date": fields.Date.today(),
                "payment_ref": "FIN-CONTROL-RECONCILIATION-LINE",
                "amount": 10,
                "thirdcode_reconciliation_id": reconciliation.id,
            }
        )
        reconciliation.action_compute_ledger_balance()
        reconciliation.write(
            {
                "closing_balance": reconciliation.ledger_balance
                - reconciliation.outstanding_deposits
                + reconciliation.outstanding_payments
            }
        )
        self.assertEqual(reconciliation.difference, 0)
        reconciliation.action_reconcile()
        self.assertEqual(reconciliation.state, "reconciled")

        with self.assertRaises(UserError):
            statement_line.with_user(self.accountant).write({"amount": 11})
        with self.assertRaises(UserError):
            statement_line.with_user(self.accountant).unlink()

        unattached_line = self.env["account.bank.statement.line"].with_user(
            self.accountant
        ).create(
            {
                "journal_id": self.company_data["default_journal_bank"].id,
                "date": fields.Date.today(),
                "payment_ref": "FIN-CONTROL-UNATTACHED-LINE",
                "amount": 5,
            }
        )
        with self.assertRaises(UserError):
            unattached_line.write(
                {"thirdcode_reconciliation_id": reconciliation.id}
            )
        with self.assertRaises(UserError):
            self.env["account.bank.statement.line"].with_user(
                self.accountant
            ).create(
                {
                    "journal_id": self.company_data["default_journal_bank"].id,
                    "date": fields.Date.today(),
                    "payment_ref": "FIN-CONTROL-LATE-LINE",
                    "amount": 5,
                    "thirdcode_reconciliation_id": reconciliation.id,
                }
            )

    def test_bank_reconciliation_rejects_forged_ledger_balance(self):
        bank_journal = self.company_data["default_journal_bank"]
        current_balance = sum(
            self.env["account.move.line"].search(
                [
                    ("company_id", "=", self.company.id),
                    ("account_id", "=", bank_journal.default_account_id.id),
                    ("date", "<=", fields.Date.today()),
                    ("parent_state", "=", "posted"),
                ]
            ).mapped("balance")
        )
        reconciliation = self.env["thirdcode.bank.reconciliation"].with_user(
            self.accountant
        ).create(
            {
                "name": "FIN-CONTROL-FORGED-BALANCE",
                "company_id": self.company.id,
                "journal_id": bank_journal.id,
                "statement_reference": "FIN-CONTROL-FORGED-STATEMENT",
                "date_start": fields.Date.today(),
                "date_end": fields.Date.today(),
                "ledger_balance": current_balance + 100,
                "closing_balance": current_balance + 100,
                "evidence_file": base64.b64encode(b"synthetic bank statement"),
                "evidence_filename": "synthetic-statement.txt",
                "definition": "Synthetic QA procedure.",
            }
        )

        self.assertEqual(reconciliation.difference, 0)
        with self.assertRaises(UserError):
            reconciliation.action_reconcile()
        self.assertEqual(reconciliation.state, "draft")

    def test_posted_statement_amount_requires_reversal(self):
        statement_line = self.env["account.bank.statement.line"].with_user(
            self.accountant
        ).create(
            {
                "journal_id": self.company_data["default_journal_bank"].id,
                "date": fields.Date.today(),
                "payment_ref": "FIN-CONTROL-STATEMENT-SYNC",
                "amount": 10,
            }
        )
        move = statement_line.move_id
        if move.state == "draft":
            move.action_post()

        with self.assertRaises(UserError):
            move.with_user(self.accountant).write({"ref": "DIRECT-EDIT-BLOCKED"})

        with self.assertRaises(UserError), self.cr.savepoint():
            statement_line.with_user(self.accountant).write({"amount": 11})

        self.assertEqual(statement_line.amount, 10)
        self.assertEqual(move.state, "posted")
        liquidity_lines, _, _ = statement_line._seek_for_lines()
        self.assertEqual(abs(sum(liquidity_lines.mapped("balance"))), 10)
        with self.assertRaises(UserError):
            statement_line.with_user(self.accountant).unlink()
        self.assertTrue(statement_line.exists())

    def test_partial_customer_payment_allocates_vat_by_reconciled_amount(self):
        tax = self.company_data["default_tax_sale"]
        self.assertGreater(tax.amount, 0)
        invoice = self._posted_invoice(tax=tax)
        self.assertGreater(invoice.amount_tax, 0)
        payment_amount = invoice.amount_total / 2
        context = {
            "active_model": "account.move",
            "active_ids": invoice.ids,
            "active_id": invoice.id,
        }
        wizard = self.env["account.payment.register"].with_context(**context).create(
            {
                "amount": payment_amount,
                "journal_id": self.company_data["default_journal_bank"].id,
                "payment_date": fields.Date.today(),
                "communication": "FIN-CONTROL-PARTIAL-VAT",
            }
        )
        wizard.action_create_payments()
        payment = self.env["account.payment"].search(
            [("memo", "=", "FIN-CONTROL-PARTIAL-VAT")], limit=1
        )

        self.assertTrue(payment)
        self.assertAlmostEqual(payment.amount, payment_amount, places=2)
        self.assertAlmostEqual(
            payment.thirdcode_receipt_vat_amount,
            invoice.amount_tax / 2,
            places=2,
        )
        self.assertAlmostEqual(invoice.amount_residual, payment_amount, places=2)

    def test_golden_invoice_and_partial_receipt_tie_to_posted_ledger(self):
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
                            "name": "Golden dataset tax-free service",
                            "quantity": 1,
                            "price_unit": 10_000,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                        }
                    )
                ],
            }
        )
        invoice.action_post()

        self.assertAlmostEqual(invoice.amount_total, 10_000, places=2)
        self.assertAlmostEqual(invoice.amount_residual, 10_000, places=2)
        receivable = self.partner_a.property_account_receivable_id
        revenue = self.company_data["default_account_revenue"]
        bank = self.company_data["default_journal_bank"].default_account_id
        self.assertAlmostEqual(
            sum(invoice.line_ids.filtered(lambda line: line.account_id == receivable).mapped("balance")),
            10_000,
            places=2,
        )
        self.assertAlmostEqual(
            sum(invoice.line_ids.filtered(lambda line: line.account_id == revenue).mapped("balance")),
            -10_000,
            places=2,
        )

        payment_memo = "FIN-CONTROL-GOLDEN-RECEIPT"
        wizard = self.env["account.payment.register"].with_context(
            active_model="account.move",
            active_ids=invoice.ids,
            active_id=invoice.id,
        ).create(
            {
                "amount": 4_000,
                "journal_id": self.company_data["default_journal_bank"].id,
                "payment_date": fields.Date.today(),
                "communication": payment_memo,
            }
        )
        wizard.action_create_payments()
        payments = self.env["account.payment"].search(
            [("memo", "=", payment_memo)]
        )

        self.assertEqual(len(payments), 1)
        payment = payments
        self.assertAlmostEqual(payment.amount, 4_000, places=2)
        self.assertEqual(payment.move_id.state, "posted")

        bank_journal = self.company_data["default_journal_bank"]
        outstanding_receipts = payment.outstanding_account_id
        statement_line = self.env["account.bank.statement.line"].create(
            {
                "journal_id": bank_journal.id,
                "date": fields.Date.today(),
                "payment_ref": payment_memo,
                "amount": 4_000,
                "counterpart_account_id": outstanding_receipts.id,
            }
        )
        payment_outstanding_line = payment.move_id.line_ids.filtered(
            lambda line: line.account_id == outstanding_receipts
        )
        statement_outstanding_line = statement_line.move_id.line_ids.filtered(
            lambda line: line.account_id == outstanding_receipts
        )
        self.assertEqual(len(payment_outstanding_line), 1)
        self.assertEqual(len(statement_outstanding_line), 1)
        (payment_outstanding_line | statement_outstanding_line).reconcile()
        self.assertTrue(payment_outstanding_line.full_reconcile_id)

        self.assertAlmostEqual(invoice.amount_residual, 6_000, places=2)
        moves = invoice + payment.move_id + statement_line.move_id
        posted_lines = moves.line_ids.filtered(lambda line: line.parent_state == "posted")
        self.assertAlmostEqual(
            sum(posted_lines.filtered(lambda line: line.account_id == receivable).mapped("balance")),
            6_000,
            places=2,
        )
        self.assertAlmostEqual(
            sum(posted_lines.filtered(lambda line: line.account_id == bank).mapped("balance")),
            4_000,
            places=2,
        )
        self.assertAlmostEqual(
            sum(posted_lines.filtered(lambda line: line.account_id == revenue).mapped("balance")),
            -10_000,
            places=2,
        )
        self.assertAlmostEqual(
            sum(
                posted_lines.filtered(
                    lambda line: line.account_id == outstanding_receipts
                ).mapped("balance")
            ),
            0,
            places=2,
        )
        self.assertAlmostEqual(sum(posted_lines.mapped("debit")), 18_000, places=2)
        self.assertAlmostEqual(sum(posted_lines.mapped("credit")), 18_000, places=2)

    def test_migration_batches_and_rows_are_scoped_to_allowed_companies(self):
        batch = self.env["thirdcode.migration.batch"].sudo().create(
            {
                "name": "FIN-CONTROL-OTHER-COMPANY",
                "company_id": self.other_company.id,
                "cutover_date": fields.Date.today(),
            }
        )
        row = self.env["thirdcode.migration.row"].sudo().create(
            {
                "batch_id": batch.id,
                "source_identifier": "FIN-CONTROL-OTHER-ROW",
                "target_model": "account.move",
            }
        )
        actor_env = self.env["thirdcode.migration.batch"].with_user(
            self.accountant
        ).with_context(allowed_company_ids=[self.company.id])

        self.assertEqual(actor_env.search_count([("id", "=", batch.id)]), 0)
        self.assertEqual(
            actor_env.env["thirdcode.migration.row"].search_count(
                [("id", "=", row.id)]
            ),
            0,
        )

    def test_company_attachment_metadata_is_hidden_from_other_company_users(self):
        batch = self.env["thirdcode.migration.batch"].sudo().create(
            {
                "name": "FIN-CONTROL-ATTACHMENT-ISOLATION",
                "company_id": self.other_company.id,
                "cutover_date": fields.Date.today(),
            }
        )
        attachment = self.env["ir.attachment"].sudo().create(
            {
                "name": "synthetic-isolation-evidence.txt",
                "type": "binary",
                "datas": base64.b64encode(b"company-private synthetic evidence"),
                "mimetype": "text/plain",
                "company_id": self.other_company.id,
                "res_model": batch._name,
                "res_id": batch.id,
            }
        )
        actor_attachments = (
            self.env["ir.attachment"]
            .with_user(self.accountant)
            .with_context(allowed_company_ids=[self.company.id])
        )

        self.assertEqual(actor_attachments.search_count([("id", "=", attachment.id)]), 0)
        with self.assertRaises(AccessError):
            actor_attachments.browse(attachment.id).read(["datas"])

    def test_report_wizards_reject_inactive_company_exports(self):
        actor_financial_reports = (
            self.env["thirdcode.financial.report.wizard"]
            .with_user(self.accountant)
            .with_context(allowed_company_ids=[self.company.id])
        )
        with self.assertRaises(AccessError):
            actor_financial_reports.create(
                {
                    "company_id": self.other_company.id,
                    "date_from": fields.Date.today().replace(month=1, day=1),
                    "date_to": fields.Date.today(),
                }
            )

        actor_trial_balance_reports = (
            self.env["trial.balance.report.wizard"]
            .with_user(self.accountant)
            .with_context(allowed_company_ids=[self.company.id])
        )
        with self.assertRaises(AccessError):
            actor_trial_balance_reports.create(
                {
                    "company_id": self.other_company.id,
                    "date_from": fields.Date.today(),
                    "date_to": fields.Date.today(),
                    "target_move": "posted",
                    "account_ids": [Command.set([])],
                    "partner_ids": [Command.set([])],
                    "journal_ids": [Command.set([])],
                }
            )

    def test_trial_balance_defaults_to_active_company_fiscal_year(self):
        report_env = (
            self.env["trial.balance.report.wizard"]
            .with_user(self.accountant)
            .with_context(allowed_company_ids=[self.company.id])
        )
        wizard = report_env.create({"company_id": self.company.id})
        today = fields.Date.context_today(wizard)
        expected_start, _expected_end = date_utils.get_fiscal_year(
            today,
            day=self.company.fiscalyear_last_day,
            month=int(self.company.fiscalyear_last_month),
        )

        self.assertEqual(wizard.date_from, expected_start)
        self.assertEqual(wizard.date_to, today)

        wizard.onchange_date_range_id()
        self.assertEqual(wizard.date_from, expected_start)
        self.assertEqual(wizard.date_to, today)

    def test_journal_ledger_defaults_to_active_company_fiscal_year(self):
        report_env = (
            self.env["journal.ledger.report.wizard"]
            .with_user(self.accountant)
            .with_context(allowed_company_ids=[self.company.id])
        )
        wizard = report_env.create({"company_id": self.company.id})
        today = fields.Date.context_today(wizard)
        expected_start, _expected_end = date_utils.get_fiscal_year(
            today,
            day=self.company.fiscalyear_last_day,
            month=int(self.company.fiscalyear_last_month),
        )

        self.assertEqual(wizard.date_from, expected_start)
        self.assertEqual(wizard.date_to, today)

        wizard.onchange_date_range_id()
        self.assertEqual(wizard.date_from, expected_start)
        self.assertEqual(wizard.date_to, today)

    def test_open_items_defaults_to_active_company_reconcilable_accounts(self):
        report_env = (
            self.env["open.items.report.wizard"]
            .with_user(self.accountant)
            .with_context(allowed_company_ids=[self.company.id])
        )
        wizard = report_env.create({"company_id": self.company.id})
        expected_accounts = self.env["account.account"].search(
            [
                ("company_ids", "in", [self.company.id]),
                ("reconcile", "=", True),
            ]
        )

        self.assertEqual(set(wizard.account_ids.ids), set(expected_accounts.ids))
        self.assertIn(self.company_data["default_account_receivable"], wizard.account_ids)
        self.assertIn(self.company_data["default_account_payable"], wizard.account_ids)

        wizard.receivable_accounts_only = True
        wizard.onchange_type_accounts_only()
        self.assertTrue(wizard.account_ids)
        self.assertTrue(
            all(account.account_type == "asset_receivable" for account in wizard.account_ids)
        )

        wizard.receivable_accounts_only = False
        wizard.onchange_type_accounts_only()
        self.assertEqual(set(wizard.account_ids.ids), set(expected_accounts.ids))

    def test_aged_partner_balance_defaults_to_active_company_reconcilable_accounts(self):
        report_env = (
            self.env["aged.partner.balance.report.wizard"]
            .with_user(self.accountant)
            .with_context(allowed_company_ids=[self.company.id])
        )
        wizard = report_env.create({"company_id": self.company.id})
        expected_accounts = self.env["account.account"].search(
            [
                ("company_ids", "in", [self.company.id]),
                ("reconcile", "=", True),
            ]
        )

        self.assertEqual(set(wizard.account_ids.ids), set(expected_accounts.ids))

        wizard.receivable_accounts_only = True
        wizard.onchange_type_accounts_only()
        self.assertTrue(wizard.account_ids)
        self.assertTrue(
            all(account.account_type == "asset_receivable" for account in wizard.account_ids)
        )

        wizard.receivable_accounts_only = False
        wizard.onchange_type_accounts_only()
        self.assertEqual(set(wizard.account_ids.ids), set(expected_accounts.ids))

    def test_ten_trial_companies_cannot_read_each_others_accounting_records(self):
        accountant_group = self.env.ref(
            "thirdcode_accounting.group_thirdcode_accountant"
        )
        companies = [self.company] + [
            self.env["res.company"].sudo().create(
                {"name": f"Trial isolation company {index}"}
            )
            for index in range(2, 11)
        ]
        users = [self.accountant]
        for index, company in enumerate(companies[1:], start=2):
            users.append(
                self.env["res.users"].create(
                    {
                        "name": f"Trial isolation accountant {index}",
                        "login": f"trial-isolation-accountant-{index}",
                        "company_id": company.id,
                        "company_ids": [Command.set([company.id])],
                        "groups_id": [Command.set([accountant_group.id])],
                    }
                )
            )
        batches = self.env["thirdcode.migration.batch"].sudo().create(
            [
                {
                    "name": f"TRIAL-ISOLATION-{index}",
                    "company_id": company.id,
                    "cutover_date": fields.Date.today(),
                }
                for index, company in enumerate(companies, start=1)
            ]
        )
        journal_model = self.env["account.journal"].sudo()
        journals = []
        for index, company in enumerate(companies, start=1):
            journals.append(
                journal_model.create(
                    {
                        "name": f"Trial isolation journal {index}",
                        "code": f"TI{index:02d}",
                        "type": "general",
                        "company_id": company.id,
                    }
                )
            )
        account_model = self.env["account.account"].sudo()
        income_codes = [f"TI{index:03}1" for index in range(1, 11)]
        income_accounts = []
        expense_accounts = []
        for index, company in enumerate(companies, start=1):
            income_accounts.append(
                account_model.create(
                    {
                        "name": f"Trial isolation income {index}",
                        "code": income_codes[index - 1],
                        "account_type": "income",
                        "company_ids": [Command.set([company.id])],
                    }
                )
            )
            expense_accounts.append(
                account_model.create(
                    {
                        "name": f"Trial isolation expense {index}",
                        "code": f"TI{index:03}2",
                        "account_type": "expense",
                        "company_ids": [Command.set([company.id])],
                    }
                )
            )

        moves = self.env["account.move"].sudo().create(
            [
                {
                    "company_id": company.id,
                    "journal_id": journal.id,
                    "date": fields.Date.today(),
                    "move_type": "entry",
                    "ref": f"TRIAL-ISOLATION-MOVE-{index}",
                    "line_ids": [
                        Command.create(
                            {
                                "name": "Synthetic isolated trial expense",
                                "account_id": expense_accounts[index - 1].id,
                                "debit": 100,
                            }
                        ),
                        Command.create(
                            {
                                "name": "Synthetic isolated trial income",
                                "account_id": income_accounts[index - 1].id,
                                "credit": 100,
                            }
                        ),
                    ],
                }
                for index, (company, journal) in enumerate(
                    zip(companies, journals), start=1
                )
            ]
        )
        moves.action_post()
        attachments = self.env["ir.attachment"].sudo().create(
            [
                {
                    "name": f"trial-isolation-{index}.txt",
                    "type": "binary",
                    "datas": base64.b64encode(
                        f"Synthetic company {index} evidence".encode()
                    ),
                    "mimetype": "text/plain",
                    "company_id": company.id,
                    "res_model": "account.move",
                    "res_id": move.id,
                }
                for index, (company, move) in enumerate(
                    zip(companies, moves), start=1
                )
            ]
        )

        for index, (company, user, batch, move, attachment) in enumerate(
            zip(companies, users, batches, moves, attachments), start=1
        ):
            actor_batches = (
                self.env["thirdcode.migration.batch"]
                .with_user(user)
                .with_context(allowed_company_ids=[company.id])
            )
            self.assertEqual(actor_batches.search_count([]), 1)
            self.assertEqual(actor_batches.search_count([("id", "=", batch.id)]), 1)
            self.assertEqual(
                actor_batches.search_count([("id", "in", batches.ids)]), 1
            )
            actor_moves = (
                self.env["account.move"]
                .with_user(user)
                .with_context(allowed_company_ids=[company.id])
            )
            self.assertEqual(actor_moves.search_count([("id", "=", move.id)]), 1)
            self.assertEqual(actor_moves.search_count([("id", "in", moves.ids)]), 1)
            self.assertEqual(move.state, "posted")

            actor_attachments = (
                self.env["ir.attachment"]
                .with_user(user)
                .with_context(allowed_company_ids=[company.id])
            )
            self.assertEqual(
                actor_attachments.search_count([("id", "in", attachments.ids)]), 1
            )
            self.assertEqual(
                actor_attachments.search_count([("id", "=", attachment.id)]), 1
            )
            with self.assertRaises(AccessError):
                actor_attachments.browse(attachments[(index % len(attachments))].id).read(
                    ["datas"]
                )

            report_wizard = (
                self.env["thirdcode.financial.report.wizard"]
                .with_user(user)
                .with_context(allowed_company_ids=[company.id])
                .create(
                    {
                        "company_id": company.id,
                        "report_type": "profit_loss",
                        "date_from": fields.Date.today().replace(month=1, day=1),
                        "date_to": fields.Date.today(),
                        "target_move": "posted",
                    }
                )
            )
            report_data = report_wizard.get_report_data()
            self.assertEqual(report_data["sections"][0]["total"], "100.00")
            self.assertEqual(report_data["sections"][1]["total"], "100.00")
            self.assertEqual(report_data["net_result"], "0.00")
            self.assertEqual(
                [line["code"] for line in report_data["sections"][0]["lines"]],
                [income_codes[index - 1]],
            )

    def test_validated_migration_snapshot_cannot_be_changed_or_revalidated(self):
        batch_model = self.env["thirdcode.migration.batch"].with_user(
            self.accountant
        )
        batch = batch_model.create(
            {
                "name": "FIN-CONTROL-VALIDATED",
                "company_id": self.company.id,
            }
        )
        row = self.env["thirdcode.migration.row"].with_user(self.accountant).create(
            {
                "batch_id": batch.id,
                "source_identifier": "FIN-CONTROL-VALIDATED-ROW",
                "target_model": "account.move",
            }
        )
        batch.action_validate()

        with self.assertRaises(UserError):
            row.write({"target_id": 1})
        with self.assertRaises(UserError):
            batch.write({"source_file_name": "changed-after-validation.csv"})
        with self.assertRaises(UserError):
            batch.action_validate()

        self.assertEqual(batch.state, "validated")

    def test_posted_move_lines_reject_api_reclassification(self):
        """Direct writes on move lines must not bypass the posted guard.

        The move-level guard covers ``account.move`` writes; without a twin on
        ``account.move.line`` an API client could reclassify posted amounts
        between accounts (or alter price/quantity/label) while the entry
        stayed balanced.
        """
        invoice = self._posted_invoice()
        line = invoice.invoice_line_ids[0]
        expense_account = self.company_data["default_account_expense"]
        revenue_account = self.company_data["default_account_revenue"]

        with self.assertRaises(UserError):
            line.with_user(self.accountant).write(
                {"account_id": expense_account.id}
            )
        with self.assertRaises(UserError):
            line.with_user(self.accountant).write({"price_unit": 999})
        with self.assertRaises(UserError):
            line.with_user(self.accountant).write({"quantity": 7})
        with self.assertRaises(UserError):
            line.with_user(self.accountant).write({"name": "tampered label"})

        self.assertEqual(line.account_id, revenue_account)
        self.assertEqual(line.price_unit, 100)
        self.assertEqual(line.quantity, 1)

    def test_draft_edits_allowed_but_sudo_cannot_edit_posted_lines(self):
        draft = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "company_id": self.company.id,
                "journal_id": self.company_data["default_journal_sale"].id,
                "partner_id": self.partner_a.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Draft guard bypass item",
                            "quantity": 1,
                            "price_unit": 50,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                        }
                    )
                ],
            }
        )
        draft_line = draft.invoice_line_ids[0]
        draft_line.with_user(self.accountant).write({"price_unit": 123})
        self.assertEqual(draft_line.price_unit, 123)

        posted = self._posted_invoice()
        posted_line = posted.invoice_line_ids[0]
        with self.assertRaises(UserError):
            posted_line.sudo().write({"price_unit": 456})
        self.assertEqual(posted_line.price_unit, 100)

    def test_posted_entries_reject_reset_cancel_and_history_erasure(self):
        invoice = self._posted_invoice()
        for record in (invoice.with_user(self.accountant), invoice.sudo()):
            for action in (record.button_draft, record.button_cancel, record.unlink):
                with self.assertRaises(UserError), self.cr.savepoint():
                    action()
            for values in ({"state": "draft"}, {"posted_before": False}, {"ref": "changed"}):
                with self.assertRaises(UserError), self.cr.savepoint():
                    record.write(values)
        self.assertEqual(invoice.state, "posted")
        self.assertTrue(invoice.posted_before)

    def test_posted_line_insert_delete_reparent_and_economic_fields_rejected(self):
        invoice = self._posted_invoice()
        line = invoice.invoice_line_ids[0].with_user(self.accountant)
        for values in ({"balance": 999}, {"partner_id": self.partner_b.id},
                       {"date_maturity": str(date_utils.add(line.date, days=10))}):
            with self.assertRaises(UserError), self.cr.savepoint():
                line.write(values)
        with self.assertRaises(UserError), self.cr.savepoint():
            line.unlink()
        with self.assertRaises(UserError), self.cr.savepoint():
            self.env["account.move.line"].create({
                "move_id": invoice.id, "name": "Injected", "account_id": line.account_id.id,
            })

    def test_native_reversal_preserves_original_posted_entry(self):
        invoice = self._posted_invoice().with_user(self.accountant)
        before = [(line.id, line.account_id.id, line.balance) for line in invoice.line_ids]
        reversal = invoice._reverse_moves([{"date": fields.Date.today()}], cancel=True)
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(reversal.state, "posted")
        self.assertEqual(reversal.reversed_entry_id, invoice)
        self.assertEqual(before, [(line.id, line.account_id.id, line.balance) for line in invoice.line_ids])
        self.assertEqual(invoice.amount_residual, 0)

    def test_closed_period_blocks_native_post_and_period_deletion(self):
        invoice = self._posted_invoice()
        period = self.env["thirdcode.accounting.period"].sudo().create({
            "name": "Locked test day", "company_id": self.company.id,
            "date_start": invoice.date, "date_end": invoice.date,
        })
        period.with_user(self.accountant).action_close()
        with self.assertRaises(UserError), self.cr.savepoint():
            invoice._reverse_moves([{"date": invoice.date}], cancel=True)
        with self.assertRaises(UserError):
            period.sudo().unlink()
        with self.assertRaises(UserError):
            period.sudo().write({"date_end": date_utils.add(invoice.date, days=1)})
        with self.assertRaises(AccessError):
            period.with_user(self.accountant).action_reopen()


    def _alignment_administrator(self):
        return self.env["res.users"].create({
            "name": "Alignment administrator", "login": "alignment-admin",
            "company_id": self.company.id, "company_ids": [Command.set(self.company.ids)],
            "groups_id": [Command.set(self.env.ref("thirdcode_accounting.group_thirdcode_administrator").ids)],
        })

    def test_direct_post_and_forged_tokens_cannot_bypass_policy(self):
        draft = self._posted_invoice().copy()
        for context in ({}, {"thirdcode_posting_token": True}, {"thirdcode_state_transition_token": True}):
            with self.assertRaises(UserError), self.cr.savepoint():
                draft.with_context(**context).write({"state": "posted", "posted_before": True})
        draft.action_post()
        self.assertEqual(draft.state, "posted")

    def test_open_period_reversal_can_correct_closed_period_original(self):
        invoice = self._posted_invoice().with_user(self.accountant)
        period = self.env["thirdcode.accounting.period"].sudo().create({
            "name": "Closed original", "company_id": self.company.id,
            "date_start": invoice.date, "date_end": invoice.date,
        })
        period.with_user(self.accountant).action_close()
        reversal = invoice._reverse_moves([{"date": date_utils.add(invoice.date, days=1)}], cancel=True)
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(reversal.state, "posted")
        self.assertEqual(invoice.amount_residual, 0)
        partials = invoice.line_ids.matched_debit_ids | invoice.line_ids.matched_credit_ids
        self.assertTrue(partials)
        self.assertTrue(all(partial.max_date > period.date_end for partial in partials))

    def test_closed_period_reconciliation_cannot_be_removed_or_forged(self):
        invoice = self._posted_invoice().with_user(self.accountant)
        invoice._reverse_moves([{"date": invoice.date}], cancel=True)
        period = self.env["thirdcode.accounting.period"].sudo().create({
            "name": "Closed reconciled day", "company_id": self.company.id,
            "date_start": invoice.date, "date_end": invoice.date,
        })
        period.with_user(self.accountant).action_close()
        with self.assertRaises(UserError), self.cr.savepoint():
            invoice.line_ids.remove_move_reconcile()
        partials = invoice.line_ids.matched_debit_ids | invoice.line_ids.matched_credit_ids
        with self.assertRaises(UserError):
            partials.write({"amount": 1})

    def test_line_audit_captures_actor_old_new_and_cannot_be_changed(self):
        draft = self._posted_invoice().copy().with_user(self.accountant)
        line = draft.invoice_line_ids[0]
        line.write({"name": "Audited changed narration"})
        logs = self.env["auditlog.log"].sudo().search([
            ("model_model", "=", "account.move.line"), ("res_id", "=", line.id), ("method", "=", "write"),
        ])
        details = logs.line_ids.filtered(lambda detail: detail.field_name == "name" and "Audited changed narration" in (detail.new_value or ""))
        self.assertTrue(details)
        self.assertEqual(details[-1].log_id.user_id, self.accountant)
        self.assertTrue(details[-1].old_value)
        self.assertTrue(details[-1].log_id.create_date)
        with self.assertRaises(AccessError):
            details.sudo().write({"old_value": "forged"})
        with self.assertRaises(AccessError):
            details.sudo().unlink()
        scoped = details[-1].log_id.with_user(self.accountant)
        self.assertTrue(scoped.read(["method"]))
        other_user = self.env["res.users"].create({
            "name": "Other audit reader", "login": "other-audit-reader",
            "company_id": self.other_company.id, "company_ids": [Command.set(self.other_company.ids)],
            "groups_id": [Command.set(self.env.ref("thirdcode_accounting.group_thirdcode_readonly").ids)],
        })
        with self.assertRaises(AccessError):
            scoped.with_user(other_user).read(["method"])

    def test_receipt_series_cannot_be_reset_consumed_or_deleted_directly(self):
        sequence = self.company._thirdcode_receipt_sequence()
        for values in ({"number_next": 1}, {"number_next_actual": 1}, {"use_date_range": True}):
            with self.assertRaises(UserError):
                sequence.write(values)
        with self.assertRaises(UserError):
            sequence.next_by_id()
        with self.assertRaises(UserError):
            sequence.unlink()

    def test_atomic_import_retry_and_changed_payload(self):
        administrator = self._alignment_administrator()
        model = self.env["account.move"].with_user(administrator)
        payload = {
            "company_id": self.company.id, "journal_id": self.company_data["default_journal_misc"].id,
            "date": str(fields.Date.today()), "move_type": "entry", "ref": "Synthetic migration",
            "thirdcode_source_identifier": "ATOMIC/1", "line_ids": [
                [0, 0, {"name": "Capital", "account_id": self.company_data["default_account_assets"].id, "debit": 100, "credit": 0}],
                [0, 0, {"name": "Capital", "account_id": self.company_data["default_account_revenue"].id, "debit": 0, "credit": 100}],
            ],
        }
        first = model.action_import_thirdcode_move(payload)
        retry = model.action_import_thirdcode_move(payload)
        self.assertTrue(first["created"])
        self.assertFalse(retry["created"])
        self.assertEqual(first["id"], retry["id"])
        with self.assertRaises(UserError):
            model.action_import_thirdcode_move(dict(payload, ref="Changed source"))
        failed = dict(payload, thirdcode_source_identifier="ATOMIC/FAIL", line_ids=payload["line_ids"][:1])
        with self.assertRaises(UserError), self.cr.savepoint():
            model.action_import_thirdcode_move(failed)
        self.assertFalse(model.search([("thirdcode_source_identifier", "=", "ATOMIC/FAIL")]))
        recovered = model.action_import_thirdcode_move(dict(payload, thirdcode_source_identifier="ATOMIC/FAIL"))
        self.assertEqual(model.browse(recovered["id"]).state, "posted")

    def test_comparative_financial_report_and_cash_flow_reconcile(self):
        self._posted_invoice()
        wizard = self.env["thirdcode.financial.report.wizard"].with_user(self.accountant).create({
            "company_id": self.company.id, "report_type": "balance_sheet",
            "date_from": fields.Date.today(), "date_to": fields.Date.today(),
            "comparison_date_from": fields.Date.today(), "comparison_date_to": fields.Date.today(),
        })
        data = wizard.get_report_data()
        self.assertTrue(data["balanced"])
        self.assertEqual(data["sections"], data["comparison"]["sections"])
        self.company.sudo().thirdcode_report_samples_approved = True
        self.assertIn("DRAFT", wizard.get_report_data()["layout_status"])
        cash = self.company_data["default_journal_bank"].default_account_id
        revenue = self.company_data["default_account_revenue"]
        self.env["account.move"].create({
            "company_id": self.company.id, "journal_id": self.company_data["default_journal_misc"].id,
            "date": fields.Date.today(), "line_ids": [
                Command.create({"name": "Cash sale", "account_id": cash.id, "debit": 75}),
                Command.create({"name": "Cash sale", "account_id": revenue.id, "credit": 75}),
            ],
        }).action_post()
        wizard.write({"report_type": "cash_flow"})
        data = wizard.get_report_data()
        self.assertEqual(data["cash_movement"], "75.00")
        self.assertEqual(data["cash_reconciliation_difference"], "0.00")
        self.assertFalse(data["classification_complete"])
        revenue.sudo().thirdcode_cash_flow_category = "operating"
        self.assertTrue(wizard.get_report_data()["classification_complete"])
        html, _ = self.env["ir.actions.report"].with_user(self.accountant)._render_qweb_html(
            "thirdcode_accounting.action_report_thirdcode_financial_statement", wizard.ids
        )
        self.assertIn(b"Cash reconciliation", html)
        self.assertIn(b"Operating activities", html)


    def test_year_end_transfer_does_not_erase_income_statement(self):
        invoice = self._posted_invoice()
        equity = self.env["account.account"].create({
            "name": "QA Retained earnings", "code": "YE9001", "account_type": "equity",
            "company_ids": [Command.set(self.company.ids)],
        })
        wizard = self.env["thirdcode.financial.report.wizard"].with_user(self.accountant).create({
            "company_id": self.company.id, "report_type": "profit_loss",
            "date_from": invoice.date, "date_to": invoice.date,
        })
        before = wizard.get_report_data()["net_result"]
        close = self.env["thirdcode.year.end.close"].with_user(self.accountant).create({
            "company_id": self.company.id, "date_end": invoice.date,
            "journal_id": self.company_data["default_journal_misc"].id,
            "retained_earnings_account_id": equity.id,
        })
        close.action_post()
        self.assertEqual(before, "100.00")
        self.assertEqual(wizard.get_report_data()["net_result"], before)
        wizard.report_type = "balance_sheet"
        self.assertTrue(wizard.get_report_data()["balanced"])
        close.move_id._reverse_moves([{"date": invoice.date}], cancel=True)
        wizard.report_type = "profit_loss"
        self.assertEqual(wizard.get_report_data()["net_result"], before)

    def test_context_defaults_cannot_forge_posting_or_closure_history(self):
        for context in ({"default_state": "posted"}, {"default_posted_before": True}):
            with self.assertRaises(UserError), self.cr.savepoint():
                self.env["account.move"].with_context(**context).create({
                    "company_id": self.company.id,
                    "journal_id": self.company_data["default_journal_misc"].id,
                })
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env["thirdcode.accounting.period"].sudo().with_context(
                default_closed_by=self.accountant.id
            ).create({"name": "Forged closure", "company_id": self.company.id,
                      "date_start": fields.Date.today(), "date_end": fields.Date.today()})
        with self.assertRaises(UserError), self.cr.savepoint():
            self.env["account.payment"].with_context(default_thirdcode_receipt_number="FORGED").create({
                "company_id": self.company.id, "partner_id": self.partner_a.id,
                "journal_id": self.company_data["default_journal_bank"].id, "amount": 10,
            })

    def test_receipt_rollback_retry_and_year_boundary_preserve_series(self):
        sequence = self.company._thirdcode_receipt_sequence()
        def posted_receipt(day):
            payment = self.env["account.payment"].create({
                "company_id": self.company.id, "journal_id": self.company_data["default_journal_bank"].id,
                "partner_id": self.partner_a.id, "amount": 10, "payment_type": "inbound",
                "partner_type": "customer", "date": day,
            })
            payment.action_post()
            self.assertTrue(payment.thirdcode_receipt_number)
            return payment
        next_before = sequence.number_next_actual
        with self.assertRaisesRegex(UserError, "Simulated downstream failure"), self.cr.savepoint():
            posted_receipt("2030-12-31")
            raise UserError("Simulated downstream failure")
        sequence.invalidate_recordset()
        self.assertEqual(sequence.number_next_actual, next_before)
        december = posted_receipt("2030-12-31")
        january = posted_receipt("2031-01-01")
        sequence.invalidate_recordset()
        self.assertEqual(sequence.number_next_actual, next_before + 2)
        self.assertNotEqual(december.thirdcode_receipt_number, january.thirdcode_receipt_number)
        january.action_assign_thirdcode_receipt_number()
        self.assertEqual(sequence.number_next_actual, next_before + 2)
        with self.assertRaises(UserError):
            january.action_cancel()

    def test_advance_later_allocation_and_customer_refund_reconcile(self):
        payment = self.env["account.payment"].create({
            "company_id": self.company.id, "journal_id": self.company_data["default_journal_bank"].id,
            "partner_id": self.partner_a.id, "amount": 100, "payment_type": "inbound", "partner_type": "customer",
        })
        payment.action_post()
        invoice = self._posted_invoice()
        (payment.move_id.line_ids | invoice.line_ids).filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        ).reconcile()
        self.assertEqual(invoice.amount_residual, 0)
        credit = invoice._reverse_moves([{"date": invoice.date}], cancel=False)
        credit.action_post()
        register = self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=credit.ids
        ).create({"journal_id": self.company_data["default_journal_bank"].id, "amount": 100})
        refunds = register._create_payments()
        self.assertEqual(credit.amount_residual, 0)
        self.assertEqual(refunds.payment_type, "outbound")
        all_moves = payment.move_id | invoice | credit | refunds.move_id
        self.assertTrue(all(move.state == "posted" for move in all_moves))
        self.assertAlmostEqual(sum(all_moves.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable").mapped("balance")), 0)

    def test_employee_reimbursement_and_company_paid_expense_post_to_ledger(self):
        administrator = self._alignment_administrator()
        employee = self.env["hr.employee"].sudo().create({
            "name": "Synthetic reimbursement employee", "company_id": self.company.id,
            "work_contact_id": self.partner_b.id,
        })
        product = self.env["product.product"].sudo().create({
            "name": "Synthetic expense", "can_be_expensed": True,
            "property_account_expense_id": self.company_data["default_account_expense"].id,
            "supplier_taxes_id": [Command.clear()],
        })
        bank = self.company_data["default_journal_bank"]
        for mode in ("own_account", "company_account"):
            sheet = self.env["hr.expense.sheet"].with_user(administrator).create({
                "name": "Synthetic " + mode, "company_id": self.company.id, "employee_id": employee.id,
                "journal_id": self.company_data["default_journal_purchase"].id,
                "payment_method_line_id": bank.outbound_payment_method_line_ids[:1].id,
                "expense_line_ids": [Command.create({
                    "name": "Synthetic reimbursement", "employee_id": employee.id, "company_id": self.company.id,
                    "product_id": product.id, "account_id": self.company_data["default_account_expense"].id,
                    "total_amount_currency": 25, "payment_mode": mode, "tax_ids": [Command.clear()],
                    "date": fields.Date.today(),
                })],
            })
            sheet.action_submit_sheet()
            sheet.action_approve_expense_sheets()
            sheet.action_sheet_move_post()
            moves = sheet.account_move_ids
            self.assertTrue(moves)
            self.assertTrue(all(move.state == "posted" for move in moves))
            self.assertAlmostEqual(sum(moves.line_ids.filtered(
                lambda line: line.account_id == self.company_data["default_account_expense"]
            ).mapped("balance")), 25)
            if mode == "own_account":
                self.env["account.payment.register"].with_user(administrator).with_context(
                    active_model="account.move", active_ids=moves.ids
                ).create({"journal_id": bank.id, "amount": 25})._create_payments()
                self.assertEqual(moves.amount_residual, 0)
            self.assertEqual(sheet.state, "done")


@tagged("post_install", "-at_install")
class TestExpenseRole(TestExpenseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.company_data["company"]
        cls.accountant = cls.env["res.users"].create({
            "name": "Expense workflow accountant",
            "login": "expense-workflow-accountant",
            "company_id": company.id,
            "company_ids": [Command.set([company.id])],
            "groups_id": [Command.set([
                cls.env.ref("thirdcode_accounting.group_thirdcode_accountant").id
            ])],
        })
        cls.unassigned_accountant = cls.env["res.users"].create({
            "name": "Unassigned expense accountant",
            "login": "unassigned-expense-accountant",
            "company_id": company.id,
            "company_ids": [Command.set([company.id])],
            "groups_id": [Command.set([
                cls.env.ref("thirdcode_accounting.group_thirdcode_accountant").id
            ])],
        })
        cls.expense_employee.expense_manager_id = cls.accountant

    def test_accountant_can_approve_post_and_reimburse_employee_expense(self):
        company = self.company_data["company"]
        sheet = self.create_expense_report({
            "name": "Synthetic employee reimbursement",
            "expense_line_ids": [Command.create({
                "name": "Synthetic employee purchase",
                "employee_id": self.expense_employee.id,
                "product_id": self.product_c.id,
                "total_amount_currency": 100.0,
                "tax_ids": [Command.clear()],
                "payment_mode": "own_account",
                "date": fields.Date.today(),
                "company_id": company.id,
                "currency_id": company.currency_id.id,
            })],
        })

        sheet.action_submit_sheet()
        with self.assertRaises(UserError):
            sheet.with_user(self.unassigned_accountant).action_approve_expense_sheets()
        sheet.with_user(self.accountant).action_approve_expense_sheets()
        sheet.with_user(self.accountant).action_sheet_move_post()

        self.assertEqual(sheet.state, "post")
        self.assertEqual(sheet.account_move_ids.state, "posted")
        self.assertEqual(sheet.payment_state, "not_paid")

        payment_register = self.env["account.payment.register"].with_user(
            self.accountant
        ).with_context(
            active_model="account.move", active_ids=sheet.account_move_ids.ids
        ).create({
            "journal_id": self.company_data["default_journal_bank"].id,
            "amount": sheet.total_amount,
        })
        payment_register.action_create_payments()

        self.assertEqual(sheet.payment_state, "paid")
