# TCSI Accounting Platform checklist

## Error dialog branding — 6 October 2026

- Objective: use TCSI in customer-facing error titles, messages and copied reports; retain diagnostic identifiers and accounting behavior.
- Reproduced: a synthetic native RPC error on production showed a TCSI detail heading but retained the original vendor's server-error text in the message and stack heading. No server mutation was used.
- Root cause: the existing patch changed titles and warnings; the shared error template and clipboard handlers still used the original message.
- Implemented: branded presentation getters, shared clipboard formatting, and a native error-template extension. Original exception payloads remain unchanged.
- Verified: three new regression tests failed before the fix; 16 branding and 8 token JS cases, 7 Python checks, package validation and scoped lint pass. Exact candidate JS/XML rendered through the native browser runtime; server/client/network dialogs, validation reason and copy behavior checked. Review approved after diagnostic-preservation fix.
- Remaining: release CI, production deployment and post-deploy browser verification.

## Form input visibility — 5 October 2026

- Objective: repair hidden editable amounts across native workspace forms, tables and dialogs; preserve permissions, computed fields and palette; deploy to production.
- Confirmed: the live monetary widget accepts focus but its positioned currency span receives an opaque background from shared input styling. Dark mode has the same override.
- Completed: isolated current `origin/main`; added a shared transparent monetary overlay rule and repeatable native CSS browser fixture.
- Verified: 220 browser checks (forms/tables/dialogs, 1440/390px, light/dark); 25 branding/token tests; 61 manifest resources; Sass compilation. Original production CSS reproduces the hidden overlay. Source review found no blocking issues.
- Pending: CI, deployment and unsaved production input checks.
- Next action: merge the reviewed release after CI, then verify live stylesheet and route interactions.

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

## Public landing page — 6 October 2026

- Objective: company-focused landing page, complete verified core features, explicit light/dark switch (light default), production deployment.
- Design contract: `docs/landing-page-design.md`.
- Base: current production/main `55c58eb`; isolated branch `codex/accounting-landing`. User documents in original checkout preserved.
- Implemented: outcome-led hero, interactive sample product preview, 12 capability groups, controls, Orvexa, rollout, FAQs, demo CTAs, shared public navigation/footer, cookie-backed server-rendered theme.
- Verified: lint/typecheck, 62 unit tests, 19 branding/palette tests, initial production build, 10 responsive size/theme checks, preview keyboard navigation, FAQ disclosure, zero axe WCAG A/AA violations in light desktop and dark mobile. Evidence: `docs/landing-page-verification.md`.
- Final local verification: full web/worker build, final web build after contrast corrections, 10 public route/theme axe scans (zero violations), final 10 responsive checks, keyboard theme/preview controls, cached navigation and readable form input passed.
- Next: PR #12 release CI; merge, deploy and verify live production.
- Blockers: none. Vercel connector has project access; local CLI is signed into a different account, so prefer existing Git deployment and connector verification.
