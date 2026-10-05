"""Company-scoped contacts. Sharing grants access, never inferred ownership."""
import logging
from copy import deepcopy
from collections import defaultdict

from odoo import SUPERUSER_ID, Command, _, api, fields, models
from odoo.exceptions import AccessError
from odoo.addons.mail.tools.discuss import Store
from odoo.osv import expression

from .platform_access import is_platform_owner, require_platform_owner

_logger = logging.getLogger(__name__)
_SCOPE_FIELDS = {
    "thirdcode_shared_company_ids", "thirdcode_identity_company_ids",
    "thirdcode_is_identity", "thirdcode_company_identity_ids",
}


class ContactScopeUser(models.Model):
    _inherit = "res.users"

    def _get_invalidation_fields(self):
        return super()._get_invalidation_fields() | {"thirdcode_platform_owner"}

    @api.model
    def _thirdcode_is_contact_owner(self):
        return is_platform_owner(self.env)

    @api.model
    def _thirdcode_contact_domain(self, company_ids, write=False, bank=False):
        if is_platform_owner(self.env):
            return []
        prefix = "partner_id." if bank else ""
        if not self.has_group("base.group_user"):
            # Preserve native public/portal rules, including their own-tree rule.
            return ["|", "|", (prefix + "partner_share", "=", False),
                    (prefix + "company_id", "parent_of", company_ids),
                    (prefix + "company_id", "=", False)]
        # ir.rule evaluates with an empty context; use its validated company_ids,
        # never env.company here, and never search delegated res.users recursively.
        companies = list(set(company_ids) & set(self.env.user.sudo().company_ids.ids))
        owned = [(prefix + "thirdcode_is_identity", "=", False),
                 (prefix + "company_id", "in", companies)]
        own_profile = [(prefix + "id", "=", self.env.user.sudo().partner_id.id)]
        if write:
            domains = [owned, own_profile]
            if bank:
                domains.append([(prefix + "thirdcode_company_identity_ids", "in", companies)])
            elif self.has_group("base.group_system"):
                # res.users delegates access checks to res.partner even for
                # group-only writes. Preserve authorized Settings administration
                # within active companies; owner identities have no tenant scope.
                domains.append([(prefix + "thirdcode_is_identity", "=", True),
                                (prefix + "thirdcode_identity_company_ids", "in", companies)])
            return expression.OR(domains)
        identities = [(prefix + "thirdcode_is_identity", "=", True),
                      (prefix + "thirdcode_identity_company_ids", "in", companies)]
        shared = [(prefix + "thirdcode_is_identity", "=", False),
                  (prefix + "company_id", "=", False),
                  (prefix + "thirdcode_shared_company_ids", "in", companies)]
        return expression.OR([owned, identities, shared, own_profile])


