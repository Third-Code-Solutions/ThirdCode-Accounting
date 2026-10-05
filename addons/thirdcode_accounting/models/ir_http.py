"""HTTP boundary hardening.

Fixes the four database-manager findings (H5, H6, M7, L1) and the missing
engine security headers (H4, M3) at the dispatcher, so they hold for every
deployment regardless of how ``odoo.conf`` was generated:

* ``_pre_dispatch`` answers a plain 404 for the whole ``/web/database`` prefix
  instead of the mix of 200/500/403/404 responses the manager produced.
* ``_post_dispatch`` adds HSTS, Referrer-Policy, Permissions-Policy and
  X-Content-Type-Options, and forces ``Secure``/``SameSite=Lax``/``HttpOnly``
  on the session cookie.

Both knobs are System Parameters, so an operator can re-enable the manager for
a known address without a code change.
"""

import json
import logging

from odoo import SUPERUSER_ID, models
from odoo.http import Response, request
from odoo.addons.bus.websocket import UpgradeRequired
from werkzeug.exceptions import HTTPException, NotFound

_logger = logging.getLogger(__name__)

DB_MANAGER_PREFIX = "/web/database"
DB_MANAGER_ENABLED_PARAM = "tcsi.db_manager_enabled"
DB_MANAGER_ALLOW_IPS_PARAM = "tcsi.db_manager_allow_ips"
HSTS_MAX_AGE_PARAM = "tcsi.security.hsts_max_age"
DEFAULT_HSTS_MAX_AGE = 31536000

