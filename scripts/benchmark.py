"""Measure synthetic Odoo save/post latency with the proposed two-user load."""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import http.cookiejar
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Any


class OdooHttp:
    def __init__(self, base_url: str, database: str, login: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        payload = self._request(
            "/web/session/authenticate",
            {"db": database, "login": login, "password": password},
        )
        result = payload.get("result") or {}
        if not result.get("uid"):
            raise RuntimeError(f"Odoo authentication failed: {payload}")

    def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": params}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self.opener.open(request, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError) as exc:
            raise RuntimeError(f"Odoo HTTP request failed: {exc}") from exc
        if payload.get("error"):
            raise RuntimeError(json.dumps(payload["error"], sort_keys=True))
        return payload

    def call(self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        payload = self._request(
            "/web/dataset/call_kw",
            {"model": model, "method": method, "args": args, "kwargs": kwargs or {}},
        )
        return payload.get("result")


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * fraction))
    return ordered[index]


def summary(values: list[float]) -> dict[str, float | int]:
    return {
        "count": len(values),
        "min_ms": round(min(values), 2) if values else 0.0,
        "p50_ms": round(statistics.median(values), 2) if values else 0.0,
        "p95_ms": round(percentile(values, 0.95), 2),
        "max_ms": round(max(values), 2) if values else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8069")
    parser.add_argument("--database", default="thirdcode_accounting")
    parser.add_argument("--login", default="admin")
    parser.add_argument("--password", default="admin")
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--post", action="store_true", help="Also post each synthetic invoice; posted probes remain in the database")
    parser.add_argument("--target-save-ms", type=float, default=2000.0)
    parser.add_argument("--target-post-ms", type=float, default=2000.0)
    parser.add_argument("--output", type=str)
    args = parser.parse_args()
    if args.iterations <= 0 or args.workers <= 0:
        raise SystemExit("--iterations and --workers must be positive")

    odoo = OdooHttp(args.url, args.database, args.login, args.password)
    company = odoo.call("res.company", "search_read", [[]], {"fields": ["id"], "limit": 1})[0]
    company_id = int(company["id"])
    partner_rows = odoo.call(
        "res.partner",
        "search_read",
        [[("ref", "=", "TC-BENCHMARK-PARTNER")]],
        {"fields": ["id"], "limit": 1},
    )
    if partner_rows:
        partner = partner_rows[0]
    else:
        receivable = odoo.call(
            "account.account",
            "search_read",
            [[("company_ids", "in", [company_id]), ("code", "=", "121000")]],
            {"fields": ["id"], "limit": 1},
        )[0]
        payable = odoo.call(
            "account.account",
            "search_read",
            [[("company_ids", "in", [company_id]), ("code", "=", "211000")]],
            {"fields": ["id"], "limit": 1},
        )[0]
        partner_id = odoo.call(
            "res.partner",
            "create",
            [{
                "name": "Synthetic Performance Benchmark Partner",
                "ref": "TC-BENCHMARK-PARTNER",
                "company_type": "company",
                "customer_rank": 1,
                "property_account_receivable_id": int(receivable["id"]),
                "property_account_payable_id": int(payable["id"]),
            }],
        )
        partner = {"id": int(partner_id)}
    income = odoo.call(
        "account.account",
        "search_read",
        [[("company_ids", "in", [company_id]), ("code", "=", "400000")]],
        {"fields": ["id"], "limit": 1},
    )[0]
    journal = odoo.call(
        "account.journal",
        "search_read",
        [[("company_id", "=", company_id), ("type", "=", "sale")]],
        {"fields": ["id"], "limit": 1},
    )[0]

    def one(iteration: int) -> dict[str, Any]:
        local = OdooHttp(args.url, args.database, args.login, args.password)
        reference = f"TC-BENCH-{uuid.uuid4().hex[:12]}-{iteration}"
        values = {
            "company_id": company_id,
            "move_type": "out_invoice",
            "partner_id": int(partner["id"]),
            "journal_id": int(journal["id"]),
            "invoice_date": date.today().isoformat(),
            "ref": reference,
            "invoice_line_ids": [[0, 0, {
                "name": "Synthetic performance probe",
                "quantity": 1,
                "price_unit": 1.0,
                "account_id": int(income["id"]),
            }]],
        }
        move_id = None
        try:
            started = time.perf_counter()
            move_id = int(local.call("account.move", "create", [values]))
            create_ms = (time.perf_counter() - started) * 1000
            post_ms = None
            if args.post:
                started = time.perf_counter()
                local.call("account.move", "action_post", [[move_id]])
                post_ms = (time.perf_counter() - started) * 1000
            else:
                local.call("account.move", "unlink", [[move_id]])
            return {"create_ms": create_ms, "post_ms": post_ms, "reference": reference}
        except Exception:
            if move_id:
                try:
                    state = local.call("account.move", "read", [[move_id]], {"fields": ["state"]})[0]["state"]
                    if state == "draft":
                        local.call("account.move", "unlink", [[move_id]])
                except Exception:
                    pass
            raise

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(one, index) for index in range(args.iterations)]
        for future in as_completed(futures):
            results.append(future.result())
    create_values = [float(item["create_ms"]) for item in results]
    post_values = [float(item["post_ms"]) for item in results if item["post_ms"] is not None]
    result = {
        "status": "VERIFIED LOCALLY",
        "synthetic": True,
        "database": args.database,
        "workers": args.workers,
        "iterations": args.iterations,
        "post_enabled": args.post,
        "targets_ms": {"save": args.target_save_ms, "post": args.target_post_ms},
        "save": summary(create_values),
        "post": summary(post_values),
        "target_observed": {
            "save_p95_within_target": bool(create_values) and percentile(create_values, 0.95) <= args.target_save_ms,
            "post_p95_within_target": bool(post_values) and percentile(post_values, 0.95) <= args.target_post_ms if args.post else None,
        },
        "note": "Synthetic local timing only; not evidence for client hardware, volume, or production concurrency acceptance.",
    }
    serialized = json.dumps(result, indent=2, sort_keys=True)
    print(serialized)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(serialized + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
