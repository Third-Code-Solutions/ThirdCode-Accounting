"""Measure annual statements on an explicitly isolated Odoo database.

Run with the deployed Odoo Python environment and its isolated configuration.
Defaults to existing ledger data, with transient report writes rolled back. An
explicit --seed-documents adds native synthetic invoices, bills and settlements;
no chart, permission, lock-date or audit configuration is changed. This is an
engineering scenario, not an approved client annual volume or browser benchmark.
"""
from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit
import uuid

DATABASE = re.compile(r"tcsi_alignment_[A-Za-z0-9_]+\Z")
KINDS = ("balance_sheet", "profit_loss", "cash_flow")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def plan_documents(year, documents, settle_every):
    """Each pair covers one month: customer invoice then supplier bill."""
    return [{"index": i, "date": date(year, (i // 2) % 12 + 1, 15).isoformat(),
             "move_type": "out_invoice" if i % 2 == 0 else "in_invoice",
             "settle": i % settle_every == 0} for i in range(documents)]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--config", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--confirm-isolated-database", required=True)
    parser.add_argument("--company-id", required=True, type=int)
    parser.add_argument("--actor-id", required=True, type=int)
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--seed-documents", type=int, default=0, help="0 reads existing ledger; 24 is a small full-year synthetic smoke")
    parser.add_argument("--settle-every", type=int, default=3)
    parser.add_argument("--max-seed-seconds", type=float, default=180)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--render-pdf", action="store_true", help="Requires an independently guarded isolated loopback Odoo server for assets")
    parser.add_argument("--report-url", help="Exact independently verified isolated loopback asset URL, required for PDF")
    parser.add_argument("--target-seconds", type=float, default=30)
    parser.add_argument("--output-directory", required=True, help="New private directory; never reuse prior evidence")
    args = parser.parse_args(argv)
    if not DATABASE.fullmatch(args.database) or args.confirm_isolated_database != args.database:
        parser.error("An isolated tcsi_alignment_ database and exact confirmation are required")
    if args.company_id < 1 or args.actor_id <= 1:
        parser.error("Use a valid company and a non-superuser actor ID greater than 1")
    if not 1900 <= args.year <= 9998 or args.seed_documents < 0 or 0 < args.seed_documents < 24:
        parser.error("Year must be 1900..9998; seed documents must be 0 or at least 24")
    if args.settle_every < 1 or args.repeats < 2:
        parser.error("Settlement interval must be positive; use at least two repetitions")
    if args.render_pdf:
        parsed = urlsplit(args.report_url or "")
        if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost") or
                parsed.port is None or parsed.username or parsed.password or parsed.query or parsed.fragment):
            parser.error("PDF requires --report-url pointing to an independently verified isolated loopback port")
    import math
    if any(not math.isfinite(n) or n <= 0 for n in (args.target_seconds, args.max_seed_seconds)):
        parser.error("Targets and seed time budget must be finite and positive")
    return args


def validate_environment(env, args):
    require(env.cr.dbname == args.database and DATABASE.fullmatch(env.cr.dbname), "Native database identity mismatch")
    require(env.uid == args.actor_id and env.uid != 1 and not env.su, "Use the configured non-superuser actor without sudo")
    require(args.company_id in env.user.company_ids.ids and env.company.id == args.company_id and
            env.companies.ids == [args.company_id], "Actor/active company scope mismatch")
    # These are read-only checks. Never switch controls off to make a benchmark run.
    require(not env["ir.cron"].search_count([("active", "=", True)]), "Isolated cron is still active")
    require(not env["ir.mail_server"].search_count([("active", "=", True)]), "Isolated outbound mail is still active")
    if args.render_pdf:
        report_url = env["ir.config_parameter"].get_param("report.url")
        parsed = urlsplit(report_url or "")
        require(report_url == args.report_url and parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost") and
                parsed.port is not None and not parsed.username and not parsed.password,
                "PDF assets need an independently guarded isolated loopback report.url")


def fixture(env, args, run_id):
    accounts = {}
    for kind in ("asset_receivable", "liability_payable", "income", "expense"):
        accounts[kind] = env["account.account"].search([
            ("company_ids", "in", [args.company_id]), ("account_type", "=", kind), ("deprecated", "=", False),
        ], order="id", limit=1)
        require(accounts[kind], f"No usable company-scoped {kind} account")
    journals = {}
    for kind in ("sale", "purchase"):
        journals[kind] = env["account.journal"].search([
            ("company_id", "=", args.company_id), ("type", "=", kind), ("active", "=", True),
        ], order="id", limit=1)
        require(journals[kind], f"No active company-scoped {kind} journal")
    bank = inbound = outbound = None
    for candidate in env["account.journal"].search([
        ("company_id", "=", args.company_id), ("type", "=", "bank"), ("active", "=", True),
    ], order="id"):
        incoming = candidate.inbound_payment_method_line_ids.filtered(lambda line: line.payment_account_id)[:1]
        outgoing = candidate.outbound_payment_method_line_ids.filtered(lambda line: line.payment_account_id)[:1]
        if incoming and outgoing:
            bank, inbound, outbound = candidate, incoming, outgoing
            break
    require(bank, "No company bank journal with configured incoming/outgoing payment accounts")
    partner = env["res.partner"].create({
        "name": "Synthetic annual capacity customer and supplier", "ref": f"TC-ANNUAL-{run_id}",
        "company_id": args.company_id, "customer_rank": 1, "supplier_rank": 1,
        "property_account_receivable_id": accounts["asset_receivable"].id,
        "property_account_payable_id": accounts["liability_payable"].id,
    })
    return accounts, journals, bank, inbound, outbound, partner


