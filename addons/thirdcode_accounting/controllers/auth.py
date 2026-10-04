"""Password-reset surface hardening (finding H2).

``AuthSignupHome.web_auth_reset_password`` has a second enumeration oracle next
to the one in the model: on a GET carrying ``signup_email`` it redirects to
``/web/login?login=<login>`` when that address belongs to an account, and
renders the page when it does not. Dropping the probe parameter makes the
response identical either way; the password-reset POST path is unaffected and
the reset itself is silenced in ``res.users.reset_password``.
"""

import logging

from odoo import http
from odoo.http import request
from odoo.addons.auth_signup.controllers.main import AuthSignupHome

_logger = logging.getLogger(__name__)

SIGNUP_EMAIL_PARAM = "signup_email"


RESET_ROUTES = ("/web/reset_password", "/web/login")


class ThirdCodeAuthSignup(AuthSignupHome):
    def get_auth_signup_qcontext(self):
        """Never expose ``signup_email`` on the reset page.

        The parent method redirects a GET carrying ``signup_email`` to
        ``/web/login?login=<login>`` when the address exists and renders the
        page when it does not, which is a clean user-enumeration oracle.
        Removing the value from the context makes both responses identical.
        """
        qcontext = super().get_auth_signup_qcontext()
        try:
            if request.httprequest.path in RESET_ROUTES:
                qcontext.pop(SIGNUP_EMAIL_PARAM, None)
        except Exception:  # noqa: BLE001 - never break the reset page
            _logger.exception("TCSI: could not drop the %s probe", SIGNUP_EMAIL_PARAM)
        return qcontext

    @http.route()
    def web_auth_reset_password(self, *args, **kwargs):
        try:
            params = getattr(request, "params", None)
            if isinstance(params, dict) and SIGNUP_EMAIL_PARAM in params:
                params.pop(SIGNUP_EMAIL_PARAM, None)
        except Exception:  # noqa: BLE001 - never break the reset page
            _logger.exception("TCSI: could not drop the %s parameter", SIGNUP_EMAIL_PARAM)
        return super().web_auth_reset_password(*args, **kwargs)
