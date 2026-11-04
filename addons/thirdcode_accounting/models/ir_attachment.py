"""Tenant boundary for stored files served by ``/web/content`` and ``/web/image``.

Audit finding F1 (live production, 2026-10): the stock
``ir.attachment.validate_access`` gate serves any non-public attachment to
anonymous visitors, and a logged-in user of one organization could download
files of another organization byte for byte through both the engine and the
portal origin. The override below keeps the stock token and portal behaviour
and adds the missing tenant checks:

* anonymous visitors may only read attachments flagged ``public``;
* internal users may only read attachments within their companies, and when
  the attachment is linked to a business record that record must itself be
  readable by the requesting user.

Denials raise ``UserError``, which the binary download routes turn into a 404
(or image placeholder), so the endpoints never reveal whether a file exists.
"""

from odoo import _, models
from odoo.exceptions import AccessError, UserError

_PLATFORM_GROUPS = (
    "base.group_system",
    "thirdcode_accounting.group_thirdcode_platform_console",
)


def _raise_file_not_found():
    raise UserError(_("The requested file is not available."))


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def validate_access(self, *args, **kwargs):
        # The signature is pass-through on purpose: the adjacent Odoo build
        # varies between ``(access_token)`` and ``(access_token, field)``.
        attachment = super().validate_access(*args, **kwargs)
        access_token = args[0] if args else kwargs.get("access_token")
        if access_token or self.env.su:
            return attachment
        user = self.env.user
        if any(user.has_group(xmlid) for xmlid in _PLATFORM_GROUPS):
            return attachment
        managed = attachment.sudo()
        for record in managed:
            if user._is_public():
                if record.public:
                    continue
                _raise_file_not_found()
            if user._is_portal():
                # Stock behaviour: portal members read through the linked
                # record check performed by the native implementation.
                continue
            companies = set(record.company_id.ids)
            if record.res_model and record.res_id:
                try:
                    target_model = self.env[record.res_model]
                except KeyError:
                    target_model = None
                target = (
                    target_model.browse(record.res_id).exists()
                    if target_model is not None
                    else None
                )
                if target:
                    if "company_id" in target._fields:
                        companies.update(target.company_id.ids)
                    try:
                        target.check_access("read")
                    except (AccessError, UserError):
                        _raise_file_not_found()
            if companies and not (companies & set(user.company_ids.ids)):
                _raise_file_not_found()
        return attachment
