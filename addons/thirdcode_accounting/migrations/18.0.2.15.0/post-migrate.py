"""Replace retained raw HTTP session identifiers with database-scoped digests.

Audit finding C2: the OCA audit log stored ``request.session.sid`` verbatim on
every logged HTTP session, readable by every business role. New records are
digested at write time (``auditlog.http.session.current_http_session``); this
migration rewrites the already stored values in place. Row identity, user,
timestamps and request evidence are untouched.

The second step removes the native ``auditlog.group_auditlog_user`` membership
that tenant users materialized from the old role definitions: Odoo adds newly
implied groups to users on upgrade but never removes withdrawn ones.
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


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    replaced = _replace_stored_session_ids(env)
    if replaced:
        _logger.info(
            "Audit session digests: %s stored session identifiers replaced", replaced
        )
    stripped = _strip_native_audit_group(env)
    if stripped:
        _logger.info(
            "Audit access: native audit group removed from %s tenant accounts",
            stripped,
        )
