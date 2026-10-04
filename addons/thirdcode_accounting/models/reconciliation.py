from odoo import _, api, models
from odoo.exceptions import UserError

from .account_move import _RECONCILIATION_METADATA_TOKEN


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    @api.model
    def _update_matching_number(self, amls):
        controlled = amls.with_context(thirdcode_reconciliation_metadata_token=_RECONCILIATION_METADATA_TOKEN)
        return super()._update_matching_number(controlled)

    def _thirdcode_check_period(self):
        for partial in self:
            self.env["thirdcode.accounting.period"]._check_date_allowed(
                partial.company_id, partial.max_date
            )

    @api.model_create_multi
    def create(self, vals_list):
        # A payment in an open period may settle an older invoice. The native
        # max_date is the effective reconciliation date used by ageing reports.
        for vals in vals_list:
            lines = self.env["account.move.line"].browse([
                vals.get("debit_move_id"), vals.get("credit_move_id")
            ]).exists()
            if lines:
                self.env["thirdcode.accounting.period"]._check_date_allowed(
                    lines[0].company_id, max(lines.mapped("date"))
                )
        return super().create(vals_list)

    def write(self, vals):
        if {"debit_move_id", "credit_move_id", "amount", "debit_amount_currency",
            "credit_amount_currency", "max_date", "company_id"}.intersection(vals):
            raise UserError(_("Reconciliation amounts cannot be edited. Undo and reconcile again in an open period."))
        return super().write(vals)

    def unlink(self):
        self._thirdcode_check_period()
        return super().unlink()


class AccountFullReconcile(models.Model):
    _inherit = "account.full.reconcile"

    def unlink(self):
        self.partial_reconcile_ids._thirdcode_check_period()
        return super().unlink()
