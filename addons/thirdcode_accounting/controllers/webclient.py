"""TCSI-branded entry points for the authenticated workspace."""

from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.home import Home
from ..models.platform_access import is_platform_owner
import re


def branded_workspace_url(url):
    """Change only the internal workspace prefix, preserving query and fragment.

    The login redirect chain produced ``/workspace?`` and ``/workspace/?`` for a
    bare workspace request: ``Home.index`` builds the redirect from the raw
    ``full_path``, so an empty query string survives as a lone ``?`` (finding
    M6). Normalising the empty query and the redundant trailing slash keeps
    every branded URL canonical.
    """
    if not url:
        return url
    branded = re.sub(r"^/odoo(?=[/?#]|$)", "/workspace", url)
    branded = re.sub(r"^(/workspace)/?(?=[?#]|$)", r"\1", branded)
    return branded[:-1] if branded.endswith("?") else branded


def _workspace_action_url():
    """Resolve a stable target for the legacy dashboard shortcuts.

    Action ids are database-specific, so the overview action is resolved by
    XML id at request time instead of being hard-coded; a stale id would send
    bookmarks to an unrelated action.
    """
    action_id = request.env["ir.model.data"].sudo()._xmlid_to_res_id(
        "thirdcode_accounting.action_tcsi_dashboard", raise_if_not_found=False
    )
    return f"/workspace/action-{action_id}" if action_id else "/workspace"


class TCSIWebClient(Home):
    """Serve the web client through a product-facing route prefix."""

    @http.route()
    def index(self, **kw):
        response = super().index(**kw)
        if response.location:
            response.location = branded_workspace_url(response.location)
        return response

    @http.route()
    def web_login(self, redirect=None, **kw):
        branded = branded_workspace_url(redirect) if redirect else redirect
        if branded != redirect and request.httprequest.method == "GET":
            return request.redirect_query("/web/login", query={**request.params, "redirect": branded})
        return super().web_login(redirect=branded, **kw)

    @http.route()
    def web_client(self, s_action=None, **kw):
        original = request.httprequest.full_path
        branded = branded_workspace_url(original)
        if branded != original:
            return request.redirect(branded, code=303)
        return super().web_client(s_action=s_action, **kw)

    def _login_redirect(self, uid, redirect=None):
        return branded_workspace_url(super()._login_redirect(uid, redirect))

    @http.route(
        ["/workspace", "/workspace/<path:subpath>"],
        type="http",
        auth="none",
        readonly=False,
    )
    def workspace(self, s_action=None, **kw):
        return super().web_client(s_action=s_action, **kw)

    @http.route(
        ["/workspace/console", "/workspace/console/<path:subpath>"],
        type="http", auth="user", readonly=False,
    )
    def platform_console(self, **kw):
        """Reject company accounts before serving the owner workspace shell."""
        if not is_platform_owner(request.env):
            return request.make_response(
                "<!doctype html><html lang='en'><head><title>Access denied</title></head>"
                "<body><main><h1>Access denied</h1>"
                "<p>This console is reserved for the TCSI platform owner.</p>"
                "<a href='/workspace'>Return to your workspace</a></main></body></html>",
                status=403,
                headers=[("Content-Type", "text/html; charset=utf-8"),
                         ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff")],
            )
        return super().web_client(**kw)

    @http.route("/dashboards", type="http", auth="none", readonly=False)
    def dashboards_alias(self, **kw):
        """Keep the product-facing dashboard URL useful for bookmarks and deep links."""
        return request.redirect(_workspace_action_url())

    @http.route("/workspace/dashboards", type="http", auth="none", readonly=False)
    def workspace_dashboards_alias(self, **kw):
        """Redirect the legacy native dashboard path to the TCSI overview."""
        return request.redirect(_workspace_action_url())

    @http.route("/action-307", type="http", auth="none", readonly=False)
    def action_307_alias(self, **kw):
        """Route the legacy numeric shortcut to the live TCSI overview."""
        return request.redirect(_workspace_action_url())

    @http.route("/action-425", type="http", auth="none", readonly=False)
    def action_425_alias(self, **kw):
        """Route the legacy numeric shortcut to the live TCSI overview."""
        return request.redirect(_workspace_action_url())
