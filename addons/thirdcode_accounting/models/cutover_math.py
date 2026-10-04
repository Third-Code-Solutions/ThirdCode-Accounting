"""Decimal-only residual opening policy. No ORM, files, or network side effects."""
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation


class CutoverPolicyError(ValueError):
    pass


def build_cutover_plan(payload, account_types, rounding="0.01"):
    if not isinstance(payload, dict) or payload.get("policy") != "residual_cutover_v1":
        raise CutoverPolicyError("Select the residual_cutover_v1 accounting policy explicitly")
    allowed = {"policy", "trial_balance", "open_items", "undeposited_receipts", "history", "clearing_account_id", "journal_id"}
    if set(payload) - allowed or payload.get("history"):
        raise CutoverPolicyError("Live history cannot be added to a cutover snapshot; retain historical records in the source archive")
    quantum = Decimal(rounding)
    def money(raw):
        try:
            value = Decimal(str(raw))
            valid = value.is_finite() and value >= 0 and value.quantize(quantum) == value
        except (InvalidOperation, ValueError, TypeError):
            raise CutoverPolicyError("Amounts must be decimal numbers")
        if not valid:
            raise CutoverPolicyError("Amounts must be nonnegative finite values at company-currency precision")
        return value
    def account(raw):
        if raw not in account_types:
            raise CutoverPolicyError("An account is missing from the approved company mapping")
        return raw
    clearing = account(payload.get("clearing_account_id"))
    if account_types[clearing] != "equity":
        raise CutoverPolicyError("Use a dedicated equity opening-clearing account")
    expected = {}
    for row in payload.get("trial_balance", []):
        key = account(row["account_id"])
        if key in expected:
            raise CutoverPolicyError("Duplicate source trial-balance account")
        debit, credit = money(row["debit"]), money(row["credit"])
        if debit and credit:
            raise CutoverPolicyError("A source TB account cannot have both debit and credit")
        expected[key] = debit - credit
    if not expected or sum(expected.values()):
        raise CutoverPolicyError("The source trial balance must exist and balance")
    if expected.get(clearing, Decimal(0)):
        raise CutoverPolicyError("The opening-clearing account must be zero in the source TB")
    entries, identifiers = [], set()
    components = defaultdict(Decimal)
    receipt_cash = set()
    def add(source, kind, reference, lines, document_date=None):
        if not isinstance(source, str) or not source.strip() or source in identifiers:
            raise CutoverPolicyError("Component source identifiers must be nonempty and unique")
        identifiers.add(source)
        if sum(line["balance"] for line in lines):
            raise CutoverPolicyError("A component is unbalanced")
        for line in lines:
            components[line["account_id"]] += line["balance"]
        entries.append({"source_id": source, "kind": kind, "reference": reference or source,
                        "document_date": document_date, "lines": lines})
    signs = {"out_invoice": ("asset_receivable", 1), "out_refund": ("asset_receivable", -1),
             "in_invoice": ("liability_payable", -1), "in_refund": ("liability_payable", 1)}
    for row in payload.get("open_items", []):
        key = account(row["account_id"])
        if row.get("move_type") not in signs:
            raise CutoverPolicyError("Unsupported open-item document type")
        kind, sign = signs[row["move_type"]]
        if account_types[key] != kind or not row.get("partner_id"):
            raise CutoverPolicyError("Open items require a partner and the matching AR/AP control account")
        document_date = date.fromisoformat(row["document_date"]).isoformat()
        due = date.fromisoformat(row.get("due_date") or document_date).isoformat()
        amount = money(row["residual"])
        if not amount:
            raise CutoverPolicyError("Open items must have a nonzero remaining balance")
        add(row["source_id"], "open_item", row.get("reference"), [
            {"account_id": key, "partner_id": row["partner_id"], "balance": amount * sign, "due_date": due},
            {"account_id": clearing, "balance": -amount * sign},
        ], document_date)
    for row in payload.get("undeposited_receipts", []):
        cash = account(row["cash_account_id"])
        if account_types[cash] not in {"asset_cash", "asset_current"} or cash == clearing:
            raise CutoverPolicyError("Undeposited receipts need an asset cash/clearing account")
        amount = money(row["amount"])
        if not amount or not row.get("partner_id"):
            raise CutoverPolicyError("Receipts need a positive amount and customer")
        disposition = row.get("disposition")
        if disposition == "already_allocated":
            if not row.get("source_allocation_reference"):
                raise CutoverPolicyError("Already-settled receipts require source allocation evidence; never settle imported residuals again")
            counterpart = clearing
            partner = False
        elif disposition == "unallocated":
            counterpart = account(row.get("receivable_account_id"))
            if account_types[counterpart] != "asset_receivable":
                raise CutoverPolicyError("Unallocated customer receipts need a receivable control account")
            partner = row["partner_id"]
        else:
            raise CutoverPolicyError("Specify whether each receipt was already allocated in MYOB or remains unallocated")
        receipt_cash.add(cash)
        add(row["source_id"], "undeposited_receipt", row.get("reference"), [
            {"account_id": cash, "balance": amount},
            {"account_id": counterpart, "partner_id": partner, "balance": -amount},
        ], date.fromisoformat(row["document_date"]).isoformat())
    controls = {key for key in set(expected) | set(components) if account_types[key] in {"asset_receivable", "liability_payable"}}
    for key in controls | receipt_cash:
        if expected.get(key, Decimal(0)) != components.get(key, Decimal(0)):
            raise CutoverPolicyError("Open-item/receipt detail does not reconcile to source control account %s" % key)
    residual = [{"account_id": key, "balance": expected.get(key, Decimal(0)) - components.get(key, Decimal(0))}
                for key in sorted(set(expected) | set(components), key=str)]
    residual = [line for line in residual if line["balance"]]
    if residual:
        add("__residual_opening__", "residual_opening", "Residual opening trial balance", residual)
    if not entries:
        raise CutoverPolicyError("There are no opening balances to import")
    for key in set(expected) | set(components):
        if components.get(key, Decimal(0)) != expected.get(key, Decimal(0)):
            raise CutoverPolicyError("Internal residual policy reconciliation failed")
    # JSON-safe decimals remain strings until conversion into native monetary fields.
    for entry in entries:
        for line in entry["lines"]:
            line["balance"] = str(line["balance"])
    return {"policy": "residual_cutover_v1", "entries": entries,
            "expected_balances": {str(key): str(value) for key, value in expected.items()},
            "control_accounts": sorted(controls, key=str), "clearing_account_id": clearing}
