"""Operational setup endpoint.

Hardening applied after the production audit (finding M5):

* the accepted token digests are a tuple, so a token can be rotated without a
  code-change window (add the new digest, deploy, verify, then remove the old);
* an optional IP allowlist (``tcsi.setup_allow_ips``) restricts the endpoint to
  known operator addresses;
* a database-backed throttle blocks repeated unauthorised attempts - the stock
  login cooldown cannot cover an ``auth='none'`` route;
* the request body is size-capped before it is parsed.
"""

import hashlib
import hmac
import json
import logging
import traceback

from odoo import SUPERUSER_ID, http
from odoo.http import request

from odoo.addons.thirdcode_accounting.models.setup_service import (
    SETUP_ENTRY_CONTEXT_KEY,
    SETUP_ENTRY_SENTINEL,
)

_logger = logging.getLogger(__name__)

# SHA-256 digests of the operational setup tokens. The plaintext tokens are held
# by the pilot operator (outside the repository) and are required for every call.
_SETUP_TOKEN_SHA256S = (
    "f07adcd6202f89bd091beb906bf552c57039bddfc095cf25323b4837ae69f3e6",
)

_SETUP_SCOPE = "setup-ip"
_SETUP_ALLOW_IPS_PARAM = "tcsi.setup_allow_ips"
# A traceback is only returned when an operator has deliberately enabled it: the
# error text alone is enough to debug a refused action (finding M5).
_SETUP_DEBUG_PARAM = "tcsi.setup_allow_debug"
_MAX_BODY_BYTES = 262144
_DEFAULT_MAX_FAILURES = 5
_DEFAULT_WINDOW_SECONDS = 3600
_DEFAULT_BLOCK_SECONDS = 900


def _token_authorized(token):
    if not token:
        return False
    digest = hashlib.sha256(token.encode()).hexdigest()
    return any(hmac.compare_digest(digest, known) for known in _SETUP_TOKEN_SHA256S)


def _param(name, default):
    try:
        value = request.env["ir.config_parameter"].sudo().get_param(name, default)
    except Exception:  # noqa: BLE001 - a parameter read must never 500 the route
        return default
    return default if value in (None, "") else value


def _param_int(name, default):
    try:
        return int(_param(name, default))
    except (TypeError, ValueError):
        return default


def _param_bool(name, default=False):
    try:
        return str(_param(name, "1" if default else "0")).strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
    except Exception:  # noqa: BLE001 - a parameter read must never 500 the route
        return default


def _ip_allowed(remote_addr):
    """Empty allowlist means "any address" (the token is still required)."""
    raw = str(_param(_SETUP_ALLOW_IPS_PARAM, "") or "")
    entries = {item.strip() for item in raw.split(",") if item.strip()}
    if not entries:
        return True
    return remote_addr in entries


class ThirdCodeSetupController(http.Controller):
    @http.route(
        "/tcsi/setup",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def tcsi_setup(self, **kwargs):
        remote_addr = request.httprequest.remote_addr or "unknown"
        limiter = request.env["thirdcode.auth.throttle"].sudo()

        def reject(status, error):
            limiter._tcsi_register_failure(
                remote_addr,
                _SETUP_SCOPE,
                _param_int("tcsi.setup.max_failures", _DEFAULT_MAX_FAILURES),
                _param_int("tcsi.setup.window_seconds", _DEFAULT_WINDOW_SECONDS),
                _param_int("tcsi.setup.block_seconds", _DEFAULT_BLOCK_SECONDS),
            )
            return request.make_json_response({"ok": False, "error": error}, status=status)

        blocked = limiter._tcsi_blocked_seconds(remote_addr, _SETUP_SCOPE)
        if blocked:
            _logger.warning(
                "TCSI setup: throttled attempt from %s (%s seconds left)",
                remote_addr,
                blocked,
            )
            return request.make_json_response(
                {"ok": False, "error": "too many attempts"}, status=429
            )
        if not _ip_allowed(remote_addr):
            _logger.warning("TCSI setup: address %s is not allowlisted", remote_addr)
            return reject(401, "unauthorized")
        if (request.httprequest.content_length or 0) > _MAX_BODY_BYTES:
            return reject(413, "payload too large")
        try:
            payload = json.loads(request.httprequest.get_data() or b"{}")
        except ValueError:
            return reject(400, "invalid json")
        if not isinstance(payload, dict):
            return reject(400, "payload must be an object")
        if not _token_authorized(str(payload.get("token") or "")):
            _logger.warning("TCSI setup: unauthorized attempt from %s", remote_addr)
            return reject(401, "unauthorized")
        limiter._tcsi_register_success(remote_addr, _SETUP_SCOPE)

        action = str(payload.get("action") or "")
        # Run as the superuser *user* (not just sudo mode): core code paths such
        # as module installation and res.company/user defaults access
        # env.user, which is an empty recordset on an anonymous request.
        # The sentinel is a module-level object, so a web caller cannot forge
        # it through kwargs.context, and the superuser flag cannot be entered
        # remotely. The token check above remains the entry gate.
        service = (
            request.env["thirdcode.setup.service"]
            .with_user(SUPERUSER_ID)
            .sudo()
            .with_context({SETUP_ENTRY_CONTEXT_KEY: SETUP_ENTRY_SENTINEL})
        )
        try:
            result = service.dispatch(action, payload)
        except Exception as exc:  # noqa: BLE001 - reported to the token holder for debugging
            _logger.exception("TCSI setup: action %s failed", action)
            error = {
                "ok": False,
                "action": action,
                "error": "%s: %s" % (type(exc).__name__, exc),
            }
            if payload.get("debug") and _param_bool(_SETUP_DEBUG_PARAM):
                error["traceback"] = traceback.format_exc()[-4000:]
            return request.make_json_response(error, status=400)
        return request.make_json_response({"ok": True, "action": action, "result": result})
