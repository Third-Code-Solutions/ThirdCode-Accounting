from odoo import _, api, fields, models
from odoo.exceptions import UserError


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
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

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

    def action_validate(self):
        for batch in self:
            if not batch.row_ids:
                raise UserError(_("A migration batch must contain validation rows."))
            batch.row_ids._refresh_reconciliation_state()
            if batch.error_count or batch.row_ids.filtered(lambda row: row.state == "pending"):
                batch.state = "rejected"
                raise UserError(_("Resolve migration validation errors before loading."))
            batch.write(
                {
                    "state": "validated",
                    "validated_by": self.env.user.id,
                    "validated_at": fields.Datetime.now(),
                }
            )
        return True

    def action_mark_loaded(self):
        self.ensure_one()
        if self.state != "validated":
            raise UserError(_("Only a validated migration batch may be marked loaded."))
        self.write(
            {
                "state": "loaded",
                "loaded_by": self.env.user.id,
                "loaded_at": fields.Datetime.now(),
            }
        )
        return True

    def action_mark_reconciled(self):
        self.ensure_one()
        if self.state != "loaded" or self.error_count or self.matched_count != self.row_count:
            raise UserError(_("Every loaded migration row must match before reconciliation sign-off."))
        self.write(
            {
                "state": "reconciled",
                "reconciled_by": self.env.user.id,
                "reconciled_at": fields.Datetime.now(),
            }
        )
        return True


class MigrationRow(models.Model):
    _name = "thirdcode.migration.row"
    _description = "Third Code Migration Reconciliation Row"
    _order = "source_identifier, id"

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
        rows = super().create(vals_list)
        rows._refresh_reconciliation_state()
        return rows

    def write(self, vals):
        result = super().write(vals)
        if {"source_debit", "source_credit", "target_debit", "target_credit"} & set(vals):
            self._refresh_reconciliation_state()
        return result

    def _refresh_reconciliation_state(self):
        for row in self:
            source = (row.source_debit, row.source_credit)
            target = (row.target_debit, row.target_credit)
            if source == target:
                row.state = "matched"
                row.error_message = False
            elif row.target_debit or row.target_credit:
                row.state = "error"
                row.error_message = "Source and target debit/credit totals do not match."
            else:
                row.state = "pending"
                row.error_message = False

    @api.onchange("source_debit", "source_credit", "target_debit", "target_credit")
    def _onchange_reconciliation(self):
        self._refresh_reconciliation_state()
