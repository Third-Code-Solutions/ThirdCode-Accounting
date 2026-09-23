from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .write_tokens import BANK_STATEMENT_SYNC_TOKEN


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"
    _check_company_auto = True

    thirdcode_reconciliation_id = fields.Many2one(
        "thirdcode.bank.reconciliation",
        string="Third Code reconciliation",
        copy=False,
        check_company=True,
    )
    thirdcode_reconciliation_status = fields.Selection(
        [
            ("unreconciled", "Unreconciled"),
            ("reconciled", "Reconciled"),
        ],
        compute="_compute_thirdcode_reconciliation_status",
        store=True,
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            reconciliation_ids = {
                values.get("thirdcode_reconciliation_id")
                for values in vals_list
                if values.get("thirdcode_reconciliation_id")
            }
            locked_reconciliations = self.env[
                "thirdcode.bank.reconciliation"
            ].sudo().browse(reconciliation_ids).filtered(
                lambda reconciliation: reconciliation.state == "reconciled"
            )
            if locked_reconciliations:
                raise UserError(
                    _("A signed-off reconciliation cannot accept statement lines. Reopen it first.")
                )
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and vals:
            lines = self.sudo()
            reconciliations = lines.mapped("thirdcode_reconciliation_id")
            if any(reconciliation.state == "reconciled" for reconciliation in reconciliations):
                raise UserError(
                    _("A signed-off reconciliation's statement lines cannot be edited. Reopen it first.")
                )
            if "thirdcode_reconciliation_id" in vals:
                destination_id = vals.get("thirdcode_reconciliation_id") or False
                destination = self.env[
                    "thirdcode.bank.reconciliation"
                ].sudo().browse(destination_id)
                if destination and destination.state == "reconciled" and any(
                    line.thirdcode_reconciliation_id.id != destination.id
                    for line in lines
                ):
                    raise UserError(
                        _("A signed-off reconciliation cannot accept statement lines. Reopen it first.")
                    )
        return super().write(vals)

    def unlink(self):
        if not self.env.su and any(
            reconciliation.state == "reconciled"
            for reconciliation in self.sudo().mapped("thirdcode_reconciliation_id")
        ):
            raise UserError(
                _("A signed-off reconciliation's statement lines cannot be deleted. Reopen it first.")
            )
        if any(line.move_id.state == "posted" for line in self.sudo()):
            raise UserError(
                _("A bank statement line with a posted entry cannot be deleted. Reverse or correct the entry instead.")
            )
        return super().unlink()

    def _synchronize_to_moves(self, changed_fields):
        lines = self.with_context(
            thirdcode_bank_statement_sync_token=BANK_STATEMENT_SYNC_TOKEN
        )
        return super(AccountBankStatementLine, lines)._synchronize_to_moves(
            changed_fields
        )

    @api.depends("is_reconciled")
    def _compute_thirdcode_reconciliation_status(self):
        for line in self:
            line.thirdcode_reconciliation_status = (
                "reconciled" if line.is_reconciled else "unreconciled"
            )
