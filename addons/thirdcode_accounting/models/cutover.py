import base64
import hashlib
import json
from decimal import Decimal

from odoo import _, api, Command, fields, models
from odoo.exceptions import AccessError, UserError

from .cutover_math import build_cutover_plan, CutoverPolicyError

_CUTOVER_TOKEN = object()


class CutoverBatch(models.Model):
    _inherit = "thirdcode.migration.batch"

    cutover_payload = fields.Json(copy=False)
    cutover_mapping_file = fields.Binary(attachment=True, copy=False)
    cutover_mapping_filename = fields.Char(copy=False)
    cutover_review = fields.Text(readonly=True, copy=False)
    cutover_fingerprint = fields.Char(readonly=True, copy=False)
    cutover_result = fields.Json(readonly=True, copy=False)
    source_archive = fields.Binary(attachment=True, copy=False)
    source_archive_filename = fields.Char(copy=False)
    cutover_move_ids = fields.One2many("account.move", "thirdcode_cutover_batch_id", readonly=True)

    def _cutover_plan(self):
        self.ensure_one()
        self._check_migration_access()
        if self.company_id not in self.env.companies:
            raise AccessError(_("Select an active company."))
        if not self.cutover_date or not self.opening_balance_owner:
            raise UserError(_("Record the cutover date and the finance person accountable for opening balances."))
        if self.retention_policy != "archive_only":
            raise UserError(_("This residual snapshot policy requires 'Open items only; older history archived'. Confirm the client's retention choice before applying it; it does not load historical transactions into the live ledger."))
        payload = self.cutover_payload or {}
        accounts = self.env["account.account"].search([("company_ids", "in", self.company_id.ids)])
        try:
            plan = build_cutover_plan(payload, {account.id: account.account_type for account in accounts}, str(self.company_id.currency_id.rounding))
        except (CutoverPolicyError, KeyError, TypeError, ValueError) as exc:
            raise UserError(_("Invalid cutover accounting policy: %s", str(exc)))
        journal = self.env["account.journal"].browse(payload.get("journal_id")).exists()
        if not journal or journal.company_id != self.company_id or journal.type != "general":
            raise UserError(_("Choose a general journal in the cutover company."))
        for entry in plan["entries"]:
            if entry["document_date"] and fields.Date.to_date(entry["document_date"]) > self.cutover_date:
                raise UserError(_("Source documents cannot be later than cutover."))
            for line in entry["lines"]:
                if line.get("partner_id"):
                    partner = self.env["res.partner"].browse(line["partner_id"]).exists()
                    partner.check_access("read")
                    if not partner or (partner.company_id and partner.company_id != self.company_id):
                        raise UserError(_("A mapped partner is missing or belongs to another company."))
        return plan

    def action_preview_cutover(self):
        return self._cutover_plan()

    def action_review_cutover_file(self):
        self.ensure_one()
        self._check_migration_access()
        if self.state != "draft" or not self.cutover_mapping_file:
            raise UserError(_("Upload the reviewed mapping package to a draft cutover batch."))
        try:
            payload = json.loads(base64.b64decode(self.cutover_mapping_file).decode("utf-8"))
        except (ValueError, UnicodeError):
            raise UserError(_("The mapping package must be valid UTF-8 JSON."))
        self.cutover_payload = payload
        plan = self._cutover_plan()
        lines = [_("Technical validation passed: %s opening components. This is not client sign-off.", len(plan["entries"]))]
        for account_id, amount in plan["expected_balances"].items():
            account = self.env["account.account"].browse(int(account_id)).with_company(self.company_id)
            lines.append("%s %s: %s" % (account.code, account.name, amount))
        self.with_context(thirdcode_cutover_token=_CUTOVER_TOKEN).write({"cutover_review": "\n".join(lines)})
        return {"type": "ir.actions.client", "tag": "display_notification", "params": {
            "title": _("Cutover package checked"), "message": _("Review the per-account source balances before applying."), "type": "success"}}

    def action_apply_cutover(self):
        self.ensure_one()
        self._check_migration_access()
        if not self.env.user.has_group("thirdcode_accounting.group_thirdcode_administrator"):
            raise AccessError(_("Only an Administrator may apply a cutover."))
        plan = self._cutover_plan()
        if not self.source_archive or not self.source_archive_filename:
            raise UserError(_("Retain the original source archive before applying the cutover."))
        digest = hashlib.sha256(base64.b64decode(self.source_archive)).hexdigest()
        if digest != self.source_file_hash:
            raise UserError(_("The retained source archive does not match its recorded SHA-256."))
        fingerprint = hashlib.sha256(json.dumps([self.company_id.id, str(self.cutover_date), digest, self.cutover_payload], sort_keys=True).encode()).hexdigest()
        self.company_id._thirdcode_lock_period_state(exclusive=True)
        self.flush_recordset()
        self.env.cr.execute("SELECT id FROM thirdcode_migration_batch WHERE id = %s FOR UPDATE", [self.id])
        self.invalidate_recordset()
        if self.cutover_fingerprint:
            if self.cutover_fingerprint != fingerprint or not self.cutover_move_ids or any(move.state != "posted" for move in self.cutover_move_ids):
                raise UserError(_("This batch already contains different or incomplete cutover content."))
            return self.cutover_result
        if self.state != "draft" or self.row_ids:
            raise UserError(_("Apply a new cutover from a draft batch without manually supplied reconciliation rows."))
        with self.env.registry.cursor() as latest:
            latest.execute("SELECT EXISTS(SELECT 1 FROM account_move WHERE company_id = %s AND state IN ('draft', 'posted'))", [self.company_id.id])
            committed_postings = latest.fetchone()[0]
        if committed_postings or self.env["account.move"].sudo().search_count([("company_id", "=", self.company_id.id), ("state", "in", ["draft", "posted"])], limit=1):
            raise UserError(_("A cutover snapshot requires an empty ledger, including drafts. Existing books must be reconciled separately; do not add a second opening."))
        self.env["thirdcode.accounting.period"]._check_date_allowed(self.company_id, self.cutover_date)
        for entry in plan["entries"]:
            values = []
            for line in entry["lines"]:
                balance = Decimal(line["balance"])
                values.append(Command.create({"name": entry["reference"], "account_id": line["account_id"],
                    "partner_id": line.get("partner_id") or False, "date_maturity": line.get("due_date"),
                    "debit": float(max(balance, 0)), "credit": float(max(-balance, 0))}))
            self.env["account.move"].with_context(thirdcode_cutover_token=_CUTOVER_TOKEN).create({
                "company_id": self.company_id.id, "journal_id": self.cutover_payload["journal_id"],
                "date": self.cutover_date, "ref": entry["reference"], "thirdcode_is_opening_balance": True,
                "thirdcode_source_identifier": "CUTOVER/%s/%s" % (self.id, entry["source_id"]),
                "thirdcode_cutover_batch_id": self.id, "thirdcode_source_document_date": entry["document_date"],
                "line_ids": values,
            }).action_post()
        actual = {str(account.id): Decimal(str(balance)) for account, balance in self.env["account.move.line"]._read_group(
            [("company_id", "=", self.company_id.id), ("parent_state", "=", "posted")], ["account_id"], ["balance:sum"])}
        expected = {key: Decimal(value) for key, value in plan["expected_balances"].items()}
        rows = []
        for key in sorted(set(expected) | set(actual), key=int):
            source, target = expected.get(key, Decimal(0)), actual.get(key, Decimal(0))
            if self.company_id.currency_id.compare_amounts(float(source), float(target)):
                raise UserError(_("Cutover account %s does not match the source; the transaction is rolled back.", key))
            rows.append(Command.create({"source_identifier": key, "target_model": "account.account", "target_id": int(key),
                "source_debit": float(max(source, 0)), "source_credit": float(max(-source, 0)),
                "target_debit": float(max(target, 0)), "target_credit": float(max(-target, 0))}))
        result = {"policy": plan["policy"], "source_archive_sha256": digest, "move_ids": self.cutover_move_ids.ids,
                  "balances": {key: str(value) for key, value in actual.items()}, "line_by_line_equal": True,
                  "acceptance": "Technical reconciliation only; client sign-off and parallel month remain required"}
        self.with_context(thirdcode_cutover_token=_CUTOVER_TOKEN).write({"row_ids": rows})
        self.with_context(thirdcode_cutover_token=_CUTOVER_TOKEN).sudo().write({"state": "loaded", "loaded_by": self.env.uid,
            "loaded_at": fields.Datetime.now(), "cutover_fingerprint": fingerprint, "cutover_result": result})
        return result

    @api.model_create_multi
    def create(self, vals_list):
        if any(values.get(key, self.env.context.get("default_" + key)) for values in vals_list
               for key in ("cutover_fingerprint", "cutover_result", "cutover_review")):
            raise AccessError(_("Cutover results are generated by the import action."))
        return super().create(vals_list)

    def write(self, values):
        if self.env.context.get("thirdcode_cutover_token") is not _CUTOVER_TOKEN:
            if {"cutover_fingerprint", "cutover_result", "cutover_review"}.intersection(values):
                raise AccessError(_("Cutover results are immutable."))
            locked = {"cutover_payload", "cutover_mapping_file", "cutover_mapping_filename", "source_archive", "source_archive_filename", "source_file_hash",
                      "company_id", "cutover_date", "row_ids", "opening_balance_owner", "source_system", "source_file_name"}
            if locked.intersection(values) and any(batch.cutover_fingerprint for batch in self):
                raise UserError(_("The imported cutover and retained source archive cannot be changed."))
        return super().write(values)

    def unlink(self):
        if any(batch.cutover_fingerprint for batch in self):
            raise UserError(_("Imported cutover evidence must be retained."))
        return super().unlink()


