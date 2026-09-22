# TCSI platform deployment

## ORVEXA local task engine

ORVEXA presents supported commands as a chat conversation with inline draft
review/confirmation. Enter sends a message; Shift+Enter inserts a new line.
The chat transcript is held only while the dialog is open, not stored in browser
storage. Existing server-side activity memory and task proposals remain persistent.
The chatbot interface does not add general language inference or change permissions.

ORVEXA uses deterministic, allowlisted commands inside the accounting server;
it does not call an AI provider or require a model. It is not an unrestricted
natural-language agent. Supported requests are `show overdue invoices`,
`find "customer or invoice reference"`, `show recent activity`, and
`draft invoice for "Customer" with 2 x "Product" at 100`. Exact customer and
product names and a single sales journal are required. Unsupported or compound
requests are not executed. The UI explains the supported forms.

Draft proposals expire after ten minutes and require an explicit confirmation.
Execution checks current role, company, record rules and referenced record versions;
confirmation retries are serialized and cannot create a second invoice. No tool
posts entries, transfers money, sends invoices or deletes business records.
Only proposal/activity metadata uses elevated access; accounting CRUD does not.
The session API is `POST /thirdcode_accounting/orvexa` (JSON-RPC), with a valid
session CSRF token and authorized `company_id`. Proposal confirmation takes only
the server-created ID, not client-supplied financial values.

Organization memory records committed invoice, bill and journal-entry changes
from deployment onward; it is not a retrospective archive or whole-application
surveillance. Each read rechecks current record access. Own task history persists
across sessions. Notifications contain invalidation hints only, refresh the open
panel after 250ms, and use the existing authenticated WebSocket relay. A 15-second
poll while visible recovers missed notifications. The UI shows snapshot time and
connection failure; exact one-second freshness is not guaranteed.

Version 18.0.2.6.0 adds two metadata tables. Startup upgrades the custom module
before accepting traffic when its numeric manifest version exceeds the installed
version. Take a database/filestore snapshot before this release. On failure, the
new instance must remain unready; roll back its image without dropping tables.
Existing financial data is preserved. Local and CI integration tests use disposable
databases; do not run synthetic write tests against customer books.

## Hosted pilot (approved deployment architecture)

The customer pilot uses the existing TCSI-branded accounting engine. The new
portal is deployed separately; it is not the replacement ledger.

```text
Vercel portal -> Railway TCSI Accounting -> dedicated Railway Postgres + filestore
     |
     +-> Supabase Auth connectivity (no live accounting schema)
```

- Portal: https://tcsi-accounting-portal.vercel.app
- Customer login: https://tcsi-accounting-portal.vercel.app/web/login
- Railway origin (operations/recovery): https://tcsi-accounting-production.up.railway.app/web/login
- Railway project: `4af92f83-8aa1-4135-9eeb-c6bcf9f7cbc8`, production environment.
- Vercel team: `pavi-2e9809a4`, project `tcsi-accounting-portal`, root `apps/web`.
- Supabase project: `zcalwevgunkevwzficvm`.

Set `TCSI_PORTAL_ONLY=true` in Vercel. The portal links to `/web/login` on its
own domain. Engine paths use external CDN rewrites to Railway; they bypass
Next middleware body buffering and shared caching is disabled. Sessions remain
host-only on the customer domain. The origin still performs authentication and
authorization. Do not replace these rewrites with a catch-all that exposes the
unfinished standalone app. Portal mode blocks its API routes and redirects its
pages to the entry page. `/api/readiness` probes Supabase Auth; it does not certify ledger
correctness. Do not switch portal mode off for customer use until standalone
accounting has passed its release gates.

`/websocket` uses a small same-origin Vercel Function relay because external CDN
rewrites do not preserve the accounting WebSocket handshake. It forwards only
the existing session cookie to the fixed Railway origin, enforces Origin checks,
bounds buffers, and reconnects before the function duration limit. Railway remains
the authorization and subscription authority. This uses Vercel's beta WebSocket
API and requires Fluid Compute; verify a real handshake and notification delivery
after each runtime/provider change. `/websocket/*` HTTP endpoints still use rewrites.
The Railway URL remains available for operational recovery if Vercel is unavailable.
Legacy `/odoo` bookmarks redirect to `/workspace` at both the Vercel edge and
the accounting controller. Client-generated workspace links use the same prefix,
including query-only URLs. Routing/branding regression tests protect these paths.
Production `web.base.url` is `https://tcsi-accounting-portal.vercel.app` and
`web.base.url.freeze` is `True` so administrative origin logins do not change
generated customer links back to Railway.

