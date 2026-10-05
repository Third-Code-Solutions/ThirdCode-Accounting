"""Exercise the PRD's four business roles through actual ORM actions."""
import json
import unittest
from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestBusinessRoleMatrix(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.roles = {}
        for role in ("administrator", "accountant", "encoder", "readonly"):
            cls.roles[role] = cls.env["res.users"].create({
                "name": "Matrix " + role, "login": "matrix-" + role,
                "company_id": cls.env.company.id, "company_ids": [Command.set(cls.env.company.ids)],
                "groups_id": [Command.set(cls.env.ref("thirdcode_accounting.group_thirdcode_" + role).ids)],
            })

    def _invoice_values(self, kind):
        purchase = kind == "in_invoice"
        return {"company_id": self.env.company.id, "move_type": kind,
            "journal_id": self.company_data["default_journal_purchase" if purchase else "default_journal_sale"].id,
            "partner_id": self.partner_a.id, "invoice_date": fields.Date.today(),
            "invoice_line_ids": [Command.create({"name": "Role matrix source", "quantity": 1, "price_unit": 25,
                "account_id": self.company_data["default_account_expense" if purchase else "default_account_revenue"].id,
                "tax_ids": [Command.clear()]})]}

    def test_draft_post_reverse_and_immutable_document_matrix(self):
        for role, user in self.roles.items():
            for kind in ("out_invoice", "in_invoice", "out_receipt"):
                with self.subTest(role=role, kind=kind):
                    model = self.env["account.move"].with_user(user)
                    if role == "readonly":
                        with self.assertRaises(AccessError), self.cr.savepoint():
                            model.create(self._invoice_values(kind))
                        continue
                    move = model.create(self._invoice_values(kind))
                    move.write({"ref": "Draft edited by " + role})
                    if role == "encoder":
                        with self.assertRaises(AccessError), self.cr.savepoint():
                            move.action_post()
                        self.assertEqual(move.state, "draft")
                        continue
                    move.action_post()
                    self.assertEqual(move.state, "posted")
                    for actor in self.roles.values():
                        visible = move.with_user(actor)
                        self.assertEqual(visible.read(["state"])[0]["state"], "posted")
                        for operation in (lambda: visible.write({"invoice_date": "2035-01-01"}), visible.unlink, visible.button_draft):
                            with unittest.TestCase.assertRaises(self, (AccessError, UserError)), self.cr.savepoint():
                                operation()
                    reversal = self.env["account.move.reversal"].with_user(user).create({
                        "move_ids": [Command.set(move.ids)], "date": fields.Date.today(),
                        "reason": "Matrix correction", "journal_id": move.journal_id.id,
                    })
                    reversal.reverse_moves()
                    self.assertEqual(move.state, "posted")
                    self.assertTrue(move.reversal_move_ids)

    def test_settlement_reconciliation_matrix(self):
        for role, user in self.roles.items():
            with self.subTest(role=role):
                invoice = self.env["account.move"].create(self._invoice_values("out_invoice"))
                invoice.action_post()
                refund = self.env["account.move"].create({**self._invoice_values("out_invoice"), "move_type": "out_refund"})
                refund.action_post()
                lines = (invoice | refund).line_ids.filtered(lambda line: line.account_id.account_type == "asset_receivable").with_user(user)
                if role in {"encoder", "readonly"}:
                    with self.assertRaises(AccessError), self.cr.savepoint():
                        lines.reconcile()
                    self.assertEqual(invoice.amount_residual, 25)
                else:
                    lines.reconcile()
                    self.assertEqual(invoice.amount_residual, 0)
                    self.assertEqual(refund.amount_residual, 0)

    def test_encoder_cannot_bypass_settlement_guard_with_native_sudo_paths(self):
        invoice = self.env["account.move"].create(self._invoice_values("out_invoice"))
        refund = self.env["account.move"].create({**self._invoice_values("out_invoice"), "move_type": "out_refund"})
        (invoice | refund).action_post()
        lines = (invoice | refund).line_ids.filtered(lambda line: line.account_id.account_type == "asset_receivable")
        values = {"debit_move_id": lines.filtered(lambda line: line.balance > 0).id,
                  "credit_move_id": lines.filtered(lambda line: line.balance < 0).id,
                  "amount": 10, "debit_amount_currency": 10, "credit_amount_currency": 10}
        encoder = self.roles["encoder"]
        accountant = self.roles["accountant"]
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env["account.partial.reconcile"].with_user(encoder).sudo().create(values)
        partial = self.env["account.partial.reconcile"].with_user(accountant).create(values)
        self.assertEqual(invoice.amount_residual, 15)
        with self.assertRaises(AccessError), self.cr.savepoint():
            partial.with_user(encoder).sudo().unlink()
        self.assertEqual(invoice.amount_residual, 15)
        partial.unlink()
        lines.with_user(accountant).reconcile()
        self.assertEqual(invoice.amount_residual, 0)
        for operation in (lines.with_user(encoder).remove_move_reconcile,
                          lines.full_reconcile_id.with_user(encoder).sudo().unlink):
            with self.assertRaises(AccessError), self.cr.savepoint():
                operation()
            self.assertEqual(invoice.amount_residual, 0)
        lines.with_user(accountant).remove_move_reconcile()
        self.assertEqual(invoice.amount_residual, 25)
        self.assertEqual(refund.amount_residual, 25)

    def test_reports_permissions_and_audit_matrix(self):
        for role, user in self.roles.items():
            with self.subTest(role=role):
                reports = self.env["trial.balance.report.wizard"].with_user(user)
                if role == "encoder":
                    with self.assertRaises(AccessError), self.cr.savepoint():
                        reports.create({"company_id": self.env.company.id})
                else:
                    wizard = reports.create({"company_id": self.env.company.id})
                    for action in (wizard.button_export_html, wizard.button_export_pdf, wizard.button_export_xlsx):
                        self.assertTrue(action())
                log = self.env["auditlog.log"].with_user(user).search([], limit=1)
                self.assertTrue(log, "Business role must see its company audit history")
                with self.assertRaises(AccessError), self.cr.savepoint():
                    log.write({"name": "Forbidden rewrite"})
                with self.assertRaises(AccessError), self.cr.savepoint():
                    log.unlink()
                if role != "administrator":
                    with self.assertRaises(AccessError), self.cr.savepoint():
                        self.env["thirdcode.employee.wizard"].with_user(user).create({
                            "name": "Forbidden", "login": "forbidden-matrix-" + role,
                            "role": "administrator", "password": "Disposable-test-password-only",
                        })

    def test_direct_report_rendering_rechecks_role_and_company(self):
        reader = self.roles["readonly"]
        encoder = self.roles["encoder"]
        other = self.env["res.company"].create({"name": "Unselected report scope"})
        context = {"allowed_company_ids": self.env.company.ids, "active_ids": self.partner_a.ids}
        for model in ("trial.balance.report.wizard", "general.ledger.report.wizard", "activity.statement.wizard"):
            wizard = self.env[model].with_user(reader).with_context(**context).create({"company_id": self.env.company.id})
            for method, renderer in (("button_export_html", "_render_qweb_html"), ("button_export_xlsx", "_render_xlsx")):
                with self.subTest(model=model, renderer=renderer):
                    action = getattr(wizard, method)()
                    data = json.loads(json.dumps(action["data"], default=str))
                    # The web client applies the report action's context; its
                    # active_ids replace the partner selection with wizard ids
                    # for financial XLSX reports.
                    report_context = {**context, **action.get("context", {})}
                    reports = self.env["ir.actions.report"].with_user(reader).with_context(**report_context)
                    output, _format = getattr(reports, renderer)(action["report_name"], [], data=data)
                    self.assertTrue(output)
                    if renderer == "_render_xlsx":
                        self.assertTrue(output.startswith(b"PK"), "Expected an actual XLSX archive")
                    for actor, options in ((reader, {**data, "company_id": other.id}), (encoder, data)):
                        with self.assertRaises(AccessError):
                            getattr(reports.with_user(actor), renderer)(action["report_name"], [], data=options)

    def test_statement_export_rechecks_changed_company(self):
        wizard = self.env["activity.statement.wizard"].with_context(active_ids=self.partner_a.ids).create({"company_id": self.env.company.id})
        wizard.company_id = self.env["res.company"].create({"name": "Unselected statement scope"})
        wizard = wizard.with_context(allowed_company_ids=self.env.company.ids)
        for method in (wizard.button_export_html, wizard.button_export_pdf, wizard.button_export_xlsx):
            with self.assertRaises(AccessError):
                method()

    def test_close_reopen_matrix(self):
        period = self.env["thirdcode.accounting.period"].with_user(self.roles["administrator"]).create({
            "name": "Matrix empty period", "company_id": self.env.company.id,
            "date_start": "2035-02-01", "date_end": "2035-02-28",
        })
        for role in ("encoder", "readonly"):
            with self.assertRaises(AccessError), self.cr.savepoint():
                period.with_user(self.roles[role]).action_close()
        for closer in ("accountant", "administrator"):
            period.with_user(self.roles[closer]).action_close()
            self.assertEqual(period.state, "closed")
            for role in ("accountant", "encoder", "readonly"):
                with self.assertRaises(AccessError), self.cr.savepoint():
                    period.with_user(self.roles[role]).action_reopen()
            period.with_user(self.roles["administrator"]).action_reopen()
            self.assertEqual(period.state, "open")
