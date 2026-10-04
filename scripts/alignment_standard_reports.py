"""Render actual OCA outputs in a disposable alignment database via odoo shell."""
import hashlib
import json
from pathlib import Path

assert env.cr.dbname.startswith("tcsi_alignment_")
company = env.ref("base.main_company")
env["ir.config_parameter"].sudo().set_param("report.url", "http://127.0.0.1:8069")
env.cr.commit()
output = Path("/tmp/alignment-standard-reports")
output.mkdir(exist_ok=True)
results = {}
for key, model, report, values in [
    ("trial_balance", "trial.balance.report.wizard", "account_financial_report.trial_balance", {"date_from": "2025-01-01", "date_to": "2025-12-31", "target_move": "posted"}),
    ("general_ledger", "general.ledger.report.wizard", "account_financial_report.general_ledger", {"date_from": "2025-01-01", "date_to": "2025-12-31", "target_move": "posted"}),
    ("journal_listing", "journal.ledger.report.wizard", "account_financial_report.journal_ledger", {"date_from": "2025-01-01", "date_to": "2026-12-31"}),
    ("customer_ageing", "aged.partner.balance.report.wizard", "account_financial_report.aged_partner_balance", {"date_at": "2026-12-31", "account_ids": [(6, 0, env["account.account"].search([("company_ids", "in", company.ids), ("account_type", "=", "asset_receivable")]).ids)]}),
    ("supplier_ageing", "aged.partner.balance.report.wizard", "account_financial_report.aged_partner_balance", {"date_at": "2026-12-31", "account_ids": [(6, 0, env["account.account"].search([("company_ids", "in", company.ids), ("account_type", "=", "liability_payable")]).ids)]}),
    ("unpaid_balances", "open.items.report.wizard", "account_financial_report.open_items", {"date_at": "2026-12-31"}),
    ("vat_summary", "vat.report.wizard", "account_financial_report.vat_report", {"date_from": "2025-01-01", "date_to": "2026-12-31"}),
]:
    with env.cr.savepoint():
        wizard = env[model].create(dict(values, company_id=company.id))
        action = wizard._print_report("qweb-pdf")
        pdf, _ = env["ir.actions.report"]._render_qweb_pdf(report, wizard.ids, data=json.loads(json.dumps(action.get("data"), default=str)))
        assert pdf.startswith(b"%PDF")
        (output / (key + ".pdf")).write_bytes(pdf)
        results[key] = {"report": report, "bytes": len(pdf), "sha256": hashlib.sha256(pdf).hexdigest(),
                        "scope": "Synthetic rendered output; not accountant-approved Philippine tax computation"}
partner = env["res.partner"].search([("ref", "=", "TC-ALIGNMENT-PARTNER")], limit=1)
assert partner
wizard = env["activity.statement.wizard"].with_context(active_ids=partner.ids).create({
    "company_id": company.id, "date_start": "2025-07-01", "date_end": "2025-12-31", "show_aging_buckets": True,
    "filter_partners_non_due": False, "filter_negative_balances": False})
data = json.loads(json.dumps(wizard._prepare_statement(), default=str))
calculation = env["report.partner_statement.activity_statement"]._get_report_values(partner.ids, data)["data"][partner.id]["currencies"][company.currency_id.id]
assert calculation["balance_forward"] == 600 and calculation["amount_due"] == 1050
assert calculation["lines"][-1]["thirdcode_running_balance"] == 1050
pdf, _ = env["ir.actions.report"]._render_qweb_pdf("partner_statement.activity_statement", partner.ids, data=data)
assert pdf.startswith(b"%PDF")
(output / "soa.pdf").write_bytes(pdf)
results["soa"] = {"report": "partner_statement.activity_statement", "bytes": len(pdf), "sha256": hashlib.sha256(pdf).hexdigest(),
    "opening": calculation["balance_forward"], "closing": calculation["amount_due"], "running_balances": [row["thirdcode_running_balance"] for row in calculation["lines"]],
    "ageing": calculation["buckets"], "scope": "Synthetic customer; provisional layout pending approved client sample"}
(output / "standard-reports.json").write_text(json.dumps(results, indent=2))
print("STANDARD_REPORTS " + json.dumps(results))
env.cr.commit()
