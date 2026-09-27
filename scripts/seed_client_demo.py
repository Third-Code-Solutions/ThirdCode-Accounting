#!/usr/bin/env python3
"""Seed five fictional companies in an isolated, loopback Odoo demo database.

This is presentation data, never an accounting migration or client approval.
The URL and database guards deliberately reject the hosted pilot.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import sys
import xmlrpc.client
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse
from typing import Any


COMPANIES = (
    "DEMO | Meridian Design Studio",
    "DEMO | Harbor Trading",
    "DEMO | Cedar Services",
    "DEMO | Atlas Retail",
    "DEMO | Summit Logistics",
)
ACCOUNT_SPECS = (
    ("bank", 101000, "Demo operating bank", "asset_cash"),
    ("receivable", 121000, "Demo trade receivables", "asset_receivable"),
    ("payable", 211000, "Demo trade payables", "liability_payable"),
    ("equity", 301000, "Demo retained earnings", "equity"),
    ("income", 401000, "Demo service revenue", "income"),
    ("expense", 601000, "Demo operating expense", "expense"),
)
JOURNAL_SPECS = (
    ("sale", "Sales", "sale"),
    ("purchase", "Purchases", "purchase"),
    ("general", "General", "general"),
    ("bank", "Bank", "bank"),
)


class Odoo:
    def __init__(self, url: str, database: str, login: str, password: str):
        self.database = database
        self.password = password
        self.common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
        self.models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
        self.uid = self.common.authenticate(database, login, password, {})
        if not self.uid:
            raise RuntimeError("Demo administrator authentication failed")

    def call(self, model: str, method: str, args: list[Any], company_id: int | None = None,
             fields: list[str] | None = None) -> Any:
        options: dict[str, Any] = {}
        if company_id is not None:
            options["context"] = {"allowed_company_ids": [company_id]}
        if fields is not None:
            options["fields"] = fields
        return self.models.execute_kw(self.database, self.uid, self.password, model, method, args, options)

    def first(self, model: str, domain: list[Any], fields: list[str],
              company_id: int | None = None, include_inactive: bool = False) -> dict[str, Any] | None:
        context: dict[str, Any] = {}
        if company_id is not None:
            context["allowed_company_ids"] = [company_id]
        if include_inactive:
            context["active_test"] = False
        rows = self.models.execute_kw(
            self.database, self.uid, self.password, model, "search_read", [domain],
            {"fields": fields, "limit": 1, **({"context": context} if context else {})},
        )
        return rows[0] if rows else None


def required(row: dict[str, Any] | None, label: str) -> dict[str, Any]:
    if row is None:
        raise RuntimeError(f"Missing demo prerequisite: {label}")
    return row


def ensure_account(odoo: Odoo, company_id: int, index: int, key: str,
                   number: int, name: str, kind: str) -> int:
    code = f"{number + index:06d}"
    row = odoo.first("account.account", [("code", "=", code), ("company_ids", "in", [company_id])],
                     ["id", "account_type"], company_id)
    if row:
        if row["account_type"] != kind:
            raise RuntimeError(f"Demo account {code} has an unexpected type")
        return int(row["id"])
    return int(odoo.call("account.account", "create", [{
        "code": code, "name": name, "account_type": kind,
        "company_ids": [[6, 0, [company_id]]],
        "reconcile": kind in {"asset_receivable", "liability_payable"},
    }], company_id))


def ensure_journal(odoo: Odoo, company_id: int, index: int, key: str,
                   name: str, kind: str, accounts: dict[str, int]) -> int:
    code = f"{key[0].upper()}{index:02d}"
    row = odoo.first("account.journal", [("company_id", "=", company_id), ("code", "=", code)],
                     ["id", "type"], company_id)
    if row:
        if row["type"] != kind:
            raise RuntimeError(f"Demo journal {code} has an unexpected type")
        return int(row["id"])
    values: dict[str, Any] = {"name": f"Demo {name}", "code": code,
                              "type": kind, "company_id": company_id}
    if key == "bank":
        values["default_account_id"] = accounts["bank"]
    return int(odoo.call("account.journal", "create", [values], company_id))


def ensure_partner(odoo: Odoo, company_id: int, index: int, kind: str,
                   accounts: dict[str, int]) -> int:
    reference = f"DEMO-{index:02d}-{kind.upper()}"
    row = odoo.first("res.partner", [("ref", "=", reference), ("company_id", "=", company_id)],
                     ["id"], company_id)
    if row:
        return int(row["id"])
    values = {
        "name": f"DEMO | {kind.title()} {index}", "ref": reference,
        "company_id": company_id, "company_type": "company",
        "email": f"{kind}{index}@example.invalid",
        "customer_rank": 1 if kind == "customer" else 0,
        "supplier_rank": 1 if kind == "supplier" else 0,
        "property_account_receivable_id": accounts["receivable"],
        "property_account_payable_id": accounts["payable"],
    }
    return int(odoo.call("res.partner", "create", [values], company_id))


def ensure_document(odoo: Odoo, company_id: int, index: int, kind: str,
                    partner_id: int, journal_id: int, account_id: int, amount: float,
                    today: date) -> dict[str, Any]:
    reference = f"DEMO-{index:02d}-{kind.upper()}-001"
    move_type = "out_invoice" if kind == "invoice" else "in_invoice"
    row = odoo.first("account.move", [("company_id", "=", company_id),
                                     ("move_type", "=", move_type), ("ref", "=", reference)],
                     ["id", "state", "amount_total", "amount_residual"], company_id)
    if not row:
        move_id = odoo.call("account.move", "create", [{
            "company_id": company_id,
            "journal_id": journal_id,
            "move_type": move_type,
            "partner_id": partner_id,
            "invoice_date": today.isoformat(),
            "invoice_date_due": (today + timedelta(days=30)).isoformat(),
            "ref": reference,
            "invoice_line_ids": [[0, 0, {"name": "Fictional demonstration service",
                                         "quantity": 1, "price_unit": amount,
                                         "account_id": account_id}]],
        }], company_id)
        row = required(odoo.first("account.move", [("id", "=", move_id)],
                                  ["id", "state", "amount_total", "amount_residual"], company_id),
                       reference)
    if row["state"] == "draft":
        odoo.call("account.move", "action_post", [[row["id"]]], company_id)
        row = required(odoo.first("account.move", [("id", "=", row["id"])],
                                  ["id", "state", "amount_total", "amount_residual"], company_id),
                       reference)
    if row["state"] != "posted" or abs(row["amount_total"] - amount) > 0.01:
        raise RuntimeError(f"Demo {reference} was not posted with the expected total")
    return row


def ensure_period(odoo: Odoo, company_id: int, today: date) -> int:
    name = f"DEMO {today.year} open period"
    row = odoo.first("thirdcode.accounting.period", [("company_id", "=", company_id),
                                                       ("name", "=", name)], ["id", "state"], company_id)
    if row:
        if row["state"] != "open":
            raise RuntimeError(f"Demo period {name} is closed")
        return int(row["id"])
    return int(odoo.call("thirdcode.accounting.period", "create", [{
        "name": name, "company_id": company_id,
        "date_start": date(today.year, 1, 1).isoformat(),
        "date_end": date(today.year, 12, 31).isoformat(),
    }], company_id))


def ensure_tax_demo(odoo: Odoo, company_id: int, today: date) -> None:
    name = "DEMO ONLY | No statutory tax determination"
    row = odoo.first("thirdcode.tax.profile", [("company_id", "=", company_id),
                                                ("name", "=", name)], ["id", "status"], company_id)
    if row:
        if row["status"] != "configured":
            odoo.call("thirdcode.tax.profile", "action_configure", [[row["id"]]], company_id)
        return
    profile_id = odoo.call("thirdcode.tax.profile", "create", [{
        "name": name, "company_id": company_id, "effective_date": today.isoformat(),
        "accountant_owner": "Fictional demo operator", "vat_registered": False,
        "notes": "Synthetic presentation data only. This is not a legal tax assessment or a rate recommendation.",
    }], company_id)
    odoo.call("thirdcode.tax.profile", "action_configure", [[profile_id]], company_id)


def ensure_demo_payment(odoo: Odoo, company_id: int, journal_id: int,
                        invoice_id: int, partner_id: int, amount: float,
                        today: date, name: str, payment_type: str,
                        partner_type: str, instrument_reference: str) -> int:
    row = odoo.first("thirdcode.payment.batch", [("company_id", "=", company_id),
                                                    ("name", "=", name)],
                     ["id", "state"], company_id)
    if row is None:
        batch_id = int(odoo.call("thirdcode.payment.batch", "create", [{
            "name": name, "company_id": company_id, "journal_id": journal_id,
            "date": today.isoformat(), "payment_type": payment_type,
            "partner_type": partner_type, "payment_instrument": "bank_transfer",
            "instrument_reference": instrument_reference,
            "line_ids": [[0, 0, {"move_id": invoice_id, "partner_id": partner_id,
                                 "amount": amount, "communication": "DEMO partial settlement"}]],
        }], company_id))
        row = required(odoo.first("thirdcode.payment.batch", [("id", "=", batch_id)],
                                  ["id", "state"], company_id), name)
    if row["state"] == "draft":
        odoo.call("thirdcode.payment.batch", "action_submit", [[row["id"]]], company_id)
        row = required(odoo.first("thirdcode.payment.batch", [("id", "=", row["id"])],
                                  ["id", "state"], company_id), name)
    if row["state"] == "pending_approval":
        odoo.call("thirdcode.payment.batch", "action_approve", [[row["id"]]], company_id)
        row = required(odoo.first("thirdcode.payment.batch", [("id", "=", row["id"])],
                                  ["id", "state"], company_id), name)
    if row["state"] == "approved":
        odoo.call("thirdcode.payment.batch", "action_post", [[row["id"]]], company_id)
        row = required(odoo.first("thirdcode.payment.batch", [("id", "=", row["id"])],
                                  ["id", "state"], company_id), name)
    if row["state"] != "posted":
        raise RuntimeError("Demo payment batch is not posted")
    return int(row["id"])


def ensure_recurring_invoice(odoo: Odoo, company_id: int, journal_id: int,
                             partner_id: int, income_id: int, today: date) -> None:
    reference = "DEMO-01-MONTHLY-SERVICE"
    row = odoo.first("thirdcode.recurring.invoice", [
        ("company_id", "=", company_id), ("reference", "=", reference)],
        ["id", "last_run"], company_id)
    if row is None:
        recurring_id = odoo.call("thirdcode.recurring.invoice", "create", [{
            "name": "DEMO | Monthly service agreement", "company_id": company_id,
            "move_type": "out_invoice", "partner_id": partner_id,
            "journal_id": journal_id, "reference": reference,
            "date_start": today.isoformat(), "next_run": today.isoformat(),
            "interval_number": 1, "interval_type": "months",
            "line_ids": [[0, 0, {"name": "Fictional monthly design support",
                                 "account_id": income_id, "quantity": 1,
                                 "price_unit": 300.0}]],
        }], company_id)
        row = {"id": recurring_id, "last_run": False}
    if row["last_run"] != today.isoformat():
        odoo.call("thirdcode.recurring.invoice", "action_run_now", [[row["id"]]], company_id)
    move = required(odoo.first("account.move", [
        ("thirdcode_recurring_invoice_id", "=", row["id"]),
        ("thirdcode_recurring_invoice_run_date", "=", today.isoformat())],
        ["id", "state", "amount_total"], company_id), "generated recurring invoice")
    if move["state"] != "posted" or abs(move["amount_total"] - 300.0) > 0.01:
        raise RuntimeError("Demo recurring invoice did not post")


def ensure_recurring_journal(odoo: Odoo, company_id: int, journal_id: int,
                             expense_id: int, accrual_id: int, today: date) -> None:
    reference = "DEMO-01-MONTHLY-ACCRUAL"
    row = odoo.first("thirdcode.recurring.journal", [
        ("company_id", "=", company_id), ("reference", "=", reference)],
        ["id", "last_run"], company_id)
    if row is None:
        recurring_id = odoo.call("thirdcode.recurring.journal", "create", [{
            "name": "DEMO | Monthly operating accrual", "company_id": company_id,
            "journal_id": journal_id, "reference": reference,
            "date_start": today.isoformat(), "next_run": today.isoformat(),
            "interval_number": 1, "interval_type": "months",
            "line_ids": [
                [0, 0, {"name": "Fictional monthly cost", "account_id": expense_id,
                        "debit": 80.0, "credit": 0.0}],
                [0, 0, {"name": "Fictional accrued liability", "account_id": accrual_id,
                        "debit": 0.0, "credit": 80.0}],
            ],
        }], company_id)
        row = {"id": recurring_id, "last_run": False}
    if row["last_run"] != today.isoformat():
        odoo.call("thirdcode.recurring.journal", "action_run_now", [[row["id"]]], company_id)
    move = required(odoo.first("account.move", [
        ("thirdcode_recurring_journal_id", "=", row["id"]),
        ("thirdcode_recurring_run_date", "=", today.isoformat())],
        ["id", "state"], company_id), "generated recurring journal")
    if move["state"] != "posted":
        raise RuntimeError("Demo recurring journal did not post")


def ensure_bank_opening(odoo: Odoo, company_id: int, journal_id: int,
                        bank_id: int, equity_id: int, today: date) -> None:
    reference = "DEMO-01-OPENING-BANK"
    row = odoo.first("account.move", [("company_id", "=", company_id),
                                      ("ref", "=", reference)], ["id", "state"], company_id)
    if row is None:
        move_id = odoo.call("account.move", "create", [{
            "company_id": company_id, "journal_id": journal_id,
            "date": today.isoformat(), "ref": reference,
            "line_ids": [
                [0, 0, {"name": "Fictional opening bank balance", "account_id": bank_id,
                        "debit": 3000.0, "credit": 0.0}],
                [0, 0, {"name": "Fictional opening equity", "account_id": equity_id,
                        "debit": 0.0, "credit": 3000.0}],
            ],
        }], company_id)
        row = {"id": move_id, "state": "draft"}
    if row["state"] == "draft":
        odoo.call("account.move", "action_post", [[row["id"]]], company_id)


def demonstration_pdf() -> bytes:
    content = b"BT /F1 14 Tf 50 750 Td (DEMO ONLY - FICTIONAL BANK STATEMENT) Tj 0 -28 Td (Meridian Design Studio - closing PHP 3,000.00) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, item in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode() + item + b"\nendobj\n")
    cross_reference = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{cross_reference}\n%%EOF\n".encode())
    return bytes(output)


def ensure_bank_reconciliation(odoo: Odoo, company_id: int, journal_id: int,
                               today: date) -> None:
    name = "DEMO | Meridian bank reconciliation"
    row = odoo.first("thirdcode.bank.reconciliation", [
        ("company_id", "=", company_id), ("name", "=", name)],
        ["id", "state", "difference"], company_id)
    if row is None:
        recon_id = odoo.call("thirdcode.bank.reconciliation", "create", [{
            "name": name, "company_id": company_id, "journal_id": journal_id,
            "statement_reference": "DEMO-STATEMENT-001",
            "date_start": date(today.year, 1, 1).isoformat(),
            "date_end": today.isoformat(), "opening_balance": 0.0,
            "closing_balance": 3000.0,
            "evidence_file": base64.b64encode(demonstration_pdf()).decode("ascii"),
            "evidence_filename": "DEMO-fictional-bank-statement.pdf",
            "definition": "Synthetic example only. Compare the posted bank ledger to the fictional statement, then sign off.",
        }], company_id)
        row = {"id": recon_id, "state": "draft"}
    if row["state"] != "reconciled":
        odoo.call("thirdcode.bank.reconciliation", "action_compute_ledger_balance",
                  [[row["id"]]], company_id)
        latest = required(odoo.first("thirdcode.bank.reconciliation", [
            ("id", "=", row["id"])], ["difference", "ledger_balance"], company_id), name)
        if abs(latest["difference"]) > 0.01 or abs(latest["ledger_balance"] - 3000.0) > 0.01:
            raise RuntimeError("Demo bank reconciliation does not tie to the posted bank ledger")
        odoo.call("thirdcode.bank.reconciliation", "action_reconcile", [[row["id"]]], company_id)


def ensure_company(odoo: Odoo, index: int, currency_id: int, country_id: int) -> int:
    name = COMPANIES[index - 1]
    row = odoo.first("res.company", [("name", "=", name)], ["id"])
    if row:
        return int(row["id"])
    if index == 1:
        existing = required(odoo.first("res.company", [], ["id", "name"]), "base company")
        if odoo.call("account.move", "search_count", [[("state", "=", "posted")]]) != 0:
            raise RuntimeError("The demo base company already has posted entries; refusing to rename it")
        odoo.call("res.company", "write", [[existing["id"]], {
            "name": name, "currency_id": currency_id, "country_id": country_id,
        }])
        return int(existing["id"])
    return int(odoo.call("res.company", "create", [{
        "name": name, "currency_id": currency_id, "country_id": country_id,
        "email": f"company{index}@example.invalid",
    }]))


def ensure_user(odoo: Odoo, login: str, name: str, company_ids: list[int],
                group_ids: list[int], password: str) -> int:
    row = odoo.first("res.users", [("login", "=", login)], ["id"])
    values = {"name": name, "login": login, "password": password,
              "company_id": company_ids[0], "company_ids": [[6, 0, company_ids]],
              "groups_id": [[6, 0, group_ids]]}
    if row:
        odoo.call("res.users", "write", [[row["id"]], values])
        return int(row["id"])
    return int(odoo.call("res.users", "create", [values]))


def group_id(odoo: Odoo, xml_id: str) -> int:
    module, name = xml_id.split(".")
    row = required(odoo.first("ir.model.data", [("module", "=", module), ("name", "=", name)],
                              ["res_id"]), xml_id)
    return int(row["res_id"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8077")
    parser.add_argument("--database", default="tcsi_demo")
    parser.add_argument("--login", default="admin")
    parser.add_argument("--report-url", default="http://tcsi-client-demo-odoo:8069",
                        help="Odoo origin reachable from wkhtmltopdf inside the demo container")
    parser.add_argument("--credentials-file", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="Write fictional records to the isolated demo")
    args = parser.parse_args()
    parsed = urlparse(args.url)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"}:
        parser.error("The demo seeder accepts only a loopback HTTP origin")
    if "demo" not in args.database.lower():
        parser.error("The database name must contain 'demo'")
    report_origin = urlparse(args.report_url)
    if report_origin.scheme != "http" or report_origin.hostname != "tcsi-client-demo-odoo":
        parser.error("The PDF report origin must be the isolated demo container")
    credentials_path = args.credentials_file.resolve()
    if any((folder / ".git").exists() for folder in credentials_path.parents):
        parser.error("Keep the demo credentials file outside any Git repository")
    if not args.apply:
        print(json.dumps({"status": "dry_run", "companies": list(COMPANIES),
                          "database": args.database, "origin": args.url}))
        return 0

    password = os.environ.get("TCSI_DEMO_ADMIN_PASSWORD")
    if not password:
        parser.error("Set TCSI_DEMO_ADMIN_PASSWORD for the isolated local administrator")
    odoo = Odoo(args.url.rstrip("/"), args.database, args.login, password)
    currency = required(odoo.first("res.currency", [("name", "=", "PHP")],
                                   ["id", "active"], include_inactive=True), "PHP currency")
    country = required(odoo.first("res.country", [("code", "=", "PH")], ["id"]), "Philippines country")
    if not currency["active"]:
        odoo.call("res.currency", "write", [[currency["id"]], {"active": True}])
    administrator_group = group_id(odoo, "thirdcode_accounting.group_thirdcode_administrator")
    report_layout = group_id(odoo, "web.external_layout_standard")
    odoo.call("res.users", "write", [[odoo.uid], {"groups_id": [[4, administrator_group]]}])
    odoo.call("ir.config_parameter", "set_param", ["auth_signup.invitation_scope", "b2b"])
    odoo.call("ir.config_parameter", "set_param", ["report.url", args.report_url])
    today = date.today()
    company_ids: list[int] = []
    summary: list[dict[str, Any]] = []
    for index, name in enumerate(COMPANIES, start=1):
        company_id = ensure_company(odoo, index, int(currency["id"]), int(country["id"]))
        company_ids.append(company_id)
        odoo.call("res.users", "write", [[odoo.uid], {"company_ids": [[4, company_id]]}])
        odoo.call("res.company", "write", [[company_id], {
            "external_report_layout_id": report_layout,
        }], company_id)
        accounts = {key: ensure_account(odoo, company_id, index, key, number, label, kind)
                    for key, number, label, kind in ACCOUNT_SPECS}
        journals = {key: ensure_journal(odoo, company_id, index, key, label, kind, accounts)
                    for key, label, kind in JOURNAL_SPECS}
        customer_id = ensure_partner(odoo, company_id, index, "customer", accounts)
        supplier_id = ensure_partner(odoo, company_id, index, "supplier", accounts)
        ensure_period(odoo, company_id, today)
        ensure_tax_demo(odoo, company_id, today)
        invoice = ensure_document(odoo, company_id, index, "invoice", customer_id,
                                  journals["sale"], accounts["income"], float(1000 + index * 250), today)
        bill = ensure_document(odoo, company_id, index, "bill", supplier_id,
                               journals["purchase"], accounts["expense"], float(200 + index * 40), today)
        summary.append({"company": name, "invoice_id": invoice["id"], "bill_id": bill["id"]})
        print(json.dumps({"seeded_company": name, "index": index}), flush=True)

    first_company = company_ids[0]
    first_invoice = required(odoo.first("account.move", [("company_id", "=", first_company),
                                                      ("move_type", "=", "out_invoice"),
                                                      ("ref", "=", "DEMO-01-INVOICE-001")],
                                        ["id", "amount_total", "amount_residual", "partner_id"],
                                        first_company), "Meridian invoice")
    first_bank = required(odoo.first("account.journal", [("company_id", "=", first_company),
                                                      ("code", "=", "B01")], ["id"],
                                     first_company), "Meridian bank journal")
    odoo.call("res.company", "write", [[first_company], {
        "thirdcode_payment_approval_enabled": True,
        "thirdcode_payment_approval_threshold": 100.0,
        "thirdcode_reconciliation_definition":
            "Fictional demonstration: compare the manually entered statement to posted bank ledger, attach evidence, and sign off.",
    }], first_company)
    expected_payment = round(first_invoice["amount_total"] / 2, 2)
    ensure_demo_payment(odoo, first_company, int(first_bank["id"]),
                        int(first_invoice["id"]), int(first_invoice["partner_id"][0]),
                        expected_payment, today, "DEMO | Meridian customer receipt",
                        "inbound", "customer", "DEMO-TRANSFER-001")
    first_invoice = required(odoo.first("account.move", [("id", "=", first_invoice["id"])],
                                       ["amount_residual"], first_company),
                             "Meridian invoice after payment")
    if abs(first_invoice["amount_residual"] - expected_payment) > 0.01:
        raise RuntimeError("Demo partial payment did not reduce the invoice balance")
    first_bill = required(odoo.first("account.move", [("company_id", "=", first_company),
                                                   ("move_type", "=", "in_invoice"),
                                                   ("ref", "=", "DEMO-01-BILL-001")],
                                    ["id", "amount_total", "partner_id"], first_company),
                          "Meridian supplier bill")
    expected_supplier_payment = round(first_bill["amount_total"] / 2, 2)
    ensure_demo_payment(odoo, first_company, int(first_bank["id"]),
                        int(first_bill["id"]), int(first_bill["partner_id"][0]),
                        expected_supplier_payment, today, "DEMO | Meridian supplier settlement",
                        "outbound", "supplier", "DEMO-TRANSFER-002")
    first_bill = required(odoo.first("account.move", [("id", "=", first_bill["id"])],
                                    ["amount_residual"], first_company),
                          "Meridian bill after payment")
    if abs(first_bill["amount_residual"] - expected_supplier_payment) > 0.01:
        raise RuntimeError("Demo supplier payment did not reduce the bill balance")
    first_sale = required(odoo.first("account.journal", [("company_id", "=", first_company),
                                                      ("code", "=", "S01")], ["id"],
                                     first_company), "Meridian sales journal")
    first_general = required(odoo.first("account.journal", [("company_id", "=", first_company),
                                                         ("code", "=", "G01")], ["id"],
                                        first_company), "Meridian general journal")
    first_income = required(odoo.first("account.account", [("code", "=", "401001"),
                                                       ("company_ids", "in", [first_company])],
                                        ["id"], first_company), "Meridian income account")
    first_bank_account = required(odoo.first("account.account", [("code", "=", "101001"),
                                                             ("company_ids", "in", [first_company])],
                                              ["id"], first_company), "Meridian bank account")
    first_equity = required(odoo.first("account.account", [("code", "=", "301001"),
                                                       ("company_ids", "in", [first_company])],
                                        ["id"], first_company), "Meridian equity account")
    first_expense = required(odoo.first("account.account", [("code", "=", "601001"),
                                                        ("company_ids", "in", [first_company])],
                                         ["id"], first_company), "Meridian expense account")
    first_accrual = ensure_account(odoo, first_company, 1, "accrual", 229900,
                                   "Demo operating accrual", "liability_current")
    first_customer = int(required(odoo.first("account.move", [
        ("company_id", "=", first_company), ("move_type", "=", "out_invoice"),
        ("ref", "=", "DEMO-01-INVOICE-001")],
        ["partner_id"], first_company), "Meridian customer document")["partner_id"][0])
    ensure_recurring_invoice(odoo, first_company, int(first_sale["id"]),
                             first_customer, int(first_income["id"]), today)
    ensure_recurring_journal(odoo, first_company, int(first_general["id"]),
                             int(first_expense["id"]), first_accrual, today)
    ensure_bank_opening(odoo, first_company, int(first_general["id"]),
                        int(first_bank_account["id"]), int(first_equity["id"]), today)
    ensure_bank_reconciliation(odoo, first_company, int(first_bank["id"]), today)

    presenter_password = secrets.token_urlsafe(24)
    accountant_passwords = [secrets.token_urlsafe(24) for _ in company_ids]
    presenter_login = "demo.presenter@example.invalid"
    accountant_group = group_id(odoo, "thirdcode_accounting.group_thirdcode_accountant")
    settings_group = group_id(odoo, "base.group_system")
    ensure_user(odoo, presenter_login, "DEMO | Presenter", company_ids,
                [administrator_group, settings_group], presenter_password)
    credentials = [{"role": "presenter", "login": presenter_login,
                    "password": presenter_password}]
    for index, company_id in enumerate(company_ids, start=1):
        login = f"demo.accountant{index}@example.invalid"
        ensure_user(odoo, login, f"DEMO | Accountant {index}", [company_id],
                    [accountant_group], accountant_passwords[index - 1])
        credentials.append({"role": f"company_{index}_accountant", "login": login,
                            "password": accountant_passwords[index - 1]})
    local_admin_password = secrets.token_urlsafe(24)
    credentials.append({"role": "local_setup_administrator", "login": args.login,
                        "password": local_admin_password})
    args.credentials_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_credentials = args.credentials_file.with_suffix(args.credentials_file.suffix + ".tmp")
    with temporary_credentials.open("w", encoding="utf-8") as output:
        json.dump({"database": args.database, "origin": args.url, "accounts": credentials}, output, indent=2)
    try:
        os.chmod(temporary_credentials, 0o600)
    except OSError:
        pass
    os.replace(temporary_credentials, args.credentials_file)
    odoo.call("res.users", "write", [[odoo.uid], {"password": local_admin_password}])
    print(json.dumps({"status": "seeded", "database": args.database,
                      "companies": summary, "credentials_file": str(args.credentials_file)}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except xmlrpc.client.Fault as error:
        print(json.dumps({"status": "failed", "fault": "\n".join(error.faultString.splitlines()[-12:])[:1800]}),
              file=sys.stderr)
        sys.exit(1)
