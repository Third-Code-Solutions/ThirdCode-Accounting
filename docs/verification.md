# Full local verification

Last verified: 21 September 2026 in the local workspace. All records used by
these checks are synthetic. This document distinguishes implementation evidence
from client acceptance, production operations, and regulatory approval.

## Environment

- Repository: `ThirdCode-Accounting`, branch `main`, local working tree only;
  no commit, push, or external deployment was performed.
- Odoo Community 18.0 in Docker, database `thirdcode_accounting`.
- PostgreSQL 16 Alpine in Docker.
- Company/currency: `Third Code Solutions Inc.` / USD.
- Local URL: <http://localhost:8069/web/login>.
- Local development administrator: `admin` / `admin` from
  `config/odoo.conf`; never reuse outside this disposable proof.
- Synthetic business users created by the verifiers: `m1.readonly`,
  `m1.encoder`, `m1.accountant`, and `m1.administrator`.

## Checks

| Check | Result | Evidence |
| --- | --- | --- |
| Docker services | **PASSED** | `docker compose ps`: PostgreSQL healthy and Odoo published on port 8069 |
| Final image/module update | **PASSED** | `docker compose up -d --build odoo`; Odoo `-u thirdcode_accounting --stop-after-init`; 63 modules loaded with the addon data/views/reports |
| TCSI branding assets and server-rendered identity | **PASSED** | Official Th/rd Code violet mark and wordmark served; login contains Third Code Solutions Inc. and TCSI Accounting; `Powered by Odoo` and `Manage Databases` are absent; frontend/backend bundles compile without CSS fallback errors; app manifest uses TCSI metadata and icon |
| TCSI command center and shared UI shell | **PASSED** | Local browser rendered the live dashboard at `/odoo/action-425` with KPI cards, six-month activity chart, attention queue, recent ledger activity, shortcuts, role-aware invoice CTA, and the refreshed violet mark; the invoice CTA opened `/odoo/action-425/account.move/new` with the branded responsive form shell |
| Responsive UI rules | **PARTIAL** | Shared shell and dashboard include tested 1180px, 720px, and 430px breakpoints plus reduced-motion handling; desktop browser rendering passed, while a separate physical mobile-device matrix remains pending |
| Python syntax | **PASSED** | `py_compile` over all 26 repository Python files (migration, benchmark, verifiers, report access, financial report, and addon models) |
| Installed audit configuration | **PASSED** | 11 subscribed full-log audit rules loaded from `data/auditlog_rule_data.xml` |
| Full-scope regression | **PASSED** | `scripts/verify_full_scope.py` returned `VERIFIED LOCALLY` after final image rebuild |
| Closed-period posting | **PASSED** | `closed_period_post_blocked: true` |
| Period reopen authorization | **PASSED** | Read-only reopen blocked; Administrator reopened and reclosed the synthetic period |
| Recurring journal | **PASSED** | One posted generated entry; second run did not duplicate (`move_id: 70`) |
| Recurring invoice | **PASSED** | One posted customer invoice; second run did not duplicate; total `125.00` (`move_id: 71`) |
| Concurrent idempotency | **PASSED** | Two simultaneous calls for each recurring definition, payment batch, and year-end close completed; recurring count stayed `1`, the batch produced one payment, and the close kept move `91` |
| Payment batch and official-receipt guard | **PASSED** | Native payment batch posted; receipt `OR/00000001`; print rejected without BIR control |
| Approved BIR-control guard | **PASSED** | A control value with `thirdcode_bir_ack_approved = false` was rejected; company fields were restored immediately |
| Customer advance | **PASSED** | Native advance payment posted; receipt `OR/00000002` |
| Optional threshold approval | **PASSED** | Fresh over-threshold batch `4` was blocked before approval, approved, and posted; later reruns correctly observed its already-posted state |
| Credit/debit notes | **PASSED** | Native `out_refund`/`in_refund` documents classified correctly (`99`, `100`) |
| Employee reimbursement surface | **PASSED** | Native `hr.expense` draft created and removed through ORM |
| Bank statement-line status | **PASSED** | Synthetic line reports `unreconciled`; posted source records were retained |
| Manual bank reconciliation | **PASSED** | Paper/PDF evidence model reconciled at difference `0.00` |
| Numbering control | **PASSED** | Synthetic journal validation returned `no_gap_validated`; observed sequence holes false |
| Year-end retained earnings | **PASSED** | Native closing entry `91` posted and native reversal `94` posted |
| Report sample/tax profile/migration batch | **PASSED** | Synthetic sample approved, tax profile configured, migration batch reconciled with zero errors |
| Audit immutability | **PASSED** | Audit-log write and unlink both blocked; M1 audit rows contained user/timestamp metadata and prior/new field values |
| Milestone 1 regression | **PASSED** | `scripts/verify_milestone1.py` returned `VERIFIED LOCALLY`; invoice/bill balances, role matrix, period reopen authorization, audit traceability, soft-lock behavior, and PDFs passed |
| Encoder report restriction | **PASSED** | `m1.encoder` was rejected when creating a trial-balance wizard; Accountant and Read-only report exports remained available |
| M1 rendered reports | **PASSED** | Partner statement `34,567` bytes; general ledger `84,711` bytes; trial balance `24,844` bytes; provisional balance sheet `27,499` bytes and P&L `23,954` bytes |
| Accountant report permissions | **PASSED** | `m1.accountant` created/exported the partner statement (`34,567` bytes), trial balance (`24,844` bytes), and general ledger (`84,711` bytes) through web report wizards |
| Read-only report permissions | **PASSED** | `m1.readonly` exported the partner statement (`34,567` bytes), trial balance (`24,844` bytes), and general ledger (`84,711` bytes) through transient report wizards while remaining blocked from accounting-record mutations |
| Standard OCA report exports | **PASSED** | Accountant and Read-only exported aged partner balance, journal ledger, open items, and VAT report PDFs through the OCA transient wizards |
| Financial statement reports | **PASSED** | Accountant exported provisional balance-sheet (`27,499` bytes; balance check `0.00`), profit-and-loss (`23,954` bytes; net result `1,365.00`), and cash-movement (`23,270` bytes) PDFs; Encoder creation and configuration validation were blocked |
| Full-year financial-report timing | **PASSED** | Synthetic 2026 balance sheet, P&L, and cash-movement PDFs rendered in `6,793.07 ms`, within the proposed `30,000 ms` target; client volume remains untested |
| Guarded custom invoice/receipt PDF render | **PASSED** | With temporary synthetic approved-control/signatory values that were restored immediately: invoice `24,672` bytes and official receipt `20,497` bytes; no client/BIR value was retained |
| Migration validator | **PASSED** | Six-file final synthetic fixture: no errors, opening totals `12.00/12.00`, transaction totals `75.00/75.00`, deterministic source hash |
| Migration dry run | **PASSED** | Returned `DRY RUN` and created no Odoo records |
| Migration apply/idempotency | **PASSED** | First apply created 3 accounts, 1 partner, and 2 moves; repeated apply created 0 and skipped 3 accounts, 1 partner, and 3 moves |
| Migration source identifiers | **PASSED** | A second synthetic six-file package persisted source IDs on 4 accounts, 1 partner, and 2 posted moves; repeat apply created 0 masters/moves |
| Backup creation | **PASSED** | Database custom archive, filestore, read-only config, image metadata, and hash manifest created |
| Backup verification | **PASSED** | Manifest hashes, `pg_restore -l`, and filestore tar listing verified |
| Disposable restore | **PASSED** | Restored database contained 63 installed modules; restored filestore contained 513 files; disposable target was dropped afterward |
| Synthetic performance | **PASSED** | Two workers, 10 iterations, native save/post; save p95 `545.20 ms`, post p95 `329.70 ms`, both within proposed `2,000 ms` targets |
| Browser UI journey | **PASSED (desktop)** | Codex local browser rendered the TCSI dashboard and opened a new customer-invoice form without an Odoo promotion/error surface; Chrome DevTools mobile emulation was unavailable, so responsive device coverage remains partial |
| Real MYOB extraction and mapping | **NOT TESTED** | No authorized export was available |
| Real parallel month | **NOT TESTED** | Requires source data and named client users |
| Client report/sample acceptance | **BLOCKED — CLIENT DECISION** | Signed SOA, financial statements, invoice, official receipt, and reconciliation samples are absent |
| BIR/EIS/tax acceptance | **BLOCKED — CLIENT DECISION** | Accountant-owned classification, values, and legal review are absent |
| Production on-premise performance/backup | **NOT TESTED** | Client hardware, second device, RPO/RTO, and restore owner are absent |

