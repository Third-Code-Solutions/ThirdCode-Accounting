from odoo import models

from .account_move import _RECONCILIATION_METADATA_TOKEN


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def action_create_payments(self):
        """Allow the native wizard to link a payment to a posted invoice.

        Odoo stores that link in ``account.move.matched_payment_ids``.  It is
        reconciliation metadata, not a journal-line edit. A private in-process
        token lets the native wizard make this one controlled update without
        exposing a forgeable RPC context flag.
        """
        return super(
            AccountPaymentRegister,
            self.with_context(
                thirdcode_reconciliation_metadata_token=_RECONCILIATION_METADATA_TOKEN
            ),
        ).action_create_payments()

    def _reconcile_payments(self, to_process, edit_mode=False):
        context = dict(self.env.context)
        context["thirdcode_reconciliation_metadata_token"] = (
            _RECONCILIATION_METADATA_TOKEN
        )
        prepared = []
        for values in to_process:
            values = dict(values)
            values["to_reconcile"] = values["to_reconcile"].with_context(**context)
            prepared.append(values)
        return super(
            AccountPaymentRegister,
            self.with_context(**context),
        )._reconcile_payments(prepared, edit_mode=edit_mode)
