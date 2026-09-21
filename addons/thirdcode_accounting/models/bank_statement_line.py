from odoo import api, fields, models


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    thirdcode_reconciliation_id = fields.Many2one(
        "thirdcode.bank.reconciliation", string="Third Code reconciliation", copy=False
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

    @api.depends("is_reconciled")
    def _compute_thirdcode_reconciliation_status(self):
        for line in self:
            line.thirdcode_reconciliation_status = (
                "reconciled" if line.is_reconciled else "unreconciled"
            )
