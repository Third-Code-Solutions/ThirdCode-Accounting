from odoo import http
from odoo.addons.web.controllers.webmanifest import WebManifest
from odoo.http import request


class TCSIWebManifest(WebManifest):
    def _get_webmanifest(self):
        manifest = super()._get_webmanifest()
        manifest.update(
            {
                "name": "TCSI Accounting",
                "short_name": "TCSI",
                "background_color": "#efe8f7",
                "theme_color": "#601be6",
                "icons": [
                    {
                        "src": "/thirdcode_accounting/static/src/img/tcsi-mark.svg?v=2.5.0",
                        "sizes": "192x192",
                        "type": "image/svg+xml",
                    },
                    {
                        "src": "/thirdcode_accounting/static/src/img/tcsi-mark.svg?v=2.5.0",
                        "sizes": "512x512",
                        "type": "image/svg+xml",
                    },
                ],
            }
        )
        return manifest

    @http.route(
        "/web/manifest.webmanifest",
        type="http",
        auth="public",
        methods=["GET"],
        readonly=True,
    )
    def webmanifest(self):
        return request.make_json_response(
            self._get_webmanifest(), {"Content-Type": "application/manifest+json"}
        )
