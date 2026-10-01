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

## Hosted platform verification — 2 October 2026

Verified from the repository checkout against the deployed hosting: the Vercel
production portal (`tcsi-accounting-portal`), the Railway pilot engine
(`tcsi-accounting-production`), and Supabase project `zcalwevgunkevwzficvm`.
All probe records were removed after each check; the hosted systems carry no
test data. These checks prove platform wiring, tenant isolation, and role
enforcement. They are not a substitute for the client accounting acceptance in
section 5 of the user guide.

| Check | Result | Evidence |
| --- | --- | --- |
| Quality gates | **PASSED** | `npm ci`, `npm run lint`, `npm run typecheck`, `npm test` (60 tests: contracts 4, worker 2, web 54), `npm run validate:migrations`, `npm run build`, `npm audit --audit-level=high` — zero findings after upgrading Next.js to 16.3.8 (GHSA-vcvr-r3jv-pc5j) |
| CI on pushed commit | **PASSED** | GitHub Actions run for `ea3ac40`: `verify` and `orvexa-integration` (Odoo Docker suite with the ten-company isolation tests) both succeeded |
| Provider deployments | **PASSED** | Commit `ea3ac40` produced a Vercel Production deployment and a Railway engine deployment; both commit statuses report success |
| Supabase migration history | **PASSED** | Repository files reconciled to the applied versions (`20260922090204` … `20260927172751`); `supabase db push --dry-run` reports `Remote database is up to date` |
| Supabase schema hardening | **PASSED** | 14 public tables with RLS enabled and forced, 29 policies, verified directly via `pg_class`/`pg_policies`; `create_workspace` revoked from `authenticated`, `rls_auto_enable` revoked from `anon`/`authenticated` (pg_proc ACL audit) |
| Multi-tenant RBAC matrix | **PASSED 25/25** | `npm run verify:rbac` against the hosted project: two probe organizations, six probe users, full role matrix; every assertion rolled back and all probe rows deleted |
| Cross-organization isolation | **PASSED** | Owner B could not read, write, or rename anything in organization A (and vice versa): workspace, chart of accounts, invoices, and journal entries all filtered to zero rows or rejected |
| Role enforcement | **PASSED** | Viewer read-only; encoder may create drafts but cannot update accounts, post entries, or forge `created_by`; accountant may update accounts and post; owner may rename the organization; deletes are denied for every role |
| Anonymous surfaces | **PASSED** | `anon` cannot read accounting tables, leads, or the platform-owner table; may insert one website lead per submission and cannot read leads back |
| Platform-owner gating | **PASSED** | Non-owner customers receive `Platform owner access required`; `platform_owner_access` is unreadable to customers |
| Portal pages | **PASSED** | `/`, `/platform`, `/controls`, `/pilot`, `/contact`, `/login`, `/owner`, `/web/login` all return 200; standalone accounting pages and APIs redirect or 404 in portal mode |
| Portal readiness | **PASSED** | `/api/readiness` → `{"status":"ready","mode":"pilot_portal","checks":{"supabaseAuth":true,"accountingEngine":true}}` |
| Website lead intake | **PASSED** | Live `POST /api/demo-requests` returned 201 and the row appeared in `demo_requests`; the probe row was deleted afterwards |
| Platform owner bootstrap | **PASSED** | `scripts/bootstrap-platform-owner.mjs` created a probe owner, verified password sign-in through Supabase Auth, and `/api/platform/analytics` returned 200 with a real session through the deployed portal; `/owner` rendered the analytics view; probe user and assignment removed afterwards |
| Engine availability | **PASSED** | Odoo 18.0 engine answers `/web/login` (200) and `/web/webclient/version_info` reports `18.0-20260908` |

### Team readiness verification — 2 October 2026 (evening)

| Check | Result | Evidence |
| --- | --- | --- |
| Production role accounts | **PASSED** | All four named logins (`administrator@`, `accountant@`, `encoder@`, `readonly@tcsi.local`) authenticate against the hosted engine (uids 6–9), both directly and through the portal origin, each holding the correct TCSI role group and the Third Code Solutions Inc. company assignment |
| Company currency | **PASSED** | PHP activated through the pilot Administrator session; the hosted company previously defaulted to USD with no country set |
| Company baseline automation | **READY** | `scripts/configure_company_setup.py` (idempotent country/currency/chart/journals/period provisioning over the engine API) added; execution requires the engine administrator login (`pilot-admin@thirdcodesolutions.com`, the Railway `TCSI_ADMIN_*` account), which this workspace does not hold |
| Portal set-password flow | **PASSED (deployed)** | `/auth/confirm` token-hash route deployed at commit `f01e92e` (invalid tokens redirect to `/login?state=link_invalid`; verified live); `/login?mode=update` and `/login?state=link_invalid` return 200; recovery and invite email templates updated to the `{{ .TokenHash }}` pattern (verified through the Management API) |
| Platform-owner account | **PASSED (created)** | Auth user created for the approved owner address through the GoTrue admin API without a password; `platform_owner_access` points at it (exactly one row). The first set-password email is pending the project email sender's rate-limit window; afterwards `/login` → `/owner` serves the cross-tenant analytics console |

Still open after this verification:

- The hosted engine company still needs its chart of accounts, journals, and
  open period — now one reviewed, idempotent command
  (`scripts/configure_company_setup.py`) to be run once the engine
  administrator credentials (`pilot-admin@thirdcodesolutions.com` / the Railway
  `TCSI_ADMIN_*` values) are supplied. Tax profiles, BIR values, and
  report-sample approvals remain accountant-owned and must not be invented.
  Then run `scripts/check_company_readiness.py` and section 1 of the user
  guide for acceptance.
- The first set-password email for the owner address is queued behind the
  project email sender's rate limit. Either wait for the window to clear and
  press "Forgot password?" on the live `/login`, or re-run
  `node scripts/bootstrap-platform-owner.mjs --email <approved-address> --send-recovery`.
