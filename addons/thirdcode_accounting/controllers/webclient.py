"""TCSI-branded entry points for the authenticated workspace."""

from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.home import Home


class TCSIWebClient(Home):
    """Serve the web client through a product-facing route prefix."""

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

    @http.route("/action-307", type="http", auth="none", readonly=False)
    def action_307_alias(self, **kw):
        """Keep the legacy action shortcut inside the branded workspace shell."""
        return request.redirect("/workspace/action-307")

    @http.route("/action-425", type="http", auth="none", readonly=False)
    def action_425_alias(self, **kw):
        """Keep the command-center shortcut inside the branded workspace shell."""
        return request.redirect("/workspace/action-425")
