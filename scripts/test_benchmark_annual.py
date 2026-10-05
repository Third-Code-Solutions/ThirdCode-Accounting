"""Scope, workload and evidence regressions; native smoke remains a separate gate."""
import contextlib
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import benchmark_annual as annual
import test_annual_native as native


def arguments(*extra):
    return annual.parse_args([
        "--config", "/isolated.conf", "--database", "tcsi_alignment_test",
        "--confirm-isolated-database", "tcsi_alignment_test", "--company-id", "14", "--actor-id", "11",
        "--year", "2025", "--output-directory", "/private/new-evidence", *extra,
    ])


class AnnualBenchmarkTests(unittest.TestCase):
    def test_production_and_inexact_confirmation_fail_before_native_loading(self):
        with contextlib.redirect_stderr(io.StringIO()):
            for extra in (("--database", "tcsi_pilot"), ("--confirm-isolated-database", "tcsi_alignment_other"), ("--actor-id", "1")):
                with self.subTest(extra=extra), self.assertRaises(SystemExit):
                    arguments(*extra)

    def test_budget_and_pdf_endpoint_are_explicit(self):
        invalid = (("--seed-documents", "2"), ("--max-seed-seconds", "nan"), ("--target-seconds", "inf"),
                   ("--render-pdf",), ("--render-pdf", "--report-url", "https://customer.example"))
        with contextlib.redirect_stderr(io.StringIO()):
            for extra in invalid:
                with self.subTest(extra=extra), self.assertRaises(SystemExit):
                    arguments(*extra)
        self.assertEqual(arguments("--render-pdf", "--report-url", "http://127.0.0.1:18068").report_url,
                         "http://127.0.0.1:18068")

    def test_smoke_contains_both_document_directions_in_every_month_and_both_settlements(self):
        plan = annual.plan_documents(2025, 24, 3)
        self.assertEqual(len(plan), 24)
        for month in range(1, 13):
            documents = [x for x in plan if x["date"][5:7] == f"{month:02}"]
            self.assertEqual({x["move_type"] for x in documents}, {"out_invoice", "in_invoice"})
        settlements = [x for x in plan if x["settle"]]
        self.assertEqual(len(settlements), 8)
        self.assertEqual({x["move_type"] for x in settlements}, {"out_invoice", "in_invoice"})

    def test_larger_scenario_estimate_is_ten_thousand_lines_without_claiming_actual_volume(self):
        plan = annual.plan_documents(2025, 3750, 3)
        self.assertEqual(len(plan) * 2 + sum(x["settle"] for x in plan) * 2, 10000)
        for direction in ("out_invoice", "in_invoice"):
            self.assertEqual(sum(x["move_type"] == direction for x in plan), 1875)
            self.assertEqual(sum(x["move_type"] == direction and x["settle"] for x in plan), 625)
        self.assertEqual(len({x["date"][5:7] for x in plan}), 12)
        self.assertEqual(arguments().seed_documents, 0)

    def test_capacity_is_fixed_opt_in_and_default_smoke_keeps_original_budgets(self):
        default = native.scenario_settings({})
        self.assertEqual((default["documents"], default["max_seed_seconds"], default["benchmark_seconds"], default["deadline_seconds"]),
                         (24, 180, 300, 0))
        capacity = native.scenario_settings({"TCSI_ANNUAL_CAPACITY_CI": "engineering-only", "GITHUB_ACTIONS": "true"})
        self.assertEqual((capacity["documents"], capacity["max_seed_seconds"], capacity["deadline_seconds"]), (3750, 3300, 3600))
        for bad in ({"TCSI_ANNUAL_CAPACITY_CI": "3751"}, {"TCSI_ANNUAL_CAPACITY_CI": "engineering-only"},
                    {"TCSI_ANNUAL_CAPACITY_CI": "engineering-only", "GITHUB_ACTIONS": "true", "PGHOSTADDR": "192.0.2.1"}):
            with self.subTest(bad=bad), self.assertRaises(RuntimeError):
                native.scenario_settings(bad)

    def test_invalid_capacity_fails_before_directory_or_database_access(self):
        environ = {"TCSI_ANNUAL_NATIVE_CI": "disposable-only", "PGHOST": "127.0.0.1", "PGUSER": "odoo",
                   "PGPASSWORD": "ci-only", "TCSI_ANNUAL_CAPACITY_CI": "3751"}
        with patch.dict("os.environ", environ, clear=True), patch.object(Path, "mkdir") as mkdir, \
                patch.object(native, "clone_database") as clone, self.assertRaises(RuntimeError):
            native.main()
        mkdir.assert_not_called()
        clone.assert_not_called()

    def test_capacity_totals_reject_balanced_but_incomplete_or_out_of_scope_ledger(self):
        totals = {"documents": 3750, "invoices": 1875, "bills": 1875, "document_amount": "375000.00",
                  "payments": 1250, "inbound": 625, "outbound": 625, "payment_amount": "125000.00",
                  "moves": 5000, "lines": 10000, "debit": "500000.00", "credit": "500000.00", "months": 12,
                  "scope_valid": True}
        native.verify_capacity_totals(totals)
        for changed in ({"debit": 499900, "credit": 499900}, {"invoices": 1876, "bills": 1874},
                        {"payment_amount": 124900}, {"scope_valid": False}, {"months": 11}):
            with self.subTest(changed=changed), self.assertRaises(RuntimeError):
                native.verify_capacity_totals({**totals, **changed})

    def test_capacity_verifier_closes_connection_when_readonly_setup_fails(self):
        connection = MagicMock()
        connection.set_session.side_effect = RuntimeError("read-only setup failed")
        postgres = SimpleNamespace(connect=MagicMock(return_value=connection))
        environ = {"PGHOST": "127.0.0.1", "PGUSER": "odoo", "PGPASSWORD": "ci-only"}
        with patch.dict("sys.modules", {"psycopg2": postgres}), patch.dict("os.environ", environ, clear=True), \
                self.assertRaisesRegex(RuntimeError, "read-only setup failed"):
            native.capacity_ledger_totals("tcsi_alignment_annual_ci_test", {})
        connection.close.assert_called_once()
        connection.cursor.assert_not_called()

    def test_payment_entry_with_copied_invoice_ref_is_not_counted_as_an_invoice(self):
        # Execute the verifier's actual aggregate SQL on a tiny relational fixture.
        # Only PostgreSQL session setup/placeholders/functions are adapted here.
        database = "tcsi_alignment_annual_ci_test"
        db = sqlite3.connect(":memory:")
        class BoolAnd:
            def __init__(self):
                self.value = True
            def step(self, value):
                self.value = self.value and bool(value)
            def finalize(self):
                return self.value
        db.create_aggregate("bool_and", 1, BoolAnd)
        db.create_function("starts_with", 2, lambda value, prefix: value.startswith(prefix))
        db.create_function("date_trunc", 2, lambda _unit, value: value[:7])
        db.executescript("""
            CREATE TABLE account_move (id,partner_id,ref,move_type,amount_total,company_id,state,date);
            INSERT INTO account_move VALUES
              (1,20,'TC-ANNUAL-run-0','out_invoice',100,1,'posted','2025-01-15'),
              (2,20,'TC-ANNUAL-run-1','in_invoice',100,1,'posted','2025-01-15'),
              (3,20,'TC-ANNUAL-run-0','entry',100,1,'posted','2025-01-15');
            CREATE TABLE account_payment (partner_id,payment_type,amount,company_id,date,move_id);
            INSERT INTO account_payment VALUES (20,'inbound',100,1,'2025-01-15',3);
            CREATE TABLE account_move_line (id,move_id,debit,credit,company_id);
            INSERT INTO account_move_line VALUES
              (1,1,100,0,1),(2,1,0,100,1),(3,2,100,0,1),(4,2,0,100,1),(5,3,100,0,1),(6,3,0,100,1);
        """)
        class Cursor:
            row = None
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                pass
            def execute(self, query, values=()):
                if query.startswith("SET LOCAL"):
                    return
                if query == "SELECT current_database()":
                    self.row = (database,)
                    return
                row = db.execute(query.replace("%s", "?"), values).fetchone()
                self.row = (*row[:-1], bool(row[-1]))
            def fetchone(self):
                return self.row
        connection = SimpleNamespace(set_session=lambda **_kw: None, cursor=Cursor, rollback=lambda: None, close=db.close)
        postgres = SimpleNamespace(connect=lambda **_kw: connection)
        environ = {"PGHOST": "127.0.0.1", "PGUSER": "odoo", "PGPASSWORD": "ci-only"}
        with patch.dict("sys.modules", {"psycopg2": postgres}), patch.dict("os.environ", environ, clear=True):
            totals = native.capacity_ledger_totals(database, {"partner_id": 20, "run_id": "run"})
        self.assertEqual((totals["documents"], totals["invoices"], totals["bills"], totals["document_amount"]), (2, 1, 1, 200))
        self.assertEqual((totals["payments"], totals["moves"], totals["lines"], totals["debit"], totals["credit"]), (1, 3, 6, 300, 300))
        self.assertTrue(totals["scope_valid"])

    def test_capacity_timeout_retains_failure_and_cleans_every_owned_process(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "new-capacity"
            environ = {"TCSI_ANNUAL_NATIVE_CI": "disposable-only", "PGHOST": "127.0.0.1", "PGUSER": "odoo",
                       "PGPASSWORD": "ci-only", "TCSI_ANNUAL_CAPACITY_CI": "engineering-only", "GITHUB_ACTIONS": "true",
                       "TCSI_ANNUAL_EVIDENCE": str(output)}
            bootstrap, server, benchmark = MagicMock(), MagicMock(), MagicMock()
            bootstrap.wait.return_value = 0
            benchmark.wait.side_effect = subprocess.TimeoutExpired("native benchmark", 3600)
            with patch.dict("os.environ", environ, clear=True), patch.object(native.sys, "platform", "linux"), \
                    patch.object(native.signal, "signal"), patch.object(native.signal, "alarm", create=True) as alarm, \
                    patch.object(native.socket, "socket"), patch.object(native, "clone_database", return_value=0), \
                    patch.object(native, "write_configuration"), patch.object(native, "ready"), \
                    patch.object(native, "OwnedProcess", side_effect=[bootstrap, server, benchmark]) as launch, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(native.main(), 1)
            result = json.loads((output / "summary.json").read_text())
            self.assertEqual(result["status"], "FAILED")
            self.assertFalse(result["acceptance_claim"])
            self.assertIn("TimeoutExpired", result["error"])
            self.assertEqual([call.args[0] for call in alarm.call_args_list], [3600, 0])
            for process in (bootstrap, server, benchmark):
                process.stop.assert_called()
            command = launch.call_args_list[2].args[0]
            self.assertEqual(command[command.index("--seed-documents") + 1], "3750")
            self.assertEqual(command[command.index("--max-seed-seconds") + 1], "3300")

    def test_capacity_success_serializes_exact_native_decimal_totals(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "new-capacity"
            environ = {"TCSI_ANNUAL_NATIVE_CI": "disposable-only", "PGHOST": "127.0.0.1", "PGUSER": "odoo",
                       "PGPASSWORD": "ci-only", "TCSI_ANNUAL_CAPACITY_CI": "engineering-only", "GITHUB_ACTIONS": "true",
                       "TCSI_ANNUAL_EVIDENCE": str(output)}
            processes = []
            def launch(command, _log):
                process = MagicMock()
                process.wait.return_value = 0
                process.process.poll.return_value = None
                processes.append(process)
                if "--output-directory" in command:
                    directory = Path(command[command.index("--output-directory") + 1])
                    directory.mkdir()
                    (directory / "results.json").write_text(json.dumps({"seeded": {}, "measured_cardinality": {}, "samples": []}))
                if "--monthly-child" in command:
                    directory = Path(command[-1])
                    directory.mkdir()
                    (directory / "results.json").write_text('{"status":"PASSED"}')
                return process
            totals = {"documents": 3750, "invoices": 1875, "bills": 1875, "document_amount": Decimal("375000.00"),
                      "payments": 1250, "inbound": 625, "outbound": 625, "payment_amount": Decimal("125000.00"),
                      "moves": 5000, "lines": 10000, "debit": Decimal("500000.00"), "credit": Decimal("500000.00"),
                      "months": 12, "scope_valid": True}
            with patch.dict("os.environ", environ, clear=True), patch.object(native.sys, "platform", "linux"), \
                    patch.object(native.signal, "signal"), patch.object(native.signal, "alarm", create=True), \
                    patch.object(native.socket, "socket"), patch.object(native, "clone_database", return_value=0), \
                    patch.object(native, "write_configuration"), patch.object(native, "ready"), \
                    patch.object(native, "OwnedProcess", side_effect=launch), patch.object(native, "verify_smoke"), \
                    patch.object(native, "verify_monthly_smoke"), patch.object(native, "listener_owned", return_value=True), \
                    patch.object(native, "capacity_ledger_totals", return_value=totals), contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(native.main(), 0)
            summary = json.loads((output / "summary.json").read_text())
            self.assertEqual(summary["status"], "PASSED")
            self.assertEqual(summary["native_ledger_totals"]["debit"], "500000.00")
            printed = json.loads(stdout.getvalue().removeprefix("ANNUAL_NATIVE "))
            self.assertEqual(printed, summary)
            self.assertEqual(len(processes), 4)
            for process in processes:
                process.stop.assert_called()

    def test_both_native_scenarios_require_exact_deltas_and_six_pdf_checksums(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            samples = []
            for kind in ("balance_sheet", "profit_loss", "cash_flow"):
                for repeat in (0, 1):
                    pdf = f"%PDF-1.4 {kind} {repeat}".encode()
                    (output / f"{kind}-{repeat}.pdf").write_bytes(pdf)
                    samples.append({"report": kind, "repeat": repeat, "pdf_bytes": len(pdf),
                                    "pdf_sha256": hashlib.sha256(pdf).hexdigest()})
            for documents, payments, moves, lines in ((24, 8, 32, 64), (3750, 1250, 5000, 10000)):
                result = {"status": "ENGINEERING_TARGET_OBSERVED", "exit_code": 0, "seed_committed": True,
                          "acceptance_claim": False, "approved_client_volume": False,
                          "seeded": {"documents": documents, "payments": payments, "posted_moves": moves,
                                     "posted_lines": lines, "months": 12}, "samples": samples,
                          "before": {"year_posted_documents": 13, "year_posted_lines": 26},
                          "measured_cardinality": {"year_posted_documents": 13 + moves, "year_posted_lines": 26 + lines}}
                native.verify_smoke(result, output, documents)
                for changed in ({"acceptance_claim": True}, {"exit_code": 2, "status": "ENGINEERING_TARGET_MISSED"},
                                {"measured_cardinality": {"year_posted_documents": 13 + moves, "year_posted_lines": 27 + lines}}):
                    with self.subTest(documents=documents, changed=changed), self.assertRaises(RuntimeError):
                        native.verify_smoke({**result, **changed}, output, documents)
            (output / "balance_sheet-0.pdf").write_bytes(b"wrong PDF")
            with self.assertRaisesRegex(RuntimeError, "PDF evidence"):
                native.verify_smoke(result, output, 3750)

    def test_scope_mismatch_fails_before_accessing_any_models(self):
        class Environment:
            cr = SimpleNamespace(dbname="tcsi_alignment_test")
            uid = 11
            su = False
            user = SimpleNamespace(company_ids=SimpleNamespace(ids=[14, 99]))
            company = SimpleNamespace(id=14)
            companies = SimpleNamespace(ids=[14, 99])
            def __getitem__(self, name):
                raise AssertionError("Scope guard must run before model access")
        with self.assertRaisesRegex(RuntimeError, "company scope"):
            annual.validate_environment(Environment(), arguments())

    def test_calculation_only_never_satisfies_full_statement_target(self):
        self.assertEqual(annual.report_status([{"pdf_seconds": None, "calculation_seconds": .01}], 30), ("CALCULATION_ONLY", 3))
        self.assertEqual(annual.report_status([], 30), ("CALCULATION_ONLY", 3))
        self.assertEqual(annual.report_status([{"pdf_seconds": 30}], 30), ("ENGINEERING_TARGET_MISSED", 2))
        self.assertEqual(annual.report_status([{"pdf_seconds": 29.9}], 30), ("ENGINEERING_TARGET_OBSERVED", 0))

    def test_first_sample_survives_later_report_failure(self):
        class Reports:
            count = 0
            def create(self, values):
                self.count += 1
                if self.count == 2:
                    raise RuntimeError("Second report access denied")
                return SimpleNamespace(get_report_data=lambda: {"balanced": True})
        reports = Reports()
        samples = []
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "access denied"):
                annual.measure_reports({"thirdcode.financial.report.wizard": reports}, arguments(), Path(folder), samples)
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0]["report"], "balance_sheet")
        self.assertEqual(samples[0]["cache"], "first report call in process")

    def test_config_mismatch_preserves_failure_without_loading_odoo(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "isolated.conf"
            config.write_text("[options]\ndb_name=tcsi_pilot\ndbfilter=^tcsi_pilot$\n")
            output = Path(folder) / "new-evidence"
            args = arguments()
            args.config, args.output_directory = str(config), str(output)
            with patch.object(annual, "parse_args", return_value=args), patch.dict("sys.modules", {"odoo": None}), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(annual.main([]), 1)
            result = json.loads((output / "results.json").read_text())
            self.assertIn("Config database/filter mismatch", result["error"])
            self.assertFalse(result["acceptance_claim"])
            self.assertIsNone(result["seeded"])
            with patch.object(annual, "parse_args", return_value=args), self.assertRaises(FileExistsError):
                annual.main([])

    def test_monthly_pdf_evidence_requires_real_bytes_and_native_readonly_scope(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            pdf = b"%PDF-1.4\nSynthetic verifier fixture"
            (output / "monthly-reconciliation.pdf").write_bytes(pdf)
            result = {"status": "PASSED", "acceptance_claim": False, "company_id": 1,
                      "render_role": "readonly", "render_actor_id": 20, "sudo": False,
                      "report": "thirdcode_accounting.action_report_monthly_bank_reconciliation",
                      "ledger_closing": 100, "statement_closing": 100, "difference": 0,
                      "unmatched_count": 1, "render_preserved_accounting": True,
                      "pdf_bytes": len(pdf), "pdf_sha256": hashlib.sha256(pdf).hexdigest()}
            native.verify_monthly_smoke(result, output)
            for changed in ({"sudo": True}, {"company_id": 2}, {"acceptance_claim": True},
                            {"render_preserved_accounting": False}, {"difference": 1}):
                with self.subTest(changed=changed), self.assertRaises(RuntimeError):
                    native.verify_monthly_smoke({**result, **changed}, output)
            (output / "monthly-reconciliation.pdf").write_bytes(b"corrupt")
            with self.assertRaisesRegex(RuntimeError, "PDF evidence"):
                native.verify_monthly_smoke(result, output)

    def test_monthly_child_cannot_start_without_disposable_ci_guard(self):
        with patch.dict("os.environ", {}, clear=True), tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "new-monthly"
            with self.assertRaisesRegex(RuntimeError, "disposable CI marker"):
                native.monthly_child("/irrelevant.conf", "tcsi_alignment_annual_ci_test", str(output))
            self.assertFalse(output.exists())

    def test_monthly_child_rejects_config_that_overrides_guarded_loopback_connection(self):
        environ = {"TCSI_ANNUAL_NATIVE_CI": "disposable-only", "PGHOST": "127.0.0.1", "PGUSER": "odoo", "PGPASSWORD": "ci-only"}
        with patch.dict("os.environ", environ, clear=True), tempfile.TemporaryDirectory() as folder:
            database = "tcsi_alignment_annual_ci_test"
            config = Path(folder) / "isolated.conf"
            output = Path(folder) / "new-monthly"
            config.write_text(f"[options]\ndb_name={database}\ndbfilter=^{database}$\ndb_host=remote.example\ndb_user=odoo\ndb_port=5432\ndb_password=ci-only\n")
            with self.assertRaisesRegex(RuntimeError, "guarded disposable connection"):
                native.monthly_child(str(config), database, str(output))
            self.assertFalse(output.exists())

    def test_successful_samples_cannot_mask_transaction_cleanup_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "isolated.conf"
            config.write_text("[options]\ndb_name=tcsi_alignment_test\ndbfilter=^tcsi_alignment_test$\n")
            args = arguments()
            args.config, args.output_directory = str(config), str(Path(folder) / "cleanup-failed")
            cursor = MagicMock()
            cursor.__enter__.return_value = cursor
            cursor.rollback.side_effect = RuntimeError("transaction cleanup failed")
            env = MagicMock()
            env.company.currency_id.name = "USD"
            env.__getitem__.return_value.search.return_value.latest_version = "18.0.test"
            odoo = SimpleNamespace(
                tools=SimpleNamespace(config=SimpleNamespace(parse_config=lambda *a: None)),
                registry=lambda *a: SimpleNamespace(cursor=lambda: cursor),
                api=SimpleNamespace(Environment=lambda *a: env),
            )
            def samples(_env, _args, _output, evidence, checkpoint):
                evidence.append({"report": "balance_sheet", "pdf_seconds": .01})
                checkpoint()
            with patch.object(annual, "parse_args", return_value=args), patch.dict("sys.modules", {"odoo": odoo}), \
                    patch.object(annual, "validate_environment"), patch.object(annual, "cardinality", return_value={}), \
                    patch.object(annual, "measure_reports", side_effect=samples), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(annual.main([]), 1)
            result = json.loads((Path(args.output_directory) / "results.json").read_text())
            self.assertEqual(result["status"], "FAILED")
            self.assertEqual(result["exit_code"], 1)
            self.assertIn("transaction cleanup failed", result["error"])
            self.assertEqual(len(result["samples"]), 1, "Completed measurements must survive cleanup failure")


if __name__ == "__main__":
    unittest.main()
