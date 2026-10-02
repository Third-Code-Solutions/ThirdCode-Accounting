import hashlib
import hmac
import json
import logging
import traceback

from odoo import SUPERUSER_ID, http
from odoo.http import request

_logger = logging.getLogger(__name__)

# SHA-256 of the operational setup token. The plaintext token is stored with the
# pilot operator (outside the repository) and is required for every call.
_SETUP_TOKEN_SHA256 = "f07adcd6202f89bd091beb906bf552c57039bddfc095cf25323b4837ae69f3e6"


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
        try:
            payload = json.loads(request.httprequest.get_data() or b"{}")
        except ValueError:
            return request.make_json_response(
                {"ok": False, "error": "invalid json"}, status=400
            )
        if not isinstance(payload, dict):
            return request.make_json_response(
                {"ok": False, "error": "payload must be an object"}, status=400
            )
        token = str(payload.get("token") or "")
        if not token or not hmac.compare_digest(
            hashlib.sha256(token.encode()).hexdigest(), _SETUP_TOKEN_SHA256
        ):
            _logger.warning(
                "TCSI setup: unauthorized attempt from %s",
                request.httprequest.remote_addr,
            )
            return request.make_json_response(
                {"ok": False, "error": "unauthorized"}, status=401
            )
        action = str(payload.get("action") or "")
        # Run as the superuser *user* (not just sudo mode): core code paths such
        # as module installation and res.company/user defaults access
        # env.user, which is an empty recordset on an anonymous request.
        service = (
            request.env["thirdcode.setup.service"]
            .with_user(SUPERUSER_ID)
            .sudo()
            .with_context(tcsi_setup_token_ok=True)
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
            if payload.get("debug"):
                error["traceback"] = traceback.format_exc()[-4000:]
            return request.make_json_response(error, status=400)
        return request.make_json_response({"ok": True, "action": action, "result": result})
