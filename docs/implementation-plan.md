# Implementation plan

This plan covers the implementable portion of the PRD review draft and keeps
client-owned approvals separate from technical work. The latest local
checkpoint is a full synthetic-scope implementation; production, cutover, and
client acceptance are not authorized by the draft.

## Architecture

- Odoo Community 18.0 and PostgreSQL 16 are the only accounting platform and
  ledger. Odoo ORM/XML-RPC posting and payment operations are used throughout.
- OCA modules are pinned to reviewed commits and installed only for reporting,
  statements, audit, and reconciliation surfaces that fit Community.
- Third Code behavior lives in `thirdcode_accounting`; upstream Odoo/OCA code is
  not forked.
- Corrections use native reversals, credit/debit notes, payment registration,
  and reconciliation. No replacement ledger or direct accounting-table writes
  exist.
- Client-specific report layouts, tax values, BIR controls, EIS scope,
  history policy, and approval thresholds are fields and guarded workflows,
  not invented decisions.

## Phase status

### Phase 1 — foundation and platform fit — VERIFIED LOCALLY

- Reproducible Docker Compose stack with pinned Odoo/PostgreSQL images.
- Pinned OCA audit, report, statement, and reconciliation modules.
- Separate addon and provisional role groups.
- Local HTTP login, module installation/update, and native report surfaces.

### Phase 2 — accounting controls — VERIFIED LOCALLY

- Period open/close/reopen and actual posting restriction.
- Recurring journal and recurring invoice/bill scheduler with duplicate-safe run
  keys.
- Posted-entry immutability, native reversal support, and immutable audit logs.
- Journal numbering policy evidence and observed sequence-gap validation.
- Native year-end income/expense close to retained earnings and reversal.

### Phase 3 — AR, AP, cash, and bank workflows — VERIFIED LOCALLY

- Native customer/supplier documents, attachments, payments, partial
  allocations, advances, credit/debit notes, and employee-expense surface.
- Payment batches with optional threshold approval and instrument references.
- Official-receipt sequence/metadata, amount words, customer TIN/VAT-derived
  values, and accountant-owned control-number guard.
- Manual paper/PDF bank reconciliation with evidence and statement-line status.

### Phase 4 — reports and regulatory configuration — PARTIAL / CLIENT-GATED

- OCA general-ledger, trial-balance, aged-balance, and partner-statement
  surfaces are installed and rendered locally.
- Provisional balance-sheet, profit-and-loss, and cash-movement PDFs derive
  from native move lines with Encoder report restrictions.
- Third Code invoice/receipt templates, report-sample approval metadata, tax
  profiles, retention fields, and CAS documentation template are present.
- Signed client samples, statutory tax decisions, BIR control values, and EIS
  classification remain required before acceptance or production use.

### Phase 5 — migration and operations — VERIFIED LOCALLY FOR SYNTHETIC INPUT

- CSV validation, deterministic fingerprints, dry-run, native XML-RPC load,
  source identifiers, duplicate-safe repeat load, and migration reconciliation.
- Database/filestore/config backup, hash/manifest verification, disposable
  restore, and restore database/filestore inspection.
- Two-worker synthetic save/post benchmark against proposed 2-second targets.
- CAS/runbook content and explicit client owner fields.
- Real MYOB extraction, parallel month, second-device backup, client hardware,
  restore owner, and production cutover remain open.

## Verification checkpoints

1. Foundation: install/update succeeds and the Milestone 1 regression remains
   green.
2. Controls: period, recurring, reversal, audit, numbering, and year-end tests
   pass.
3. Workflows: AR/AP/cash/report paths reconcile to the same Odoo ledger.
4. Operations: synthetic migration validation/load/idempotency and backup/
   restore pass.
5. Acceptance: AC-01–AC-09 are evidenced or marked `BLOCKED — CLIENT DECISION`;
   no synthetic result is labeled client acceptance.

The exact command results are maintained in
[docs/verification.md](verification.md), while requirement-level state is in
[docs/prd-traceability.md](prd-traceability.md).

## Next authorized gate

Before production configuration or cutover, obtain the approved v1.0 scope,
report samples, tax/BIR/EIS decision, real MYOB extract/mapping, role matrix,
infrastructure/backup owner, data retention policy, and parallel-run sign-off.
No production deployment, push, or client acceptance was performed in this
workspace.
