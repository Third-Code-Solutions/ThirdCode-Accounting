# Decisions and blockers

This register separates engineering decisions made for the local synthetic
implementation from business decisions that require the client, accountant, or
infrastructure owner. The PRD is still version 0.1 review draft.

## Engineering decisions already made

| Decision | Consequence |
| --- | --- |
| Odoo Community 18.0 + PostgreSQL 16 | Odoo remains the single authoritative ledger and document store. Images are pinned by digest. |
| OCA modules are pinned to reviewed commits | Installed surfaces are audit logging, reporting, partner statements, and reconciliation; upstream code is not forked. |
| Third Code code stays in `thirdcode_accounting` | No Enterprise code, second ledger, direct accounting-table writes, or external accounting service was introduced. |
| Native posting/payment/reversal/reconciliation operations | Odoo validation, balances, and audit trails remain in the normal accounting paths. |
| Provisional role groups are mapped to native Odoo capabilities | The custom Administrator is an application role, not a server/database superuser; the final segregation-of-duties matrix remains pending. |
| Posted accounting records are immutable in the application | Corrections use supported reversals or credit/debit notes; synthetic posted probes are retained. |
| Recurring run keys are unique per source and date | Scheduler retries do not create a second posted entry for the same recurrence. |
| Official-receipt output is guarded | No BIR acknowledgement/control number is fabricated; printing requires an accountant-owned value and an explicit approval flag. |
| Unapproved report templates are visibly provisional | A report sample approval flag and revision are required before a custom layout can be represented as approved. |
| Migration is source-identifier driven | Validation, dry-run, explicit `--apply`, duplicate-safe load, and reconciliation records precede any real cutover. |
| Backup/restore targets are explicit and disposable | The scripts cover database, filestore, config, image metadata, hashes, and restore inspection; production scheduling is still client-owned. |

## Client decisions required before acceptance or production

1. Approve PRD v1.0 or an explicit scope addendum. Confirm recurring customer
   invoices, optional payment approval, live history/archive, integrations,
   monthly reconciliation, and all assumptions.
2. Approve the chart of accounts, tax/withholding rules, payment terms,
   journals, numbering/gap policy, BIR books, official documents, signatory,
   statutory retention, and EIS classification.
3. Provide signed samples for the statement of account, full financial
   statements, sales invoice, official receipt, and monthly reconciliation.
4. Provide an authorized MYOB export and mapping owner. Decide whether live
   history is migrated or retained in a read-only archive; define opening
   balances, cutover date, rollback, line-by-line reconciliation, and parallel
   month sign-off.
5. Approve the final role matrix: draft creation/editing, posting, reversal,
   reconciliation, period close/reopen, tax configuration, payment approval,
   audit-log visibility, user management, and server/database ownership.
6. Confirm on-premise OS/hardware/storage, five named users, concurrency and
   data-volume test, browser versions, TLS, monitoring, support, and response
   targets.
7. Name backup and restore owners, second-device destination, nightly schedule,
   retention, restore frequency, RPO, RTO, and disaster-recovery procedure.
8. Approve OCA license obligations before redistribution or managed-service
   deployment. The installed `account_financial_report`, `partner_statement`,
   `auditlog`, and reconciliation components include AGPL-3 modules; the
   `date_range` component is LGPL-3.

## Explicit current blockers / not-tested states

- No real MYOB extract, client mapping, archive, opening balance, or parallel
  accounting month was available.
- No client report sample, tax rate, BIR acknowledgement/control value, EIS
  classification, statutory/legal review, or client sign-off was available.
- Browser visual acceptance was not completed because the available browser
  automation kernel failed to initialize (`failed to write kernel assets: path
  not found`). Server-side/API and report rendering checks did run.
- The local benchmark and backup/restore use synthetic data and local Docker;
  client hardware, second-device backup, restore ownership, and production
  operations are not proven.
- Odoo native reports were rendered locally, but comparative/full client
  financial-statement samples and accepted layouts remain open.

These blockers do not prevent independent technical work, but no synthetic
result should be labeled client acceptance or regulatory compliance.
