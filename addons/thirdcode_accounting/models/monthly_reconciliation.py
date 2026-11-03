"""Read-only monthly bank-to-ledger review; client-specific format is provisional."""
from calendar import monthrange
from math import fsum

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class MonthlyBankReconciliation(models.Model):
    _inherit = "thirdcode.bank.reconciliation"

    def _check_monthly_report_scope(self):
        user = self.env.user
        if not any(user.has_group("thirdcode_accounting.group_thirdcode_" + role)
                   for role in ("readonly", "accountant", "administrator")) or (
            user.has_group("thirdcode_accounting.group_thirdcode_encoder")
            and not any(user.has_group("thirdcode_accounting.group_thirdcode_" + role)
                        for role in ("accountant", "administrator"))
        ):
            raise AccessError(_("Only Read-only, Accountant or Administrator users may run this report."))
        self.check_access("read")
        if any(record.company_id not in self.env.companies for record in self):
            raise AccessError(_("You may only run reports for active companies."))

    def _check_monthly_report_period(self):
        self.ensure_one()
        start, end = self.date_start, self.date_end
        if (not start or not end or start.day != 1
                or (start.year, start.month) != (end.year, end.month)
                or end.day != monthrange(end.year, end.month)[1]):
            raise UserError(_("Select one complete calendar month for the monthly bank-to-ledger report."))
        journal = self.journal_id
        if journal.type not in ("bank", "cash") or not journal.default_account_id:
            raise UserError(_("Select a bank or cash journal with a default ledger account."))
        if journal.company_id != self.company_id:
            raise UserError(_("The journal must belong to the reconciliation company."))
        if journal.currency_id and journal.currency_id != self.currency_id:
            raise UserError(_("This report requires a journal in company currency; foreign-currency reconciliation needs a separately defined basis."))

    def _monthly_ledger_data(self):
        account = self.journal_id.default_account_id
        domain = [("company_id", "=", self.company_id.id),
                  ("account_id", "=", account.id), ("parent_state", "=", "posted")]
        model = self.env["account.move.line"]
        opening = model._read_group(domain + [("date", "<", self.date_start)], [], ["balance:sum"])[0][0]
        lines = model.search(domain + [("date", ">=", self.date_start), ("date", "<=", self.date_end)],
                             order="date, move_id, id")
        running = opening
        rows = []
        for line in lines:
            running = self.currency_id.round(running + line.balance)
            rows.append({"line": line, "running_balance": running})
        return {"account": account, "opening": opening, "closing": running,
                "debit": fsum(lines.mapped("debit")), "credit": fsum(lines.mapped("credit")), "rows": rows}

    def _monthly_statement_data(self):
        lines = self.bank_statement_line_ids.sorted(lambda line: (line.date, line.id))
        if any(line.company_id != self.company_id or line.journal_id != self.journal_id
               or not self.date_start <= line.date <= self.date_end for line in lines):
            raise UserError(_("Every linked statement line must belong to this company, journal and calendar month."))
        # Linked rows are the evidence scope. Other journal rows are disclosed,
        # never silently added to the selected statement's balance calculation.
        other = self.env["account.bank.statement.line"].search([
            ("company_id", "=", self.company_id.id), ("journal_id", "=", self.journal_id.id),
            ("date", ">=", self.date_start), ("date", "<=", self.date_end), ("id", "not in", lines.ids),
        ], order="date, id")
        running = self.opening_balance
        rows = []
        for line in lines:
            running = self.currency_id.round(running + line.amount)
            rows.append({"line": line, "running_balance": running,
                         "matched": line.state == "posted" and line.is_reconciled})
        unmatched = lines.filtered(lambda line: line.state != "posted" or not line.is_reconciled)
        return {"rows": rows, "other_lines": other, "calculated_closing": running,
                "activity_difference": self.currency_id.round(self.closing_balance - running),
                "receipts": fsum(amount for amount in lines.mapped("amount") if amount > 0),
                "payments": -fsum(amount for amount in lines.mapped("amount") if amount < 0),
                "unmatched_receipts": fsum(amount for amount in unmatched.mapped("amount") if amount > 0),
                "unmatched_payments": -fsum(amount for amount in unmatched.mapped("amount") if amount < 0),
                "matched_count": len(lines - unmatched), "unmatched_count": len(unmatched),
                "unposted_count": len(lines.filtered(lambda line: line.state != "posted"))}

    def _monthly_matching_adjustments(self):
        history = self.bank_statement_line_ids.thirdcode_match_history_ids
        moves = (history | history.reversal_move_ids).filtered(lambda move: move.state == "posted")
        rows = []
        for move in moves.sorted(lambda move: (move.date, move.id)):
            if move.company_id != self.company_id:
                raise AccessError(_("Matching adjustments must belong to the reconciliation company."))
            bank_lines = move.line_ids.filtered(lambda line: line.account_id == self.journal_id.default_account_id)
            rows.append({"move": move, "bank_impact": fsum(bank_lines.mapped("balance")),
                         "in_period": self.date_start <= move.date <= self.date_end})
        return rows

    def _monthly_review_warnings(self, ledger, statement, difference):
        warnings = []
        if not statement["rows"]:
            warnings.append(_("No statement lines are linked. Statement activity completeness is not established, even when balances agree."))
        if statement["other_lines"]:
            warnings.append(_("Other statement lines exist for this journal and month. Review the coverage list; they are excluded from this statement's activity totals."))
        if statement["unposted_count"]:
            warnings.append(_("Linked statement rows include unposted entries. Their bank amounts appear in statement activity, but only posted entries appear in the ledger."))
        if not self.currency_id.is_zero(statement["activity_difference"]):
            warnings.append(_("Statement opening plus linked activity does not equal the recorded statement closing balance."))
        if not self.currency_id.is_zero(difference):
            warnings.append(_("The bank-to-ledger reconciliation has an unresolved difference."))
        if statement["unmatched_count"]:
            warnings.append(_("Statement rows remain unmatched at generation time. Their amounts are not automatically deposits in transit or outstanding payments."))
        if self.currency_id.compare_amounts(self.ledger_balance, ledger["closing"]):
            warnings.append(_("The stored reconciliation ledger balance differs from the current posted ledger. This report uses the current posted ledger without changing the record."))
        if not self.with_context(bin_size=True).evidence_file or not self.evidence_filename:
            warnings.append(_("Statement source evidence is missing. Entered balances have no attached source in this record."))
        return warnings

    def get_monthly_report_data(self):
        self._check_monthly_report_scope()
        self.ensure_one()
        self._check_monthly_report_period()
        ledger = self._monthly_ledger_data()
        statement = self._monthly_statement_data()
        expected = self.currency_id.round(ledger["closing"] - self.outstanding_deposits + self.outstanding_payments)
        difference = self.currency_id.round(self.closing_balance - expected)
        return {"generated_at": fields.Datetime.now(), "ledger": ledger, "statement": statement,
                "expected_statement_closing": expected, "difference": difference,
                "adjustments": self._monthly_matching_adjustments(),
                "warnings": self._monthly_review_warnings(ledger, statement, difference)}

    def action_print_monthly_report(self):
        self._check_monthly_report_scope()
        for record in self:
            record._check_monthly_report_period()
        return self.env.ref("thirdcode_accounting.action_report_monthly_bank_reconciliation").report_action(self)


class MonthlyBankReconciliationReport(models.AbstractModel):
    _name = "report.thirdcode_accounting.report_monthly_bank_reconciliation"
    _description = "Monthly bank-to-ledger reconciliation report"

    @api.model
    def _get_report_values(self, docids, data=None):
        records = self.env["thirdcode.bank.reconciliation"].browse(docids)
        records._check_monthly_report_scope()
        if not records or records.exists() != records:
            raise UserError(_("Select an existing reconciliation record."))
        return {"doc_ids": records.ids, "doc_model": records._name, "docs": records,
                "monthly_data": {record.id: record.get_monthly_report_data() for record in records}}
