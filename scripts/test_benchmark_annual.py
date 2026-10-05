"""Scope, workload and evidence regressions; native smoke remains a separate gate."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import benchmark_annual as annual


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
        self.assertEqual(arguments().seed_documents, 0)

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


if __name__ == "__main__":
    unittest.main()
