# Full local verification

## 28 September 2026 isolated pilot checks

These checks used the `ThirdCode-Accounting-pilot-release` checkout and synthetic
databases. They did not alter the hosted `tcsi_pilot` ledger.

| Check | Result | Evidence |
| --- | --- | --- |
| Client demo restart and accounting acceptance | **PASSED** | `scripts/start_client_demo.ps1` started the isolated `tcsi_demo` containers; `check_client_demo.py` passed for five fictional companies, ten or more posted documents, five restricted accountant logins, payment batches, recurring entries, bank reconciliation, and 15 financial reports. The fixture date was 28 September 2026. |
| Saved fixture date regression | **PASSED** | `python scripts/test_check_client_demo.py`: two tests passed; saved demo data does not expire merely because the workstation date advances. |
| Addon package | **PASSED** | `python scripts/validate-odoo-package.py`: 47 resources validated. |
| Fresh Odoo installation and full addon suite | **PASSED** | Isolated `tcsi_readiness_20260928` database on PostgreSQL 16 / Odoo 18: 33 post-install tests, zero failures or errors. |
| Employee expense through reimbursement | **PASSED** | Native expense submitted, approved by its assigned expense manager, posted by Accountant, and paid through the bank journal; an unassigned Accountant was denied approval. The test uses synthetic data and does not approve a company reimbursement policy. |
| Hosted company configuration preflight | **BLOCKED** | Read-only preflight of `tcsi_pilot` found one visible company, no chart accounts or required journals, no open period or tax profile, and no approved samples or assigned control/backup owners. Portal and Odoo service health do not prove financial readiness. |
| Hosted company legal identity | **BLOCKED** | The live company has no country or legal identifier recorded and currently uses USD. The intended country, book currency, and registration details require company approval before any live change. |
| Production backup schedules | **PASSED** | Railway lists daily six-day backup schedules for both the PostgreSQL and Odoo filestore volumes; current database and prior-day filestore snapshots exist. |
| Fresh paired Railway snapshot | **BLOCKED** | Railway rejected creation of a new database volume snapshot with `Plan limit of 10 backups per volume exceeded`; no new volume snapshot was created and existing backups were left intact. |
| Fresh paired logical backup and isolated restore | **PASSED** | A PostgreSQL custom dump and Odoo filestore archive were copied from the live container into `private-pilot-access/bookkeeping-prep-20260928` outside Git with a private hash manifest. Remote and local SHA-256 hashes matched. PostgreSQL 18 restored the dump in a disposable container with no network; it contained one company, zero posted moves, and addon version `18.0.2.7.4`. Every one of its 558 stored attachment references appeared in the 883-entry filestore archive. The disposable restore container was stopped and removed. |
| Temporary backup cleanup | **BLOCKED** | Automatic command review refused deletion of two temporary `/tmp/tcsi-bookkeeping-20260928-*` files on the live container and the revoked temporary SSH key files on this workstation. The Railway SSH key registration was removed and confirmed absent; no live access remains through that key. |

## 21 September 2026 local baseline

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

Still open after this verification (superseded in part on 3 October 2026 — see the trial-launch verification below):

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

### Trial launch verification — 3 October 2026

