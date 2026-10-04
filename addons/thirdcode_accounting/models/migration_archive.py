"""Queryable source history, explicitly separate from the posted ledger."""
import hashlib
import json
from decimal import Decimal

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_ARCHIVE_TOKEN = object()


class MigrationArchiveEntry(models.Model):
    _name = "thirdcode.migration.archive.entry"
    _description = "Read-only source history"
    _order = "date, source_entry_id, source_line_id, id"

    batch_id = fields.Many2one("thirdcode.migration.batch", required=True, ondelete="restrict", index=True)
    company_id = fields.Many2one(related="batch_id.company_id", store=True, index=True)
    source_entry_id = fields.Char(required=True, index=True)
    source_line_id = fields.Char(required=True)
    date = fields.Date(required=True, index=True)
    account_code = fields.Char(required=True, index=True)
    partner_reference = fields.Char()
    description = fields.Char()
    debit = fields.Monetary(currency_field="currency_id")
    credit = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(related="company_id.currency_id")
    source_fingerprint = fields.Char(required=True, readonly=True)

    _sql_constraints = [("source_line_unique", "unique(batch_id, source_entry_id, source_line_id)", "A source archive line can only be retained once.")]

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("thirdcode_archive_token") is not _ARCHIVE_TOKEN:
            raise AccessError(_("Archive history is loaded through the validated archive action."))
        return super().create(vals_list)

    def write(self, values):
        raise AccessError(_("Retained source history cannot be edited."))

    def unlink(self):
        raise AccessError(_("Retained source history cannot be purged."))


class MigrationArchiveBatch(models.Model):
    _inherit = "thirdcode.migration.batch"

    archive_entry_ids = fields.One2many("thirdcode.migration.archive.entry", "batch_id", readonly=True)

    def action_archive_source_history(self, rows):
        self.ensure_one()
        self._check_migration_access()
        if not self.env.user.has_group("thirdcode_accounting.group_thirdcode_administrator"):
            raise AccessError(_("Only an Administrator may load retained source history."))
        if self.company_id not in self.env.companies or not self.source_archive or not self.source_file_hash:
            raise UserError(_("An active company and retained source archive are required."))
        if not self.cutover_fingerprint:
            raise UserError(_("First complete the atomic snapshot import; this source history is a non-posting archive."))
        if not isinstance(rows, list) or not rows:
            raise UserError(_("Provide a nonempty list of source history lines."))
        values, seen, totals, dates = [], set(), {}, {}
        allowed = {"source_entry_id", "source_line_id", "date", "account_code", "partner_reference", "description", "debit", "credit"}
        for row in rows:
            if not isinstance(row, dict) or set(row) - allowed:
                raise UserError(_("Unsupported source history fields."))
            key = (row.get("source_entry_id"), row.get("source_line_id"))
            if not all(key) or key in seen or not row.get("account_code"):
                raise UserError(_("Each archive entry/line identifier and account must be present and unique."))
            seen.add(key)
            try:
                day = fields.Date.to_date(row.get("date"))
                debit, credit = Decimal(str(row.get("debit", 0))), Decimal(str(row.get("credit", 0)))
                quantum = Decimal(str(self.company_id.currency_id.rounding))
                precise = all(value.is_finite() and value.quantize(quantum) == value for value in (debit, credit))
            except (ValueError, TypeError, ArithmeticError):
                raise UserError(_("Invalid archive date or amount."))
            if not day or day > self.cutover_date or not precise or min(debit, credit) < 0 or bool(debit) == bool(credit):
                raise UserError(_("Archive lines must be before/at cutover and contain one finite nonnegative debit or credit."))
            if dates.setdefault(key[0], day) != day:
                raise UserError(_("All source lines of an entry must have the same date."))
            totals[key[0]] = totals.get(key[0], Decimal(0)) + debit - credit
            canonical = dict(row, date=str(day), debit=str(debit.normalize()), credit=str(credit.normalize()))
            fingerprint = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
            values.append(dict(canonical, batch_id=self.id, source_fingerprint=fingerprint, debit=float(debit), credit=float(credit)))
        if any(totals.values()):
            raise UserError(_("Every archived source entry must balance; provide all lines of each entry."))
        self.env.cr.execute("SELECT id FROM thirdcode_migration_batch WHERE id = %s FOR UPDATE", [self.id])
        retained = self.env["thirdcode.migration.archive.entry"].search([("batch_id", "=", self.id)])
        existing = {(row.source_entry_id, row.source_line_id): row for row in retained}
        to_create = []
        for value in values:
            previous = existing.get((value["source_entry_id"], value["source_line_id"]))
            if previous:
                if previous.source_fingerprint != value["source_fingerprint"]:
                    raise UserError(_("The archive already contains different source content for this entry/line."))
            else:
                if any(key[0] == value["source_entry_id"] for key in existing):
                    raise UserError(_("An existing archived entry cannot gain additional lines; review the source package."))
                to_create.append(value)
        created = self.env["thirdcode.migration.archive.entry"].sudo().with_context(thirdcode_archive_token=_ARCHIVE_TOKEN).create(to_create)
        return {"created_lines": len(created), "existing_lines": len(values) - len(created), "posted_moves_created": 0}
