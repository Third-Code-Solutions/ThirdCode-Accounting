# Refreshed baseline — 5 October 2026 (Asia/Manila)

## Evidence boundaries before implementation

- Clean checkout: `25b91a7b68fc65b0d36618018cc48b86ca2672f3`, branch `work`.
- Fresh Vercel connector read: production alias `tcsi-accounting-portal.vercel.app`, deployment `dpl_8jQqpmq39da1sFAUZaxe9uwUnHPg`, READY, same commit. This is deployment metadata, not accounting acceptance.
- Source addon version: `18.0.2.11.2`. Railway installed version, modules, companies, balances, permissions, backups and scheduler NOT INSPECTED: no engine credentials/identity or Railway connector available in this environment. No customer records inspected or altered.
- At initial inspection the PRD PDF, build prompt, historical audit REPORT.md and requirements.csv were absent. The user subsequently uploaded the eight-page PRD v0.1; its exact numbered requirements now populate requirements.csv. The original build prompt and historical audit remain unavailable. User confirms they exist on their computer; `/Users/hoon` is not mounted. Existing `docs/prd-traceability.md` is secondary evidence, not a replacement for exact original requirements.
- Docker engine 28.4.0 and prepared `tcsi-cloud-dev` image `678275793ec0` are available. Isolated PostgreSQL 16 started. Prepared setup log describes prior synthetic tests; those are historical, not fresh verification.
- Current source explicitly allows posted reset/cancel and sudo edits; bank-statement synchronization can change a posted amount; line create/unlink and several economic fields lack custom protection. Period restriction checks only `action_post`, while native reversal and payment paths can call `_post`.
- Audit rules omit journal lines, partial/full reconciliations and relevant masters; only parent audit rows are protected from edits/deletion.
- Migration independently adds opening TB, open items and history; source IDs alone do not establish non-overlap. A created draft is skipped on retry before posting.
- Cash movement output is not a complete cash flow statement; comparative financial periods are absent. Production report outputs are unverified.

## Approved scope amendment

The user's 5 October request accepts Vercel portal/proxy, Railway Odoo Community, Odoo PostgreSQL as authoritative ledger, persistent filestore and existing Supabase responsibilities. On-premise/client-owned-server/LAN-only mismatch findings are withdrawn. No internet removal, ledger replacement, company migration or historical renumbering is authorized. NF-01 and NF-11 deployment assumptions are superseded only to that extent. Hosted backup consistency, separate recovery destination, retention, recovery ownership, isolation and accounting controls remain mandatory and unverified.

## Release hold

No production deployment until relevant tests, representative upgrade rehearsal, consistent recoverable database/filestore/configuration backup and transaction-preserving recovery plan pass. Git push to main can trigger Vercel/Railway, so do not push this candidate to a deployment branch while gates remain blocked.

## Source identity

Uploaded PRD SHA-256: `20ad1ab7f7012c72cf833ec378f3f18019ffe843fd4c84c81f0ec4030028dc0d`. The source PDF remains in the authorized upload location; it is not substituted with repository prose. Dates in this directory follow Asia/Manila; raw tool logs use UTC.
