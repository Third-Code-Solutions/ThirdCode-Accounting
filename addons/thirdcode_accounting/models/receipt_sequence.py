from odoo import _, models
from odoo.exceptions import UserError

from .write_tokens import RECEIPT_NUMBER_TOKEN


class ReceiptSequence(models.Model):
    _inherit = "ir.sequence"

    def init(self):
        # Fail the upgrade for duplicate existing company sequences; never
        # silently merge or renumber historical receipts.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS thirdcode_receipt_company_sequence
            ON ir_sequence (company_id)
            WHERE code = 'thirdcode.official.receipt' AND company_id IS NOT NULL
        """)

    def _next(self, sequence_date=None):
        if any(seq.code == "thirdcode.official.receipt" for seq in self):
            if self.env.context.get("thirdcode_receipt_number_token") is not RECEIPT_NUMBER_TOKEN:
                raise UserError(_("Receipt numbers may only be consumed when issuing a posted receipt."))
        return super()._next(sequence_date=sequence_date)

    def write(self, vals):
        protected = {"code", "company_id", "implementation", "prefix", "suffix", "padding",
                     "number_next", "number_next_actual", "number_increment", "use_date_range", "active"}
        if protected.intersection(vals) and any(seq.code == "thirdcode.official.receipt" for seq in self):
            raise UserError(_("Receipt series cannot be reset or reconfigured. An approved new-series procedure is required."))
        return super().write(vals)

    def unlink(self):
        if any(seq.code == "thirdcode.official.receipt" for seq in self):
            raise UserError(_("Receipt numbering series must be retained."))
        return super().unlink()
