"""Dry-run or explicitly apply a validated migration package through Odoo ORM."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import xmlrpc.client
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from migration_validate import validate_package


class Odoo:
    def __init__(self, url: str, database: str, login: str, password: str) -> None:
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        self.uid = common.authenticate(database, login, password, {})
        if not self.uid:
            raise RuntimeError("Odoo authentication failed")
        self.database = database
        self.password = password
        self.models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    def call(self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        return self.models.execute_kw(self.database, self.uid, self.password, model, method, args, kwargs or {})

    def search_read(self, model: str, domain: list[Any], fields: list[str], limit: int = 0) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {"fields": fields}
        if limit:
            kwargs["limit"] = limit
        return self.call(model, "search_read", [domain], kwargs)


def rows(root: Path, filename: str) -> list[dict[str, str]]:
    with (root / filename).open("r", encoding="utf-8-sig", newline="") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def bool_value(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "y"}


def existing_one(odoo: Odoo, model: str, domain: list[Any], fields: list[str]) -> dict[str, Any] | None:
    found = odoo.search_read(model, domain, fields, limit=2)
    if len(found) > 1:
        raise RuntimeError(f"Ambiguous existing {model} match for {domain!r}")
    return found[0] if found else None


def existing_source_record(
    odoo: Odoo,
    model: str,
    source_identifier: str,
    extra_domain: list[Any],
    fields: list[str],
) -> dict[str, Any] | None:
    """Find a master record by its persisted source-system identifier first."""
    if not source_identifier:
        return None
    return existing_one(
        odoo,
        model,
        [("thirdcode_source_identifier", "=", source_identifier), *extra_domain],
        fields,
    )


def persist_source_identifier(
    odoo: Odoo, model: str, record: dict[str, Any], source_identifier: str
) -> None:
    if source_identifier and not record.get("thirdcode_source_identifier"):
        odoo.call(
            model,
            "write",
            [[int(record["id"])], {"thirdcode_source_identifier": source_identifier}],
        )


def load(args: argparse.Namespace, validation: dict[str, Any]) -> dict[str, Any]:
    root: Path = args.input
    odoo = Odoo(args.url, args.database, args.login, args.password)
    if not args.company_id or not args.journal_id or not args.cutover_date:
        raise RuntimeError("--company-id, --journal-id, and --cutover-date are required with --apply")
    date.fromisoformat(args.cutover_date)
    company_id = int(args.company_id)
    journal_id = int(args.journal_id)
    opening_journal_id = int(args.opening_journal_id or journal_id)
    sales_journal_id = int(args.sales_journal_id or journal_id)
    purchase_journal_id = int(args.purchase_journal_id or journal_id)
    if rows(root, "open_items.csv") and not (args.sales_journal_id and args.purchase_journal_id):
        raise RuntimeError("Open-item loads require --sales-journal-id and --purchase-journal-id so invoice journals are explicit")
    account_map: dict[str, int] = {}
    partner_map: dict[str, int] = {}
    tax_map: dict[str, int] = {}
    created = {"accounts": 0, "partners": 0, "taxes": 0, "moves": 0}
    existing = {"accounts": 0, "partners": 0, "taxes": 0, "moves": 0}

    for row in rows(root, "accounts.csv"):
        account_fields = ["id", "name", "code", "thirdcode_source_identifier"]
        match = existing_source_record(
            odoo,
            "account.account",
            row["source_id"],
            [("company_ids", "in", [company_id])],
            account_fields,
        ) or existing_one(
            odoo,
            "account.account",
            [("company_ids", "in", [company_id]), ("code", "=", row["code"])],
            account_fields,
        )
        if match:
            persist_source_identifier(odoo, "account.account", match, row["source_id"])
            account_map[row["source_id"]] = int(match["id"])
            existing["accounts"] += 1
        else:
            account_id = int(odoo.call("account.account", "create", [{
                "company_ids": [(6, 0, [company_id])],
                "code": row["code"],
                "name": row["name"],
                "account_type": row["account_type"],
                "thirdcode_source_identifier": row["source_id"],
            }]))
            account_map[row["source_id"]] = account_id
            created["accounts"] += 1

    for row in rows(root, "partners.csv"):
        partner_fields = ["id", "name", "vat", "thirdcode_source_identifier"]
        domain = [("vat", "=", row["vat"])] if row.get("vat") else [("name", "=", row["name"])]
        match = existing_source_record(
            odoo, "res.partner", row["source_id"], [], partner_fields
        ) or existing_one(odoo, "res.partner", domain, partner_fields)
        if match:
            persist_source_identifier(odoo, "res.partner", match, row["source_id"])
            partner_map[row["source_id"]] = int(match["id"])
            existing["partners"] += 1
        else:
            partner_id = int(odoo.call("res.partner", "create", [{
                "name": row["name"],
                "vat": row.get("vat") or False,
                "customer_rank": 1 if bool_value(row.get("customer", "")) else 0,
                "supplier_rank": 1 if bool_value(row.get("supplier", "")) else 0,
                "street": row.get("street") or False,
                "city": row.get("city") or False,
                "zip": row.get("zip") or False,
                "thirdcode_source_identifier": row["source_id"],
            }]))
            partner_map[row["source_id"]] = partner_id
            created["partners"] += 1

    for row in rows(root, "taxes.csv"):
        tax_fields = ["id", "name", "thirdcode_source_identifier"]
        match = existing_one(
            odoo,
            "account.tax",
            [("company_id", "=", company_id), ("name", "=", row["name"])],
            tax_fields,
        )
        match = existing_source_record(
            odoo,
            "account.tax",
            row["source_id"],
            [("company_id", "=", company_id)],
            tax_fields,
        ) or match
        if match:
            persist_source_identifier(odoo, "account.tax", match, row["source_id"])
            tax_map[row["source_id"]] = int(match["id"])
            existing["taxes"] += 1
        else:
            tax_id = int(odoo.call("account.tax", "create", [{
                "company_id": company_id,
                "name": row["name"],
                "amount": float(Decimal(row["amount"])),
                "amount_type": row["amount_type"],
                "type_tax_use": row["type_tax_use"],
                "thirdcode_source_identifier": row["source_id"],
            }]))
            tax_map[row["source_id"]] = tax_id
            created["taxes"] += 1

    def create_move(source_identifier: str, values: dict[str, Any]) -> bool:
        found = existing_one(
            odoo,
            "account.move",
            [("company_id", "=", company_id), ("thirdcode_source_identifier", "=", source_identifier)],
            ["id", "state"],
        )
        if found:
            existing["moves"] += 1
            return False
        move_id = int(odoo.call("account.move", "create", [values]))
        odoo.call("account.move", "action_post", [[move_id]])
        created["moves"] += 1
        return True

    opening_lines = []
    for row in rows(root, "opening_tb.csv"):
        opening_lines.append([0, 0, {
            "name": f"MYOB opening balance {args.cutover_date}",
            "account_id": account_map[row["account_source_id"]],
            "debit": float(Decimal(row["debit"])),
            "credit": float(Decimal(row["credit"])),
        }])
    if opening_lines:
        create_move(
            f"OPENING/{args.cutover_date}",
            {
                "company_id": company_id,
                "journal_id": opening_journal_id,
                "date": args.cutover_date,
                "move_type": "entry",
                "ref": f"MYOB opening balance {args.cutover_date}",
                "thirdcode_source_identifier": f"OPENING/{args.cutover_date}",
                "thirdcode_is_opening_balance": True,
                "line_ids": opening_lines,
            },
        )

    transaction_rows = rows(root, "transactions.csv")
    by_entry: dict[str, list[dict[str, str]]] = {}
    for row in transaction_rows:
        by_entry.setdefault(row["entry_id"], []).append(row)
    for entry_id, entry_rows in by_entry.items():
        line_values = []
        for row in entry_rows:
            line = {
                "name": row["reference"] or entry_id,
                "account_id": account_map[row["account_source_id"]],
                "partner_id": partner_map.get(row.get("partner_source_id", ""), False),
                "debit": float(Decimal(row["debit"])),
                "credit": float(Decimal(row["credit"])),
            }
            if row.get("tax_source_id"):
                line["tax_ids"] = [(6, 0, [tax_map[row["tax_source_id"]]])]
            line_values.append([0, 0, line])
        create_move(
            f"TRANSACTION/{entry_id}",
            {
                "company_id": company_id,
                "journal_id": journal_id,
                "date": entry_rows[0]["date"],
                "move_type": "entry",
                "ref": entry_rows[0]["reference"] or entry_id,
                "thirdcode_source_identifier": f"TRANSACTION/{entry_id}",
                "line_ids": line_values,
            },
        )

    for row in rows(root, "open_items.csv"):
        amount = float(Decimal(row["amount"]))
        line_values = [[0, 0, {
            "name": row["reference"] or row["source_id"],
            "account_id": account_map[row["counterpart_account_source_id"]],
            "quantity": 1,
            "price_unit": amount,
            "partner_id": partner_map[row["partner_source_id"]],
            "tax_ids": [(6, 0, [])],
        }]]
        create_move(
            row["source_id"],
            {
                "company_id": company_id,
                "journal_id": sales_journal_id if row["move_type"] == "out_invoice" else purchase_journal_id,
                "move_type": row["move_type"],
                "partner_id": partner_map[row["partner_source_id"]],
                "invoice_date": row["invoice_date"],
                "invoice_date_due": row["date_maturity"] or False,
                "ref": row["reference"],
                "thirdcode_source_identifier": row["source_id"],
                "invoice_line_ids": line_values,
            },
        )

    return {
        "status": "APPLIED",
        "source_hash": validation["source_hash"],
        "created": created,
        "existing_skipped": existing,
        "duplicate_safe": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--apply", action="store_true", help="Actually create/post through Odoo ORM")
    parser.add_argument("--url", default="http://localhost:8069")
    parser.add_argument("--database", default="thirdcode_accounting")
    parser.add_argument("--login", default="admin")
    parser.add_argument("--password", default="admin")
    parser.add_argument("--company-id", type=int)
    parser.add_argument("--journal-id", type=int)
    parser.add_argument("--opening-journal-id", type=int)
    parser.add_argument("--sales-journal-id", type=int)
    parser.add_argument("--purchase-journal-id", type=int)
    parser.add_argument("--cutover-date")
    args = parser.parse_args()
    validation = validate_package(args.input)
    if validation["status"] != "VALID":
        result = {"status": "NOT APPLIED", "validation": validation}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1
    if not args.apply:
        result = {
            "status": "DRY RUN",
            "source_hash": validation["source_hash"],
            "counts": validation["counts"],
            "message": "No Odoo records were created. Use --apply with explicit company, journal, and cutover values.",
        }
    else:
        result = load(args, validation)
    serialized = json.dumps(result, indent=2, sort_keys=True)
    print(serialized)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(serialized + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, xmlrpc.client.Fault) as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(1)
