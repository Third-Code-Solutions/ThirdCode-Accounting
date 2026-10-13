from datetime import timedelta
from unittest.mock import patch

from psycopg2.errors import SerializationFailure

from odoo import SUPERUSER_ID, Command, fields
from odoo.exceptions import AccessDenied, AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import AccountTestInvoicingCommon
from ..models.write_tokens import RECURRING_MOVE_TOKEN


@tagged("post_install", "-at_install")
class TestRecurringCron(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.partner_a.company_id = cls.company
        cls.today = fields.Date.context_today(cls.env.user)
        cls.accountant = cls.env["res.users"].create({
            "name": "Recurring cron accountant", "login": "recurring-cron-accountant",
            "company_id": cls.company.id, "company_ids": [Command.set(cls.company.ids)],
            "groups_id": [Command.set(cls.env.ref(
                "thirdcode_accounting.group_thirdcode_accountant"
            ).ids)],
        })
        cls.encoder = cls.env["res.users"].create({
            "name": "Recurring cron encoder", "login": "recurring-cron-encoder",
            "company_id": cls.company.id, "company_ids": [Command.set(cls.company.ids)],
            "groups_id": [Command.set(cls.env.ref("thirdcode_accounting.group_thirdcode_encoder").ids)],
        })

    def _journal(self, reference, **values):
        return self.env["thirdcode.recurring.journal"].with_user(self.accountant).create({
            "name": reference, "reference": reference, "company_id": self.company.id,
            "journal_id": self.company_data["default_journal_misc"].id,
            "next_run": self.today,
            "line_ids": [
                Command.create({"account_id": self.company_data["default_account_expense"].id, "debit": 10}),
                Command.create({"account_id": self.company_data["default_account_revenue"].id, "credit": 10}),
            ],
            **values,
        })

    def _invoice_line(self):
        return Command.create({
            "name": "Recurring item", "account_id": self.company_data["default_account_revenue"].id,
            "quantity": 1, "price_unit": 10,
        })

    def _invoice(self, reference, **values):
        return self.env["thirdcode.recurring.invoice"].with_user(self.accountant).create({
            "name": reference, "reference": reference, "company_id": self.company.id,
            "journal_id": self.company_data["default_journal_sale"].id,
            "partner_id": self.partner_a.id, "next_run": self.today,
            "line_ids": [self._invoice_line()],
            **values,
        })

    def test_recurring_tax_type_matches_document_on_create_edit_and_run(self):
        for move_type, tax_type, journal_key, account_key in (
            ("out_invoice", "sale", "default_journal_sale", "default_account_revenue"),
            ("in_invoice", "purchase", "default_journal_purchase", "default_account_expense"),
        ):
            with self.subTest(move_type=move_type):
                opposite = "purchase" if tax_type == "sale" else "sale"
                tax = self.env["account.tax"].create({
                    "name": "Recurring %s VAT" % tax_type, "amount": 12,
                    "type_tax_use": tax_type, "company_id": self.company.id,
                })
                wrong_tax = tax.copy({"type_tax_use": opposite})
                values = {"move_type": move_type, "journal_id": self.company_data[journal_key].id,
                    "line_ids": [Command.create({"account_id": self.company_data[account_key].id,
                        "quantity": 1, "price_unit": 10, "tax_ids": [Command.set(tax.ids)]})]}
                record = self._invoice("TAX-TYPE-%s" % tax_type, **values)
                with self.assertRaises(ValidationError), self.cr.savepoint():
                    self._invoice("WRONG-TAX-%s" % tax_type, **{**values,
                        "line_ids": [Command.create({"account_id": self.company_data[account_key].id,
                            "quantity": 1, "price_unit": 10, "tax_ids": [Command.set(wrong_tax.ids)]})]})
                with self.assertRaises(ValidationError), self.cr.savepoint():
                    record.line_ids.write({"tax_ids": [Command.set(wrong_tax.ids)]})
                with self.assertRaises(ValidationError), self.cr.savepoint():
                    record.write({"move_type": "in_invoice" if tax_type == "sale" else "out_invoice",
                        "journal_id": self.company_data["default_journal_purchase" if tax_type == "sale" else "default_journal_sale"].id})
                tax.write({"type_tax_use": opposite})
                with self.assertRaises(ValidationError), self.cr.savepoint():
                    record.action_run_now()
                self.assertFalse(record.generated_move_ids)
                tax.write({"type_tax_use": tax_type})
                record.action_run_now()
                self.assertEqual(record.generated_move_ids.state, "posted")
                self.assertAlmostEqual(record.generated_move_ids.amount_total, 11.20, places=2)

    def _run_cron(self):
        cron = self.env.ref("thirdcode_accounting.ir_cron_thirdcode_recurring_journals").sudo()
        cron.ir_actions_server_id.with_user(cron.user_id).run()

    def test_root_cron_isolates_failures_and_retries_without_duplicates(self):
        before = self._journal("CRON-BEFORE")
        failed = self._journal("CRON-PARTIAL", next_run=self.today - timedelta(days=1), interval_type="days")
        after = self._journal("CRON-AFTER")
        invoice_before = self._invoice("CRON-INVOICE-BEFORE")
        failed_invoice = self._invoice("CRON-INVOICE-EMPTY", line_ids=[])
        invoice_after = self._invoice("CRON-INVOICE-AFTER")
        original = type(failed)._prepare_move_values

        def reject_second_run(record, day):
            if record == failed and day == self.today:
                raise UserError("Review <script>blocked</script> definition")
            return original(record, day)

        with patch.object(type(failed), "_prepare_move_values", reject_second_run):
            self._run_cron()
        for record in (before, after, invoice_before, invoice_after):
            self.assertEqual(len(record.generated_move_ids), 1)
            self.assertEqual(record.generated_move_ids.state, "posted")
            self.assertFalse(record.last_cron_error)
        self.assertFalse(failed.generated_move_ids)
        self.assertFalse(failed_invoice.generated_move_ids)
        self.assertEqual(failed.next_run, self.today - timedelta(days=1))
        self.assertEqual(failed_invoice.next_run, self.today)
        self.assertFalse(failed.last_run)
        self.assertIn("<script>", failed.last_cron_error)
        self.assertTrue(failed.last_cron_error_at)
        self.assertTrue(failed_invoice.last_cron_error)

        failed_invoice.line_ids = [self._invoice_line()]
        failed_invoice.with_user(self.accountant).action_run_due()
        self.assertFalse(failed_invoice.last_cron_error)
        self.assertFalse(failed_invoice.last_cron_error_at)
        self._run_cron()
        self.assertEqual(len(failed.generated_move_ids), 2)
        self.assertEqual(len(failed_invoice.generated_move_ids), 1)
        for record in (failed, failed_invoice):
            self.assertFalse(record.last_cron_error)
            self.assertFalse(record.last_cron_error_at)
        all_moves = (before | failed | after).generated_move_ids | (invoice_before | failed_invoice | invoice_after).generated_move_ids
        self.assertEqual(len(all_moves), 7)
        self._run_cron()
        self.assertEqual(
            (before | failed | after).generated_move_ids | (invoice_before | failed_invoice | invoice_after).generated_move_ids,
            all_moves,
        )

    def test_manual_errors_and_unexpected_cron_errors_propagate(self):
        for model_name, record in (
            ("thirdcode.recurring.journal", self._journal("CRON-ERROR-JOURNAL", line_ids=[])),
            ("thirdcode.recurring.invoice", self._invoice("CRON-ERROR-INVOICE", line_ids=[])),
        ):
            with self.subTest(model=model_name):
                # Sudo for an ordinary user must not acquire the root cron exemption.
                with self.assertRaises(AccessError), self.cr.savepoint():
                    record.with_user(self.env.user).sudo().action_run_due()
                with self.assertRaises(UserError), self.cr.savepoint():
                    record.with_user(self.accountant).action_run_due()
                self.assertFalse(record.last_cron_error)
                for error in (AccessError, AccessDenied, RuntimeError, SerializationFailure):
                    with self.subTest(error=error.__name__):
                        with patch.object(type(record), "action_run_due", side_effect=error("unexpected")):
                            with self.assertRaises(error), self.cr.savepoint():
                                self.env[model_name].with_user(self.accountant)._cron_run_due()
                        self.assertFalse(record.last_cron_error)

    def test_failure_metadata_is_system_managed_and_company_scoped(self):
        records = [
            self._journal("CRON-SCOPED-JOURNAL", line_ids=[]),
            self._invoice("CRON-SCOPED-INVOICE", line_ids=[]),
        ]
        self._run_cron()
        other_company = self.env["res.company"].sudo().create({"name": "Cron other company"})
        outsider = self.env["res.users"].sudo().create({
            "name": "Cron outsider", "login": "cron-outsider",
            "company_id": other_company.id, "company_ids": [Command.set(other_company.ids)],
            "groups_id": [Command.set(self.env.ref("thirdcode_accounting.group_thirdcode_readonly").ids)],
        })
        for record in records:
            with self.subTest(model=record._name):
                self.assertTrue(record.with_user(self.accountant).last_cron_error)
                with self.assertRaises(AccessError), self.cr.savepoint():
                    record.with_user(self.accountant).write({"last_cron_error": False})
                with self.assertRaises(AccessError), self.cr.savepoint():
                    self.env[record._name].with_user(self.accountant).with_context(
                        default_last_cron_error="Forged status"
                    ).create({})
                with self.assertRaises(AccessError):
                    record.with_user(outsider).with_context(allowed_company_ids=other_company.ids).read(["last_cron_error"])

    def test_recurring_definitions_reject_hidden_partner_references(self):
        hidden = self.env["res.partner"].sudo().create({"name": "Private unassigned contact", "company_id": False})
        with self.assertRaises(AccessError):
            hidden.with_user(self.accountant).read(["name"])
        with self.assertRaises(AccessError), self.cr.savepoint():
            self._invoice("CRON-HIDDEN", partner_id=hidden.id)
        invoice = self._invoice("CRON-VISIBLE")
        with self.assertRaises(AccessError), self.cr.savepoint():
            invoice.write({"partner_id": hidden.id})
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env["thirdcode.recurring.invoice"].with_user(self.accountant).with_context(
                default_partner_id=hidden.id
            ).create({
                "name": "Hidden default", "reference": "CRON-HIDDEN-DEFAULT",
                "company_id": self.company.id, "journal_id": self.company_data["default_journal_sale"].id,
            })
        journal = self._journal("CRON-VISIBLE-JOURNAL")
        with self.assertRaises(AccessError), self.cr.savepoint():
            journal.line_ids[0].write({"partner_id": hidden.id})
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env["thirdcode.recurring.journal.line"].with_user(self.accountant).with_context(
                default_partner_id=hidden.id
            ).create({"recurring_id": journal.id, "account_id": self.company_data["default_account_revenue"].id})

    def test_encoder_cannot_supply_recurring_provenance(self):
        definitions = [
            (self._journal("CRON-ENCODER-JOURNAL"), "thirdcode_recurring_journal_id", "thirdcode_recurring_run_date"),
            (self._invoice("CRON-ENCODER-INVOICE"), "thirdcode_recurring_invoice_id", "thirdcode_recurring_invoice_run_date"),
        ]
        for definition, link_field, date_field in definitions:
            values = definition._prepare_move_values(self.today)
            provenance = {field: values.pop(field) for field in (link_field, date_field)}
            model = self.env["account.move"].with_user(self.encoder)
            draft = model.create(values)
            with self.subTest(model=definition._name):
                for field, value in provenance.items():
                    with self.assertRaises(AccessError), self.cr.savepoint():
                        model.create(dict(values, **{field: value}))
                    with self.assertRaises(AccessError), self.cr.savepoint():
                        model.with_context(**{"default_" + field: value}).create(values)
                    with self.assertRaises(AccessError), self.cr.savepoint():
                        draft.write({field: value})
                with self.assertRaises(AccessError), self.cr.savepoint():
                    model.with_context(thirdcode_recurring_move_token=True).create({**values, **provenance})
                self.assertEqual(draft.state, "draft")
        self._run_cron()
        for definition, _link_field, _date_field in definitions:
            self.assertEqual(len(definition.generated_move_ids), 1)
            self.assertEqual(definition.generated_move_ids.state, "posted")

    def test_cron_refuses_preexisting_unposted_run_documents(self):
        for factory in (self._journal, self._invoice):
            definition = factory("CRON-LEGACY-DOCUMENT")
            # Trusted fixture simulates an old forged link without weakening guards.
            move = self.env["account.move"].with_context(
                thirdcode_recurring_move_token=RECURRING_MOVE_TOKEN,
            ).create(definition._prepare_move_values(self.today))
            self._run_cron()
            self.assertEqual(move.state, "draft")
            self.assertEqual(definition.generated_move_ids, move)
            self.assertEqual(definition.next_run, self.today)
            self.assertIn("will not be posted automatically", definition.last_cron_error)

    def test_cron_rejects_wrong_type_posted_run_document(self):
        definition = self._invoice("CRON-LEGACY-WRONG-TYPE")
        values = self._journal("CRON-FIXTURE-ONLY", active=False)._prepare_move_values(self.today)
        values.pop("thirdcode_recurring_journal_id")
        values.pop("thirdcode_recurring_run_date")
        values.update({"thirdcode_recurring_invoice_id": definition.id,
                       "thirdcode_recurring_invoice_run_date": self.today})
        move = self.env["account.move"].with_context(
            thirdcode_recurring_move_token=RECURRING_MOVE_TOKEN,
        ).create(values)
        move.action_post()
        self._run_cron()
        self.assertEqual(definition.next_run, self.today)
        self.assertIn("different company or document type", definition.last_cron_error)

    def test_root_cron_rechecks_revoked_shared_contacts_and_commercial_parent(self):
        shared = self.env["res.partner"].with_user(SUPERUSER_ID).create({
            "name": "Approved shared contact", "company_id": False,
            "thirdcode_shared_company_ids": [Command.set(self.company.ids)],
        })
        shared_invoice = self._invoice("CRON-SHARED", partner_id=shared.id)
        journal = self._journal("CRON-SHARED-JOURNAL")
        journal.line_ids.write({"partner_id": shared.id})
        self._run_cron()
        self.assertEqual(shared_invoice.generated_move_ids.state, "posted")
        self.assertEqual(journal.generated_move_ids.state, "posted")

        blocked_invoice = self._invoice("CRON-REVOKED", partner_id=shared.id)
        blocked_journal = self._journal("CRON-REVOKED-JOURNAL")
        blocked_journal.line_ids.write({"partner_id": shared.id})
        drafted_invoice = self._invoice("CRON-REVOKED-DRAFT", partner_id=shared.id)
        draft = self.env["account.move"].with_user(SUPERUSER_ID).with_context(
            thirdcode_recurring_move_token=RECURRING_MOVE_TOKEN,
        ).create(
            drafted_invoice._prepare_move_values(self.today)
        )
        shared.write({"thirdcode_shared_company_ids": [Command.clear()]})
        healthy = self._invoice("CRON-HEALTHY-AFTER-REVOKE")
        self._run_cron()
        for record in (blocked_invoice, blocked_journal):
            self.assertFalse(record.generated_move_ids)
            self.assertEqual(record.next_run, self.today)
            self.assertTrue(record.last_cron_error)
        self.assertEqual(healthy.generated_move_ids.state, "posted")
        self.assertEqual(draft.state, "draft")
        self.assertEqual(drafted_invoice.next_run, self.today)
        self.assertTrue(drafted_invoice.last_cron_error)

        parent = self.env["res.partner"].with_user(SUPERUSER_ID).create({
            "name": "Shared commercial parent", "is_company": True, "company_id": False,
            "thirdcode_shared_company_ids": [Command.set(self.company.ids)],
        })
        child = self.env["res.partner"].with_user(SUPERUSER_ID).create({
            "name": "Visible invoice contact", "parent_id": parent.id, "company_id": False,
            "thirdcode_shared_company_ids": [Command.set(self.company.ids)],
        })
        child_invoice = self._invoice("CRON-COMMERCIAL-PARENT", partner_id=child.id)
        parent.write({"thirdcode_shared_company_ids": [Command.clear()]})
        self._run_cron()
        self.assertFalse(child_invoice.generated_move_ids)
        self.assertTrue(child_invoice.last_cron_error)
