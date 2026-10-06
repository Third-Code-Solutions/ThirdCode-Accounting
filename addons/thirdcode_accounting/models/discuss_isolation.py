"""Company boundaries for Discuss, including native elevated mail paths.

Company membership is an additional boundary, never a replacement for native
private-channel membership checks. Only uid=1 is the trusted migration operator.
"""
from odoo import SUPERUSER_ID, Command, _, api, fields, models
from odoo.addons.mail.tools.discuss import Store
from odoo.exceptions import AccessError, UserError
from odoo.osv import expression

from .platform_access import is_platform_owner, require_platform_owner

STAFF_GROUP = "thirdcode_accounting.group_thirdcode_platform_support"
READY = "thirdcode.discuss_isolation_ready"
SCOPE_FIELDS = {"thirdcode_company_id", "thirdcode_quarantined", "thirdcode_general_company_id"}


def scoped_companies(env, company_ids):
    user = env.user.sudo()
    if not env.uid or not user.has_group("base.group_user"):
        return []
    home = env.ref("thirdcode_accounting.company_platform", raise_if_not_found=False)
    if is_platform_owner(env) or user.has_group(STAFF_GROUP):
        return home.ids if home and home in user.company_ids else []
    return list((set(company_ids) & set(user.company_ids.ids)) - set(home.ids if home else []))


class DiscussUser(models.Model):
    _inherit = "res.users"

    def _thirdcode_discuss_domain(self, company_ids, prefix=""):
        return [(prefix + "thirdcode_company_id", "in", scoped_companies(self.env, company_ids)),
                (prefix + "thirdcode_quarantined", "=", False)]

    @api.model
    def _thirdcode_contact_domain(self, company_ids, write=False, bank=False):
        domain = super()._thirdcode_contact_domain(company_ids, write=write, bank=bank)
        if not write and not bank and self.has_group(STAFF_GROUP):
            home = self.env.ref("thirdcode_accounting.company_platform", raise_if_not_found=False)
            if home and home.id in scoped_companies(self.env, company_ids):
                domain = expression.OR([domain, [("user_ids.thirdcode_platform_owner", "=", True),
                                                  ("user_ids.company_ids", "in", home.ids)]])
        return domain

    def _sync_company_discuss(self):
        if self.env["ir.config_parameter"].sudo().get_param(READY):
            self.env["discuss.channel"].with_user(SUPERUSER_ID)._sync_company_channels()

    def _check_support_role(self, values):
        if "groups_id" in values:
            staff = self.env.ref(STAFF_GROUP, raise_if_not_found=False)
            if staff and (staff.id in self.sudo().groups_id.ids or any(
                cmd[0] == 4 and cmd[1] == staff.id or cmd[0] == 6 and staff.id in cmd[2]
                for cmd in values["groups_id"]
            )):
                require_platform_owner(self.env)

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            self._check_support_role(values)
        users = super().create(values_list)
        users._sync_company_discuss()
        return users

    def write(self, values):
        self._check_support_role(values)
        result = super().write(values)
        if {"company_id", "company_ids", "groups_id", "active", "thirdcode_platform_owner"} & values.keys():
            self._sync_company_discuss()
        return result


