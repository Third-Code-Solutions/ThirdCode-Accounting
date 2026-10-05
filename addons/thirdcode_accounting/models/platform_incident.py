"""First-party error monitor: fingerprints/counts only, never raw exceptions."""
import hashlib
import re
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from .platform_access import require_platform_owner


class PlatformIncident(models.Model):
    _name = "thirdcode.platform.incident"
    _description = "Platform Sentry incident"
    _order = "last_seen desc,id desc"

    fingerprint = fields.Char(required=True, index=True)
    kind = fields.Char(required=True)
    route = fields.Char(required=True)
    occurrences = fields.Integer(default=1)
    first_seen = fields.Datetime(default=fields.Datetime.now)
    last_seen = fields.Datetime(default=fields.Datetime.now, index=True)
    state = fields.Selection([("open", "Open"), ("acknowledged", "Acknowledged"), ("resolved", "Resolved")], default="open", required=True)
    _sql_constraints = [("fingerprint_unique", "unique(fingerprint)", "Incident already exists.")]

    @api.model_create_multi
    def create(self, values_list):
        raise AccessError(_("Incidents are captured by the system."))

    def write(self, values):
        require_platform_owner(self.env)
        if set(values) != {"state"} or values["state"] not in ("open", "acknowledged", "resolved"):
            raise AccessError(_("Only the incident workflow state may be changed."))
        result = super().write(values)
        for incident in self:
            self.env["thirdcode.platform.event"]._record("incident."+values["state"], str(incident.id))
        return result

    def unlink(self):
        raise AccessError(_("Incident retention is managed by the system."))

    @api.model
    def _capture(self, exception_name, route):
        # Only the Python class name and a bounded route family are retained.
        kind = re.sub(r"[^A-Za-z0-9_.]", "", str(exception_name))[:100] or "ServerError"
        family = "/" + str(route).split("?", 1)[0].strip("/").split("/", 1)[0]
        family = family if family in ("/web", "/workspace", "/report", "/mail", "/thirdcode_accounting", "/websocket") else "/other"
        fingerprint = hashlib.sha256((kind+":"+family).encode()).hexdigest()
        self.env.cr.execute("""
            INSERT INTO thirdcode_platform_incident
                (fingerprint,kind,route,occurrences,first_seen,last_seen,state,create_uid,write_uid,create_date,write_date)
            VALUES (%s,%s,%s,1,now() AT TIME ZONE 'UTC',now() AT TIME ZONE 'UTC','open',1,1,now() AT TIME ZONE 'UTC',now() AT TIME ZONE 'UTC')
            ON CONFLICT (fingerprint) DO UPDATE SET
                occurrences=thirdcode_platform_incident.occurrences+1,
                last_seen=EXCLUDED.last_seen,write_date=EXCLUDED.write_date,
                state=CASE WHEN thirdcode_platform_incident.state='resolved' THEN 'open' ELSE thirdcode_platform_incident.state END
        """, [fingerprint,kind,family])
        self.invalidate_model()

    @api.model
    def _purge_expired(self):
        # Non-personal grouped telemetry only; financial/operator audit logs are retained.
        self.env.cr.execute("DELETE FROM thirdcode_platform_incident WHERE last_seen < %s", [fields.Datetime.now()-timedelta(days=90)])


class PlatformMonitoring(models.TransientModel):
    _inherit = "thirdcode.platform.console"

    @api.model
    def get_monitoring(self):
        self._check_console_access()
        incidents = self.env["thirdcode.platform.incident"].sudo()
        cron = self.env["ir.cron"].sudo()
        cron_fields = [n for n in ("name", "active", "nextcall", "lastcall", "failure_count") if n in cron._fields]
        jobs = cron.with_context(active_test=False).search_read([], cron_fields, limit=50, order="nextcall,id")
        for job in jobs:
            for key in ("nextcall", "lastcall"):
                if key in job:
                    job[key] = self._fmt(job[key])
        limiter = self.env["thirdcode.auth.throttle"].sudo()
        return {"incidents": incidents.search_read([], ["kind", "route", "occurrences", "first_seen", "last_seen", "state"], limit=100),
                "open_count": incidents.search_count([("state", "!=", "resolved")]),
                "total_groups": incidents.search_count([]), "jobs": jobs,
                "active_lockouts": limiter.search_count([("blocked_until", ">", fields.Datetime.now())]),
                "captured_at": fields.Datetime.to_string(fields.Datetime.now()),
                "coverage": "Server dispatch failures since this release; grouped by error class and route family. No request bodies or traceback contents. No external uptime or host CPU probe is configured."}

    @api.model
    def set_incident_state(self, incident_id, state):
        self._check_console_access()
        record = self.env["thirdcode.platform.incident"].sudo().browse(int(incident_id)).exists()
        if not record:
            raise UserError(_("Incident no longer exists."))
        record.write({"state": state})
        return True
