"""Bounded ORVEXA tools. Business records always use the requesting user's ORM."""
from datetime import timedelta
import math
import re

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

# Deterministic command registry. Every supported request maps to one of these
# tools with validated arguments; nothing else can run and nothing is inferred.
COMMANDS = (
    {"tool": "help", "usage": "/help", "example": "/help",
     "summary": "List every supported command with its parameters and an example."},
    {"tool": "read_everything", "usage": "/summary", "example": "/summary",
     "summary": "Read everything in your dashboard: cash, receivables, payables, invoices, bills, payments, entries, periods and activity memory."},
    {"tool": "overdue_invoices", "usage": "/overdue", "example": "/overdue",
     "summary": "List up to 20 posted customer invoices past their due date, from live records."},
    {"tool": "find_invoices", "usage": '/find "customer or reference"', "example": '/find "Acme"',
     "summary": "Search customer invoices by customer name or document reference."},
    {"tool": "draft_invoice", "usage": '/draft "Customer" 2 x "Product" at 100', "example": '/draft "Acme Corp" 2 x "Consulting" at 100',
     "summary": "Prepare one draft invoice preview for review; nothing is posted, sent or paid."},
    {"tool": "activity", "usage": "/activity", "example": "/activity",
     "summary": "Show recent authorized accounting activity and your saved task proposals."},
)

BOUNDARIES = (
    "ORVEXA is deterministic: it runs inside this deployment, uses only the commands "
    "listed here, and never guesses missing customers, products, amounts, dates or "
    "companies. It cannot access your computer or local files, cannot call external "
    "AI services, and cannot post, pay, send, delete or execute anything outside its "
    "registered, audited actions."
)


def _parse_slash(text):
    match = re.match(r"/([a-z]+)\s*(.*)$", text, re.I | re.S)
    if not match:
        return {"tool": "invalid", "message": "Type /help to list the supported commands, their parameters and examples."}
    name, rest = "/" + match[1].lower(), match[2].strip()
    if name == "/help":
        return {"tool": "help"} if not rest else {"tool": "invalid", "message": "Usage: /help takes no parameters."}
    if name == "/summary":
        return {"tool": "read_everything"} if not rest else {"tool": "invalid", "message": "Usage: /summary takes no parameters."}
    if name == "/overdue":
        return {"tool": "overdue_invoices"} if not rest else {"tool": "invalid", "message": "Usage: /overdue takes no parameters."}
    if name == "/activity":
        return {"tool": "activity"} if not rest else {"tool": "invalid", "message": "Usage: /activity takes no parameters."}
    if name == "/find":
        quoted = re.fullmatch(r'"([^"\n]{1,100})"', rest)
        if quoted:
            return {"tool": "find_invoices", "query": quoted[1]}
        if rest and '"' not in rest:
            return {"tool": "invalid", "message": 'Wrap the customer or reference in double quotes, e.g. /find "Acme".'}
        return {"tool": "invalid", "message": 'Usage: /find "customer or reference". Include a search phrase, e.g. /find "Acme".'}
    if name == "/draft":
        full = re.fullmatch(
            r'"([^"\n]{1,100})"\s+(\d+(?:\.\d{1,4})?)\s+x\s+"([^"\n]{1,100})"\s+at\s+(\d+(?:\.\d{1,4})?)',
            rest, re.I,
        )
        if full:
            return {"tool": "draft_invoice", "customer": full[1], "quantity": float(full[2]),
                    "product": full[3], "unit_price": float(full[4])}
        return {"tool": "invalid", "message": 'Usage: /draft "Customer" 2 x "Product" at 100. Provide the quoted customer, a quantity, the quoted product and a unit price.'}
    return {"tool": "invalid", "message": f'Unknown command "{name}". Type /help to list the supported commands.'}


