from odoo import _, models
from odoo.exceptions import AccessError


class AuditLog(models.Model):
    _inherit = "auditlog.log"

    def write(self, vals):
        raise AccessError(_("Audit log entries are read-only and cannot be edited."))

    def unlink(self):
        raise AccessError(_("Audit log entries are retained and cannot be purged by application users."))
