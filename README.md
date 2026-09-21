# TCSI Accounting Workspace

Third Code Solutions Inc. local implementation of the feasible portions of `Accounting_System_PRD_v0.1`
using Odoo Community 18.0, PostgreSQL 16, pinned OCA modules, and the separate
`thirdcode_accounting` addon. The repository is a working synthetic-data
implementation and verification environment. It is not a production cutover,
BIR approval, MYOB migration sign-off, or client acceptance record.

## What is implemented

The local stack uses Odoo's native accounting ledger, documents, posting,
payments, reconciliation, attachments, users, and reports. The custom addon
adds:

- provisional Administrator, Accountant, Encoder, and Read-only role groups;
- server-side report-wizard guards so Encoder users cannot run accounting
  reports while Accountant and Read-only users retain report access;
- server-side posting, period-close, reversal, and posted-record protections;
- immutable application audit-log entries;
- open/closed accounting periods and an administrator-only reopen path;
- recurring journal entries and recurring customer invoices/supplier bills with
  idempotent run keys and a daily scheduler;
- customer/supplier invoices, bills, credit notes, debit notes, advances,
  partial payments, official-receipt numbering, payment instruments, and
  accountant-guarded invoice/receipt reports;
- payment batches with cash, cheque, transfer, optional threshold approval,
  native payment-register reconciliation, and advance payments;
- manual paper/PDF bank and cash reconciliation records with evidence,
  zero-difference sign-off, reopen control, and statement-line status;
- tax-profile and BIR/EIS configuration fields that remain unapproved until
  accountant-owned values and samples are supplied;
- report-sample approval metadata and provisional invoice/receipt templates;
- provisional balance-sheet, profit-and-loss, and cash-movement PDF reports
  derived from native posted move lines;
- native year-end income/expense closing to a configured retained-earnings
  account using a reversible native journal entry;
- repeatable CSV migration validation/loading through Odoo XML-RPC with source
  identifiers, duplicate safety, balanced opening/transaction checks, and
  reconciliation rows;
- TCSI-branded login, favicon, official Th/rd Code app mark, navigation
  identity, violet/lilac visual language, typography, forms, lists, reports,
  and user-facing promotional-link cleanup, aligned to
  <https://www.thirdcodesolutions.com>;
- database, filestore, configuration, manifest, hash, verification, restore,
  and synthetic performance tooling.

The OCA add-ons are pinned in `docker/odoo/Dockerfile` and installed in the
compose database: `auditlog`, `date_range`, `report_xlsx`,
`report_xlsx_helper`, `account_financial_report`, `partner_statement`,
`account_statement_base`, `account_reconcile_model_oca`, `account_reconcile_oca`,
and `account_statement_reconcile_status`.

## Start the local stack

Prerequisite: Docker Desktop with the Linux engine running.

```powershell
Copy-Item .env.example .env
.\scripts\bootstrap.ps1
```

Open <http://localhost:8069/web/login>. The sign-in and accounting workspace are
branded for Third Code Solutions Inc. The default disposable database is
`thirdcode_accounting`; the development administrator is `admin` / `admin` as
configured in `config/odoo.conf`. These credentials are local-only and must not
be reused outside this proof environment.

`bootstrap.ps1` builds the pinned image, installs the Odoo Community and OCA
modules, installs/updates `thirdcode_accounting`, starts Odoo, and waits for
the local HTTP endpoint. It is intended for a disposable local database, not a
production database.

## Verification commands

Run the full synthetic regression as the seeded local administrator created by
the verifier:

```powershell
$py = 'C:\Users\MSI\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py .\scripts\verify_full_scope.py
& $py .\scripts\verify_milestone1.py
```

The full verifier covers the closed-period posting guard, recurring journal and
invoice idempotency, payment batches and official-receipt guard, advances,
credit/debit notes, employee-expense surface, statement-line status, manual
bank reconciliation, numbering control, year-end retained earnings and native
reversal, report-sample approval, tax profile configuration, migration-batch
reconciliation, and audit-log immutability. It leaves clearly synthetic posted
records in the disposable database because posted accounting records are not
deleted.