class ContactIsolation(models.Model):
    _inherit = "res.partner"

    thirdcode_shared_company_ids = fields.Many2many(
        "res.company", "thirdcode_partner_shared_company_rel", "partner_id", "company_id",
        string="Approved shared access", copy=False, groups="base.group_system",
        help="Explicit read access to an unassigned business contact. Does not assign ownership.",
    )
    thirdcode_company_identity_ids = fields.One2many("res.company", "partner_id", groups="base.group_system")
    thirdcode_is_identity = fields.Boolean(compute="_compute_contact_identity", store=True, compute_sudo=True)
    thirdcode_identity_company_ids = fields.Many2many(
        "res.company", "thirdcode_partner_identity_company_rel", "partner_id", "company_id",
        compute="_compute_contact_identity", store=True, compute_sudo=True, groups="base.group_system",
    )

    @api.depends("user_ids", "user_ids.company_ids", "user_ids.thirdcode_platform_owner",
                 "thirdcode_company_identity_ids")
    def _compute_contact_identity(self):
        for partner in self.with_context(active_test=False):
            users = partner.user_ids
            partner.thirdcode_is_identity = bool(users or partner.thirdcode_company_identity_ids)
            users = users.filtered(lambda u: u.id != SUPERUSER_ID and not u.thirdcode_platform_owner)
            partner.thirdcode_identity_company_ids = (
                partner.thirdcode_company_identity_ids | users.company_ids
            )

    def _to_store(self, store, /, *, fields=None, main_user_by_partner=None):
        # Mail intentionally sudo-serializes personas. Apply the actual caller's
        # contact rules again before names, emails, avatars or user IDs leave ORM.
        records = self
        actor = self.sudo(False)
        if not is_platform_owner(self.env) and actor.env.user.has_group("base.group_user"):
            records = actor.with_context(active_test=False).search([("id", "in", self.ids)])
        return super(ContactIsolation, records)._to_store(
            store, fields=fields, main_user_by_partner=main_user_by_partner)

    def _check_contact_scope_values(self, values):
        if _SCOPE_FIELDS.intersection(values) or any(
            self.env.context.get("default_" + field) for field in _SCOPE_FIELDS
        ):
            require_platform_owner(self.env)
        if self.env.su or is_platform_owner(self.env):
            return
        if "company_id" in values and values["company_id"] not in self.env.companies.ids:
            raise AccessError(_("Choose an active company you are authorized to manage."))
        if "parent_id" in values and values["parent_id"]:
            parent = self.browse(values["parent_id"])
            parent.check_access("read")
            # Native commercial synchronization uses sudo. Do not join another
            # tenant's hierarchy or change a shared commercial identity indirectly.
            parent.check_access("write")
            if parent.company_id.id != values.get("company_id", self[:1].company_id.id or self.env.company.id):
                raise AccessError(_("Parent and child contacts must belong to the same company."))
        if "child_ids" in values:
            for command in values["child_ids"]:
                if command[0] in (1, 2, 3, 4):
                    self.browse(command[1]).check_access("write")
                elif command[0] == 6:
                    self.browse(command[2]).check_access("write")
        if "company_id" in values and self:
            # Changing a tree's scope may expose hidden children through native
            # sudo synchronization. Ownership transfers require owner review.
            if any(p.company_id.id != values["company_id"] for p in self):
                raise AccessError(_("Contact ownership changes require platform owner review."))

    @api.model_create_multi
    def create(self, values_list):
        values_list = [dict(values) for values in values_list]
        defaults = self.default_get(["parent_id", "child_ids", *_SCOPE_FIELDS])
        for values in values_list:
            for name, value in defaults.items():
                values.setdefault(name, value)
        if not self.env.su and not is_platform_owner(self.env):
            for values in values_list:
                values["company_id"] = values.get("company_id") or self.env.context.get("default_company_id") or self.env.company.id
        for values in values_list:
            self._check_contact_scope_values(values)
        return super().create(values_list)

    def write(self, values):
        self.check_access("write")
        self._check_contact_scope_values(values)
        return super().write(values)

    @api.model
    def _install_contact_isolation(self):
        """Idempotent upgrade: replace permissive globals, preserve portal rules."""
        require_platform_owner(self.env)
        self.env.ref("base.res_partner_rule").write({
            "domain_force": "user._thirdcode_contact_domain(company_ids)",
        })
        self.env.ref("base.res_partner_bank_rule").write({
            "domain_force": "user._thirdcode_contact_domain(company_ids, bank=True)",
        })
        marker = "thirdcode.contact_scope_backfill_v1"
        params = self.env["ir.config_parameter"].sudo()
        if params.get_param(marker):
            return
        # Snapshot existing document relationships ONCE. A newly forged draft
        # never creates a grant. Keep company_id and every accounting row intact.
        self.env.flush_all()
        self.env.cr.execute("""
            SELECT DISTINCT partner_id, company_id FROM (
                SELECT partner_id, company_id FROM account_move
                UNION SELECT commercial_partner_id, company_id FROM account_move
                UNION SELECT partner_shipping_id, company_id FROM account_move
                UNION SELECT partner_id, company_id FROM account_move_line
                UNION SELECT partner_id, company_id FROM account_payment
            ) refs WHERE partner_id IS NOT NULL AND company_id IS NOT NULL
        """)
        grants = defaultdict(set)
        for partner_id, company_id in self.env.cr.fetchall():
            partner = self.browse(partner_id)
            # Ancestors are needed for native display/commercial fields, siblings
            # are not. Existing foreign ownership and identities stay restricted.
            seen = set()
            while partner and partner.id not in seen:
                seen.add(partner.id)
                if not partner.company_id and not partner.thirdcode_is_identity:
                    grants[partner.id].add(company_id)
                partner = partner.parent_id
        for partner_id, companies in grants.items():
            self.browse(partner_id).write({"thirdcode_shared_company_ids": [Command.link(c) for c in sorted(companies)]})
        params.set_param(marker, "done")
        _logger.info("Contact isolation: preserved %s shared business contacts through explicit accounting links; ownership unchanged", len(grants))


