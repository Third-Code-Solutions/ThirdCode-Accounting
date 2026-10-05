import json
import uuid
from datetime import datetime, time, timedelta
from unittest.mock import patch
from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPlatformOperations(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.home = cls.env.ref("thirdcode_accounting.company_platform")
        cls.company = cls.env["res.company"].create({"name": "Operations test client"})
        cls.owner = cls.env["res.users"].create({
            "name": "Operations owner", "login": "operations-owner", "thirdcode_platform_owner": True,
            "company_id": cls.home.id, "company_ids": [Command.set(cls.home.ids)],
            "groups_id": [Command.set([cls.env.ref(x).id for x in ["base.group_user", "base.group_system", "thirdcode_accounting.group_thirdcode_platform_console"]])],
        })
        cls.tenant = cls.env["res.users"].create({
            "name": "Operations tenant", "login": "operations-tenant",
            "company_id": cls.company.id, "company_ids": [Command.set(cls.company.ids)],
            "groups_id": [Command.set([cls.env.ref("thirdcode_accounting.group_thirdcode_administrator").id])],
        })
        cls.group_only = cls.env["res.users"].create({
            "name": "Group only", "login": "operations-group-only",
            "company_id": cls.company.id, "company_ids": [Command.set(cls.company.ids)],
            "groups_id": [Command.set([cls.env.ref(x).id for x in ["base.group_user", "thirdcode_accounting.group_thirdcode_platform_console"]])],
        })
        cls.console = cls.env["thirdcode.platform.console"].with_user(cls.owner)

    def test_tenant_and_group_only_cannot_use_any_platform_api(self):
        calls = [
            ("get_console_data", []), ("get_analytics", []), ("get_options", []),
            ("get_organizations", []), ("get_people", []), ("get_audit", []),
            ("get_monitoring", []), ("get_publications", []), ("create_organization", [{}]),
            ("save_publication", [{}]), ("publish_content", [1,1]),
            ("set_incident_state", [1,"resolved"]), ("manage_person", [self.owner.id,"disable"]),
            ("extend_trial", [self.company.id,7]), ("mark_trial", [self.company.id]),
            ("convert_to_active", [self.company.id]), ("suspend_company", [self.company.id]),
            ("resume_company", [self.company.id]), ("provision_baseline", [self.company.id]),
            ("open_organization", [self.company.id]), ("open_company_users", [self.company.id]),
        ]
        for user in [self.tenant,self.group_only,self.env.ref("base.public_user")]:
            for method,args in calls:
                with self.subTest(user=user.login,method=method), self.assertRaises(AccessError):
                    getattr(self.console.with_user(user).with_context(tcsi_setup_token_ok=True),method)(*args)

    def test_forged_setup_context_does_not_authorize_recovery(self):
        for sudo in [False,True]:
            service = self.env["thirdcode.setup.service"].with_user(self.tenant)
            if sudo:service=service.sudo()
            with self.assertRaises(AccessError):
                service.with_context(tcsi_setup_token_ok=True).dispatch("status")

    def test_owner_is_outside_customer_membership_and_lists(self):
        self.assertEqual(self.owner.company_ids,self.home)
        self.assertEqual(self.owner.company_id,self.home)
        ids=[r["id"] for r in self.console.get_organizations()["rows"]]
        self.assertNotIn(self.home.id,ids)
        self.assertNotIn(self.owner.id,[r["id"] for r in self.console.get_people()["rows"]])
        tenant_users=self.env["res.users"].with_user(self.tenant).search([])
        self.assertNotIn(self.owner,tenant_users)
        self.assertNotIn(self.home,self.env["res.company"].with_user(self.tenant).search([]))
        self.env["res.company"].create({"name":"Another customer"})
        self.assertEqual(self.owner.company_ids,self.home)
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.owner.write({"company_ids":[Command.link(self.company.id)]})

    def test_owner_flag_and_context_defaults_are_protected(self):
        with self.assertRaises(AccessError):
            self.tenant.with_user(self.tenant).sudo().write({"thirdcode_platform_owner":True})
        with self.assertRaises(AccessError):
            self.env["res.users"].with_user(self.tenant).sudo().with_context(default_thirdcode_platform_owner=True).create({"name":"Forged", "login":"forged-owner"})
        for model in ["thirdcode.platform.event","thirdcode.platform.publication","thirdcode.platform.incident"]:
            with self.assertRaises(AccessError):
                self.env[model].with_user(self.tenant).create({})

    def test_owner_creation_and_promotion_force_private_home(self):
        user = self.env["res.users"].create({"name":"New owner", "login":"new-isolated-owner",
            "thirdcode_platform_owner":True, "company_id":self.company.id,
            "company_ids":[Command.set(self.company.ids)]})
        self.assertEqual(user.company_ids,self.home)
        self.tenant.write({"thirdcode_platform_owner":True})
        self.assertEqual(self.tenant.company_ids,self.home)
        self.assertEqual(self.tenant.company_id,self.home)

    def test_private_home_cannot_be_a_customer_target(self):
        with self.assertRaises(UserError):self.console.open_organization(self.home.id)
        wizard=self.env["thirdcode.employee.wizard"].with_user(self.owner).create({
            "name":"Customer", "login":"home-customer", "password":"not-a-real-secret", "company_id":self.home.id})
        with self.assertRaises(UserError):wizard.action_create_employee()

    def test_provisioning_is_atomic_and_response_loss_retry_is_idempotent(self):
        payload={"request_id":str(uuid.uuid4()),"name":"New console company", "country":"PH","currency":"PHP",
                 "admin_name":"Client lead","admin_login":"console-new@example.invalid","admin_password":"Synthetic-only-password"}
        service=type(self.env["thirdcode.setup.service"])
        with patch.object(service,"_action_ensure_baseline", return_value={"steps":[]}):
            result=self.console.create_organization(payload)
            retry=self.console.create_organization(payload)
        self.assertEqual(result["id"],retry["id"])
        admin=self.env["res.users"].browse(result["user_id"])
        self.assertEqual(admin.company_ids.ids,[result["id"]])
        self.assertTrue(admin.has_group("thirdcode_accounting.group_thirdcode_administrator"))
        self.assertFalse(admin.has_group("base.group_system"))
        self.assertEqual(self.owner.company_ids,self.home)
        failure=dict(payload,request_id=str(uuid.uuid4()),name="Rolled back company",admin_login="rollback@example.invalid")
        with self.assertRaises(UserError), self.cr.savepoint():
            with patch.object(service,"_action_ensure_baseline",side_effect=UserError("Synthetic baseline failure")):
                self.console.create_organization(failure)
        self.assertFalse(self.env["res.company"].search([("name","=",failure["name"])]))

    def test_publications_hold_public_snapshot_until_explicit_publish(self):
        values={"kind":"seo","title":"Original title","description":"Reviewed description","version":"","category":"improvement"}
        result=self.console.with_context(default_published_json='{"title":"Forged public"}', default_archived=True).save_publication(values)
        record=self.env["thirdcode.platform.publication"].browse(result["id"])
        self.assertFalse(record.published_json)
        self.assertFalse(record.archived)
        self.console.publish_content(record.id,record.revision)
        self.assertEqual(json.loads(record.published_json)["title"],"Original title")
        old_revision=record.revision
        self.console.save_publication(dict(values,title="Changed draft"),record.id,record.revision)
        self.assertEqual(json.loads(record.published_json)["title"],"Original title")
        with self.assertRaises(UserError):self.console.publish_content(record.id,old_revision)
        self.console.publish_content(record.id,record.revision)
        self.assertEqual(json.loads(record.published_json)["title"],"Changed draft")
        self.console.publish_content(record.id,record.revision,"revert")
        self.assertEqual(json.loads(record.published_json)["title"],"Original title")
        self.console.publish_content(record.id,record.revision,"archive")
        self.assertTrue(record.archived)
        with self.assertRaises(AccessError):record.with_user(self.tenant).read(["published_json"])
        with self.assertRaises(AccessError):record.with_user(self.group_only).read(["published_json"])
        with self.assertRaises(AccessError):record.with_user(self.owner).sudo().write({"published_json":"{}"})

    def test_incidents_group_without_private_request_contents(self):
        model=self.env["thirdcode.platform.incident"]
        model._capture("ValueError","/web/secret-user@example.com?token=private")
        model._capture("ValueError","/web/another-record")
        incident=model.search([("kind","=","ValueError"),("route","=","/web")])
        self.assertEqual(incident.occurrences,2)
        self.console.set_incident_state(incident.id,"resolved")
        model._capture("ValueError","/web/another-record")
        self.assertEqual(incident.state,"open")
        self.assertEqual(incident.occurrences,3)
        with self.assertRaises(AccessError):incident.with_user(self.group_only).read(["kind"])
        with self.assertRaises(AccessError):incident.with_user(self.tenant).sudo().write({"state":"resolved"})
        self.assertIn("jobs",self.console.get_monitoring())

    def test_operator_evidence_is_immutable_and_tenant_inaccessible(self):
        self.console.mark_trial(self.company.id)
        event=self.env["thirdcode.platform.event"].search([("company_id","=",self.company.id)],limit=1)
        self.assertEqual(event.actor_id,self.owner)
        with self.assertRaises(AccessError):event.write({"action":"forged"})
        with self.assertRaises(AccessError):event.unlink()
        with self.assertRaises(AccessError):event.with_user(self.group_only).read(["action"])
        self.assertGreaterEqual(self.console.get_audit()["total"],1)

    def test_analytics_counts_match_source(self):
        data=self.console.get_analytics(30)
        self.assertEqual(sum(p["count"] for p in data["points"]),data["total"])
        self.assertEqual(len(data["points"]),30)
        with self.assertRaises(UserError):self.console.get_analytics(36500)
        with self.assertRaises(UserError):self.console.get_people(page=-1)

    def test_publication_paging_always_keeps_homepage_seo(self):
        model = self.env["thirdcode.platform.publication"]
        seo = model._new_draft({"kind":"seo", "title":"Homepage", "description":"SEO"})
        for n in range(27):
            model._new_draft({"kind":"release", "title":"Update %s" % n, "description":"Details"})
        first = self.console.get_publications(0)
        second = self.console.get_publications(1)
        self.assertEqual(first["total"], 27)
        self.assertIn(seo.id, [r["id"] for r in first["rows"]])
        self.assertIn(seo.id, [r["id"] for r in second["rows"]])
        self.assertEqual(len(second["rows"]), 3)

    def test_analytics_uses_same_utc_day_window_for_totals_and_points(self):
        moves = self.env["account.move"]
        oldest = datetime.combine(fields.Date.today()-timedelta(days=29), time.min)
        # A real dated document is unnecessary here: exercise the grouping query
        # contract at UTC/Manila boundaries without requiring a client chart.
        with patch.object(type(moves), "_read_group", autospec=True, return_value=[]) as grouped:
            self.console.with_context(tz="Asia/Manila").get_analytics(30)
            recordset, domain = grouped.call_args.args[:2]
            self.assertEqual(recordset.env.context.get("tz"), "UTC")
            self.assertIn(("create_date", ">=", oldest), domain)
