"""Run with python3 -m unittest discover -s scripts -p test_migration_policy.py."""
import csv
import tempfile
import unittest
from pathlib import Path
from migration_validate import EXPECTED_FILES, validate_package


class MigrationPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in EXPECTED_FILES:
            self.write(name, [])
        self.write("accounts.csv", [
            dict(source_id="cash", code="1000", name="Cash", account_type="asset_cash"),
            dict(source_id="equity", code="3000", name="Equity", account_type="equity"),
        ])

    def write(self, name, rows):
        with (self.root / name).open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=sorted(EXPECTED_FILES[name]))
            writer.writeheader()
            writer.writerows(rows)

    def opening(self):
        self.write("opening_tb.csv", [
            dict(account_source_id="cash", debit="100", credit="0"),
            dict(account_source_id="equity", debit="0", credit="100"),
        ])

    def history(self):
        self.write("transactions.csv", [
            dict(entry_id="historical", line_id="1", date="2026-01-01", reference="Capital", account_source_id="cash", partner_source_id="", debit="100", credit="0"),
            dict(entry_id="historical", line_id="2", date="2026-01-01", reference="Capital", account_source_id="equity", partner_source_id="", debit="0", credit="100"),
        ])

    def test_balanced_history_plus_balanced_opening_rejected(self):
        self.opening()
        self.history()
        result = validate_package(self.root)
        self.assertEqual(result["status"], "INVALID")
        self.assertTrue(any("Overlapping accounting bases" in error for error in result["errors"]))

    def test_single_basis_is_deterministic_and_changes_are_detected(self):
        self.opening()
        first = validate_package(self.root)
        self.assertEqual(first["status"], "VALID")
        self.assertEqual(first["source_hash"], validate_package(self.root)["source_hash"])
        with (self.root / "opening_tb.csv").open("a") as handle:
            handle.write("cash,0,0\n")
        second = validate_package(self.root)
        self.assertNotEqual(first["source_hash"], second["source_hash"])
        self.assertEqual(second["status"], "INVALID")

    def test_undeposited_receipts_are_not_silently_ignored(self):
        self.opening()
        (self.root / "undeposited_receipts.csv").write_text("source_id,amount\nreceipt1,100\n")
        self.assertEqual(validate_package(self.root)["status"], "INVALID")

    def test_malformed_opening_number_reports_error(self):
        self.write("opening_tb.csv", [dict(account_source_id="cash", debit="invalid", credit="0")])
        self.assertEqual(validate_package(self.root)["status"], "INVALID")

    def test_duplicate_history_lines_and_mixed_dates_rejected(self):
        self.history()
        with (self.root / "transactions.csv").open() as handle:
            records = list(csv.DictReader(handle))
        records[1]["line_id"] = "1"
        records[1]["date"] = "2026-01-02"
        self.write("transactions.csv", records)
        errors = validate_package(self.root)["errors"]
        self.assertTrue(any("duplicate entry/line" in error for error in errors))
        self.assertTrue(any("inconsistent dates" in error for error in errors))