class CompanyDiscussChannel(models.Model):
    _inherit = "discuss.channel"

    thirdcode_company_id = fields.Many2one("res.company", index=True, copy=False, readonly=True)
    thirdcode_quarantined = fields.Boolean(default=False, copy=False, readonly=True)
    thirdcode_general_company_id = fields.Many2one("res.company", copy=False, readonly=True)
    _sql_constraints = [("company_general_unique", "unique(thirdcode_general_company_id)",
                         "Each organization has one General channel.")]

    def _assert_company_scope(self):
        if not self or self.env.uid == SUPERUSER_ID:
            return
        actor = self.sudo(False)
        if not self.env.uid:
            raise AccessError(_("Sign in to your organization's workspace to access Discuss."))
        # env.companies validates forged allowed_company_ids before the sudo read.
        companies = scoped_companies(actor.env, actor.env.companies.ids)
        if any(c.thirdcode_quarantined or c.thirdcode_company_id.id not in companies for c in self.sudo()):
            raise AccessError(_("This conversation belongs to another organization."))

    def _assert_company_access(self):
        self._assert_company_scope()
        if self and self.env.uid != SUPERUSER_ID:
            self.sudo(False).check_access("read")

    def _eligible_partners(self):
        self.ensure_one()
        company = self.sudo().thirdcode_company_id
        if not company or self.sudo().thirdcode_quarantined:
            return self.env["res.partner"]
        users = self.env["res.users"].with_user(SUPERUSER_ID).search([
            ("active", "=", True), ("share", "=", False), ("company_ids", "in", company.ids),
            ("id", "!=", SUPERUSER_ID)])
        if company.thirdcode_is_platform:
            users = users.filtered(lambda u: is_platform_owner(u.with_user(u).env) or u.has_group(STAFF_GROUP))
        else:
            users = users.filtered(lambda u: not u.thirdcode_platform_owner and not u.has_group(STAFF_GROUP))
        return users.partner_id

    def _assert_participants(self, partner_ids, guest_ids=None):
        if self.env.uid == SUPERUSER_ID:
            return
        self._assert_company_scope()
        bot = self.env.ref("base.partner_root")
        for channel in self:
            if guest_ids or set(partner_ids) - set(channel._eligible_partners().ids) - set(bot.ids):
                raise AccessError(_("Conversations can include only users in the same organization."))

    @api.model_create_multi
    def create(self, values_list):
        values_list = [dict(v) for v in values_list]
        if self.env.uid != SUPERUSER_ID:
            company_ids = scoped_companies(self.sudo(False).env, self.sudo(False).env.companies.ids)
            if self.env.company.id not in company_ids:
                raise AccessError(_("Choose your organization's workspace to start a conversation."))
            for values in values_list:
                if any(values.get(key) or self.env.context.get("default_" + key) for key in SCOPE_FIELDS):
                    raise AccessError(_("Conversation ownership is assigned by the system."))
                if values.get("parent_channel_id"):
                    parent = self.browse(values["parent_channel_id"])
                    parent._assert_company_access()
                    company_id = parent.sudo().thirdcode_company_id.id
                else:
                    company_id = self.env.company.id
                values.update(thirdcode_company_id=company_id, thirdcode_quarantined=False,
                              thirdcode_general_company_id=False, allow_public_upload=False)
            # Never trust client install_mode to skip native creator membership.
            creator = self.with_context(install_mode=False)
        else:
            creator = self.with_context(install_mode=True)
        return super(CompanyDiscussChannel, creator).create(values_list)

    def write(self, values):
        if self.env.uid != SUPERUSER_ID:
            self._assert_company_access()
            if SCOPE_FIELDS & values.keys() or values.get("allow_public_upload"):
                raise AccessError(_("Conversation ownership and privacy cannot be changed."))
        return super().write(values)

    def _subscribe_users_automatically_get_members(self):
        # Groups span the database. Filter by channel ownership even for uid=1.
        return {c.id: (c.sudo().group_ids.users.partner_id & c._eligible_partners()
                       - c.sudo().channel_partner_ids).ids for c in self}

    def _subscribe_users_automatically(self):
        candidates = self._subscribe_users_automatically_get_members()
        values = [{"channel_id": cid, "partner_id": pid} for cid, ids in candidates.items() for pid in ids]
        if values:
            self.env["discuss.channel.member"].sudo().create(values)
        # Native group-wide broadcast would disclose the channel to other companies.

    def _find_or_create_persona_for_channel(self, *args, **kwargs):
        self._assert_company_access()
        return super()._find_or_create_persona_for_channel(*args, **kwargs)

    def _add_members(self, **kwargs):
        self._assert_company_access()
        partners = kwargs.get("partners") or self.env["res.partner"]
        users = kwargs.get("users") or self.env["res.users"]
        self._assert_participants((partners | users.sudo().partner_id).ids, kwargs.get("guests"))
        return super()._add_members(**kwargs)

    def message_post(self, **kwargs):
        self._assert_company_access()
        self._assert_participants(kwargs.get("partner_ids") or [])
        return super().message_post(**kwargs)

    def _to_store(self, store):
        self._assert_company_access()
        return super()._to_store(store)

    def _read_format(self, fnames, load="_classic_read"):
        self._assert_company_scope()
        return super()._read_format(fnames, load=load)

    @api.returns("self", lambda channels: Store(channels).get_result())
    def channel_get(self, partners_to, pin=True, force_open=False):
        partners = sorted(set(partners_to) | {self.env.user.partner_id.id})
        if len(partners) > 2:
            raise UserError(_("Use a group conversation for more than two people."))
        company = self.env.company
        # Use the canonical company channel to validate recipients before lookup.
        general = self.search([("thirdcode_general_company_id", "=", company.id)], limit=1)
        if not general:
            raise AccessError(_("Your organization does not have an available Discuss workspace."))
        general._assert_participants(partners)
        channels = self.search([("channel_type", "=", "chat"), ("thirdcode_company_id", "=", company.id),
                                ("channel_partner_ids", "in", partners)])
        channel = channels.filtered(lambda c: set(c.sudo().channel_partner_ids.ids) == set(partners))[:1]
        if not channel:
            channel = self.create({"name": ", ".join(self.env["res.partner"].browse(partners).mapped("name")),
                                   "channel_type": "chat", "channel_member_ids": [
                                       Command.create({"partner_id": pid, "unpin_dt": False if pid == self.env.user.partner_id.id else fields.Datetime.now()})
                                       for pid in partners]})
        if pin or force_open:
            values = {"last_interest_dt": fields.Datetime.now()}
            if pin:
                values["unpin_dt"] = False
            if force_open:
                values["fold_state"] = "open"
            self.env["discuss.channel.member"].search([
                ("channel_id", "=", channel.id), ("partner_id", "=", self.env.user.partner_id.id)]).write(values)
        channel._broadcast(self.env.user.partner_id.ids)
        return channel

    @api.model
    def _sync_company_channels(self):
        if self.env.uid != SUPERUSER_ID:
            raise AccessError(_("Only the trusted system operator may synchronize Discuss."))
        companies = self.env["res.company"].search([])
        for company in companies:
            # Serialize provisioning with a stable row lock and a unique constraint.
            self.env.cr.execute("SELECT id FROM res_company WHERE id = %s FOR UPDATE", [company.id])
            channel = self.with_context(active_test=False).search([
                ("thirdcode_general_company_id", "=", company.id)], limit=1)
            if not channel:
                channel = self.create({"name": "Platform support & moderation" if company.thirdcode_is_platform else "General",
                    "description": "Private conversations for this organization's users only.",
                    "channel_type": "channel", "thirdcode_company_id": company.id,
                    "thirdcode_general_company_id": company.id})
            eligible = channel._eligible_partners()
            missing = eligible - channel.channel_partner_ids
            if missing:
                self.env["discuss.channel.member"].create([
                    {"channel_id": channel.id, "partner_id": pid} for pid in missing.ids])
        # Revoke memberships immediately after user deactivation or scope changes.
        for channel in self.search([("thirdcode_company_id", "!=", False), ("thirdcode_quarantined", "=", False)]):
            eligible = channel._eligible_partners() | self.env.ref("base.partner_root")
            invalid = channel.channel_member_ids.filtered(lambda m: m.guest_id or m.partner_id not in eligible)
            for member in invalid:
                member._bus_send("discuss.channel/delete", {"id": channel.id})
            invalid.unlink()

    @api.model
    def _legacy_company(self):
        """Retain only history with one unambiguous organization of participants."""
        self.ensure_one()
        if self == self.env.ref("mail.channel_all_employees", raise_if_not_found=False):
            return self.env["res.company"]
        messages = self.env["mail.message"].search([("model", "=", "discuss.channel"), ("res_id", "=", self.id)])
        if self.channel_member_ids.guest_id or messages.author_guest_id or messages.filtered(
            lambda m: m.message_type == "comment" and not m.author_id
        ):
            return self.env["res.company"]
        partners = (self.channel_partner_ids | messages.author_id | messages.partner_ids) - self.env.ref("base.partner_root")
        companies = self.env["res.company"]
        for partner in partners.with_context(active_test=False):
            users = partner.user_ids
            if not users or users.filtered("share") or any(len(u.company_ids) != 1 for u in users):
                return self.env["res.company"]
            companies |= users.company_ids
        return companies if len(companies) == 1 else self.env["res.company"]

    @api.model
    def _install_company_discuss(self):
        if self.env.uid != SUPERUSER_ID:
            raise AccessError(_("Only the trusted system operator may migrate Discuss."))
        # Never split shared history based only on an author's current company.
        # Retain a private conversation only when members, authors and recipients
        # all identify the same single organization; otherwise restrict it.
        legacy = self.with_context(active_test=False).search([("thirdcode_company_id", "=", False)])
        for channel in legacy:
            company = channel._legacy_company()
            if company:
                channel.write({"thirdcode_company_id": company.id, "group_ids": [Command.clear()]})
                continue
            channel.rtc_session_ids.unlink()
            for member in channel.channel_member_ids:
                member._bus_send("discuss.channel/delete", {"id": channel.id})
            channel.write({"thirdcode_quarantined": True, "active": False, "group_ids": [Command.clear()],
                           "allow_public_upload": False})
        self._sync_company_channels()
        self.env["ir.config_parameter"].set_param(READY, "1")


