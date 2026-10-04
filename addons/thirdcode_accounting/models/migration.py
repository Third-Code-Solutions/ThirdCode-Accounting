import hashlib
import json

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class AccountAccountMigrationReference(models.Model):
    _inherit = "account.account"

    thirdcode_source_identifier = fields.Char(
        string="Migration source identifier", index=True, copy=False
    )


class ResPartnerMigrationReference(models.Model):
    _inherit = "res.partner"

    thirdcode_source_identifier = fields.Char(
        string="Migration source identifier", index=True, copy=False
    )


class AccountTaxMigrationReference(models.Model):
    _inherit = "account.tax"

    thirdcode_source_identifier = fields.Char(
        string="Migration source identifier", index=True, copy=False
    )


class MigrationBatch(models.Model):
    _name = "thirdcode.migration.batch"
    _description = "Third Code Migration Batch"
    _inherit = ["mail.thread", "mail.activity.mixin", "thirdcode.workflow.guard.mixin"]
    _order = "create_date desc, id desc"
    _workflow_state_field = "state"
    _workflow_initial_state = "draft"
    _workflow_protected_fields = frozenset(
        {
            "state",
            "validated_by",
            "validated_at",
            "loaded_by",
            "loaded_at",
            "reconciled_by",
            "reconciled_at",
        }
    )

    name = fields.Char(required=True, copy=False, default="New", tracking=True)
    source_system = fields.Selection(
        [("myob", "MYOB"), ("csv", "CSV fixture"), ("archive", "Archive manifest")],
        required=True,
        default="myob",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    cutover_date = fields.Date(copy=False)
    retention_policy = fields.Selection(
        related="company_id.thirdcode_live_history_policy", readonly=False
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("validated", "Validated"),
            ("loaded", "Loaded"),
            ("reconciled", "Reconciled"),
            ("rejected", "Rejected"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    source_file_hash = fields.Char(copy=False)
    source_file_name = fields.Char(copy=False)
    validated_by = fields.Many2one("res.users", readonly=True, copy=False)
    validated_at = fields.Datetime(readonly=True, copy=False)
    loaded_by = fields.Many2one("res.users", readonly=True, copy=False)
    loaded_at = fields.Datetime(readonly=True, copy=False)
    reconciled_by = fields.Many2one("res.users", readonly=True, copy=False)
    reconciled_at = fields.Datetime(readonly=True, copy=False)
    owner_id = fields.Many2one("res.users", default=lambda self: self.env.user, copy=False)
    opening_balance_owner = fields.Char(copy=False)
    notes = fields.Text(copy=False)
    row_ids = fields.One2many("thirdcode.migration.row", "batch_id")
    row_count = fields.Integer(compute="_compute_counts", store=True)
    error_count = fields.Integer(compute="_compute_counts", store=True)
    matched_count = fields.Integer(compute="_compute_counts", store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("thirdcode.migration.batch") or "New"
        return super().create(vals_list)

    @api.depends("row_ids", "row_ids.state")
    def _compute_counts(self):
        for batch in self:
            batch.row_count = len(batch.row_ids)
            batch.error_count = len(batch.row_ids.filtered(lambda row: row.state == "error"))
            batch.matched_count = len(batch.row_ids.filtered(lambda row: row.state == "matched"))

    def _check_migration_access(self):
        if not (
            self.env.user.has_group("thirdcode_accounting.group_thirdcode_accountant")
            or self.env.user.has_group("thirdcode_accounting.group_thirdcode_administrator")
        ):
            raise AccessError(_("Only an Accountant or Administrator may manage migration batches."))
        self.check_access("write")

    def action_validate(self):
        self._check_migration_access()
        for batch in self:
            if batch.state != "draft":
                raise UserError(_("Only a draft migration batch may be validated."))
            if not batch.row_ids:
                raise UserError(_("A migration batch must contain validation rows."))
            batch.row_ids._refresh_reconciliation_state()
            if batch.error_count or batch.row_ids.filtered(lambda row: row.state == "pending"):
                raise UserError(_("Resolve migration validation errors before loading."))
            batch.sudo().write(
                {
                    "state": "validated",
                    "validated_by": self.env.user.id,
                    "validated_at": fields.Datetime.now(),
                }
            )
        return True

    def action_mark_loaded(self):
        self._check_migration_access()
        self.ensure_one()
        if self.state != "validated":
            raise UserError(_("Only a validated migration batch may be marked loaded."))
        self.sudo().write(
            {
                "state": "loaded",
                "loaded_by": self.env.user.id,
                "loaded_at": fields.Datetime.now(),
            }
        )
        return True

    def action_mark_reconciled(self):
        self._check_migration_access()
        self.ensure_one()
        if self.state != "loaded" or self.error_count or self.matched_count != self.row_count:
            raise UserError(_("Every loaded migration row must match before reconciliation sign-off."))
        self.sudo().write(
            {
                "state": "reconciled",
                "reconciled_by": self.env.user.id,
                "reconciled_at": fields.Datetime.now(),
            }
        )
        return True

    def write(self, vals):
        immutable_fields = {
            "source_system",
            "company_id",
            "cutover_date",
            "source_file_hash",
            "source_file_name",
            "opening_balance_owner",
            "row_ids",
        }
        if not self.env.su and immutable_fields.intersection(vals) and any(
            batch.state in ("validated", "loaded", "reconciled") for batch in self
        ):
            raise UserError(_("Validated migration batches cannot be changed."))
        return super().write(vals)


class MigrationRow(models.Model):
    _name = "thirdcode.migration.row"
    _inherit = "thirdcode.workflow.guard.mixin"
    _description = "Third Code Migration Reconciliation Row"
    _order = "source_identifier, id"
    _workflow_state_field = "state"
    _workflow_initial_state = "pending"
    _workflow_protected_fields = frozenset({"state", "error_message"})

    batch_id = fields.Many2one("thirdcode.migration.batch", required=True, ondelete="cascade")
    source_identifier = fields.Char(required=True, index=True)
    target_model = fields.Selection(
        [
            ("account.move", "Journal entry"),
            ("res.partner", "Partner"),
            ("account.account", "Account"),
            ("account.tax", "Tax"),
            ("opening_balance", "Opening balance"),
        ],
        required=True,
    )
    target_id = fields.Integer()
    source_debit = fields.Monetary(currency_field="currency_id")
    source_credit = fields.Monetary(currency_field="currency_id")
    target_debit = fields.Monetary(currency_field="currency_id")
    target_credit = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(related="batch_id.company_id.currency_id", store=True)
    state = fields.Selection(
        [("pending", "Pending"), ("matched", "Matched"), ("error", "Error")],
        default="pending",
        required=True,
    )
    error_message = fields.Text()

    _sql_constraints = [
        (
            "thirdcode_migration_source_unique",
            "unique(batch_id, source_identifier)",
            "A source identifier may appear only once in a migration batch.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        batch_ids = {vals.get("batch_id") for vals in vals_list if vals.get("batch_id")}
        batches = self.env["thirdcode.migration.batch"].browse(list(batch_ids))
        if any(batch.state in ("validated", "loaded", "reconciled") for batch in batches):
            raise UserError(_("Rows cannot be added to a validated migration batch."))
        rows = super().create(vals_list)
        rows._refresh_reconciliation_state()
        return rows

    def write(self, vals):
        immutable_fields = {
            "batch_id",
            "source_identifier",
            "target_model",
            "target_id",
            "source_debit",
            "source_credit",
            "target_debit",
            "target_credit",
        }
        if not self.env.su and immutable_fields.intersection(vals) and any(
            row.batch_id.state in ("validated", "loaded", "reconciled") for row in self
        ):
            raise UserError(_("Validated migration rows cannot be changed."))
        result = super().write(vals)
        if {"source_debit", "source_credit", "target_debit", "target_credit"} & set(vals):
            self._refresh_reconciliation_state()
        return result

    def _refresh_reconciliation_state(self):
        for row in self:
            source = (row.source_debit, row.source_credit)
            target = (row.target_debit, row.target_credit)
            if source == target:
                values = {"state": "matched", "error_message": False}
            elif row.target_debit or row.target_credit:
                values = {
                    "state": "error",
                    "error_message": "Source and target debit/credit totals do not match.",
                }
            else:
                values = {"state": "pending", "error_message": False}
            if row.id:
                row.sudo().write(values)
            else:
                row.state = values["state"]
                row.error_message = values["error_message"]

    @api.onchange("source_debit", "source_credit", "target_debit", "target_credit")
    def _onchange_reconciliation(self):
        self._refresh_reconciliation_state()

    def unlink(self):
        if not self.env.su and any(
            row.batch_id.state in ("validated", "loaded", "reconciled") for row in self
        ):
            raise UserError(_("Rows cannot be removed from a validated migration batch."))
        return super().unlink()


class AccountMoveImport(models.Model):
    _inherit = "account.move"

    thirdcode_import_fingerprint = fields.Char(readonly=True, copy=False, index=True)

    @api.model
    def action_import_thirdcode_move(self, values):
        """One RPC transaction: compare payload, create, map, and post or roll back.

        A retry after loss of the response finds the same posted fingerprint.
        Historical identifiers with no fingerprint require manual reconciliation.
        """
        if not self.env.user.has_group("thirdcode_accounting.group_thirdcode_administrator"):
            raise AccessError(_("Only an Administrator may run accounting imports."))
        allowed = {"company_id", "journal_id", "date", "move_type", "ref",
                   "thirdcode_source_identifier", "thirdcode_is_opening_balance", "line_ids",
                   "partner_id", "invoice_date", "invoice_date_due", "invoice_line_ids",
                   "thirdcode_import_control_account_id"}
        if not isinstance(values, dict) or set(values) - allowed:
            raise UserError(_("Unsupported accounting import fields."))
        company = self.env["res.company"].browse(values.get("company_id"))
        source = values.get("thirdcode_source_identifier")
        if company not in self.env.companies or not source:
            raise AccessError(_("An active company and source identifier are required."))
        for field in ("line_ids", "invoice_line_ids"):
            for command in values.get(field, []):
                if len(command) != 3 or command[0] != 0:
                    raise UserError(_("Imports may create new lines only."))
        fingerprint = hashlib.sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        existing = self.search([("company_id", "=", company.id), ("thirdcode_source_identifier", "=", source)], limit=1)
        if existing:
            if existing.thirdcode_import_fingerprint != fingerprint or existing.state != "posted":
                raise UserError(_("The source identifier exists with different or unverified accounting content. Reconcile it before retrying."))
            return {"id": existing.id, "created": False}
        payload = dict(values)
        control_id = payload.pop("thirdcode_import_control_account_id", False)
        payload["thirdcode_import_fingerprint"] = fingerprint
        move = self.with_company(company).create(payload)
        if control_id:
            account = self.env["account.account"].browse(control_id)
            expected = "asset_receivable" if move.move_type == "out_invoice" else "liability_payable"
            if account.account_type != expected or company not in account.company_ids:
                raise UserError(_("The approved open-item control account must match the company and document type."))
            move.line_ids.filtered(lambda line: line.display_type == "payment_term").write({"account_id": account.id})
        move.action_post()
        return {"id": move.id, "created": True}
