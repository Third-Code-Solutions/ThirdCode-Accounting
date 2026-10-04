"""Attribute retained audit rows without rewriting their original evidence."""
import ast
import logging
from odoo import SUPERUSER_ID, api, Command

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    logs = env["auditlog.log"].search([("thirdcode_company_ids", "=", False)])
    unknown = 0
    for log in logs:
        companies = set()
        for line in log.line_ids.filtered(lambda item: item.field_name in {"company_id", "company_ids"}):
            for raw in (line.old_value, line.new_value):
                try:
                    value = ast.literal_eval(raw or "False")
                except (ValueError, SyntaxError):
                    continue
                if line.field_name == "company_id" and value:
                    companies.add(value[0] if isinstance(value, (tuple, list)) else value)
                elif line.field_name == "company_ids" and isinstance(value, list):
                    companies.update(v for v in value if isinstance(v, int))
        if log.model_model in env:
            record = env[log.model_model].browse(log.res_id).exists()
            if record and "company_id" in record._fields:
                companies.update(record.company_id.ids)
            if record and "company_ids" in record._fields:
                companies.update(record.company_ids.ids)
        companies = env["res.company"].browse([value for value in companies if isinstance(value, int)]).exists()
        if companies:
            # Bypass only this addon's immutable-log wrapper for new scope
            # metadata. Original user/time/old/new evidence is never rewritten.
            from odoo.addons.thirdcode_accounting.models.auditlog import AuditLog
            super(AuditLog, log).write({"thirdcode_company_ids": [Command.set(companies.ids)]})
        else:
            unknown += 1
    _logger.warning("Retained audit scope: %s rows inspected; %s unresolved rows remain platform-only", len(logs), unknown)
