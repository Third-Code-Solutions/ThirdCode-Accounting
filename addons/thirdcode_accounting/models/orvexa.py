"""Bounded ORVEXA tools. Business records always use the requesting user's ORM."""
from datetime import timedelta
import math
import re

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


def parse_command(message):
    """Local command mode, not an LLM; unsupported requests are never guessed."""
    if not isinstance(message, str) or not 1 <= len(message.strip()) <= 2000:
        raise ValidationError("Enter a request between 1 and 2,000 characters.")
    text = message.strip()
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
        return {"status": "complete", "message": "Live invoice results (up to 20).",
                "has_more": len(moves) > 20, "records": [
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
        if re.fullmatch(r"(?:show |what is |what's )?(?:the )?(?:recent |latest )?(?:activity|activity feed|organization activity|organisation activity|task history)[.!?]?", message.strip(), re.I):
            return service.memory(company_id)
        if command["tool"] == "overdue_invoices":
            return service._invoice_rows([("state", "=", "posted"), ("amount_residual", ">", 0),
                                          ("invoice_date_due", "<", fields.Date.context_today(service))])
        if command["tool"] == "find_invoices":
            return service._invoice_rows(["|", ("name", "ilike", command["query"]), ("partner_id.name", "ilike", command["query"])])
        if command["tool"] == "draft_invoice":
            return service._prepare_invoice(command)
        return {"status": "help", "message": 'I can find invoices, list overdue invoices, or prepare one draft invoice with an explicit customer, product, quantity and unit price. Try: show overdue invoices; find "customer or reference"; or draft invoice for "Customer" with 2 x "Product" at 100. I cannot post, send, pay, delete, or run unsupported tasks.'}

    def _prepare_invoice(self, command):
        self.env["account.move"].check_access("create")
        quantity, price = command["quantity"], command["unit_price"]
        if not all(math.isfinite(value) for value in (quantity, price)) or not 0 < quantity <= 1000000 or not 0 <= price <= 1000000000:
            raise ValidationError("Quantity or unit price is outside the supported range.")
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
            return service._completed(move)
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

    def _completed(self, move):
        message = "Draft invoice created. ORVEXA has not posted or sent it." if move.state == "draft" else f"This task already completed. The invoice is now {move.state}."
        return {"status": "complete", "message": message,
                "record_id": move.id, "url": f"/workspace/account.move/{move.id}"}

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
