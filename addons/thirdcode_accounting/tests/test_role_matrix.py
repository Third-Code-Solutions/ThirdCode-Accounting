"""Exercise the PRD's four business roles through actual ORM actions."""
import json
import unittest
from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from .common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestBusinessRoleMatrix(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (cls.partner_a | cls.partner_b).write({"company_id": cls.env.company.id})
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
        other = self.env["res.company"].sudo().create({"name": "Unselected report scope"})
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
        wizard.company_id = self.env["res.company"].sudo().create({"name": "Unselected statement scope"})
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

    def test_shared_contact_accounting_and_company_bank_setup(self):
        from odoo import SUPERUSER_ID
        shared = self.partner_a.with_user(SUPERUSER_ID).copy({"name": "Approved shared business", "company_id": False})
        shared.with_user(SUPERUSER_ID).write({"thirdcode_shared_company_ids": [Command.set(self.env.company.ids)]})
        accountant = self.roles["accountant"]
        for kind in ["out_invoice", "in_invoice"]:
            move = self.env["account.move"].with_user(accountant).create({**self._invoice_values(kind), "partner_id": shared.id})
            move.action_post()
            refund = move._reverse_moves([{"date": fields.Date.today()}])
            refund.action_post()
            lines = (move | refund).line_ids.filtered(lambda line: line.account_id.account_type in {"asset_receivable", "liability_payable"})
            # Native reversal may already settle the pair. Exercise explicit
            # removal and reconciliation under the accountant identity as well.
            lines.remove_move_reconcile()
            self.assertFalse(any(lines.mapped("reconciled")))
            lines.reconcile()
            self.assertEqual(move.amount_residual, 0)
            self.assertEqual(refund.amount_residual, 0)
        journal = self.company_data["default_journal_bank"].with_user(self.roles["administrator"])
        journal.write({"bank_acc_number": "TEST-COMPANY-BANK-123"})
        self.assertEqual(journal.bank_account_id.partner_id, self.env.company.partner_id)
        self.assertFalse(shared.company_id)

    def test_historical_shared_backfill_preserves_ownership_and_is_one_time(self):
        from odoo import SUPERUSER_ID
        partners = self.env["res.partner"].with_user(SUPERUSER_ID)
        shared = self.partner_a.with_user(SUPERUSER_ID).copy({"name": "Legacy shared business", "company_id": False})
        shipping = partners.create({"name": "Legacy shipping", "company_id": False})
        move = self.env["account.move"].with_user(SUPERUSER_ID).create({**self._invoice_values("out_invoice"), "partner_id": shared.id, "partner_shipping_id": shipping.id})
        marker = self.env["ir.config_parameter"].sudo()
        marker.set_param("thirdcode.contact_scope_backfill_v1", False)
        partners._install_contact_isolation()
        for partner in [shared, shipping]:
            self.assertFalse(partner.company_id)
            self.assertEqual(partner.thirdcode_shared_company_ids, self.env.company)
        self.assertEqual(move.partner_id, shared)
        shared.with_user(SUPERUSER_ID).write({"thirdcode_shared_company_ids": [Command.clear()]})
        partners._install_contact_isolation()
        self.assertFalse(shared.thirdcode_shared_company_ids)
        later = partners.create({"name": "Unreviewed later", "company_id": False})
        self.env["account.move"].with_user(SUPERUSER_ID).create({**self._invoice_values("out_invoice"), "partner_id": later.id})
        partners._install_contact_isolation()
        self.assertFalse(later.thirdcode_shared_company_ids)

    def test_multicompany_journal_switch_checks_effective_company(self):
        from odoo import SUPERUSER_ID
        other = self.setup_other_company(name="Contact switch company")
        company_b = other["company"]
        companies = self.env.company | company_b
        user = self.roles["administrator"]
        user.company_ids = companies
        shared = self.partner_a.with_user(SUPERUSER_ID).copy({"name": "Switch shared", "company_id": False,
            "thirdcode_shared_company_ids": [Command.set(self.env.company.ids)]})
        banks = self.env["res.partner.bank"].with_user(SUPERUSER_ID)
        bank_a = banks.create({"partner_id": self.env.company.partner_id.id, "acc_number": "SWITCH-A-BANK"})
        bank_b = banks.create({"partner_id": company_b.partner_id.id, "acc_number": "SWITCH-B-BANK"})
        moves = self.env["account.move"].with_user(user).with_context(allowed_company_ids=companies.ids)
        move = moves.create({"company_id": self.env.company.id, "move_type": "out_invoice",
            "journal_id": self.company_data["default_journal_sale"].id, "partner_id": shared.id})
        self.assertEqual(move.partner_bank_id, bank_a)
        with self.assertRaises(AccessError), self.cr.savepoint():
            move.write({"journal_id": other["default_journal_sale"].id})
        with self.assertRaises(AccessError), self.cr.savepoint():
            moves.with_context(default_journal_id=other["default_journal_sale"].id).create({
                "move_type": "out_invoice", "partner_id": shared.id})
        target = moves.create({"company_id": company_b.id, "journal_id": other["default_journal_misc"].id})
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env["account.move.line"].with_user(user).with_context(
                allowed_company_ids=companies.ids, default_move_id=target.id
            ).create({"partner_id": shared.id, "name": "Forbidden shared contact"})
        shared.with_user(SUPERUSER_ID).write({"thirdcode_shared_company_ids": [Command.set(companies.ids)]})
        move.write({"journal_id": other["default_journal_sale"].id})
        self.assertEqual(move.company_id, company_b)
        self.assertEqual(move.partner_id, shared)
        self.assertEqual(move.partner_bank_id, bank_b)
