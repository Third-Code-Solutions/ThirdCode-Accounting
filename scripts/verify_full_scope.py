#!/usr/bin/env python3
"""Exercise the implementable PRD slices through Odoo's supported RPC API.

This deliberately uses synthetic records with stable ``TC-FULL`` identifiers.
It proves behavior and idempotency; it is not client acceptance or a MYOB
cutover test.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import xmlrpc.client
from decimal import Decimal
from typing import Any, Callable

from verify_milestone1 import (
    Odoo,
    TODAY,
    account_by_code,
    ensure_partner,
    ensure_role_users,
    journal_by_type,
    money,
    required_row,
    reverse_posted_move,
)


def expect_error(action: Callable[[], Any], label: str) -> str:
    try:
        action()
    except Exception as exc:  # XML-RPC wraps server exceptions in Fault.
        message = str(exc)
        if not message:
            raise RuntimeError(f"{label} failed without an error message") from exc
        return message
    raise RuntimeError(f"{label} unexpectedly succeeded")


def first_or_none(odoo: Odoo, model: str, domain: list[Any], fields: list[str]) -> dict[str, Any] | None:
    return odoo.first(model, domain, fields)


def ensure_period(odoo: Odoo, company_id: int, admin: Odoo) -> tuple[int, bool]:
    fields = ["id", "name", "state", "date_start", "date_end"]
    row = first_or_none(
        odoo,
        "thirdcode.accounting.period",
        [("name", "=", "TC-FULL-CLOSED-2026")],
        fields,
    )
    if not row:
        period_id = int(
            admin.call(
                "thirdcode.accounting.period",
                "create",
                [
                    {
                        "name": "TC-FULL-CLOSED-2026",
                        "company_id": company_id,
                        "date_start": "2026-01-01",
                        "date_end": "2026-01-31",
                    }
                ],
            )
        )
        row = required_row(
            admin.first("thirdcode.accounting.period", [("id", "=", period_id)], fields),
            "synthetic closed period",
        )
    period_id = int(row["id"])
    if row["state"] != "closed":
        admin.call("thirdcode.accounting.period", "action_close", [[period_id]])
    return period_id, True


def ensure_recurring_journal(odoo: Odoo, admin: Odoo, company_id: int, journal_id: int, debit_id: int, credit_id: int) -> dict[str, Any]:
    fields = ["id", "name", "reference", "next_run", "generated_move_ids"]
    row = first_or_none(
        odoo,
        "thirdcode.recurring.journal",
        [("reference", "=", "TC-FULL-RECUR-JOURNAL")],
        fields,
    )
    if not row:
        record_id = int(
            admin.call(
                "thirdcode.recurring.journal",
                "create",
                [
                    {
                        "name": "TC-FULL monthly accrual",
                        "company_id": company_id,
                        "journal_id": journal_id,
                        "reference": "TC-FULL-RECUR-JOURNAL",
                        "date_start": TODAY,
                        "next_run": TODAY,
                        "interval_number": 1,
                        "interval_type": "months",
                        "line_ids": [
                            [0, 0, {"name": "Synthetic debit", "account_id": debit_id, "debit": 100.0}],
                            [0, 0, {"name": "Synthetic credit", "account_id": credit_id, "credit": 100.0}],
                        ],
                    }
                ],
            )
        )
        row = required_row(admin.first("thirdcode.recurring.journal", [("id", "=", record_id)], fields), "recurring journal")
    record_id = int(row["id"])
    before = len(row.get("generated_move_ids") or [])
    admin.call("thirdcode.recurring.journal", "action_run_now", [[record_id]])
    after_first = admin.first("thirdcode.recurring.journal", [("id", "=", record_id)], fields)
    admin.call("thirdcode.recurring.journal", "action_run_now", [[record_id]])
    after_second = admin.first("thirdcode.recurring.journal", [("id", "=", record_id)], fields)
    generated = after_second.get("generated_move_ids") or []
    first_generated = after_first.get("generated_move_ids") or []
    if len(first_generated) < before or (before == 0 and len(first_generated) != 1):
        raise RuntimeError("Recurring journal did not create exactly one new entry")
    if len(generated) != len(first_generated):
        raise RuntimeError("Recurring journal run was not idempotent")
    move = required_row(
        admin.first("account.move", [("id", "=", int(generated[-1]))], ["id", "state", "thirdcode_document_class"]),
        "generated recurring journal entry",
    )
    if move["state"] != "posted" or move["thirdcode_document_class"] != "recurring_journal":
        raise RuntimeError("Recurring journal entry was not posted/classified")
    return {"id": record_id, "generated_count": len(generated), "move_id": int(move["id"])}


def ensure_recurring_invoice(odoo: Odoo, admin: Odoo, company_id: int, partner_id: int, journal_id: int, income_id: int) -> dict[str, Any]:
    fields = ["id", "name", "reference", "generated_move_ids", "next_run"]
    row = first_or_none(
        odoo,
        "thirdcode.recurring.invoice",
        [("reference", "=", "TC-FULL-RECUR-INVOICE")],
        fields,
    )
    if not row:
        record_id = int(
            admin.call(
                "thirdcode.recurring.invoice",
                "create",
                [
                    {
                        "name": "TC-FULL monthly service invoice",
                        "company_id": company_id,
                        "move_type": "out_invoice",
                        "partner_id": partner_id,
                        "journal_id": journal_id,
                        "reference": "TC-FULL-RECUR-INVOICE",
                        "date_start": TODAY,
                        "next_run": TODAY,
                        "interval_number": 1,
                        "interval_type": "months",
                        "line_ids": [
                            [0, 0, {"name": "Synthetic recurring service", "account_id": income_id, "quantity": 1.0, "price_unit": 125.0}],
                        ],
                    }
                ],
            )
        )
        row = required_row(admin.first("thirdcode.recurring.invoice", [("id", "=", record_id)], fields), "recurring invoice")
    record_id = int(row["id"])
    before = len(row.get("generated_move_ids") or [])
    admin.call("thirdcode.recurring.invoice", "action_run_now", [[record_id]])
    after_first = required_row(admin.first("thirdcode.recurring.invoice", [("id", "=", record_id)], fields), "recurring invoice after first run")
    admin.call("thirdcode.recurring.invoice", "action_run_now", [[record_id]])
    after_second = required_row(admin.first("thirdcode.recurring.invoice", [("id", "=", record_id)], fields), "recurring invoice after second run")
    first_ids = after_first.get("generated_move_ids") or []
    second_ids = after_second.get("generated_move_ids") or []
    if len(first_ids) < before or (before == 0 and len(first_ids) != 1) or len(second_ids) != len(first_ids):
        raise RuntimeError("Recurring invoice scheduler is not idempotent")
    move = required_row(
        admin.first("account.move", [("id", "=", int(second_ids[-1]))], ["id", "state", "move_type", "amount_total", "thirdcode_document_class"]),
        "generated recurring invoice",
    )
    if move["state"] != "posted" or move["move_type"] != "out_invoice" or move["thirdcode_document_class"] != "recurring_invoice":
        raise RuntimeError("Recurring invoice was not posted/classified")
    return {"id": record_id, "generated_count": len(second_ids), "move_id": int(move["id"]), "amount_total": str(money(move["amount_total"]))}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.environ.get("ODOO_URL", "http://localhost:8069"))
    parser.add_argument("--database", default=os.environ.get("ODOO_DB", "thirdcode_accounting"))
    parser.add_argument("--login", default=os.environ.get("ODOO_LOGIN", "admin"))
    parser.add_argument("--password", default=os.environ.get("ODOO_PASSWORD", "admin"))
    args = parser.parse_args()

    root = Odoo(args.url, args.database, args.login, args.password)
    roles = ensure_role_users(root)
    admin_spec = roles["administrator"]
    admin = Odoo(args.url, args.database, admin_spec["login"], admin_spec["password"])
    odoo = admin
    company = required_row(
        odoo.first(
            "res.company",
            [],
            [
                "id",
                "name",
                "currency_id",
                "thirdcode_reconciliation_definition",
                "thirdcode_payment_approval_enabled",
                "thirdcode_payment_approval_threshold",
            ],
        ),
        "company",
    )
    company_id = int(company["id"])
    receivable = account_by_code(odoo, company_id, "121000")
    payable = account_by_code(odoo, company_id, "211000")
    expense_account = account_by_code(odoo, company_id, "600000")
    income = first_or_none(odoo, "account.account", [("account_type", "=", "income"), ("company_ids", "in", [company_id])], ["id", "code", "name"])
    income = required_row(income, "an income account")
    sale = journal_by_type(odoo, company_id, "sale")
    purchase = journal_by_type(odoo, company_id, "purchase")
    general = journal_by_type(odoo, company_id, "general")
    bank = journal_by_type(odoo, company_id, "bank")
    partner = ensure_partner(odoo, "TC Full Scope Customer", "TC-FULL-CUSTOMER", True, int(receivable["id"]), int(payable["id"]))

    checks: dict[str, Any] = {}
    period_id, _ = ensure_period(odoo, company_id, admin)
    probe = first_or_none(odoo, "account.move", [("ref", "=", "TC-FULL-CLOSED-PROBE")], ["id", "state"])
    if not probe:
        probe_id = int(admin.call("account.move", "create", [{
            "company_id": company_id,
            "move_type": "entry",
            "journal_id": int(general["id"]),
            "date": "2026-01-15",
            "ref": "TC-FULL-CLOSED-PROBE",
            "line_ids": [
                [0, 0, {"name": "Closed period debit", "account_id": int(receivable["id"]), "debit": 10.0}],
                [0, 0, {"name": "Closed period credit", "account_id": int(income["id"]), "credit": 10.0}],
            ],
        }]))
        probe = required_row(admin.first("account.move", [("id", "=", probe_id)], ["id", "state"]), "closed-period probe")
    checks["closed_period_post_blocked"] = bool(expect_error(lambda: admin.call("account.move", "action_post", [[int(probe["id"])] ]), "posting in closed period"))
    if probe["state"] == "draft":
        admin.call("account.move", "unlink", [[int(probe["id"])]])
    readonly = Odoo(
        args.url,
        args.database,
        roles["readonly"]["login"],
        roles["readonly"]["password"],
    )
    checks["period_reopen"] = {
        "readonly_reopen_blocked": bool(
            expect_error(
                lambda: readonly.call(
                    "thirdcode.accounting.period",
                    "action_reopen",
                    [[period_id]],
                ),
                "read-only period reopen",
            )
        ),
    }
    admin.call("thirdcode.accounting.period", "action_reopen", [[period_id]])
    reopened = required_row(
        admin.first(
            "thirdcode.accounting.period",
            [("id", "=", period_id)],
            ["state", "reopened_by"],
        ),
        "reopened synthetic period",
    )
    checks["period_reopen"]["administrator_reopened"] = (
        reopened["state"] == "open" and bool(reopened["reopened_by"])
    )
    admin.call("thirdcode.accounting.period", "action_close", [[period_id]])
    checks["period_reopen"]["administrator_reclosed"] = (
        required_row(
            admin.first(
                "thirdcode.accounting.period",
                [("id", "=", period_id)],
                ["state"],
            ),
            "reclosed synthetic period",
        )["state"]
        == "closed"
    )
    checks["period_id"] = period_id

    checks["recurring_journal"] = ensure_recurring_journal(odoo, admin, company_id, int(general["id"]), int(receivable["id"]), int(income["id"]))
    checks["recurring_invoice"] = ensure_recurring_invoice(odoo, admin, company_id, partner, int(sale["id"]), int(income["id"]))

    invoice_id = checks["recurring_invoice"]["move_id"]
    batch = first_or_none(odoo, "thirdcode.payment.batch", [("name", "=", "PB/FULL-SCOPE")], ["id", "state", "line_ids", "total_amount"])
    if not batch:
        batch_id = int(admin.call("thirdcode.payment.batch", "create", [{
            "name": "PB/FULL-SCOPE",
            "company_id": company_id,
            "journal_id": int(bank["id"]),
            "date": TODAY,
            "payment_type": "inbound",
            "partner_type": "customer",
            "payment_instrument": "bank_transfer",
            "instrument_reference": "TC-FULL-TRANSFER-001",
            "line_ids": [[0, 0, {"move_id": invoice_id, "partner_id": partner, "amount": 0.0, "communication": "TC-FULL-PAYMENT"}]],
        }]))
        batch = required_row(admin.first("thirdcode.payment.batch", [("id", "=", batch_id)], ["id", "state", "line_ids", "total_amount"]), "payment batch")
    batch_id = int(batch["id"])
    if batch["state"] != "posted":
        admin.call("thirdcode.payment.batch", "action_post", [[batch_id]])
    batch = required_row(admin.first("thirdcode.payment.batch", [("id", "=", batch_id)], ["id", "state", "line_ids", "total_amount"]), "posted payment batch")
    if batch["state"] != "posted":
        raise RuntimeError("Payment batch did not post")
    line = required_row(admin.first("thirdcode.payment.batch.line", [("batch_id", "=", batch_id)], ["payment_id"]), "payment batch line")
    payment_id = int(line["payment_id"][0])
    payment = required_row(admin.first("account.payment", [("id", "=", payment_id)], ["id", "state", "thirdcode_receipt_number", "thirdcode_payment_instrument", "thirdcode_instrument_reference"]), "batch payment")
    if not payment["thirdcode_receipt_number"] or payment["thirdcode_payment_instrument"] != "bank_transfer":
        raise RuntimeError("Posted batch payment did not receive receipt/instrument metadata")
    checks["payment_batch"] = {"id": batch_id, "payment_id": payment_id, "receipt_number": payment["thirdcode_receipt_number"]}
    checks["official_receipt_guarded"] = bool(expect_error(lambda: admin.call("account.payment", "action_print_thirdcode_receipt", [[payment_id]]), "printing without BIR control"))

    advance_batch = first_or_none(odoo, "thirdcode.payment.batch", [("name", "=", "PB/FULL-SCOPE-ADVANCE")], ["id", "state"])
    if not advance_batch:
        advance_id = int(admin.call("thirdcode.payment.batch", "create", [{
            "name": "PB/FULL-SCOPE-ADVANCE",
            "company_id": company_id,
            "journal_id": int(bank["id"]),
            "date": TODAY,
            "payment_type": "inbound",
            "partner_type": "customer",
            "payment_instrument": "cash",
            "line_ids": [[0, 0, {"partner_id": partner, "amount": 25.0, "communication": "TC-FULL-CUSTOMER-ADVANCE"}]],
        }]))
        advance_batch = required_row(admin.first("thirdcode.payment.batch", [("id", "=", advance_id)], ["id", "state"]), "customer advance batch")
    advance_id = int(advance_batch["id"])
    if advance_batch["state"] != "posted":
        admin.call("thirdcode.payment.batch", "action_post", [[advance_id]])
    advance_line = required_row(admin.first("thirdcode.payment.batch.line", [("batch_id", "=", advance_id)], ["payment_id"]), "customer advance payment")
    advance_payment = required_row(admin.first("account.payment", [("id", "=", int(advance_line["payment_id"][0]))], ["id", "state", "thirdcode_receipt_number"]), "posted customer advance")
    checks["customer_advance"] = {"batch_id": advance_id, "payment_id": int(advance_payment["id"]), "receipt_number": advance_payment["thirdcode_receipt_number"]}

    supplier = ensure_partner(odoo, "TC Full Scope Supplier", "TC-FULL-SUPPLIER", False, int(receivable["id"]), int(payable["id"]))
    approval_batch = first_or_none(odoo, "thirdcode.payment.batch", [("name", "=", "PB/FULL-SCOPE-APPROVAL-REGRESSION")], ["id", "state"])
    original_approval = {
        "thirdcode_payment_approval_enabled": company["thirdcode_payment_approval_enabled"],
        "thirdcode_payment_approval_threshold": company["thirdcode_payment_approval_threshold"],
    }
    try:
        root.call(
            "res.company",
            "write",
            [[company_id], {"thirdcode_payment_approval_enabled": True, "thirdcode_payment_approval_threshold": 10.0}],
        )
        if not approval_batch:
            approval_id = int(
                admin.call(
                    "thirdcode.payment.batch",
                    "create",
                    [{
                        "name": "PB/FULL-SCOPE-APPROVAL-REGRESSION",
                        "company_id": company_id,
                        "journal_id": int(bank["id"]),
                        "date": TODAY,
                        "payment_type": "outbound",
                        "partner_type": "supplier",
                        "payment_instrument": "cash",
                        "line_ids": [[0, 0, {"partner_id": supplier, "amount": 20.0, "communication": "TC-FULL-THRESHOLD-APPROVAL"}]],
                    }],
                )
            )
            approval_batch = required_row(
                admin.first("thirdcode.payment.batch", [("id", "=", approval_id)], ["id", "state"]),
                "threshold payment batch",
            )
        approval_id = int(approval_batch["id"])
        if approval_batch["state"] == "draft":
            admin.call("thirdcode.payment.batch", "action_submit", [[approval_id]])
        approval_batch = required_row(
            admin.first("thirdcode.payment.batch", [("id", "=", approval_id)], ["id", "state"]),
            "threshold payment batch after submit",
        )
        approval_blocked = False
        if approval_batch["state"] == "pending_approval":
            approval_blocked = bool(expect_error(lambda: admin.call("thirdcode.payment.batch", "action_post", [[approval_id]]), "posting threshold payment before approval"))
            admin.call("thirdcode.payment.batch", "action_approve", [[approval_id]])
            approval_batch = required_row(
                admin.first("thirdcode.payment.batch", [("id", "=", approval_id)], ["id", "state"]),
                "approved threshold payment batch",
            )
        if approval_batch["state"] in ("approved", "draft"):
            admin.call("thirdcode.payment.batch", "action_post", [[approval_id]])
        final_approval = required_row(
            admin.first("thirdcode.payment.batch", [("id", "=", approval_id)], ["id", "state"]),
            "posted threshold payment batch",
        )
        if final_approval["state"] != "posted":
            raise RuntimeError(f"Threshold payment batch did not post after approval: {final_approval}")
        checks["optional_payment_approval"] = {
            "batch_id": approval_id,
            "approval_required": True,
            "blocked_before_approval": approval_blocked,
            "state": final_approval["state"],
        }
    finally:
        root.call("res.company", "write", [[company_id], original_approval])
    adjustments = []
    for reference, move_type, journal_id, adjustment_partner, account_id, expected_class in (
        ("TC-FULL-CREDIT-NOTE", "out_refund", int(sale["id"]), partner, int(income["id"]), "credit_note"),
        ("TC-FULL-DEBIT-NOTE", "in_refund", int(purchase["id"]), supplier, int(expense_account["id"]), "debit_note"),
    ):
        adjustment = first_or_none(odoo, "account.move", [("ref", "=", reference)], ["id", "state", "thirdcode_document_class"])
        if not adjustment:
            adjustment_id = int(admin.call("account.move", "create", [{
                "company_id": company_id,
                "move_type": move_type,
                "partner_id": adjustment_partner,
                "journal_id": journal_id,
                "invoice_date": TODAY,
                "ref": reference,
                "invoice_line_ids": [[0, 0, {"name": reference, "quantity": 1, "price_unit": 10.0, "account_id": account_id}]],
            }]))
            admin.call("account.move", "action_post", [[adjustment_id]])
            adjustment = required_row(admin.first("account.move", [("id", "=", adjustment_id)], ["id", "state", "thirdcode_document_class"]), reference)
        if adjustment["state"] != "posted" or adjustment["thirdcode_document_class"] != expected_class:
            raise RuntimeError(f"Adjustment document did not post/classify correctly: {adjustment}")
        adjustments.append(int(adjustment["id"]))
    checks["credit_and_debit_notes"] = {"credit_note_id": adjustments[0], "debit_note_id": adjustments[1]}

    employee = required_row(admin.first("hr.employee", [], ["id", "name"]), "native employee for reimbursement")
    expense = first_or_none(odoo, "hr.expense", [("name", "=", "TC-FULL-EMPLOYEE-EXPENSE")], ["id", "state"])
    if not expense:
        expense_id = int(admin.call("hr.expense", "create", [{
            "name": "TC-FULL-EMPLOYEE-EXPENSE",
            "employee_id": int(employee["id"]),
            "date": TODAY,
            "quantity": 1.0,
            "total_amount": 18.0,
            "payment_mode": "own_account",
            "account_id": int(expense["id"]) if expense else int(expense_account["id"]),
        }]))
        expense = required_row(admin.first("hr.expense", [("id", "=", expense_id)], ["id", "state"]), "employee reimbursement draft")
    if expense["state"] != "draft":
        raise RuntimeError(f"Employee reimbursement probe was not left as a draft: {expense}")
    admin.call("hr.expense", "unlink", [[int(expense["id"])]])
    checks["employee_reimbursement_surface"] = {"model": "hr.expense", "draft_created": True, "draft_removed": True}

    statement_line = first_or_none(odoo, "account.bank.statement.line", [("payment_ref", "=", "TC-FULL-STATEMENT-LINE")], ["id", "amount"])
    if not statement_line:
        statement_line_id = int(admin.call("account.bank.statement.line", "create", [{
            "name": "TC-FULL-STATEMENT-LINE",
            "date": TODAY,
            "amount": 123.45,
            "journal_id": int(bank["id"]),
            "payment_ref": "TC-FULL-STATEMENT-LINE",
            "partner_id": partner,
        }]))
    else:
        statement_line_id = int(statement_line["id"])
    statement_line = required_row(admin.first("account.bank.statement.line", [("id", "=", statement_line_id)], ["thirdcode_reconciliation_status", "is_reconciled"]), "bank statement reconciliation status")
    if statement_line["thirdcode_reconciliation_status"] != "unreconciled" or statement_line["is_reconciled"]:
        raise RuntimeError(f"New bank statement line was not unreconciled: {statement_line}")
    checks["bank_statement_line_status"] = {"status": "unreconciled", "synthetic_line_retained": True}

    recon = first_or_none(odoo, "thirdcode.bank.reconciliation", [("statement_reference", "=", "TC-FULL-BANK-001")], ["id", "state", "difference"])
    if not recon:
        recon_id = int(admin.call("thirdcode.bank.reconciliation", "create", [{
            "name": "TC-FULL bank reconciliation",
            "company_id": company_id,
            "journal_id": int(bank["id"]),
            "statement_reference": "TC-FULL-BANK-001",
            "date_start": TODAY,
            "date_end": TODAY,
            "opening_balance": 0.0,
            "closing_balance": 0.0,
            "ledger_balance": 0.0,
            "outstanding_deposits": 0.0,
            "outstanding_payments": 0.0,
            "evidence_file": base64.b64encode(b"synthetic paper statement evidence").decode("ascii"),
            "evidence_filename": "TC-FULL-BANK-001.txt",
            "definition": "Synthetic evidence only; client owner, bank source, cadence and sign-off remain configurable.",
        }]))
        recon = required_row(admin.first("thirdcode.bank.reconciliation", [("id", "=", recon_id)], ["id", "state", "difference"]), "bank reconciliation")
    recon_id = int(recon["id"])
    if recon["state"] != "reconciled":
        admin.call("thirdcode.bank.reconciliation", "action_reconcile", [[recon_id]])
    recon = required_row(admin.first("thirdcode.bank.reconciliation", [("id", "=", recon_id)], ["state", "difference"]), "reconciled bank record")
    checks["bank_reconciliation"] = {"id": recon_id, "state": recon["state"], "difference": str(money(recon["difference"]))}

    general_journal = required_row(
        admin.first(
            "account.journal",
            [("company_id", "=", company_id), ("type", "=", "general")],
            ["id", "thirdcode_numbering_policy", "thirdcode_numbering_owner"],
        ),
        "general journal for numbering control",
    )
    general_journal_id = int(general_journal["id"])
    if general_journal["thirdcode_numbering_policy"] != "no_gap_validated":
        admin.call(
            "account.journal",
            "write",
            [[general_journal_id], {"thirdcode_numbering_owner": "Synthetic control owner"}],
        )
        admin.call("account.journal", "action_validate_thirdcode_numbering", [[general_journal_id]])
    numbering = required_row(
        admin.first(
            "account.journal",
            [("id", "=", general_journal_id)],
            ["thirdcode_numbering_policy", "has_sequence_holes"],
        ),
        "validated numbering journal",
    )
    if numbering["thirdcode_numbering_policy"] != "no_gap_validated" or numbering["has_sequence_holes"]:
        raise RuntimeError(f"Numbering control did not validate: {numbering}")
    checks["numbering_control"] = numbering

    equity = required_row(
        admin.first(
            "account.account",
            [("company_ids", "in", [company_id]), ("account_type", "=", "equity")],
            ["id", "code", "name"],
        ),
        "retained earnings account candidate",
    )
    year_end = first_or_none(
        odoo,
        "thirdcode.year.end.close",
        [("name", "=", "TC-FULL-YEAR-END")],
        ["id", "state", "move_id", "profit_loss", "line_count"],
    )
    if not year_end:
        year_end_id = int(
            admin.call(
                "thirdcode.year.end.close",
                "create",
                [{
                    "name": "TC-FULL-YEAR-END",
                    "company_id": company_id,
                    "date_end": "2026-12-31",
                    "journal_id": general_journal_id,
                    "retained_earnings_account_id": int(equity["id"]),
                    "notes": "Synthetic proof only; client year-end account remains configurable.",
                }],
            )
        )
        admin.call("thirdcode.year.end.close", "action_post", [[year_end_id]])
        year_end = required_row(
            admin.first("thirdcode.year.end.close", [("id", "=", year_end_id)], ["id", "state", "move_id", "profit_loss", "line_count"]),
            "posted year-end close",
        )
    year_end_move_id = int(year_end["move_id"][0]) if year_end.get("move_id") else 0
    if year_end.get("state") != "posted" or not year_end_move_id:
        raise RuntimeError(f"Year-end close did not post: {year_end}")
    reversal = first_or_none(odoo, "account.move", [("reversed_entry_id", "=", year_end_move_id)], ["id", "state"])
    if not reversal:
        reversal_id = reverse_posted_move(admin, year_end_move_id, "Synthetic year-end close rollback")
        reversal = required_row(admin.first("account.move", [("id", "=", reversal_id)], ["id", "state"]), "year-end close reversal")
    checks["year_end_retained_earnings"] = {
        "id": int(year_end["id"]),
        "move_id": year_end_move_id,
        "state": year_end["state"],
        "reversal_id": int(reversal["id"]),
        "reversal_state": reversal["state"],
    }

    sample = first_or_none(odoo, "thirdcode.report.sample", [("name", "=", "TC-FULL-REPORT-SAMPLE")], ["id", "state", "revision"])
    if not sample:
        sample_id = int(admin.call("thirdcode.report.sample", "create", [{
            "name": "TC-FULL-REPORT-SAMPLE",
            "company_id": company_id,
            "sample_type": "statement",
            "revision": "synthetic-1",
            "source_file": base64.b64encode(b"synthetic report sample").decode("ascii"),
            "source_filename": "TC-FULL-REPORT-SAMPLE.txt",
        }]))
        sample = required_row(admin.first("thirdcode.report.sample", [("id", "=", sample_id)], ["id", "state", "revision"]), "report sample")
    sample_id = int(sample["id"])
    if sample["state"] != "approved":
        admin.call("thirdcode.report.sample", "action_approve", [[sample_id]])
    checks["report_sample_approval"] = admin.first("thirdcode.report.sample", [("id", "=", sample_id)], ["state", "revision"])

    tax = first_or_none(odoo, "thirdcode.tax.profile", [("name", "=", "TC-FULL-TAX-ASSESSMENT")], ["id", "status"])
    if not tax:
        tax_id = int(admin.call("thirdcode.tax.profile", "create", [{
            "name": "TC-FULL-TAX-ASSESSMENT",
            "company_id": company_id,
            "vat_registered": False,
            "effective_date": TODAY,
            "accountant_owner": "Synthetic accountant",
            "notes": "Synthetic profile: no statutory rate is inferred.",
        }]))
        tax = required_row(admin.first("thirdcode.tax.profile", [("id", "=", tax_id)], ["id", "status"]), "tax profile")
    tax_id = int(tax["id"])
    if tax["status"] != "configured":
        admin.call("thirdcode.tax.profile", "action_configure", [[tax_id]])
    checks["tax_profile"] = admin.first("thirdcode.tax.profile", [("id", "=", tax_id)], ["status"])

    migration = first_or_none(odoo, "thirdcode.migration.batch", [("name", "=", "MIG/FULL-SCOPE")], ["id", "state", "row_ids"])
    if not migration:
        migration_id = int(admin.call("thirdcode.migration.batch", "create", [{"name": "MIG/FULL-SCOPE", "source_system": "csv", "company_id": company_id, "row_ids": [[0, 0, {"source_identifier": "TC-FULL-OPENING-001", "target_model": "opening_balance", "source_debit": 100.0, "target_debit": 100.0, "source_credit": 0.0, "target_credit": 0.0}]]}]))
        migration = required_row(admin.first("thirdcode.migration.batch", [("id", "=", migration_id)], ["id", "state", "row_ids"]), "migration batch")
    migration_id = int(migration["id"])
    if migration["state"] == "draft":
        admin.call("thirdcode.migration.batch", "action_validate", [[migration_id]])
    if admin.first("thirdcode.migration.batch", [("id", "=", migration_id), ("state", "=", "validated")], ["id"]):
        admin.call("thirdcode.migration.batch", "action_mark_loaded", [[migration_id]])
    if admin.first("thirdcode.migration.batch", [("id", "=", migration_id), ("state", "=", "loaded")], ["id"]):
        admin.call("thirdcode.migration.batch", "action_mark_reconciled", [[migration_id]])
    checks["migration_batch"] = admin.first("thirdcode.migration.batch", [("id", "=", migration_id)], ["state", "row_count", "matched_count", "error_count"])

    audit_row = first_or_none(odoo, "auditlog.log", [], ["id"])
    if audit_row:
        audit_id = int(audit_row["id"])
        checks["audit_log_immutable"] = {
            "write_blocked": bool(expect_error(lambda: admin.call("auditlog.log", "write", [[audit_id], {"name": "forbidden"}]), "audit log write")),
            "unlink_blocked": bool(expect_error(lambda: admin.call("auditlog.log", "unlink", [[audit_id]]), "audit log delete")),
        }

    print(json.dumps({"status": "VERIFIED LOCALLY", "stack": {"database": args.database, "company": company["name"]}, "checks": checks}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}, indent=2), file=sys.stderr)
        raise
