from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    thirdcode_numbering_policy = fields.Selection(
        [
            ("unverified", "Unverified"),
            ("review_required", "Review required"),
            ("no_gap_validated", "No observed gap at validation"),
        ],
        string="Third Code numbering policy",
        default="unverified",
        required=True,
        copy=False,
    )
    thirdcode_numbering_owner = fields.Char(copy=False)
    thirdcode_numbering_checked_at = fields.Datetime(readonly=True, copy=False)
    thirdcode_numbering_notes = fields.Text(copy=False)

    def action_validate_thirdcode_numbering(self):
        if not (
            self.env.user.has_group("thirdcode_accounting.group_thirdcode_accountant")
            or self.env.user.has_group("thirdcode_accounting.group_thirdcode_administrator")
        ):
            raise AccessError(_("Only an Accountant or Administrator may validate numbering controls."))
        for journal in self:
            if journal.has_sequence_holes:
                journal.thirdcode_numbering_policy = "review_required"
                raise UserError(
                    _(
                        "Journal %(journal)s has observed sequence irregularities. Review cancelled, deleted, or draft-numbered documents before validation.",
                        journal=journal.display_name,
                    )
                )
            if not journal.thirdcode_numbering_owner:
                raise UserError(_("Record a numbering-control owner before validation."))
            journal.write(
                {
                    "thirdcode_numbering_policy": "no_gap_validated",
                    "thirdcode_numbering_checked_at": fields.Datetime.now(),
                }
            )
        return True
