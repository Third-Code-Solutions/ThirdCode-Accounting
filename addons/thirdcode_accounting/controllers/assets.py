"""Real responses for the well-known engine paths.

The engine origin answered /favicon.ico, /apple-touch-icon.png, /robots.txt and
/sitemap.xml with the branded HTML 404 page (finding L4). These routes serve the
real assets instead. The workspace is a private application origin, so robots
disallows everything and the sitemap stays empty on purpose.
"""

import logging

from odoo import http
from odoo.http import request
from odoo.modules.module import get_module_resource
from werkzeug.exceptions import NotFound

_logger = logging.getLogger(__name__)

MODULE = "thirdcode_accounting"

ROBOTS_TXT = "User-agent: *\nDisallow: /\n"
SITEMAP_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>\n'
)

BINARY_ROUTES = (
    ("/favicon.ico", "static/src/img/favicon.ico", "image/vnd.microsoft.icon"),
    ("/apple-touch-icon.png", "static/src/img/apple-touch-icon.png", "image/png"),
    ("/apple-touch-icon-precomposed.png", "static/src/img/apple-touch-icon.png", "image/png"),
)


class ThirdCodeAssets(http.Controller):
    def _tcsi_binary(self, relative_path, mimetype):
        path = get_module_resource(MODULE, *relative_path.split("/"))
        if not path:
            _logger.warning("TCSI assets: %s is missing from %s", relative_path, MODULE)
            raise NotFound()
        with open(path, "rb") as handle:
            payload = handle.read()
        return request.make_response(
            payload,
            headers=[
                ("Content-Type", mimetype),
                ("Content-Length", str(len(payload))),
                ("Cache-Control", "public, max-age=86400"),
            ],
        )

    def _tcsi_text(self, payload, mimetype):
        return request.make_response(
            payload,
            headers=[
                ("Content-Type", mimetype),
                ("Cache-Control", "public, max-age=86400"),
            ],
        )

    @http.route(
        [route for route, _path, _mimetype in BINARY_ROUTES],
        type="http",
        auth="none",
        methods=["GET", "HEAD"],
        csrf=False,
        save_session=False,
    )
    def tcsi_wellknown_binary(self, **kwargs):
        for route, relative_path, mimetype in BINARY_ROUTES:
            if request.httprequest.path == route:
                return self._tcsi_binary(relative_path, mimetype)
        raise NotFound()

    @http.route(
        ["/robots.txt"],
        type="http",
        auth="none",
        methods=["GET", "HEAD"],
        csrf=False,
        save_session=False,
    )
    def tcsi_robots(self, **kwargs):
        return self._tcsi_text(ROBOTS_TXT, "text/plain; charset=utf-8")

    @http.route(
        ["/sitemap.xml"],
        type="http",
        auth="none",
        methods=["GET", "HEAD"],
        csrf=False,
        save_session=False,
    )
    def tcsi_sitemap(self, **kwargs):
        return self._tcsi_text(SITEMAP_XML, "application/xml; charset=utf-8")
