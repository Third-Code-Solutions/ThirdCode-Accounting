#!/usr/bin/env python3
"""Check the isolated five-company client demo without changing accounting records."""

from __future__ import annotations

import argparse
import json
import sys
import xmlrpc.client
from datetime import date
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.request import HTTPCookieProcessor, Request, build_opener

from seed_client_demo import COMPANIES, Odoo, required


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def dashboard(account: dict[str, str], origin: str, database: str,
              company_id: int) -> dict:
    opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def post(path: str, params: dict) -> dict:
        body = json.dumps({"jsonrpc": "2.0", "method": "call", "params": params,
                           "id": 1}).encode("utf-8")
        request = Request(f"{origin}{path}", body,
                          {"Content-Type": "application/json"})
        with opener.open(request, timeout=20) as response:
            return json.load(response)

    session = post("/web/session/authenticate", {
        "db": database, "login": account["login"], "password": account["password"],
    })
    check(session.get("result", {}).get("uid"),
          f"Browser session authentication failed for {account['role']}")
    return post("/thirdcode_accounting/dashboard", {"company_id": company_id})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials-file", required=True, type=Path)
    args = parser.parse_args()
    access = json.loads(args.credentials_file.read_text(encoding="utf-8"))
    origin = access["origin"]
    database = access["database"]
    check(origin.startswith(("http://localhost:", "http://127.0.0.1:")) and
          "demo" in database.lower(), "Refusing to inspect a nonlocal or non-demo database")
    accounts = access["accounts"]
    presenter = accounts[0]
    admin = Odoo(origin, database, presenter["login"], presenter["password"])
    signup_scope = admin.call("ir.config_parameter", "get_param", ["auth_signup.invitation_scope"])
    check(signup_scope == "b2b", "Public self-signup is enabled")
    today = date.today().isoformat()
    company_ids: list[int] = []
    for index, name in enumerate(COMPANIES, start=1):
        company = required(admin.first("res.company", [("name", "=", name)], ["id", "currency_id"]),
                           name)
        company_id = int(company["id"])
        company_ids.append(company_id)
        check(company["currency_id"][1] == "PHP", f"{name} does not use PHP")
        period = required(admin.first("thirdcode.accounting.period", [
            ("company_id", "=", company_id), ("state", "=", "open")], ["id"]),
            f"{name} open period")
        check(bool(period), f"{name} has no open period")
        for kind, move_type, amount in (
            ("INVOICE", "out_invoice", float(1000 + index * 250)),
            ("BILL", "in_invoice", float(200 + index * 40)),
        ):
            move = required(admin.first("account.move", [
                ("company_id", "=", company_id),
                ("move_type", "=", move_type),
                ("ref", "=", f"DEMO-{index:02d}-{kind}-001")],
                ["id", "state", "move_type", "amount_total", "invoice_date"], company_id),
                f"{name} {kind}")
            check(move["state"] == "posted" and move["move_type"] == move_type and
                  abs(move["amount_total"] - amount) < 0.01 and
                  move["invoice_date"] == today, f"{name} {kind} is not a current posted document")
        tax = required(admin.first("thirdcode.tax.profile", [
            ("company_id", "=", company_id),
            ("name", "=", "DEMO ONLY | No statutory tax determination")],
            ["id", "status"], company_id), f"{name} tax disclosure")
        check(tax["status"] == "configured", f"{name} tax disclosure not configured")

    check(len(set(company_ids)) == 5, "The five demo company records are not distinct")
    for index, company_id in enumerate(company_ids, start=1):
        selected = dashboard(presenter, origin, database, company_id)
        result = selected.get("result", {})
        check(result.get("company_id") == company_id and
              result.get("company_name") == COMPANIES[index - 1],
              f"Presenter dashboard did not switch to {COMPANIES[index - 1]}")
        expected_receivables = float(1000 + index * 250 + (300 if index == 1 else 0) -
                                     (625 if index == 1 else 0))
        check(abs(result["kpis"]["receivables"] - expected_receivables) < 0.01,
              f"Presenter dashboard mixed company {index} receivables")
    first_invoice = required(admin.first("account.move", [
        ("company_id", "=", company_ids[0]), ("move_type", "=", "out_invoice"),
        ("ref", "=", "DEMO-01-INVOICE-001")],
        ["id", "amount_total", "amount_residual"], company_ids[0]), "Meridian invoice")
    check(abs(first_invoice["amount_residual"] - first_invoice["amount_total"] / 2) < 0.01,
          "Partial receipt did not leave the expected invoice balance")
    try:
        admin.call("account.move", "action_print_thirdcode_invoice",
                   [[first_invoice["id"]]], company_ids[0])
    except xmlrpc.client.Fault as error:
        check("BIR acknowledgement control number" in error.faultString,
              "The unapproved statutory invoice print failed for an unexpected reason")
    else:
        raise RuntimeError("An unapproved statutory invoice was printable")
    batch = required(admin.first("thirdcode.payment.batch", [
        ("company_id", "=", company_ids[0]), ("name", "=", "DEMO | Meridian customer receipt")],
        ["id", "state", "approved_by", "line_ids"], company_ids[0]), "Meridian payment batch")
    check(batch["state"] == "posted" and bool(batch["approved_by"]) and
          len(batch["line_ids"]) == 1, "The approval and payment batch did not complete")
    supplier_batch = required(admin.first("thirdcode.payment.batch", [
        ("company_id", "=", company_ids[0]),
        ("name", "=", "DEMO | Meridian supplier settlement")],
        ["id", "state", "approved_by", "line_ids"], company_ids[0]),
        "Meridian supplier payment batch")
    check(supplier_batch["state"] == "posted" and bool(supplier_batch["approved_by"]) and
          len(supplier_batch["line_ids"]) == 1,
          "The supplier approval and payment batch did not complete")
    first_bill = required(admin.first("account.move", [
        ("company_id", "=", company_ids[0]), ("move_type", "=", "in_invoice"),
        ("ref", "=", "DEMO-01-BILL-001")],
        ["amount_total", "amount_residual"], company_ids[0]), "Meridian bill")
    check(abs(first_bill["amount_residual"] - first_bill["amount_total"] / 2) < 0.01,
          "Supplier settlement did not reduce the open bill balance")
    recurring = required(admin.first("thirdcode.recurring.invoice", [
        ("company_id", "=", company_ids[0]),
        ("reference", "=", "DEMO-01-MONTHLY-SERVICE")],
        ["id", "last_run", "generated_move_ids"], company_ids[0]), "Meridian recurring invoice")
    check(recurring["last_run"] == today and len(recurring["generated_move_ids"]) == 1,
          "The recurring invoice did not generate exactly one current invoice")
    recurring_journal = required(admin.first("thirdcode.recurring.journal", [
        ("company_id", "=", company_ids[0]),
        ("reference", "=", "DEMO-01-MONTHLY-ACCRUAL")],
        ["id", "last_run", "generated_move_ids"], company_ids[0]),
        "Meridian recurring journal")
    check(recurring_journal["last_run"] == today and
          len(recurring_journal["generated_move_ids"]) == 1,
          "The recurring journal did not generate exactly one current entry")
    reconciliation = required(admin.first("thirdcode.bank.reconciliation", [
        ("company_id", "=", company_ids[0]),
        ("name", "=", "DEMO | Meridian bank reconciliation")],
        ["id", "state", "difference", "ledger_balance", "evidence_filename"],
        company_ids[0]), "Meridian reconciliation")
    check(reconciliation["state"] == "reconciled" and
          abs(reconciliation["difference"]) < 0.01 and
          abs(reconciliation["ledger_balance"] - 3000.0) < 0.01 and
          reconciliation["evidence_filename"] == "DEMO-fictional-bank-statement.pdf",
          "The signed fictional bank reconciliation is incomplete")

    for index, company_id in enumerate(company_ids, start=1):
        for report_type in ("balance_sheet", "profit_loss", "cash_flow"):
            wizard_id = admin.call("thirdcode.financial.report.wizard", "create", [{
                "company_id": company_id, "report_type": report_type,
                "date_from": f"{date.today().year}-01-01", "date_to": today,
                "target_move": "posted",
            }], company_id)
            report = admin.call("thirdcode.financial.report.wizard", "get_report_data",
                                [[wizard_id]], company_id)
            check(report["sections"], f"{COMPANIES[index - 1]} {report_type} is empty")
            check(report["layout_status"].startswith("DRAFT LAYOUT"),
                  "A fictional company was presented as client-approved")
            if report_type == "balance_sheet":
                check(report["balanced"], f"{COMPANIES[index - 1]} balance sheet does not balance")
            elif report_type == "profit_loss":
                expected_net = float(800 + index * 210 + (220 if index == 1 else 0))
                actual_net = float(report["net_result"].replace(",", ""))
                check(abs(actual_net - expected_net) < 0.01,
                      f"{COMPANIES[index - 1]} profit and loss does not match posted documents")

    accountants = [account for account in accounts if account["role"].startswith("company_")]
    check(len(accountants) == 5, "Expected five named restricted accountants")
    for index, account in enumerate(accountants, start=1):
        user = Odoo(origin, database, account["login"], account["password"])
        own_company = company_ids[index - 1]
        visible_companies = user.call("res.users", "read", [[user.uid]], fields=["company_ids"])[0]["company_ids"]
        check(visible_companies == [own_company], f"Accountant {index} can select another company")
        own_moves = user.call("account.move", "search_count", [[
            ("company_id", "=", own_company), ("state", "=", "posted")]], own_company)
        check(own_moves >= 2, f"Accountant {index} cannot see own posted documents")
        other_company = company_ids[index % 5]
        other_moves = user.call("account.move", "search_count", [[
            ("company_id", "=", other_company), ("state", "=", "posted")]], own_company)
        check(other_moves == 0, f"Accountant {index} can read another company's documents")
        own_dashboard = dashboard(account, origin, database, own_company)
        check(own_dashboard.get("result", {}).get("company_id") == own_company,
              f"Accountant {index} dashboard did not use the selected company")
        other_dashboard = dashboard(account, origin, database, other_company)
        check("error" in other_dashboard and "result" not in other_dashboard,
              f"Accountant {index} dashboard exposed another company's data")

    print(json.dumps({"status": "passed", "companies": len(company_ids),
                      "posted_documents_minimum": 10, "restricted_accountants": 5,
                      "approved_customer_and_supplier_payments": True,
                      "recurring_invoice": True, "recurring_journal": True,
                      "bank_reconciliation": True,
                      "financial_reports": 15, "public_signup": False}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, xmlrpc.client.Fault) as error:
        print(json.dumps({"status": "failed", "error": str(error).splitlines()[-1][:300]}),
              file=sys.stderr)
        sys.exit(1)
