"""A narrow public read surface: published marketing content only."""
import json
from odoo import http
from odoo.http import request


class PlatformPublic(http.Controller):
    @http.route('/thirdcode_accounting/public/website', type='http', auth='public', methods=['GET'], csrf=False, save_session=False)
    def website_content(self):
        model = request.env['thirdcode.platform.publication'].sudo()
        domain = [('published_json', '!=', False), ('archived', '=', False)]
        seo = model.search(domain + [('kind', '=', 'seo')], order='published_at desc,id desc', limit=1)
        releases = model.search(domain + [('kind', '=', 'release')], order='published_at desc,id desc', limit=100)
        keys = {'id', 'kind', 'title', 'description', 'version', 'category', 'published_at'}
        def snapshot(record):
            return {k: v for k,v in json.loads(record.published_json).items() if k in keys}
        return request.make_json_response({
            'seo': snapshot(seo) if seo else None,
            'releases': [snapshot(r) for r in releases],
        }, headers=[('Cache-Control', 'public, max-age=30'), ('X-Content-Type-Options', 'nosniff')])
