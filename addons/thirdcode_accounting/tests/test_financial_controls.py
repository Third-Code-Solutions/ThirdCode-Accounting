import base64

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tools import date_utils
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestFinancialControls(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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

    def test_statement_line_sync_updates_posted_move_without_opening_direct_write(self):
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

        statement_line.with_user(self.accountant).write({"amount": 11})

        self.assertEqual(statement_line.amount, 11)
        self.assertEqual(move.state, "posted")
        liquidity_lines, _, _ = statement_line._seek_for_lines()
        self.assertEqual(abs(sum(liquidity_lines.mapped("balance"))), 11)
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
