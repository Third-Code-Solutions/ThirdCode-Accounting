"""Native audit equivalence and query regressions for snapshot batching."""

from contextlib import nullcontext
from copy import deepcopy
import json
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.auditlog.models.log import AuditlogLogLine as NativeAuditLogLine
from odoo.addons.auditlog.models.rule import AuditlogRule as NativeAuditLogRule
from odoo.addons.auditlog.models.rule import ThrowAwayCache
from odoo.addons.thirdcode_accounting.models import auditlog as accounting_audit


@tagged("post_install", "-at_install")
class TestAuditMetadataPerformance(AccountTestInvoicingCommon):
    FIELD_NAMES = (
        "name", "ref", "date", "state", "move_type", "partner_id", "company_id",
        "journal_id", "line_ids", "invoice_line_ids", "currency_id", "amount_total",
    )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.actor = cls.env["res.users"].create({
            "name": "Audit metadata accountant", "login": "audit-metadata-accountant",
            "company_id": cls.company.id,
            "company_ids": [Command.set(cls.company.ids)],
            "groups_id": [Command.set(cls.env.ref(
                "thirdcode_accounting.group_thirdcode_accountant"
            ).ids)],
        })

    def _metadata(self, res_model, names, batch):
        rule = self.env["auditlog.rule"].sudo().with_context(prefetch_fields=False)
        model_id = self.env.registry._auditlog_model_cache[res_model]
        self.env.invalidate_all()
        with patch.dict(self.env.registry._auditlog_field_cache, {res_model: {}}):
            before = self.cr.sql_log_count
            if batch:
                rule._thirdcode_prefetch_audit_fields(res_model, names)
            result = {
                name: NativeAuditLogRule._get_field(rule, model_id, name)
                for name in names
            }
            count = self.cr.sql_log_count - before
            if batch:
                before_warm = self.cr.sql_log_count
                rule._thirdcode_prefetch_audit_fields(res_model, names)
                self.assertEqual(self.cr.sql_log_count, before_warm)
        return result, count

    def test_cold_metadata_matches_native_and_reduces_queries(self):
        names = [*self.FIELD_NAMES, "thirdcode_nonexistent_dummy_field"]
        expected, native_queries = self._metadata("account.move", names, False)
        actual, batch_queries = self._metadata("account.move", names, True)
        self.assertEqual(actual, expected)
        self.assertIs(actual["thirdcode_nonexistent_dummy_field"], False)
        self.assertLessEqual(batch_queries, native_queries - len(self.FIELD_NAMES))

    def test_inherited_field_ambiguity_keeps_native_resolution(self):
        rule = self.env["auditlog.rule"].sudo()
        model = self.env["ir.model"].browse(self.env.registry._auditlog_model_cache["res.users"])
        candidates = self.env["ir.model.fields"].search([
            ("model_id", "in", [model.id, *model.inherited_model_ids.ids]),
            ("name", "=", "name"),
        ])
        self.assertGreater(len(candidates), 1, "Fixture must exercise delegated inheritance")
        with patch.dict(self.env.registry._auditlog_field_cache, {"res.users": {}}):
            rule._thirdcode_prefetch_audit_fields("res.users", ["name"])
            self.assertNotIn("name", self.env.registry._auditlog_field_cache["res.users"])
            expected = NativeAuditLogRule._get_field(rule, model.id, "name")
            self.assertEqual(rule._get_field(model.id, "name"), expected)

    def test_detail_labels_and_values_match_native_with_fewer_queries(self):
        metadata = self.env["ir.model.fields"].search([
            ("model", "=", "account.move"), ("name", "in", list(self.FIELD_NAMES)),
        ])
        self.assertEqual(len(metadata), len(self.FIELD_NAMES))
        log = self.env["auditlog.log"].sudo().create({
            "model_id": self.env.registry._auditlog_model_cache["account.move"],
            "user_id": self.actor.id, "method": "write", "log_type": "full",
            "thirdcode_company_ids": [Command.set(self.company.ids)],
        })
        values = [{
            "log_id": log.id, "field_id": field_id,
            "old_value": "Before\n₱0.00", "old_value_text": "Before\n₱0.00",
            "new_value": "After\n₱100.00", "new_value_text": "After\n₱100.00",
        } for field_id in metadata.ids]
        model = self.env["auditlog.log.line"].sudo().with_context(prefetch_fields=False)
        self.env.invalidate_all()
        before = self.cr.sql_log_count
        expected = NativeAuditLogLine.create(model, deepcopy(values))
        native_queries = self.cr.sql_log_count - before
        self.env.invalidate_all()
        before = self.cr.sql_log_count
        actual = model.create(deepcopy(values))
        batch_queries = self.cr.sql_log_count - before
        columns = ["field_id", "field_name", "field_description", "old_value",
                   "new_value", "old_value_text", "new_value_text", "log_id"]
        def normalize(rows):
            return [{key: value for key, value in row.items() if key != "id"}
                    for row in rows.read(columns, load="_classic_write")]
        self.assertEqual(normalize(actual), normalize(expected))
        self.assertLessEqual(batch_queries, native_queries - len(metadata) + 1)
        with self.assertRaises(UserError), self.cr.savepoint():
            model.create([values[0].copy(), {"log_id": log.id}])

    def test_metadata_read_failure_does_not_publish_partial_cache(self):
        rule = self.env["auditlog.rule"].sudo()
        model_class = type(self.env["ir.model.fields"])
        with patch.dict(self.env.registry._auditlog_field_cache, {"account.move": {}}):
            with patch.object(model_class, "read", side_effect=UserError("Synthetic metadata failure")):
                with self.assertRaisesRegex(UserError, "Synthetic metadata failure"):
                    rule._thirdcode_prefetch_audit_fields("account.move", self.FIELD_NAMES)
            self.assertEqual(self.env.registry._auditlog_field_cache["account.move"], {})
            rule._thirdcode_prefetch_audit_fields("account.move", self.FIELD_NAMES)
            self.assertTrue(self.env.registry._auditlog_field_cache["account.move"]["ref"])

    def test_actual_invoice_audit_retains_actor_scope_values_and_immutability(self):
        invoice = self.env["account.move"].with_user(self.actor).create({
            "company_id": self.company.id, "move_type": "out_invoice",
            "partner_id": self.partner_a.id,
            "journal_id": self.company_data["default_journal_sale"].id,
            "invoice_date": fields.Date.today(), "ref": "Before metadata batching",
            "invoice_line_ids": [Command.create({
                "name": "Synthetic audit performance item", "quantity": 1, "price_unit": 100,
                "account_id": self.company_data["default_account_revenue"].id,
            })],
        })
        invoice.write({"ref": "After metadata batching"})
        logs = self.env["auditlog.log"].sudo().search([
            ("model_model", "=", "account.move"), ("res_id", "=", invoice.id),
            ("method", "=", "write"),
        ])
        detail = logs.line_ids.filtered(lambda line:
            line.field_name == "ref" and line.new_value == "After metadata batching")
        self.assertEqual(len(detail), 1)
        self.assertEqual(detail.old_value, "Before metadata batching")
        self.assertEqual(detail.old_value_text, detail.old_value)
        self.assertEqual(detail.new_value_text, detail.new_value)
        self.assertEqual(detail.log_id.user_id, self.actor)
        self.assertEqual(detail.log_id.thirdcode_company_ids, self.company)
        self.assertTrue(detail.log_id.create_date)
        self.assertTrue(detail.log_id.with_user(self.actor).read(["method"]))
        other_company = self.env["res.company"].create({"name": "Audit metadata other company"})
        other_reader = self.env["res.users"].create({
            "name": "Audit metadata other reader", "login": "audit-metadata-other-reader",
            "company_id": other_company.id, "company_ids": [Command.set(other_company.ids)],
            "groups_id": [Command.set(self.env.ref("thirdcode_accounting.group_thirdcode_readonly").ids)],
        })
        with self.assertRaises(AccessError):
            detail.log_id.with_user(other_reader).read(["method"])
        for record in (detail, detail.log_id):
            with self.assertRaises(AccessError):
                record.sudo().write({})
            with self.assertRaises(AccessError):
                record.sudo().unlink()

    def _snapshot_invoice(self):
        return self.env["account.move"].with_user(self.actor).create({
            "company_id": self.company.id, "move_type": "out_invoice",
            "partner_id": self.partner_a.id,
            "journal_id": self.company_data["default_journal_sale"].id,
            "invoice_date": fields.Date.today(), "ref": "Snapshot before",
            "invoice_line_ids": [Command.create({
                "name": "Snapshot item %s" % index, "quantity": 1,
                "price_unit": 100 + index,
                "account_id": self.company_data["default_account_revenue"].id,
                "tax_ids": [Command.clear()],
            }) for index in range(2)],
        })

    def _snapshot(self, records, batch, load="_classic_read", **context):
        names = self.env["auditlog.rule"].get_auditlog_fields(records)
        self.env.flush_all()
        records = records.sudo().with_context(
            auditlog_disabled=True, prefetch_fields=False, **context
        )
        native = patch.object(accounting_audit, "_prefetch_audit_relation_labels")
        with nullcontext() if batch else native:
            with ThrowAwayCache(records.env):
                before = self.cr.sql_log_count
                values = records.read(names, load=load)
                queries = self.cr.sql_log_count - before
        return values, queries

    def test_accounting_snapshots_match_all_native_values_with_fewer_queries(self):
        invoice = self._snapshot_invoice()
        for records in (invoice, invoice.line_ids):
            with self.subTest(model=records._name):
                expected, native_queries = self._snapshot(records, False)
                actual, batch_queries = self._snapshot(records, True)
                self.assertEqual(actual, expected)
                self.assertLess(batch_queries, native_queries)
                self.assertIn("company_id", actual[0])
        self.assertEqual(actual[0]["company_id"][0], self.company.id)

    def test_snapshot_labels_preserve_language_company_and_display_context(self):
        invoice = self._snapshot_invoice()
        self.env["res.lang"]._activate_lang("fr_FR")
        for context in (
            {"lang": "en_US", "allowed_company_ids": self.company.ids},
            {"lang": "fr_FR", "allowed_company_ids": self.company.ids,
             "show_address": True, "show_vat": True},
        ):
            with self.subTest(context=context):
                for records in (invoice, invoice.line_ids):
                    self.assertEqual(
                        self._snapshot(records, True, **context)[0],
                        self._snapshot(records, False, **context)[0],
                    )
        # Raw relation IDs need no label fetches at all.
        self.assertEqual(
            self._snapshot(invoice, True, load="_classic_write"),
            self._snapshot(invoice, False, load="_classic_write"),
        )

    def test_write_and_post_emit_identical_full_audit_history(self):
        invoice = self._snapshot_invoice()
        line = invoice.invoice_line_ids[0]
        tracked = {"account.move": invoice.ids, "account.move.line": invoice.line_ids.ids}

        class RollbackComparison(Exception):
            pass

        def history(batch):
            rows = []
            native = patch.object(accounting_audit, "_prefetch_audit_relation_labels")
            with self.assertRaises(RollbackComparison), self.cr.savepoint():
                start_id = self.env["auditlog.log"].sudo().search([], order="id desc", limit=1).id
                with nullcontext() if batch else native:
                    invoice.write({
                        "ref": "Snapshot after",
                        "invoice_line_ids": [Command.update(line.id, {"price_unit": 150})],
                    })
                    invoice.action_post()
                logs = self.env["auditlog.log"].sudo().search([("id", ">", start_id)], order="id")
                for log in logs:
                    if log.res_id not in tracked.get(log.model_model, []):
                        continue
                    self.assertTrue(log.create_date)
                    self.assertEqual(log.user_id, self.actor)
                    self.assertEqual(log.thirdcode_company_ids, self.company)
                    rows.append({
                        "model": log.model_model, "res_id": log.res_id,
                        "method": log.method, "log_type": log.log_type,
                        "actor": log.user_id.id, "companies": log.thirdcode_company_ids.ids,
                        "details": sorted([{
                            key: value for key, value in detail.items() if key != "id"
                        } for detail in log.line_ids.read([
                            "field_id", "field_name", "field_description", "old_value",
                            "old_value_text", "new_value", "new_value_text",
                        ], load="_classic_write")], key=lambda row: row["field_name"]),
                    })
                raise RollbackComparison()
            return sorted(rows, key=lambda row: json.dumps(row, sort_keys=True))

        expected = history(False)
        actual = history(True)
        self.assertTrue(expected)
        self.assertEqual(actual, expected)
        details = [detail for row in actual for detail in row["details"]]
        self.assertTrue(any(detail["field_name"] == "state" and detail["new_value"] == "posted"
                            for detail in details))
        self.assertTrue(any(detail["field_name"] == "amount_total" for detail in details))

    def test_snapshot_cache_is_discarded_on_success_and_failure(self):
        invoice = self._snapshot_invoice()
        self.env.flush_all()
        unsaved = self.env["account.move"].new({"ref": "Unsaved caller cache"})
        original_cache = self.env.cache
        original_tocompute = self.env.transaction.tocompute
        self._snapshot(invoice, True)
        self.assertIs(self.env.cache, original_cache)
        self.assertIs(self.env.transaction.tocompute, original_tocompute)
        self.assertEqual(unsaved.ref, "Unsaved caller cache")
        with patch.object(type(self.env["res.partner"]), "fetch",
                          side_effect=UserError("Synthetic label dependency failure")):
            with self.assertRaisesRegex(UserError, "Synthetic label dependency failure"):
                self._snapshot(invoice, True)
        self.assertIs(self.env.cache, original_cache)
        self.assertIs(self.env.transaction.tocompute, original_tocompute)
        self.assertEqual(unsaved.ref, "Unsaved caller cache")

    def test_snapshot_optimization_does_not_grant_read_or_post_access(self):
        invoice = self._snapshot_invoice()
        other_company = self.env["res.company"].create({"name": "Snapshot outside company"})
        reader = self.env["res.users"].create({
            "name": "Snapshot outside reader", "login": "snapshot-outside-reader",
            "company_id": other_company.id,
            "company_ids": [Command.set(other_company.ids)],
            "groups_id": [Command.set(self.env.ref(
                "thirdcode_accounting.group_thirdcode_readonly"
            ).ids)],
        })
        with self.assertRaises(AccessError):
            invoice.with_user(reader).with_context(
                auditlog_disabled=True, prefetch_fields=False,
                allowed_company_ids=reader.company_ids.ids,
            ).read(["partner_id", "amount_total"])
        encoder = self.env["res.users"].create({
            "name": "Snapshot encoder", "login": "snapshot-encoder",
            "company_id": self.company.id, "company_ids": [Command.set(self.company.ids)],
            "groups_id": [Command.set(self.env.ref(
                "thirdcode_accounting.group_thirdcode_encoder"
            ).ids)],
        })
        with self.assertRaises(AccessError), self.cr.savepoint():
            invoice.with_user(encoder).with_context(
                auditlog_disabled=True, prefetch_fields=False,
            ).action_post()
