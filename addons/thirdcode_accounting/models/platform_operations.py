"""Bounded owner APIs. All authority checks precede cross-company elevation."""
import re
import uuid
from datetime import datetime, time, timedelta

from odoo import _, api, fields, models, Command
from odoo.exceptions import UserError
from .setup_service import TRIAL_ROLE_GROUPS


def bounded_text(value, label, maximum=160, required=True):
    if not isinstance(value, str) or len(value.strip()) > maximum or (required and not value.strip()):
        raise UserError(_("Invalid %s.") % label)
    return value.strip()


def bounded_page(value):
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 100000:
        raise UserError(_("Invalid page."))
    return value


class PlatformOperations(models.TransientModel):
    _inherit = "thirdcode.platform.console"

    @api.model
    def get_options(self):
        self._check_console_access()
        return {
            "countries": self.env["res.country"].sudo().search_read([], ["name", "code"], order="name"),
            "currencies": self.env["res.currency"].sudo().with_context(active_test=False).search_read(
                [], ["name"], order="name"),
        }

    @api.model
    def create_organization(self, payload):
        self._check_console_access()
        allowed = {"request_id", "name", "country", "currency", "admin_name", "admin_login", "admin_password"}
        if not isinstance(payload, dict) or set(payload) != allowed:
            raise UserError(_("Complete all organization and administrator fields."))
        try:
            request_id = str(uuid.UUID(payload["request_id"]))
        except (ValueError, TypeError, AttributeError):
            raise UserError(_("Invalid creation request.")) from None
        # Lock this request before the lookup: a response-loss retry is idempotent.
        self.env.cr.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", [request_id])
        existing = self.env["res.company"].sudo().search([("thirdcode_provisioning_key", "=", request_id)], limit=1)
        if existing:
            return {"id": existing.id, "name": existing.name, "reused": True}
        name = bounded_text(payload["name"], "company name")
        admin_name = bounded_text(payload["admin_name"], "administrator name")
        login = bounded_text(payload["admin_login"], "login email").lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", login):
            raise UserError(_("Enter a valid administrator email."))
        password = payload["admin_password"]
        if not isinstance(password, str) or not 12 <= len(password) <= 256:
            raise UserError(_("Use an initial password between 12 and 256 characters."))
        country_code = bounded_text(payload["country"], "country", 2).upper()
        currency_code = bounded_text(payload["currency"], "currency", 3).upper()
        country = self.env["res.country"].sudo().search([("code", "=", country_code)], limit=1)
        currency = self.env["res.currency"].sudo().with_context(active_test=False).search([("name", "=", currency_code)], limit=1)
        if not country or not currency:
            raise UserError(_("Select a valid country and currency."))
        # The current product provisions the reviewed Philippine baseline only.
        if country_code != "PH":
            raise UserError(_("Automatic onboarding currently supports the Philippine chart. Other countries require an approved localization."))
        if self.env["res.users"].sudo().with_context(active_test=False).search_count([("login", "=", login)]):
            raise UserError(_("This login is not available."))
        if self.env["res.company"].sudo().search_count([("name", "=", name)]):
            raise UserError(_("An organization with this name already exists."))
        currency.sudo().write({"active": True})
        company = self.env["res.company"].sudo().create({
            "name": name, "country_id": country.id, "currency_id": currency.id,
            "thirdcode_provisioning_key": request_id, "thirdcode_trial_mode": True,
            "thirdcode_platform_status": "trial", "thirdcode_trial_start": fields.Date.today(),
            "thirdcode_trial_end": fields.Date.today() + timedelta(days=30),
        })
        service = self.env["thirdcode.setup.service"].sudo()
        service._action_ensure_baseline({"company_id": company.id, "country_code": country_code,
                                        "currency": currency_code, "chart_template": "ph"})
        user = service._provision_user(login=login, name=admin_name, password=password,
                                      company=company, role="administrator", require_new=True)
        self._event("organization.created", company)
        return {"id": company.id, "name": company.name, "admin_login": login, "user_id": user["uid"]}

    @api.model
    def get_organizations(self, query="", status="", page=0):
        self._check_console_access()
        query = bounded_text(query, "search", 100, required=False)
        if status not in ("", "trial", "active", "suspended"):
            raise UserError(_("Invalid organization status."))
        domain = [("thirdcode_is_platform", "=", False)]
        if query:
            domain.append(("name", "ilike", query))
        if status:
            domain.append(("thirdcode_platform_status", "=", status))
        model = self.env["res.company"].sudo()
        records = model.search(domain, offset=bounded_page(page)*25, limit=25, order="name,id")
        return {"rows": [self._company_row(c, fields.Datetime.now()-timedelta(days=7)) for c in records],
                "total": model.search_count(domain), "page": page, "page_size": 25}

    @api.model
    def get_people(self, company_id=False, query="", page=0):
        self._check_console_access()
        domain = [("share", "=", False), ("thirdcode_platform_owner", "=", False),
                  ("company_id.thirdcode_is_platform", "=", False)]
        if company_id:
            domain.append(("company_ids", "in", self._get_company(company_id).id))
        query = bounded_text(query, "search", 100, required=False)
        if query:
            domain += ["|", ("name", "ilike", query), ("login", "ilike", query)]
        model = self.env["res.users"].sudo().with_context(active_test=False)
        users = model.search(domain, offset=bounded_page(page)*25, limit=25, order="name,id")
        role_groups = {role: self.env.ref(xmlid) for role, xmlid in TRIAL_ROLE_GROUPS.items()}
        return {"rows": [{"id": u.id, "name": u.name, "login": u.login, "active": u.active,
                           "company": u.company_id.name, "company_id": u.company_id.id, "protected": u.has_group("base.group_system"),
                           "last_login": self._fmt(u.login_date),
                           "role": next((r for r,g in role_groups.items() if g in u.groups_id), "custom")}
                          for u in users], "total": model.search_count(domain), "page": page, "page_size": 25}

    @api.model
    def manage_person(self, user_id, action, role=False):
        self._check_console_access()
        user = self.env["res.users"].sudo().with_context(active_test=False).browse(int(user_id)).exists()
        if not user or user.share or user.thirdcode_platform_owner or user.has_group("base.group_system"):
            raise UserError(_("Choose a customer employee account."))
        company = self._get_company(user.company_id.id)
        if action in ("enable", "disable"):
            if action == "enable" and company.thirdcode_platform_status == "suspended":
                raise UserError(_("Resume the organization before enabling its employees."))
            user.write({"active": action == "enable"})
        elif action == "role" and role in TRIAL_ROLE_GROUPS:
            user.write({"groups_id": [Command.set([self.env.ref("base.group_user").id,
                                                   self.env.ref(TRIAL_ROLE_GROUPS[role]).id])]})
        else:
            raise UserError(_("Invalid employee action."))
        self.env["thirdcode.platform.event"]._record("employee."+action, str(user.id), company)
        return True

    @api.model
    def get_audit(self, query="", company_id=False, page=0, source="platform"):
        self._check_console_access()
        query = bounded_text(query, "search", 100, required=False)
        offset = bounded_page(page)*30
        if source == "platform":
            model = self.env["thirdcode.platform.event"].sudo()
            domain = [("company_id", "=", self._get_company(company_id).id)] if company_id else []
            if query:
                domain += ["|", ("action", "ilike", query), ("target", "ilike", query)]
            rows = [{"id": r.id, "when": self._fmt(r.create_date), "actor": r.actor_id.name,
                     "action": r.action, "target": r.target, "company": r.company_id.name or "Platform"}
                    for r in model.search(domain, offset=offset, limit=30, order="id desc")]
        elif source == "accounting":
            model = self.env["auditlog.log"].sudo()
            domain = [("thirdcode_company_ids", "in", self._get_company(company_id).id)] if company_id else []
            if query:
                domain += [("model_id.model", "ilike", query)]
            rows = [{"id": r.id, "when": self._fmt(r.create_date), "actor": r.user_id.name,
                     "action": r.method, "target": "%s #%s" % (r.model_id.model, r.res_id),
                     "company": ", ".join(r.thirdcode_company_ids.mapped("name")) or "Platform / historical scope"}
                    for r in model.search(domain, offset=offset, limit=30, order="id desc")]
        else:
            raise UserError(_("Invalid audit source."))
        return {"rows": rows, "total": model.search_count(domain), "page": page, "page_size": 30}

    @api.model
    def get_analytics(self, days=30):
        self._check_console_access()
        if days not in (7, 30, 90):
            raise UserError(_("Choose a 7, 30 or 90 day window."))
        today = fields.Date.today()
        start = datetime.combine(today-timedelta(days=days-1), time.min)
        moves = self.env["account.move"].sudo().with_context(tz="UTC")
        domain = [("create_date", ">=", start), ("company_id.thirdcode_is_platform", "=", False)]
        states = moves.read_group(domain, ["state"], ["state"], lazy=False)
        # Volumes only: never sum unrelated organizations/currencies into revenue.
        daily = moves._read_group(domain, ["create_date:day"], ["__count"])
        counts = {str(day.date() if hasattr(day, "date") else day): count for day,count in daily}
        points = [{"date": str(today-timedelta(days=days-1-i)), "count": counts.get(str(today-timedelta(days=days-1-i)),0)} for i in range(days)]
        maximum = max([p["count"] for p in points]+[1])
        for point in points:
            point["height"] = round(point["count"]*100/maximum)
        return {"days": days, "since": fields.Datetime.to_string(start), "points": points,
                "states": [{"label": STATE, "count": r["__count"]} for r in states for STATE in [r["state"]]],
                "total": moves.search_count(domain),
                "organizations": self.env["res.company"].sudo().search_count([("thirdcode_is_platform", "=", False)]),
                "active_users": self.env["res.users"].sudo().search_count([("share", "=", False), ("thirdcode_platform_owner", "=", False), ("company_id.thirdcode_is_platform", "=", False)])}