class CompanyDiscussMember(models.Model):
    _inherit = "discuss.channel.member"

    def _to_store(self, store, **kwargs):
        self.sudo().channel_id._assert_company_access()
        return super()._to_store(store, **kwargs)

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            channel_id = values.get("channel_id", self.env.context.get("default_channel_id"))
            if channel_id:
                self.env["discuss.channel"].browse(channel_id)._assert_participants(
                    [values.get("partner_id", self.env.context.get("default_partner_id"))],
                    values.get("guest_id", self.env.context.get("default_guest_id")))
        return super().create(values_list)


class CompanyDiscussMessage(models.Model):
    _inherit = "mail.message"

    thirdcode_channel_id = fields.Many2one("discuss.channel", compute="_compute_discuss_channel", store=True, index=True)

    @api.depends("model", "res_id")
    def _compute_discuss_channel(self):
        valid = set(self.env["discuss.channel"].sudo().browse(
            self.filtered(lambda m: m.model == "discuss.channel").mapped("res_id")).exists().ids)
        for message in self:
            message.thirdcode_channel_id = message.res_id if message.model == "discuss.channel" and message.res_id in valid else False

    def _assert_discuss_access(self):
        self.sudo().thirdcode_channel_id._assert_company_access()

    def _read_format(self, fnames, load="_classic_read"):
        self._assert_discuss_access()
        return super()._read_format(fnames, load=load)

    def _export_rows(self, fields, *, _is_toplevel_call=True):
        self._assert_discuss_access()
        return super()._export_rows(fields, _is_toplevel_call=_is_toplevel_call)

    @api.model_create_multi
    def create(self, values_list):
        if self.env.uid != SUPERUSER_ID:
            for values in values_list:
                if "thirdcode_channel_id" in values or self.env.context.get("default_thirdcode_channel_id"):
                    raise AccessError(_("Conversation links are assigned by the system."))
                if values.get("model", self.env.context.get("default_model")) == "discuss.channel":
                    self.env["discuss.channel"].browse(values.get("res_id", self.env.context.get("default_res_id")))._assert_company_access()
        return super().create(values_list)

    def write(self, values):
        if self.env.uid != SUPERUSER_ID:
            self._assert_discuss_access()
            if "thirdcode_channel_id" in values or (
                {"model", "res_id"} & values.keys()
                and (self.sudo().thirdcode_channel_id or values.get("model") == "discuss.channel")
            ):
                raise AccessError(_("Messages cannot be moved between conversations."))
        return super().write(values)

    def _to_store(self, store, **kwargs):
        self._assert_discuss_access()
        return super()._to_store(store, **kwargs)


