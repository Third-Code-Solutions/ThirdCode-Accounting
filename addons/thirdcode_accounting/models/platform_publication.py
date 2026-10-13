"""Drafts remain private; public pages receive a separate published snapshot."""
import json

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from .platform_access import require_platform_owner
from .platform_operations import bounded_text, bounded_page


class PlatformPublication(models.Model):
    _name = "thirdcode.platform.publication"
    _description = "Platform website publication"
    _order = "id desc"

    kind = fields.Selection([("seo", "Homepage SEO"), ("release", "Product update")], required=True)
    title = fields.Char(required=True)
    description = fields.Text(required=True)
    version = fields.Char()
    category = fields.Selection([("feature", "New feature"), ("improvement", "Improvement"), ("fix", "Fix"), ("security", "Security")], default="improvement")
    revision = fields.Integer(default=1, required=True)
    published_json = fields.Text(readonly=True, copy=False)
    previous_json = fields.Text(readonly=True, copy=False)
    published_at = fields.Datetime(readonly=True, copy=False)
    archived = fields.Boolean(default=False)

    @api.model_create_multi
    def create(self, values_list):
        require_platform_owner(self.env)
        raise AccessError(_("Use the website draft controls to create publications."))

    def write(self, values):
        require_platform_owner(self.env)
        raise AccessError(_("Use the website draft and publish controls."))

    def unlink(self):
        raise AccessError(_("Archive a publication to retain its history."))

    def _save_values(self, values):
        return super(PlatformPublication, self).write(values)

    @api.model
    def _new_draft(self, values):
        values = dict(values, revision=1, published_json=False, previous_json=False,
                      published_at=False, archived=False)
        return super(PlatformPublication, self.with_context({})).create(values)

    def _lock_revision(self, expected):
        self.ensure_one()
        self.flush_recordset(["revision"])
        self.env.cr.execute("SELECT revision FROM thirdcode_platform_publication WHERE id=%s FOR UPDATE", [self.id])
        current = self.env.cr.fetchone()
        if not current or expected != current[0]:
            raise UserError(_("This draft changed. Refresh before saving or publishing."))
        self.invalidate_recordset()

    def _payload(self):
        return {"id": self.id, "kind": self.kind, "title": self.title, "description": self.description,
                "version": self.version or "", "category": self.category,
                "published_at": fields.Datetime.to_string(fields.Datetime.now())}


class PlatformPublishing(models.TransientModel):
    _inherit = "thirdcode.platform.console"

    @api.model
    def get_publications(self, page=0):
        self._check_console_access()
        model = self.env["thirdcode.platform.publication"].sudo()
        records = model.search([("kind", "=", "seo")], limit=1) | model.search([("kind", "=", "release")], offset=bounded_page(page)*25, limit=25)
        return {"rows": records.read(["kind", "title", "description", "version", "category", "revision", "published_json", "published_at", "archived"]), "total": model.search_count([("kind", "=", "release")]), "page": page}

    @api.model
    def save_publication(self, payload, record_id=False, revision=False):
        self._check_console_access()
        if not isinstance(payload, dict) or set(payload) != {"kind", "title", "description", "version", "category"}:
            raise UserError(_("Invalid publication fields."))
        kind = payload["kind"]
        if kind not in ("seo", "release") or payload["category"] not in ("feature", "improvement", "fix", "security"):
            raise UserError(_("Invalid publication type."))
        values = {"kind": kind, "title": bounded_text(payload["title"], "title", 70 if kind == "seo" else 120),
                  "description": bounded_text(payload["description"], "description", 200 if kind == "seo" else 12000),
                  "version": bounded_text(payload["version"], "version", 40, required=False), "category": payload["category"]}
        model = self.env["thirdcode.platform.publication"].sudo()
        if record_id:
            record = model.browse(int(record_id)).exists()
            if not record or record.kind != kind:
                raise UserError(_("Publication not found or type changed."))
            record._lock_revision(revision)
            record._save_values(dict(values, revision=record.revision+1))
        else:
            if kind == "seo":
                self.env.cr.execute("SELECT pg_advisory_xact_lock(hashtextextended('tcsi-homepage-seo',0))")
                if model.search_count([("kind", "=", "seo")]):
                    raise UserError(_("Edit the existing homepage SEO draft."))
            record = model._new_draft(values)
        self.env["thirdcode.platform.event"]._record("website.draft_saved", "%s:%s" % (kind,record.id))
        return {"id": record.id, "revision": record.revision}

    @api.model
    def publish_content(self, record_id, revision, action="publish"):
        self._check_console_access()
        record = self.env["thirdcode.platform.publication"].sudo().browse(int(record_id)).exists()
        if not record or action not in ("publish", "archive", "revert"):
            raise UserError(_("Invalid publication action."))
        record._lock_revision(revision)
        values = {"revision": record.revision+1}
        if action == "publish":
            values.update(previous_json=record.published_json, published_json=json.dumps(record._payload()),
                          published_at=fields.Datetime.now(), archived=False)
        elif action == "archive":
            values["archived"] = True
        else:
            if not record.previous_json:
                raise UserError(_("No previous published revision exists."))
            values.update(published_json=record.previous_json, previous_json=record.published_json,
                          archived=False, published_at=fields.Datetime.now())
        record._save_values(values)
        self.env["thirdcode.platform.event"]._record("website."+action, "%s:%s" % (record.kind,record.id))
        return True
