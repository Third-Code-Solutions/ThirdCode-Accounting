"""Unforgeable tokens for narrowly scoped native metadata writes."""

RECEIPT_NUMBER_TOKEN = object()
RECURRING_MOVE_TOKEN = object()
# Passed inside the batch posting flow after the Administrator approval gate;
# lets the created payment pass the company approval threshold control.
PAYMENT_APPROVAL_TOKEN = object()
