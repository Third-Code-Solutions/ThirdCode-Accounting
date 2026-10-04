"""Authentication hardening for ``res.users``.

Three production findings are fixed here:

* H1 - login timing oracle. ``res.users._login`` raises ``AccessDenied`` for an
  unknown login *before* any password hash is computed, so an unknown account
  answers ~2.7x faster than a known one (measured 250 ms vs 666 ms). The
  override computes a throw-away hash for unresolvable logins so both branches
  pay the same cost.
* H2 - password-reset enumeration. ``auth_signup``'s ``reset_password`` raises
  ``Exception('No account found for this login')`` and
  ``UserError('Cannot send email: user <display name> has no email address.')``;
  the controller renders both to the visitor. The override answers uniformly
  and records the detail server-side only.
* H3 - no shared throttling. ``_assert_can_auth`` is extended with the
  database-backed counter (see ``thirdcode.auth.throttle``), which also covers
  logins that never resolve to a user record.
"""

import contextlib
import logging

from odoo import SUPERUSER_ID, _, api, models
from odoo.exceptions import AccessDenied
from odoo.http import request

_logger = logging.getLogger(__name__)

IP_SCOPE = "login-ip"
LOGIN_SCOPE = "login-user"

MAX_FAILURES_PARAM = "tcsi.auth.max_failures"
WINDOW_PARAM = "tcsi.auth.window_seconds"
BLOCK_PARAM = "tcsi.auth.block_seconds"
LOGIN_MAX_FAILURES_PARAM = "tcsi.auth.login_max_failures"
LOGIN_BLOCK_PARAM = "tcsi.auth.login_block_seconds"
ALLOW_IPS_PARAM = "tcsi.auth.allow_ips"

DEFAULT_MAX_FAILURES = 10
DEFAULT_WINDOW_SECONDS = 900
DEFAULT_BLOCK_SECONDS = 900
DEFAULT_LOGIN_MAX_FAILURES = 5
DEFAULT_LOGIN_BLOCK_SECONDS = 900


