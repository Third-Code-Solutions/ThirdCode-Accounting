"""Company control editing must not grant company or platform administration."""
from lxml import etree

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCompanyControls(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company, cls.other = cls.env["res.company"].sudo().create([
            {"name": "Controls Company"}, {"name": "Foreign Controls Company"},
        ])
        cls.roles = {}
        for role in ("administrator", "accountant", "encoder", "readonly"):
            cls.roles[role] = cls.env["res.users"].create({
                "name": "Controls " + role, "login": "controls-" + role,
                "company_id": cls.company.id, "company_ids": [Command.set(cls.company.ids)],
                "groups_id": [Command.set(cls.env.ref("thirdcode_accounting.group_thirdcode_" + role).ids)],
            })
        cls.admin = cls.roles["administrator"]

    def test_administrator_edits_and_restores_own_business_controls(self):
        company = self.company.with_user(self.admin)
        self.assertFalse(self.admin.has_group("base.group_erp_manager"))
        self.assertTrue(company.check_access_rights("write", raise_exception=False))
        original = company.read(["thirdcode_backup_owner", "thirdcode_receipt_signatory_name"])[0]
        company.write({"thirdcode_backup_owner": "Named backup owner", "thirdcode_receipt_signatory_name": "Approved signatory"})
        self.assertEqual(company.thirdcode_backup_owner, "Named backup owner")
        self.assertEqual(company.thirdcode_receipt_signatory_name, "Approved signatory")
        company.write({key: value for key, value in original.items() if key != "id"})
        self.assertEqual(company.thirdcode_backup_owner, original["thirdcode_backup_owner"])

    def test_controls_menu_opens_selected_company_in_restricted_form(self):
        menu = self.env.ref("thirdcode_accounting.menu_company_controls")
        self.assertIn(menu.id, self.env["ir.ui.menu"].with_user(self.admin)._visible_menu_ids())
        self.assertEqual(menu.parent_id, self.env.ref("thirdcode_accounting.menu_thirdcode_controls"))
        action = menu.action.with_user(self.admin).with_context(
            allowed_company_ids=self.company.ids, active_model="res.company",
            active_id=self.other.id, active_ids=self.other.ids,
        ).run()
        self.assertEqual(action["res_id"], self.company.id)
        self.assertEqual(action["context"]["allowed_company_ids"], self.company.ids)
        window = self.env.ref("thirdcode_accounting.action_company_controls_form")
        self.assertEqual(action["id"], window.id)
        self.assertEqual(window.res_model, "res.company")
        self.assertEqual(window.view_mode, "form")
        self.assertEqual(window.groups_id, self.env.ref("thirdcode_accounting.group_thirdcode_administrator"))
        view = self.env.ref("thirdcode_accounting.view_company_controls_form")
        self.assertEqual(window.view_id, view)
        self.assertEqual(window.views, [(view.id, "form")])
        self.assertEqual(action["views"], [(view.id, "form")])
        arch = etree.fromstring(self.company.with_user(self.admin).get_view(window.view_id.id, "form")["arch"])
        for operation in ("create", "delete", "duplicate"):
            self.assertEqual(arch.get(operation), "0")
        self.assertEqual(arch.xpath("//field[@name='name']")[0].get("readonly"), "1")
        currency_fields = arch.xpath("//field[@name='currency_id']")
        self.assertEqual(len(currency_fields), 1)
        self.assertEqual(currency_fields[0].get("invisible"), "1")
        self.assertFalse(arch.xpath("//field[@name='thirdcode_trial_mode']"))
        self.assertTrue(arch.xpath("//field[@name='thirdcode_backup_owner']"))

    def test_controls_action_denies_other_roles_and_forged_company_scope(self):
        menu = self.env.ref("thirdcode_accounting.menu_company_controls")
        for role in ("accountant", "encoder", "readonly"):
            user = self.roles[role]
            self.assertNotIn(menu.id, self.env["ir.ui.menu"].with_user(user)._visible_menu_ids())
            with self.subTest(role=role), self.assertRaises(AccessError), self.cr.savepoint():
                menu.action.with_user(user).run()
        for company in (self.other, self.env.ref("thirdcode_accounting.company_platform")):
            with self.subTest(company=company.id), self.assertRaises(AccessError), self.cr.savepoint():
                menu.action.with_user(self.admin).with_context(allowed_company_ids=company.ids).run()

    def test_other_business_roles_cannot_edit_controls(self):
        for role in ("accountant", "encoder", "readonly"):
            with self.subTest(role=role), self.assertRaises(AccessError), self.cr.savepoint():
                self.company.with_user(self.roles[role]).write({"thirdcode_backup_owner": "Forbidden"})

    def test_control_values_are_validated_on_save_and_invalid_edits_roll_back(self):
        company = self.company.with_user(self.admin)
        company.write({"thirdcode_payment_approval_enabled": True, "thirdcode_payment_approval_threshold": 10,
                       "thirdcode_statutory_retention_years": 10})
        for values in (
            {"thirdcode_payment_approval_threshold": 0}, {"thirdcode_payment_approval_threshold": -1},
            {"thirdcode_statutory_retention_years": 0}, {"thirdcode_statutory_retention_years": -1},
        ):
            with self.subTest(values=values), self.assertRaises(UserError), self.cr.savepoint():
                company.write(values)
            self.assertEqual(company.thirdcode_payment_approval_threshold, 10)
            self.assertEqual(company.thirdcode_statutory_retention_years, 10)
        company.write({"thirdcode_payment_approval_enabled": False, "thirdcode_payment_approval_threshold": 0})
        self.assertFalse(company.thirdcode_payment_approval_enabled)
        with self.assertRaises(UserError), self.cr.savepoint():
            company.write({"thirdcode_payment_approval_enabled": True})
        self.assertFalse(company.thirdcode_payment_approval_enabled)
        with self.assertRaises(UserError), self.cr.savepoint():
            self.env["res.company"].sudo().with_context(default_thirdcode_statutory_retention_years=0).create({"name": "Invalid defaults"})

    def test_administrator_cannot_change_company_or_platform_fields(self):
        forbidden = {
            "name": "Unauthorized rename", "partner_id": self.other.partner_id.id,
            "thirdcode_trial_mode": True, "thirdcode_platform_status": "active",
            "thirdcode_trial_start": "2026-01-01", "thirdcode_trial_end": "2099-01-01",
            "thirdcode_suspended_from_status": "active", "thirdcode_suspended_user_ids": "[]",
            "thirdcode_is_platform": True, "thirdcode_provisioning_key": "forged",
            "thirdcode_period_revision": 99,
        }
        for field, value in forbidden.items():
            with self.subTest(field=field), self.assertRaises(AccessError), self.cr.savepoint():
                self.company.with_user(self.admin).with_context(tcsi_setup_token_ok=True).write({field: value})

    def test_no_company_creation_deletion_or_default_bypass(self):
        model = self.env["res.company"].with_user(self.admin)
        for defaults in ({}, {"default_thirdcode_trial_mode": True}, {"default_thirdcode_platform_status": "active"}):
            with self.subTest(defaults=defaults), self.assertRaises(AccessError), self.cr.savepoint():
                model.with_context(**defaults).create({"name": "Forbidden company"})
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.company.with_user(self.admin).unlink()

    def test_foreign_and_mixed_company_updates_are_denied(self):
        for records in (self.other, self.company | self.other):
            for context in ({}, {"allowed_company_ids": self.other.ids}):
                with self.subTest(ids=records.ids, context=context), self.assertRaises(AccessError), self.cr.savepoint():
                    records.with_user(self.admin).with_context(**context).write({"thirdcode_backup_owner": "Forbidden"})

    def test_account_and_journal_controls_require_matching_company_and_type(self):
        accounts = [
            self.env["account.account"].sudo().with_company(company).create({
                "name": "Controls " + kind, "code": code, "account_type": kind,
                "company_ids": [Command.set(company.ids)],
            })
            for company, code, kind in (
                (self.company, "991001", "equity"), (self.other, "991002", "equity"),
                (self.company, "991003", "expense"),
            )
        ]
        journals = self.env["account.journal"].sudo().create([
            {"name": "Controls general", "code": "CCT", "type": "general", "company_id": self.company.id},
            {"name": "Foreign general", "code": "FCCT", "type": "general", "company_id": self.other.id},
            {"name": "Controls sales", "code": "SCCT", "type": "sale", "company_id": self.company.id},
        ])
        company = self.company.with_user(self.admin)
        company.write({"thirdcode_retained_earnings_account_id": accounts[0].id, "thirdcode_year_end_journal_id": journals[0].id})
        for field, records in (("thirdcode_retained_earnings_account_id", accounts[1:]), ("thirdcode_year_end_journal_id", journals[1:])):
            for record, error in zip(records, (AccessError, UserError)):
                with self.subTest(field=field, record=record.id), self.assertRaises(error), self.cr.savepoint():
                    company.write({field: record.id})
        # Even a legitimately assigned second company cannot supply references
        # to the first company's controls.
        self.admin.write({"company_ids": [Command.set((self.company | self.other).ids)]})
        for field, record in (("thirdcode_retained_earnings_account_id", accounts[1]), ("thirdcode_year_end_journal_id", journals[1])):
            with self.subTest(field=field), self.assertRaises(UserError), self.cr.savepoint():
                company.with_context(allowed_company_ids=(self.company | self.other).ids).write({field: record.id})
