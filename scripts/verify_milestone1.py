#!/usr/bin/env python3
"""Verify the synthetic Milestone 1 accounting proof through Odoo's RPC API."""

from __future__ import annotations

import json
import os
import sys
import http.cookiejar
import urllib.parse
import urllib.request
import xmlrpc.client
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


MONEY = Decimal("0.01")
TODAY = "2026-09-21"
INVOICE_DATE = "2026-09-01"
PAYMENT_DATE = "2026-09-15"

ROLE_USERS = {
    "administrator": {
        "login": "m1.administrator",
        "password": "M1-administrator-pass",
        "name": "M1 Administrator",
        "group_xmlid": "group_thirdcode_administrator",
    },
    "accountant": {
        "login": "m1.accountant",
        "password": "M1-accountant-pass",
        "name": "M1 Accountant",
        "group_xmlid": "group_thirdcode_accountant",
    },
    "encoder": {
        "login": "m1.encoder",
        "password": "M1-encoder-pass",
        "name": "M1 Encoder",
        "group_xmlid": "group_thirdcode_encoder",
    },
    "readonly": {
        "login": "m1.readonly",
        "password": "M1-readonly-pass",
        "name": "M1 Readonly",
        "group_xmlid": "group_thirdcode_readonly",
    },
}


def money(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)


