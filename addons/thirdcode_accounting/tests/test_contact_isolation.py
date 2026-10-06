"""Real ORM rules: positive business access and negative tenant boundaries."""
import json
from unittest.mock import patch

from odoo.addons.bus.models.bus import ImBus

from odoo import Command, api
from odoo.addons.mail.tools.discuss import Store
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
             "company_ids": [Command.set(companies.ids)], "groups_id": [Command.set((group | cls.env.ref("base.group_allow_export")).ids)]}
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

    def test_company_bank_management_preserved(self):
        banks = self.env["res.partner.bank"].with_user(self.ua).with_context(allowed_company_ids=self.a.ids)
        bank = banks.create({"partner_id": self.a.partner_id.id, "acc_number": "OWN-COMPANY-BANK"})
        bank.write({"acc_holder_name": "Company A"})
        self.assertEqual(bank.acc_holder_name, "Company A")
        with self.assertRaises(AccessError), self.cr.savepoint():
            banks.create({"partner_id": self.b.partner_id.id, "acc_number": "OTHER-COMPANY-BANK"})
        bank.unlink()

    def test_shipping_commercial_and_bank_defaults_checked(self):
        moves = self.env["account.move"].with_user(self.ua).with_context(allowed_company_ids=self.a.ids)
        for values in [{"partner_shipping_id": self.unassigned.id}, {"commercial_partner_id": self.pb.id}]:
            with self.assertRaises(AccessError), self.cr.savepoint():
                moves.create(values)
        with self.assertRaises(AccessError), self.cr.savepoint():
            moves.with_context(default_partner_bank_id=self.bank_b.id).create({})

    def test_shared_is_company_write_cannot_use_native_sudo_branch(self):
        for partner in [self.shared, self.pb]:
            with self.assertRaises(AccessError), self.cr.savepoint():
                self.partners(self.ua).browse(partner.id).write({"is_company": True})

    def test_multicompany_document_does_not_spread_shared_grants(self):
        # A grant to A cannot be used on B's document just because both companies
        # are selected. Native check_company accepts company-less partners.
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env["account.move"].with_user(self.multi).with_context(allowed_company_ids=(self.a | self.b).ids).create({
                "company_id": self.b.id, "partner_id": self.shared.id})

    def test_plain_internal_users_cannot_read_delegated_foreign_contacts(self):
        self.ua.groups_id = self.env.ref("base.group_user")
        users = self.env["res.users"].with_user(self.ua).with_context(allowed_company_ids=self.a.ids)
        self.assertIn(self.ua, users.search([]))
        self.assertNotIn(self.ub, users.search([]))
        with self.assertRaises(AccessError):
            users.browse(self.ub.id).read(["name", "email"])

    def test_owner_flag_revocation_invalidates_cached_rules(self):
        self.assertIn(self.pb, self.partners(self.owner).search([]))
        self.owner.thirdcode_platform_owner = False
        self.assertNotIn(self.pb, self.partners(self.owner).search([]))

    def test_user_defaults_do_not_grant_hidden_partner_access(self):
        self.env["ir.default"].set("account.move", "partner_id", self.unassigned.id, user_id=self.ua.id)
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env["account.move"].with_user(self.ua).with_context(allowed_company_ids=self.a.ids).create({})

    def test_console_groups_without_owner_flag_cannot_share_contacts(self):
        self.ua.groups_id |= self.env.ref("base.group_system") | self.env.ref("thirdcode_accounting.group_thirdcode_platform_console")
        self.assertNotIn(self.pb, self.partners(self.ua).search([]))
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.partners(self.ua).browse(self.pa.id).write({"thirdcode_shared_company_ids": [Command.set(self.b.ids)]})

    def test_automatic_channel_membership_scopes_candidate_contacts(self):
        group = self.env["res.groups"].create({"name": "Contact test subscription"})
        (self.ua | self.ub).write({"groups_id": [Command.link(group.id)]})
        channel = self.env["discuss.channel"].create({"name": "Contact subscription test", "channel_type": "channel"})
        # Set the group without invoking subscription yet, so both are candidates.
        with patch.object(type(channel), "_subscribe_users_automatically", return_value=None):
            channel.write({"group_ids": [Command.link(group.id)]})
        candidates = channel.with_user(self.ua).with_context(allowed_company_ids=self.a.ids)._subscribe_users_automatically_get_members()[channel.id]
        self.assertIn(self.ua.partner_id.id, candidates)
        self.assertNotIn(self.ub.partner_id.id, candidates)

    def test_mail_store_sudo_does_not_serialize_foreign_contacts(self):
        for user, own, foreign in [(self.ua, self.pa, self.pb), (self.ub, self.pb, self.pa)]:
            records = self.partners(user).browse((own | foreign).ids).sudo()
            data = Store(records, fields=["name", "email"]).get_result()
            ids = {row["id"] for row in data.get("res.partner", [])}
            self.assertIn(own.id, ids)
            self.assertNotIn(foreign.id, ids)
        owner_data = Store((self.pa | self.pb).with_user(self.owner), fields=["name"]).get_result()
        self.assertEqual({row["id"] for row in owner_data["res.partner"]}, {self.pa.id, self.pb.id})

    def test_channel_member_api_scopes_existing_shared_channel(self):
        channel = self.env["discuss.channel"].create({"name": "Legacy shared channel", "channel_type": "channel",
            "channel_member_ids": [Command.create({"partner_id": u.partner_id.id}) for u in (self.ua | self.ub)]})
        for user, foreign in [(self.ua, self.ub), (self.ub, self.ua)]:
            data = channel.with_user(user).with_context(allowed_company_ids=user.company_id.ids)._load_more_members([])
            ids = {row["id"] for row in data.get("res.partner", [])}
            self.assertIn(user.partner_id.id, ids)
            self.assertNotIn(foreign.partner_id.id, ids)

    def test_message_author_email_and_bus_payload_are_receiver_scoped(self):
        self.ub.email = "foreign-contact-marker@example.invalid"
        channel = self.env["discuss.channel"].create({"name": "Shared message test", "channel_type": "channel",
            "channel_member_ids": [Command.create({"partner_id": u.partner_id.id}) for u in (self.ua | self.ub)]})
        message = self.env["mail.message"].create({"model": "discuss.channel", "res_id": channel.id,
            "body": "Contact boundary test", "author_id": self.ub.partner_id.id,
            "email_from": self.ub.email, "message_type": "comment",
            "partner_ids": [Command.set((self.ua.partner_id | self.ub.partner_id).ids)]})
        readable = message.with_user(self.ua).with_context(allowed_company_ids=self.a.ids)
        readable.check_access("read")
        direct = Store(readable).get_result()
        self.assertNotIn(self.ub.email, json.dumps(direct))
        self.assertFalse(direct["mail.message"][0]["author"])
        for load in ["_classic_read", None]:
            row = readable.read(["author_id", "email_from", "partner_ids", "body"], load=load)[0]
            self.assertFalse(row["author_id"])
            self.assertFalse(row["email_from"])
            self.assertEqual(row["partner_ids"], self.ua.partner_id.ids)
            self.assertIn("Contact boundary test", row["body"])
        searched = readable.search_read([("id", "=", message.id)], ["author_id", "email_from"])
        self.assertFalse(searched[0]["email_from"])
        # Native web_read expands the actual ORM relation, independently of
        # formatted rows. The partner rule must deny that foreign expansion.
        with self.assertRaises(AccessError):
            readable.web_read({"author_id": {"fields": {"name": {}}}, "email_from": {}})
        # Exercise native parent export initialization and nested message rows.
        # The top-level mail.message export gate is not involved in this path.
        readable_channel = channel.with_user(self.ua).with_context(allowed_company_ids=self.a.ids)
        with self.assertRaises(AccessError):
            readable_channel.export_data(["message_ids/email_from"])
        exported = readable_channel.export_data(["message_ids/body"])
        self.assertIn("Contact boundary test", json.dumps(exported))
        for user, companies in [(self.owner, self.owner.company_ids), (self.multi, self.a | self.b)]:
            allowed = message.with_user(user).with_context(allowed_company_ids=companies.ids)
            self.assertEqual(allowed.sudo().read(["email_from"])[0]["email_from"], self.ub.email)
        self.assertEqual(message.email_from, self.ub.email)

        # Build the actual native sender Store, then poll as each receiver.
        sender_store = Store(self.ua.partner_id | self.ub.partner_id, fields=["name", "email"])
        message._author_to_store(sender_store)
        data = sender_store.get_result()
        notifications = [
            {"id": 101, "message": {"type": "discuss.channel/new_message", "payload": {"id": 1, "data": data}}},
            {"id": 102, "message": {"type": "mail.record/insert", "payload": data}},
            {"id": 103, "message": {"type": "unrelated/test", "payload": {"value": "unchanged"}}},
        ]
        with patch.object(ImBus, "_poll", return_value=notifications):
            for user, own, foreign in [(self.ua, self.ua, self.ub), (self.ub, self.ub, self.ua)]:
                result = self.env["bus.bus"].with_user(user).with_context(allowed_company_ids=user.company_id.ids)._poll([])
                self.assertEqual([item["id"] for item in result], [101, 102, 103])
                self.assertEqual(result[2], notifications[2])
                for store_data in [result[0]["message"]["payload"]["data"], result[1]["message"]["payload"]]:
                    ids = {row["id"] for row in store_data["res.partner"]}
                    self.assertIn(own.partner_id.id, ids)
                    self.assertNotIn(foreign.partner_id.id, ids)
                if user == self.ua:
                    self.assertNotIn(self.ub.email, json.dumps(result))
            self.assertEqual(self.env["bus.bus"].with_user(self.owner)._poll([]), notifications)
            self.assertEqual(self.env["bus.bus"].with_user(self.multi).with_context(allowed_company_ids=(self.a | self.b).ids)._poll([]), notifications)
            self.assertEqual(api.Environment(self.cr, None, {})["bus.bus"]._poll([]), notifications)
        self.assertIn(self.ub.email, json.dumps(notifications))

    def test_hidden_member_call_dependencies_are_pruned(self):
        from ..models.contact_isolation import scope_contact_store
        data = {"res.partner": [{"id": self.ub.partner_id.id, "name": "Foreign"}],
            "discuss.channel.member": [{"id": 20, "persona": {"id": self.ub.partner_id.id, "type": "partner"}}],
            "discuss.channel.rtc.session": [{"id": 30, "channelMember": 20}],
            "discuss.channel": [{"id": 5, "channelMembers": [20], "invitedMembers": [["ADD", [20]], ["DELETE", [20]]],
                "rtcSessions": [["ADD", [30]]], "rtcInvitingSession": 30}]}
        result = scope_contact_store(self.partners(self.ua).env, data)
        self.assertFalse(result["discuss.channel.member"])
        self.assertFalse(result["discuss.channel.rtc.session"])
        channel = result["discuss.channel"][0]
        self.assertEqual(channel["channelMembers"], [])
        self.assertEqual(channel["invitedMembers"], [["ADD", []], ["DELETE", [20]]])
        self.assertEqual(channel["rtcSessions"], [["ADD", []]])
        self.assertFalse(channel["rtcInvitingSession"])
