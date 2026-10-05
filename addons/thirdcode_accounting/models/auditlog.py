import hashlib

from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.addons.auditlog.models.rule import DictDiffer, FIELDS_BLACKLIST


def _prefetch_audit_relation_labels(records, field_names, load):
    """Batch label dependencies in OCA's accounting snapshots.

    Keep the snapshot context and native formatter. In particular, do not turn
    general prefetching back on: that fetches unrelated columns on every model.
    ``fetch`` loads only stored dependencies; native conversion still computes
    each display name, including its language/company context and missing-row
    handling. Keep the caller's cache semantics: create/write use OCA's
    disposable cache, while unlink reads use the existing environment cache.
    """
    if not (
        load == "_classic_read"
        and records.env.su
        and records.env.context.get("auditlog_disabled")
        and records.env.context.get("prefetch_fields") is False
    ):
        return
    relations = {}
    # Native formatting omits source records deleted since read() fetched them.
    existing = records.exists()
    for name in field_names:
        field = records._fields[name]
        if field.type != "many2one" or not field.store:
            continue
        related = existing.mapped(name).sudo()
        if related:
            relations[related._name] = relations.get(related._name, related.browse()) | related
    for related in relations.values():
        related.fetch(["display_name"])


class AccountMoveAuditSnapshot(models.Model):
    _inherit = "account.move"

    def _read_format(self, fnames, load="_classic_read"):
        _prefetch_audit_relation_labels(self, fnames, load)
        return super()._read_format(fnames, load=load)


class AccountMoveLineAuditSnapshot(models.Model):
    _inherit = "account.move.line"

    def _read_format(self, fnames, load="_classic_read"):
        _prefetch_audit_relation_labels(self, fnames, load)
        return super()._read_format(fnames, load=load)


class AuditLog(models.Model):
    _inherit = "auditlog.log"

    thirdcode_company_ids = fields.Many2many("res.company", string="Recorded company scope", readonly=True)

    def write(self, vals):
        raise AccessError(_("Audit log entries are read-only and cannot be edited."))

    def unlink(self):
        raise AccessError(_("Audit log entries are retained and cannot be purged by application users."))


class AuditLogLine(models.Model):
    _inherit = "auditlog.log.line"

    @api.model_create_multi
    def create(self, vals_list):
        # OCA reads these two labels separately for every field. Prime the
        # existing environment cache in one batch, then retain native creation
        # and validation (including its sudo and language semantics).
        field_ids = {values["field_id"] for values in vals_list if values.get("field_id")}
        if field_ids:
            self.env["ir.model.fields"].sudo().browse(sorted(field_ids)).fetch(
                ["name", "field_description"]
            )
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(_("Audit field history is immutable."))

    def unlink(self):
        raise AccessError(_("Audit field history cannot be purged."))


