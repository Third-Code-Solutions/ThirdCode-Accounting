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

import logging

from odoo import SUPERUSER_ID, models
from odoo.http import request
from werkzeug.exceptions import NotFound

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
        try:
            if request.httprequest.is_secure:
                return True
            proto = request.httprequest.environ.get("HTTP_X_FORWARDED_PROTO", "")
            return proto.split(",")[0].strip().lower() == "https"
        except Exception:  # noqa: BLE001
            return False

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
            if response is not None:
                cls._tcsi_harden_headers(response)
        except Exception:  # noqa: BLE001 - an error page must still be served
            _logger.exception("TCSI: could not apply security headers to an error response")
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