Railway uses `docker/odoo/Dockerfile` and start command
`python3 /opt/tcsi/cloud_start.py`, with `/web/login` as its health check.
New Railway services no longer accept the legacy `railway.json` mechanism;
configure these service settings explicitly. Set `RAILWAY_DOCKERFILE_PATH`,
`RAILWAY_RUN_UID=0` (the bootstrap immediately drops to the odoo user),
`PORT=8069`, and mount a persistent volume at `/var/lib/odoo`.
Set `PGHOST`, `PGPORT`, `PGDATABASE=tcsi_pilot`, `PGUSER=tcsi_app`, and
`PGPASSWORD` in Railway. The application role must not be a superuser.
Provision `pg_trgm` and `unaccent` in its empty database using the database
administrator. Do not expose the database over public TCP.

`TCSI_ADMIN_LOGIN`, `TCSI_ADMIN_PASSWORD`, and `TCSI_MASTER_PASSWORD` live only
in Railway variables. Bootstrap initializes a fresh database and sets the
first administrator once; restarts do not reset credentials. Database listing
is disabled. No local customer records or shared demo credentials are copied.
Run `python scripts/validate-odoo-package.py` before uploading; module XML data
must not be excluded by `.gitignore` or the container build context.
Vercel enforces portal mode in code, including previews with no configured flag.

The reviewed Supabase portal migrations have been applied to the project:
the tenant foundation, website demo-request intake, platform-owner access
boundary, and explicit function-grant hardening. Never run an unreviewed bulk
migration push against this project. The event-trigger hardening revokes public
execution without disabling automatic RLS.

The marketing routes are `/`, `/platform`, `/controls`, `/pilot`, and
`/contact`; each is a real page rather than a hash-scroll section. `/contact`
accepts a company demo request and writes only a `new` website lead. The
separate `/login` route is the Supabase platform-owner sign-in; `/web/login`
remains the customer accounting-engine sign-in.

Platform ownership is deliberately singleton and server-enforced. The
`platform_owner_access` table can contain one assigned Supabase user, and the
analytics RPCs require that authenticated user before returning cross-tenant
metrics. Customer organization owners remain limited to their own workspace.
Create the owner's Supabase Auth user first, then assign that user through a
reviewed administrative database operation. Do not add a service-role key to
Vercel or the browser.

Rollback: restore the last verified application deployment through the provider.
Keep database and filestore volumes intact. A code rollback does not roll back
database changes. Before customer onboarding, configure paired database and
filestore backups, test restoration into an isolated environment, and approve
retention/RPO/RTO. Do not import real company records until those gates pass.

## Future standalone architecture (not released)

### Verified pilot infrastructure — 2026-09-22

Railway's GitHub-linked engine deployment and GitHub quality gates passed.
Administrator authentication passed on the fresh pilot database. The separate
portal returned healthy responses; unfinished ledger APIs returned 404 and
unfinished pages redirected to the portal. Eight portal-boundary tests cover
the hosted restrictions, including missing preview configuration.

Both Railway volumes have DAILY backups with six-day retention, and manual
`Pilot launch baseline` snapshots exist. A logical database dump was restored
to an isolated database with the TCSI module installed and zero accounting
entries. A filestore archive was extracted and byte-compared successfully.
Only the disposable verification database and scratch files were removed.
The temporary deployment SSH key was revoked and deleted after verification.
These checks do not constitute a full on-premise recovery rehearsal or client
accounting acceptance.

The release author email must match an authorized Vercel team identity. The
owner confirmed `kurtgavin.design@gmail.com` for release commits; do not rewrite
shared Git history to change older authors. Keep concurrent frontend debugging
changes out of deployment until reviewed and tested. Customer acceptance and
the reported local interaction-freeze fix remain separate release gates.