| Check | Result | Evidence |
| --- | --- | --- |
| Token-gated provisioning endpoint | **PASSED (live)** | `POST /tcsi/setup` on the Railway engine: wrong token → 401; valid token → status/provisioning as superuser (`uid: 1`). Plaintext token held outside the repository; only its SHA-256 is committed. |
| Pilot company baseline | **PASSED** | Third Code Solutions Inc.: PHP, Philippines, trial mode, report layout, 104-account PH chart, 7 journals, 60 taxes, FY 2026 period open. |
| Ten trial organisations | **PASSED** | Trial Client 01–10 created with the same baseline; role logins (administrator/accountant/encoder/readonly per org, 40 users); credentials recorded outside the repository. |
| End-to-end posting per company | **PASSED** | 22/22 steps for administrator@ and accountant@ (pilot) and trial01/trial02: customer → invoice post → TRIAL-watermarked print + PDF → payment → receipt (`OR/00000001+`, per company) → manual journal entry → financial report → trial balance. |
| Role guards | **PASSED** | Encoder: drafts allowed, posting denied, reports denied. Read-only: input denied, reading and report wizards allowed. Verified on the pilot and trial02. |
| Company isolation | **PASSED** | Pilot admin session rejected when addressing a trial company (`Access to unauthorized or invalid companies`); multi-company rules hold outside tests. |
| Readiness preflight (trial) | **PASSED** | `scripts/check_company_readiness.py --trial` exit 0 for all 11 companies (legal gates reported as trial-deferred, not blockers). |
| Engine stability | **PASSED (hardened)** | Intermittent stalls root-caused to single-process threaded mode; engine now prefork (`workers=2`, `limit_time_real=600`) with token-gated maintenance ops (`locks`, `terminate_idle`, `terminate_pids`). Readiness script retries transport-level connection drops. |

Notes: legal/BIR items are trial-deferred by design; no SMTP is configured, so
trial passwords are distributed and rotated out-of-band. Each push to `main`
restarts the engine — schedule pushes outside trial working hours.

### Organization management & superadmin verification — 3 October 2026 (later run)

