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
            ("cash_flow", "Cash movement"),
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
    target_move = fields.Selection(
        [("posted", "Posted entries only"), ("all", "All entries")],
        required=True,
        default="posted",
    )
    report_status = fields.Selection(
        selection=[("draft", "Draft layout"), ("approved", "Approved layout")],
        compute="_compute_report_status",
        string="Layout status",
    )

    @api.depends("company_id.thirdcode_report_samples_approved")
    def _compute_report_status(self):
        for wizard in self:
            wizard.report_status = (
                "approved"
                if wizard.company_id.thirdcode_report_samples_approved
                else "draft"
            )

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for wizard in self:
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

    @api.model_create_multi
    def create(self, vals_list):
        self._check_report_access()
        return super().create(vals_list)

    def _move_line_domain(self, balance_sheet=False):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id),
            ("date", "<=", self.date_to),
        ]
        if not balance_sheet:
            domain.append(("date", ">=", self.date_from))
        if self.target_move == "posted":
            domain.append(("parent_state", "=", "posted"))
        return domain

    def _account_totals(self, domain):
        totals = defaultdict(lambda: Decimal("0"))
        for line in self.env["account.move.line"].search(domain):
            totals[line.account_id] += Decimal(str(line.debit - line.credit))
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

    def get_report_data(self):
        self.ensure_one()
        self._check_report_access()
        balance_check = None
        net_result = None
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
            totals = self._account_totals(self._move_line_domain())
            rows = []
            for account, balance in sorted(
                totals.items(), key=lambda item: (item[0].code or "", item[0].id)
            ):
                if account.account_type != "asset_cash" or abs(balance) < Decimal("0.005"):
                    continue
                rows.append(
                    {
                        "code": account.code or "",
                        "name": account.name,
                        "amount": self._amount(balance),
                    }
                )
            sections = [self._section("Cash and bank movement", rows)]
        report_type = dict(self._fields["report_type"]._description_selection(self.env))
        target_move = dict(self._fields["target_move"]._description_selection(self.env))
        return {
            "title": report_type.get(self.report_type),
            "date_from": self.date_from,
            "date_to": self.date_to,
            "target_move": target_move.get(self.target_move),
            "layout_status": "Approved layout"
            if self.company_id.thirdcode_report_samples_approved
            else "DRAFT LAYOUT - client sample approval pending",
            "sections": sections,
            "balance_check": self._amount(balance_check) if balance_check is not None else False,
            "balanced": balance_check is not None and abs(balance_check) < Decimal("0.005"),
            "net_result": self._amount(net_result) if net_result is not None else False,
        }

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