def seed(env, args, run_id):
    started = time.perf_counter()
    accounts, journals, bank, inbound, outbound, partner = fixture(env, args, run_id)
    move_ids, payment_ids = [], []
    for item in plan_documents(args.year, args.seed_documents, args.settle_every):
        require(time.perf_counter() - started < args.max_seed_seconds, "Seed budget exceeded; entire uncommitted scenario will roll back")
        sale = item["move_type"] == "out_invoice"
        move = env["account.move"].create({
            "company_id": args.company_id, "move_type": item["move_type"], "partner_id": partner.id,
            "journal_id": journals["sale" if sale else "purchase"].id,
            "invoice_date": item["date"], "date": item["date"], "ref": f"TC-ANNUAL-{run_id}-{item['index']}",
            "invoice_line_ids": [(0, 0, {"name": "Synthetic annual capacity line", "quantity": 1, "price_unit": 100,
                "account_id": accounts["income" if sale else "expense"].id, "tax_ids": [(6, 0, [])]})],
        })
        move.action_post()
        require(move.state == "posted" and move.company_id.id == args.company_id, "Native scenario document did not post in scope")
        require(move.date.isoformat() == item["date"], "Native accounting date shifted outside the planned scenario; review period locks")
        move_ids.append(move.id)
        if item["settle"]:
            register = env["account.payment.register"].with_context(active_model="account.move", active_ids=move.ids).create({
                "journal_id": bank.id, "payment_date": item["date"], "amount": move.amount_residual,
                "payment_method_line_id": (inbound if sale else outbound).id,
            })
            action = register.action_create_payments()
            require(isinstance(action, dict) and action.get("res_model") == "account.payment", "Native payment register returned no payment action")
            if action.get("res_id"):
                payments = env["account.payment"].browse(action["res_id"]).exists()
            else:
                require(action.get("domain"), "Native payment action omitted payment scope")
                payments = env["account.payment"].search(action["domain"])
            require(len(payments) == 1, "Expected one native payment per selected scenario document")
            require(payments and all(p.company_id.id == args.company_id for p in payments), "Native settlement escaped company scope")
            require(move.currency_id.is_zero(move.amount_residual), "Native settlement left an unexpected open balance")
            payment_ids.extend(payments.ids)
        if len(move_ids) % 12 == 0:
            print(f"ANNUAL_SEED documents={len(move_ids)} payments={len(payment_ids)}", flush=True)
    require(time.perf_counter() - started <= args.max_seed_seconds, "Seed budget exceeded; scenario will roll back")
    payments = env["account.payment"].browse(payment_ids)
    all_moves = env["account.move"].browse(move_ids) | payments.move_id
    require(all(m.state == "posted" for m in all_moves), "Unposted scenario payment entry")
    return {"documents": len(move_ids), "payments": len(payment_ids), "posted_moves": len(all_moves),
            "posted_lines": len(all_moves.line_ids), "months": 12, "partner_id": partner.id,
            "elapsed_seconds": time.perf_counter() - started, "run_id": run_id}


def cardinality(env, args):
    company = [("company_id", "=", args.company_id)]
    period = [("date", ">=", f"{args.year}-01-01"), ("date", "<=", f"{args.year}-12-31")]
    posted = company + [("state", "=", "posted")]
    oldest = env["account.move"].search(posted, order="date,id", limit=1)
    newest = env["account.move"].search(posted, order="date desc,id desc", limit=1)
    attachment_totals = env["ir.attachment"]._read_group(company, [], ["file_size:sum"])
    return {
        "year_posted_documents": env["account.move"].search_count(posted + period),
        "year_posted_lines": env["account.move.line"].search_count(company + [("parent_state", "=", "posted")] + period),
        "all_history_posted_documents": env["account.move"].search_count(posted),
        "all_history_posted_lines": env["account.move.line"].search_count(company + [("parent_state", "=", "posted")]),
        "company_attachments": env["ir.attachment"].search_count(company),
        "company_attachment_bytes": attachment_totals[0][0] if attachment_totals else 0,
        "oldest_posted_date": str(oldest.date) if oldest else None,
        "newest_posted_date": str(newest.date) if newest else None,
    }


