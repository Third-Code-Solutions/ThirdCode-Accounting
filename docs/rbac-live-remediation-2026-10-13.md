# Live RBAC remediation — 2026-10-13

Remediation of the RBAC/role-workflow audit run against the live independent
production line (addon `18.0.2.15.5`, portal `f8c23ef`, database
`tcsi_pilot`). Every finding below was reproduced against production before
this change set; every fix is covered by a regression test in
`tests/test_rbac_hardening.py`.

## Findings and fixes

| ID | Severity | Fix shipped in 18.0.2.16.0 |
|----|----------|-----------------------------|
| F1 | CRITICAL | `/web/content` and `/web/image` no longer serve non-public attachments to anonymous visitors; internal users are confined to their companies and to records they can read. Model override (`models/ir_attachment.py`) + global attachment company rule. |
| F2 | CRITICAL | Audit HTTP sessions store database-scoped digests instead of raw session identifiers; the setup service is reachable only through the token-checked controller (in-process sentinel inside a superuser environment, `@api.private`); tenant roles no longer hold the native auditlog group (dedicated read-only evidence group instead). |
| F3 | HIGH | Outbound bank payments require an administrator-verified recipient bank (`allow_out_payment`); the Administrator role holds `account.group_validate_bank_account`. |
| F4 | HIGH | Payment batches cannot be approved by their creator; payments above the company threshold only post through an administrator-approved batch (unforgeable in-process token), closing the direct-posting bypass even when approval is disabled. |
| F5 | HIGH | Encoders cannot arm automatic posting on create or write, and the nightly auto-post job demotes drafts last edited by an Encoder account. |
| F6 | HIGH | Tenant administrators cannot reset passwords, disable, or expense-profile peer administrators / platform owners / accounts that reach outside their companies. |
| F7 | MEDIUM | Confirm/Post, Credit Note, Send and the official invoice print are hidden and server-refused for Encoder and Read-only roles; the automatic-post fields are hidden from Encoders. |
| F8 | MEDIUM | Existing role accounts are backfilled with the finance-overview home action (migration), matching new provisioning. |
| F9 | MEDIUM | Export capability confined to the platform and the Administrator role. |
| F10 | HIGH | Audit trail for financial changes is retained unchanged; tamper-proofing from C2 (digests) now applies to the session dimension too. |

## Operator steps after deploy (one-time)

1. Rotate `database.secret` (kills every stored session identifier, including
   any that predate the digest migration) and restart workers.
2. Re-run the role matrix smoke check with the four demo accounts
   (`qa-demo-report.json` workflows).
3. Confirm the engine reports addon version `18.0.2.16.0` and that the
   post-migration log lines appear ("session identifiers replaced", "native
   audit group removed", "evidence reader group added", "home action
   backfilled").

## Migration behaviour (18.0.2.16.0, post-migrate)

* Rewrites retained raw HTTP session identifiers to digests (row identity,
  user and timestamps untouched).
* Removes the native `auditlog.group_auditlog_user` membership from tenant
  accounts; platform staff keep it.
* Grants `group_thirdcode_audit_reader` to every existing role account.
* Backfills `action_tcsi_dashboard` for role accounts without a home action.

Odoo adds newly implied groups on upgrade but never removes withdrawn ones,
which is why the group changes require the migration rather than only the
XML data update.

## Deliberate non-changes

* Portal members retain the native attachment access behaviour (token and
  linked-record checks); the tenant boundary targets anonymous and internal
  users.
* Receipt/invoice control-number flows and receipt numbering are unchanged.
* The payment approval policy flag remains opt-in per company; the fix
  closes the bypass, it does not force the policy on.