class CutoverMove(models.Model):
    _inherit = "account.move"

    thirdcode_cutover_batch_id = fields.Many2one("thirdcode.migration.batch", readonly=True, copy=False, ondelete="restrict", index=True)
    thirdcode_source_document_date = fields.Date(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("thirdcode_cutover_token") is not _CUTOVER_TOKEN and any(
            values.get("thirdcode_cutover_batch_id", self.env.context.get("default_thirdcode_cutover_batch_id")) for values in vals_list
        ):
            raise AccessError(_("Cutover links can only be created by the atomic cutover action."))
        return super().create(vals_list)

    def write(self, values):
        if "thirdcode_cutover_batch_id" in values:
            raise AccessError(_("Cutover source links cannot be changed."))
        return super().write(values)


class CutoverReconciliationRow(models.Model):
    _inherit = "thirdcode.migration.row"

    def write(self, values):
        if set(values) - {"state", "error_message"} and any(row.batch_id.cutover_fingerprint for row in self):
            raise UserError(_("Imported source and target reconciliation amounts are immutable."))
        return super().write(values)

    def unlink(self):
        if any(row.batch_id.cutover_fingerprint for row in self):
            raise UserError(_("Imported reconciliation evidence must be retained."))
        return super().unlink()


class CutoverArchive(models.Model):
    _inherit = "ir.attachment"

    def _check_cutover_archive(self):
        for attachment in self.filtered(lambda item: item.res_model == "thirdcode.migration.batch" and item.res_field in {"source_archive", "cutover_mapping_file"}):
            batch = self.env["thirdcode.migration.batch"].sudo().browse(attachment.res_id).exists()
            if batch.cutover_fingerprint:
                raise UserError(_("The retained cutover source archive is immutable."))

    def write(self, values):
        if {"datas", "raw", "db_datas", "store_fname", "checksum", "res_model", "res_id", "res_field", "type", "url"}.intersection(values):
            self._check_cutover_archive()
        return super().write(values)

    def unlink(self):
        self._check_cutover_archive()
        return super().unlink()