| Check | Result | Evidence |
| --- | --- | --- |
| In-app org user management | **PASSED (live, 12/12)** | Trial Client 01 administrator, entirely through `TCSI Accounting → Organization` wizards: created an employee account, signed in as it, reset its password (old password rejected afterwards), enabled/disabled it, was refused for another company's user, refused for an encoder, listed only own-company users, and the created user carried the correct TCSI role group. Runner: `~/tcsi-private/verify_org_admin.py`. |
| Cross-tenant user visibility | **PASSED (live)** | The scoped `res.users` rule keeps each tenant's user list to its own people: Trial Client 01 sees exactly its four logins, Trial Client 02's users are invisible. |
| Platform owner (superadmin) | **PASSED (live)** | `superadmin@tcsi.local` provisioned through the token-gated endpoint (`extra_groups: [base.group_system]`, all companies): sees all 11 organizations and 47 internal users and can target any company in the New Employee Account wizard. Master credentials live in `~/tcsi-private/owner-credentials.txt` (mode 600, outside the repository); operator guide `~/tcsi-private/OWNER-GUIDE.md`. Runner: `~/tcsi-private/owner_admin.py`. |
| Superadmin hidden & protected from tenants | **PASSED (live)** | The `thirdcode_platform_owner` flag keeps the superadmin out of every tenant user list (tenant search returns none) and tenant admins are denied reset/enable/disable against it server-side ("You can only manage accounts of your own company."). Regression-checked: tenants still manage their own staff freely. |
| Backend stylesheet compile | **PASSED (fixed, deployed)** | The redesigned `tcsi_apps.scss` used lowercase `min(100%, 256px)`; libsass (both the engine's asset compiler and the CI "production Sass runtime") evaluates that as the Sass builtin and aborted the whole `web.assets_web` bundle with `Incompatible units: 'px' and '%'` — Odoo served stale fallback CSS with a red error banner. Fixed to the pass-through `Min(` form in `6606a31`; the live bundle now recompiles clean (1.3 MB, redesigned classes present, no error banner). |
| Quality gates | **PASSED** | CI run [37071399442](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/actions/runs/37071399442) at `6606a31`: `verify` and `orvexa-integration` both success (module install + full test suite incl. the new employee-management and platform-owner protection tests). Portal health reports commit `6606a31d9092`; engine serves HTTP 200. |

### Platform console verification — 3 October 2026 (later run)

| Check | Result | Evidence |
| --- | --- | --- |
| Console deployed and wired | **PASSED (live)** | Module 18.0.2.9.3; menu `TCSI Accounting → Platform Console` resolves to `ir.actions.client,480`; the superadmin's home action points at the console (`console_bootstrap.py`). |
| Console payload (live, JSON-RPC, as superadmin) | **PASSED** | `get_console_data` returns 4 KPI cards, 11 organisations with trial windows, 20 attention items, 24 recent documents and 12 sign-ins; per-organisation user counts exclude platform-owner accounts and match what each tenant itself sees (4 users on trial clients, 5 on Trial Client 01). |
| Trial lifecycle actions | **PASSED (live + unit)** | Live: pilot set to `active`, the 10 trial clients re-marked onto fresh 30-day windows. Unit tests (green in CI): extend (+7/+120 validation), convert (trial mode off), start trial, suspend (deactivates users, remembers ids) and exact resume. |
| Tenant isolation | **PASSED (live)** | Trial Client 01 administrator: console read and suspend both refused ("The platform console is reserved to the system owner."); its own user list is unchanged. Menu is invisible to role users. |
| Quality gates | **PASSED** | CI runs 37076657100, 37077197462, 37077469123, 37078195738 (`fcc3788` → `2ca9b8c`) all success. |
| Live-vs-CI note | recorded | `res.users.login_date` is a non-stored computed field on the engine's Odoo build (`18.0-20260908`) — ordering a search by it raises `ValueError` live, while the CI image's older build tolerated it (tests were green). The sign-in feed now reads `res.users.log` directly; live JSON-RPC verification is the acceptance path for console changes. |

Owner-facing documentation for the console: `~/tcsi-private/OWNER-GUIDE.md` § 6.

### TCSI design-system unification — 3 October 2026 (later run)

| Check | Result | Evidence |
| --- | --- | --- |
| Canonical token layer | **PASSED (source + compile)** | New `tcsi_tokens.scss` declares the palette once (light + dark) and is loaded first in `web.assets_backend` and `web.assets_frontend` (manifest 18.0.2.9.4). `tcsi_routes.scss` now reads the shared tokens instead of local hexes; the retired values (`#fbfbfd`, `#1d2b33`, `#6b48d8`, …) are gone from the route layer. |
| Addon stylesheet compile | **PASSED** | Every addon stylesheet compiled standalone and as a bundle with libsass 3.6.6 — the runtime Odoo's asset compiler uses — ten stylesheets, 236,251 bytes of CSS, no errors. An SCSS error aborts the whole bundle and serves stale fallback CSS, so this is the gate that matters. |
| Token parity portal ↔ addon | **PASSED (8/8)** | `scripts/test-design-tokens.mjs` (wired into CI) compares the light and dark palettes, shared radii, bundle order, route-layer token usage and the dashboard reference rules between `apps/web/app/globals.css` and `tcsi_tokens.scss`. |
| Portal dark theme | **PASSED (rendered)** | `apps/web/app/globals.css` gained a `prefers-color-scheme: dark` theme built from the workspace dark palette. 84 rendered loads (14 routes × 1440/834/390 × light/dark) found no horizontal overflow, no unlabeled buttons, no clipped labels and **no light surface leaking into dark mode**. |
| Pointer targets | **PASSED (rendered, fixed)** | The rendered sweep flagged standalone links below the WCAG 2.5.8 24px minimum. Marketing and auth links plus `.topbar-link` got the minimum height/width; the same audit now reports clean on `/`, `/contact`, `/login`, `/owner`, `/controls`, `/dashboard` and the section routes (was 8/7/3/1 per page). |
| Workspace rendered verification | **BLOCKED** | No stored login for the engine origin (the vault prompt was declined) and Docker is unavailable locally, so no authenticated Odoo screen was exercised. `docs/workspace-ui-coverage.md` marks those rows `source-verified`, not rendered. |
| Quality gates | **PASSED** | `npm run lint`, `npm run typecheck`, `npm test` (55), `npm run build` (web + worker), `npm run validate:migrations`, `scripts/validate-odoo-package.py` (55 resources), `node --test scripts/test-*.mjs` (31) and `python scripts/test-branding.py` (3). `npm audit` could not run: this host's egress allowlist refuses the npm registry. |

Screenshots for the rendered sweeps are in `~/.hermes/cache/scratch/evidence/`
(`before-deployed/` = the deployed portal, `final2/` = this change), one PNG per
route, viewport and theme.

### Live demo-safety QA pass — 3 October 2026 (latest)

| Check | Result | Evidence |
| --- | --- | --- |
| Dedicated demo company | **PASSED (live)** | "Demo Company (TCSI)" created through the token endpoint (company id 14): PHP, PH chart (104 accounts), 7 journals, FY 2026 open, trial mode on, demo administrator provisioned; credentials in `~/tcsi-private/demo-credentials.json` (0600). The ten client slots stay reserved for onboarding. |
| Business-day E2E suite (52 checks) | **PASSED after triage** | `~/tcsi-private/qa_demo_e2e.py` on the live engine: invoice 50,000 + 12% VAT = 56,000 exact, TRIAL-marked HTML + PDF renders, partial (20,000) then full payment with automatic receipt numbers (`OR/00000001…`), 15,000 unpaid invoice for aging, bill 8,000 + VAT = 8,960 paid, journal entry + reversal (original intact), Balance Sheet / Profit & Loss / Cash Flow render marked, trial balance balanced (261,920 = 261,920), close blocked by drafts → close → posting blocked → reopen → posting restored, encoder/read-only guard probes, password reset + disable/re-enable through the wizards. The Trial Balance PDF export is verified live through the wizard's own export action (OCA reports are data-driven: `button_export_pdf` returns the prepared action, which renders as a real 16,920-byte PDF when passed as `?options=` — the exact call the web client makes; a bare `/report/pdf/...` request without those options is a 500 by design). Report: `~/tcsi-private/qa-demo-report.json`. |
| Line-level immutability gap | **FOUND & FIXED (18.0.2.9.5)** | Live probing showed direct `account.move.line` writes bypassed the move-level guard: an API client (never the UI — posted fields are readonly there) could reclassify posted amounts (`account_id`, `price_unit`, `quantity`, label) while the entry stayed balanced; ledger totals remained protected by the balance rule (`The entry is not balanced`) and reconciliation checks. The twin guard now refuses accounting fields on posted lines for non-superuser writes (drafts, sudo and the sync/reconciliation tokens exempt); unit tests in `tests/test_financial_controls.py`. Live re-probe returns "Posted accounting entries are immutable…" and a fresh invoice→payment flow re-tested green. |
| Workspace sidebar defect | **FOUND & FIXED (18.0.2.9.6)** | Rendered QA showed the finance overview reporting the native "Insights" app and rendering its 4-item leftover navigation. `renderSidebar` now falls back to the TCSI Accounting app for the dashboards root (the design workstream's fix, shipped); re-render as the demo administrator shows "TCSI Accounting" with the accounting navigation. |
| Rendered UI, authenticated | **PASSED** | Passwordless session minting + debug browser as the demo administrator on 18.0.2.9.6: dark-theme dashboard (KPI cards: receivables ₱15,001, net result ₱107,101, demo company shown as active workspace) and the invoices list with the seeded rows. Screenshots: `~/tcsi-private/qa-evidence/ui-dashboard-fixed.png`, `ui-invoices-fixed.png` (pre-fix shots kept beside them). |
| Tenant isolation (live re-check) | **PASSED** | Demo administrator: sees exactly 1 company, cannot see or read Trial Client 01's moves, console refused. Trial Client 01 administrator: demo users invisible, 1 company, console refused. |
| Owner console cross-check | **PASSED** | Console shows 12 organisations / 11 trials; the demo company row live (trial status, 30-day window, user and document counts). |

### Workspace update notices — 3 October 2026 (latest)

| Check | Result | Evidence |
| --- | --- | --- |
| Outdated-page notice sources | **DIAGNOSED (live)** | The running build raises two notices: (1) the bus reconnect watcher ("The page is out of date" / "Save your work and refresh to get the latest updates and avoid potential issues.") fires whenever the bus reconnects and `/bus/has_missed_notifications` answers true — verified live to answer true for ANY `last_notification_id` (0, 1, 100, 99999999), so every engine restart surfaced the banner even on fully current pages; (2) the assets watchdog ("The page appears to be out of date.") fires only on a genuine `bundle_changed` version mismatch. |
| Graceful-updates service (18.0.2.9.7) | **FIXED & live-verified** | The new backend service `tcsi_updates` intercepts both notices: the reconnect false alarm is suppressed; a genuine stale notice silently refreshes the tab when no work is at risk (no dirty form, dialog, blocking overlay or pending input) and keeps the native prompt when edits are pending; a 5-minute cooldown prevents reload loops. Live on 18.0.2.9.7, all branches exercised in the served client: (1) the exact stale-notice call in a clean tab auto-refreshed the session silently (no banner); (2) the same call on a dirty invoice form kept the prompt and did NOT reload; (3) the exact reconnect message produced no banner and no reload; (4) ordinary notifications still display normally (interceptor passthrough). Evidence: `~/tcsi-private/qa-evidence/ui-outdated-dirty-prompt.png`. |

**Demo company state after the QA pass:** 15 posted documents, 0 drafts, 0 cancelled (probe artifacts removed; three empty auto-saved drafts from form probing were unlinked).

### Production audit remediation — 4 October 2026 (latest)

The unauthenticated production audit (`dogfood-output/prod-2026-10-04/REPORT.md`) findings H1-H6,
M1-M8 and L1-L5 are fixed in this working tree. The per-finding table, the new system parameters
and the deploy steps are in `docs/security-hardening.md`; nothing was applied to the live systems
from this workspace.

| Check | Result | Evidence |
| --- | --- | --- |
| Addon syntax, data and package | **PASSED** | `python -m py_compile` over every model, controller and test module; `xml.dom.minidom` parse of `data/tcsi_security_data.xml`; `python scripts/validate-odoo-package.py` (57 manifest resources present and deployable); `python scripts/test-branding.py` (5 tests OK) |
| Addon install and test suite | **PASSED** | Pinned runtime image (`docker/odoo/Dockerfile`, `INSTALL_ODOO_TEST_HELPER=true`) against PostgreSQL 16 with the CI command (`-i thirdcode_accounting --without-demo=all --test-enable --test-tags /thirdcode_accounting --no-http --max-cron-threads=0`): 59 tests, 0 failed, 0 errors. The new `tests/test_auth_hardening.py` covers the committed throttle counters, blocking, clearing, window reset, the disabled limit, the login-oracle helpers, the silent password reset and the header/cookie helpers |
| Throttle counter isolation | **VERIFIED** | The counter is written on a cursor of its own and committed immediately, because `res.users._login` rolls its cursor back as soon as `AccessDenied` leaves the `with` block. Odoo opens every connection at `REPEATABLE READ`, so the tests read committed counters through a cursor of their own — exactly what the next request does in production |
| Portal checks | **PASSED** | `npm run lint` (clean); `npm run typecheck` (contracts, web, worker); `npm test` (contracts 4, worker 2, web 55 tests); `npm run build` (the route table lists `/robots.txt`, `/sitemap.xml` and `/icon.svg` as served routes) |
| Live re-verification of the engine surface | **PENDING** | The engine fixes take effect after `odoo -u thirdcode_accounting` on the running instance. The HTTP-level behaviour that needs a live server (database-manager refusal, security headers, session-cookie flags, `/favicon.ico`, `/robots.txt`, `/sitemap.xml`) was not re-probed against production from this workspace |

### Workspace audit + ORVEXA extension — 5 October 2026 (latest)

| Check | Result | Evidence |
| --- | --- | --- |
| ORVEXA command registry (18.0.2.11.0) | **SHIPPED & live-verified** | Slash commands (`/help`, `/summary`, `/overdue`, `/find`, `/draft`, `/activity`) with precise validation messages, source/limit/UTC disclosure and a `/help` command list in the chat UI (6 entries + boundaries block rendered live). CI run 37214687386 green (`verify` + `orvexa-integration`). |
| Encoder "server errors" on `/workspace` | **FOUND & FIXED** | The trial encoder role had read access to only 2 of 10 control models and hit a hard AccessError on Payment batches. Fix: read rows for the 8 missing models (`ir.model.access.csv`), Financial statements menu group, and the sidebar home guard. Live matrix 19/19 across all control models; pages open and type clean for encoder/accountant/read-only. |
| Wrong landing + wrong sidebar for trial users | **FOUND & FIXED** | Provisioned users had no `action_id`, so `/workspace` resolved the default app (Messages) and the sidebar rendered Discuss menus. Fix: `provision_user` now sets the finance overview (platform console for owners); 45 existing users swept via RPC; fresh encoder login lands on `/workspace/action-408` with the TCSI navigation. |
| Stale redirect ids in `/dashboards` | **FOUND & FIXED (18.0.2.11.1)** | `/dashboards`, `/workspace/dashboards`, `/action-307` and `/action-425` redirected to hard-coded ids; on this database 425 had become a l10n_ph server action and rendered "Oops!". Aliases now resolve `thirdcode_accounting.action_tcsi_dashboard` by XML id at request time; all four verified 303→`/workspace/action-408`. CI run 37215166753 green. |
| 10-page click-through (owner/admin/encoder/accountant) | **PASSED** | All ten control pages open, edit and save; file upload confirmed via CDP (report samples); Financial statements wizard renders editable and Export PDF returns with no server error. |
| ORVEXA draft-invoice workflow (live E2E, 18.0.2.11.2) | **PASSED 19/19** | `~/tcsi-private/verify_orvexa_e2e.py` against the demo company: preview writes nothing; another user cannot confirm the proposal; confirm creates exactly one unposted draft; retry is idempotent and now reports "This task already completed" (18.0.2.11.2); confirm after invoice removal refuses to recreate; cancel returns `cancelled` and the cancel/expired guard refuses re-confirmation; foreign company refused; read-only reads work with source/limit/timestamp disclosure and draft preparation is refused. Cancel/expiry path left no invoices; cleanup verified. Time-based expiry itself is covered by `tests/test_orvexa.py` (docker job). |


## Unmerged release preparation — 5 October 2026

- Objective: integrate the remaining readiness PR #6 and accounting release PR #7, then verify their production deployments.
- Branch inventory: only `fix/accounting-pilot-readiness` and `release/accounting-18.0.2.13.0` contain commits absent from main; the other remote branch tips are already represented.
- PR #6 was merged with current main locally. Conflict resolution retains the current financial-control tests, current documented setup, and the existing positional `trial` argument. Country/currency expectations are keyword-only. Legal identity remains a production gate and is explicitly reported as deferred in trial mode.
- Combined candidate `8f72da523db85017862becfe0b7816d9c6fbc83b` includes PR #6 and PR #7. Local saved-demo checks (2), readiness checks (4), migration policy checks (5), Python compilation, package validation (60 resources), and `git diff --check` pass. [GitHub run 37242476746](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/actions/runs/37242476746) passes platform lint/typecheck/tests/build, 110 native Odoo tests, and 59 integration checks.
- Railway browser console access resolved the operator-access blocker. Production was inspected at commit `25b91a7b68fc65b0d36618018cc48b86ca2672f3`, module `18.0.2.11.2`, PostgreSQL 18.6. Both engine and database volumes have daily Railway backups; their schedules are separate and are not treated as a coordinated recovery bundle.
- A coordinated database/filestore/runtime/configuration bundle was captured at `2026-10-04T23:09:09Z`; accounting writers were paused for 3.767 seconds and resumed. The bundle was encrypted with AES-256 CMS using a public certificate; its private key remained off-host. The encrypted bundle was downloaded outside Railway, successfully decrypted, and all 1,262 archived file hashes verified. Sensitive contents and keys remain outside Git.
- The production backup restored into a separate database and filestore in 70.406 seconds. Rehearsal used the exact candidate addon tree with the inspected production runtime and pinned OCA revisions; runtime dependency files are unchanged by this release. HTTP, cron, and outgoing mail were disabled in the copy. Upgrade to `18.0.2.13.0` completed in 43.142 seconds. Comparisons preserved original posted document IDs/names/amounts/residuals, posted lines, per-company/account balances, audit actors/timestamps/old/new values, company scope, and every referenced business attachment. No synthetic accounting transactions were written to production.
- Technical backup, restore, and representative-upgrade gates now pass. Next action: merge the reviewed candidate and confirm both hosted deployment revisions, installed module version, health, and production accounting fingerprints. Formal client RPO/RTO, recovery deputies, backup-alert ownership, Windows coverage, ten-user latency acceptance, and the parallel accounting month remain tracked acceptance work; this rehearsal does not certify them.
- Local untracked beginner-guide and live-audit files are preserved outside this release. They include production inspection evidence and have not been reviewed for publication in this public repository.

## Production alignment implementation — 5 October 2026

- Objective: audit the adopted accounting brief against current production, implement independent engineering gaps, and retain explicit client acceptance dependencies.
- Release preparation above completed: PRs #6 and #7 merged; main `7a1bc57a680ba69cc993205f0e131a8f9fbec3f7` deployed to Vercel (`dpl_GRJmhifKS1XS7xBMWDtsnGfAmn4H`) and Railway (`26fc1bc7-a18b-4b80-8f0b-7864da4cccf9`). Installed module `18.0.2.13.0`; production fingerprint preserved original accounting records, audit history and referenced attachment bytes. Private evidence remains outside Git.
- Live defect: `/websocket` reached the prefork HTTP worker on port 8069 instead of the evented worker on 8072. The resulting HTTP exception also bypassed security headers because it was not a response object. Candidate `18.0.2.13.1` routes the two services behind one supervised public listener and normalizes error responses without changing their status or content.
- Local process-failure/shutdown tests pass (3). Native error regression and a real hosted-launcher HTTP/login/WebSocket round-trip gate added to CI; runtime result pending. No production accounting transactions created by this audit.
- Next: verify this runtime slice, implement trial-balance source drilldown, expand role/action evidence, and recheck live reports/configuration. RP-04 definition, real MYOB extraction, client format approval, Windows coverage, representative workload volumes and formal acceptance remain explicit inputs rather than invented approvals.

- Expanded candidate native suite passes: 118 tests, zero failures/errors; the separate accounting integration pass remains59 checks. Trial-balance amount/source domains and active-company export checks pass. The role matrix exposed and now guards encoder reconciliation, including direct elevated ORM paths. Live read-only inventory covers48 business users;24 actual PDFs rendered across12 report variants/two companies.
- Fresh coordinated encrypted off-host backup captured at2026-10-04T23:54:28Z;3.163-second writer pause,1,283 file hashes verified after decryption. Isolated production copy `tcsi_release_20261005b` restored in69.049seconds and upgraded to13.1 in28.184seconds; original accounting, audit and482 referenced files preserved. Private evidence downloaded and retained outside Git.
- Runtime CI caught an unprivileged nginx temporary-directory failure; all temporary paths now use its private writable directory. The hosted gate is independent of the accounting suite and uses the production image without test-helper packages. Final runtime result and live deployment remain pending. The current92-row matrix and AC01–09 status are in `docs/prd-alignment-2026-10-05/LIVE-IMPLEMENTATION.md`; nightly remote delivery, representative ten-user/annual-volume performance, Windows and client inputs remain explicit.

- Final report-access expansion adds direct HTML/PDF/XLSX rendering and Statement of Account scope checks. The actual report-action context is applied in XLSX tests, matching the web client. A further representative-copy upgrade at `d376b23` took35.605seconds and preserved the original fingerprint. Live report evidence now includes25 PDFs, including an existing partner SOA.
- Hosted HTTP tests exposed Odoo18's `UpgradeRequired.get_headers` signature incompatibility with its installed Werkzeug. The WSGI error path now preserves426/body/`Sec-WebSocket-Version` directly; native and real-hosted regression gates retain assertions for this behavior. Final CI/deployment results remain pending.
