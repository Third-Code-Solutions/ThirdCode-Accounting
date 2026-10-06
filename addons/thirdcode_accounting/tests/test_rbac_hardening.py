"""Server-side guards added by the 2026-10-06 RBAC audit remediation.

Covers the audit-log tenant boundary and session digests (C2), the Encoder
auto-post control (C3), vendor-bank verification before payment (H2), payment
batch approval separation and threshold enforcement (H3), and organization
user-management scoping (H7). The setup-service entry gate (C1) is exercised in
``test_trial_mode`` and ``test_platform_operations``.
"""
from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestRbacHardening(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.roles = {}
        for role in ("administrator", "accountant", "encoder", "readonly"):
            cls.roles[role] = cls.env["res.users"].create({
                "name": "Hardening " + role,
                "login": "hardening-" + role,
                "company_id": cls.company.id,
                "company_ids": [Command.set(cls.company.ids)],
                "groups_id": [
                    Command.set(
                        [cls.env.ref("thirdcode_accounting.group_thirdcode_" + role).id]
                    )
                ],
            })
        cls.supplier = cls.env["res.partner"].create({
            "name": "Hardening supplier",
            "company_id": cls.company.id,
            "supplier_rank": 1,
        })

    def _invoice_values(self, kind, **overrides):
        purchase = kind == "in_invoice"
        values = {
            "company_id": self.company.id,
            "move_type": kind,
            "journal_id": self.company_data[
                "default_journal_purchase" if purchase else "default_journal_sale"
            ].id,
            "partner_id": self.partner_a.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "name": "RBAC hardening item",
                    "quantity": 1,
                    "price_unit": 25,
                    "account_id": self.company_data[
                        "default_account_expense" if purchase else "default_account_revenue"
                    ].id,
                    "tax_ids": [Command.clear()],
                })
            ],
        }
        values.update(overrides)
        return values

    # ------------------------------------------------------------------
    # C2: audit evidence boundary
    # ------------------------------------------------------------------
    def test_roles_read_only_log_evidence_and_never_sessions(self):
        self.env["account.move"].create(self._invoice_values("out_invoice"))
        oca_group = self.env.ref("auditlog.group_auditlog_user")
        reader_group = self.env.ref("thirdcode_accounting.group_thirdcode_audit_reader")
        for role, user in self.roles.items():
            with self.subTest(role=role):
                self.assertNotIn(oca_group, user.groups_id.trans_implied_ids)
                self.assertIn(reader_group, user.groups_id.trans_implied_ids)
                logs = self.env["auditlog.log"].with_user(user).search([], limit=1)
                self.assertTrue(
                    logs, "Business roles keep read access to retained log entries"
                )
                for model in (
                    "auditlog.http.session",
                    "auditlog.http.request",
                    "auditlog.rule",
                ):
                    with self.assertRaises(AccessError), self.cr.savepoint():
                        self.env[model].with_user(user).search([], limit=1)

    def test_session_digest_never_keeps_the_raw_secret(self):
        from odoo.addons.thirdcode_accounting.models.auditlog import session_digest

        digest = session_digest(self.env, "raw-session-secret")
        self.assertTrue(digest.startswith("sha256:"))
        self.assertNotIn("raw-session-secret", digest)
        self.assertEqual(digest, session_digest(self.env, "raw-session-secret"))

    # ------------------------------------------------------------------
    # C3: an Encoder cannot arm automatic posting
    # ------------------------------------------------------------------
    def test_encoder_cannot_arm_automatic_posting(self):
        encoder = self.roles["encoder"]
        move = self.env["account.move"].create(self._invoice_values("out_invoice"))
        with self.assertRaises(AccessError), self.cr.savepoint():
            move.with_user(encoder).write({"auto_post": "at_date"})
        with self.assertRaises(AccessError), self.cr.savepoint():
            move.with_user(encoder).write({"auto_post_until": fields.Date.today()})
        with self.assertRaises(AccessError), self.cr.savepoint():
            move.with_user(encoder).write({"checked": True})
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env["account.move"].with_user(encoder).create(
                self._invoice_values("out_invoice", auto_post="at_date")
            )
        # Turning automatic posting off stays available to the Encoder.
        move.with_user(encoder).write({"auto_post": "no", "checked": False})
        self.assertEqual(move.auto_post, "no")

    def test_autopost_job_demotes_encoder_written_drafts(self):
        encoder = self.roles["encoder"]
        move = self.env["account.move"].create(self._invoice_values("out_invoice"))
        move.with_user(encoder).sudo().write({"auto_post": "at_date", "checked": True})
        self.assertEqual(move.write_uid, encoder)
        self.env["account.move"].sudo()._autopost_draft_entries()
        move.invalidate_recordset()
        self.assertEqual(move.state, "draft")
        self.assertEqual(move.auto_post, "no")
        self.assertFalse(move.checked)
        self.assertTrue(
            any("Encoder" in (message.body or "") for message in move.message_ids)
        )

    # ------------------------------------------------------------------
    # H2: vendor-bank verification before payment
    # ------------------------------------------------------------------
    def test_administrator_holds_the_bank_validation_group(self):
        self.assertIn(
            self.env.ref("account.group_validate_bank_account"),
            self.env.ref(
                "thirdcode_accounting.group_thirdcode_administrator"
            ).trans_implied_ids,
        )

    def test_outbound_payments_need_a_verified_recipient_bank(self):
        accountant = self.roles["accountant"]
        administrator = self.roles["administrator"]
        bank = self.env["res.partner.bank"].create({
            "partner_id": self.supplier.id,
            "acc_number": "PH-1122334455",
        })
        self.assertFalse(bank.allow_out_payment)
        with self.assertRaises(UserError), self.cr.savepoint():
            bank.with_user(accountant).write({"allow_out_payment": True})

        payment = self.env["account.payment"].create({
            "payment_type": "outbound",
            "partner_type": "supplier",
            "partner_id": self.supplier.id,
            "amount": 25,
            "journal_id": self.company_data["default_journal_bank"].id,
            "company_id": self.company.id,
        })
        payment.partner_bank_id = bank
        self.assertEqual(payment.partner_bank_id, bank)

        with self.assertRaises(UserError) as raised, self.cr.savepoint():
            payment.with_user(accountant).action_post()
        self.assertIn("verified", str(raised.exception))
        self.assertEqual(payment.state, "draft")

        # Only a reviewer (the Administrator role) may mark the account as
        # trusted; afterwards the same payment posts.
        bank.with_user(administrator).write({"allow_out_payment": True})
        self.assertTrue(bank.allow_out_payment)
        payment.with_user(accountant).action_post()
        self.assertIn(payment.state, ("in_process", "paid"))

    # ------------------------------------------------------------------
    # H3: approval separation and the payment threshold
    # ------------------------------------------------------------------
    def test_payment_batch_cannot_be_approved_by_its_creator(self):
        self.company.sudo().write({
            "thirdcode_payment_approval_enabled": True,
            "thirdcode_payment_approval_threshold": 10,
        })
        administrator = self.roles["administrator"]
        batch = self.env["thirdcode.payment.batch"].with_user(administrator).create({
            "name": "H3 self approval",
            "company_id": self.company.id,
            "journal_id": self.company_data["default_journal_cash"].id,
            "date": fields.Date.today(),
            "payment_type": "outbound",
            "partner_type": "supplier",
            "payment_instrument": "cash",
            "line_ids": [
                Command.create({"partner_id": self.supplier.id, "amount": 20})
            ],
        })
        batch.action_submit()
        self.assertEqual(batch.state, "pending_approval")
        with self.assertRaises(UserError) as raised, self.cr.savepoint():
            batch.action_approve()
        self.assertIn("created it", str(raised.exception))
        self.assertEqual(batch.state, "pending_approval")

    def test_native_payments_above_threshold_require_an_approved_batch(self):
        self.company.sudo().write({
            "thirdcode_payment_approval_enabled": True,
            "thirdcode_payment_approval_threshold": 100,
        })
        accountant = self.roles["accountant"]
        administrator = self.roles["administrator"]

        def new_payment(amount):
            return self.env["account.payment"].create({
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": self.supplier.id,
                "amount": amount,
                "journal_id": self.company_data["default_journal_cash"].id,
                "company_id": self.company.id,
            })

        below = new_payment(50)
        below.with_user(accountant).action_post()
        self.assertIn(below.state, ("in_process", "paid"))

        above = new_payment(150)
        with self.assertRaises(UserError) as raised, self.cr.savepoint():
            above.with_user(accountant).action_post()
        self.assertIn("approval threshold", str(raised.exception))
        self.assertEqual(above.state, "draft")

        # The batch route, approved by a different Administrator, posts.
        batch = self.env["thirdcode.payment.batch"].with_user(accountant).create({
            "name": "H3 threshold batch",
            "company_id": self.company.id,
            "journal_id": self.company_data["default_journal_cash"].id,
            "date": fields.Date.today(),
            "payment_type": "outbound",
            "partner_type": "supplier",
            "payment_instrument": "cash",
            "line_ids": [
                Command.create({"partner_id": self.supplier.id, "amount": 150})
            ],
        })
        batch.action_submit()
        self.assertEqual(batch.state, "pending_approval")
        batch.with_user(administrator).action_approve()
        batch.action_post()
        self.assertEqual(batch.state, "posted")
        self.assertTrue(batch.line_ids.payment_id)

    # ------------------------------------------------------------------
    # H7: organization user management
    # ------------------------------------------------------------------
    def test_admin_cannot_manage_peer_admins_or_foreign_company_users(self):
        administrator = self.roles["administrator"]
        company_a = self.company
        # Trusted fixture setup, like the role-matrix tests: the contact rules
        # do not let a business user claim a brand-new company's contact.
        company_b = self.env["res.company"].sudo().create({"name": "Hardening foreign org"})
        peer_admin = self.env["res.users"].sudo().create({
            "name": "Hardening peer admin",
            "login": "hardening-peer-admin",
            "company_id": company_a.id,
            "company_ids": [Command.set(company_a.ids)],
            "groups_id": [
                Command.set(
                    [self.env.ref("thirdcode_accounting.group_thirdcode_administrator").id]
                )
            ],
        })
        accountant = self.roles["accountant"]
        shared = self.env["res.users"].sudo().create({
            "name": "Hardening shared user",
            "login": "hardening-shared-user",
            "company_id": company_a.id,
            "company_ids": [Command.set((company_a | company_b).ids)],
            "groups_id": [
                Command.set([self.env.ref("thirdcode_accounting.group_thirdcode_encoder").id])
            ],
        })
        wizard = self.env["thirdcode.employee.password.wizard"].with_user(administrator)
        with self.assertRaises(AccessError), self.cr.savepoint():
            wizard.create({
                "user_id": peer_admin.id,
                "new_password": "Peer-admin-secret",
            }).action_reset_password()
        with self.assertRaises(AccessError), self.cr.savepoint():
            wizard.create({
                "user_id": shared.id,
                "new_password": "Shared-user-secret",
            }).action_reset_password()
        # Same-company, non-administrator accounts stay manageable.
        wizard.create({
            "user_id": accountant.id,
            "new_password": "Managed-accountant-secret",
        }).action_reset_password()

        with self.assertRaises(AccessError), self.cr.savepoint():
            peer_admin.with_user(administrator).action_thirdcode_toggle_active()
        with self.assertRaises(AccessError), self.cr.savepoint():
            shared.with_user(administrator).action_thirdcode_toggle_active()
        accountant.with_user(administrator).action_thirdcode_toggle_active()
        self.assertFalse(accountant.active)