def normalize_partner_defaults(records, values_list):
    """Check the same effective values the ORM will store, including ir.default."""
    names = {name for name, field in records._fields.items()
             if field.type == "many2one" and field.comodel_name in {"res.partner", "res.partner.bank"}}
    names |= {"company_id", "journal_id", "move_id"} & records._fields.keys()
    result = []
    for values in values_list:
        defaults = records.with_context(**{
            "default_" + name: values[name]
            for name in ("company_id", "journal_id", "move_id") if name in values
        }).default_get(list(names - values.keys()))
        result.append({**defaults, **values})
    return result


def check_partner_reference(records, values):
    """Many2one assignment does not itself check the referenced record's rules."""
    if records.env.su or is_platform_owner(records.env):
        return
    names = [name for name, field in records._fields.items()
             if field.type == "many2one" and field.comodel_name in {"res.partner", "res.partner.bank"}]
    scope_fields = {"company_id", "journal_id", "move_id"}
    if records and not (scope_fields | set(names)).intersection(values):
        return
    for record in records or [records]:
        company_id = values.get("company_id")
        if not company_id and values.get("move_id") and "move_id" in records._fields:
            company_id = records.env["account.move"].browse(values["move_id"]).company_id.id
        if not company_id and values.get("journal_id"):
            company_id = records.env["account.journal"].browse(values["journal_id"]).company_id.id
        if not company_id and record:
            company_id = record.company_id.id
        company_id = company_id or records.env.context.get("default_company_id") or records.env.company.id
        for name in names:
            target_id = values.get(name)
            if name not in values:
                if (record and scope_fields.intersection(values) and records._fields[name].store
                        and not records._fields[name].compute):
                    target_id = record[name].id
                elif not record:
                    target_id = records.env.context.get("default_" + name)
            if target_id:
                records.env[records._fields[name].comodel_name].with_context(
                    allowed_company_ids=[company_id]
                ).browse(target_id).check_access("read")


def validate_final_partner_references(records):
    if records.env.su or is_platform_owner(records.env):
        return
    names = [name for name, field in records._fields.items()
             if field.store and field.type == "many2one"
             and field.comodel_name in {"res.partner", "res.partner.bank"}]
    for record in records:
        values = {name: record[name].id for name in names}
        values["company_id"] = record.company_id.id
        check_partner_reference(record, values)


class ContactScopedMove(models.Model):
    _inherit = "account.move"

    @api.model_create_multi
    def create(self, values_list):
        values_list = normalize_partner_defaults(self, values_list)
        for values in values_list:
            check_partner_reference(self, values)
        records = super().create(values_list)
        validate_final_partner_references(records)
        return records

    def write(self, values):
        check_partner_reference(self, values)
        result = super().write(values)
        if {"company_id", "journal_id", "move_id", "partner_id", "partner_shipping_id", "partner_bank_id", "commercial_partner_id"}.intersection(values):
            validate_final_partner_references(self)
        return result


class ContactScopedMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.model_create_multi
    def create(self, values_list):
        values_list = normalize_partner_defaults(self, values_list)
        for values in values_list:
            check_partner_reference(self, values)
        records = super().create(values_list)
        validate_final_partner_references(records)
        return records

    def write(self, values):
        check_partner_reference(self, values)
        result = super().write(values)
        if {"company_id", "journal_id", "move_id", "partner_id", "partner_shipping_id", "partner_bank_id", "commercial_partner_id"}.intersection(values):
            validate_final_partner_references(self)
        return result


class ContactScopedPayment(models.Model):
    _inherit = "account.payment"

    @api.model_create_multi
    def create(self, values_list):
        values_list = normalize_partner_defaults(self, values_list)
        for values in values_list:
            check_partner_reference(self, values)
        records = super().create(values_list)
        validate_final_partner_references(records)
        return records

    def write(self, values):
        check_partner_reference(self, values)
        result = super().write(values)
        if {"company_id", "journal_id", "move_id", "partner_id", "partner_shipping_id", "partner_bank_id", "commercial_partner_id"}.intersection(values):
            validate_final_partner_references(self)
        return result


class ContactScopedBank(models.Model):
    _inherit = "res.partner.bank"

    def _check_partner_target(self, values):
        if self.env.su or is_platform_owner(self.env):
            return
        partner_id = values.get("partner_id", self.env.context.get("default_partner_id") if not self else None)
        if partner_id:
            partner = self.env["res.partner"].browse(partner_id)
            partner.check_access("read")
            if partner not in self.env.companies.partner_id:
                partner.check_access("write")
            if self and any(bank.partner_id != partner for bank in self):
                raise AccessError(_("Bank account ownership changes require platform owner review."))

    @api.model_create_multi
    def create(self, values_list):
        defaults = self.default_get(["partner_id"])
        values_list = [{**defaults, **values} for values in values_list]
        for values in values_list:
            self._check_partner_target(values)
        return super().create(values_list)

    def write(self, values):
        self._check_partner_target(values)
        return super().write(values)


