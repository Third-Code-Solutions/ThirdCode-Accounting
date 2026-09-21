from odoo import _, api, models
from odoo.exceptions import AccessError


class ThirdCodeReportAccessMixin(models.AbstractModel):
    """Enforce the provisional role matrix on transient report wizards."""

    _name = "thirdcode.report.access.mixin"
    _description = "Third Code report role access mixin"

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

    @api.model_create_multi
    def create(self, vals_list):
        self._thirdcode_check_report_access()
        return super().create(vals_list)

    def button_export_pdf(self, *args, **kwargs):
        self._thirdcode_check_report_access()
        return super().button_export_pdf(*args, **kwargs)

    def button_export_xlsx(self, *args, **kwargs):
        self._thirdcode_check_report_access()
        return super().button_export_xlsx(*args, **kwargs)


class AgedPartnerBalanceReportWizard(models.TransientModel):
    _name = "aged.partner.balance.report.wizard"
    _inherit = ["aged.partner.balance.report.wizard", "thirdcode.report.access.mixin"]


class GeneralLedgerReportWizard(models.TransientModel):
    _name = "general.ledger.report.wizard"
    _inherit = ["general.ledger.report.wizard", "thirdcode.report.access.mixin"]


class JournalLedgerReportWizard(models.TransientModel):
    _name = "journal.ledger.report.wizard"
    _inherit = ["journal.ledger.report.wizard", "thirdcode.report.access.mixin"]


class OpenItemsReportWizard(models.TransientModel):
    _name = "open.items.report.wizard"
    _inherit = ["open.items.report.wizard", "thirdcode.report.access.mixin"]


class TrialBalanceReportWizard(models.TransientModel):
    _name = "trial.balance.report.wizard"
    _inherit = ["trial.balance.report.wizard", "thirdcode.report.access.mixin"]


class VatReportWizard(models.TransientModel):
    _name = "vat.report.wizard"
    _inherit = ["vat.report.wizard", "thirdcode.report.access.mixin"]


class ActivityStatementWizard(models.TransientModel):
    _name = "activity.statement.wizard"
    _inherit = ["activity.statement.wizard", "thirdcode.report.access.mixin"]
