"""Native Discuss confidentiality, membership and lifecycle regressions."""
import json
from unittest.mock import patch

from odoo import Command, SUPERUSER_ID
from odoo.addons.bus.models.bus import ImBus
from odoo.addons.mail.tools.discuss import Store
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCompanyDiscuss(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.a, cls.b = cls.env["res.company"].create([{"name": "Discuss A"}, {"name": "Discuss B"}])
        cls.home = cls.env.ref("thirdcode_accounting.company_platform")
        internal = cls.env.ref("base.group_user") | cls.env.ref("base.group_allow_export")
        cls.ua, cls.ua2, cls.ub = cls.env["res.users"].create([
            {"name": name, "login": name, "company_id": company.id, "company_ids": [Command.set(company.ids)],
             "groups_id": [Command.set(internal.ids)]}
            for name, company in [("discuss-a", cls.a), ("discuss-a2", cls.a), ("discuss-b", cls.b)]])
        cls.owner = cls.env["res.users"].create({"name": "Discuss owner", "login": "discuss-owner",
            "thirdcode_platform_owner": True, "company_id": cls.home.id, "company_ids": [Command.set(cls.home.ids)],
            "groups_id": [Command.set((internal | cls.env.ref("base.group_system") |
                                       cls.env.ref("thirdcode_accounting.group_thirdcode_platform_console")).ids)]})
        cls.staff = cls.env["res.users"].create({"name": "Discuss support", "login": "discuss-support",
            "company_id": cls.home.id, "company_ids": [Command.set(cls.home.ids)], "groups_id": [Command.set(
                (internal | cls.env.ref("thirdcode_accounting.group_thirdcode_platform_support")).ids)]})
        cls.ca, cls.cb, cls.cp = [cls.env["discuss.channel"].search([
            ("thirdcode_general_company_id", "=", c.id)]) for c in [cls.a, cls.b, cls.home]]

    def as_user(self, record, user):
        return record.with_user(user).with_context(allowed_company_ids=user.company_id.ids)

    def test_general_membership_and_discovery(self):
        self.assertEqual(self.ca.channel_partner_ids, self.ua.partner_id | self.ua2.partner_id)
        self.assertEqual(self.cb.channel_partner_ids, self.ub.partner_id)
        self.assertIn(self.owner.partner_id, self.cp.channel_partner_ids)
        self.assertIn(self.staff.partner_id, self.cp.channel_partner_ids)
        for user, own, foreign in [(self.ua, self.ca, self.cb | self.cp), (self.ub, self.cb, self.ca | self.cp),
                                   (self.owner, self.cp, self.ca | self.cb), (self.staff, self.cp, self.ca | self.cb)]:
            model = self.as_user(self.env["discuss.channel"], user)
            self.assertIn(own, model.search([]))
            self.assertFalse(model.search([("id", "in", foreign.ids)]))
            self.assertTrue(self.as_user(own, user)._load_more_members([]))
            for channel in foreign:
                with self.assertRaises(AccessError):
                    self.as_user(channel, user).read(["name", "channel_member_ids"])
                with self.assertRaises(AccessError):
                    self.as_user(channel, user).sudo()._to_store(Store())

    def test_message_body_history_export_and_sudo_store(self):
        message = self.as_user(self.ca, self.ua).message_post(body="TENANT-A-PRIVATE-MARKER", message_type="comment",
                                                           subtype_xmlid="mail.mt_comment")
        self.assertIn("TENANT-A-PRIVATE-MARKER", json.dumps(Store(self.as_user(message, self.ua2)).get_result()))
        for user in [self.ub, self.owner, self.staff]:
            hidden = self.as_user(message, user)
            self.assertFalse(hidden.search([("id", "=", message.id)]))
            with self.assertRaises(AccessError):
                hidden.read(["body"])
            with self.assertRaises(AccessError):
                hidden.sudo().read(["body"])
            with self.assertRaises(AccessError):
                Store(hidden.sudo()).get_result()
            with self.assertRaises(AccessError):
                hidden._export_rows([["body"]])

    def test_membership_invitation_and_forged_scope_denied(self):
        channel = self.as_user(self.ca, self.ua)
        for partner in [self.ub.partner_id, self.owner.partner_id]:
            with self.assertRaises(AccessError), self.cr.savepoint():
                channel.add_members(partner_ids=partner.ids)
            with self.assertRaises(AccessError), self.cr.savepoint():
                self.as_user(self.env["discuss.channel.member"], self.ua).sudo().create({
                    "channel_id": self.ca.id, "partner_id": partner.id})
            with self.assertRaises(AccessError), self.cr.savepoint():
                self.as_user(self.env["discuss.channel"], self.ua).create({"name": "Forged group", "channel_type": "group",
                    "channel_member_ids": [Command.create({"partner_id": partner.id})]})
        for values in [{"thirdcode_company_id": self.b.id}, {"thirdcode_quarantined": False}, {"allow_public_upload": True}]:
            with self.assertRaises(AccessError), self.cr.savepoint():
                channel.write(values)
        with self.assertRaises(AccessError):
            self.as_user(self.cb, self.ua).sudo()._find_or_create_persona_for_channel()
        with self.assertRaises(AccessError):
            channel.with_context(allowed_company_ids=self.b.ids).message_post(body="forged")
        with self.assertRaises(AccessError), self.cr.savepoint():
            channel.with_context(default_thirdcode_company_id=self.b.id, install_mode=True).create({"name": "Forged"})

    def test_direct_chat_same_company_and_owner_support(self):
        for user, peer, company in [(self.ua, self.ua2, self.a), (self.owner, self.staff, self.home)]:
            model = self.as_user(self.env["discuss.channel"], user)
            channel = model.channel_get(peer.partner_id.ids)
            self.assertEqual(channel.thirdcode_company_id, company)
            self.assertEqual(channel, model.channel_get(peer.partner_id.ids))
            posted = channel.message_post(body="Private same-company conversation", message_type="comment")
            self.assertTrue(self.as_user(posted, peer).read(["body"]))
        for user, peer in [(self.ua, self.ub), (self.owner, self.ua), (self.ua, self.owner)]:
            with self.assertRaises(AccessError):
                self.as_user(self.env["discuss.channel"], user).channel_get(peer.partner_id.ids)

    def test_chat_picker_only_suggests_company_colleagues(self):
        for user, peer, foreign in [(self.ua, self.ua2, self.ub | self.owner | self.staff),
                                    (self.owner, self.staff, self.ua | self.ua2 | self.ub),
                                    (self.staff, self.owner, self.ua | self.ua2 | self.ub)]:
            result = self.as_user(self.env["res.partner"], user).im_search("Discuss")
            ids = {row["id"] for row in result.get("res.partner", [])}
            self.assertIn(peer.partner_id.id, ids)
            self.assertFalse(ids & set(foreign.partner_id.ids))

    def test_attachment_token_cannot_cross_company(self):
        attachment = self.env["ir.attachment"].create({"name": "private.txt", "raw": b"PRIVATE FILE", "mimetype": "text/plain",
            "res_model": "discuss.channel", "res_id": self.ca.id, "public": True})
        self.assertTrue(self.as_user(attachment, self.ua2)._to_http_stream())
        for user in [self.ub, self.owner, self.env.ref("base.public_user")]:
            with self.assertRaises(AccessError):
                self.as_user(attachment, user).sudo()._to_http_stream()
            self.assertFalse(self.as_user(attachment, user).search([("id", "=", attachment.id)]))

    def test_realtime_drops_foreign_bodies_and_channel_members(self):
        message = self.as_user(self.ca, self.ua).message_post(body="PRIVATE REALTIME")
        data = Store(message.with_user(SUPERUSER_ID)).get_result()
        notifications = [
            {"id": 1, "message": {"type": "discuss.channel/new_message", "payload": {"id": self.ca.id, "data": data}}},
            {"id": 2, "message": {"type": "mail.record/insert", "payload": data}},
            {"id": 3, "message": {"type": "discuss.channel/joined", "payload": {"channel": {"id": self.ca.id, "name": "Private"}}}},
            {"id": 4, "message": {"type": "discuss.channel/delete", "payload": {"id": self.ca.id}}},
        ]
        with patch.object(ImBus, "_poll", return_value=notifications):
            for user in [self.ub, self.owner, self.staff]:
                result = self.as_user(self.env["bus.bus"], user)._poll([])
                self.assertEqual([n["id"] for n in result], [4])
            result = self.as_user(self.env["bus.bus"], self.ua2)._poll([])
            self.assertEqual([n["id"] for n in result], [1, 2, 3, 4])

    def test_user_company_change_revokes_old_membership(self):
        self.ua2.write({"company_id": self.b.id, "company_ids": [Command.set(self.b.ids)]})
        self.assertNotIn(self.ua2.partner_id, self.ca.channel_partner_ids)
        self.assertIn(self.ua2.partner_id, self.cb.channel_partner_ids)
        self.ua2.active = False
        self.assertNotIn(self.ua2.partner_id, self.cb.channel_partner_ids)

    def test_upgrade_preserves_mixed_history_without_exposing_it(self):
        legacy = self.env["discuss.channel"].create({"name": "Legacy global", "channel_type": "channel",
            "channel_member_ids": [Command.create({"partner_id": u.partner_id.id}) for u in (self.ua | self.ub | self.owner)]})
        message = legacy.message_post(body="RETAINED MIXED HISTORY")
        channels = self.env["discuss.channel"]
        channels._install_company_discuss()
        channels._install_company_discuss()
        self.assertTrue(legacy.thirdcode_quarantined)
        self.assertFalse(legacy.active)
        self.assertIn("RETAINED MIXED HISTORY", message.body)
        self.assertEqual(channels.search_count([("thirdcode_general_company_id", "=", self.a.id)]), 1)
        for user in [self.ua, self.ub, self.owner]:
            with self.assertRaises(AccessError):
                self.as_user(message, user).read(["body"])
        self.assertEqual(message.res_id, legacy.id)
