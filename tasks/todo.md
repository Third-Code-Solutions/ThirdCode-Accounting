# TCSI Accounting Platform checklist

## Phase 1 — foundation

- [ ] Create `apps/web` Next.js App Router application with TCSI design system.
- [ ] Create `apps/worker` Railway-compatible TypeScript worker.
- [ ] Add Supabase migrations and tenant-scoped RLS policies.
- [ ] Add shared environment validation and API contracts.
- [ ] Add Vercel, Railway, and CI configuration without committed secrets.
- [ ] Add health/readiness, structured logs, and failure-safe startup.

## Phase 2 — accounting vertical slices

- [ ] Auth, workspace membership, and role authorization.
- [ ] Chart of accounts, journals, periods, and balanced posting.
- [ ] Invoices, bills, payments, batches, and receipt metadata.
- [ ] Bank reconciliation and evidence storage.
- [ ] Recurring accounting jobs and idempotent worker retries.
- [ ] Reports, migration validation/import, and audit history.

## Phase 3 — hosting and cutover

- [ ] Replace all development credentials with platform-managed secrets.
- [ ] Configure HTTPS, custom domain, CORS, CSP/HSTS, rate limits, and probes.
- [ ] Configure encrypted external backups and restore verification.
- [ ] Complete MYOB mapping, tax/BIR/EIS approval, report samples, and role
      sign-off.
- [ ] Complete client acceptance and only then remove legacy Odoo runtime files.

## Evidence gates

- [ ] `npm ci`
- [ ] `npm run lint`
- [ ] `npm run typecheck`
- [ ] `npm test`
- [ ] `npm run build`
- [ ] `npm audit --audit-level=high`
- [ ] Supabase migration/RLS verification
- [ ] Browser checks at 320/768/1024/1440px
- [ ] Worker idempotency and rollback checks
