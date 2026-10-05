"""Measure native invoice save/post RPC latency in an explicitly isolated database.

Credentials come from ODOO_LOGIN and ODOO_PASSWORD. Synthetic posted invoices and
fixture partners remain in the disposable database; never point this at customer
books. This measures RPC calls, not browser interaction or client acceptance.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from typing import Any, Callable


ISOLATED_DATABASE = re.compile(r"tcsi_alignment_[A-Za-z0-9_]+\Z")


class OdooHttp:
    def __init__(self, base_url: str, database: str, login: str, password: str) -> None:
        if not ISOLATED_DATABASE.fullmatch(database):
            raise ValueError("Synthetic probes require an isolated tcsi_alignment_ database")
        self.base_url = base_url.rstrip("/")
        self.password = password
        self.company_id: int | None = None
        self.closed = False
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        payload = self._request("/web/session/authenticate", {"db": database, "login": login, "password": password})
        result = payload.get("result") or {}
        if not result.get("uid"):
            raise RuntimeError("Odoo authentication failed")
        self.uid = int(result["uid"])

    def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": params}).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with self.opener.open(request, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError) as exc:
            message = str(exc).replace(self.password, "[redacted]")
            raise RuntimeError(f"Odoo HTTP request failed: {message}") from exc
        if payload.get("error"):
            error = payload["error"]
            message = (error.get("data") or {}).get("message") or error.get("message") or "Odoo RPC failed"
            raise RuntimeError(str(message).replace(self.password, "[redacted]"))
        return payload

    def call(self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        scoped_kwargs = dict(kwargs or {})
        if self.company_id is not None:
            scoped_kwargs["context"] = {**scoped_kwargs.get("context", {}), "allowed_company_ids": [self.company_id]}
        payload = self._request("/web/dataset/call_kw", {
            "model": model, "method": method, "args": args, "kwargs": scoped_kwargs,
        })
        return payload.get("result")

    def bind_company(self, company_id: int) -> None:
        users = self.call("res.users", "read", [[self.uid]], {"fields": ["company_ids"]})
        if not users or company_id not in users[0]["company_ids"]:
            raise RuntimeError("Company is outside the authenticated user's scope")
        self.company_id = company_id

    def close(self) -> None:
        if not self.closed:
            self._request("/web/session/destroy", {})
            self.closed = True


def percentile(values: list[float], fraction: float) -> float | None:
    """Nearest-rank quantile: rank ceil(n * fraction), with no interpolation."""
    if not 0 < fraction <= 1:
        raise ValueError("Percentile fraction must be greater than zero and at most one")
    if not values:
        return None
    return sorted(values)[math.ceil(len(values) * fraction) - 1]


def summary(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "min_ms": round(min(values), 2) if values else None,
        "p50_ms": round(statistics.median(values), 2) if values else None,
        "p95_ms": round(percentile(values, .95), 2) if values else None,
        "max_ms": round(max(values), 2) if values else None,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--url", default=os.environ.get("ODOO_URL", "http://localhost:8069"))
    parser.add_argument("--database", required=True)
    parser.add_argument("--confirm-isolated-database", required=True, help="Repeat the disposable database name to acknowledge synthetic writes")
    parser.add_argument("--company-id", type=int, required=True)
    parser.add_argument("--login", default=os.environ.get("ODOO_LOGIN"))
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--min-samples", type=int, default=20, help="Minimum successful samples per enabled phase; 20 is only a directional small-sample check")
    parser.add_argument("--post", action="store_true", help="Post synthetic invoices; they remain in the isolated database")
    parser.add_argument("--target-save-ms", type=float, default=2000.0)
    parser.add_argument("--target-post-ms", type=float, default=2000.0)
    parser.add_argument("--output")
    supplied = sys.argv[1:] if argv is None else argv
    if any(value == "--password" or value.startswith("--password=") for value in supplied):
        parser.error("Use ODOO_PASSWORD; --password is not supported")
    args = parser.parse_args(supplied)
    if not ISOLATED_DATABASE.fullmatch(args.database) or args.confirm_isolated_database != args.database:
        parser.error("Synthetic transaction probes require an isolated tcsi_alignment_ database and matching --confirm-isolated-database")
    if min(args.iterations, args.workers, args.company_id, args.min_samples) <= 0:
        parser.error("--iterations, --workers, --company-id and --min-samples must be positive")
    if any(not math.isfinite(target) or target <= 0 for target in (args.target_save_ms, args.target_post_ms)):
        parser.error("Latency targets must be finite and positive")
    url = urllib.parse.urlsplit(args.url)
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.query or url.fragment:
        parser.error("--url must be an HTTP(S) base URL without credentials, query or fragment")
    args.password = os.environ.get("ODOO_PASSWORD")
    if not args.login or not args.password:
        parser.error("Set ODOO_LOGIN (or --login) and ODOO_PASSWORD; password arguments are not accepted")
    return args


def prepare_fixture(client: OdooHttp, company_id: int, run_id: str) -> dict[str, int]:
    """Resolve all company-scoped chart requirements before creating any fixture."""
    accounts = {}
    for kind in ("asset_receivable", "liability_payable", "income"):
        rows = client.call("account.account", "search_read", [[
            ("company_ids", "in", [company_id]), ("account_type", "=", kind), ("deprecated", "=", False),
        ]], {"fields": ["id"], "limit": 1, "order": "id"})
        if not rows:
            raise RuntimeError(f"No usable {kind} account in selected company")
        accounts[kind] = int(rows[0]["id"])
    journals = client.call("account.journal", "search_read", [[
        ("company_id", "=", company_id), ("type", "=", "sale"), ("active", "=", True),
    ]], {"fields": ["id"], "limit": 1, "order": "id"})
    if not journals:
        raise RuntimeError("No active sale journal in selected company")
    partner_id = client.call("res.partner", "create", [{
        "name": "Synthetic Performance Benchmark Partner", "ref": f"TC-BENCH-{company_id}-{run_id}",
        "company_id": company_id, "company_type": "company", "customer_rank": 1,
        "property_account_receivable_id": accounts["asset_receivable"],
        "property_account_payable_id": accounts["liability_payable"],
    }])
    return {"partner_id": int(partner_id), "income_id": accounts["income"], "journal_id": int(journals[0]["id"])}


def error_text(exc: Exception, password: str) -> str:
    return f"{type(exc).__name__}: {exc}".replace(password, "[redacted]")


def run_probe(args: argparse.Namespace, fixture: dict[str, int], iteration: int, run_id: str,
              client_factory: Callable[..., OdooHttp] = OdooHttp, submitted_at: float | None = None,
              timeline_origin: float | None = None) -> dict[str, Any]:
    worker_started = time.perf_counter()
    origin = worker_started if timeline_origin is None else timeline_origin
    reference = f"TC-BENCH-{run_id}-{iteration}"
    result: dict[str, Any] = {
        "reference": reference, "iteration": iteration, "create_ms": None, "post_ms": None,
        "error": None, "cleanup_errors": [], "rpc_intervals": [],
        "client_executor_wait_ms": (worker_started - submitted_at) * 1000 if submitted_at is not None else None,
        "authentication_scope_ms": None, "session_cleanup_ms": None,
    }
    client = None
    move_id = None

    def timed_call(phase: str, method: str, values: list[Any]) -> Any:
        started = time.perf_counter()
        succeeded = False
        try:
            response = client.call("account.move", method, values)
            succeeded = True
            return response
        finally:
            ended = time.perf_counter()
            result["rpc_intervals"].append({"phase": phase, "start_s": started - origin,
                                            "end_s": ended - origin, "succeeded": succeeded})
            if succeeded:
                result[f"{phase}_ms"] = (ended - started) * 1000

    try:
        client = client_factory(args.url, args.database, args.login, args.password)
        client.bind_company(args.company_id)
        result["authentication_scope_ms"] = (time.perf_counter() - worker_started) * 1000
        values = {
            "company_id": args.company_id, "move_type": "out_invoice", "partner_id": fixture["partner_id"],
            "journal_id": fixture["journal_id"], "invoice_date": date.today().isoformat(), "ref": reference,
            "invoice_line_ids": [[0, 0, {
                "name": "Synthetic performance probe", "quantity": 1, "price_unit": 1.0,
                "account_id": fixture["income_id"], "tax_ids": [[6, 0, []]],
            }]],
        }
        move_id = int(timed_call("create", "create", [values]))
        if args.post:
            timed_call("post", "action_post", [[move_id]])
        else:
            client.call("account.move", "unlink", [[move_id]])
            move_id = None
    except Exception as exc:
        result["error"] = error_text(exc, args.password)
        if client is not None and move_id is not None:
            try:
                rows = client.call("account.move", "read", [[move_id]], {"fields": ["state"]})
                if rows and rows[0]["state"] == "draft":
                    client.call("account.move", "unlink", [[move_id]])
            except Exception as cleanup_exc:
                result["cleanup_errors"].append(error_text(cleanup_exc, args.password))
    finally:
        if client is not None:
            cleanup_started = time.perf_counter()
            try:
                client.close()
            except Exception as cleanup_exc:
                result["cleanup_errors"].append(error_text(cleanup_exc, args.password))
            finally:
                result["session_cleanup_ms"] = (time.perf_counter() - cleanup_started) * 1000
        result["worker_total_ms"] = (time.perf_counter() - worker_started) * 1000
    return result


def peak_rpc_overlap(results: list[dict[str, Any]]) -> int:
    """Observed overlapping client RPC intervals; never server queue depth."""
    events = []
    for item in results:
        for interval in item.get("rpc_intervals", []):
            if interval["end_s"] > interval["start_s"]:
                events.extend(((interval["start_s"], 1), (interval["end_s"], -1)))
    active = peak = 0
    for _, delta in sorted(events):  # End before start at the same instant.
        active += delta
        peak = max(peak, active)
    return peak


def build_report(args: argparse.Namespace, results: list[dict[str, Any]], errors: list[str]) -> dict[str, Any]:
    saves = [item["create_ms"] for item in results if item["create_ms"] is not None]
    posts = [item["post_ms"] for item in results if item["post_ms"] is not None]
    failures = [item for item in results if item["error"] or item["cleanup_errors"]]
    target_observed = {
        "save_p95_within_target": bool(saves) and percentile(saves, .95) < args.target_save_ms,
        "post_p95_within_target": bool(posts) and percentile(posts, .95) < args.target_post_ms if args.post else None,
    }
    sufficient = len(saves) >= args.min_samples and (not args.post or len(posts) >= args.min_samples)
    if errors or failures:
        status, exit_code = "EXECUTION_FAILED", 1
    elif len(results) != args.iterations or not sufficient:
        status, exit_code = "INSUFFICIENT_SAMPLES", 3
    elif not target_observed["save_p95_within_target"] or (args.post and not target_observed["post_p95_within_target"]):
        status, exit_code = "TARGET_MISSED", 2
    else:
        status, exit_code = "TARGET_OBSERVED", 0
    return {
        "status": status, "exit_code": exit_code, "accepted": exit_code == 0, "synthetic": True,
        "database": args.database, "company_id": args.company_id, "workers": args.workers,
        "iterations": args.iterations, "attempted_iterations": len(results), "failed_iterations": len(failures),
        "failure_rate": len(failures) / len(results) if results else None, "post_enabled": args.post,
        "targets_ms": {"save": args.target_save_ms, "post": args.target_post_ms}, "target_comparison": "strictly less than",
        "save": summary(saves), "post": summary(posts), "target_observed": target_observed,
        "percentile_method": "nearest rank: ceil(n * 0.95)", "minimum_samples": args.min_samples,
        "sufficient_samples": sufficient, "errors": errors, "failed_probes": failures,
        "samples": sorted(results, key=lambda item: item.get("iteration", 0)),
        "client_executor_wait": summary([item["client_executor_wait_ms"] for item in results if item.get("client_executor_wait_ms") is not None]),
        "maximum_simultaneous_save_post_calls": peak_rpc_overlap(results),
        "server_queue_measurement": None,
        "timeline_scope": "RPC intervals are seconds from this run's monotonic origin. Executor wait is local client backlog, excluded from save/post latency. RPC latency includes transport, server admission and execution; their individual contributions are not measured.",
        "measurement_scope": "Per-call invoice create/post RPC, one authenticated account across independent sessions; authentication, fixture setup and cleanup excluded from timings but contribute concurrent server load. Cold/warm calls are not separated.",
        "note": "Synthetic isolated timing only. A 20-sample p95 is directional; agree larger samples and representative annual volume. No browser/network path, role-mix or client acceptance is implied.",
    }


def run_benchmark(args: argparse.Namespace, client_factory: Callable[..., OdooHttp] = OdooHttp) -> dict[str, Any]:
    run_id = uuid.uuid4().hex[:12]
    started_at = datetime.now(timezone.utc).isoformat()
    timeline_origin = time.perf_counter()
    setup = None
    errors: list[str] = []
    results: list[dict[str, Any]] = []
    fixture = None
    try:
        setup = client_factory(args.url, args.database, args.login, args.password)
        setup.bind_company(args.company_id)
        fixture = prepare_fixture(setup, args.company_id, run_id)
    except Exception as exc:
        errors.append(error_text(exc, args.password))
    finally:
        if setup is not None:
            try:
                setup.close()
            except Exception as exc:
                errors.append("Setup session teardown: " + error_text(exc, args.password))
    if not errors and fixture:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [executor.submit(run_probe, args, fixture, index, run_id, client_factory,
                                       time.perf_counter(), timeline_origin) for index in range(args.iterations)]
            for future in as_completed(futures):
                results.append(future.result())
    return {**build_report(args, results, errors), "run_id": run_id, "actor_uid": setup.uid if setup is not None else None,
            "started_at": started_at, "completed_at": datetime.now(timezone.utc).isoformat()}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_benchmark(args)
    serialized = json.dumps(result, indent=2, sort_keys=True)
    print(serialized)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(serialized + "\n")
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
