"""Synthetic fixture and evidence, executed via `odoo shell` in a tcsi_alignment_ DB.

No customer database is accepted. See docs/prd-alignment-2026-10-05/REPORT.md.
"""
import base64
import hashlib
import json
import os
import time
from datetime import date
from pathlib import Path

from odoo import Command, fields

if not env.cr.dbname.startswith("tcsi_alignment_"):
    raise RuntimeError("Refusing synthetic operations outside tcsi_alignment_ databases")

mode = os.environ.get("ALIGNMENT_MODE", "snapshot")
company = env.ref("base.main_company")
admin = env.ref("base.user_admin")
if mode == "seed":
    admin.write({"groups_id": [Command.link(env.ref("thirdcode_accounting.group_thirdcode_administrator").id)]})
    company.write({"thirdcode_trial_mode": True})
    accounts = {}
    for code, name, kind in [
        ("101000", "QA Cash", "asset_cash"), ("121000", "QA Receivable", "asset_receivable"),
        ("211000", "QA Payable", "liability_payable"), ("300000", "QA Retained earnings", "equity"),
        ("400000", "QA Revenue", "income"), ("500000", "QA Expense", "expense"),
    ]:
        accounts[code] = env["account.account"].search([("company_ids", "in", company.ids), ("code", "=", code)], limit=1) or env["account.account"].create({
            "code": code, "name": name, "account_type": kind, "company_ids": [Command.set(company.ids)],
            "reconcile": kind in {"asset_receivable", "liability_payable"},
            "thirdcode_cash_flow_category": "operating" if kind != "asset_cash" else False,
        })
    for code, account in accounts.items():
        account.write({"thirdcode_cash_equivalent": code == "101000", "thirdcode_cash_flow_category": "operating" if code != "101000" else False})
    journals = {}
    for code, name, kind, default in [("QAS", "QA Sales", "sale", "400000"), ("QAP", "QA Purchases", "purchase", "500000"),
                                        ("QAB", "QA Bank", "bank", "101000"), ("QAJ", "QA Journal", "general", None)]:
        journals[kind] = env["account.journal"].search([("company_id", "=", company.id), ("code", "=", code)], limit=1) or env["account.journal"].create({
            "name": name, "code": code, "type": kind, "company_id": company.id,
            "default_account_id": accounts[default].id if default else False,
        })
    for method in journals["bank"].inbound_payment_method_line_ids | journals["bank"].outbound_payment_method_line_ids:
        method.payment_account_id = accounts["101000"]
    partner = env["res.partner"].search([("ref", "=", "TC-ALIGNMENT-PARTNER")], limit=1) or env["res.partner"].create({
        "name": "Synthetic alignment customer/supplier", "ref": "TC-ALIGNMENT-PARTNER", "company_id": company.id,
        "property_account_receivable_id": accounts["121000"].id, "property_account_payable_id": accounts["211000"].id,
    })
    invoices = env["account.move"]
    for month in range(1, 13):
        ref = f"TC-ALIGNMENT-2025-{month:02}"
        move = env["account.move"].search([("ref", "=", ref)], limit=1)
        if not move:
            move = env["account.move"].create({
                "company_id": company.id, "journal_id": journals["sale"].id, "move_type": "out_invoice",
                "partner_id": partner.id, "invoice_date": date(2025, month, 1), "date": date(2025, month, 1), "ref": ref,
                "narration": "Synthetic recovery and report evidence, not customer books",
                "invoice_line_ids": [Command.create({"name": ref, "quantity": 1, "price_unit": 100,
                    "account_id": accounts["400000"].id, "tax_ids": [Command.clear()]})],
            })
            move.action_post()
        invoices |= move
    if not env["ir.attachment"].search([("name", "=", "alignment-recovery-proof.txt")]):
        env["ir.attachment"].create({"name": "alignment-recovery-proof.txt", "res_model": "account.move", "res_id": invoices[0].id,
            "datas": base64.b64encode(b"TCSI synthetic attachment retained through isolated restore\n"), "mimetype": "text/plain"})
    if not env["account.payment"].search([("partner_id", "=", partner.id), ("journal_id", "=", journals["bank"].id)]):
        env["account.payment.register"].with_context(active_model="account.move", active_ids=invoices[:2].ids).create({
            "journal_id": journals["bank"].id, "payment_date": date(2025, 12, 15), "amount": 150,
            "group_payment": True,
        }).action_create_payments()
    env.cr.commit()

if mode == "reports":
    output = Path("/tmp/alignment-reports")
    output.mkdir(exist_ok=True)
    evidence = {}
    for report_type in ("balance_sheet", "profit_loss", "cash_flow"):
        wizard = env["thirdcode.financial.report.wizard"].with_user(admin).create({
            "report_type": report_type, "company_id": company.id, "date_from": "2025-01-01", "date_to": "2025-12-31",
            "comparison_date_from": "2024-01-01", "comparison_date_to": "2024-12-31",
        })
        start = time.monotonic()
        data = wizard.get_report_data()
        pdf, _ = env["ir.actions.report"].with_user(admin)._render_qweb_pdf("thirdcode_accounting.action_report_thirdcode_financial_statement", wizard.ids)
        elapsed = time.monotonic() - start
        assert pdf.startswith(b"%PDF"), "Expected an actual PDF"
        (output / (report_type + ".pdf")).write_bytes(pdf)
        evidence[report_type] = {"calculation": data, "render_seconds": round(elapsed, 3), "pdf_bytes": len(pdf), "sha256": hashlib.sha256(pdf).hexdigest()}
    (output / "report-evidence.json").write_text(json.dumps(evidence, default=str, indent=2))
    env.cr.commit()
    print("ALIGNMENT_REPORTS " + json.dumps({key: {"render_seconds": item["render_seconds"], "pdf_bytes": item["pdf_bytes"]} for key, item in evidence.items()}))
else:
    balances = {}
    for line in env["account.move.line"].search([("company_id", "=", company.id), ("parent_state", "=", "posted")]):
        balances[line.account_id.code] = round(balances.get(line.account_id.code, 0) + line.balance, 2)
    attachments = []
    for attachment in env["ir.attachment"].search([("res_model", "=", "account.move")]):
        blob = base64.b64decode(attachment.datas or b"")
        attachments.append({"name": attachment.name, "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()})
    audits = env["auditlog.log"].search([])
    audit_lines = env["auditlog.log.line"].search([])
    audit_content = [(item.model_model, item.res_id, item.user_id.id, str(item.create_date), item.method) for item in audits.sorted("id")]
    detail_content = [(item.log_id.id, item.field_name, item.old_value, item.new_value) for item in audit_lines.sorted("id")]
    snapshot = {"dataset": "Isolated synthetic fixture; not a production backup", "balances": balances,
                "posted_moves": env["account.move"].search_count([("state", "=", "posted")]),
                "attachments": sorted(attachments, key=lambda item: item["name"]), "audit_count": len(audits), "audit_line_count": len(audit_lines),
                "audit_sha256": hashlib.sha256(json.dumps([audit_content, detail_content], sort_keys=True).encode()).hexdigest()}
    print("ALIGNMENT_SNAPSHOT " + json.dumps(snapshot, sort_keys=True))
