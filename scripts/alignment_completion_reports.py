"""Synthetic .13 ledger/report proof, run via odoo shell on an isolated fixture."""
import base64
import hashlib
import json
import time
from pathlib import Path

from odoo import api, Command

assert env.cr.dbname.startswith("tcsi_alignment_")
company = env.ref("base.main_company")
env = api.Environment(env.cr, env.ref("base.user_admin").id, {"allowed_company_ids": company.ids})
company = env["res.company"].browse(company.id)
output = Path("/tmp/alignment-completion-reports")
output.mkdir(exist_ok=True)
env["ir.config_parameter"].sudo().set_param("report.url", "http://127.0.0.1:8069")
partner = env["res.partner"].search([("ref", "=", "TC-ALIGNMENT-PARTNER")], limit=1)
sale = env["account.journal"].search([("code", "=", "QAS"), ("company_id", "=", company.id)], limit=1)
general = env["account.journal"].search([("code", "=", "QAJ"), ("company_id", "=", company.id)], limit=1)
bank = env["account.journal"].search([("code", "=", "QAB"), ("company_id", "=", company.id)], limit=1)
assert partner and sale and bank and general
taxes = env["account.tax"].create([
    {"name": "Synthetic VAT 12", "amount": 12, "type_tax_use": "sale", "company_id": company.id, "thirdcode_summary_kind": "vat"},
    {"name": "Synthetic withholding 2", "amount": -2, "type_tax_use": "sale", "company_id": company.id, "thirdcode_summary_kind": "withholding"},
])
invoice = env["account.move"].create({"company_id": company.id, "journal_id": sale.id, "partner_id": partner.id,
    "move_type": "out_invoice", "invoice_date": "2027-01-15", "date": "2027-01-15", "ref": "Synthetic tax report evidence",
    "invoice_line_ids": [Command.create({"name": "Synthetic taxable service", "account_id": sale.default_account_id.id,
        "price_unit": 100, "tax_ids": [Command.set(taxes.ids)]})]})
invoice.action_post()
bank.suspense_account_id.reconcile = True
outstanding = env["account.account"].create({"name": "Synthetic deposit clearing", "code": "QADEP13", "account_type": "asset_current",
    "reconcile": True, "company_ids": [Command.set(company.ids)]})
receipt = env["account.move"].create({"company_id": company.id, "journal_id": general.id, "date": "2027-01-15", "ref": "Synthetic receipt pending bank deposit",
    "line_ids": [Command.create({"account_id": outstanding.id, "debit": 75}), Command.create({"account_id": sale.default_account_id.id, "credit": 75})]})
receipt.action_post()
statement = env["account.bank.statement.line"].create({"journal_id": bank.id, "date": "2027-01-15", "amount": 50, "payment_ref": "Synthetic bank deposit"})
target = receipt.line_ids.filtered(lambda line: line.account_id == outstanding)
original = [(line.id, line.account_id.id, line.balance) for line in statement.move_id.line_ids]
match = statement.action_match_thirdcode_items([{"line_id": target.id, "amount": 50}], general.id, "2027-01-15")
assert original == [(line.id, line.account_id.id, line.balance) for line in statement.move_id.line_ids]
assert target.amount_residual == 25 and statement.is_reconciled
review = env["thirdcode.bank.reconciliation"].create({"name": "Synthetic January 2027 review", "company_id": company.id, "journal_id": bank.id,
    "statement_reference": "SYNTHETIC-JAN-2027", "date_start": "2027-01-01", "date_end": "2027-01-31", "closing_balance": 0,
    "evidence_file": base64.b64encode(b"Synthetic statement evidence; not client approval"), "evidence_filename": "synthetic-bank.txt",
    "definition": "Synthetic verification only; client monthly report remains undefined"})
statement.thirdcode_reconciliation_id = review.id
review.action_compute_ledger_balance()
review.closing_balance = review.ledger_balance
review.action_reconcile()
results = {"scope": "Synthetic USD data; tax rates and review are test inputs, not client decisions", "statement": {
    "original_entry_unchanged": True, "matched": statement.is_reconciled, "outstanding_residual": target.amount_residual,
    "adjustment_move_id": match, "bank_difference": review.difference}}

def render(key, action, record, calculation):
    start = time.monotonic()
    pdf, _ = env["ir.actions.report"]._render_qweb_pdf(action, record.ids)
    assert pdf.startswith(b"%PDF")
    (output / (key + ".pdf")).write_bytes(pdf)
    results[key] = {"calculation": calculation, "seconds": round(time.monotonic() - start, 3),
                    "bytes": len(pdf), "sha256": hashlib.sha256(pdf).hexdigest()}

for kind, total in (("vat", "12.00"), ("withholding", "-2.00")):
    wizard = env["thirdcode.tax.summary.wizard"].create({"company_id": company.id, "date_from": "2027-01-01", "date_to": "2027-01-31", "summary_kind": kind})
    data = wizard.get_report_data()
    assert data["tax_total"] == total and data["rows"][0]["base"] == "100.00"
    render(kind, "thirdcode_accounting.action_report_thirdcode_tax_summary", wizard, data)
render("bank_summary", "thirdcode_accounting.action_report_thirdcode_bank_summary", review,
       {"closing_book_balance": review.ledger_balance, "statement_closing": review.closing_balance, "difference": review.difference})
for kind in ("balance_sheet", "profit_loss", "cash_flow"):
    wizard = env["thirdcode.financial.report.wizard"].create({"company_id": company.id, "report_type": kind,
        "date_from": "2025-01-01", "date_to": "2025-12-31", "comparison_date_from": "2024-01-01", "comparison_date_to": "2024-12-31"})
    render(kind, "thirdcode_accounting.action_report_thirdcode_financial_statement", wizard, wizard.get_report_data())
(output / "results.json").write_text(json.dumps(results, indent=2, default=str) + "\n")
env.cr.commit()
print("COMPLETION_REPORTS " + json.dumps(results, default=str))