def parse_command(message):
    """Local command mode, not an LLM; unsupported requests are never guessed.

    Slash commands and the earlier natural phrasing both map onto the same
    registry. Incomplete or unknown input returns an "invalid" tool with a
    precise validation message instead of triggering any action.
    """
    if not isinstance(message, str) or not 1 <= len(message.strip()) <= 2000:
        raise ValidationError("Enter a request between 1 and 2,000 characters.")
    text = message.strip()
    if text.startswith("/"):
        return _parse_slash(text)
    if re.fullmatch(r"(?:please )?(?:(?:show|list|find)(?: me)? )?(?:my |our |all )?(?:overdue|unpaid overdue|past due) (?:customer )?invoices[.!?]?", text, re.I):
        return {"tool": "overdue_invoices"}
    match = re.fullmatch(r'(?:find|search)(?: invoice)?\s+"([^"\n]{1,100})"', text, re.I)
    if match:
        return {"tool": "find_invoices", "query": match[1]}
    match = re.fullmatch(
        r'(?:create |prepare )?draft invoice for "([^"\n]{1,100})" with '
        r'(\d+(?:\.\d{1,4})?) x "([^"\n]{1,100})" at (\d+(?:\.\d{1,4})?)', text, re.I,
    )
    if match:
        return {"tool": "draft_invoice", "customer": match[1], "quantity": float(match[2]),
                "product": match[3], "unit_price": float(match[4])}
    if (
        re.search(r"\beverything\b", text, re.I)
        or re.fullmatch(
            r"(?:please )?(?:show|read|open|give)(?: me)? (?:the |my |our )?"
            r"(?:dashboard|workspace|overview)(?: overview)?[.!?]?", text, re.I
        )
        or re.fullmatch(
            r"(?:what(?:'s| is)) (?:inside|in|on) (?:my|the|our) (?:dashboard|workspace)[.!?]?",
            text, re.I,
        )
    ):
        return {"tool": "read_everything"}
    if re.fullmatch(r"(?:show |what is |what's )?(?:the )?(?:recent |latest )?(?:activity|activity feed|organization activity|organisation activity|task history)[.!?]?", text, re.I):
        return {"tool": "activity"}
    # Deterministic usage reminders for the common incomplete phrasings. These
    # never assume data or intent; they only point at the exact accepted form.
    if re.fullmatch(r"(?:find|search)(?: me)?(?: invoice| invoices)?[.!?]?", text, re.I) or re.fullmatch(
        r"(?:find|search)(?: me)?(?: invoice| invoices)?\s+[^\"\n]{1,100}", text, re.I
    ):
        return {"tool": "invalid", "message": 'Searches need the customer or reference in double quotes, e.g. find "Acme".'}
    if re.fullmatch(r"(?:create |prepare )?draft invoice.*", text, re.I):
        return {"tool": "invalid", "message": 'Draft invoices need the full detail: draft invoice for "Customer" with 2 x "Product" at 100.'}
    if re.fullmatch(r"(?:show |list |find |give )?(?:me )?(?:my |our |the )?overdue[.!?]?", text, re.I):
        return {"tool": "invalid", "message": "To list overdue invoices, send: show overdue invoices."}
    return {"tool": "help"}


class OrvexaProposal(models.Model):
    _name = "thirdcode.orvexa.proposal"
    _description = "ORVEXA confirmed task audit"
    # No public ACL: only the service below may create/update audit records.
    user_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    company_id = fields.Many2one("res.company", required=True, ondelete="restrict")
    payload = fields.Json(required=True)
    state = fields.Selection([("pending", "Pending"), ("done", "Done"), ("cancelled", "Cancelled")], required=True, default="pending")
    expires_at = fields.Datetime(required=True)
    result_id = fields.Many2one("account.move", ondelete="set null")