The latest results and exact evidence states are recorded in
[`docs/verification.md`](/D:/thirdcode/accounting-system/ThirdCode-Accounting/docs/verification.md).

## Migration tooling

The validator accepts the six agreed CSV surfaces: `accounts.csv`,
`partners.csv`, `taxes.csv`, `open_items.csv`, `transactions.csv`, and
`opening_tb.csv`. It reports schema errors, duplicate/source-reference errors,
missing references, unbalanced rows, and deterministic SHA-256 fingerprints.

```powershell
& $py .\scripts\migration_validate.py --input C:\path\to\myob-export --report C:\temp\migration-validation.json
& $py .\scripts\migration_load.py --input C:\path\to\myob-export --database thirdcode_accounting --company-id 1 --journal-id 3 --cutover-date 2026-09-21 --opening-journal-id 3 --sales-journal-id 1 --purchase-journal-id 2 --login m1.administrator --password M1-administrator-pass
& $py .\scripts\migration_load.py --input C:\path\to\myob-export --database thirdcode_accounting --company-id 1 --journal-id 3 --cutover-date 2026-09-21 --opening-journal-id 3 --sales-journal-id 1 --purchase-journal-id 2 --login m1.administrator --password M1-administrator-pass --apply
```

Loading is dry-run by default. `--apply` is required for writes. Sales and
purchase journals must be supplied explicitly when open items are loaded; the
loader uses Odoo ORM/XML-RPC operations and source identifiers to make repeated
loads skip already-created records. A real MYOB export, mapping approval,
opening-balance owner, history/archive decision, and parallel month are still
client-gated.

## Backup, restore, and performance

Back up the database, Odoo filestore, read-only configuration, image metadata,
and hashes to an explicit directory:

```powershell
.\scripts\backup.ps1 -Database thirdcode_accounting -OutputRoot D:\backups\thirdcode-accounting
.\scripts\verify_backup.ps1 -BackupDirectory D:\backups\thirdcode-accounting\thirdcode_accounting-<timestamp>
.\scripts\restore.ps1 -BackupDirectory D:\backups\thirdcode-accounting\thirdcode_accounting-<timestamp> -TargetDatabase thirdcode_accounting_restore -FilestoreTarget D:\restore\thirdcode-accounting
```

Restore targets are explicit and disposable; replacement requires the separate
`-AllowReplaceExisting` switch. The client still needs to choose the nightly
second-device destination, owner, RPO/RTO, retention, and restore schedule.

The synthetic benchmark uses separate HTTP sessions for concurrent workers and
native ORM posting:

```powershell
& $py .\scripts\benchmark.py --url http://localhost:8069 --database thirdcode_accounting --login m1.administrator --password M1-administrator-pass --iterations 10 --workers 2 --post
```

This measures local synthetic data only. It does not prove performance on the
client's on-premise hardware, data volume, browser, or network.

## Repository status and boundaries

- The source is in the local working tree on `main`; no commit, push, external
  deployment, or production database change was performed by this task.
- Client-specific report samples, BIR acknowledgement/control values, tax and
  withholding rates, EIS classification, MYOB extraction/mapping, live-history
  policy, parallel run, production roles, infrastructure, and statutory/legal
  acceptance remain explicitly pending.
- The custom reports display a visible draft marker until report samples are
  approved. Invoice and official-receipt printing is blocked until the
  accountant-owned BIR acknowledgement control number is configured and marked
  approved.
- No second ledger, direct accounting-table writes, Enterprise code, payroll,
  purchasing system, bank feed, EIS transmission, or external integration was
  introduced.

See [`docs/prd-traceability.md`](/D:/thirdcode/accounting-system/ThirdCode-Accounting/docs/prd-traceability.md),
[`docs/decisions-and-blockers.md`](/D:/thirdcode/accounting-system/ThirdCode-Accounting/docs/decisions-and-blockers.md),
[`docs/implementation-plan.md`](/D:/thirdcode/accounting-system/ThirdCode-Accounting/docs/implementation-plan.md),
and [`docs/verification.md`](/D:/thirdcode/accounting-system/ThirdCode-Accounting/docs/verification.md).
