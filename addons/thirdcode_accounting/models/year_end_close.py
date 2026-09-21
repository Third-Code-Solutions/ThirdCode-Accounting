from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class YearEndClose(models.Model):
    _name = "thirdcode.year.end.close"
    _description = "Third Code Year-end Retained Earnings Close"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_end desc, id desc"

    name = fields.Char(required=True, copy=False, default="New", tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    date_end = fields.Date(required=True, tracking=True)
    journal_id = fields.Many2one(
        "account.journal",
        required=True,
        domain="[(\"company_id\", \"=\", company_id), (\"type\", \"=\", \"general\")]",
    )
    retained_earnings_account_id = fields.Many2one(
        "account.account",
        required=True,
        domain="[(\"company_ids\", \"in\", [company_id]), (\"account_type\", \"=\", \"equity\")]",
    )
    state = fields.Selection(
        [("draft", "Draft"), ("posted", "Posted"), ("cancelled", "Cancelled")],
        default="draft",
        required=True,
        tracking=True,
    )
    move_id = fields.Many2one("account.move", readonly=True, copy=False)
    profit_loss = fields.Monetary(compute="_compute_profit_loss", currency_field="currency_id")
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    line_count = fields.Integer(compute="_compute_profit_loss")
    notes = fields.Text(copy=False)

    _sql_constraints = [
        (
            "thirdcode_year_end_company_date_unique",
            "unique(company_id, date_end)",
            "Only one year-end retained-earnings close may exist for a company and date.",
        )
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = f"YEAR-END/{vals.get('date_end', fields.Date.today())}"
        return super().create(vals_list)

    @api.constrains("journal_id", "retained_earnings_account_id", "company_id")
    def _check_configuration(self):
        for close in self:
            if close.journal_id and close.journal_id.company_id != close.company_id:
                raise ValidationError(_("The year-end journal must belong to the selected company."))
            if close.retained_earnings_account_id and close.company_id not in close.retained_earnings_account_id.company_ids:
                raise ValidationError(_("The retained-earnings account must belong to the selected company."))
            if close.retained_earnings_account_id and close.retained_earnings_account_id.account_type != "equity":
                raise ValidationError(_("The retained-earnings account must be an equity account."))

    def _check_thirdcode_access(self):
        if not (
            self.env.user.has_group("thirdcode_accounting.group_thirdcode_accountant")
            or self.env.user.has_group("thirdcode_accounting.group_thirdcode_administrator")
        ):
            raise AccessError(_("Only an Accountant or Administrator may prepare a year-end close."))

    def _profit_and_loss_lines(self):
        self.ensure_one()
        lines = self.env["account.move.line"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("parent_state", "=", "posted"),
                ("date", "<=", self.date_end),
                ("account_id.internal_group", "in", ["income", "expense"]),
            ]
        )
        totals = {}
        for line in lines:
            totals[line.account_id] = totals.get(line.account_id, 0.0) + line.balance
        return [(account, balance) for account, balance in totals.items() if abs(balance) > 0.000001]

    @api.depends("date_end", "company_id")
    def _compute_profit_loss(self):
        for close in self:
            if not close.date_end or not close.company_id:
                close.profit_loss = 0.0
                close.line_count = 0
                continue
            lines = close._profit_and_loss_lines()
            close.profit_loss = -sum(balance for _account, balance in lines)
            close.line_count = len(lines)

    def action_prepare(self):
        self._check_thirdcode_access()
        for close in self:
            if close.state != "draft":
                continue
            if not close._profit_and_loss_lines():
                raise UserError(_("There is no posted income or expense balance to close."))
        return True

    def action_post(self):
        self._check_thirdcode_access()
        self._lock_for_posting()
        for close in self:
            if close.state != "draft":
                continue
            close.action_prepare()
            line_values = []
            net_balance = 0.0
            for account, balance in close._profit_and_loss_lines():
                net_balance += balance
                line_values.append(
                    [
                        0,
                        0,
                        {
                            "name": f"Year-end close {close.date_end}",
                            "account_id": account.id,
                            "debit": -balance if balance < 0 else 0.0,
                            "credit": balance if balance > 0 else 0.0,
                        },
                    ]
                )
            line_values.append(
                [
                    0,
                    0,
                    {
                        "name": f"Retained earnings transfer {close.date_end}",
                        "account_id": close.retained_earnings_account_id.id,
                        "debit": net_balance if net_balance > 0 else 0.0,
                        "credit": -net_balance if net_balance < 0 else 0.0,
                    },
                ]
            )
            move = self.env["account.move"].create(
                {
                    "company_id": close.company_id.id,
                    "journal_id": close.journal_id.id,
                    "date": close.date_end,
                    "move_type": "entry",
                    "ref": close.name,
                    "line_ids": line_values,
                }
            )
            move.action_post()
            close.write({"move_id": move.id, "state": "posted"})
        return True

    def _lock_for_posting(self):
        """Serialize a close record before creating its native journal entry."""
        if not self.ids:
            return
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT id FROM thirdcode_year_end_close WHERE id IN %s FOR UPDATE",
            [tuple(self.ids)],
        )
        self.invalidate_recordset()

    def action_cancel(self):
        self._check_thirdcode_access()
        self.filtered(lambda close: close.state == "draft").write({"state": "cancelled"})
        return True