class OrvexaService(models.AbstractModel):
    _name = "thirdcode.orvexa"
    _description = "ORVEXA permission-checked task execution"

    def _scoped(self, company_id):
        if not self.env.user.has_group("base.group_user"):
            raise AccessError("ORVEXA requires an internal workspace account.")
        if type(company_id) is not int or company_id not in self.env.user.company_ids.ids:
            raise AccessError("You do not have access to this company.")
        return self.with_context(allowed_company_ids=[company_id]).with_company(self.env["res.company"].browse(company_id))

    def _invoice_rows(self, domain):
        moves = self.env["account.move"].search(
            [("company_id", "=", self.env.company.id), ("move_type", "=", "out_invoice")] + domain,
            limit=21, order="invoice_date_due asc, id desc",
        )
        as_of = fields.Datetime.to_string(fields.Datetime.now())
        overflow = len(moves) > 20
        message = "Live customer-invoice results from account.move records, scoped to your company and role (up to 20 shown"
        message += "; more matches exist — narrow your search)." if overflow else ")."
        return {"status": "complete", "message": f"{message} Snapshot: {as_of} UTC.",
                "as_of": as_of, "source": "account.move customer invoices (live records, role- and company-scoped)",
                "has_more": overflow, "records": [
                    {"id": move.id, "name": move.name, "customer": move.partner_id.display_name,
                     "due": str(move.invoice_date_due or ""), "amount_due": move.amount_residual,
                     "currency": move.currency_id.name, "state": move.state,
                     "url": f"/workspace/account.move/{move.id}"} for move in moves[:20]]}

    def _exact(self, model, name, domain):
        records = self.env[model].search(domain + [("name", "=", name)], limit=2)
        if len(records) != 1:
            raise UserError(f'Please provide one unique, existing {model.replace("res.partner", "customer").replace("product.product", "product")} name. "{name}" did not resolve uniquely.')
        return records

    def _reference_versions(self, partner, product, journal):
        # Product names/taxes live on the template, not only on the variant.
        return [{"updated": str(record.write_date), "name": record.display_name}
                for record in (partner, product, product.product_tmpl_id, journal)]

    @api.model
    def request_task(self, message, company_id):
        service = self._scoped(company_id)
        command = parse_command(message)
        tool = command["tool"]
        if tool == "invalid":
            return {"status": "invalid", "message": command["message"]}
        if tool == "help":
            return service.help()
        if tool == "activity":
            return service.memory(company_id)
        if tool == "overdue_invoices":
            return service._invoice_rows([("state", "=", "posted"), ("amount_residual", ">", 0),
                                          ("invoice_date_due", "<", fields.Date.context_today(service))])
        if command["tool"] == "find_invoices":
            return service._invoice_rows(["|", ("name", "ilike", command["query"]), ("partner_id.name", "ilike", command["query"])])
        if command["tool"] == "read_everything":
            return service.read_everything(company_id)
        if command["tool"] == "draft_invoice":
            return service._prepare_invoice(command)
        return service.help()

    def help(self):
        """Discoverable command help: usage, parameters and one example each."""
        return {
            "status": "help",
            "message": "Deterministic command help — every supported request is listed below. The earlier natural phrasing keeps working (for example: show overdue invoices).",
            "commands": [dict(command) for command in COMMANDS],
            "boundaries": BOUNDARIES,
        }

    def _prepare_invoice(self, command):
        self.env["account.move"].check_access("create")
        quantity, price = command["quantity"], command["unit_price"]
        if not all(math.isfinite(value) for value in (quantity, price)) or not 0 < quantity <= 1000000 or not 0 <= price <= 1000000000:
            raise ValidationError("Quantity must be greater than 0 and at most 1,000,000; unit price must be between 0 and 1,000,000,000.")
        company = self.env.company
        company_domain = ["|", ("company_id", "=", False), ("company_id", "=", company.id)]
        partner = self._exact("res.partner", command["customer"], company_domain)
        product = self._exact("product.product", command["product"], company_domain + [("sale_ok", "=", True)])
        journals = self.env["account.journal"].search([("company_id", "=", company.id), ("type", "=", "sale")], limit=2)
        if len(journals) != 1:
            raise UserError("ORVEXA needs one unambiguous sales journal. Use the invoice form when multiple journals are configured.")
        payload = {"partner_id": partner.id, "product_id": product.id, "journal_id": journals.id,
                   "quantity": quantity, "unit_price": price,
                   "revisions": self._reference_versions(partner, product, journals)}
        # Only assistant metadata is elevated; no accounting operation uses sudo.
        proposal = self.env["thirdcode.orvexa.proposal"].sudo().create({
            "user_id": self.env.uid, "company_id": company.id, "payload": payload,
            "expires_at": fields.Datetime.now() + timedelta(minutes=10),
        })
        return {"status": "confirmation_required", "proposal_id": proposal.id,
                "message": "Review before creating one draft invoice. Nothing has been saved to the ledger.",
                "review": {"company": company.display_name, "customer": partner.display_name,
                           "product": product.display_name, "quantity": quantity, "unit_price": price,
                           "currency": company.currency_id.name, "journal": journals.display_name,
                           "note": "Product taxes and customer payment terms apply. The final draft must be reviewed; it will not be posted or sent."}}

    @api.model
    def confirm_task(self, proposal_id, company_id, cancel=False):
        service = self._scoped(company_id)
        if type(proposal_id) is not int or type(cancel) is not bool:
            raise ValidationError("Invalid confirmation.")
        proposal = service.env["thirdcode.orvexa.proposal"].sudo().search([
            ("id", "=", proposal_id), ("user_id", "=", self.env.uid), ("company_id", "=", company_id)], limit=1)
        if not proposal:
            raise AccessError("This confirmation does not belong to your active workspace.")
        # Serialize retries. Creation and audit completion commit in one transaction.
        self.env.cr.execute("SELECT id FROM thirdcode_orvexa_proposal WHERE id = %s FOR UPDATE", [proposal.id])
        proposal.invalidate_recordset()
        if proposal.state == "done":
            move = service.env["account.move"].browse(proposal.result_id.id).exists()
            if not move:
                raise UserError("This task already completed, but its invoice was removed. It will not be created again.")
            move.check_access("read")
            return service._completed(move, already=True)
        if cancel:
            proposal.write({"state": "cancelled"})
            return {"status": "cancelled", "message": "Cancelled. No invoice was created."}
        if proposal.state != "pending" or proposal.expires_at < fields.Datetime.now():
            raise UserError("This proposal was cancelled or expired. Please request a new preview.")
        service.env["account.move"].check_access("create")
        data = proposal.payload
        records = [service.env[model].browse(data[key]).exists() for model, key in (
            ("res.partner", "partner_id"), ("product.product", "product_id"), ("account.journal", "journal_id"))]
        for record in records:
            if not record:
                raise UserError("A referenced record no longer exists. Request a new preview.")
            record.check_access("read")
        if service._reference_versions(*records) != data["revisions"]:
            raise UserError("Customer, product, or journal changed. Request a new preview.")
        partner, product, journal = records
        if journal.company_id.id != company_id or any(record.company_id and record.company_id.id != company_id for record in (partner, product)):
            raise AccessError("The proposal references a different company.")
        move = service.env["account.move"].create({
            "move_type": "out_invoice", "company_id": company_id, "currency_id": service.env.company.currency_id.id,
            "partner_id": partner.id, "journal_id": journal.id,
            "invoice_date": fields.Date.context_today(service),
            "invoice_payment_term_id": partner.property_payment_term_id.id,
            "invoice_line_ids": [(0, 0, {"product_id": product.id, "name": product.display_name,
                                       "quantity": data["quantity"], "price_unit": data["unit_price"]})],
        })
        proposal.write({"state": "done", "result_id": move.id})
        return service._completed(move)

    def _completed(self, move, already=False):
        if move.state == "draft":
            message = ("This task already completed; the draft invoice exists and was not created again."
                       if already else
                       "Draft invoice created. ORVEXA has not posted or sent it.")
        else:
            message = f"This task already completed. The invoice is now {move.state}."
        return {"status": "complete", "message": message,
                "record_id": move.id, "url": f"/workspace/account.move/{move.id}"}

    @api.model
    def read_everything(self, company_id):
        """Read the whole workspace dashboard for the requesting user.

        Mirrors the Finance overview data (cash, receivables, payables, net
        result) and adds invoices, bills, payments, entries, accounting
        periods and ORVEXA's own memory. Every query runs with the
        requesting user's ORM inside the selected company; sections a role
        may not read come back marked as restricted instead of failing the
        whole read.
        """
        service = self._scoped(company_id)
        return service._read_everything_sections()

    def _role_name(self, user):
        if user._is_admin() or user.has_group("thirdcode_accounting.group_thirdcode_administrator"):
            return "Administrator"
        if user.has_group("thirdcode_accounting.group_thirdcode_accountant"):
            return "Accountant"
        if user.has_group("thirdcode_accounting.group_thirdcode_encoder"):
            return "Encoder"
        return "Read-only"

    def _read_everything_sections(self):
        company = self.env.company
        user = self.env.user
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        currency = company.currency_id.name or company.currency_id.symbol or ""

        def money(value):
            symbol = company.currency_id.symbol or ""
            return f"{symbol}{value:,.2f} {currency}".strip()

        def lines_for(builder):
            try:
                return builder()
            except AccessError:
                return ["Your role cannot read this section, so it was skipped."]

        def line_balance(account_types, reconciled=None):
            domain = [
                ("company_id", "=", company.id),
                ("parent_state", "=", "posted"),
                ("account_id.account_type", "in", account_types),
            ]
            if reconciled is False:
                domain.append(("full_reconcile_id", "=", False))
            rows = self.env["account.move.line"].read_group(domain, ["balance:sum"], [])
            return float((rows[0] if rows else {}).get("balance", 0.0) or 0.0)

        def move_count(domain):
            return self.env["account.move"].search_count(
                [("company_id", "=", company.id)] + domain
            )

        def move_residual_sum(domain):
            rows = self.env["account.move"].read_group(
                [("company_id", "=", company.id)] + domain, ["amount_residual:sum"], []
            )
            return float((rows[0] if rows else {}).get("amount_residual", 0.0) or 0.0)

        def cash_and_banks():
            liquidity = line_balance(["asset_cash"])
            journals = self.env["account.journal"].search_count(
                [("company_id", "=", company.id), ("type", "in", ("bank", "cash"))]
            )
            return [
                f"Cash & bank balance: {money(liquidity)} across {journals} bank/cash journal(s)."
            ]

        def receivables_and_payables():
            receivable = line_balance(["asset_receivable"], reconciled=False)
            payable = line_balance(["liability_payable"], reconciled=False)
            return [
                f"Outstanding receivables: {money(receivable)}.",
                f"Outstanding payables: {money(payable)}.",
            ]

        def net_result():
            value = -line_balance(
                ["income", "income_other", "expense", "expense_depreciation", "expense_direct_cost"]
            )
            return [f"Net result (posted to date): {money(value)}."]

        def invoices():
            open_domain = [
                ("move_type", "in", ("out_invoice", "out_refund")),
                ("state", "=", "posted"),
                ("payment_state", "not in", ("paid", "reversed")),
            ]
            open_count = move_count(open_domain)
            overdue = move_count(
                open_domain + [("amount_residual", ">", 0), ("invoice_date_due", "<", today)]
            )
            drafts = move_count([("move_type", "=", "out_invoice"), ("state", "=", "draft")])
            return [
                f"Customer invoices: {drafts} draft(s), {open_count} posted with a balance of "
                f"{money(move_residual_sum(open_domain))}; {overdue} overdue."
            ]

        def bills():
            open_domain = [
                ("move_type", "in", ("in_invoice", "in_refund")),
                ("state", "=", "posted"),
                ("payment_state", "not in", ("paid", "reversed")),
            ]
            open_count = move_count(open_domain)
            overdue = move_count(
                open_domain + [("amount_residual", ">", 0), ("invoice_date_due", "<", today)]
            )
            drafts = move_count([("move_type", "=", "in_invoice"), ("state", "=", "draft")])
            return [
                f"Supplier bills: {drafts} draft(s), {open_count} posted with a balance of "
                f"{money(move_residual_sum(open_domain))}; {overdue} overdue."
            ]

        def payments():
            domain = [
                ("company_id", "=", company.id),
                ("state", "in", ("in_process", "paid")),
                ("date", ">=", month_start),
            ]
            count = self.env["account.payment"].search_count(domain)
            rows = self.env["account.payment"].read_group(domain, ["amount:sum"], [])
            total = float((rows[0] if rows else {}).get("amount", 0.0) or 0.0)
            return [f"Payments this month: {count} worth {money(total)}."]

        def entries():
            drafts = move_count([("state", "=", "draft")])
            posted_month = move_count([("state", "=", "posted"), ("date", ">=", month_start)])
            return [
                f"Entries: {drafts} draft(s) awaiting work; {posted_month} posted this month."
            ]

        def periods():
            model = self.env["thirdcode.accounting.period"]
            open_count = model.search_count(
                [("company_id", "=", company.id), ("state", "=", "open")]
            )
            closed_count = model.search_count(
                [("company_id", "=", company.id), ("state", "=", "closed")]
            )
            current = model.search(
                [("company_id", "=", company.id), ("state", "=", "open")],
                order="date_start desc, id desc",
                limit=2,
            )
            names = ", ".join(f"{p.name} ({p.date_start} – {p.date_end})" for p in current) or "none yet"
            return [
                f"Accounting periods: {open_count} open, {closed_count} closed. "
                f"Current open: {names}."
            ]

        def memory_lines():
            snapshot = self.memory(company.id)
            events = snapshot.get("events", [])
            tasks = snapshot.get("tasks", [])
            lines = [
                f"Activity memory: {len(events)} recent record event(s) visible to your role; "
                f"{len(tasks)} saved task proposal(s)."
            ]
            for event in events[:3]:
                lines.append(
                    f"· {event['name']} {event['event']} by {event['by']} at {event['at']} UTC"
                )
            for task in tasks[:3]:
                lines.append(f"· Task #{task['id']}: {task['state']} at {task['at']} UTC")
            return lines

        sections = [
            {
                "title": "Workspace",
                "lines": lines_for(lambda: [
                    f"{company.name} · reader: {user.name} ({self._role_name(user)}) · currency {currency}.",
                    "Everything below is scoped to your role and this company.",
                ]),
            },
            {"title": "Cash & bank", "lines": lines_for(cash_and_banks)},
            {"title": "Receivables & payables", "lines": lines_for(receivables_and_payables)},
            {"title": "Net result", "lines": lines_for(net_result)},
            {"title": "Customer invoices", "lines": lines_for(invoices)},
            {"title": "Supplier bills", "lines": lines_for(bills)},
            {"title": "Payments", "lines": lines_for(payments)},
            {"title": "Entries", "lines": lines_for(entries)},
            {"title": "Accounting periods", "lines": lines_for(periods)},
            {"title": "Memory", "lines": lines_for(memory_lines)},
        ]

        def recent_links():
            moves = self.env["account.move"].search(
                [("company_id", "=", company.id), ("state", "!=", "cancel")],
                order="write_date desc, id desc",
                limit=5,
            )
            return [
                {"name": move.display_name, "url": f"/workspace/account.move/{move.id}"}
                for move in moves
            ]

        try:
            links = recent_links()
        except AccessError:
            links = []
        now = fields.Datetime.to_string(fields.Datetime.now())
        return {
            "status": "complete",
            "message": (
                f"Full read of {company.name} complete — everything your role can see, "
                f"as of {now} UTC."
            ),
            "as_of": now,
            "source": "live workspace records (account.move, account.payment, periods) plus ORVEXA activity memory; role- and company-scoped",
            "sections": sections,
            "links": links,
        }

    @api.model
    def memory(self, company_id):
        service = self._scoped(company_id)
        events = service.env["thirdcode.orvexa.event"].sudo().search([
            ("company_id", "=", company_id)], order="id desc", limit=60)
        visible = []
        for event in events:
            move = service.env["account.move"].browse(event.move_id.id).exists()
            if not move:
                continue
            try:
                move.check_access("read")
            except AccessError:
                continue
            visible.append({"id": event.id, "name": move.display_name, "event": event.kind,
                            "at": fields.Datetime.to_string(event.create_date), "by": event.user_id.name,
                            "url": f"/workspace/account.move/{move.id}"})
            if len(visible) == 20:
                break
        proposals = service.env["thirdcode.orvexa.proposal"].sudo().search([
            ("user_id", "=", self.env.uid), ("company_id", "=", company_id)], order="id desc", limit=20)
        return {"status": "complete", "message": "Latest authorized accounting activity and your task history.",
                "as_of": fields.Datetime.to_string(fields.Datetime.now()), "events": visible,
                "source": "account.move audit events recorded since ORVEXA tracking was enabled, re-checked against your current role; task proposals owned by your account",
                "tasks": [{"id": row.id, "state": "expired" if row.state == "pending" and row.expires_at < fields.Datetime.now() else row.state,
                           "at": fields.Datetime.to_string(row.create_date)} for row in proposals],
                "scope": "Invoices, bills and journal entries recorded since ORVEXA activity tracking was enabled. Only records your current role may read are shown."}


