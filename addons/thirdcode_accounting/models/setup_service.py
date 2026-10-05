import logging

from odoo import Command, _, fields, models
from odoo.exceptions import AccessError, UserError
from .platform_access import require_platform_owner

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
        require_platform_owner(self.env)
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

    def _action_maintenance(self, payload):
        op = str(payload.get("op") or "locks")
        if op == "locks":
            self.env.cr.execute(
                """
                SELECT pid,
                       state,
                       wait_event_type,
                       wait_event,
                       EXTRACT(EPOCH FROM (now() - xact_start))::int AS xact_age_s,
                       EXTRACT(EPOCH FROM (now() - query_start))::int AS query_age_s,
                       left(query, 200) AS query
                  FROM pg_stat_activity
                 WHERE datname = current_database()
                   AND pid <> pg_backend_pid()
                 ORDER BY xact_start NULLS LAST
                """
            )
            return {"backends": self.env.cr.dictfetchall()}
        if op == "terminate_pids":
            pids = [int(pid) for pid in payload.get("pids") or []]
            terminated = {}
            for pid in pids:
                self.env.cr.execute("SELECT pg_terminate_backend(%s)", (pid,))
                terminated[str(pid)] = self.env.cr.fetchone()[0]
            return {"terminated": terminated}
        if op == "terminate_idle":
            min_age = int(payload.get("min_age_seconds") or 600)
            self.env.cr.execute(
                """
                SELECT pid,
                       EXTRACT(EPOCH FROM (now() - state_change))::int AS idle_age_s,
                       left(query, 160) AS query
                  FROM pg_stat_activity
                 WHERE datname = current_database()
                   AND pid <> pg_backend_pid()
                   AND state = 'idle in transaction'
                   AND now() - state_change > make_interval(secs => %s)
                """,
                (min_age,),
            )
            victims = self.env.cr.dictfetchall()
            terminated = {}
            for row in victims:
                try:
                    self.env.cr.execute("SELECT pg_terminate_backend(%s)", (row["pid"],))
                    terminated[str(row["pid"])] = self.env.cr.fetchone()[0]
                except Exception as exc:  # noqa: BLE001
                    terminated[str(row["pid"])] = str(exc)[:120]
            return {"examined": victims, "terminated": terminated, "min_age_seconds": min_age}
        raise UserError(_("Unknown maintenance op: %s") % op)

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
        return self._provision_user(
            login=payload.get("login"),
            name=payload.get("name"),
            password=payload.get("password"),
            company=self._get_company(payload),
            role=str(payload.get("role") or "").strip(),
            extra_group_xmlids=payload.get("extra_groups"),
            all_companies=bool(payload.get("all_companies")),
            company_ids=payload.get("company_ids"),
            regroup=bool(payload.get("regroup")),
        )

    def _provision_user(
        self,
        login,
        name=None,
        password=None,
        company=None,
        role="accountant",
        extra_group_xmlids=None,
        all_companies=False,
        company_ids=None,
        regroup=True,
        require_new=False,
    ):
        """Create or update a role user inside a company.

        Callers are responsible for access checks: the setup controller is
        token-gated, and the in-app wizards verify administrator rights.
        """
        login = str(login or "").strip().lower()
        if not login:
            raise UserError(_("A login is required."))
        name = str(name or login).strip()
        role = str(role or "").strip()
        if role not in TRIAL_ROLE_GROUPS:
            raise UserError(
                _("Unknown role '%s'. Expected one of: %s")
                % (role, ", ".join(sorted(TRIAL_ROLE_GROUPS)))
            )
        if not company:
            raise UserError(_("A company is required."))
        role_group = self.env.ref(TRIAL_ROLE_GROUPS[role])
        base_group = self.env.ref("base.group_user")
        group_ids = [base_group.id, role_group.id]
        for xmlid in extra_group_xmlids or []:
            extra_group = self.env.ref(str(xmlid), raise_if_not_found=False)
            if not extra_group:
                raise UserError(_("Unknown security group: %s") % xmlid)
            group_ids.append(extra_group.id)
        target_company_ids = [company.id]
        if all_companies:
            target_company_ids = self.env["res.company"].sudo().search([]).ids
        elif company_ids:
            target_company_ids = [int(cid) for cid in company_ids]
        platform_owner = "base.group_system" in (extra_group_xmlids or [])
        home_action = self.env.ref(
            "thirdcode_accounting.action_thirdcode_platform_console"
            if platform_owner
            else "thirdcode_accounting.action_tcsi_dashboard",
            raise_if_not_found=False,
        )
        if platform_owner:
            company = self.env.ref("thirdcode_accounting.company_platform", raise_if_not_found=False) or company
            target_company_ids = company.ids
            group_ids = [base_group.id, self.env.ref("base.group_system").id]
            console_group = self.env.ref(
                "thirdcode_accounting.group_thirdcode_platform_console",
                raise_if_not_found=False,
            )
            if console_group and console_group.id not in group_ids:
                group_ids.append(console_group.id)
        user = (
            self.env["res.users"]
            .sudo()
            .with_context(active_test=False)
            .search([("login", "=", login)], limit=1)
        )
        if user and require_new:
            raise UserError(_("This login is not available."))
        if user:
            updates = {"name": name, "active": True}
            if password:
                updates["password"] = password
            if regroup:
                updates["company_id"] = company.id
                updates["company_ids"] = [Command.set(target_company_ids)]
                updates["groups_id"] = [Command.set(group_ids)]
                updates["thirdcode_platform_owner"] = platform_owner
            user.write(updates)
            if home_action and not user.action_id:
                # Land every workspace account on its finance overview (or the
                # platform console for owners) instead of the client default.
                user.write({"action_id": home_action.id})
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
                    "company_ids": [Command.set(target_company_ids)],
                    "groups_id": [Command.set(group_ids)],
                    "thirdcode_platform_owner": platform_owner,
                    "action_id": home_action.id if home_action else False,
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
            payload.get("external_report_layout") or "web.external_layout_standard"
        )
        current_layout = company.external_report_layout_id
        if not current_layout or "external_layout" not in (current_layout.key or ""):
            layout_ref = self.env.ref(layout_xmlid, raise_if_not_found=False)
            layout_view = layout_ref
            if (
                layout_ref
                and layout_ref._name != "ir.ui.view"
                and "view_id" in layout_ref._fields
            ):
                layout_view = layout_ref.view_id
            if layout_view and layout_view._name == "ir.ui.view" and layout_view.key:
                updates["external_report_layout_id"] = layout_view.id
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
