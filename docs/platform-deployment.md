# TCSI platform deployment

## Hosted pilot (approved deployment architecture)

The customer pilot uses the existing TCSI-branded accounting engine. The new
portal is deployed separately; it is not the replacement ledger.

```text
Vercel portal -> Railway TCSI Accounting -> dedicated Railway Postgres + filestore
     |
     +-> Supabase Auth connectivity (no live accounting schema)
```

- Portal: https://tcsi-accounting-portal.vercel.app
- Pilot: https://tcsi-accounting-production.up.railway.app/web/login
- Railway project: `4af92f83-8aa1-4135-9eeb-c6bcf9f7cbc8`, production environment.
- Vercel team: `pavi-2e9809a4`, project `tcsi-accounting-portal`, root `apps/web`.
- Supabase project: `zcalwevgunkevwzficvm`.

Set `TCSI_PORTAL_ONLY=true` and `TCSI_PILOT_URL` in Vercel. Portal mode blocks
all unfinished standalone API routes and redirects non-portal pages to the
entry page. `/api/readiness` probes Supabase Auth; it does not certify ledger
correctness. Do not switch portal mode off for customer use until standalone
accounting has passed its release gates.

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

Only `restrict_rls_event_trigger_execute` has been applied to the Supabase
portal project. The standalone foundation migration has NOT been applied.
Never run an unreviewed bulk migration push against this project. The event
trigger hardening revokes public execution without disabling automatic RLS.

Rollback: restore the last verified application deployment through the provider.
Keep database and filestore volumes intact. A code rollback does not roll back
database changes. Before customer onboarding, configure paired database and
filestore backups, test restoration into an isolated environment, and approve
retention/RPO/RTO. Do not import real company records until those gates pass.

## Future standalone architecture (not released)

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