class OrvexaEvent(models.Model):
    _name = "thirdcode.orvexa.event"
    _description = "ORVEXA accounting activity memory"
    move_id = fields.Many2one("account.move", ondelete="set null", index=True)
    user_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    company_id = fields.Many2one("res.company", required=True, ondelete="restrict", index=True)
    kind = fields.Selection([("created", "Created"), ("updated", "Updated")], required=True)


class OrvexaAccountingActivity(models.Model):
    _inherit = "account.move"

    def _orvexa_track(self, kind):
        self.env["thirdcode.orvexa.event"].sudo().create([
            {"move_id": move.id, "user_id": self.env.uid, "company_id": move.company_id.id, "kind": kind} for move in self])
        for company in self.company_id:
            # Invalidation only, no business values in notifications. Read permissions
            # are rechecked when a recipient asks for current activity.
            users = self.env["res.users"].sudo().search([("company_ids", "in", company.id), ("share", "=", False)])
            for partner in users.partner_id:
                self.env["bus.bus"]._sendone(partner, "tcsi.orvexa.activity", {"company_id": company.id})

    @api.model_create_multi
    def create(self, values_list):
        moves = super().create(values_list)
        moves._orvexa_track("created")
        return moves

    def write(self, values):
        result = super().write(values)
        tracked = {"state", "payment_state", "partner_id", "invoice_line_ids", "line_ids", "invoice_date", "invoice_date_due", "amount_residual"}
        if tracked.intersection(values):
            self._orvexa_track("updated")
        return result
