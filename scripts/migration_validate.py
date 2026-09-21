"""Validate a repeatable, MYOB-shaped CSV migration package.

The validator is deliberately independent of Odoo.  It checks structure,
cross-file references, dates, amounts, duplicate source identifiers, and
balance invariants before any ORM load is attempted.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


EXPECTED_FILES = {
    "accounts.csv": {
        "source_id",
        "code",
        "name",
        "account_type",
    },
    "partners.csv": {
        "source_id",
        "name",
        "vat",
        "customer",
        "supplier",
    },
    "taxes.csv": {
        "source_id",
        "name",
        "amount",
        "amount_type",
        "type_tax_use",
    },
    "open_items.csv": {
        "source_id",
        "partner_source_id",
        "account_source_id",
        "counterpart_account_source_id",
        "move_type",
        "invoice_date",
        "date_maturity",
        "amount",
        "reference",
    },
    "transactions.csv": {
        "entry_id",
        "line_id",
        "date",
        "reference",
        "account_source_id",
        "partner_source_id",
        "debit",
        "credit",
    },
    "opening_tb.csv": {
        "account_source_id",
        "debit",
        "credit",
    },
}

DATE_FIELDS = {
    ("open_items.csv", "invoice_date"),
    ("open_items.csv", "date_maturity"),
    ("transactions.csv", "date"),
}


def parse_decimal(value: str, field: str, errors: list[str], location: str) -> Decimal | None:
    if not value.strip():
        errors.append(f"{location}: {field} is required")
        return None
    try:
        amount = Decimal(value.strip())
    except InvalidOperation:
        errors.append(f"{location}: {field} is not a decimal: {value!r}")
        return None
    if not amount.is_finite():
        errors.append(f"{location}: {field} must be finite")
        return None
    if amount < 0:
        errors.append(f"{location}: {field} cannot be negative")
        return None
    return amount


def load_csv(root: Path, filename: str, errors: list[str]) -> list[dict[str, str]]:
    path = root / filename
    if not path.is_file():
        errors.append(f"missing required file: {filename}")
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            missing = EXPECTED_FILES[filename] - headers
            if missing:
                errors.append(f"{filename}: missing columns: {sorted(missing)}")
            rows = [
                {key: (value or "").strip() for key, value in row.items()}
                for row in reader
            ]
    except (OSError, csv.Error) as exc:
        errors.append(f"{filename}: cannot read CSV: {exc}")
        return []

    seen: set[str] = set()
    id_field = "source_id" if filename not in {"transactions.csv", "opening_tb.csv"} else None
    for line_number, row in enumerate(rows, start=2):
        location = f"{filename}:{line_number}"
        if id_field:
            source_id = row.get(id_field, "")
            if not source_id:
                errors.append(f"{location}: {id_field} is required")
            elif source_id in seen:
                errors.append(f"{location}: duplicate {id_field} {source_id!r}")
            else:
                seen.add(source_id)
        for field in EXPECTED_FILES[filename]:
            if field in {"vat", "customer", "supplier", "reference", "date_maturity", "partner_source_id", "tax_source_id"}:
                continue
            if not row.get(field, ""):
                errors.append(f"{location}: {field} is required")
        for field in EXPECTED_FILES[filename]:
            if (filename, field) in DATE_FIELDS and row.get(field):
                try:
                    date.fromisoformat(row[field])
                except ValueError:
                    errors.append(f"{location}: {field} must use ISO YYYY-MM-DD")
    return rows


def validate_package(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    rows = {
        filename: load_csv(root, filename, errors)
        for filename in EXPECTED_FILES
    }
    accounts = {row.get("source_id", "") for row in rows["accounts.csv"]}
    partners = {row.get("source_id", "") for row in rows["partners.csv"]}
    taxes = {row.get("source_id", "") for row in rows["taxes.csv"]}

    for filename, row_list in rows.items():
        for line_number, row in enumerate(row_list, start=2):
            location = f"{filename}:{line_number}"
            if filename == "accounts.csv":
                if not row.get("code", "").strip():
                    errors.append(f"{location}: account code must be nonblank")
            elif filename == "partners.csv":
                for field in ("customer", "supplier"):
                    if row.get(field) not in {"0", "1", "true", "false", "True", "False", ""}:
                        errors.append(f"{location}: {field} must be a boolean flag")
            elif filename == "taxes.csv":
                amount = parse_decimal(row.get("amount", ""), "amount", errors, location)
                if amount is not None and amount > Decimal("1000000"):
                    warnings.append(f"{location}: unusually large tax amount {amount}")
                if row.get("amount_type") not in {"percent", "fixed", "division", "group"}:
                    errors.append(f"{location}: amount_type must be percent, fixed, division, or group")
                if row.get("type_tax_use") not in {"sale", "purchase", "none"}:
                    errors.append(f"{location}: type_tax_use must be sale, purchase, or none")
            elif filename == "open_items.csv":
                if row.get("partner_source_id") not in partners:
                    errors.append(f"{location}: unknown partner_source_id {row.get('partner_source_id')!r}")
                for field in ("account_source_id", "counterpart_account_source_id"):
                    if row.get(field) not in accounts:
                        errors.append(f"{location}: unknown {field} {row.get(field)!r}")
                if row.get("move_type") not in {"out_invoice", "in_invoice"}:
                    errors.append(f"{location}: move_type must be out_invoice or in_invoice")
                parse_decimal(row.get("amount", ""), "amount", errors, location)
            elif filename == "transactions.csv":
                if row.get("account_source_id") not in accounts:
                    errors.append(f"{location}: unknown account_source_id {row.get('account_source_id')!r}")
                if row.get("partner_source_id") and row.get("partner_source_id") not in partners:
                    errors.append(f"{location}: unknown partner_source_id {row.get('partner_source_id')!r}")
                debit = parse_decimal(row.get("debit", ""), "debit", errors, location)
                credit = parse_decimal(row.get("credit", ""), "credit", errors, location)
                if debit is not None and credit is not None:
                    if debit and credit:
                        errors.append(f"{location}: a line cannot contain both debit and credit")
                    if not debit and not credit:
                        errors.append(f"{location}: a line must contain a debit or credit")
                if row.get("tax_source_id") and row.get("tax_source_id") not in taxes:
                    errors.append(f"{location}: unknown tax_source_id {row.get('tax_source_id')!r}")
            elif filename == "opening_tb.csv":
                if row.get("account_source_id") not in accounts:
                    errors.append(f"{location}: unknown account_source_id {row.get('account_source_id')!r}")
                parse_decimal(row.get("debit", ""), "debit", errors, location)
                parse_decimal(row.get("credit", ""), "credit", errors, location)

    transaction_totals: dict[str, list[Decimal]] = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    for row in rows["transactions.csv"]:
        debit = parse_decimal(row.get("debit", ""), "debit", [], "transaction") or Decimal("0")
        credit = parse_decimal(row.get("credit", ""), "credit", [], "transaction") or Decimal("0")
        transaction_totals[row.get("entry_id", "")][0] += debit
        transaction_totals[row.get("entry_id", "")][1] += credit
    for entry_id, (debit, credit) in transaction_totals.items():
        if debit != credit:
            errors.append(f"transactions.csv: entry {entry_id!r} is unbalanced: debit={debit} credit={credit}")

    opening_debit = Decimal("0")
    opening_credit = Decimal("0")
    for row in rows["opening_tb.csv"]:
        opening_debit += parse_decimal(row.get("debit", ""), "debit", [], "opening_tb") or Decimal("0")
        opening_credit += parse_decimal(row.get("credit", ""), "credit", [], "opening_tb") or Decimal("0")
    if opening_debit != opening_credit:
        errors.append(f"opening_tb.csv: unbalanced totals: debit={opening_debit} credit={opening_credit}")

    all_source_ids: dict[str, str] = {}
    for filename in ("accounts.csv", "partners.csv", "taxes.csv", "open_items.csv"):
        for row in rows[filename]:
            source_id = row.get("source_id", "")
            if not source_id:
                continue
            previous = all_source_ids.get(source_id)
            if previous and previous != filename:
                errors.append(f"source identifier {source_id!r} is reused by {previous} and {filename}")
            all_source_ids[source_id] = filename

    source_hash = hashlib.sha256()
    file_hashes: dict[str, str] = {}
    for filename in sorted(EXPECTED_FILES):
        path = root / filename
        if not path.exists():
            continue
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        file_hashes[filename] = digest
        source_hash.update(filename.encode("utf-8"))
        source_hash.update(b"\0")
        source_hash.update(content)

    counts = {filename: len(row_list) for filename, row_list in rows.items()}
    return {
        "status": "VALID" if not errors else "INVALID",
        "source_directory": str(root.resolve()),
        "source_hash": source_hash.hexdigest(),
        "file_hashes": file_hashes,
        "counts": counts,
        "transaction_totals": {
            entry_id: {"debit": str(debit), "credit": str(credit)}
            for entry_id, (debit, credit) in sorted(transaction_totals.items())
        },
        "opening_totals": {"debit": str(opening_debit), "credit": str(opening_credit)},
        "warnings": warnings,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Directory containing the six CSV files")
    parser.add_argument("--report", type=Path, help="Optional JSON report path")
    args = parser.parse_args()
    result = validate_package(args.input)
    serialized = json.dumps(result, indent=2, sort_keys=True)
    print(serialized)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(serialized + "\n", encoding="utf-8")
    return 0 if result["status"] == "VALID" else 1


if __name__ == "__main__":
    raise SystemExit(main())