class CompanyDiscussBus(models.Model):
    _inherit = "bus.bus"

    def _poll(self, channels, last=0, ignore_ids=None):
        notifications = super()._poll(channels, last=last, ignore_ids=ignore_ids)
        if self.env.uid == SUPERUSER_ID:
            return notifications
        result = []
        for notification in notifications:
            message = notification["message"]
            kind, payload = message["type"], message["payload"]
            if not isinstance(payload, dict):
                result.append(notification)
                continue
            if kind == "discuss.channel/delete":
                result.append(notification)
                continue
            ids = set()
            if isinstance(payload.get("channel"), dict) and payload["channel"].get("id"):
                ids.add(payload["channel"]["id"])
            if isinstance(payload.get("channelId"), int):
                ids.add(payload["channelId"])
            if isinstance(payload.get("channel_id"), int):
                ids.add(payload["channel_id"])
            if kind.startswith("discuss.channel/") or payload.get("model") == "discuss.channel":
                if isinstance(payload.get("id"), int):
                    ids.add(payload["id"])
            data = payload.get("data", payload)
            if isinstance(data, dict):
                ids.update(row["id"] for row in data.get("discuss.channel", []) if "id" in row)
                for row in data.get("mail.message", []):
                    thread = row.get("thread")
                    if isinstance(thread, dict) and thread.get("model") == "discuss.channel":
                        ids.add(thread["id"])
                for model, relation in [("mail.message", "thirdcode_channel_id"),
                                         ("discuss.channel.member", "channel_id"),
                                         ("discuss.channel.rtc.session", "channel_id")]:
                    record_ids = [r["id"] for r in data.get(model, []) if isinstance(r.get("id"), int)]
                    ids.update(self.env[model].sudo().browse(record_ids).exists().mapped(relation).ids)
            try:
                self.env["discuss.channel"].browse(list(ids))._assert_company_access()
            except AccessError:
                continue
            result.append(notification)
        return result