## Synthetic data integrity notes

The verifiers use supported Odoo ORM/XML-RPC operations. Draft probes are
removed; posted probes, reversals, benchmark invoices, migration moves,
credit/debit notes, threshold-approved payments, and statement lines remain in
the disposable database because posted accounting records are not deleted.
The database must not be treated as client opening data.

The custom Administrator is an application role and is not granted Odoo's
technical Administration/Access Rights group. The verifier uses the local
technical `admin` only to seed test users and temporarily set the optional
company approval configuration; payment submission, approval, and posting are
performed by the custom business Administrator.

## Reproduction

From the repository root:

```powershell
Copy-Item .env.example .env
.\scripts\bootstrap.ps1
$py = 'C:\Users\MSI\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py .\scripts\verify_full_scope.py
& $py .\scripts\verify_milestone1.py
& $py .\scripts\benchmark.py --url http://localhost:8069 --database thirdcode_accounting --login m1.administrator --password M1-administrator-pass --iterations 10 --workers 2 --post
```

The bootstrap command is for a disposable local database. Production backup,
restore, MYOB migration, report sign-off, regulatory registration, parallel
run, and cutover require the client-owned gates in
[`docs/decisions-and-blockers.md`](decisions-and-blockers.md) and
[`docs/cas-control-pack.md`](cas-control-pack.md).
