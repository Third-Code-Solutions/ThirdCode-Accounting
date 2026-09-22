"""TCSI-branded entry points for the authenticated workspace."""

from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.home import Home
import re


def branded_workspace_url(url):
    """Change only the internal workspace prefix, preserving query and fragment."""
    return re.sub(r"^/odoo(?=[/?#]|$)", "/workspace", url)


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

    @http.route("/dashboards", type="http", auth="none", readonly=False)
    def dashboards_alias(self, **kw):
        """Keep the product-facing dashboard URL useful for bookmarks and deep links."""
        return request.redirect("/workspace/action-425")

    @http.route("/workspace/dashboards", type="http", auth="none", readonly=False)
    def workspace_dashboards_alias(self, **kw):
        """Redirect the legacy native dashboard path to the TCSI overview."""
        return request.redirect("/workspace/action-425")

    @http.route("/action-307", type="http", auth="none", readonly=False)
    def action_307_alias(self, **kw):
        """Keep the legacy action shortcut inside the branded workspace shell."""
        return request.redirect("/workspace/action-307")

    @http.route("/action-425", type="http", auth="none", readonly=False)
    def action_425_alias(self, **kw):
        """Keep the command-center shortcut inside the branded workspace shell."""
        return request.redirect("/workspace/action-425")