class CompanyDiscussAttachment(models.Model):
    _inherit = "ir.attachment"

    thirdcode_channel_id = fields.Many2one("discuss.channel", compute="_compute_discuss_channel", store=True, index=True)

    @api.depends("res_model", "res_id")
    def _compute_discuss_channel(self):
        valid = set(self.env["discuss.channel"].sudo().browse(
            self.filtered(lambda a: a.res_model == "discuss.channel").mapped("res_id")).exists().ids)
        for attachment in self:
            attachment.thirdcode_channel_id = attachment.res_id if attachment.res_model == "discuss.channel" and attachment.res_id in valid else False

    def _to_http_stream(self):
        # Native attachment tokens/public=True bypass ir.rules. They must never
        # turn a company conversation attachment into a public download.
        self.sudo().thirdcode_channel_id._assert_company_access()
        return super()._to_http_stream()

    def _read_format(self, fnames, load="_classic_read"):
        self.sudo().thirdcode_channel_id._assert_company_access()
        return super()._read_format(fnames, load=load)

    @api.model_create_multi
    def create(self, values_list):
        if self.env.uid != SUPERUSER_ID:
            for values in values_list:
                if "thirdcode_channel_id" in values or self.env.context.get("default_thirdcode_channel_id"):
                    raise AccessError(_("Conversation links are assigned by the system."))
                if values.get("res_model", self.env.context.get("default_res_model")) == "discuss.channel":
                    self.env["discuss.channel"].browse(values.get("res_id", self.env.context.get("default_res_id")))._assert_company_access()
        return super().create(values_list)

    def write(self, values):
        if self.env.uid != SUPERUSER_ID:
            self.sudo().thirdcode_channel_id._assert_company_access()
            if "thirdcode_channel_id" in values:
                raise AccessError(_("Conversation links are assigned by the system."))
            if {"res_model", "res_id"} & values.keys():
                for attachment in self.sudo():
                    if values.get("res_model", attachment.res_model) == "discuss.channel":
                        self.env["discuss.channel"].browse(values.get("res_id", attachment.res_id))._assert_company_access()
        return super().write(values)


class CompanyDiscussRtc(models.Model):
    _inherit = "discuss.channel.rtc.session"

    def _notify_peers(self, notifications):
        self.channel_id._assert_company_access()
        for ids, _content in notifications:
            targets = self.env[self._name].sudo().browse(ids).exists()
            if targets.channel_id - self.channel_id:
                raise AccessError(_("Calls cannot connect to another conversation."))
        return super()._notify_peers(notifications)

    def _update_and_broadcast(self, values):
        self.channel_id._assert_company_access()
        return super()._update_and_broadcast(values)

    def _to_store(self, store, extra=False):
        self.channel_id._assert_company_access()
        return super()._to_store(store, extra=extra)


class CompanyDiscussPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def im_search(self, name, limit=20, excluded_ids=None):
        general = self.env["discuss.channel"].search([
            ("thirdcode_general_company_id", "=", self.env.company.id)], limit=1)
        eligible = general._eligible_partners() if general else self.browse()
        partners = self.search([("id", "in", eligible.ids), ("name", "ilike", name),
                                ("id", "not in", list(excluded_ids or []) + self.env.user.partner_id.ids)],
                               order="name, id", limit=limit)
        return Store(partners).get_result()