class ResUsers(models.Model):
    _inherit = "res.users"

    # ------------------------------------------------------------------
    # H3 - shared, database-backed throttle
    # ------------------------------------------------------------------
    def _tcsi_client_ip(self):
        """Best-effort client address for the current request."""
        try:
            if request:
                return request.httprequest.remote_addr or "unknown"
        except Exception:  # noqa: BLE001 - never let logging break authentication
            pass
        return "unknown"

    def _tcsi_login_key(self, user):
        """Normalise the ``_assert_can_auth`` argument into a counter key."""
        if user is None:
            return None
        if isinstance(user, int):
            return "uid:%s" % user
        return "login:%s" % str(user).strip().lower()

    def _tcsi_allowlisted(self):
        """Whether the current client address is exempt from the throttle."""
        try:
            raw = self.env["ir.config_parameter"].sudo().get_param(ALLOW_IPS_PARAM, "") or ""
        except Exception:  # noqa: BLE001
            return False
        entries = {item.strip() for item in raw.split(",") if item.strip()}
        if not entries:
            return False
        return self._tcsi_client_ip() in entries

    @contextlib.contextmanager
    def _assert_can_auth(self, user=None):
        limiter = self.env["thirdcode.auth.throttle"].sudo()
        ip = self._tcsi_client_ip()
        login_key = self._tcsi_login_key(user)
        if not self._tcsi_allowlisted():
            try:
                limiter._tcsi_assert_allowed(
                    [
                        pair
                        for pair in ((ip, IP_SCOPE), (login_key, LOGIN_SCOPE))
                        if pair[0]
                    ]
                )
            except AccessDenied:
                raise
            except Exception:  # noqa: BLE001 - fail open, never lock the pilot out
                _logger.exception("TCSI auth throttle: cooldown check failed")
        try:
            with super()._assert_can_auth(user=user):
                yield
        except AccessDenied:
            self._tcsi_record_failure(limiter, ip, login_key)
            raise
        else:
            self._tcsi_record_success(limiter, ip, login_key)

    def _tcsi_record_failure(self, limiter, ip, login_key):
        if self._tcsi_allowlisted():
            return
        try:
            if ip:
                limiter._tcsi_register_failure(
                    ip,
                    IP_SCOPE,
                    limiter._tcsi_param(MAX_FAILURES_PARAM, DEFAULT_MAX_FAILURES),
                    limiter._tcsi_param(WINDOW_PARAM, DEFAULT_WINDOW_SECONDS),
                    limiter._tcsi_param(BLOCK_PARAM, DEFAULT_BLOCK_SECONDS),
                )
            if login_key:
                limiter._tcsi_register_failure(
                    login_key,
                    LOGIN_SCOPE,
                    limiter._tcsi_param(LOGIN_MAX_FAILURES_PARAM, DEFAULT_LOGIN_MAX_FAILURES),
                    limiter._tcsi_param(WINDOW_PARAM, DEFAULT_WINDOW_SECONDS),
                    limiter._tcsi_param(LOGIN_BLOCK_PARAM, DEFAULT_LOGIN_BLOCK_SECONDS),
                )
        except Exception:  # noqa: BLE001 - counting must never mask the failure
            _logger.exception("TCSI auth throttle: could not record a failure")

    def _tcsi_record_success(self, limiter, ip, login_key):
        try:
            for key, scope in ((ip, IP_SCOPE), (login_key, LOGIN_SCOPE)):
                if key:
                    limiter._tcsi_register_success(key, scope)
        except Exception:  # noqa: BLE001
            _logger.exception("TCSI auth throttle: could not clear a counter")

    # ------------------------------------------------------------------
    # H1 - constant-cost login for unknown accounts
    # ------------------------------------------------------------------
    @classmethod
    def _tcsi_login_exists(cls, db, login):
        """Whether ``login`` resolves to an account (by login or by email)."""
        try:
            with cls.pool.cursor() as cr:
                users = api.Environment(cr, SUPERUSER_ID, {})[cls._name]
                domain = users._get_login_domain(login)
                if users.sudo().search(domain, order=users._get_login_order(), limit=1):
                    return True
                return bool(
                    users.sudo().search(
                        users._get_email_domain(login),
                        order=users._get_login_order(),
                        limit=1,
                    )
                )
        except Exception:  # noqa: BLE001 - on error keep upstream behaviour
            _logger.exception("TCSI login hardening: account lookup failed")
            return True

    @classmethod
    def _tcsi_burn_password_hash(cls, password):
        """Pay the same password-hashing cost as a real credential check."""
        try:
            with cls.pool.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                env["res.users"]._crypt_context().hash(password or "")
        except Exception:  # noqa: BLE001 - timing hardening must never block login
            _logger.exception("TCSI login hardening: dummy hash failed")

    @classmethod
    def _login(cls, db, credential, user_agent_env):
        login = (credential or {}).get("login")
        if login and not cls._tcsi_login_exists(db, login):
            # Unknown account: upstream would return after a single SELECT.
            # Burn a hash so the response time matches the known-account path.
            cls._tcsi_burn_password_hash((credential or {}).get("password"))
        return super()._login(db, credential, user_agent_env)

    # ------------------------------------------------------------------
    # H2 - uniform password reset (no account enumeration)
    # ------------------------------------------------------------------
    def reset_password(self, login):
        """Reset silently and identically for every login.

        The caller (``/web/reset_password``) shows the generic "instructions
        sent" message whenever no exception escapes, so an unknown login, a
        login with several matches and a user without an email address all look
        exactly like a successful reset. The detail is logged for operators.
        """
        try:
            return super().reset_password(login)
        except Exception as exc:  # noqa: BLE001 - deliberately uniform response
            _logger.warning(
                "TCSI password reset: no email sent for login %r (%s: %s)",
                login,
                type(exc).__name__,
                exc,
            )
            return False
