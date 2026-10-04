from collections import defaultdict
from decimal import Decimal

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class CashFlowAllocation(models.Model):
    _name = "thirdcode.cash.flow.allocation"
    _description = "Reviewed cash flow allocation"
    _check_company_auto = True

    move_id = fields.Many2one("account.move", required=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="move_id.company_id", store=True, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    category = fields.Selection([(key, key.title()) for key in ("operating", "investing", "financing")], required=True)
    amount = fields.Monetary(required=True, currency_field="currency_id", help="Signed cash inflow or outflow. All allocations for the entry must equal its net cash movement.")
    explanation = fields.Char(required=True)

    @api.constrains("move_id", "amount")
    def _check_posted_move(self):
        for allocation in self:
            if allocation.move_id.state != "posted" or not allocation.amount:
                raise ValidationError(_("Allocate a nonzero cash amount from a posted entry."))


class TaxSummaryClassification(models.Model):
    _inherit = "account.tax"

    thirdcode_summary_kind = fields.Selection([
        ("vat", "VAT"), ("withholding", "Withholding"), ("other", "Other tax"),
    ], string="Ledger tax summary classification", copy=False,
       help="Configure with the client's accountant. This classification does not change tax computation.")


class LedgerTaxSummary(models.TransientModel):
    _name = "thirdcode.tax.summary.wizard"
    _inherit = "thirdcode.report.access.mixin"
    _description = "Ledger VAT and withholding summary"

    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    date_from = fields.Date(required=True, default=lambda self: self._thirdcode_default_fiscal_year_start())
    date_to = fields.Date(required=True, default=fields.Date.context_today)
    summary_kind = fields.Selection([("vat", "VAT"), ("withholding", "Withholding")], required=True, default="vat")

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for wizard in self:
            if wizard.date_from > wizard.date_to:
                raise ValidationError(_("The start date must precede the end date."))

    def get_report_data(self):
        self.ensure_one()
        self._thirdcode_check_report_access()
        tax_lines = self.env["account.move.line"].search([
            ("company_id", "=", self.company_id.id), ("parent_state", "=", "posted"),
            ("date", ">=", self.date_from), ("date", "<=", self.date_to), ("tax_line_id", "!=", False),
        ], order="date, move_id, id")
        groups = defaultdict(lambda: {"amount": Decimal(0), "base": Decimal(0), "lines": []})
        unclassified = tax_lines.filtered(lambda line: not line.tax_line_id.thirdcode_summary_kind)
        for line in tax_lines.filtered(lambda line: line.tax_line_id.thirdcode_summary_kind == self.summary_kind):
            key = (line.move_id.id, line.tax_line_id.id)
            group = groups[key]
            sign = -1 if line.tax_line_id.type_tax_use == "sale" else 1
            signed = Decimal(str(line.balance)) * sign
            group["amount"] += signed
            # Repartition lines may repeat the same base; count it once per
            # document/tax rather than multiplying it by repartition count.
            base = abs(Decimal(str(line.tax_base_amount)))
            group["base"] = max(group["base"], base)
            group["lines"].append(line)
        rows = []
        for group in groups.values():
            line = group["lines"][0]
            base = group["base"] * (-1 if line.move_id.move_type in {"out_refund", "in_refund"} else 1)
            rows.append({"document": line.move_id.name, "date": str(line.date), "partner": line.partner_id.name or "",
                "tax": line.tax_line_id.name, "base": f"{base:,.2f}", "amount": f"{group['amount']:,.2f}",
                "ledger_line_ids": [item.id for item in group["lines"]]})
        return {"rows": rows, "tax_total": f"{sum((group['amount'] for group in groups.values()), Decimal(0)):,.2f}",
                "unclassified_count": len(unclassified), "classification_complete": not unclassified,
                "status": "Provisional ledger summary — client tax classification and statutory format review required"}

    def action_export_pdf(self):
        self._thirdcode_check_report_access()
        return self.env.ref("thirdcode_accounting.action_report_thirdcode_tax_summary").report_action(self)


class BankSummary(models.Model):
    _inherit = "thirdcode.bank.reconciliation"

    def action_print_summary(self):
        self.check_access("read")
        if any(record.company_id not in self.env.companies for record in self):
            raise AccessError(_("Select an active company."))
        return self.env.ref("thirdcode_accounting.action_report_thirdcode_bank_summary").report_action(self)

    def get_summary_data(self):
        self.ensure_one()
        self.check_access("read")
        if self.company_id not in self.env.companies:
            raise AccessError(_("Select an active company."))
        return {"current_ledger_balance": self._posted_ledger_balance(),
                "ledger_changed": bool(self.currency_id.compare_amounts(self.ledger_balance, self._posted_ledger_balance())),
                "lines": self.bank_statement_line_ids.sorted(lambda line: (line.date, line.id))}


class ActivityStatementRunningBalance(models.AbstractModel):
    _inherit = "report.partner_statement.activity_statement"

    def _get_report_values(self, docids, data=None):
        result = super()._get_report_values(docids, data=data)
        if not result.get("is_detailed"):
            for partner in result["data"].values():
                for currency in partner["currencies"].values():
                    # OCA's line.balance is cumulative period activity and
                    # excludes balance forward. Include that opening here.
                    running = Decimal(str(currency["balance_forward"]))
                    for line in currency["lines"]:
                        running += Decimal(str(line["amount"]))
                        line["thirdcode_running_balance"] = float(running)
        return result
