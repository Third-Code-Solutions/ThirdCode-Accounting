"""Database-backed authentication throttle.

Odoo's stock login cooldown (``res.users._assert_can_auth``) keeps its counters
in ``registry._login_failures``: per-process, non-shared memory. With prefork
workers (the production pilot runs ``workers = 2``) an attacker gets the full
allowance on every worker, and a worker restart clears every counter.

This model stores the counters in the database so the limit is shared by every
worker and survives restarts. It is written to only through ``sudo()`` from the
authentication paths; the ACL keeps it out of the UI for everyone but system
administrators.
"""

import datetime
import logging
import random

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessDenied

_logger = logging.getLogger(__name__)

PRUNE_DAYS = 1
PRUNE_PROBABILITY = 0.05


class ThirdCodeAuthThrottle(models.Model):
    _name = "thirdcode.auth.throttle"
    _description = "TCSI authentication throttle counter"
    _rec_name = "key"
    _order = "blocked_until desc, id desc"
    _sql_constraints = [
        (
            "thirdcode_auth_throttle_key_scope_uniq",
            "unique(key, scope)",
            "A throttle counter already exists for this key.",
        ),
    ]

    key = fields.Char(required=True, index=True, help="Client address or login being counted.")
    scope = fields.Char(required=True, index=True, help="Which limit this counter belongs to.")
    failures = fields.Integer(default=0, readonly=True)
    first_failure = fields.Datetime(readonly=True)
    last_failure = fields.Datetime(readonly=True)
    blocked_until = fields.Datetime(readonly=True, index=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @api.model
    def _tcsi_param(self, name, default):
        """Read an integer System Parameter, falling back to ``default``."""
        try:
            raw = self.env["ir.config_parameter"].sudo().get_param(name, default)
            return int(raw)
        except (TypeError, ValueError):
            _logger.warning("TCSI auth throttle: invalid value for %s, using %s", name, default)
            return int(default)

    @api.model
    def _tcsi_find(self, key, scope):
        return self.sudo().search([("key", "=", key), ("scope", "=", scope)], limit=1)

    @api.model
    def _tcsi_blocked_seconds(self, key, scope):
        """Return the remaining cooldown in seconds, or 0 when not blocked."""
        record = self._tcsi_find(key, scope)
        if not record or not record.blocked_until:
            return 0
        now = fields.Datetime.now()
        if record.blocked_until <= now:
            return 0
        return int((record.blocked_until - now).total_seconds()) + 1

    @api.model
    def _tcsi_prune(self):
        """Opportunistically drop stale counters so the table cannot grow forever."""
        if random.random() >= PRUNE_PROBABILITY:
            return
        cutoff = fields.Datetime.now() - datetime.timedelta(days=PRUNE_DAYS)
        self.sudo().search(
            [("last_failure", "!=", False), ("last_failure", "<", cutoff)]
        ).unlink()

    @api.model
    def _tcsi_commit(self, method, *args):
        """Run a counter update on a cursor of its own and commit it at once.

        The counters have to outlive the caller's transaction: ``res.users._login``
        records a failure inside a cursor that is rolled back the moment
        ``AccessDenied`` leaves its ``with`` block, and any later failure in the
        same request would drop the counter with it. A connection of its own that
        commits immediately keeps the count, and keeps it shared by every prefork
        worker instead of each worker counting in its own memory.
        """
        for attempt in (1, 2):
            try:
                with self.pool.cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    result = getattr(env["thirdcode.auth.throttle"], method)(*args)
                    cr.commit()
                return result
            except Exception:  # noqa: BLE001 - counting must never break the caller
                _logger.exception(
                    "TCSI auth throttle: %s failed (attempt %s)", method, attempt
                )
        return None

    @api.model
    def _tcsi_register_failure(self, key, scope, max_failures, window_seconds, block_seconds):
        """Count one failure and commit it on its own cursor (see ``_tcsi_commit``)."""
        return self._tcsi_commit(
            "_tcsi_register_failure_on",
            key,
            scope,
            max_failures,
            window_seconds,
            block_seconds,
        )

    @api.model
    def _tcsi_register_failure_on(self, key, scope, max_failures, window_seconds, block_seconds):
        """Count one failure; start (or extend) the cooldown once the limit is hit."""
        max_failures = int(max_failures or 0)
        if max_failures <= 0:
            return 0
        now = fields.Datetime.now()
        record = self._tcsi_find(key, scope)
        if not record:
            record = self.sudo().create(
                {"key": key, "scope": scope, "failures": 0, "first_failure": now}
            )
        window = datetime.timedelta(seconds=int(window_seconds or 0))
        failures = record.failures or 0
        first_failure = record.first_failure
        if not first_failure or (window and (now - first_failure) > window):
            # The observation window elapsed: start counting again.
            failures = 0
            first_failure = now
        failures += 1
        values = {"failures": failures, "first_failure": first_failure, "last_failure": now}
        if failures >= max_failures:
            values["blocked_until"] = now + datetime.timedelta(seconds=int(block_seconds or 0))
            _logger.warning(
                "TCSI auth throttle: %s blocked for %s (%s failures on scope %s)",
                key,
                block_seconds,
                failures,
                scope,
            )
        record.write(values)
        self._tcsi_prune()
        return failures

    @api.model
    def _tcsi_register_success(self, key, scope):
        """Clear the counters for a key after a successful authentication.

        Committed on its own cursor (see ``_tcsi_commit``) so that a cleared
        counter cannot be re-instated by a rollback of the surrounding request.
        """
        return self._tcsi_commit("_tcsi_register_success_on", key, scope)

    @api.model
    def _tcsi_register_success_on(self, key, scope):
        record = self._tcsi_find(key, scope)
        if record:
            record.unlink()

    @api.model
    def _tcsi_assert_allowed(self, keys):
        """Raise ``AccessDenied`` when any ``(key, scope)`` pair is on cooldown.

        ``keys`` is an iterable of ``(key, scope)`` pairs.
        """
        blocked = 0
        for key, scope in keys:
            blocked = max(blocked, self._tcsi_blocked_seconds(key, scope))
        if blocked:
            raise AccessDenied(
                _(
                    "Too many failed attempts. Please wait %(seconds)s seconds before trying again.",
                    seconds=blocked,
                )
            )
