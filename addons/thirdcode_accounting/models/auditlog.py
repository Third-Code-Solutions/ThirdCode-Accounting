from odoo import _, fields, models
from odoo.exceptions import AccessError


class AuditLog(models.Model):
    _inherit = "auditlog.log"

    thirdcode_company_ids = fields.Many2many("res.company", string="Recorded company scope", readonly=True)

    def write(self, vals):
        raise AccessError(_("Audit log entries are read-only and cannot be edited."))

    def unlink(self):
        raise AccessError(_("Audit log entries are retained and cannot be purged by application users."))


class AuditLogLine(models.Model):
    _inherit = "auditlog.log.line"

    def write(self, vals):
        raise AccessError(_("Audit field history is immutable."))

    def unlink(self):
        raise AccessError(_("Audit field history cannot be purged."))


class AuditLogRule(models.Model):
    _inherit = "auditlog.rule"

    def create_logs(self, uid, res_model, res_ids, method, old_values=None,
                    new_values=None, additional_log_values=None):
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
                if res_model == "account.full.reconcile":
                    companies.update(record.reconciled_line_ids.company_id.ids)
            if not companies and record and "company_id" in record._fields and not record.company_id:
                companies.add(self.env.company.id)
            values = dict(additional_log_values or {})
            values["thirdcode_company_ids"] = [(6, 0, sorted(companies))]
            super().create_logs(uid, res_model, [res_id], method, old_values, new_values, values)
