from odoo import _, api, models
from odoo.exceptions import AccessError


class WorkflowGuardMixin(models.AbstractModel):
    """Keep workflow state and approval metadata behind checked actions."""

    _name = "thirdcode.workflow.guard.mixin"
    _description = "Third Code guarded workflow fields"

    _workflow_state_field = None
    _workflow_initial_state = None
    _workflow_protected_fields = frozenset()

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            for vals in vals_list:
                if self._workflow_state_field:
                    state = vals.get(
                        self._workflow_state_field, self._workflow_initial_state
                    )
                    if state not in (None, self._workflow_initial_state):
                        raise AccessError(
                            _("Workflow records must start in their initial state.")
                        )
                metadata_fields = self._workflow_protected_fields - {
                    self._workflow_state_field
                }
                if any(vals.get(field) for field in metadata_fields):
                    raise AccessError(
                        _("Workflow metadata can only be set by an authorized action.")
                    )
        return super().create(vals_list)

    def write(self, vals):
        protected = self._workflow_protected_fields.intersection(vals)
        if protected and not self.env.su:
            raise AccessError(
                _("Workflow state and approval metadata can only be changed by an authorized action.")
            )
        return super().write(vals)
