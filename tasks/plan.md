# Implementation Plan: TCSI Accounting Platform

## Objective

Replace the current Odoo-bound runtime with a TCSI-owned accounting platform
that can run as a Vercel web application, use Supabase for Postgres/Auth/
Storage, and run scheduled accounting workers on Railway. The existing Odoo
implementation is treated as a migration reference and temporary compatibility
surface until the standalone workflows reach parity; it is not part of the new
runtime path.

## Architecture decisions

- **Web:** Next.js App Router in `apps/web`, deployed to Vercel. The browser
  receives only publishable Supabase configuration; privileged keys remain
  server-side.
- **Data and identity:** Supabase Postgres, Supabase Auth, and Supabase
  Storage. Every exposed table is protected by Row Level Security and tenant
  membership is checked server-side.
- **Workers:** TypeScript worker in `apps/worker`, deployed as a long-running
  Railway service for recurring journals, invoice runs, audit delivery, and
  backup orchestration. It must fail closed when production secrets are absent.
- **Contracts:** Shared Zod schemas and explicit API response envelopes keep
  Vercel route handlers and Railway jobs compatible without importing legacy
  framework models.
- **Operations:** Environment-only secrets, health/readiness endpoints,
  structured logs, CI quality gates, immutable migration files, and an
  explicit rollback/backup runbook.
- **Brand:** TCSI Accounting / Third Code Solutions Inc. is the product
  identity. Legacy framework names are not used in the new UI, package names,
  API routes, or runtime copy.

## Dependency graph

```text
Supabase migrations + RLS
        |
        +--> shared contracts and server data access
                    |
                    +--> Vercel web routes and dashboard UI
                    |
                    +--> Railway worker and scheduled accounting jobs
```

## Phase 1 — standalone foundation

- [ ] Create the Vercel-compatible Next.js web app with TCSI shell, responsive
      navigation, dashboard states, error/loading boundaries, and health route.
- [ ] Create the Supabase migration baseline for workspaces, memberships,
      accounts, journal entries, entry lines, counterparties, invoices, and
      audit events with tenant-scoped RLS.
- [ ] Create shared runtime environment validation and API contracts; fail
      clearly when required production variables are missing.
- [ ] Create the Railway worker image, health endpoint, graceful shutdown, and
      idempotent job contract.
- [ ] Add CI for install, lint, typecheck, tests, build, migration validation,
      and dependency audit without storing secrets.

### Checkpoint: foundation

- [ ] `npm ci` and all quality gates pass.
- [ ] Vercel build succeeds without Odoo assets or server dependencies.
- [ ] Supabase migrations apply cleanly with RLS enabled.
- [ ] Web and worker health checks return success with configured test env.

## Phase 2 — accounting vertical slices

- [ ] Workspace authentication, membership, role matrix, and audit events.
- [ ] Chart of accounts, journals, accounting periods, and balanced journal
      entry posting with closed-period protection.
- [ ] Customer/supplier directory and invoice/bill lifecycle.
- [ ] Payments, batches, official-receipt metadata, and approval controls.
- [ ] Bank statement import/reconciliation and evidence attachments.
- [ ] Recurring journals/invoices with unique run keys and worker scheduling.
- [ ] Financial statements and CSV migration validation/import with source IDs.

### Checkpoint: accounting core

- [ ] Balanced posting and authorization tests pass against a disposable
      Supabase project.
- [ ] Repeated worker delivery cannot duplicate accounting records.
- [ ] Dashboard totals reconcile to the same journal-entry source.
- [ ] Responsive browser journeys pass at 320, 768, 1024, and 1440px.

## Phase 3 — production operations and migration

- [ ] Replace hard-coded legacy development credentials with managed secrets
      and remove the legacy runtime from the deployment path.
- [ ] Configure HTTPS/domain, CORS allowlist, CSP/HSTS, rate limits, health
      probes, logs, error reporting, and resource limits.
- [ ] Configure encrypted external backups and restore verification with named
      RPO/RTO owners.
- [ ] Import authorized MYOB data, reconcile opening balances, and complete a
      parallel accounting month.
- [ ] Obtain signed report samples, tax/BIR/EIS decisions, role approval, and
      client acceptance evidence.
- [ ] Remove legacy Odoo source/config/docs from the product branch only after
      standalone parity and an archived migration reference are verified.

## Risks and mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Accounting parity gaps during framework replacement | High | Keep the reference implementation read-only, migrate one vertical slice at a time, and reconcile balances before removing it. |
| Tenant data exposure through Supabase Data API | Critical | RLS on every exposed table, membership predicates, server-side authorization, and advisor checks. |
| Duplicate scheduled postings | High | Unique source/run keys, database constraints, idempotent worker jobs, and retry tests. |
| Missing production secrets or provider access | High | Fail-closed env validation and deployment checklists; never use fallback credentials. |
| Unapproved tax/regulatory assumptions | High | Keep tax/BIR/EIS states provisional until accountant-owned values and signed samples exist. |

## Current boundary

The existing local Odoo stack remains available as a development reference
until Phase 3 parity is proven. It is not evidence that the new Vercel,
Supabase, or Railway application is production-ready.
