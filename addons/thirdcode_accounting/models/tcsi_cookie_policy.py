"""Session cookie policy for the engine.

Odoo 18 writes the session cookie twice, and never with ``Secure`` or
``SameSite``:

* ``_save_session`` sends it through ``FutureResponse.set_cookie``
  (``odoo/http.py``), i.e. after the dispatcher has already produced the
  response;
* the session-expired redirect sets it through ``_Response.set_cookie``.

Because both happen *after* ``ir.http._post_dispatch`` ran, the header rewrite
in ``ir_http`` can never reach the session cookie - the live pilot answered
``Set-Cookie: session_id=...; HttpOnly; Path=/`` while carrying every other
hardened header. The two ``set_cookie`` implementations are therefore wrapped
here, at import time, so the cookie leaves the process as::

    session_id=...; HttpOnly; SameSite=Lax; Path=/[; Secure]

``Secure`` is added only when the request is served over HTTPS (proxy aware,
the same rule ``ir.http._tcsi_is_secure`` applies), so a plain-HTTP local
instance can still authenticate. The wrapper is deliberately Odoo-scoped: no
third-party response class is patched.
"""

import functools
import logging

from odoo import http

_logger = logging.getLogger(__name__)

SESSION_COOKIE_NAME = "session_id"
SESSION_COOKIE_SAMESITE = "Lax"
PATCH_FLAG = "_tcsi_cookie_policy"
# set_cookie(self, key, value, max_age, expires, path, domain, secure, httponly, samesite)
_SLOT_AFTER_VALUE = {"secure": 4, "httponly": 5, "samesite": 6}


def _tcsi_request_is_secure():
    """True when this request reached us over HTTPS, proxy aware."""
    try:
        httprequest = http.request.httprequest
    except Exception:  # noqa: BLE001 - no request bound (cron, shell, tests)
        return False
    try:
        if httprequest.is_secure:
            return True
        proto = httprequest.environ.get("HTTP_X_FORWARDED_PROTO", "")
    except Exception:  # noqa: BLE001
        return False
    return str(proto).split(",")[0].strip().lower() == "https"


def _tcsi_cookie_overrides(key, secure_request):
    """The attributes this policy forces on ``key``; empty for other cookies."""
    if str(key or "").strip().lower() != SESSION_COOKIE_NAME:
        return {}
    overrides = {"httponly": True, "samesite": SESSION_COOKIE_SAMESITE}
    if secure_request:
        overrides["secure"] = True
    return overrides


def _make_wrapper(original):
    """Wrap one ``set_cookie`` implementation with the session cookie policy."""

    @functools.wraps(original)
    def set_cookie(self, key, value="", *args, **kwargs):
        overrides = _tcsi_cookie_overrides(key, _tcsi_request_is_secure())
        for name, forced in overrides.items():
            # A positional argument for that slot would collide with the
            # keyword, so leave the caller's value alone in that case.
            if name in kwargs or len(args) <= _SLOT_AFTER_VALUE[name]:
                kwargs[name] = forced
        return original(self, key, value, *args, **kwargs)

    setattr(set_cookie, PATCH_FLAG, True)
    return set_cookie


def patch_set_cookie():
    """Wrap the two Odoo ``set_cookie`` implementations. Idempotent."""
    patched = []
    for cls in (http.FutureResponse, http._Response):
        current = cls.set_cookie
        if getattr(current, PATCH_FLAG, False):
            continue
        cls.set_cookie = _make_wrapper(current)
        patched.append(cls.__name__)
    if patched:
        _logger.info("TCSI: session cookie policy installed on %s", ", ".join(patched))
    return patched


PATCHED = patch_set_cookie()
