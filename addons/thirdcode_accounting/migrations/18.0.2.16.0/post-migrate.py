"""Live-line RBAC remediation for databases running the independent release.

Complements ``18.0.2.15.0`` (which this addon version supersedes) for tenants
that already run a 15.x release before the audit remediation landed:

* replaces retained raw HTTP session identifiers with database-scoped digests
  (audit finding C2);
* detaches the native ``auditlog.group_auditlog_user`` link from the role
  definitions (additive ``(4, ref(...))`` commands survive upgrades) and
  removes the membership from tenant accounts, granting the dedicated
  read-only audit evidence group instead (Odoo adds newly implied groups on
  upgrade but never removes withdrawn ones);
* backfills the finance-overview home action for existing role accounts so
  every workspace login lands on the TCSI dashboard rather than the web
  client's Discuss default (audit finding F8).
"""
import logging

from odoo import SUPERUSER_ID, Command, api

_logger = logging.getLogger(__name__)

_ROLE_GROUP_XMLIDS = (
    "thirdcode_accounting.group_thirdcode_readonly",
    "thirdcode_accounting.group_thirdcode_encoder",
    "thirdcode_accounting.group_thirdcode_accountant",
    "thirdcode_accounting.group_thirdcode_administrator",
)


def _replace_stored_session_ids(env):
    from odoo.addons.thirdcode_accounting.models.auditlog import session_digest

    replaced = 0
    while True:
        env.cr.execute(
            "SELECT id, name FROM auditlog_http_session "
            "WHERE name IS NOT NULL AND name NOT LIKE 'sha256:%%' "
            "ORDER BY id LIMIT 500"
        )
        rows = env.cr.fetchall()
        if not rows:
            break
        for row_id, name in rows:
            env.cr.execute(
                "UPDATE auditlog_http_session SET name = %s WHERE id = %s",
                [session_digest(env, name), row_id],
            )
        replaced += len(rows)
    return replaced


def _detach_native_from_role_groups(env):
    """Remove the native audit group link from the TCSI role definitions.

    The role records historically linked the native group through additive
    ``(4, ref(...))`` commands, which survive upgrades; detaching the link
    here is what lets the per-user strip below actually apply.
    """
    oca_group = env.ref("auditlog.group_auditlog_user", raise_if_not_found=False)
    if not oca_group:
        return 0
    detached = 0
    for xmlid in _ROLE_GROUP_XMLIDS:
        group = env.ref(xmlid)
        if oca_group in group.implied_ids:
            group.write({"implied_ids": [Command.unlink(oca_group.id)]})
            detached += 1
    return detached


def _strip_native_audit_group(env):
    oca_group = env.ref("auditlog.group_auditlog_user", raise_if_not_found=False)
    if not oca_group:
        return 0
    role_ids = [env.ref(xmlid).id for xmlid in _ROLE_GROUP_XMLIDS]
    users = (
        env["res.users"]
        .sudo()
        .with_context(active_test=False)
        .search([("groups_id", "in", role_ids)])
    )
    stripped = 0
    for user in users:
        if oca_group not in user.groups_id:
            continue
        # Platform staff keep native audit visibility; only tenant roles must
        # lose it. Keep the membership if another chain still implies it.
        if user.has_group("base.group_system"):
            continue
        if oca_group in (user.groups_id - oca_group).trans_implied_ids:
            continue
        user.write({"groups_id": [Command.unlink(oca_group.id)]})
        stripped += 1
    return stripped


def _ensure_reader_membership(env):
    reader = env.ref(
        "thirdcode_accounting.group_thirdcode_audit_reader", raise_if_not_found=False
    )
    if not reader:
        return 0
    role_ids = [env.ref(xmlid).id for xmlid in _ROLE_GROUP_XMLIDS]
    users = (
        env["res.users"]
        .sudo()
        .with_context(active_test=False)
        .search([("groups_id", "in", role_ids), ("groups_id", "not in", reader.ids)])
    )
    for user in users:
        user.write({"groups_id": [Command.link(reader.id)]})
    return len(users)


def _backfill_home_action(env):
    home = env.ref(
        "thirdcode_accounting.action_tcsi_dashboard", raise_if_not_found=False
    )
    if not home:
        return 0
    role_ids = [env.ref(xmlid).id for xmlid in _ROLE_GROUP_XMLIDS]
    system_gid = env.ref("base.group_system").id
    env.cr.execute(
        "SELECT DISTINCT uid FROM res_groups_users_rel WHERE gid IN %s "
        "AND uid NOT IN (SELECT uid FROM res_groups_users_rel WHERE gid = %s)",
        [tuple(role_ids), system_gid],
    )
    uids = [row[0] for row in env.cr.fetchall()]
    if not uids:
        return 0
    env.cr.execute(
        "UPDATE res_users SET action_id = %s WHERE id IN %s AND action_id IS NULL",
        [home.id, tuple(uids)],
    )
    return env.cr.rowcount


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    replaced = _replace_stored_session_ids(env)
    if replaced:
        _logger.info(
            "Audit session digests: %s stored session identifiers replaced", replaced
        )
    detached = _detach_native_from_role_groups(env)
    if detached:
        _logger.info(
            "Audit access: role definitions detached from the native audit group: %s",
            detached,
        )
    stripped = _strip_native_audit_group(env)
    if stripped:
        _logger.info(
            "Audit access: native audit group removed from %s tenant accounts",
            stripped,
        )
    added = _ensure_reader_membership(env)
    if added:
        _logger.info(
            "Audit access: evidence reader group added to %s accounts", added
        )
    homed = _backfill_home_action(env)
    if homed:
        _logger.info(
            "Home action: finance overview backfilled for %s accounts", homed
        )
