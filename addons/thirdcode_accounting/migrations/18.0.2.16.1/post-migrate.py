"""Idempotent reconciliation for databases upgraded by the first 16.0 build.

The initial ``18.0.2.16.0`` pass could not remove the native audit membership
while the role definitions still linked the group through additive
``(4, ref(...))`` commands (those links survive module upgrades, so the
per-user guard correctly detected another chain still implying the group and
skipped). The role records now clear-then-set their implied groups, and this
pass repeats the removal so any database that upgraded before the
correction converges:

* detaches the native ``auditlog.group_auditlog_user`` link from every TCSI
  role definition;
* strips the native membership from tenant accounts (platform staff keep
  it);
* grants the dedicated read-only evidence reader group where missing.

Safe to re-run.
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


def _detach_native_from_role_groups(env):
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


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    detached = _detach_native_from_role_groups(env)
    stripped = _strip_native_audit_group(env)
    added = _ensure_reader_membership(env)
    _logger.info(
        "Audit access reconciliation: %s role definitions detached, %s tenant "
        "accounts stripped of the native audit group, %s accounts granted the "
        "evidence reader group",
        detached,
        stripped,
        added,
    )
