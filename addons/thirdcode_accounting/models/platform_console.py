import json
import logging
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

PLATFORM_CONSOLE_GROUP = "thirdcode_accounting.group_thirdcode_platform_console"
SYSTEM_GROUP = "base.group_system"
TRIAL_DEFAULT_DAYS = 30
TRIAL_WARNING_DAYS = 7
BASELINE_ACCOUNT_MIN = 20

MOVE_TYPE_LABELS = {
    "out_invoice": "Customer invoice",
    "in_invoice": "Vendor bill",
    "out_refund": "Customer credit note",
    "in_refund": "Vendor credit note",
    "entry": "Journal entry",
}
STATE_LABELS = {"draft": "Draft", "posted": "Posted", "cancel": "Cancelled"}
STATUS_LABELS = {"trial": "Trial", "active": "Active", "suspended": "Suspended"}
STATUS_ORDER = {"trial": 0, "active": 1, "suspended": 2}


class PlatformConsole(models.TransientModel):
    _name = "thirdcode.platform.console"
    _description = "TCSI platform owner console"

    name = fields.Char(default="Platform console")

    # ------------------------------------------------------------------ access

    @api.model
    def _check_console_access(self):
        user = self.env.user
        if user.has_group(SYSTEM_GROUP) or user.has_group(PLATFORM_CONSOLE_GROUP):
            return True
        raise AccessError(_("The platform console is reserved to the system owner."))

    @api.model
    def _get_company(self, company_id):
        company = self.env["res.company"].sudo().browse(int(company_id)).exists()
        if not company:
            raise UserError(_("Unknown organisation."))
        return company

    # ------------------------------------------------------------- aggregations

    @api.model
    def _company_field(self, model, candidates=("company_id", "company_ids")):
        """Return the single- or multi-company field name a model actually has."""
        for name in candidates:
            if name in model._fields:
                return name, name.endswith("s")
        return "company_id", False

    @api.model
    def _company_domain(self, model, company):
        field, multi = self._company_field(model)
        return [(field, "in" if multi else "=", company.id)]

    @api.model
    def _fmt(self, value):
        return value.strftime("%Y-%m-%d %H:%M") if value else None

    @api.model
    def _ensure_trial_window(self, company):
        """Backfill missing trial dates for organisations on a trial window."""
        if (company.thirdcode_platform_status or "trial") != "trial":
            return
        today = fields.Date.context_today(self)
        updates = {}
        if not company.thirdcode_trial_start:
            start = (company.create_date or fields.Datetime.now()).date()
            updates["thirdcode_trial_start"] = start
        if not company.thirdcode_trial_end:
            start = updates.get("thirdcode_trial_start") or company.thirdcode_trial_start
            updates["thirdcode_trial_end"] = start + relativedelta(days=TRIAL_DEFAULT_DAYS)
        if updates:
            company.write(updates)

    @api.model
    def _company_row(self, company, week_start):
        self._ensure_trial_window(company)
        today = fields.Date.context_today(self)
        move = self.env["account.move"].sudo()
        posted = self._company_domain(move, company) + [("state", "=", "posted")]
        docs_total = move.search_count(posted)
        docs_week = move.search_count(posted + [("create_date", ">=", week_start)])
        last_move = move.search(posted, order="create_date desc, id desc", limit=1)
        users = (
            self.env["res.users"]
            .sudo()
            .with_context(active_test=False)
            .search([("share", "=", False), ("company_ids", "in", company.id)])
        )
        active_users = users.filtered("active")
        signed_week = active_users.filtered(
            lambda user: user.login_date and user.login_date >= week_start
        )
        never_signed = active_users.filtered(lambda user: not user.login_date)
        logins = [user.login_date for user in active_users if user.login_date]
        accounts = self.env["account.account"].sudo().search_count(
            self._company_domain(self.env["account.account"], company)
        )
        journals = self.env["account.journal"].sudo().search_count(
            self._company_domain(self.env["account.journal"], company)
        )
        periods = self.env["thirdcode.accounting.period"].sudo().search_count(
            self._company_domain(self.env["thirdcode.accounting.period"], company)
            + [("state", "=", "open")]
        )
        days_left = None
        if company.thirdcode_trial_end:
            days_left = (company.thirdcode_trial_end - today).days
        return {
            "id": company.id,
            "name": company.name,
            "status": company.thirdcode_platform_status or "trial",
            "status_label": STATUS_LABELS.get(company.thirdcode_platform_status or "trial", "Trial"),
            "trial_start": str(company.thirdcode_trial_start) if company.thirdcode_trial_start else None,
            "trial_end": str(company.thirdcode_trial_end) if company.thirdcode_trial_end else None,
            "days_left": days_left,
            "users": len(active_users),
            "users_week": len(signed_week),
            "never_signed": len(never_signed),
            "docs": docs_total,
            "docs_week": docs_week,
            "last_document": self._fmt(last_move.create_date) if last_move else None,
            "last_document_ref": last_move.name if last_move else None,
            "last_login": self._fmt(max(logins)) if logins else None,
            "accounts": accounts,
            "journals": journals,
            "open_periods": periods,
            "baseline_ready": accounts >= BASELINE_ACCOUNT_MIN and journals >= 1,
        }

    @api.model
    def _alerts(self, rows):
        today = fields.Date.context_today(self)
        alerts = []
        for row in rows:
            if row["status"] == "trial" and row["days_left"] is not None:
                if row["days_left"] < 0:
                    alerts.append(
                        {
                            "level": "critical",
                            "company_id": row["id"],
                            "company": row["name"],
                            "title": _("Trial expired %s day(s) ago") % abs(row["days_left"]),
                            "detail": _("Extend the window or convert the organisation."),
                        }
                    )
                elif row["days_left"] <= TRIAL_WARNING_DAYS:
                    alerts.append(
                        {
                            "level": "warning",
                            "company_id": row["id"],
                            "company": row["name"],
                            "title": _("Trial ends in %s day(s)") % row["days_left"],
                            "detail": _("Extend the window or plan the conversion."),
                        }
                    )
            if not row["baseline_ready"]:
                alerts.append(
                    {
                        "level": "critical",
                        "company_id": row["id"],
                        "company": row["name"],
                        "title": _("Baseline incomplete"),
                        "detail": _("Only %(accounts)s accounts, %(journals)s journals, %(periods)s open period(s). Run Provision baseline.")
                        % {"accounts": row["accounts"], "journals": row["journals"], "periods": row["open_periods"]},
                    }
                )
            if row["status"] == "trial" and row["docs"] == 0:
                alerts.append(
                    {
                        "level": "info",
                        "company_id": row["id"],
                        "company": row["name"],
                        "title": _("No documents posted yet"),
                        "detail": _("Onboarding touch recommended — the team may need a walkthrough."),
                    }
                )
            if row["status"] == "suspended":
                alerts.append(
                    {
                        "level": "info",
                        "company_id": row["id"],
                        "company": row["name"],
                        "title": _("Suspended"),
                        "detail": _("All of this organisation's users are disabled."),
                    }
                )
            if row["never_signed"]:
                alerts.append(
                    {
                        "level": "warning",
                        "company_id": row["id"],
                        "company": row["name"],
                        "title": _("%s account(s) never signed in") % row["never_signed"],
                        "detail": _("Check that the handover reached every user."),
                    }
                )
        order = {"critical": 0, "warning": 1, "info": 2}
        alerts.sort(key=lambda alert: (order.get(alert["level"], 3), alert["company"] or ""))
        return alerts

    @api.model
    def _trend(self, days=14):
        start = fields.Datetime.now() - timedelta(days=days - 1)
        groups = self.env["account.move"].sudo().read_group(
            [("create_date", ">=", start)], ["id"], ["create_date:day"], lazy=False
        )
        counts = {}
        for group in groups:
            key = str(group.get("create_date:day") or "")[:10]
            if key:
                counts[key] = group.get("__count", 0)
        points = []
        maximum = 1
        today = fields.Date.context_today(self)
        for offset in range(days):
            day = today - timedelta(days=days - 1 - offset)
            key = str(day)
            count = counts.get(key, 0)
            maximum = max(maximum, count)
            points.append({"date": key, "label": key[5:], "count": count})
        for point in points:
            point["height"] = max(4, round(point["count"] * 100 / maximum)) if point["count"] else 0
        return points

    @api.model
    def _activity(self, limit=24):
        moves = (
            self.env["account.move"]
            .sudo()
            .search_read(
                [],
                ["name", "move_type", "state", "company_id", "create_uid", "create_date", "amount_total", "currency_id"],
                limit=limit,
                order="create_date desc, id desc",
            )
        )
        documents = [
            {
                "id": move["id"],
                "ref": move["name"] or _("(draft)"),
                "kind": MOVE_TYPE_LABELS.get(move["move_type"], move["move_type"]),
                "state": STATE_LABELS.get(move["state"], move["state"]),
                "company": move["company_id"][1] if move["company_id"] else "",
                "user": move["create_uid"][1] if move["create_uid"] else "",
                "amount": move["amount_total"],
                "currency": move["currency_id"][1] if move["currency_id"] else "",
                "when": self._fmt(move["create_date"]),
            }
            for move in moves
        ]
        signins = (
            self.env["res.users"]
            .sudo()
            .search_read(
                [("login_date", "!=", False), ("share", "=", False)],
                ["name", "login", "login_date", "company_id"],
                limit=12,
                order="login_date desc",
            )
        )
        sessions = [
            {
                "name": user["name"],
                "login": user["login"],
                "company": user["company_id"][1] if user["company_id"] else "",
                "when": self._fmt(user["login_date"]),
            }
            for user in signins
        ]
        return {"documents": documents, "signins": sessions}

    @api.model
    def _system(self):
        import odoo

        module = (
            self.env["ir.module.module"]
            .sudo()
            .search([("name", "=", "thirdcode_accounting")], limit=1)
        )
        workers = None
        try:
            from odoo.tools import config

            workers = config.get("workers")
        except Exception:  # pragma: no cover - config always exists in practice
            workers = None
        server_mode = _("threaded") if not workers else _("prefork (%s workers)") % workers
        mail_servers = self.env["ir.mail_server"].sudo().search_count([])
        return [
            {"label": _("TCSI module version"), "value": module.installed_version or module.latest_version or "n/a"},
            {"label": _("Odoo version"), "value": odoo.release.version},
            {"label": _("Server mode"), "value": server_mode},
            {"label": _("Database"), "value": self.env.cr.dbname},
            {"label": _("Outgoing email"), "value": _("configured (%s server(s))") % mail_servers if mail_servers else _("not configured — hand over passwords manually")},
            {"label": _("Platform user"), "value": self.env.user.login},
        ]

    # ---------------------------------------------------------------- main call

    @api.model
    def get_console_data(self):
        self._check_console_access()
        week_start = fields.Datetime.now() - timedelta(days=7)
        companies = self.env["res.company"].sudo().search([], order="name")
        rows = [self._company_row(company, week_start) for company in companies]
        rows.sort(key=lambda row: (STATUS_ORDER.get(row["status"], 3), row["name"]))
        trials = [row for row in rows if row["status"] == "trial"]
        ending = [
            row for row in trials if row["days_left"] is not None and row["days_left"] <= TRIAL_WARNING_DAYS
        ]
        users_total = sum(row["users"] for row in rows)
        users_week = sum(row["users_week"] for row in rows)
        users_never = sum(row["never_signed"] for row in rows)
        docs_total = sum(row["docs"] for row in rows)
        docs_week = sum(row["docs_week"] for row in rows)
        status_counts = {key: 0 for key in STATUS_ORDER}
        for row in rows:
            status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
        kpis = [
            {
                "key": "organizations",
                "label": _("Organisations"),
                "value": len(rows),
                "sub": _("%(trial)s trial · %(active)s active · %(suspended)s suspended")
                % {"trial": status_counts.get("trial", 0), "active": status_counts.get("active", 0), "suspended": status_counts.get("suspended", 0)},
            },
            {
                "key": "trials",
                "label": _("Trials running"),
                "value": len(trials),
                "sub": _("%s ending within 7 days") % len(ending) if ending else _("none ending this week"),
            },
            {
                "key": "users",
                "label": _("Active user accounts"),
                "value": users_total,
                "sub": _("%(week)s signed in this week · %(never)s never")
                % {"week": users_week, "never": users_never},
            },
            {
                "key": "documents",
                "label": _("Documents posted"),
                "value": docs_total,
                "sub": _("%s created this week") % docs_week,
            },
        ]
        alerts = self._alerts(rows)
        if self.env["ir.mail_server"].sudo().search_count([]) == 0:
            alerts.append(
                {
                    "level": "info",
                    "company_id": None,
                    "company": None,
                    "title": _("No outgoing email server"),
                    "detail": _("Trial passwords are handed over and rotated manually."),
                }
            )
        return {
            "generated_at": self._fmt(fields.Datetime.now()),
            "kpis": kpis,
            "trend": self._trend(),
            "alerts": alerts,
            "organizations": rows,
            "activity": self._activity(),
            "system": self._system(),
        }

    # ----------------------------------------------------------------- actions

    @api.model
    def extend_trial(self, company_id, days):
        self._check_console_access()
        days = int(days)
        if days < 1 or days > 120:
            raise UserError(_("Extend by between 1 and 120 days."))
        company = self._get_company(company_id)
        today = fields.Date.context_today(self)
        base = company.thirdcode_trial_end or today
        if base < today:
            base = today
        updates = {"thirdcode_trial_end": base + relativedelta(days=days)}
        if not company.thirdcode_trial_start:
            updates["thirdcode_trial_start"] = today
        if not company.thirdcode_platform_status:
            updates["thirdcode_platform_status"] = "trial"
        company.write(updates)
        return {
            "company": company.name,
            "trial_end": str(company.thirdcode_trial_end),
            "days_left": (company.thirdcode_trial_end - today).days,
        }

    @api.model
    def mark_trial(self, company_id, days=TRIAL_DEFAULT_DAYS):
        self._check_console_access()
        company = self._get_company(company_id)
        today = fields.Date.context_today(self)
        company.write(
            {
                "thirdcode_platform_status": "trial",
                "thirdcode_trial_mode": True,
                "thirdcode_trial_start": today,
                "thirdcode_trial_end": today + relativedelta(days=int(days)),
            }
        )
        return {"company": company.name, "trial_end": str(company.thirdcode_trial_end)}

    @api.model
    def convert_to_active(self, company_id):
        self._check_console_access()
        company = self._get_company(company_id)
        company.write({"thirdcode_platform_status": "active", "thirdcode_trial_mode": False})
        return {"company": company.name, "status": "active"}

    @api.model
    def suspend_company(self, company_id):
        self._check_console_access()
        company = self._get_company(company_id)
        users = (
            self.env["res.users"]
            .sudo()
            .with_context(active_test=False)
            .search([("share", "=", False), ("company_ids", "in", company.id), ("active", "=", True)])
        )
        protected = users.filtered(
            lambda user: user.has_group(SYSTEM_GROUP) or user.thirdcode_platform_owner
        )
        targets = users - protected
        company.write(
            {
                "thirdcode_platform_status": "suspended",
                "thirdcode_suspended_from_status": company.thirdcode_platform_status or "trial",
                "thirdcode_suspended_user_ids": json.dumps(targets.ids),
            }
        )
        targets.sudo().write({"active": False})
        return {"company": company.name, "deactivated": len(targets)}

    @api.model
    def resume_company(self, company_id):
        self._check_console_access()
        company = self._get_company(company_id)
        ids = json.loads(company.thirdcode_suspended_user_ids or "[]")
        users = (
            self.env["res.users"].sudo().with_context(active_test=False).browse([int(uid) for uid in ids])
        )
        users.filtered(lambda user: user.exists()).write({"active": True})
        restored = company.thirdcode_suspended_from_status or (
            "trial" if company.thirdcode_trial_mode else "active"
        )
        company.write(
            {
                "thirdcode_platform_status": restored,
                "thirdcode_suspended_from_status": False,
                "thirdcode_suspended_user_ids": False,
            }
        )
        return {"company": company.name, "restored": len(ids), "status": restored}

    @api.model
    def provision_baseline(self, company_id):
        self._check_console_access()
        company = self._get_company(company_id)
        result = (
            self.env["thirdcode.setup.service"]
            .sudo()
            ._action_ensure_baseline({"company_id": company.id})
        )
        return {"company": company.name, "steps": len(result.get("steps") or [])}

    @api.model
    def open_organization(self, company_id):
        self._check_console_access()
        company = self._get_company(company_id)
        return {
            "type": "ir.actions.act_window",
            "name": _("%s — documents") % company.name,
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("move_type", "in", ["out_invoice", "in_invoice", "entry"])],
            "context": {"allowed_company_ids": [company.id]},
        }

    @api.model
    def open_company_users(self, company_id):
        self._check_console_access()
        company = self._get_company(company_id)
        return {
            "type": "ir.actions.act_window",
            "name": _("%s — user accounts") % company.name,
            "res_model": "res.users",
            "view_mode": "list",
            "domain": [("share", "=", False), ("company_ids", "in", [company.id])],
            "context": {"create": False, "edit": False, "delete": False},
        }