SECURITY_HEADERS = (
    ("Referrer-Policy", "strict-origin-when-cross-origin"),
    ("X-Content-Type-Options", "nosniff"),
    ("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()"),
    ("X-Permitted-Cross-Domain-Policies", "none"),
)


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @classmethod
    def _tcsi_param(cls, name, default=""):
        try:
            return request.env["ir.config_parameter"].sudo().get_param(name, default)
        except Exception:  # noqa: BLE001
            return default

    @classmethod
    def _tcsi_client_ip(cls):
        try:
            return request.httprequest.remote_addr or "unknown"
        except Exception:  # noqa: BLE001
            return "unknown"

    @classmethod
    def _tcsi_is_secure(cls):
        """True when the request arrived over TLS (proxy aware).

        Shared with the session cookie policy, so the header rewrite and the
        cookie wrapper can never disagree about whether the hop was secure.
        """
        from .tcsi_cookie_policy import _tcsi_request_is_secure

        return _tcsi_request_is_secure()

    @classmethod
    def _tcsi_db_manager_allowed(cls):
        """Default deny; opt in per address with System Parameters."""
        enabled = str(cls._tcsi_param(DB_MANAGER_ENABLED_PARAM, "0")).strip().lower()
        if enabled not in ("1", "true", "yes", "on"):
            return False
        raw = cls._tcsi_param(DB_MANAGER_ALLOW_IPS_PARAM, "") or ""
        entries = {item.strip() for item in str(raw).split(",") if item.strip()}
        if not entries:
            return False
        return cls._tcsi_client_ip() in entries

    # ------------------------------------------------------------------
    # H5 / H6 / M7 / L1 - the database manager is not reachable
    # ------------------------------------------------------------------
    @classmethod
    def _pre_dispatch(cls, rule, args):
        try:
            path = request.httprequest.path or ""
        except Exception:  # noqa: BLE001
            path = ""
        if path == DB_MANAGER_PREFIX or path.startswith(DB_MANAGER_PREFIX + "/"):
            if not cls._tcsi_db_manager_allowed():
                _logger.warning(
                    "TCSI: blocked database manager request %s from %s",
                    path,
                    cls._tcsi_client_ip(),
                )
                raise NotFound()
        return super()._pre_dispatch(rule, args)

    # ------------------------------------------------------------------
    # H4 / M3 - transport and cookie hardening
    # ------------------------------------------------------------------
    @classmethod
    def _post_dispatch(cls, response):
        super()._post_dispatch(response)
        try:
            cls._tcsi_harden_headers(response)
        except Exception:  # noqa: BLE001 - headers must never break a response
            _logger.exception("TCSI: could not apply security headers")
        return response

    @classmethod
    def _handle_error(cls, exception):
        response = super()._handle_error(exception)
        try:
            if isinstance(response, UpgradeRequired) and response.response is None:
                # Odoo 18's override lacks Werkzeug's optional ASGI scope
                # argument. Call its WSGI methods directly to retain the 426
                # and Sec-WebSocket-Version instead of raising a TypeError.
                environ = request.httprequest.environ
                response = Response(response.get_body(environ), status=response.code,
                                    headers=response.get_headers(environ))
            elif isinstance(response, HTTPException):
                # HTTP dispatchers may return a WSGI exception instead of a
                # response. Preserve its status/body/headers before hardening.
                response = response.get_response(request.httprequest.environ)
            if response is not None:
                cls._tcsi_strip_error_debug(response)
                cls._tcsi_harden_headers(response)
        except Exception:  # noqa: BLE001 - an error page must still be served
            _logger.exception("TCSI: could not apply security headers to an error response")
        return response

    # ------------------------------------------------------------------
    # L6 - JSON-RPC error payloads must not carry a traceback
    # ------------------------------------------------------------------
    @classmethod
    def _tcsi_strip_error_debug(cls, response):
        """Remove the traceback Odoo serializes into JSON error payloads.

        ``odoo.http.serialize_exception`` unconditionally embeds
        ``traceback.format_exc()``, the exception arguments and its context in
        the ``error.data`` member of every JSON-RPC error, including errors
        raised for anonymous callers (a 404 on a ``type="json"`` route is
        enough). That discloses absolute file paths, the module layout and
        source lines to unauthenticated clients, so it is dropped unless the
        caller is an authenticated session in debug mode.
        """
        try:
            session = request.session
            if session.uid and (session.debug or "").strip():
                return response
        except Exception:  # noqa: BLE001 - never break error handling
            pass

        try:
            content_type = (response.headers.get("Content-Type") or "").lower()
            if "json" not in content_type:
                return response
            if response.direct_passthrough:
                return response
            raw = response.get_data()
            if not raw or len(raw) > 1_000_000:
                return response
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                return response
            error = payload.get("error")
            if not isinstance(error, dict):
                return response
            data = error.get("data")
            if not isinstance(data, dict):
                return response
            changed = False
            for key in ("debug", "arguments", "context"):
                if data.pop(key, None) is not None:
                    changed = True
            if not changed:
                return response
            response.set_data(json.dumps(payload))
        except Exception:  # noqa: BLE001 - never break error handling
            _logger.debug("TCSI: could not sanitize a JSON error payload", exc_info=True)
        return response

    @classmethod
    def _tcsi_harden_headers(cls, response):
        headers = response.headers
        for name, value in SECURITY_HEADERS:
            if name not in headers:
                headers[name] = value
        if cls._tcsi_is_secure():
            if "Strict-Transport-Security" not in headers:
                try:
                    max_age = int(cls._tcsi_param(HSTS_MAX_AGE_PARAM, DEFAULT_HSTS_MAX_AGE))
                except (TypeError, ValueError):
                    max_age = DEFAULT_HSTS_MAX_AGE
                headers["Strict-Transport-Security"] = (
                    "max-age=%s; includeSubDomains" % max_age
                )
            cls._tcsi_harden_session_cookie(headers)

    @classmethod
    def _tcsi_harden_session_cookie(cls, headers):
        """Force Secure/HttpOnly/SameSite=Lax on the session cookie."""
        try:
            cookies = headers.getlist("Set-Cookie")
        except AttributeError:
            return
        if not cookies:
            return
        hardened = []
        changed = False
        for cookie in cookies:
            new_cookie = cls._tcsi_harden_cookie_value(cookie)
            changed = changed or new_cookie != cookie
            hardened.append(new_cookie)
        if not changed:
            return
        del headers["Set-Cookie"]
        for cookie in hardened:
            headers.add("Set-Cookie", cookie)

    @staticmethod
    def _tcsi_harden_cookie_value(cookie):
        parts = [part.strip() for part in str(cookie).split(";") if part.strip()]
        if not parts:
            return cookie
        name = parts[0].split("=", 1)[0].strip().lower()
        if name != "session_id":
            return cookie
        lowered = [part.lower() for part in parts]
        for attribute in ("Secure", "HttpOnly", "SameSite=Lax"):
            token = attribute.split("=", 1)[0].lower()
            if not any(part.startswith(token) for part in lowered):
                parts.append(attribute)
                lowered.append(attribute.lower())
        return "; ".join(parts)
