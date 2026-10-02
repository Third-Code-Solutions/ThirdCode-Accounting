#!/usr/bin/env python3
"""Read-only structural preflight for the Odoo accounting pilot."""

from __future__ import annotations

import argparse
import getpass
import http.client
import json
import os
import socket
import sys
import time
import xmlrpc.client
from datetime import date
from typing import Any

LEGAL_GATED_CHECKS = frozenset(
    {
        "approved_tax_profile",
        "approved_bir_control",
        "eis_assessed",
        "report_samples_approved",
        "backup_owner",
        "restore_owner",
    }
)


def check_company(call: Any, company: dict[str, Any], on_date: str, trial: bool = False) -> dict[str, Any]:
    company_id = company["id"]
    context = {"allowed_company_ids": [company_id]}

    def count(model: str, domain: list[Any]) -> int:
        return call(model, "search_count", [domain], {"context": context})

    accounts = count("account.account", [["company_ids", "in", [company_id]]])
    journals = {
        kind: count("account.journal", [["company_id", "=", company_id], ["type", "=", kind]])
        for kind in ("sale", "purchase", "general", "bank", "cash")
    }
    periods = count("thirdcode.accounting.period", [
        ["company_id", "=", company_id], ["state", "=", "open"],
        ["date_start", "<=", on_date], ["date_end", ">=", on_date],
    ])
    tax_profiles = count("thirdcode.tax.profile", [
        ["company_id", "=", company_id], ["status", "=", "configured"],
        ["effective_date", "<=", on_date],
    ])
    approved_samples = {
        kind: count("thirdcode.report.sample", [
            ["company_id", "=", company_id], ["sample_type", "=", kind],
            ["state", "=", "approved"],
        ])
        for kind in ("statement", "financial", "invoice", "receipt", "reconciliation")
    }
    checks = {
        "chart_of_accounts": accounts > 0,
        "sales_journal": journals["sale"] > 0,
        "purchase_journal": journals["purchase"] > 0,
        "general_journal": journals["general"] > 0,
        "bank_or_cash_journal": journals["bank"] + journals["cash"] > 0,
        "open_period_today": periods > 0,
        "approved_tax_profile": tax_profiles > 0,
        "approved_bir_control": bool(company["thirdcode_bir_ack_approved"] and company["thirdcode_bir_ack_control_number"]),
        "eis_assessed": company["thirdcode_eis_status"] in ("not_in_scope", "configured"),
        "report_samples_approved": bool(company["thirdcode_report_samples_approved"] and all(approved_samples.values())),
        "backup_owner": bool(company["thirdcode_backup_owner"]),
        "restore_owner": bool(company["thirdcode_restore_owner"]),
    }
    trial_deferred: dict[str, Any] = {}
    if trial:
        trial_deferred = {
            key: checks.pop(key) for key in list(checks) if key in LEGAL_GATED_CHECKS
        }
    return {
        "id": company_id,
        "name": company["name"],
        "checks": checks,
        "trial_deferred": trial_deferred,
        "counts": {"accounts": accounts, "journals": journals, "open_periods_today": periods,
                   "configured_tax_profiles": tax_profiles, "approved_report_samples": approved_samples},
        "structurally_ready": all(checks.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Odoo origin URL")
    parser.add_argument("--database", required=True)
    parser.add_argument("--login", required=True)
    parser.add_argument("--expected-companies", type=int, default=5)
    parser.add_argument("--trial", action="store_true",
                        help="Trial/personal use: BIR, EIS, report-sample and backup-owner items are "
                             "reported separately as trial-deferred instead of blocking.")
    parser.add_argument("--date", default=date.today().isoformat())
    args = parser.parse_args()
    if args.expected_companies < 1:
        parser.error("--expected-companies must be positive")
    try:
        date.fromisoformat(args.date)
    except ValueError:
        parser.error("--date must use YYYY-MM-DD")
    password = os.environ.get("TCSI_ODOO_PASSWORD") or getpass.getpass("Odoo password: ")
    socket.setdefaulttimeout(10)
    common = xmlrpc.client.ServerProxy(f"{args.url.rstrip('/')}/xmlrpc/2/common", allow_none=True)
    models = xmlrpc.client.ServerProxy(f"{args.url.rstrip('/')}/xmlrpc/2/object", allow_none=True)
    uid = common.authenticate(args.database, args.login, password, {})
    if not uid:
        print(json.dumps({"status": "blocked", "reason": "authentication_failed"}))
        return 2

    def call(model: str, method: str, positional: list[Any], keyword: dict[str, Any] | None = None) -> Any:
        # Read-only preflight: retry once the origin edge drops a connection
        # mid-response (IncompleteRead / reset), which the hosted proxy
        # occasionally does.
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                return models.execute_kw(
                    args.database, uid, password, model, method, positional, keyword or {}
                )
            except (OSError, http.client.HTTPException, xmlrpc.client.ProtocolError) as error:
                last_error = error
                time.sleep(1.5 * (attempt + 1))
        raise last_error  # type: ignore[misc]

    user = call("res.users", "read", [[uid]], {"fields": ["company_ids"]})[0]
    allowed = user["company_ids"]
    companies = call("res.company", "search_read", [[["id", "in", allowed]]], {"fields": [
        "name", "thirdcode_bir_ack_control_number", "thirdcode_bir_ack_approved",
        "thirdcode_eis_status", "thirdcode_report_samples_approved",
        "thirdcode_backup_owner", "thirdcode_restore_owner",
    ]})
    checked = [check_company(call, company, args.date, trial=args.trial) for company in companies]
    checks = {"expected_company_count": len(checked) == args.expected_companies,
              "all_company_structures": all(item["structurally_ready"] for item in checked)}
    print(json.dumps({
        "status": "structurally_ready" if all(checks.values()) else "blocked",
        "trial_mode": args.trial,
        "checks": checks,
        "companies": checked,
        "manual_gates_not_verified": [
            "approved chart, tax and document decisions for each legal company",
            "authorized opening balances and source-to-ledger reconciliation",
            "named user role and cross-company access acceptance",
            "one real parallel accounting month and financial report sign-off",
            "recent paired production database/filestore restore and backup schedule",
            "legal and license review",
        ],
    }, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except xmlrpc.client.Fault as error:
        print(json.dumps({"status": "blocked", "reason": "odoo_rpc_fault",
                          "fault_code": error.faultCode,
                          "detail": error.faultString.splitlines()[-1][:200]}))
        sys.exit(2)
    except (OSError, xmlrpc.client.Error) as error:
        print(json.dumps({"status": "blocked", "reason": type(error).__name__}))
        sys.exit(2)
