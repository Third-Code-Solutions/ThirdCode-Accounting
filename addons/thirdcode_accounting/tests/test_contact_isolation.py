"""Real ORM rules: positive business access and negative tenant boundaries."""
from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestContactIsolation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.a, cls.b = cls.env["res.company"].create([{"name": "Contact A"}, {"name": "Contact B"}])
        group = cls.env.ref("thirdcode_accounting.group_thirdcode_accountant")
        cls.ua, cls.ub, cls.multi = cls.env["res.users"].create([
            {"name": name, "login": name, "company_id": company.id,
             "company_ids": [Command.set(companies.ids)], "groups_id": [Command.set(group.ids)]}
            for name, company, companies in [("contact-a", cls.a, cls.a), ("contact-b", cls.b, cls.b),
                                             ("contact-multi", cls.a, cls.a | cls.b)]
        ])
        cls.pa, cls.pb, cls.unassigned, cls.shared = cls.env["res.partner"].create([
            {"name": "Contact isolation A customer", "company_id": cls.a.id, "customer_rank": 1},
            {"name": "Contact isolation B vendor", "company_id": cls.b.id, "supplier_rank": 1},
            {"name": "Contact isolation unreviewed", "company_id": False},
            {"name": "Contact isolation shared vendor", "company_id": False,
             "thirdcode_shared_company_ids": [Command.set(cls.a.ids)], "supplier_rank": 1},
        ])
        cls.bank_a, cls.bank_b = cls.env["res.partner.bank"].create([
            {"partner_id": cls.pa.id, "acc_number": "TEST-A-ONLY"},
            {"partner_id": cls.pb.id, "acc_number": "TEST-B-ONLY"},
        ])
        home = cls.env.ref("thirdcode_accounting.company_platform")
        cls.owner = cls.env["res.users"].create({"name": "Contact owner", "login": "contact-owner",
            "thirdcode_platform_owner": True, "company_id": home.id,
            "company_ids": [Command.set(home.ids)], "groups_id": [Command.set([
                cls.env.ref(x).id for x in ["base.group_user", "base.group_system", "thirdcode_accounting.group_thirdcode_platform_console"]])],
        })

    def partners(self, user, companies=None):
        return self.env["res.partner"].with_user(user).with_context(allowed_company_ids=(companies or user.company_id).ids)

    def test_two_companies_search_read_dropdown_export_and_banks(self):
        for user, own, foreign, bank, foreign_bank, company, other in [
            (self.ua, self.pa, self.pb, self.bank_a, self.bank_b, self.a, self.b),
            (self.ub, self.pb, self.pa, self.bank_b, self.bank_a, self.b, self.a),
        ]:
            model = self.partners(user)
            visible = model.search([])
            self.assertIn(own, visible)
            self.assertIn(user.partner_id, visible)
            self.assertIn(company.partner_id, visible)
            for hidden in [foreign, other.partner_id, self.owner.partner_id, self.unassigned]:
                self.assertNotIn(hidden, visible)
                self.assertFalse(model.name_search(hidden.name))
                with self.assertRaises(AccessError):
                    model.browse(hidden.id).read(["name", "email"])
                with self.assertRaises(AccessError):
                    model.browse(hidden.id).export_data(["name"])
            self.assertTrue(model.browse(own.id).read(["name"]))
            banks = self.env["res.partner.bank"].with_user(user).with_context(allowed_company_ids=company.ids)
            self.assertIn(bank, banks.search([]))
            self.assertNotIn(foreign_bank, banks.search([]))
            with self.assertRaises(AccessError):
                banks.browse(foreign_bank.id).read(["acc_number"])

    def test_internal_and_archived_identity_no_longer_global(self):
        self.ub.active = False
        self.assertNotIn(self.ub.partner_id, self.partners(self.ua).with_context(active_test=False).search([]))
        self.assertIn(self.ua.partner_id, self.partners(self.ua).search([]))
        # Membership changes must affect stored scope, even after a cached search.
        self.ub.company_ids = self.a | self.b
        self.assertIn(self.ub.partner_id, self.partners(self.ua).search([]))
        self.ub.company_ids = self.b
        self.assertNotIn(self.ub.partner_id, self.partners(self.ua).search([]))

    def test_authorized_multicompany_and_owner(self):
        both = self.partners(self.multi, self.a | self.b).search([])
        self.assertIn(self.pa, both)
        self.assertIn(self.pb, both)
        self.assertNotIn(self.pb, self.partners(self.multi, self.a).search([]))
        with self.assertRaises(AccessError):
            self.partners(self.ua, self.b).search([])
        visible = self.partners(self.owner).search([])
        for contact in [self.pa, self.pb, self.unassigned, self.ua.partner_id, self.ub.partner_id]:
            self.assertIn(contact, visible)

    def test_shared_grant_is_read_only_and_revocation_immediate(self):
        self.assertIn(self.shared, self.partners(self.ua).search([]))
        self.assertNotIn(self.shared, self.partners(self.ub).search([]))
        with self.assertRaises(AccessError):
            self.partners(self.ua).browse(self.shared.id).write({"name": "Changed vendor"})
        self.shared.thirdcode_shared_company_ids = self.a | self.b
        self.assertIn(self.shared, self.partners(self.ub).search([]))
        self.shared.thirdcode_shared_company_ids = self.b
        self.assertNotIn(self.shared, self.partners(self.ua).search([]))
        self.assertFalse(self.shared.company_id)

    def test_tenant_create_and_forged_scope_and_hierarchy(self):
        model = self.partners(self.ua)
        created = model.create({"name": "Tenant new customer", "company_id": False})
        self.assertEqual(created.company_id, self.a)
        self.assertNotIn(created, self.partners(self.ub).search([]))
        for values in [
            {"company_id": self.b.id}, {"thirdcode_shared_company_ids": [Command.set(self.b.ids)]},
            {"thirdcode_is_identity": True}, {"parent_id": self.pb.id},
            {"child_ids": [Command.link(self.pb.id)]},
        ]:
            with self.assertRaises(AccessError), self.cr.savepoint():
                created.write(values)
        with self.assertRaises(AccessError), self.cr.savepoint():
            model.with_context(default_thirdcode_shared_company_ids=[Command.set(self.a.ids)]).create({"name": "Forged"})
        with self.assertRaises(AccessError), self.cr.savepoint():
            model.create({"name": "Foreign", "company_id": self.b.id})
        with self.assertRaises(AccessError), self.cr.savepoint():
            model.create({"name": "Shared child", "parent_id": self.shared.id})

    def test_guessed_accounting_partner_does_not_create_access(self):
        for model in ["account.move", "account.move.line", "account.payment"]:
            with self.assertRaises(AccessError), self.cr.savepoint():
                self.env[model].with_user(self.ua).with_context(allowed_company_ids=self.a.ids).create({"partner_id": self.pb.id})
            with self.assertRaises(AccessError), self.cr.savepoint():
                self.env[model].with_user(self.ua).with_context(allowed_company_ids=self.a.ids, default_partner_id=self.unassigned.id).create({})
        self.assertNotIn(self.pb, self.partners(self.ua).search([]))
        self.assertNotIn(self.unassigned, self.partners(self.ua).search([]))

    def test_context_defaults_and_bank_reparent_cannot_cross_scope(self):
        for hidden in [self.pb, self.shared, self.owner.partner_id]:
            with self.assertRaises(AccessError), self.cr.savepoint():
                self.partners(self.ua).with_context(default_parent_id=hidden.id).create({"name": "Forged child"})
            with self.assertRaises(AccessError), self.cr.savepoint():
                self.bank_a.with_user(self.ua).with_context(allowed_company_ids=self.a.ids).write({"partner_id": hidden.id})
            with self.assertRaises(AccessError), self.cr.savepoint():
                self.env["res.partner.bank"].with_user(self.ua).with_context(allowed_company_ids=self.a.ids, default_partner_id=hidden.id).create({"acc_number": "FORGED"})
