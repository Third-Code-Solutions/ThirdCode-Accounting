"""Native Odoo concurrency probes. Run only via odoo shell in tcsi_alignment_ DBs."""
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from odoo import api, Command, SUPERUSER_ID
from odoo.exceptions import UserError
from psycopg2.errors import SerializationFailure

assert env.cr.dbname.startswith("tcsi_alignment_")
registry = env.registry
company_id = env.ref("base.main_company").id
admin = env.ref("base.user_admin")
uid = admin.id
journal = env["account.journal"].search([("company_id", "=", company_id), ("type", "=", "general")], limit=1)
accounts = env["account.account"].search([("company_ids", "in", [company_id]), ("account_type", "=", "expense")], limit=1) | env["account.account"].search([("company_ids", "in", [company_id]), ("account_type", "=", "income")], limit=1)
assert len(accounts) == 2
suffix = uuid.uuid4().hex[:8]
last_period = env["thirdcode.accounting.period"].search([("company_id", "=", company_id)], order="date_end desc", limit=1)
year = max(2040, last_period.date_end.year + 1 if last_period else 2040)
draft_day, close_day = f"{year}-01-01", f"{year}-02-01"
periods = env["thirdcode.accounting.period"].create([
    {"name": "Concurrency draft " + suffix, "company_id": company_id, "date_start": draft_day, "date_end": draft_day},
    {"name": "Concurrency close " + suffix, "company_id": company_id, "date_start": close_day, "date_end": close_day},
])
period_ids = periods.ids
journal_id = journal.id
account_ids = accounts.ids
env.cr.commit()

def move_values(day):
    return {"company_id": company_id, "journal_id": journal_id, "date": day, "ref": "Concurrency " + suffix,
            "line_ids": [Command.create({"account_id": account_ids[0], "debit": 10, "name": "Concurrency"}),
                         Command.create({"account_id": account_ids[1], "credit": 10, "name": "Concurrency"})]}

writer_ready = threading.Event()
close_started = threading.Event()

def draft_writer():
    with registry.cursor() as cr:
        local = api.Environment(cr, uid, {"allowed_company_ids": [company_id]})
        move = local["account.move"].create(move_values(draft_day))
        writer_ready.set()
        assert close_started.wait(10)
        time.sleep(0.15)
        cr.commit()
        return move.id

def close_while_writer_finishes():
    assert writer_ready.wait(10)
    with registry.cursor() as cr:
        local = api.Environment(cr, uid, {"allowed_company_ids": [company_id]})
        period = local["thirdcode.accounting.period"].browse(period_ids[0])
        assert period.state == "open"  # establish a snapshot before writer commits
        close_started.set()
        try:
            period.action_close()
        except UserError as exc:
            assert "draft entry" in str(exc)
            cr.rollback()
            return "blocked_concurrent_draft"
        raise AssertionError("Closed a period while a concurrent draft existed")

with ThreadPoolExecutor(max_workers=2) as pool:
    writer = pool.submit(draft_writer)
    closer = pool.submit(close_while_writer_finishes)
    draft_id, close_result = writer.result(timeout=30), closer.result(timeout=30)

closing = threading.Event()
posting = threading.Event()

def close_before_post():
    with registry.cursor() as cr:
        local = api.Environment(cr, uid, {"allowed_company_ids": [company_id]})
        local["res.company"].browse(company_id)._thirdcode_lock_period_state(exclusive=True)
        closing.set()
        assert posting.wait(10)
        time.sleep(0.15)
        local["thirdcode.accounting.period"].browse(period_ids[1]).action_close()
        cr.commit()
        return "closed"

def post_against_close():
    assert closing.wait(10)
    retries = 0
    for attempt in range(3):
        with registry.cursor() as cr:
            local = api.Environment(cr, uid, {"allowed_company_ids": [company_id]})
            local["account.journal"].browse(journal_id).read(["name"])
            posting.set()
            try:
                move = local["account.move"].create(move_values(close_day))
                move.action_post()
                cr.commit()
            except SerializationFailure:
                cr.rollback()
                retries += 1
                continue
            except UserError as exc:
                assert "closed period" in str(exc)
                cr.rollback()
                return {"result": "blocked_closed_period", "serialization_retries": retries}
            raise AssertionError("Posted after concurrent close")
    raise AssertionError("Retry did not converge")

with ThreadPoolExecutor(max_workers=2) as pool:
    closer = pool.submit(close_before_post)
    poster = pool.submit(post_against_close)
    closed_result, post_result = closer.result(timeout=30), poster.result(timeout=30)

# Receipt assignment after concurrent response retries may never consume another
# number for an already numbered posted payment.
payment = env["account.payment"].search([("company_id", "=", company_id), ("thirdcode_receipt_number", "!=", False)], limit=1)
assert payment
payment_id, original_number = payment.id, payment.thirdcode_receipt_number
sequence = env["res.company"].browse(company_id)._thirdcode_receipt_sequence()
next_before = sequence.number_next_actual
env.cr.commit()

def assign_again():
    for attempt in range(3):
        with registry.cursor() as cr:
            local = api.Environment(cr, uid, {"allowed_company_ids": [company_id]})
            try:
                payment = local["account.payment"].browse(payment_id)
                payment.action_assign_thirdcode_receipt_number()
                result = payment.thirdcode_receipt_number
                cr.commit()
                return result
            except SerializationFailure:
                cr.rollback()
    raise AssertionError("Receipt retry did not converge")

with ThreadPoolExecutor(max_workers=2) as pool:
    numbers = list(pool.map(lambda _: assign_again(), range(2)))
assert numbers == [original_number, original_number]
with registry.cursor() as cr:
    local = api.Environment(cr, SUPERUSER_ID, {})
    assert local["ir.sequence"].browse(sequence.id).number_next_actual == next_before
print("CONCURRENCY_RESULT " + json.dumps({"draft_close": close_result, "post_close": post_result,
    "receipt_retries": "same number; counter unchanged", "dataset": "isolated synthetic", "workers": 2, "test_dates": [draft_day, close_day]}))
