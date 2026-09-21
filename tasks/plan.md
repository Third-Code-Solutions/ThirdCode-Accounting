# Implementation Plan: Third Code Accounting PRD

## Objective

Deliver the largest technically implementable portion of the PRD using Odoo's
native accounting ledger and record the evidence and client-owned gates without
inventing business, tax, regulatory, migration, or acceptance data.

## Completed local scope

- [x] Read the complete PRD and pasted implementation brief.
- [x] Pin Odoo/PostgreSQL and the compatible OCA modules.
- [x] Install the custom addon without an upstream fork or second ledger.
- [x] Add provisional RBAC, server-side posting/period/reversal controls, and
      immutable audit-log behavior.
- [x] Add recurring journals/invoices, payment batches, advances, notes,
      official-receipt metadata, employee-expense surface, and bank controls.
- [x] Add report surfaces, guarded custom invoice/receipt templates, tax/report
      configuration, year-end retained earnings, and CAS documentation.
- [x] Add CSV migration validation/load/idempotency and reconciliation records.
- [x] Add backup/verify/restore and synthetic concurrency benchmark tooling.
- [x] Run the full synthetic regression and the Milestone 1 regression.
- [x] Maintain requirement traceability, decisions/blockers, verification, and
      reproducible setup documentation.

## Client-gated work that must not be fabricated

- [ ] Approve PRD v1.0 and final role/segregation-of-duties matrix.
- [ ] Provide signed report samples and monthly reconciliation definition.
- [ ] Provide tax/withholding rates, BIR acknowledgement/control values, EIS
      classification, numbering policy, retention, and signatory decisions.
- [ ] Provide authorized MYOB export, mapping, opening-balance owner, history
      versus archive decision, parallel month, and rollback sign-off.
- [ ] Confirm on-premise hardware, named users, backup second device, restore
      owner, RPO/RTO, monitoring, TLS, support, and performance dataset.
- [ ] Execute AC-01 through AC-09 with the client-owned data and approvals.

## Evidence commands

```powershell
$py = 'C:\Users\MSI\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py .\scripts\verify_full_scope.py
& $py .\scripts\verify_milestone1.py
& $py -m py_compile @(Get-ChildItem .\scripts -Filter *.py | Select-Object -ExpandProperty FullName) @(Get-ChildItem .\addons\thirdcode_accounting\models -Filter *.py | Select-Object -ExpandProperty FullName)
```

See [docs/implementation-plan.md](../docs/implementation-plan.md) for phase
status and [docs/verification.md](../docs/verification.md) for the last actual
results.