The planned standalone product path is:

```text
Vercel (apps/web)  ->  Supabase Auth / Postgres / Storage
                           ^
Railway (apps/worker) -----+
```

The existing accounting engine remains the pilot's system of record until
the standalone workflows have accounting parity and receive acceptance.

## Supabase

For future standalone environments only, create a project per environment. Review the files in
`supabase/migrations/` using the Supabase CLI or the project SQL editor. The
foundation migration creates tenant-scoped accounting tables, membership
checks, role-aware write policies, immutable audit reads, and an idempotent job
run table.

Required web values:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

Required worker values:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` (Railway secret only; never a Vercel/browser value)

Run the Supabase security advisors after applying migrations. Every exposed
table must remain RLS-enabled, and policy changes must be reviewed with a
member of each workspace role. Configure point-in-time recovery and an
encrypted external backup destination before production acceptance; a database
being hosted by Supabase is not, by itself, an external backup plan.

## Vercel

Configure the project with root `apps/web` and these build settings:

- Install command: `cd ../.. && npm ci`
- Build command: `cd ../.. && npm run build:web`
- Node.js: `22.12` or newer
- Framework: Next.js

Set `NEXT_PUBLIC_APP_ENV`, `NEXT_PUBLIC_APP_URL`, and the two publishable
Supabase values in the Vercel environment settings. Preview and production
should use separate Supabase projects or explicit isolated environments. Do
not add `SUPABASE_SERVICE_ROLE_KEY` to Vercel. Attach the approved custom
domain so Vercel terminates HTTPS, then verify `/api/health` and
`/api/readiness` after each promotion.

## Railway

Do not deploy the unfinished worker for the pilot. A future worker service uses
`docker/worker/Dockerfile`; it is a long-running Node 22
service, not a serverless request handler.

Set:

- `WORKER_ENV=production`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `WORKER_POLL_INTERVAL_MS`

Railway should probe `/health`, restart on failure, and keep `/ready` private
or protected by the platform network. The worker refuses to start in
production when its Supabase secrets are missing. Scheduled accounting jobs
must claim a unique `(job_name, run_key)` before writing any business record;
retries must treat a duplicate key as an already-claimed run.

## CI and release gates

`.github/workflows/ci.yml` runs install, lint, typecheck, tests, migration
structure validation, web/worker builds, and high-severity dependency audit.
Store deployment tokens only in provider/GitHub secret stores. A release is
not accepted until the deployed web health route, worker health route, auth
flow, tenant isolation, responsive journeys, and migration status are checked.

## Still required before client cutover

This repository now contains deployable foundations, but the following need
real client/provider decisions and cannot be invented in code:

- Supabase, Vercel, and Railway project IDs, domains, owners, and secrets;
- external encrypted backup destination, retention, RPO/RTO, and restore proof;
- tax/BIR/EIS configuration and signed report samples;
- authorized MYOB export, mapping, opening-balance reconciliation, and a
  parallel accounting month;
- production role matrix, named-user acceptance, security review, and go-live
  approval;
- remaining accounting vertical slices: posting, invoices, payments,
  reconciliation, recurring jobs, reports, and migration import.
# Customer-facing branding releases

The accounting engine retains its upstream package names, exception identifiers,
diagnostic traces, and license notices. TCSI branding is implemented through the
custom addon's inherited views and client patches, not by renaming engine code.
Customer-authored accounting records and messages must not be rewritten.

After deploying a branding manifest version change, upgrade only
`thirdcode_accounting` using the module administration API, after taking database
and filestore snapshots. Verify inherited views, login, menus, and report/email
templates afterward. A source deployment alone does not apply database view changes.
To roll back these view-only changes, deactivate the affected `thirdcode_accounting`
inherited views and redeploy the previous release; do not restore the database over
new customer transactions. Keep diagnostic error details intact for support.

Run `node --test scripts/test-branding.mjs` to check the branding mutation-loop
regression before deploying. The workspace observer must never rewrite unchanged
text, and human chat windows must retain their original identities.