class Odoo:
    def __init__(self, url: str, database: str, login: str, password: str) -> None:
        self.database = database
        self.password = password
        self.url = url.rstrip("/")
        self.login = login
        self.common = xmlrpc.client.ServerProxy(
            f"{self.url}/xmlrpc/2/common", allow_none=True
        )
        self.models = xmlrpc.client.ServerProxy(
            f"{self.url}/xmlrpc/2/object", allow_none=True
        )
        self.uid = self.common.authenticate(database, login, password, {})
        if not self.uid:
            raise RuntimeError("Odoo authentication failed")

    def call(
        self,
        model: str,
        method: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        return self.models.execute_kw(
            self.database,
            self.uid,
            self.password,
            model,
            method,
            args or [],
            kwargs or {},
        )

    def search_read(
        self,
        model: str,
        domain: list[Any],
        fields: list[str],
        limit: int = 0,
    ) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {"fields": fields}
        if limit:
            kwargs["limit"] = limit
        return self.call(model, "search_read", [domain], kwargs)

    def first(
        self, model: str, domain: list[Any], fields: list[str]
    ) -> dict[str, Any] | None:
        rows = self.search_read(model, domain, fields, limit=1)
        return rows[0] if rows else None


class OdooWebSession:
    """Use Odoo's authenticated web JSON-RPC/report endpoints for rendered output."""

    def __init__(self, url: str, database: str, login: str, password: str) -> None:
        self.url = url.rstrip("/")
        self.database = database
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )
        self._call(
            "/web/session/authenticate",
            {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "db": database,
                    "login": login,
                    "password": password,
                },
            },
        )

    def _call(self, path: str, payload: dict[str, Any]) -> Any:
        request = urllib.request.Request(
            f"{self.url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with self.opener.open(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
        if body.get("error"):
            raise RuntimeError(f"Odoo web RPC error: {body['error']}")
        return body.get("result")

    def call(
        self,
        model: str,
        method: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        return self._call(
            "/web/dataset/call_kw",
            {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "model": model,
                    "method": method,
                    "args": args or [],
                    "kwargs": kwargs or {},
                },
            },
        )

    def render_pdf(
        self,
        report_name: str,
        document_ids: list[int],
        options: dict[str, Any],
        context: dict[str, Any],
    ) -> int:
        query = urllib.parse.urlencode(
            {
                "options": json.dumps(options, separators=(",", ":")),
                "context": json.dumps(context, separators=(",", ":")),
            }
        )
        request = urllib.request.Request(
            f"{self.url}/report/pdf/{report_name}/{','.join(map(str, document_ids))}?{query}",
            headers={"Accept": "application/pdf"},
        )
        with self.opener.open(request, timeout=60) as response:
            content = response.read()
            if response.status != 200 or response.headers.get("Content-Type") != "application/pdf":
                raise RuntimeError(
                    f"Report {report_name} did not return a PDF: "
                    f"status={response.status} content_type={response.headers.get('Content-Type')}"
                )
        if not content.startswith(b"%PDF"):
            raise RuntimeError(f"Report {report_name} returned a non-PDF response")
        return len(content)


def required_row(row: dict[str, Any] | None, description: str) -> dict[str, Any]:
    if not row:
        raise RuntimeError(f"Required Odoo record not found: {description}")
    return row


def ensure_partner(
    odoo: Odoo,
    name: str,
    reference: str,
    customer: bool,
    receivable_id: int,
    payable_id: int,
) -> int:
    fields = [
        "id",
        "name",
        "ref",
        "property_account_receivable_id",
        "property_account_payable_id",
    ]
    row = odoo.first("res.partner", [("ref", "=", reference)], fields)
    if row:
        return int(row["id"])
    values: dict[str, Any] = {
        "name": name,
        "ref": reference,
        "company_type": "company",
        "street": "Synthetic Test Street 1",
        "city": "Synthetic City",
        "email": f"{reference.lower()}@example.invalid",
        "vat": f"SYN-{reference}",
        "customer_rank": 1 if customer else 0,
        "supplier_rank": 0 if customer else 1,
        "property_account_receivable_id": receivable_id,
        "property_account_payable_id": payable_id,
    }
    return int(odoo.call("res.partner", "create", [values]))


def account_by_code(odoo: Odoo, company_id: int, code: str) -> dict[str, Any]:
    return required_row(
        odoo.first(
            "account.account",
            [("code", "=", code), ("company_ids", "in", [company_id])],
            ["id", "code", "name", "account_type", "reconcile"],
        ),
        f"account code {code}",
    )


def journal_by_type(odoo: Odoo, company_id: int, journal_type: str) -> dict[str, Any]:
    return required_row(
        odoo.first(
            "account.journal",
            [("type", "=", journal_type), ("company_id", "=", company_id)],
            ["id", "name", "code", "type", "default_account_id"],
        ),
        f"{journal_type} journal",
    )


def ensure_move(
    odoo: Odoo,
    company_id: int,
    reference: str,
    move_type: str,
    partner_id: int,
    account_id: int,
    amount: Decimal,
    label: str,
) -> dict[str, Any]:
    fields = [
        "id",
        "name",
        "ref",
        "state",
        "move_type",
        "partner_id",
        "amount_total",
        "amount_residual",
        "currency_id",
        "company_id",
        "line_ids",
    ]
    row = odoo.first("account.move", [("ref", "=", reference)], fields)
    if not row:
        values = {
            "company_id": company_id,
            "move_type": move_type,
            "partner_id": partner_id,
            "invoice_date": INVOICE_DATE,
            "invoice_date_due": "2026-09-30",
            "ref": reference,
            "invoice_line_ids": [
                [
                    0,
                    0,
                    {
                        "name": label,
                        "quantity": 1,
                        "price_unit": float(amount),
                        "account_id": account_id,
                    },
                ]
            ],
        }
        move_id = int(odoo.call("account.move", "create", [values]))
        row = required_row(
            odoo.first("account.move", [("id", "=", move_id)], fields),
            reference,
        )
    if row["state"] == "draft":
        odoo.call("account.move", "action_post", [[int(row["id"])]])
        row = required_row(
            odoo.first("account.move", [("id", "=", int(row["id"]))], fields),
            reference,
        )
    if row["state"] != "posted":
        raise RuntimeError(f"Synthetic move {reference} is not posted: {row['state']}")
    if money(row["amount_total"]) != amount:
        raise RuntimeError(
            f"Synthetic move {reference} total {row['amount_total']} != {amount}"
        )
    return row


def move_lines(odoo: Odoo, move_id: int) -> list[dict[str, Any]]:
    return odoo.search_read(
        "account.move.line",
        [("move_id", "=", move_id)],
        ["id", "account_id", "partner_id", "debit", "credit", "balance", "parent_state"],
    )


def assert_balanced(odoo: Odoo, move: dict[str, Any]) -> None:
    lines = move_lines(odoo, int(move["id"]))
    debit = sum((money(line["debit"]) for line in lines), Decimal("0"))
    credit = sum((money(line["credit"]) for line in lines), Decimal("0"))
    if debit != credit:
        raise RuntimeError(
            f"Move {move['name']} is not balanced: debit={debit} credit={credit}"
        )


def payment_for_move(
    odoo: Odoo,
    move: dict[str, Any],
    amount: Decimal,
    bank_journal_id: int,
    payment_reference: str,
) -> dict[str, Any]:
    fields = [
        "id",
        "name",
        "memo",
        "state",
        "amount",
        "partner_id",
        "move_id",
        "is_reconciled",
    ]
    existing = odoo.first(
        "account.payment",
        [("memo", "=", payment_reference)],
        fields,
    )
    if existing:
        if existing["state"] not in {"in_process", "paid"}:
            raise RuntimeError(
                f"Existing synthetic payment {payment_reference} is not posted/paid: {existing['state']}"
            )
        payment_move = required_row(
            odoo.first(
                "account.move",
                [("id", "=", int(existing["move_id"][0]))],
                ["id", "state"],
            ),
            f"journal entry for payment {payment_reference}",
        )
        if payment_move["state"] != "posted":
            raise RuntimeError(
                f"Payment journal entry for {payment_reference} is not posted"
            )
        return existing

    action = odoo.call("account.move", "action_register_payment", [[int(move["id"])]])
    context = dict(action.get("context") or {})
    context.update(
        {
            "active_model": "account.move",
            "active_ids": [int(move["id"])],
            "active_id": int(move["id"]),
        }
    )
    wizard_id = int(
        odoo.call(
            "account.payment.register",
            "create",
            [
                {
                    "amount": float(amount),
                    "journal_id": bank_journal_id,
                    "payment_date": PAYMENT_DATE,
                    "communication": payment_reference,
                }
            ],
            {"context": context},
        )
    )
    odoo.call(
        "account.payment.register",
        "action_create_payments",
        [[wizard_id]],
        {"context": context},
    )
    payment = odoo.first("account.payment", [("memo", "=", payment_reference)], fields)
    payment = required_row(payment, f"payment {payment_reference}")
    if payment["state"] not in {"in_process", "paid"}:
        raise RuntimeError(
            f"Payment {payment_reference} was not posted/paid: {payment['state']}"
        )
    payment_move = required_row(
        odoo.first(
            "account.move",
            [("id", "=", int(payment["move_id"][0]))],
            ["id", "state"],
        ),
        f"journal entry for payment {payment_reference}",
    )
    if payment_move["state"] != "posted":
        raise RuntimeError(f"Payment journal entry for {payment_reference} is not posted")
    return payment


def create_invoice_draft(
    odoo: Odoo,
    company_id: int,
    partner_id: int,
    income_id: int,
    amount: Decimal,
    reference: str,
    invoice_date: str = TODAY,
) -> int:
    return int(
        odoo.call(
            "account.move",
            "create",
            [
                {
                    "company_id": company_id,
                    "move_type": "out_invoice",
                    "partner_id": partner_id,
                    "date": invoice_date,
                    "invoice_date": invoice_date,
                    "ref": reference,
                    "invoice_line_ids": [
                        [
                            0,
                            0,
                            {
                                "name": "Synthetic Milestone 1 role-control probe",
                                "quantity": 1,
                                "price_unit": float(amount),
                                "account_id": income_id,
                            },
                        ]
                    ],
                }
            ],
        )
    )


def xmlid_res_id(odoo: Odoo, module: str, name: str, description: str) -> int:
    row = required_row(
        odoo.first(
            "ir.model.data",
            [("module", "=", module), ("name", "=", name)],
            ["res_id"],
        ),
        description,
    )
    return int(row["res_id"])


def ensure_role_users(odoo: Odoo) -> dict[str, dict[str, Any]]:
    users: dict[str, dict[str, Any]] = {}
    for role, specification in ROLE_USERS.items():
        group_id = xmlid_res_id(
            odoo,
            "thirdcode_accounting",
            specification["group_xmlid"],
            f"provisional {role} group",
        )
        row = odoo.first(
            "res.users",
            [("login", "=", specification["login"])],
            ["id", "login", "name", "groups_id"],
        )
        if row:
            user_id = int(row["id"])
            group_ids = set(row.get("groups_id") or [])
            values: dict[str, Any] = {"password": specification["password"]}
            if group_id not in group_ids:
                values["groups_id"] = [[4, group_id]]
            odoo.call("res.users", "write", [[user_id], values])
        else:
            user_id = int(
                odoo.call(
                    "res.users",
                    "create",
                    [
                        {
                            "name": specification["name"],
                            "login": specification["login"],
                            "password": specification["password"],
                            "groups_id": [[6, 0, [group_id]]],
                        }
                    ],
                )
            )
        users[role] = {
            "id": user_id,
            "login": specification["login"],
            "password": specification["password"],
            "group_id": group_id,
        }
    return users


def reverse_posted_move(odoo: Odoo, move_id: int, reason: str) -> int:
    move = required_row(
        odoo.first(
            "account.move",
            [("id", "=", move_id)],
            ["id", "state", "journal_id"],
        ),
        f"move {move_id} for reversal",
    )
    if move["state"] != "posted":
        raise RuntimeError(
            f"Only posted moves may be reversed in the synthetic proof: {move_id}"
        )
    existing = odoo.first(
        "account.move",
        [("reversed_entry_id", "=", move_id)],
        ["id", "state"],
    )
    if existing:
        reversal_id = int(existing["id"])
        if existing["state"] == "draft":
            odoo.call("account.move", "action_post", [[reversal_id]])
        return reversal_id

    context = {
        "active_model": "account.move",
        "active_ids": [move_id],
        "active_id": move_id,
    }
    wizard_id = int(
        odoo.call(
            "account.move.reversal",
            "create",
            [
                {
                    "date": TODAY,
                    "reason": reason,
                    "journal_id": int(move["journal_id"][0]),
                }
            ],
            {"context": context},
        )
    )
    action = odoo.call(
        "account.move.reversal",
        "reverse_moves",
        [[wizard_id]],
        {"context": context},
    )
    reversal_id = int(action["res_id"]) if action.get("res_id") else 0
    if not reversal_id:
        reversal = required_row(
            odoo.first(
                "account.move",
                [("reversed_entry_id", "=", move_id)],
                ["id", "state"],
            ),
            f"reversal for move {move_id}",
        )
        reversal_id = int(reversal["id"])
    reversal_state = required_row(
        odoo.first("account.move", [("id", "=", reversal_id)], ["state"]),
        f"reversal move {reversal_id}",
    )["state"]
    if reversal_state == "draft":
        odoo.call("account.move", "action_post", [[reversal_id]])
    final_state = required_row(
        odoo.first("account.move", [("id", "=", reversal_id)], ["state"]),
        f"posted reversal move {reversal_id}",
    )["state"]
    if final_state != "posted":
        raise RuntimeError(f"Reversal move {reversal_id} was not posted")
    return reversal_id


def cleanup_legacy_role_probes(odoo: Odoo) -> dict[str, int]:
    refs = [
        "TC-M1-REG-ROLE-PROBE",
        "TC-M1-REG-ROLE-ENCODER-GUARD",
        "TC-M1-REG-ROLE-ACCOUNTANT-POST",
    ]
    reversed_count = 0
    deleted_drafts = 0
    rows = odoo.search_read(
        "account.move",
        [("ref", "in", refs)],
        ["id", "ref", "state"],
    )
    for row in rows:
        move_id = int(row["id"])
        if row["state"] == "draft":
            odoo.call("account.move", "unlink", [[move_id]])
            deleted_drafts += 1
        elif row["state"] == "posted":
            reverse_posted_move(
                odoo,
                move_id,
                "Milestone 1 synthetic role-control cleanup",
            )
            reversed_count += 1
    return {"reversed_posted_probes": reversed_count, "deleted_draft_probes": deleted_drafts}


def run_posting_role_probe(
    admin: Odoo,
    role_client: Odoo,
    company_id: int,
    customer_id: int,
    income_id: int,
    reference: str,
    amount: Decimal,
    reversal_reason: str,
) -> tuple[bool, bool]:
    row = admin.first(
        "account.move",
        [("ref", "=", reference)],
        ["id", "state"],
    )
    move_id = int(row["id"]) if row else create_invoice_draft(
        role_client,
        company_id,
        customer_id,
        income_id,
        amount,
        reference,
    )
    state = row["state"] if row else "draft"
    if state == "draft":
        role_client.call("account.move", "action_post", [[move_id]])
    posted = required_row(
        admin.first("account.move", [("id", "=", move_id)], ["state"]),
        f"posting role probe {reference}",
    )["state"] == "posted"
    if not posted:
        return False, False
    reversal_id = reverse_posted_move(admin, move_id, reversal_reason)
    reversal_posted = required_row(
        admin.first("account.move", [("id", "=", reversal_id)], ["state"]),
        f"posting role reversal {reference}",
    )["state"] == "posted"
    return True, reversal_posted


def run_role_matrix(
    admin: Odoo,
    url: str,
    database: str,
    company_id: int,
    customer_id: int,
    income_id: int,
) -> dict[str, Any]:
    cleanup = cleanup_legacy_role_probes(admin)
    role_users = ensure_role_users(admin)
    clients = {
        role: Odoo(url, database, details["login"], details["password"])
        for role, details in role_users.items()
    }
    checks: dict[str, Any] = {
        "synthetic_users": {role: details["id"] for role, details in role_users.items()},
        "legacy_probe_cleanup": cleanup,
    }

    readonly = clients["readonly"]
    readonly_create_blocked = False
    try:
        readonly_probe_id = create_invoice_draft(
            readonly,
            company_id,
            customer_id,
            income_id,
            Decimal("1.00"),
            "TC-M1-REG-ROLE-READONLY-CREATE",
        )
    except xmlrpc.client.Fault:
        readonly_create_blocked = True
    else:
        admin.call("account.move", "unlink", [[readonly_probe_id]])

    readonly_probe_id = create_invoice_draft(
        admin,
        company_id,
        customer_id,
        income_id,
        Decimal("1.00"),
        "TC-M1-REG-ROLE-READONLY-WRITE",
    )
    readonly_write_blocked = False
    try:
        readonly.call(
            "account.move",
            "write",
            [[readonly_probe_id], {"ref": "TC-M1-REG-ROLE-READONLY-WRITE-CHANGED"}],
        )
    except xmlrpc.client.Fault:
        readonly_write_blocked = True
    readonly_unlink_blocked = False
    try:
        readonly.call("account.move", "unlink", [[readonly_probe_id]])
    except xmlrpc.client.Fault:
        readonly_unlink_blocked = True
        admin.call("account.move", "unlink", [[readonly_probe_id]])

    readonly_post_blocked = False
    readonly_post_probe_id = create_invoice_draft(
        admin,
        company_id,
        customer_id,
        income_id,
        Decimal("1.00"),
        "TC-M1-REG-ROLE-READONLY-POST",
    )
    try:
        readonly.call("account.move", "action_post", [[readonly_post_probe_id]])
    except xmlrpc.client.Fault:
        readonly_post_blocked = True
        admin.call("account.move", "unlink", [[readonly_post_probe_id]])
    else:
        reverse_posted_move(admin, readonly_post_probe_id, "Unexpected readonly post cleanup")

    encoder = clients["encoder"]
    encoder_probe_id = create_invoice_draft(
        encoder,
        company_id,
        customer_id,
        income_id,
        Decimal("2.00"),
        "TC-M1-REG-ROLE-ENCODER-POST",
    )
    encoder_post_blocked = False
    try:
        encoder.call("account.move", "action_post", [[encoder_probe_id]])
    except xmlrpc.client.Fault as fault:
        encoder_post_blocked = "may not post accounting entries" in str(fault)
        admin.call("account.move", "unlink", [[encoder_probe_id]])
    else:
        reverse_posted_move(admin, encoder_probe_id, "Unexpected encoder post cleanup")

    encoder_report_blocked = False
    encoder_report_wizard_id: int | None = None
    try:
        encoder_web = OdooWebSession(
            url,
            database,
            ROLE_USERS["encoder"]["login"],
            ROLE_USERS["encoder"]["password"],
        )
        encoder_report_wizard_id = int(
            encoder_web.call(
                "trial.balance.report.wizard",
                "create",
                [
                    {
                        "company_id": company_id,
                        "date_from": "2026-01-01",
                        "date_to": "2026-12-31",
                        "target_move": "posted",
                        "account_ids": [[6, 0, []]],
                        "partner_ids": [[6, 0, []]],
                        "journal_ids": [[6, 0, []]],
                    }
                ],
            )
        )
    except (RuntimeError, xmlrpc.client.Fault):
        encoder_report_blocked = True
    else:
        admin.call(
            "trial.balance.report.wizard",
            "unlink",
            [[encoder_report_wizard_id]],
        )

    encoder_configuration_blocked = False
    try:
        encoder.call(
            "res.company",
            "action_validate_thirdcode_configuration",
            [[company_id]],
        )
    except xmlrpc.client.Fault as fault:
        encoder_configuration_blocked = (
            "Only an Accountant or Administrator" in str(fault)
        )

    accountant_post_allowed, _ = run_posting_role_probe(
        admin,
        clients["accountant"],
        company_id,
        customer_id,
        income_id,
        "TC-M1-REG-ROLE-ACCOUNTANT-POST-CONTROL",
        Decimal("2.00"),
        "Milestone 1 accountant role cleanup",
    )
    administrator_post_allowed, administrator_reversal_posted = run_posting_role_probe(
        admin,
        clients["administrator"],
        company_id,
        customer_id,
        income_id,
        "TC-M1-REG-ROLE-ADMINISTRATOR-POST-CONTROL",
        Decimal("2.00"),
        "Milestone 1 administrator role cleanup",
    )

    checks.update(
        {
            "readonly_create_blocked": readonly_create_blocked,
            "readonly_write_blocked": readonly_write_blocked,
            "readonly_unlink_blocked": readonly_unlink_blocked,
            "readonly_post_blocked": readonly_post_blocked,
            "encoder_can_create_draft": True,
            "encoder_post_blocked": encoder_post_blocked,
            "encoder_report_blocked": encoder_report_blocked,
            "encoder_configuration_validation_blocked": encoder_configuration_blocked,
            "accountant_can_post": accountant_post_allowed,
            "administrator_can_post": administrator_post_allowed,
            "administrator_reversal_posted": administrator_reversal_posted,
        }
    )
    if not all(
        checks[key]
        for key in (
            "readonly_create_blocked",
            "readonly_write_blocked",
            "readonly_unlink_blocked",
            "readonly_post_blocked",
            "encoder_can_create_draft",
            "encoder_post_blocked",
            "encoder_report_blocked",
            "encoder_configuration_validation_blocked",
            "accountant_can_post",
            "administrator_can_post",
            "administrator_reversal_posted",
        )
    ):
        raise RuntimeError(f"Provisional role matrix failed: {checks}")
    return checks


def run_period_lock_check(
    odoo: Odoo,
    company_id: int,
    customer_id: int,
    income_id: int,
) -> bool:
    company = required_row(
        odoo.first(
            "res.company",
            [("id", "=", company_id)],
            ["id", "fiscalyear_lock_date"],
        ),
        "company fiscal-year lock state",
    )
    original_lock_date = company["fiscalyear_lock_date"]
    probe_id: int | None = None
    adjusted = False
    try:
        odoo.call(
            "res.company",
            "write",
            [[company_id], {"fiscalyear_lock_date": "2026-08-31"}],
        )
        existing = odoo.first(
            "account.move",
            [("ref", "=", "TC-M1-REG-PERIOD-LOCK-PROBE")],
            ["id", "state"],
        )
        probe_id = int(existing["id"]) if existing else create_invoice_draft(
            odoo,
            company_id,
            customer_id,
            income_id,
            Decimal("1.00"),
            "TC-M1-REG-PERIOD-LOCK-PROBE",
            invoice_date="2026-08-01",
        )
        if not existing or existing["state"] == "draft":
            try:
                odoo.call("account.move", "action_post", [[probe_id]])
            except xmlrpc.client.Fault as fault:
                raise RuntimeError(
                    f"Unexpected fiscal-year lock posting failure for the soft-lock probe: {fault}"
                ) from fault
        posted = required_row(
            odoo.first("account.move", [("id", "=", probe_id)], ["state", "date"]),
            "posted period lock probe",
        )
        adjusted = posted["state"] == "posted" and posted["date"] > "2026-08-31"
    finally:
        if probe_id is not None:
            state = required_row(
                odoo.first("account.move", [("id", "=", probe_id)], ["state"]),
                "period lock probe cleanup",
            )["state"]
            if state == "posted":
                reverse_posted_move(odoo, probe_id, "Unexpected period-lock post cleanup")
            else:
                odoo.call("account.move", "unlink", [[probe_id]])
        odoo.call(
            "res.company",
            "write",
            [[company_id], {"fiscalyear_lock_date": original_lock_date or False}],
        )
    if not adjusted:
        raise RuntimeError(
            "A backdated posting was neither blocked nor moved after fiscalyear_lock_date"
        )
    return True


def posted_totals(odoo: Odoo, company_id: int) -> tuple[Decimal, Decimal]:
    lines = odoo.search_read(
        "account.move.line",
        [("company_id", "=", company_id), ("parent_state", "=", "posted")],
        ["debit", "credit"],
    )
    debit = sum((money(line["debit"]) for line in lines), Decimal("0"))
    credit = sum((money(line["credit"]) for line in lines), Decimal("0"))
    return debit, credit


def account_partner_balance(
    odoo: Odoo, company_id: int, account_id: int, partner_id: int
) -> Decimal:
    lines = odoo.search_read(
        "account.move.line",
        [
            ("company_id", "=", company_id),
            ("parent_state", "=", "posted"),
            ("account_id", "=", account_id),
            ("partner_id", "=", partner_id),
        ],
        ["balance"],
    )
    return sum((money(line["balance"]) for line in lines), Decimal("0"))


def configure_audit_rule(odoo: Odoo) -> int:
    model = required_row(
        odoo.first("ir.model", [("model", "=", "account.move")], ["id", "name"]),
        "ir.model account.move",
    )
    fields = ["id", "name", "state", "model_id", "log_create", "log_write", "log_unlink"]
    row = odoo.first("auditlog.rule", [("model_id", "=", int(model["id"]))], fields)
    values = {
        "name": "Third Code: account moves",
        "model_id": int(model["id"]),
        "log_type": "full",
        "log_create": True,
        "log_write": True,
        "log_unlink": True,
        "log_read": False,
        "capture_record": True,
        "state": "subscribed",
    }
    if row:
        odoo.call("auditlog.rule", "write", [[int(row["id"])], values])
        return int(row["id"])
    return int(odoo.call("auditlog.rule", "create", [values]))


def report_presence(odoo: Odoo) -> dict[str, bool]:
    menu_names = {
        "general_ledger": "General Ledger",
        "trial_balance": "Trial Balance",
        "aged_partner_balance": "Aged Partner Balance",
    }
    result: dict[str, bool] = {}
    for key, name in menu_names.items():
        result[key] = bool(
            odoo.first("ir.ui.menu", [("name", "=", name)], ["id", "name"])
        )
    statement_actions = odoo.search_read(
        "ir.actions.report",
        [("report_name", "ilike", "partner_statement")],
        ["id", "name", "report_name", "model"],
    )
    result["partner_statement"] = bool(statement_actions)
    return result


def render_report_proof(
    odoo: Odoo,
    url: str,
    database: str,
    login: str,
    password: str,
    company_id: int,
    customer_id: int,
) -> dict[str, dict[str, Any]]:
    layout = required_row(
        odoo.first(
            "ir.model.data",
            [("module", "=", "web"), ("name", "=", "external_layout_standard")],
            ["res_id"],
        ),
        "standard external report layout",
    )
    company = required_row(
        odoo.first("res.company", [("id", "=", company_id)], ["id", "external_report_layout_id"]),
        "synthetic company for report layout",
    )
    if not company["external_report_layout_id"]:
        odoo.call(
            "res.company",
            "write",
            [[company_id], {"external_report_layout_id": int(layout["res_id"])}],
        )

    web = OdooWebSession(url, database, login, password)
    report_results: dict[str, dict[str, Any]] = {}

    statement_context = {
        "active_model": "res.partner",
        "active_ids": [customer_id],
        "active_id": customer_id,
    }
    statement_values = {
        "company_id": company_id,
        "date_start": "2026-09-01",
        "date_end": "2026-09-30",
        "account_type": "asset_receivable",
        "show_aging_buckets": True,
        "show_only_overdue": False,
        "aging_type": "days",
        "filter_partners_non_due": False,
        "filter_negative_balances": False,
    }
    statement_wizard_id = int(
        web.call(
            "activity.statement.wizard",
            "create",
            [statement_values],
            {"context": statement_context},
        )
    )
    statement_action = web.call(
        "activity.statement.wizard",
        "button_export_pdf",
        [[statement_wizard_id]],
        {"context": statement_context},
    )
    statement_bytes = web.render_pdf(
        statement_action["report_name"],
        [customer_id],
        statement_action["data"],
        statement_action.get("context", {}),
    )
    report_results["customer_activity_statement"] = {
        "report_name": statement_action["report_name"],
        "pdf_bytes": statement_bytes,
    }

    wizard_specs = [
        (
            "trial_balance",
            "trial.balance.report.wizard",
            {
                "company_id": company_id,
                "date_from": "2026-01-01",
                "date_to": "2026-09-30",
                "target_move": "posted",
                "hide_account_at_0": False,
                "show_hierarchy": False,
                "limit_hierarchy_level": False,
                "show_hierarchy_level": 1,
                "hide_parent_hierarchy_level": False,
                "foreign_currency": False,
                "show_partner_details": False,
                "grouped_by": False,
                "label_text_limit": 40,
                "journal_ids": [[6, 0, []]],
                "account_ids": [[6, 0, []]],
                "partner_ids": [[6, 0, []]],
            },
        ),
        (
            "general_ledger",
            "general.ledger.report.wizard",
            {
                "company_id": company_id,
                "date_from": "2026-01-01",
                "date_to": "2026-09-30",
                "target_move": "posted",
                "hide_account_at_0": False,
                "centralize": True,
                "foreign_currency": False,
                "grouped_by": "partners",
                "show_cost_center": False,
                "label_text_limit": 40,
                "account_journal_ids": [[6, 0, []]],
                "account_ids": [[6, 0, []]],
                "partner_ids": [[6, 0, []]],
                "cost_center_ids": [[6, 0, []]],
            },
        ),
    ]
    for key, model, values in wizard_specs:
        wizard_id = int(web.call(model, "create", [values]))
        action = web.call(model, "button_export_pdf", [[wizard_id]])
        pdf_bytes = web.render_pdf(
            action["report_name"],
            [wizard_id],
            action["data"],
            action.get("context", {}),
        )
        report_results[key] = {
            "report_name": action["report_name"],
            "pdf_bytes": pdf_bytes,
        }
    financial_specs = [
        ("financial_balance_sheet", "balance_sheet"),
        ("financial_profit_loss", "profit_loss"),
        ("financial_cash_flow", "cash_flow"),
    ]
    financial_web = OdooWebSession(
        url,
        database,
        ROLE_USERS["accountant"]["login"],
        ROLE_USERS["accountant"]["password"],
    )
    for key, report_type in financial_specs:
        wizard_id = int(
            financial_web.call(
                "thirdcode.financial.report.wizard",
                "create",
                [
                    {
                        "report_type": report_type,
                        "company_id": company_id,
                        "date_from": "2026-01-01",
                        "date_to": "2026-09-30",
                        "target_move": "posted",
                    }
                ],
            )
        )
        report_data = financial_web.call(
            "thirdcode.financial.report.wizard",
            "get_report_data",
            [[wizard_id]],
        )
        action = financial_web.call(
            "thirdcode.financial.report.wizard",
            "action_export_pdf",
            [[wizard_id]],
        )
        pdf_bytes = financial_web.render_pdf(
            action["report_name"],
            [wizard_id],
            action.get("data") or {},
            action.get("context") or {},
        )
        report_results[key] = {
            "report_name": action["report_name"],
            "pdf_bytes": pdf_bytes,
        }
        if report_type == "balance_sheet":
            report_results[key]["section_totals"] = [
                {"name": section["name"], "total": section["total"]}
                for section in report_data["sections"]
            ]
            report_results[key]["balance_check"] = report_data["balance_check"]
            report_results[key]["balanced"] = report_data["balanced"]
        elif report_type == "profit_loss":
            report_results[key]["section_totals"] = [
                {"name": section["name"], "total": section["total"]}
                for section in report_data["sections"]
            ]
            report_results[key]["net_result"] = report_data["net_result"]
    return report_results


def main() -> int:
    url = os.environ.get("ODOO_URL", "http://localhost:8069")
    database = os.environ.get("ODOO_DB", "thirdcode_accounting")
    login = os.environ.get("ODOO_LOGIN", "admin")
    password = os.environ.get("ODOO_PASSWORD", "admin")
    odoo = Odoo(url, database, login, password)

    company = required_row(
        odoo.first("res.company", [], ["id", "name", "currency_id"]),
        "synthetic company",
    )
    company_id = int(company["id"])
    receivable = account_by_code(odoo, company_id, "121000")
    payable = account_by_code(odoo, company_id, "211000")
    income = account_by_code(odoo, company_id, "400000")
    expense = account_by_code(odoo, company_id, "600000")
    bank = journal_by_type(odoo, company_id, "bank")

    customer_id = ensure_partner(
        odoo,
        "Synthetic Customer - Milestone 1 Regression",
        "TC-M1-REG-CUSTOMER",
        True,
        int(receivable["id"]),
        int(payable["id"]),
    )
    supplier_id = ensure_partner(
        odoo,
        "Synthetic Supplier - Milestone 1 Regression",
        "TC-M1-REG-SUPPLIER",
        False,
        int(receivable["id"]),
        int(payable["id"]),
    )

    # A draft invoice is created and removed through the ORM. Posted totals
    # must remain identical before and after the draft exists.
    before_draft = posted_totals(odoo, company_id)
    draft_id = int(
        odoo.call(
            "account.move",
            "create",
            [
                {
                    "company_id": company_id,
                    "move_type": "out_invoice",
                    "partner_id": customer_id,
                    "invoice_date": TODAY,
                    "ref": "TC-M1-REG-DRAFT-PROBE",
                    "invoice_line_ids": [
                        [
                            0,
                            0,
                            {
                                "name": "Draft-only synthetic probe",
                                "quantity": 1,
                                "price_unit": 1.0,
                                "account_id": int(income["id"]),
                            },
                        ]
                    ],
                }
            ],
        )
    )
    draft_state = required_row(
        odoo.first("account.move", [("id", "=", draft_id)], ["id", "state"]),
        "draft probe",
    )["state"]
    after_draft = posted_totals(odoo, company_id)
    if before_draft != after_draft or draft_state != "draft":
        raise RuntimeError(
            f"Draft affected posted totals: before={before_draft} after={after_draft} state={draft_state}"
        )
    odoo.call("account.move", "unlink", [[draft_id]])

    audit_rule_id = configure_audit_rule(odoo)

    customer_invoice = ensure_move(
        odoo,
        company_id,
        "TC-M1-REG-AR-001",
        "out_invoice",
        customer_id,
        int(income["id"]),
        Decimal("1000.00"),
        "Synthetic service revenue",
    )
    assert_balanced(odoo, customer_invoice)
    customer_payment = payment_for_move(
        odoo,
        customer_invoice,
        Decimal("400.00"),
        int(bank["id"]),
        "TC-M1-REG-AR-PAY-001",
    )
    customer_invoice = required_row(
        odoo.first(
            "account.move",
            [("id", "=", int(customer_invoice["id"]))],
            ["id", "name", "amount_total", "amount_residual", "state", "partner_id"],
        ),
        "customer invoice after payment",
    )
    customer_residual = money(customer_invoice["amount_residual"])
    if customer_residual != Decimal("600.00"):
        raise RuntimeError(f"Customer residual {customer_residual} != 600.00")

    supplier_bill = ensure_move(
        odoo,
        company_id,
        "TC-M1-REG-AP-001",
        "in_invoice",
        supplier_id,
        int(expense["id"]),
        Decimal("800.00"),
        "Synthetic supplier expense",
    )
    assert_balanced(odoo, supplier_bill)
    supplier_payment = payment_for_move(
        odoo,
        supplier_bill,
        Decimal("500.00"),
        int(bank["id"]),
        "TC-M1-REG-AP-PAY-001",
    )
    supplier_bill = required_row(
        odoo.first(
            "account.move",
            [("id", "=", int(supplier_bill["id"]))],
            ["id", "name", "amount_total", "amount_residual", "state", "partner_id"],
        ),
        "supplier bill after payment",
    )
    supplier_residual = money(supplier_bill["amount_residual"])
    if supplier_residual != Decimal("300.00"):
        raise RuntimeError(f"Supplier residual {supplier_residual} != 300.00")

    # Clean up the earlier manual role probes before asserting the control
    # account balances. Posted probes are reversed; draft probes are removed.
    cleanup_legacy_role_probes(odoo)

    customer_control = account_partner_balance(
        odoo, company_id, int(receivable["id"]), customer_id
    )
    supplier_control = account_partner_balance(
        odoo, company_id, int(payable["id"]), supplier_id
    )
    if customer_control != customer_residual:
        raise RuntimeError(
            f"Customer control balance {customer_control} != residual {customer_residual}"
        )
    if supplier_control != -supplier_residual:
        raise RuntimeError(
            f"Supplier control balance {supplier_control} != expected {-supplier_residual}"
        )

    role_matrix = run_role_matrix(
        odoo,
        url,
        database,
        company_id,
        customer_id,
        int(income["id"]),
    )
    period_lock_blocked = run_period_lock_check(
        odoo,
        company_id,
        customer_id,
        int(income["id"]),
    )

    total_debit, total_credit = posted_totals(odoo, company_id)
    if total_debit != total_credit:
        raise RuntimeError(
            f"Posted trial balance does not balance: debit={total_debit} credit={total_credit}"
        )

    report_status = report_presence(odoo)
    missing_reports = [name for name, present in report_status.items() if not present]
    if missing_reports:
        raise RuntimeError(f"Required M1 report surfaces missing: {missing_reports}")
    rendered_reports = render_report_proof(
        odoo,
        url,
        database,
        login,
        password,
        company_id,
        customer_id,
    )

    audit_logs = odoo.search_read(
        "auditlog.log",
        [
            ("model_model", "=", "account.move"),
            ("res_id", "=", int(customer_invoice["id"])),
        ],
        ["id", "method", "user_id", "create_date", "line_ids", "res_id"],
    )
    audit_log_ids = [int(row["id"]) for row in audit_logs]
    audit_lines = (
        odoo.search_read(
            "auditlog.log.line",
            [("log_id", "in", audit_log_ids)],
            ["log_id", "field_name", "old_value_text", "new_value_text"],
        )
        if audit_log_ids
        else []
    )
    audit_traceability = {
        "user_and_timestamp": bool(
            audit_logs
            and all(row.get("user_id") and row.get("create_date") for row in audit_logs)
        ),
        "prior_value_capture": any(
            line.get("old_value_text") and line.get("new_value_text")
            for line in audit_lines
        ),
    }
    if not all(audit_traceability.values()):
        raise RuntimeError(f"Audit traceability evidence incomplete: {audit_traceability}")

    result = {
        "status": "VERIFIED LOCALLY",
        "stack": {
            "odoo": "18.0 Community",
            "database": database,
            "company": company["name"],
            "currency": company["currency_id"][1],
        },
        "synthetic_records": {
            "customer": customer_id,
            "customer_invoice": customer_invoice["name"],
            "customer_payment": customer_payment["name"],
            "customer_invoice_total": str(money(customer_invoice["amount_total"])),
            "customer_remaining": str(customer_residual),
            "supplier": supplier_id,
            "supplier_bill": supplier_bill["name"],
            "supplier_payment": supplier_payment["name"],
            "supplier_bill_total": str(money(supplier_bill["amount_total"])),
            "supplier_remaining": str(supplier_residual),
        },
        "checks": {
            "draft_does_not_affect_posted_totals": True,
            "customer_invoice_balanced": True,
            "supplier_bill_balanced": True,
            "customer_control_equals_residual": True,
            "supplier_control_equals_residual": True,
            "role_matrix": role_matrix,
            "fiscalyear_lock_adjusts_backdated_posting": period_lock_blocked,
            "posted_trial_balance_balanced": {
                "debit": str(total_debit),
                "credit": str(total_credit),
            },
            "report_surfaces": report_status,
            "rendered_reports": rendered_reports,
            "audit_rule_id": audit_rule_id,
            "audit_log_rows_for_customer_invoice": len(audit_logs),
            "audit_traceability": audit_traceability,
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, xmlrpc.client.Fault, OSError) as exc:
        print(f"VERIFICATION FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
