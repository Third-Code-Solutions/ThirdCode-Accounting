"""Reconcile bank evidence by posting an adjustment, preserving the source entry."""
import hashlib
import json
from decimal import Decimal

from odoo import _, api, Command, fields, models
from odoo.exceptions import AccessError, UserError

_MATCH_TOKEN = object()


class StatementMatching(models.Model):
    _inherit = "account.bank.statement.line"

    thirdcode_match_move_id = fields.Many2one("account.move", readonly=True, copy=False, check_company=True)
    thirdcode_match_fingerprint = fields.Char(readonly=True, copy=False)
    thirdcode_match_history_ids = fields.One2many("account.move", "thirdcode_statement_match_id", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        if any(values.get(key, self.env.context.get("default_" + key)) for values in vals_list
               for key in ("thirdcode_match_move_id", "thirdcode_match_fingerprint")):
            raise AccessError(_("Statement matches are recorded only by the matching action."))
        return super().create(vals_list)

    def write(self, values):
        if {"thirdcode_match_move_id", "thirdcode_match_fingerprint"}.intersection(values):
            if self.env.context.get("thirdcode_match_token") is not _MATCH_TOKEN:
                raise AccessError(_("Statement matching history cannot be changed directly."))
        return super().write(values)

    def action_match_thirdcode_items(self, allocations, journal_id, accounting_date):
        """Signed company-currency allocations against posted reconcilable items.

        Each allocation contains line_id and amount (same sign as the selected
        residual). Partial allocation is supported without editing either entry.
        """
        self.ensure_one()
        self.check_access("write")
        if not (self.env.user.has_group("thirdcode_accounting.group_thirdcode_accountant")
                or self.env.user.has_group("thirdcode_accounting.group_thirdcode_administrator")):
            raise AccessError(_("Only an Accountant or Administrator may match statements."))
        if self.company_id not in self.env.companies:
            raise AccessError(_("Select an active company."))
        day = fields.Date.to_date(accounting_date)
        if not day or day < self.date:
            raise UserError(_("The matching date cannot precede the statement entry."))
        if not isinstance(allocations, list) or not allocations:
            raise UserError(_("Select posted journal items and allocation amounts."))
        normalized = []
        for item in allocations:
            if not isinstance(item, dict) or set(item) != {"line_id", "amount"}:
                raise UserError(_("Each allocation requires only line_id and amount."))
            try:
                amount = Decimal(str(item["amount"]))
                line_id = int(item["line_id"])
            except (ValueError, TypeError, ArithmeticError):
                raise UserError(_("Invalid matching allocation."))
            if not amount.is_finite() or not amount or line_id <= 0:
                raise UserError(_("Allocation amounts must be finite and non-zero."))
            normalized.append({"line_id": line_id, "amount": str(amount.normalize())})
        normalized.sort(key=lambda item: item["line_id"])
        if len({item["line_id"] for item in normalized}) != len(normalized):
            raise UserError(_("Select each journal item only once."))
        fingerprint = hashlib.sha256(json.dumps([normalized, journal_id, str(day)], sort_keys=True).encode()).hexdigest()
        self.flush_recordset()
        self.env.cr.execute("SELECT id FROM account_bank_statement_line WHERE id = %s FOR UPDATE", [self.id])
        self.invalidate_recordset()
        if self.thirdcode_match_move_id:
            reversed_match = self.thirdcode_match_move_id.reversal_move_ids.filtered(lambda move: move.state == "posted")
            if not reversed_match and self.thirdcode_match_fingerprint == fingerprint and self.is_reconciled:
                return self.thirdcode_match_move_id.id
            if not reversed_match:
                raise UserError(_("This statement already has a recorded match. Reverse the matching adjustment before rematching."))
        self.env["thirdcode.accounting.period"]._check_date_allowed(self.company_id, day)
        if self.move_id.state != "posted" or self.is_reconciled:
            raise UserError(_("Select an unreconciled posted statement line."))
        if self.foreign_currency_id or self.currency_id != self.company_id.currency_id:
            raise UserError(_("This matching workflow supports company-currency statements only."))
        journal = self.env["account.journal"].browse(journal_id).exists()
        if not journal or journal.company_id != self.company_id or journal.type != "general":
            raise UserError(_("Choose a general journal in this company for the adjustment."))
        _liquidity, suspense, _other = self._seek_for_lines()
        if not suspense or not all(suspense.account_id.mapped("reconcile")):
            raise UserError(_("The bank suspense account must allow reconciliation."))
        lines = self.env["account.move.line"].browse([item["line_id"] for item in normalized]).exists()
        lines.check_access("read")
        if len(lines) != len(normalized):
            raise UserError(_("A selected journal item no longer exists."))
        self.env.cr.execute("SELECT id FROM account_move_line WHERE id IN %s ORDER BY id FOR UPDATE", [tuple(lines.ids)])
        lines.invalidate_recordset()
        currency = self.company_id.currency_id
        total = sum(Decimal(item["amount"]) for item in normalized)
        if any(Decimal(item["amount"]).quantize(Decimal(str(currency.rounding))) != Decimal(item["amount"]) for item in normalized):
            raise UserError(_("Use company-currency precision for each allocation."))
        if currency.compare_amounts(float(total), self.amount):
            raise UserError(_("Allocations must equal the signed bank statement amount."))
        values = []
        for index, item in enumerate(normalized, start=1):
            line = lines.filtered(lambda candidate: candidate.id == item["line_id"])
            amount = float(Decimal(item["amount"]))
            if (line.company_id != self.company_id or line.parent_state != "posted"
                    or not line.account_id.reconcile or line.account_id in (self.journal_id.default_account_id | suspense.account_id)
                    or line.currency_id != currency or line.date > day):
                raise UserError(_("Select company-currency posted reconcilable items dated on or before the matching date; exclude this bank and suspense account."))
            if amount * line.amount_residual <= 0 or currency.compare_amounts(abs(amount), abs(line.amount_residual)) > 0:
                raise UserError(_("An allocation exceeds or opposes the item's remaining balance."))
            values.append(Command.create({"sequence": index, "name": self.payment_ref or self.display_name, "account_id": line.account_id.id,
                "partner_id": line.partner_id.id, "debit": max(-amount, 0), "credit": max(amount, 0)}))
        values.append(Command.create({"sequence": len(normalized) + 1, "name": "Statement suspense clearance", "account_id": suspense.account_id.id,
            "debit": max(float(total), 0), "credit": max(-float(total), 0)}))
        adjustment = self.env["account.move"].with_context(thirdcode_match_token=_MATCH_TOKEN).create({"company_id": self.company_id.id, "journal_id": journal.id,
            "thirdcode_statement_match_id": self.id,
            "date": day, "ref": "Bank statement match: " + (self.payment_ref or self.display_name), "line_ids": values})
        adjustment.action_post()
        (suspense | adjustment.line_ids.filtered(lambda line: line.account_id == suspense.account_id)).reconcile()
        for index, item in enumerate(normalized, start=1):
            target = lines.filtered(lambda line: line.id == item["line_id"])
            correction = adjustment.line_ids.filtered(lambda line: line.sequence == index)
            (target | correction).reconcile()
        self.move_id.checked = True
        self.with_context(thirdcode_match_token=_MATCH_TOKEN).write({"thirdcode_match_move_id": adjustment.id,
            "thirdcode_match_fingerprint": fingerprint})
        if not self.is_reconciled:
            raise UserError(_("The native statement residual did not clear; the match has been rolled back."))
        return adjustment.id

    def action_reverse_thirdcode_match(self, accounting_date):
        self.ensure_one()
        self.check_access("write")
        if not (self.env.user.has_group("thirdcode_accounting.group_thirdcode_accountant")
                or self.env.user.has_group("thirdcode_accounting.group_thirdcode_administrator")):
            raise AccessError(_("Only an Accountant or Administrator may reverse statement matches."))
        if self.company_id not in self.env.companies:
            raise AccessError(_("Select an active company."))
        self.flush_recordset()
        self.env.cr.execute("SELECT id FROM account_bank_statement_line WHERE id = %s FOR UPDATE", [self.id])
        self.invalidate_recordset()
        match = self.thirdcode_match_move_id
        if not match:
            raise UserError(_("This statement has no matching adjustment."))
        previous = match.reversal_move_ids.filtered(lambda move: move.state == "posted")
        if previous:
            return previous[0].id
        day = fields.Date.to_date(accounting_date)
        if not day or day < match.date:
            raise UserError(_("The reversal cannot precede the matching adjustment."))
        self.env["thirdcode.accounting.period"]._check_date_allowed(self.company_id, day)
        reversal = match._reverse_moves([{"date": day, "ref": _("Reverse bank match: %s", match.name)}], cancel=True)
        if self.is_reconciled:
            raise UserError(_("The statement did not reopen for matching; the reversal is rolled back."))
        return reversal.id

    def action_open_thirdcode_match_reversal(self):
        action = self.action_open_thirdcode_match()
        action["name"] = _("Reverse bank statement match")
        action["context"]["default_reverse_only"] = True
        action["context"]["default_journal_id"] = self.thirdcode_match_move_id.journal_id.id
        return action

    def action_open_thirdcode_match(self):
        self.ensure_one()
        self.check_access("read")
        return {"type": "ir.actions.act_window", "name": _("Match bank statement"),
                "res_model": "thirdcode.statement.match.wizard", "view_mode": "form", "target": "new",
                "context": {"default_statement_line_id": self.id}}


class StatementMatchWizard(models.TransientModel):
    _name = "thirdcode.statement.match.wizard"
    _description = "Match bank evidence without editing posted entries"

    statement_line_id = fields.Many2one("account.bank.statement.line", required=True, readonly=True)
    company_id = fields.Many2one(related="statement_line_id.company_id")
    journal_id = fields.Many2one("account.journal", required=True, domain="[('company_id', '=', company_id), ('type', '=', 'general')]")
    accounting_date = fields.Date(required=True, default=fields.Date.context_today)
    reverse_only = fields.Boolean()
    line_ids = fields.One2many("thirdcode.statement.match.wizard.line", "wizard_id")

    def action_match(self):
        self.ensure_one()
        if self.reverse_only:
            self.statement_line_id.action_reverse_thirdcode_match(str(self.accounting_date))
            return {"type": "ir.actions.act_window_close"}
        self.statement_line_id.action_match_thirdcode_items([
            {"line_id": line.move_line_id.id, "amount": line.amount} for line in self.line_ids
        ], self.journal_id.id, str(self.accounting_date))
        return {"type": "ir.actions.act_window_close"}


class StatementMatchWizardLine(models.TransientModel):
    _name = "thirdcode.statement.match.wizard.line"
    _description = "Statement allocation"

    wizard_id = fields.Many2one("thirdcode.statement.match.wizard", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="wizard_id.company_id")
    move_line_id = fields.Many2one("account.move.line", required=True,
        domain="[('company_id', '=', company_id), ('parent_state', '=', 'posted'), ('account_id.reconcile', '=', True), ('reconciled', '=', False)]")
    amount = fields.Float(required=True, digits="Account")

    @api.onchange("move_line_id")
    def _onchange_item(self):
        self.amount = self.move_line_id.amount_residual


class StatementMatchMove(models.Model):
    _inherit = "account.move"

    thirdcode_statement_match_id = fields.Many2one("account.bank.statement.line", readonly=True, copy=False, check_company=True, ondelete="restrict", index=True)

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("thirdcode_match_token") is not _MATCH_TOKEN and any(
            values.get("thirdcode_statement_match_id", self.env.context.get("default_thirdcode_statement_match_id")) for values in vals_list
        ):
            raise AccessError(_("Matching links are created only by the statement matching action."))
        return super().create(vals_list)

    def write(self, values):
        if "thirdcode_statement_match_id" in values:
            raise AccessError(_("Matching history links cannot be changed."))
        return super().write(values)
