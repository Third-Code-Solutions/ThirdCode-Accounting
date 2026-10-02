import logging

from odoo import Command, _, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

TRIAL_ROLE_GROUPS = {
    "administrator": "thirdcode_accounting.group_thirdcode_administrator",
    "accountant": "thirdcode_accounting.group_thirdcode_accountant",
    "encoder": "thirdcode_accounting.group_thirdcode_encoder",
    "readonly": "thirdcode_accounting.group_thirdcode_readonly",
}

TRIAL_JOURNALS = [
    ("Sales", "SLS", "sale"),
    ("Purchases", "PUR", "purchase"),
    ("Miscellaneous Operations", "MISC", "general"),
    ("Bank", "BNK", "bank"),
    ("Cash", "CSH", "cash"),
]


class ThirdCodeSetupService(models.AbstractModel):
    """Privileged pilot/trial provisioning service.

    Only reachable through the token-checked ``/tcsi/setup`` controller, which
    sets ``tcsi_setup_token_ok`` in the context. All operations are idempotent
    so the pilot can be re-provisioned after any partial failure.
    """

    _name = "thirdcode.setup.service"
    _description = "Privileged pilot/trial provisioning service"

    # ------------------------------------------------------------------
    # dispatch
    # ------------------------------------------------------------------
    def dispatch(self, action, payload=None):
        if self.env.context.get("tcsi_setup_token_ok") is not True:
            raise AccessError(
                _(
                    "The setup service is only callable through the token-checked setup endpoint."
                )
            )
        payload = payload or {}
        handler = getattr(self, "_action_%s" % action, None) if action else None
        if not handler or not callable(handler):
            raise UserError(_("Unknown setup action: %s") % (action or "<missing>",))
        result = handler(payload)
        _logger.info("TCSI setup: action %s -> %s", action, result)
        return result

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------
    def _action_ping(self, payload):
        return {"pong": True, "database": self.env.cr.dbname}

    def _action_status(self, payload):
        companies = [
            self._company_summary(company)
            for company in self.env["res.company"].sudo().search([])
        ]
        users = []
        role_group_ids = {
            name: self.env.ref(xmlid).id for name, xmlid in TRIAL_ROLE_GROUPS.items()
        }
        for user in self.env["res.users"].sudo().with_context(active_test=False).search([]):
            roles = [
                name for name, group_id in role_group_ids.items() if group_id in user.groups_id.ids
            ]
            users.append(
                {
                    "id": user.id,
                    "login": user.login,
                    "active": user.active,
                    "companies": user.company_ids.ids,
                    "roles": roles,
                }
            )
        return {"database": self.env.cr.dbname, "uid": self.env.uid, "companies": companies, "users": users}

    def _action_create_company(self, payload):
        name = str(payload.get("name") or "").strip()
        if not name:
            raise UserError(_("A company name is required."))
        company = (
            self.env["res.company"]
            .sudo()
            .search([("name", "=", name)], limit=1)
        )
        if company:
            steps = ["company already exists: %s" % name]
        else:
            create_vals = {"name": name}
            country = self._find_country(payload)
            if country:
                create_vals["country_id"] = country.id
            currency = self._find_currency(payload)
            if currency:
                if not currency.active:
                    currency.sudo().write({"active": True})
                create_vals["currency_id"] = currency.id
            company = self.env["res.company"].sudo().create(create_vals)
            steps = ["created company: %s" % name]
        baseline = self._action_ensure_baseline(dict(payload, company_id=company.id))
        return {
            "company_id": company.id,
            "steps": steps + baseline["steps"],
            "company": baseline["company"],
        }

    def _action_ensure_baseline(self, payload):
        company = self._get_company(payload)
        steps = []
        steps += self._ensure_country_currency(company, payload)
        steps += self._ensure_chart(company, payload)
        steps += self._ensure_journals(company)
        steps += self._ensure_period(company, payload)
        return {
            "company_id": company.id,
            "steps": steps,
            "company": self._company_summary(company),
        }

    def _action_create_user(self, payload):
        login = str(payload.get("login") or "").strip()
        if not login:
            raise UserError(_("A login is required."))
        name = str(payload.get("name") or login).strip()
        password = str(payload.get("password") or "")
        role = str(payload.get("role") or "").strip()
        if role not in TRIAL_ROLE_GROUPS:
            raise UserError(
                _("Unknown role '%s'. Expected one of: %s")
                % (role, ", ".join(sorted(TRIAL_ROLE_GROUPS)))
            )
        company = self._get_company(payload)
        role_group = self.env.ref(TRIAL_ROLE_GROUPS[role])
        base_group = self.env.ref("base.group_user")
        user = (
            self.env["res.users"]
            .sudo()
            .with_context(active_test=False)
            .search([("login", "=", login)], limit=1)
        )
        if user:
            updates = {"name": name, "active": True}
            if password:
                updates["password"] = password
            if payload.get("regroup"):
                updates["company_id"] = company.id
                updates["company_ids"] = [Command.set([company.id])]
                updates["groups_id"] = [Command.set([base_group.id, role_group.id])]
            user.write(updates)
            action = "updated"
        else:
            if not password:
                raise UserError(_("A password is required for a new user."))
            user = self.env["res.users"].sudo().create(
                {
                    "name": name,
                    "login": login,
                    "password": password,
                    "company_id": company.id,
                    "company_ids": [Command.set([company.id])],
                    "groups_id": [Command.set([base_group.id, role_group.id])],
                }
            )
            action = "created"
        return {
            "uid": user.id,
            "login": user.login,
            "role": role,
            "company_id": company.id,
            "action": action,
        }

    def _action_batch(self, payload):
        actions = payload.get("actions")
        if not isinstance(actions, list) or not actions:
            raise UserError(_("'actions' must be a non-empty list."))
        results = []
        for item in actions:
            item = dict(item or {})
            action_name = item.pop("action", None)
            try:
                results.append(
                    {
                        "action": action_name,
                        "ok": True,
                        "result": self.dispatch(action_name, item),
                    }
                )
            except Exception as exc:  # noqa: BLE001 - partial progress is reported per action
                results.append(
                    {
                        "action": action_name,
                        "ok": False,
                        "error": "%s: %s" % (type(exc).__name__, exc),
                    }
                )
        return {"results": results}

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _get_company(self, payload):
        try:
            company_id = int(payload.get("company_id") or 0)
        except (TypeError, ValueError):
            raise UserError(_("company_id must be an integer.")) from None
        company = self.env["res.company"].sudo().browse(company_id).exists()
        if not company:
            raise UserError(_("Company %s does not exist.") % company_id)
        return company

    def _company_summary(self, company):
        today = fields.Date.context_today(self)
        open_periods = self.env["thirdcode.accounting.period"].sudo().search_count(
            [
                ("company_id", "=", company.id),
                ("state", "=", "open"),
                ("date_start", "<=", today),
                ("date_end", ">=", today),
            ]
        )
        return {
            "id": company.id,
            "name": company.name,
            "currency": company.currency_id.name or False,
            "country": company.country_id.code or False,
            "trial_mode": bool(company.thirdcode_trial_mode),
            "accounts": self.env["account.account"].sudo().search_count(
                [("company_ids", "in", company.id)]
            ),
            "journals": self.env["account.journal"].sudo().search_count(
                [("company_id", "=", company.id)]
            ),
            "taxes": self.env["account.tax"].sudo().search_count(
                [("company_id", "=", company.id)]
            ),
            "open_periods_today": open_periods,
        }

    def _find_country(self, payload):
        code = str(payload.get("country_code") or "PH").upper()
        return self.env["res.country"].sudo().search([("code", "=", code)], limit=1)

    def _find_currency(self, payload):
        code = str(payload.get("currency") or "PHP").upper()
        return (
            self.env["res.currency"]
            .sudo()
            .with_context(active_test=False)
            .search([("name", "=", code)], limit=1)
        )

    def _ensure_country_currency(self, company, payload):
        steps = []
        currency_code = str(payload.get("currency") or "PHP").upper()
        updates = {}
        country = self._find_country(payload)
        if country and company.country_id != country:
            updates["country_id"] = country.id
        currency = self._find_currency(payload)
        if currency:
            if not currency.active:
                currency.sudo().write({"active": True})
                steps.append("activated currency %s" % currency_code)
            if company.currency_id != currency:
                updates["currency_id"] = currency.id
        else:
            steps.append("currency %s not found; left unchanged" % currency_code)
        layout_xmlid = str(
            payload.get("external_report_layout") or "web.report_layout_standard"
        )
        if not company.external_report_layout_id:
            layout = self.env.ref(layout_xmlid, raise_if_not_found=False)
            if layout:
                updates["external_report_layout_id"] = layout.id
            else:
                steps.append(
                    "external report layout %s not found; left unchanged" % layout_xmlid
                )
        if payload.get("trial_mode") is not None:
            updates["thirdcode_trial_mode"] = bool(payload["trial_mode"])
        if payload.get("payment_approval_enabled") is not None:
            updates["thirdcode_payment_approval_enabled"] = bool(
                payload["payment_approval_enabled"]
            )
        if updates:
            company.write(updates)
            steps.append("company updated: %s" % ", ".join(sorted(updates)))
        elif not steps:
            steps.append("country/currency already current")
        return steps

    def _ensure_chart(self, company, payload):
        chart_template = str(payload.get("chart_template") or "ph")
        accounts = self.env["account.account"].sudo().search_count(
            [("company_ids", "in", company.id)]
        )
        if accounts:
            return ["chart already present (%s accounts)" % accounts]
        self.env["account.chart.template"].sudo().try_loading(chart_template, company)
        accounts = self.env["account.account"].sudo().search_count(
            [("company_ids", "in", company.id)]
        )
        return ["loaded chart '%s' (%s accounts)" % (chart_template, accounts)]

    def _ensure_journals(self, company):
        existing = self.env["account.journal"].sudo().search(
            [("company_id", "=", company.id)]
        )
        have_types = set(existing.mapped("type"))
        used_codes = set(existing.mapped("code"))
        created = []
        for name, code, journal_type in TRIAL_JOURNALS:
            if journal_type in have_types:
                continue
            candidate = code
            suffix = 2
            while candidate in used_codes:
                candidate = "%s%d" % (code, suffix)
                suffix += 1
            self.env["account.journal"].sudo().create(
                {
                    "name": name,
                    "code": candidate,
                    "type": journal_type,
                    "company_id": company.id,
                }
            )
            used_codes.add(candidate)
            have_types.add(journal_type)
            created.append("%s:%s" % (journal_type, candidate))
        if created:
            return ["journals created: %s" % ", ".join(created)]
        return ["journals already complete"]

    def _ensure_period(self, company, payload):
        today = fields.Date.context_today(self)
        name = str(payload.get("period_name") or "FY %s" % today.year)
        try:
            start = fields.Date.to_date(payload.get("period_start")) if payload.get("period_start") else today.replace(month=1, day=1)
            end = fields.Date.to_date(payload.get("period_end")) if payload.get("period_end") else today.replace(month=12, day=31)
        except (ValueError, TypeError):
            raise UserError(_("period_start/period_end must use YYYY-MM-DD.")) from None
        periods = self.env["thirdcode.accounting.period"].sudo().search(
            [("company_id", "=", company.id)]
        )
        open_overlap = periods.filtered(
            lambda period: period.state == "open"
            and period.date_start <= end
            and period.date_end >= start
        )
        if open_overlap:
            return ["open period reused: %s" % open_overlap[0].name]
        overlapping = periods.filtered(
            lambda period: period.date_start <= end and period.date_end >= start
        )
        if overlapping:
            for period in overlapping:
                period.sudo().write(
                    {
                        "state": "open",
                        "reopened_by": self.env.uid,
                        "reopened_at": fields.Datetime.now(),
                    }
                )
            return ["reopened overlapping period: %s" % overlapping[0].name]
        period = self.env["thirdcode.accounting.period"].sudo().create(
            {
                "name": name,
                "company_id": company.id,
                "date_start": start,
                "date_end": end,
                "state": "open",
            }
        )
        return ["created open period %s (%s..%s)" % (period.name, start, end)]
