"""Unforgeable tokens for narrowly scoped native metadata writes."""

RECEIPT_NUMBER_TOKEN = object()
# Entered only by the payment batch while posting a batch an administrator has
# approved; lets account.payment post above the threshold on that one path.
PAYMENT_APPROVAL_TOKEN = object()
