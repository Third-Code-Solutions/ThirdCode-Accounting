"""Company/journal counters continue across years; existing posted names are kept."""
import re

from odoo import _, api, models
from odoo.exceptions import UserError


class ContinuousMoveNumbering(models.Model):
    _inherit = "account.move"

    @api.model
    def _deduce_sequence_number_reset(self, name):
        if re.fullmatch(r".+/C/[0-9]+", name or ""):
            return "never"
        return super()._deduce_sequence_number_reset(name)

    def _get_next_sequence_format(self):
        self.ensure_one()
        if self.journal_id.sequence_override_regex:
            raise UserError(_("A legacy sequence override is configured. Review and clear it before adopting continuous journal numbering."))
        self.env["account.move"].flush_model(["journal_id", "sequence_number", "posted_before", "state"])
        self.env.cr.execute("""
            SELECT COALESCE(MAX(sequence_number), 0) FROM account_move
            WHERE journal_id = %s AND (posted_before OR state = 'posted') AND id != %s
        """, [self.journal_id.id, self.id or 0])
        last = self.env.cr.fetchone()[0]
        # Odoo's _locked_increment supplies the unique-index lock, native RPC
        # serialization retries and transaction-local sequence cache. Rollback
        # rolls the allocated name back with the accounting transaction.
        return "{prefix}{seq:08d}", {"prefix": self.journal_id.code + "/C/", "seq": last}

    @api.depends("journal_id", "sequence_number", "sequence_prefix", "state")
    def _compute_made_sequence_gap(self):
        super()._compute_made_sequence_gap()
        for move in self.filtered(lambda item: item.state == "posted" and "/C/" in (item.name or "")):
            # The first prospective continuous name can follow a retained
            # legacy prefix. Its predecessor still counts in this journal.
            move.made_sequence_gap = move.sequence_number > 1 and not self.sudo().search_count([
                ("journal_id", "=", move.journal_id.id), ("state", "=", "posted"),
                ("sequence_number", "=", move.sequence_number - 1),
            ], limit=1)

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            name = values.get("name", self.env.context.get("default_name"))
            if name and name != "/":
                raise UserError(_("Document numbers are assigned by posting; source references belong in Reference."))
            if any(values.get(key, self.env.context.get("default_" + key)) for key in ("sequence_number", "sequence_prefix")):
                raise UserError(_("Sequence counters cannot be supplied by callers."))
        return super().create(vals_list)

    def _post(self, soft=True):
        for move in self:
            if not move.posted_before and move.name and move.name != "/":
                raise UserError(_("This draft has a preassigned legacy number. Review and clear the draft number before posting; never renumber posted documents."))
        return super()._post(soft=soft)


class ContinuousJournalNumbering(models.Model):
    _inherit = "account.journal"

    def write(self, values):
        if {"code", "company_id", "type", "refund_sequence", "payment_sequence", "sequence_override_regex"}.intersection(values):
            for journal in self:
                changed = any(self.env["account.move"]._field_will_change(journal, values, key) for key in values)
                if changed and self.env["account.move"].sudo().search_count([
                    ("journal_id", "=", journal.id), "|", ("posted_before", "=", True), ("state", "=", "posted")
                ], limit=1):
                    # Removing a legacy regex cannot change historical names;
                    # it allows the approved prospective continuous format.
                    if set(values) == {"sequence_override_regex"} and not values["sequence_override_regex"]:
                        continue
                    raise UserError(_("A journal with posting history cannot change its number-series identity."))
        return super().write(values)
