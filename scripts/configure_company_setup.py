#!/usr/bin/env python3
"""Provision a legal company's accounting baseline on the hosted workspace.

Sets the company country/currency, loads the chart-of-accounts template,
ensures the standard journals exist, and creates the open accounting period.
Idempotent: re-running skips what already exists. The password is prompted and
never passed on the command line or printed.

Run with an engine administrator login (one that holds Settings and Accounting
Manager rights, e.g. the hosted ``TCSI_ADMIN_LOGIN`` account).

Usage:
  python3 scripts/configure_company_setup.py \
      --url https://tcsi-accounting-production.up.railway.app \
      --database tcsi_pilot \
      --login pilot-admin@thirdcodesolutions.com \
      --company-id 1 \
      --chart-template ph \
      --period-name "FY 2026" --period-start 2026-01-01 --period-end 2026-12-31

Exit codes: 0 complete (or already complete), 1 a step failed, 2 bad arguments.
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
import urllib.error
import urllib.request

JOURNALS = [
    ("Sales", "SLS", "sale"),
    ("Purchases", "PUR", "purchase"),
    ("Miscellaneous Operations", "MISC", "general"),
    ("Bank", "BNK", "bank"),
    ("Cash", "CSH", "cash"),
]


class Engine:
    def __init__(self, base_url: str, database: str, login: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.database = database
        self.login = login
        self.password = password
        self.session_id: str | None = None
        self.uid: int | None = None

    def _rpc(self, path: str, params: dict) -> dict:
        body = {"jsonrpc": "2.0", "method": "call", "params": params}
        headers = {"Content-Type": "application/json"}
        if self.session_id:
            headers["Cookie"] = f"session_id={self.session_id}"
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=json.dumps(body).encode(), headers=headers
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.loads(response.read())
            for cookie in response.headers.get_all("Set-Cookie") or []:
                if cookie.startswith("session_id="):
                    self.session_id = cookie.split(";")[0].split("=", 1)[1]
        if "error" in payload:
            error = payload["error"].get("data", {}).get("message", str(payload["error"]))
            raise RuntimeError(error.splitlines()[0][:220])
        return payload.get("result")

    def authenticate(self) -> None:
        result = self._rpc(
            "/web/session/authenticate",
            {"db": self.database, "login": self.login, "password": self.password},
        )
        if not result or not result.get("uid"):
            raise RuntimeError("authentication failed")
        self.uid = result["uid"]
        print(f"authenticated as {self.login} (uid {self.uid}) on database {self.database}")

    def call(self, model: str, method: str, args: list, kwargs: dict | None = None):
        return self._rpc(
            "/web/dataset/call_kw",
            {"model": model, "method": method, "args": args, "kwargs": kwargs or {}},
        )

    def search_read(self, model: str, domain: list, fields: list, **kwargs):
        return self.call(model, "search_read", [domain], {"fields": fields, **kwargs}) or []

    def search_count(self, model: str, domain: list) -> int:
        result = self.call(model, "search_count", [domain])
        return result if isinstance(result, int) else 0


def ensure_country_currency(engine: Engine, company_id: int, country_code: str, currency: str) -> None:
    company = engine.call("res.company", "read", [[company_id], ["name", "country_id", "currency_id"]])[0]
    print(f"company {company_id}: {company['name']}")
    country = engine.search_read("res.country", [["code", "=", country_code]], ["name"])
    if not country:
        raise RuntimeError(f"country {country_code} not found in the workspace")
    currency_row = engine.search_read(
        "res.currency", [["name", "=", currency]], ["name", "active"],
        context={"active_test": False},
    )
    if not currency_row:
        raise RuntimeError(f"currency {currency} not found in the workspace")
    if not currency_row[0]["active"]:
        engine.call("res.currency", "write", [[currency_row[0]["id"]], {"active": True}])
        print(f"activated currency {currency}")
    updates = {}
    if not company["country_id"] or company["country_id"][1] != country[0]["name"]:
        updates["country_id"] = country[0]["id"]
    if company["currency_id"][1] != currency:
        updates["currency_id"] = currency_row[0]["id"]
    if updates:
        engine.call("res.company", "write", [[company_id], updates])
    final = engine.call("res.company", "read", [[company_id], ["country_id", "currency_id"]])[0]
    print(f"company country={final['country_id'][1] if final['country_id'] else None} "
          f"currency={final['currency_id'][1] if final['currency_id'] else None}"
          + (" (unchanged)" if not updates else ""))


def ensure_chart(engine: Engine, template_code: str) -> None:
    accounts = engine.search_count("account.account", [])
    if accounts:
        print(f"chart of accounts already present ({accounts} accounts); skipping template load")
        return
    engine.call(
        "account.chart.template", "try_loading", [],
        {"template_code": template_code, "install_demo": False},
    )
    print(f"loaded chart template '{template_code}' "
          f"({engine.search_count('account.account', [])} accounts, "
          f"{engine.search_count('account.tax', [])} taxes)")


def ensure_journals(engine: Engine, company_id: int) -> None:
    existing = engine.search_read(
        "account.journal", [["company_id", "=", company_id]], ["code", "name", "type"]
    )
    have_types = {journal["type"] for journal in existing}
    print(f"journals present: {sorted(have_types) or 'none'}")
    for name, code, journal_type in JOURNALS:
        if journal_type in have_types:
            continue
        if engine.search_count("account.journal", [["company_id", "=", company_id], ["code", "=", code]]):
            print(f"journal code {code} already used; leaving as is")
            continue
        engine.call(
            "account.journal", "create",
            [{"name": name, "code": code, "type": journal_type, "company_id": company_id}],
        )
        print(f"created {journal_type} journal {name} ({code})")


def ensure_period(engine: Engine, company_id: int, name: str, start: str, end: str) -> None:
    periods = engine.search_read(
        "thirdcode.accounting.period", [["company_id", "=", company_id]],
        ["name", "date_start", "date_end", "state"],
    )
    for period in periods:
        if period["name"] == name or (period["date_start"] <= end and period["date_end"] >= start):
            print(f"period {period['name']} ({period['date_start']}..{period['date_end']}) "
                  f"state={period['state']}; reusing")
            return
    engine.call(
        "thirdcode.accounting.period", "create",
        [{"name": name, "company_id": company_id, "date_start": start, "date_end": end, "state": "open"}],
    )
    print(f"created open period {name} ({start}..{end})")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Provision a legal company's accounting baseline (country, currency, chart, journals, open period)."
    )
    parser.add_argument("--url", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--login", required=True)
    parser.add_argument("--company-id", type=int, required=True)
    parser.add_argument("--chart-template", default="ph")
    parser.add_argument("--country", default="PH")
    parser.add_argument("--currency", default="PHP")
    parser.add_argument("--period-name", required=True)
    parser.add_argument("--period-start", required=True)
    parser.add_argument("--period-end", required=True)
    args = parser.parse_args()

    password = getpass.getpass(f"Password for {args.login} (input hidden): ")
    engine = Engine(args.url, args.database, args.login, password)
    try:
        engine.authenticate()
        ensure_country_currency(engine, args.company_id, args.country, args.currency)
        ensure_chart(engine, args.chart_template)
        ensure_journals(engine, args.company_id)
        ensure_period(engine, args.company_id, args.period_name, args.period_start, args.period_end)
    except RuntimeError as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return 1

    print("\ncompany baseline complete:")
    print(f"  accounts: {engine.search_count('account.account', [])}")
    print(f"  journals: {engine.search_count('account.journal', [['company_id', '=', args.company_id]])}")
    print(f"  periods:  {engine.search_count('thirdcode.accounting.period', [['company_id', '=', args.company_id]])}")
    print("Next: map the tax profile (accountant), record BIR values on the company, "
          "then run scripts/check_company_readiness.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
