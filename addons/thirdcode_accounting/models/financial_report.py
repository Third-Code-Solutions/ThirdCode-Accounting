from collections import defaultdict
from datetime import date
from decimal import Decimal

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class FinancialReportWizard(models.TransientModel):
    _name = "thirdcode.financial.report.wizard"
    _description = "Third Code Provisional Financial Statement Report"

    report_type = fields.Selection(
        [
            ("balance_sheet", "Balance sheet"),
            ("profit_loss", "Profit and loss"),
            ("cash_flow", "Cash flow (provisional classification)"),
        ],
        required=True,
        default="balance_sheet",
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    date_from = fields.Date(
        required=True,
        default=lambda self: date(fields.Date.context_today(self).year, 1, 1),
    )
    date_to = fields.Date(required=True, default=fields.Date.context_today)
    comparison_date_from = fields.Date()
    comparison_date_to = fields.Date()

    target_move = fields.Selection(
        [("posted", "Posted entries only"), ("all", "All entries")],
        required=True,
        default="posted",
    )
    report_status = fields.Selection(
        selection=[
            ("draft", "Draft layout"),
            ("approved", "Approved layout"),
            ("trial", "Trial copy"),
        ],
        compute="_compute_report_status",
        string="Layout status",
    )

    @api.depends(
        "company_id.thirdcode_report_samples_approved",
        "company_id.thirdcode_trial_mode",
    )
    def _compute_report_status(self):
        for wizard in self:
            if wizard.company_id._thirdcode_approved_sample("financial"):
                wizard.report_status = "approved"
            elif wizard.company_id.thirdcode_trial_mode:
                wizard.report_status = "trial"
            else:
                wizard.report_status = "draft"

    @api.constrains("date_from", "date_to", "comparison_date_from", "comparison_date_to")
    def _check_dates(self):
        for wizard in self:
            if bool(wizard.comparison_date_from) != bool(wizard.comparison_date_to):
                raise ValidationError(_("Both comparative dates are required."))
            if wizard.comparison_date_from and wizard.comparison_date_from > wizard.comparison_date_to:
                raise ValidationError(_("Comparative start must be on or before its end."))
            if wizard.date_from > wizard.date_to:
                raise ValidationError(
                    _("The report start date must be on or before the end date.")
                )

    def _check_report_access(self):
        user = self.env.user
        if user.has_group("thirdcode_accounting.group_thirdcode_encoder") and not (
            user.has_group("thirdcode_accounting.group_thirdcode_accountant")
            or user.has_group("thirdcode_accounting.group_thirdcode_administrator")
        ):
            raise AccessError(
                _("Encoder users may prepare drafts, but may not run accounting reports.")
            )
        if self and any(wizard.company_id not in self.env.companies for wizard in self):
            raise AccessError(_("You may only run reports for an active company."))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_report_access()
        wizards = super().create(vals_list)
        wizards._check_report_access()
        return wizards

    def _move_line_domain(self, balance_sheet=False):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id),
            ("date", "<=", self.date_to),
        ]
        if not balance_sheet:
            domain.append(("date", ">=", self.date_from))
            if self.report_type == "profit_loss":
                closings = self.env["thirdcode.year.end.close"].search([
                    ("company_id", "=", self.company_id.id), ("move_id", "!=", False),
                ]).move_id
                reversals = self.env["account.move"].search([("reversed_entry_id", "in", closings.ids)])
                domain.append(("move_id", "not in", (closings | reversals).ids))
        if self.target_move == "posted":
            domain.append(("parent_state", "=", "posted"))
        return domain

    def _account_totals(self, domain):
        totals = defaultdict(lambda: Decimal("0"))
        for account, balance in self.env["account.move.line"]._read_group(domain, ["account_id"], ["balance:sum"]):
            totals[account] += Decimal(str(balance))
        return totals

    @staticmethod
    def _amount(value):
        return f"{value:,.2f}"

    def _lines_for_group(self, totals, groups, normalize=False):
        rows = []
        for account, balance in sorted(
            totals.items(), key=lambda item: (item[0].code or "", item[0].id)
        ):
            if account.internal_group not in groups or abs(balance) < Decimal("0.005"):
                continue
            amount = (
                -balance
                if normalize and account.internal_group in {"income", "liability", "equity"}
                else balance
            )
            rows.append(
                {
                    "code": account.code or "",
                    "name": account.name,
                    "amount": self._amount(amount),
                }
            )
        return rows

    def _section(self, name, rows):
        total = sum(
            (Decimal(row["amount"].replace(",", "")) for row in rows), Decimal("0")
        )
        return {"name": name, "lines": rows, "total": self._amount(total)}

    def _cash_flow_sections(self):
        """Direct cash flow classifications with an explicit unresolved bucket.

        Mixed-category counterpart entries need a reviewed allocation; inferring
        a split could classify non-cash offsets as cash flows.
        """
        cash_accounts = self.env["account.account"].search([
            ("company_ids", "in", self.company_id.ids),
            "|", ("account_type", "=", "asset_cash"), ("thirdcode_cash_equivalent", "=", True),
        ])
        domain = self._move_line_domain()
        cash_lines = self.env["account.move.line"].search(domain + [("account_id", "in", cash_accounts.ids)])
        groups = {key: [] for key in ("operating", "investing", "financing", "unclassified")}
        for move in cash_lines.move_id:
            amount = sum((Decimal(str(line.balance)) for line in move.line_ids if line.account_id in cash_accounts), Decimal("0"))
            allocations = self.env["thirdcode.cash.flow.allocation"].search([("move_id", "=", move.id)])
            if allocations:
                allocated = sum((Decimal(str(row.amount)) for row in allocations), Decimal(0))
                if self.company_id.currency_id.compare_amounts(float(allocated), float(amount)):
                    groups["unclassified"].append({"code": move.name, "name": "Allocation total does not match cash movement", "amount": self._amount(amount)})
                else:
                    for allocation in allocations:
                        groups[allocation.category].append({"code": move.name, "name": allocation.explanation, "amount": self._amount(Decimal(str(allocation.amount)))})
                continue
            counterparts = move.line_ids.filtered(lambda line: line.account_id not in cash_accounts and line.balance)
            if not amount:
                if counterparts:
                    groups["unclassified"].append({"code": move.name, "name": "Review offsetting cash flows and allocate gross inflows/outflows", "amount": "0.00"})
                continue  # Pure transfers between included cash accounts.
            categories = set(counterparts.mapped("account_id.thirdcode_cash_flow_category"))
            category = next(iter(categories)) if len(categories) == 1 and False not in categories else "unclassified"
            groups[category].append({"code": move.name, "name": move.ref or move.name, "amount": self._amount(amount)})
        opening_domain = [("company_id", "=", self.company_id.id), ("date", "<", self.date_from),
                          ("account_id", "in", cash_accounts.ids)]
        if self.target_move == "posted":
            opening_domain.append(("parent_state", "=", "posted"))
        opening = sum(self._account_totals(opening_domain).values(), Decimal("0"))
        closing_domain = self._move_line_domain(balance_sheet=True) + [("account_id", "in", cash_accounts.ids)]
        closing = sum(self._account_totals(closing_domain).values(), Decimal("0"))
        movement = sum((Decimal(row["amount"].replace(",", "")) for rows in groups.values() for row in rows), Decimal("0"))
        sections = [self._section(label, groups[key]) for key, label in (
            ("operating", "Operating activities"), ("investing", "Investing activities"),
            ("financing", "Financing activities"), ("unclassified", "Classification or allocation required"))]
        return sections, {
            "opening_cash": self._amount(opening), "closing_cash": self._amount(closing),
            "cash_movement": self._amount(movement), "cash_reconciliation_difference": self._amount(closing - opening - movement),
            "classification_complete": not groups["unclassified"],
            "unclassified_count": len(groups["unclassified"]),
        }

    def get_report_data(self):
        self.ensure_one()
        self._check_report_access()
        balance_check = None
        net_result = None
        cash_data = {}
        if self.report_type == "balance_sheet":
            totals = self._account_totals(self._move_line_domain(balance_sheet=True))
            sections = [
                self._section("Assets", self._lines_for_group(totals, {"asset"})),
                self._section(
                    "Liabilities",
                    self._lines_for_group(totals, {"liability"}, normalize=True),
                ),
                self._section(
                    "Equity", self._lines_for_group(totals, {"equity"}, normalize=True)
                ),
            ]
            earnings = sum(
                (
                    balance
                    for account, balance in totals.items()
                    if account.internal_group in {"income", "expense"}
                ),
                Decimal("0"),
            )
            if abs(earnings) >= Decimal("0.005"):
                sections.append(
                    self._section(
                        "Current period earnings",
                        [
                            {
                                "code": "",
                                "name": "Current period earnings",
                                "amount": self._amount(-earnings),
                            }
                        ],
                    )
                )
            balance_check = Decimal(sections[0]["total"].replace(",", "")) - sum(
                (
                    Decimal(section["total"].replace(",", ""))
                    for section in sections[1:]
                ),
                Decimal("0"),
            )
        elif self.report_type == "profit_loss":
            totals = self._account_totals(self._move_line_domain())
            sections = [
                self._section(
                    "Income", self._lines_for_group(totals, {"income"}, normalize=True)
                ),
                self._section("Expenses", self._lines_for_group(totals, {"expense"})),
            ]
            net_result = Decimal(sections[0]["total"].replace(",", "")) - Decimal(
                sections[1]["total"].replace(",", "")
            )
        else:
            sections, cash_data = self._cash_flow_sections()
        report_type = dict(self._fields["report_type"]._description_selection(self.env))
        target_move = dict(self._fields["target_move"]._description_selection(self.env))
        result = {
            "title": report_type.get(self.report_type),
            "date_from": self.date_from,
            "date_to": self.date_to,
            "target_move": target_move.get(self.target_move),
            "layout_status": (
                "TRIAL COPY - client acceptance pending"
                if self.company_id.thirdcode_trial_mode
                else (
                    "Approved layout"
                    if self.company_id._thirdcode_approved_sample("financial")
                    else "DRAFT LAYOUT - client sample approval pending"
                )
            ),
            "sections": sections,
            "balance_check": self._amount(balance_check) if balance_check is not None else False,
            "balanced": balance_check is not None and abs(balance_check) < Decimal("0.005"),
            "net_result": self._amount(net_result) if net_result is not None else False,
        }
        result.update(cash_data)
        result["comparison"] = False
        if self.comparison_date_from:
            comparison = self.copy({
                "date_from": self.comparison_date_from, "date_to": self.comparison_date_to,
                "comparison_date_from": False, "comparison_date_to": False,
            })
            result["comparison"] = comparison.get_report_data()
        return result

    def action_export_pdf(self):
        self.ensure_one()
        self._check_report_access()
        return self.env.ref(
            "thirdcode_accounting.action_report_thirdcode_financial_statement"
        ).report_action(self)


class ReportThirdCodeFinancialStatement(models.AbstractModel):
    _name = "report.thirdcode_accounting.report_thirdcode_financial_statement"
    _description = "Third Code Financial Statement PDF"
    _auto = False
    _table = "tc_financial_report"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env["thirdcode.financial.report.wizard"].browse(docids)
        return {
            "doc_ids": docs.ids,
            "doc_model": "thirdcode.financial.report.wizard",
            "docs": docs,
        }


class CashFlowAccount(models.Model):
    _inherit = "account.account"

    thirdcode_cash_flow_category = fields.Selection([
        ("operating", "Operating"), ("investing", "Investing"), ("financing", "Financing"),
    ], string="Cash flow counterpart category", copy=False)
    thirdcode_cash_equivalent = fields.Boolean(string="Include as cash equivalent", copy=False)
