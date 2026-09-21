"""Authenticated data endpoint for the TCSI command center."""

from datetime import date
import logging

from odoo import fields, http
from odoo.http import request


_logger = logging.getLogger(__name__)


class TCSIDashboardController(http.Controller):
    """Expose only company-scoped, permission-checked summary data."""

    @http.route(
        "/thirdcode_accounting/dashboard",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def dashboard(self):
        user = request.env.user
        company = request.env.company
        move_model = request.env["account.move"].with_company(company)

        def amount(record, field_name, fallback="amount_total"):
            value = getattr(record, field_name, False)
            if value is False:
                value = getattr(record, fallback, 0.0)
            return float(value or 0.0)

        def date_value(record, *field_names):
            for field_name in field_names:
                value = getattr(record, field_name, False)
                if value:
                    return fields.Date.to_string(value)
            return None

        def month_anchor(value):
            return value.replace(day=1)

        def shift_month(value, offset):
            index = value.year * 12 + value.month - 1 + offset
            return date(index // 12, index % 12 + 1, 1)

        def sum_account_balance(account_types):
            """Use a database aggregate so the dashboard stays fast as data grows."""
            try:
                groups = request.env["account.move.line"].read_group(
                    [
                        ("company_id", "=", company.id),
                        ("parent_state", "=", "posted"),
                        ("account_id.account_type", "in", account_types),
                    ],
                    ["balance:sum"],
                    [],
                )
                return float((groups[0] if groups else {}).get("balance", 0.0) or 0.0)
            except Exception:  # pragma: no cover - depends on installed accounting modules
                _logger.exception("Unable to aggregate dashboard account balances")
                return 0.0

        today = fields.Date.context_today(user)
        posted_domain = [
            ("company_id", "=", company.id),
            ("state", "=", "posted"),
        ]
        customer_open_domain = posted_domain + [
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("payment_state", "not in", ("paid", "reversed")),
        ]
        supplier_open_domain = posted_domain + [
            ("move_type", "in", ("in_invoice", "in_refund")),
            ("payment_state", "not in", ("paid", "reversed")),
        ]

        customer_open = move_model.search(customer_open_domain)
        supplier_open = move_model.search(supplier_open_domain)
        recent_moves = move_model.search(posted_domain, order="date desc, id desc", limit=8)

        six_month_start = shift_month(month_anchor(today), -5)
        activity_moves = move_model.search(
            posted_domain
            + [
                ("date", ">=", fields.Date.to_string(six_month_start)),
                ("move_type", "in", ("out_invoice", "out_refund", "in_invoice", "in_refund")),
            ],
            order="date asc, id asc",
        )
        monthly = {
            shift_month(six_month_start, index).strftime("%Y-%m"): {
                "key": shift_month(six_month_start, index).strftime("%Y-%m"),
                "label": shift_month(six_month_start, index).strftime("%b"),
                "sales": 0.0,
                "costs": 0.0,
            }
            for index in range(6)
        }
        for move in activity_moves:
            key = fields.Date.to_date(move.date).strftime("%Y-%m")
            if key not in monthly:
                continue
            value = abs(amount(move, "amount_total_signed"))
            if move.move_type in ("out_invoice", "out_refund"):
                monthly[key]["sales"] += value
            else:
                monthly[key]["costs"] += value

        recent = []
        labels = {
            "out_invoice": "Customer invoice",
            "out_refund": "Customer credit note",
            "in_invoice": "Supplier bill",
            "in_refund": "Supplier credit",
            "entry": "Journal entry",
        }
        for move in recent_moves:
            recent.append(
                {
                    "id": move.id,
                    "reference": move.name or move.ref or "Draft reference",
                    "label": labels.get(move.move_type, "Accounting entry"),
                    "partner": move.partner_id.display_name if move.partner_id else "Internal entry",
                    "date": date_value(move, "date", "invoice_date"),
                    "amount": abs(amount(move, "amount_total_signed")),
                    "is_refund": move.move_type in ("out_refund", "in_refund"),
                }
            )

        attention = []
        for move in sorted(
            customer_open | supplier_open,
            key=lambda record: date_value(record, "invoice_date_due", "invoice_date", "date") or "9999-12-31",
        )[:5]:
            is_customer = move.move_type in ("out_invoice", "out_refund")
            attention.append(
                {
                    "id": move.id,
                    "label": "Receivable" if is_customer else "Payable",
                    "partner": move.partner_id.display_name if move.partner_id else "Unassigned",
                    "date": date_value(move, "invoice_date_due", "invoice_date", "date"),
                    "amount": abs(amount(move, "amount_residual_signed", "amount_residual")),
                    "tone": "violet" if is_customer else "amber",
                }
            )

        def has_group(xmlid):
            return user.has_group(xmlid)

        if user._is_admin() or has_group("thirdcode_accounting.group_thirdcode_administrator"):
            role = "Administrator"
        elif has_group("thirdcode_accounting.group_thirdcode_accountant"):
            role = "Accountant"
        elif has_group("thirdcode_accounting.group_thirdcode_encoder"):
            role = "Encoder"
        else:
            role = "Read-only"

        return {
            "company_id": company.id,
            "company_name": company.name,
            "user_name": user.name,
            "role": role,
            "currency": company.currency_id.name or "USD",
            "currency_symbol": company.currency_id.symbol or company.currency_id.name or "$",
            "can_create": has_group("account.group_account_invoice"),
            "can_report": has_group("account.group_account_readonly")
            or has_group("account.group_account_user")
            or has_group("account.group_account_manager"),
            "kpis": {
                "cash": sum_account_balance(["asset_cash"]),
                "receivables": sum(
                    abs(amount(move, "amount_residual_signed", "amount_residual")) for move in customer_open
                ),
                "payables": sum(
                    abs(amount(move, "amount_residual_signed", "amount_residual")) for move in supplier_open
                ),
                "net_result": -sum_account_balance(
                    ["income", "income_other", "expense", "expense_depreciation", "expense_direct_cost"]
                ),
            },
            "monthly_activity": list(monthly.values()),
            "attention": attention,
            "recent": recent,
            "has_posted_activity": bool(recent_moves),
            "generated_at": fields.Datetime.to_string(fields.Datetime.now()),
        }
