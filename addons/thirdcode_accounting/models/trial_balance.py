"""Keep interactive trial-balance links equal to the report's native source domains."""
from functools import partial

from odoo import _, fields, models
from odoo.exceptions import AccessError
from odoo.osv import expression


class TrialBalanceSources(models.AbstractModel):
    _inherit = "report.account_financial_report.trial_balance"

    def _get_report_values(self, docids, data):
        wizard = self.env["trial.balance.report.wizard"].browse(data["wizard_id"])
        wizard.check_access("read")
        wizard._thirdcode_check_report_access()
        if data["company_id"] not in self.env.companies.ids:
            raise AccessError(_("You may only run reports for active companies."))
        result = super()._get_report_values(docids, data)
        common = [data["account_ids"], data["journal_ids"], data["partner_ids"], data["company_id"]]
        flags = [data["only_posted_moves"], data["show_partner_details"]]
        start, end, fiscal = (fields.Date.to_string(fields.Date.to_date(data[key])) for key in ("date_from", "date_to", "fy_start_date"))
        # Prepare once, not once per rendered amount/account.
        opening = expression.OR([
            self._get_initial_balances_bs_ml_domain(*common, start, *flags),
            self._get_initial_balances_pl_ml_domain(*common, start, *flags, fiscal),
        ])
        period = self._get_period_ml_domain(*common, end, start, *flags)
        carried_profit = self._get_initial_balance_fy_pl_ml_domain(*common, fiscal, *flags)
        result["thirdcode_source_domain"] = partial(
            self._thirdcode_source_domain, opening, period, carried_profit,
            data["unaffected_earnings_account"] if not data["account_ids"] else False,
        )
        return result

    @staticmethod
    def _thirdcode_source_domain(opening, period, carried_profit, earnings_id, original, metric, extra):
        account_filter = [term for term in original if term[0] == "account_id"]
        selected = set()
        for _name, operator, value in account_filter:
            selected.update([value] if operator == "=" else value)
        row_filter = [term for term in original if term[0] == "partner_id"] + extra
        initial = expression.AND([opening, account_filter])
        if earnings_id and earnings_id in selected:
            initial = expression.OR([initial, carried_profit])
        activity = expression.AND([period, account_filter])
        if metric == "initial":
            domain = initial
        elif metric == "ending":
            domain = expression.OR([initial, activity])
        else:
            domain = expression.AND([activity, [term for term in original if term[0] in {"debit", "credit", "balance"}]])
        return expression.AND([domain, row_filter])
