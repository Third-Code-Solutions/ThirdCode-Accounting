from odoo import models


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def action_create_payments(self):
        """Allow the native wizard to link a payment to a posted invoice.

        Odoo stores that link in ``account.move.matched_payment_ids``.  It is
        reconciliation metadata, not a journal-line edit, but the accounting
        immutability guard must receive an explicit context marker before
        allowing the native wizard to write it.
        """
        return super(
            AccountPaymentRegister,
            self.with_context(thirdcode_allow_reconciliation_metadata=True),
        ).action_create_payments()

    def _reconcile_payments(self, to_process, edit_mode=False):
        context = dict(self.env.context)
        context["thirdcode_allow_reconciliation_metadata"] = True
        prepared = []
        for values in to_process:
            values = dict(values)
            values["to_reconcile"] = values["to_reconcile"].with_context(**context)
            prepared.append(values)
        return super(
            AccountPaymentRegister,
            self.with_context(**context),
        )._reconcile_payments(prepared, edit_mode=edit_mode)
