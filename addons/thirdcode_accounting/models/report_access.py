from odoo import _, api, fields, models, Command
from odoo.exceptions import AccessError
from odoo.tools import date_utils


class ThirdCodeReportAccessMixin(models.AbstractModel):
    """Enforce the provisional role matrix on transient report wizards."""

    _name = "thirdcode.report.access.mixin"
    _description = "Third Code report role access mixin"

    @api.model
    def _thirdcode_default_fiscal_year_start(self):
        company = self.env.company
        date_from, _date_to = date_utils.get_fiscal_year(
            fields.Date.context_today(self),
            day=company.fiscalyear_last_day,
            month=int(company.fiscalyear_last_month),
        )
        return date_from

    @api.model
    def _thirdcode_reconcilable_account_ids(self, company_id=None):
        company_id = company_id or self.env.company.id
        if company_id not in self.env.companies.ids:
            return []
        return self.env["account.account"].search(
            [
                ("company_ids", "in", [company_id]),
                ("reconcile", "=", True),
            ]
        ).ids

    def _thirdcode_check_report_access(self):
        user = self.env.user
        if user.has_group("thirdcode_accounting.group_thirdcode_encoder") and not (
            user.has_group("thirdcode_accounting.group_thirdcode_accountant")
            or user.has_group("thirdcode_accounting.group_thirdcode_administrator")
        ):
            raise AccessError(
                _(
                    "Encoder users may prepare drafts, but may not run accounting reports."
                )
            )
        for wizard in self:
            company_ids = set()
            if "company_id" in wizard._fields and wizard.company_id:
                company_ids.add(wizard.company_id.id)
            if "company_ids" in wizard._fields:
                company_ids.update(wizard.company_ids.ids)
            if not company_ids.issubset(set(self.env.companies.ids)):
                raise AccessError(_("You may only run reports for active companies."))

    @api.model_create_multi
    def create(self, vals_list):
        self._thirdcode_check_report_access()
        wizards = super().create(vals_list)
        wizards._thirdcode_check_report_access()
        return wizards

    def button_export_pdf(self, *args, **kwargs):
        self._thirdcode_check_report_access()
        return super().button_export_pdf(*args, **kwargs)

    def button_export_xlsx(self, *args, **kwargs):
        self._thirdcode_check_report_access()
        return super().button_export_xlsx(*args, **kwargs)


class AgedPartnerBalanceReportWizard(models.TransientModel):
    _name = "aged.partner.balance.report.wizard"
    _inherit = ["aged.partner.balance.report.wizard", "thirdcode.report.access.mixin"]

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if "account_ids" in fields_list and not values.get("account_ids"):
            company_id = values.get("company_id") or self.env.company.id
            values["account_ids"] = [
                Command.set(self._thirdcode_reconcilable_account_ids(company_id))
            ]
        return values

    @api.onchange("receivable_accounts_only", "payable_accounts_only")
    def onchange_type_accounts_only(self):
        if self.receivable_accounts_only or self.payable_accounts_only:
            return super().onchange_type_accounts_only()

        company_id = self.company_id.id if self.company_id else self.env.company.id
        self.account_ids = self._thirdcode_reconcilable_account_ids(company_id)


class GeneralLedgerReportWizard(models.TransientModel):
    _name = "general.ledger.report.wizard"
    _inherit = ["general.ledger.report.wizard", "thirdcode.report.access.mixin"]


class JournalLedgerReportWizard(models.TransientModel):
    _name = "journal.ledger.report.wizard"
    _inherit = ["journal.ledger.report.wizard", "thirdcode.report.access.mixin"]

    date_from = fields.Date(
        required=True,
        default=lambda self: self._thirdcode_default_fiscal_year_start(),
    )
    date_to = fields.Date(required=True, default=fields.Date.context_today)

    @api.onchange("date_range_id")
    def onchange_date_range_id(self):
        if self.date_range_id:
            self.date_from = self.date_range_id.date_start
            self.date_to = self.date_range_id.date_end


class OpenItemsReportWizard(models.TransientModel):
    _name = "open.items.report.wizard"
    _inherit = ["open.items.report.wizard", "thirdcode.report.access.mixin"]

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if "account_ids" not in fields_list or values.get("account_ids"):
            return values

        company_id = values.get("company_id") or self.env.company.id
        values["account_ids"] = [
            Command.set(self._thirdcode_reconcilable_account_ids(company_id))
        ]
        return values

    @api.onchange("receivable_accounts_only", "payable_accounts_only")
    def onchange_type_accounts_only(self):
        if self.receivable_accounts_only or self.payable_accounts_only:
            return super().onchange_type_accounts_only()

        company_id = self.company_id.id if self.company_id else self.env.company.id
        self.account_ids = self._thirdcode_reconcilable_account_ids(company_id)


class TrialBalanceReportWizard(models.TransientModel):
    _name = "trial.balance.report.wizard"
    _inherit = ["trial.balance.report.wizard", "thirdcode.report.access.mixin"]

    date_from = fields.Date(
        required=True,
        default=lambda self: self._thirdcode_default_fiscal_year_start(),
    )
    date_to = fields.Date(required=True, default=fields.Date.context_today)

    @api.onchange("date_range_id")
    def onchange_date_range_id(self):
        if self.date_range_id:
            self.date_from = self.date_range_id.date_start
            self.date_to = self.date_range_id.date_end


class VatReportWizard(models.TransientModel):
    _name = "vat.report.wizard"
    _inherit = ["vat.report.wizard", "thirdcode.report.access.mixin"]


class ActivityStatementWizard(models.TransientModel):
    _name = "activity.statement.wizard"
    _inherit = ["activity.statement.wizard", "thirdcode.report.access.mixin"]
