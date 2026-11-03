# Turnover readiness review — 3 November 2026

Scope: one independent installation per client (`docker-compose.independent.yml`:
Odoo 18 Community + pinned OCA modules + the `thirdcode_accounting` addon
18.0.2.16.2, one PostgreSQL 16), operated by the client's IT team with
[`OPERATOR-RUNBOOK.md`](OPERATOR-RUNBOOK.md). The hosted pilot (Vercel, Railway,
Supabase) is TCSI's own environment and is not part of the handover.

## Verdict

**Ready for a supervised handover**, once TCSI completes the release steps in
"Before go-live" below. No critical or high finding is open in the code. The
remaining items are release-process and client decisions, not defects.

## What changed in this pass

### Security

| Finding | Fix |
| --- | --- |
| Any Settings user could call `/web/become` and turn the session into uid 1, which the owner checks and record rules trust | Route refused (`controllers/webclient.py`), with a test |
| Database-manager RPC (`/jsonrpc` db service, `/xmlrpc/db`) reachable through the proxy | Denied in the reference proxy `config/tls-proxy.nginx.example` |
| Forwarded headers could be spoofed past the in-container nginx | Reference proxy overwrites `Host` and every `X-Forwarded-*` header; runbook makes this mandatory |
| Slow-body uploads could hold the few engine workers | Reference proxy buffers bodies with `client_body_timeout 15s` |
| Anyone knowing the owner login could keep it locked out | Runbook: `tcsi.auth.allow_ips` for administrator addresses |
| Dev compose published Odoo on every interface | Bound to `127.0.0.1` |
| Supabase helper scripts defaulted to TCSI's hosted project | `SUPABASE_PROJECT_REF` is now required |
| Deploy notifications ran on forks | Gated to the TCSI repository |
| Platform Console menu offered to every Settings user (menu groups are OR'ed); the console itself already refused them | Menu limited to the owner console group, also removed from upgraded databases, with a test |

### Accounting correctness

| Finding | Fix |
| --- | --- |
| HIGH — recurring "Run now" on an overdue schedule skipped the missed periods silently | Refused with a message pointing to "Run due periods" (journal and invoice schedules) |
| HIGH — Send & Print failed on posted invoices (the immutability guard rejected Odoo's `is_move_sent` flag) | Delivery-state fields allowed on posted moves; no accounting field affected |
| "All entries" financial reports included cancelled entries | Cancelled entries excluded; drafts still included |
| Official-receipt amount in words read "point five six" and appended the ISO code | Uses the currency's own wording (pesos and centavos) |
| Monthly schedules starting on the 29th–31st drifted to the 28th after February | Day anchored to the schedule start date |
| A reversed year-end close could not be redone (unique date constraint, no way out) | A posted close can be cancelled once its entry is reversed; uniqueness ignores cancelled closes |
| Bank reconciliation compared a foreign-currency statement with company-currency balances | Foreign-currency journals rejected |
| Company setup silently reopened a closed period | Setup keeps it closed and reports it; reopening stays in the audited period workflow |
| Financial statement wizard always said "Trial layout", even for live books with an approved sample | Notice shown only until the client report sample is approved |

### Operations and turnover

- New [`OPERATOR-RUNBOOK.md`](OPERATOR-RUNBOOK.md): install, first sign-in, daily
  checks, backup schedule and encryption, upgrade, rollback, recovery,
  credential rotation, escalation template, licences.
- Container logs bounded (json-file, 5 × 20 MB per service).
- Docs corrected: rollback is a forward fix or a pre-upgrade restore (an older
  image refuses an upgraded database); the user guide no longer points at the
  hosted pilot or promises account emails.
- Demo seeder (`scripts/seed_client_demo.py`) rewritten for owner isolation. The
  old version renamed the platform's own home company into a demo customer
  and then failed. It now creates each company through Platform Console →
  Create organization, converts it from trial to active (so the statutory
  print gates are shown), and seeds it as that company's Administrator.
  Demo users land on the finance overview, as accounts made under People do.
- Phones: the top-bar page title was clipped to one letter at 375 px. Below
  420 px it is now kept for screen readers only; the page heading names the
  screen.

### Portal (optional component)

- Unlisted pages render the branded 404 page with a nonce CSP instead of an
  empty 404.
- Copy no longer describes hosted or shared books; robots and metadata keep
  `/login` out of search results.

### Test coverage

- `test_platform_console` and `test_branding` had never run (not imported by
  `tests/__init__.py`). They are now wired in and pass; one lock test was
  rewritten because its fixture already holds the lock it probed for.
- New regression tests for every fix above.

## Verification evidence

| Check | Result |
| --- | --- |
| Native addon suite (fresh database, CI-equivalent command) | Passed: 250 tests, 0 failures, 0 errors. Later view and menu edits re-run on an upgraded database: 57 tests (financial controls, platform console), 0 failures |
| Web lint, typecheck, unit tests (99), migration validation, production build | Passed |
| Reference proxy `nginx -t` (nginx 1.27) | Passed |
| Independent compose file (logging anchors) parsed and applied | Passed |
| Independent demo stack: install, health, seed of five fictional companies | Passed on an image built from this revision: empty volumes, first-boot install, healthy, five organizations created through the Platform Console and seeded in one pass |
| Read-only demo check (`scripts/check_client_demo.py`) | Passed: 5 companies, at least 10 posted documents, 5 company-restricted accountants, approved customer and supplier payments, recurring invoice and journal, bank reconciliation, 15 financial reports, public sign-up off, unapproved statutory invoice print refused |
| Browser walk (presenter and owner; desktop and 375 px; light and dark) | Every TCSI menu route, invoices, bills, payments, journal entries, chart of accounts, customers and Settings opened without an error dialog or page overflow; non-owner refused at `/workspace/console` |

## Before go-live (TCSI)

1. Build the release image in CI from the merged commit, push it to the
   client-agreed registry, and give the client the digest and 40-character SHA.
   Locally built test images are not release artefacts.
2. Fill in the support and escalation table (runbook section 10).
3. Decide the repository licence (`LICENSE` file) and confirm AGPL-3 obligations
   for the OCA modules in the image. This is a legal decision.
4. Run the readiness check (runbook section 4) on the client installation with
   real company settings, without `--trial`.

## Client decisions (not defects)

- BIR/EIS accreditation, receipt layout and report-sample approvals.
- Statutory retention period for backups.
- Recovery point objective and who receives backup alerts.
- Whether to enable the optional encrypted S3 backup schedule (daily 03:00
  UTC+8, 30-day retention).

## Known limits

- Automatic onboarding provisions the Philippine chart only.
- Bank reconciliation supports company-currency journals only.
- The Platform Console lists the installation's default company (#1,
  "Third Code Solutions Inc.") as a trial organization with no people. It holds
  no books; leave it unused. Whether to repurpose it is a TCSI product decision.
- PostgreSQL upgrades stay within major version 16 unless TCSI supplies a
  migration procedure; restores require the exact image recorded with the
  backup.