class AuditLogRule(models.Model):
    _inherit = "auditlog.rule"

    def _thirdcode_prefetch_audit_fields(self, res_model, field_names):
        """Batch native metadata misses without introducing another cache."""
        cache = self.pool._auditlog_field_cache.setdefault(res_model, {})
        missing = set(field_names).difference(cache, FIELDS_BLACKLIST)
        if not missing:
            return
        model = self.env["ir.model"].sudo().browse(self.pool._auditlog_model_cache[res_model])
        all_model_ids = [model.id, *model.inherited_model_ids.ids]
        metadata = self.env["ir.model.fields"].sudo().search_fetch(
            [("model_id", "in", all_model_ids), ("name", "in", sorted(missing))],
            ["name"],
        )
        by_name = {}
        for field in metadata:
            by_name.setdefault(field.name, []).append(field.id)
        # Native _get_field selects the first matching inherited field. Its
        # order has no tie-breaker, so leave ambiguous names to that method.
        unique_ids = [ids[0] for ids in by_name.values() if len(ids) == 1]
        loaded = self.env["ir.model.fields"].sudo().browse(unique_ids).read(load="_classic_write")
        values = {name: False for name in missing if name not in by_name}
        values.update({field["name"]: field for field in loaded})
        # Publish only after the complete native read succeeds. Keep existing
        # entries if another request populated them while this batch loaded.
        for name, value in values.items():
            cache.setdefault(name, value)

    @api.model
    def get_auditlog_fields(self, model):
        names = super().get_auditlog_fields(model)
        # Retain identity/permission changes, never credentials or file bytes.
        if model._name == "res.users":
            return [name for name in ("name", "login", "active", "company_id", "company_ids", "groups_id") if name in model._fields]
        if model._name == "res.groups":
            return [name for name in ("name", "category_id", "implied_ids", "users") if name in model._fields]
        excluded = {"access_token", "password", "new_password", "signup_token", "totp_secret",
                    "thirdcode_period_revision", "store_fname"}
        return [name for name in names if name not in excluded
                and model._fields[name].type != "binary"
                and not any(part in name.lower() for part in ("password", "secret", "token", "api_key"))]

    def write(self, values):
        protected = self.filtered(lambda rule: (rule.name or "").startswith("Third Code:"))
        if protected:
            fixed = {"log_type": "full", "log_create": True, "log_write": True,
                     "log_unlink": True, "capture_record": True, "state": "subscribed"}
            if any(key in values and values[key] != expected for key, expected in fixed.items()):
                raise AccessError(_("Required accounting audit subscriptions cannot be disabled or weakened."))
            if {"model_id", "name", "users_to_exclude_ids", "fields_to_exclude_ids"}.intersection(values):
                raise AccessError(_("Required accounting audit scope cannot be changed."))
        return super().write(values)

    def unsubscribe(self):
        # OCA reverts Python wrappers before writing state. Reject first so a
        # failed RPC cannot leave an unaudited registry until the next restart.
        if any((rule.name or "").startswith("Third Code:") for rule in self):
            raise AccessError(_("Required accounting audit rules cannot be unsubscribed."))
        return super().unsubscribe()

    def unlink(self):
        if any((rule.name or "").startswith("Third Code:") for rule in self):
            raise AccessError(_("Required accounting audit rules must be retained."))
        return super().unlink()

    def create_logs(self, uid, res_model, res_ids, method, old_values=None,
                    new_values=None, additional_log_values=None):
        field_names = set()
        for res_id in res_ids:
            before = (old_values or {}).get(res_id, {})
            after = (new_values or {}).get(res_id, {})
            if method == "create":
                field_names.update(DictDiffer(after, before).added())
            elif method == "write":
                field_names.update(DictDiffer(after, before).changed())
            elif method in ("read", "unlink"):
                field_names.update(before)
        if field_names:
            self._thirdcode_prefetch_audit_fields(res_model, field_names)
        # Snapshot company scope before a source record can disappear/change
        # company. Unknown historical scope stays visible to platform staff only.
        for res_id in res_ids:
            companies = set()
            for snapshot in ((old_values or {}).get(res_id, {}), (new_values or {}).get(res_id, {})):
                value = snapshot.get("company_id")
                if value:
                    companies.add(value[0] if isinstance(value, (list, tuple)) else value)
                companies.update(snapshot.get("company_ids") or [])
            record = self.env[res_model].browse(res_id).exists()
            if record:
                if "company_id" in record._fields:
                    companies.update(record.company_id.ids)
                if "company_ids" in record._fields:
                    companies.update(record.company_ids.ids)
                if "batch_id" in record._fields and record.batch_id and "company_id" in record.batch_id._fields:
                    companies.update(record.batch_id.company_id.ids)
                if res_model == "account.full.reconcile":
                    companies.update(record.reconciled_line_ids.company_id.ids)
            if res_model == "res.company":
                companies.add(res_id)
            if res_model == "ir.attachment":
                snapshots = [(old_values or {}).get(res_id, {}), (new_values or {}).get(res_id, {})]
                for snapshot in snapshots:
                    target_model, target_id = snapshot.get("res_model"), snapshot.get("res_id")
                    if target_model in self.env and target_id:
                        target = self.env[target_model].browse(target_id).exists()
                        if target and "company_id" in target._fields:
                            companies.update(target.company_id.ids)
            if not companies and record and "company_id" in record._fields and not record.company_id:
                companies.add(self.env.company.id)
            values = dict(additional_log_values or {})
            values["thirdcode_company_ids"] = [(6, 0, sorted(companies))]
            super().create_logs(uid, res_model, [res_id], method, old_values, new_values, values)


class AuditAttachmentDigest(models.Model):
    _inherit = "ir.attachment"

    thirdcode_content_sha256 = fields.Char(readonly=True, copy=False)

    def _get_datas_related_values(self, data, mimetype):
        values = super()._get_datas_related_values(data, mimetype)
        values["thirdcode_content_sha256"] = hashlib.sha256(data or b"").hexdigest()
        return values

    @api.model_create_multi
    def create(self, vals_list):
        if any(values.get(key, self.env.context.get("default_" + key)) for values in vals_list
               for key in ("thirdcode_content_sha256", "db_datas", "checksum", "store_fname")):
            raise AccessError(_("Attachment digests are derived from file contents."))
        return super().create(vals_list)

    def write(self, values):
        if {"thirdcode_content_sha256", "db_datas", "checksum", "store_fname"}.intersection(values):
            raise AccessError(_("Attachment storage metadata cannot be edited directly; upload the file content."))
        return super().write(values)