def measure_reports(env, args, output, evidence=None, checkpoint=lambda: None):
    evidence = evidence if evidence is not None else []
    hashes = {}
    for repeat in range(args.repeats):
        for kind in KINDS:
            wizard = env["thirdcode.financial.report.wizard"].create({
                "company_id": args.company_id, "report_type": kind, "date_from": f"{args.year}-01-01",
                "date_to": f"{args.year}-12-31", "target_move": "posted",
            })
            started = time.perf_counter()
            data = wizard.get_report_data()
            calculation = time.perf_counter() - started
            calculated_hash = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
            require(kind not in hashes or hashes[kind] == calculated_hash, "Report calculation changed between repeated samples")
            hashes[kind] = calculated_hash
            if kind == "balance_sheet":
                require(data["balanced"], "Annual balance sheet does not balance")
            if kind == "cash_flow":
                require(Decimal(data["cash_reconciliation_difference"].replace(",", "")) == 0, "Cash flow does not reconcile")
            sample = {"report": kind, "repeat": repeat, "cache": "first report call in process" if repeat == 0 else "same-process subsequent call",
                      "calculation_seconds": calculation, "calculation_sha256": calculated_hash,
                      "pdf_seconds": None, "pdf_bytes": None}
            if args.render_pdf:
                started = time.perf_counter()
                pdf, _ = env["ir.actions.report"]._render_qweb_pdf("thirdcode_accounting.action_report_thirdcode_financial_statement", wizard.ids)
                sample["pdf_seconds"] = time.perf_counter() - started
                require(pdf.startswith(b"%PDF"), "Native report did not return a PDF")
                path = output / f"{kind}-{repeat}.pdf"
                path.write_bytes(pdf)
                sample.update(pdf_bytes=len(pdf), pdf_sha256=hashlib.sha256(pdf).hexdigest())
            evidence.append(sample)
            checkpoint()
            print(f"ANNUAL_REPORT {kind} repeat={repeat} calculation={calculation:.3f} pdf={sample['pdf_seconds']}", flush=True)
    return evidence


def report_status(samples, target):
    if not samples or any(s["pdf_seconds"] is None for s in samples):
        return "CALCULATION_ONLY", 3
    if any(s["pdf_seconds"] >= target for s in samples):
        return "ENGINEERING_TARGET_MISSED", 2
    return "ENGINEERING_TARGET_OBSERVED", 0


def main(argv=None):
    args = parse_args(argv)
    os.umask(0o077)
    output = Path(args.output_directory)
    output.mkdir(mode=0o700)  # Prior evidence must remain intact.
    result = {"database": args.database, "company_id": args.company_id, "actor_id": args.actor_id, "year": args.year,
              "scenario": "Explicit synthetic engineering workload" if args.seed_documents else "Existing isolated ledger",
              "workload_qualification": "Small smoke only" if args.seed_documents == 24 else "Unapproved engineering volume; inspect actual cardinality",
              "seed_requested_documents": args.seed_documents, "settle_every": args.settle_every,
              "max_seed_seconds": args.max_seed_seconds, "seed_attachment_files": 0,
              "approved_client_volume": False, "acceptance_claim": False, "target_seconds": args.target_seconds,
              "boundary": "Native statement calculation and optional server PDF rendering, excluding browser/network. PDF rendering recalculates the report; do not add calculation_seconds to pdf_seconds.",
              "cache_boundary": "First and subsequent calls in one process; OS/PostgreSQL caches are not cleared. Not cold-start evidence.",
              "seeded": None, "samples": [], "status": "FAILED", "exit_code": 1}
    secrets = [v for k, v in os.environ.items() if v and any(s in k.upper() for s in ("PASSWORD", "TOKEN", "SECRET", "KEY"))]
    def checkpoint():
        temporary = output / "results.json.tmp"
        temporary.write_text(json.dumps(result, indent=2, default=str) + "\n")
        os.replace(temporary, output / "results.json")
    try:
        import configparser
        config = configparser.ConfigParser(interpolation=None)
        require(config.read(args.config) == [args.config], "Isolated configuration missing")
        secrets.extend(v for k, v in config["options"].items() if v and "password" in k)
        require(config["options"].get("db_name") == args.database and config["options"].get("dbfilter") == f"^{args.database}$",
                "Config database/filter mismatch")
        import odoo
        from odoo import api
        odoo.tools.config.parse_config(["-c", args.config, "-d", args.database, "--no-http", "--max-cron-threads", "0"])
        registry = odoo.registry(args.database)
        with registry.cursor() as cursor:
            env = api.Environment(cursor, args.actor_id, {"allowed_company_ids": [args.company_id]})
            validate_environment(env, args)
            result["module_version"] = env["ir.module.module"].search([("name", "=", "thirdcode_accounting")], limit=1).latest_version
            result["company_currency"] = env.company.currency_id.name
            result["before"] = cardinality(env, args)
            if args.seed_documents:
                result["seeded"] = seed(env, args, uuid.uuid4().hex[:12])
                cursor.commit()
                result["seed_committed"] = True
                checkpoint()
            result["measured_cardinality"] = cardinality(env, args)
            measure_reports(env, args, output, result["samples"], checkpoint)
            result["status"], result["exit_code"] = report_status(result["samples"], args.target_seconds)
            cursor.rollback()  # Transient report models are not part of the scenario.
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        for secret in secrets:
            message = message.replace(secret, "[redacted]")
        result["error"] = message
    finally:
        checkpoint()
    print("ANNUAL_RESULT", result["status"], str(output / "results.json"), flush=True)
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