class ContactScopedChannel(models.Model):
    _inherit = "discuss.channel"

    def _subscribe_users_automatically_get_members(self):
        # Native group/department subscription inspects all existing member
        # contacts, including foreign tenants. Read only internal membership IDs
        # elevated, then intersect with the acting user's actual contact rules.
        self.check_access("read")
        members = super(ContactScopedChannel, self.sudo())._subscribe_users_automatically_get_members()
        if is_platform_owner(self.env):
            return members
        candidates = {partner_id for ids in members.values() for partner_id in ids}
        visible = set(self.env["res.partner"].sudo(False).search([("id", "in", list(candidates))]).ids)
        return {channel_id: [partner_id for partner_id in ids if partner_id in visible]
                for channel_id, ids in members.items()}

    def _load_more_members(self, known_member_ids):
        self.ensure_one()
        self.check_access("read")
        if is_platform_owner(self.env) or not self.env.user.has_group("base.group_user"):
            return super()._load_more_members(known_member_ids)
        visible = self.env["res.partner"].sudo(False).with_context(active_test=False).search([])
        domain = [("channel_id", "=", self.id), "|", ("partner_id", "=", False),
                  ("partner_id", "in", visible.ids)]
        members = self.env["discuss.channel.member"]
        unknown = members.search(domain + [("id", "not in", known_member_ids)], limit=100)
        return Store(unknown).add(self, {"memberCount": members.search_count(domain)}).get_result()


class ContactScopedMessage(models.Model):
    _inherit = "mail.message"

    def _author_to_store(self, store):
        result = super()._author_to_store(store)
        actor = self.sudo(False)
        if not is_platform_owner(self.env) and actor.env.user.has_group("base.group_user"):
            authors = self.sudo().author_id
            visible = actor.env["res.partner"].with_context(active_test=False).search([("id", "in", authors.ids)])
            for message in self:
                if message.sudo().author_id and message.sudo().author_id.id not in visible.ids:
                    store.add(message, {"author": False, "email_from": False})
        return result


def scope_contact_store(env, data):
    """Scope native Store payloads at the receiving WebSocket session boundary."""
    data = deepcopy(data)
    partner_ids = {row["id"] for row in data.get("res.partner", [])}

    def collect(value):
        if isinstance(value, dict):
            if value.get("type") == "partner" and isinstance(value.get("id"), int):
                partner_ids.add(value["id"])
            for item in value.values():
                collect(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                collect(item)
    collect(data)
    visible = set(env["res.partner"].sudo(False).with_context(active_test=False).search([("id", "in", list(partner_ids))]).ids)
    hidden = partner_ids - visible

    def clean(value):
        if isinstance(value, dict):
            if value.get("type") == "partner" and value.get("id") in hidden:
                return False
            return {key: clean(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [clean(item) for item in value if not (
                isinstance(item, dict) and item.get("type") == "partner" and item.get("id") in hidden)]
        return value
    for row in data.get("mail.message", []):
        author = row.get("author")
        if isinstance(author, dict) and author.get("type") == "partner" and author.get("id") in hidden:
            row["email_from"] = False
    if "res.partner" in data:
        data["res.partner"] = [row for row in data["res.partner"] if row["id"] not in hidden]
    if "discuss.channel.member" in data:
        data["discuss.channel.member"] = [row for row in data["discuss.channel.member"]
            if not (isinstance(row.get("persona"), dict) and row["persona"].get("type") == "partner"
                    and row["persona"].get("id") in hidden)]
    return clean(data)


class ContactScopedBus(models.Model):
    _inherit = "bus.bus"

    def _poll(self, channels, last=0, ignore_ids=None):
        notifications = super()._poll(channels, last=last, ignore_ids=ignore_ids)
        if is_platform_owner(self.env) or not self.env.user.has_group("base.group_user"):
            return notifications
        # Producers broadcast the same Store to every channel member. Scope it
        # per receiver; sender-side filtering alone leaks across legacy channels.
        notifications = deepcopy(notifications)
        for notification in notifications:
            message = notification["message"]
            if message["type"] == "mail.record/insert":
                message["payload"] = scope_contact_store(self.env, message["payload"])
            elif message["type"] == "discuss.channel/new_message":
                message["payload"]["data"] = scope_contact_store(self.env, message["payload"]["data"])
        return notifications
