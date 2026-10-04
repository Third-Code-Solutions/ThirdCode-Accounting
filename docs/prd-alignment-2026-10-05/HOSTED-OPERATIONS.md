> Candidate18.0.2.13.0 adds a richer local rehearsal: [phase2 evidence](phase-2/REPORT.md). The final isolated ZIP restored in8.051seconds and preserved posted balances, audit history and retained cutover archives. This does not verify the hosted schedule, destination, configuration/credential recovery or production volume; the release gates below remain in force.

# Hosted operations and release procedure

The 5 October 2026 user amendment accepts Vercel for the portal/proxy, Railway for Odoo Community, Odoo PostgreSQL as the ledger, the persistent Odoo filestore, and existing Supabase responsibilities. On-premise, client-owned-server and LAN-only mismatch findings are withdrawn. Backup consistency, isolation, retention, permissions and recovery obligations remain. Existing PowerShell compose scripts are local tooling, not evidence of hosted nightly backups.

## Required recovery bundle

Preserve the PostgreSQL dump (including audit history), matching filestore, exact Odoo image/OCA/addon revisions, deployment/configuration manifest, required recovery secret references, database name, company scope, timestamp, file sizes and SHA-256 hashes. Store encrypted recovery copies outside the live database/volume and its failure domain. Keep secret values out of source control and evidence reports.

Odoo's ZIP backup copies files and dumps PostgreSQL sequentially. It is only a consistent bundle when all writers are quiesced, including HTTP, cron, workers, imports, attachment processing and filestore garbage collection, or when the hosting provider supplies a demonstrably coordinated snapshot. The repository's old dump-then-tar script alone is not sufficient for an active hosted system.

Before production release, the hosting operator must record the actual nightly scheduler/job ID and timezone, separate recovery destination, encryption/access policy, retention and deletion policy, monitoring and failed-job alert recipient, named recovery operator/deputy, agreed RPO/RTO and restore cadence. No values have been invented. Developer/product owner is the user; future client finance owners are not yet named. Per-client obligations belong in the turnover agreement.

## Rehearsal and deployment

1. Inventory actual Railway image, addon/database module version, PostgreSQL version, volume mount and OCA revisions. Confirm the inspected companies and real backup readiness.
2. Establish a maintenance window. Stop all accounting and file writers; verify no remaining jobs/sessions are modifying the database or filestore. Retain the last accepted document number and transaction timestamp as comparison evidence.
3. Capture the complete recovery bundle, verify hashes, restore into isolated PostgreSQL and a separate filestore. Disable email, cron, external integrations and customer access in the copy. Never point the test application at the production database/volume.
4. Verify source/restored posted document IDs/names, debit/credit totals per account and company, AR/AP residuals, representative attachment bytes, audit actors/timestamps/old/new values, and required configuration. Measure restore time. A successful process exit is insufficient.
5. Rehearse `-u thirdcode_accounting --stop-after-init --no-http --max-cron-threads=0` against that copy using the candidate image. Check duplicate receipt sequences/numbers before upgrading: resolve existing exceptions through an approved process, never renumber or delete customer documents to make constraints pass. Inspect unresolved historical audit scope; it remains accessible only to platform staff rather than leaking to other companies.
6. Run the relevant native suite and client-representative workflow/report/permission checks. Record actual revision IDs, output hashes, durations and accounting reconciliation. Resolve the release limitations listed in REPORT.md.
7. Only after these gates pass, deploy the exact reviewed revision. Keep the live schema and persistent volume authoritative. Capture read-only production verification of installed version, inspected company scope, balances, document names, audit visibility and reports. Do not insert synthetic transactions in customer books.

## Recovery without losing new transactions

Before accepting new writes, a failed upgrade can restore the pre-release bundle in the agreed maintenance window. Once customer writes resume, do not blindly replace the live database/filestore with that older backup: first preserve the current database, files, audit history, and all post-release transactions. Prefer a forward correction or a compatible code rollback against the current schema. Any data recovery must reconcile the intervening transactions and their document numbers with the client's finance owner before reopening. A tested application rollback is not proof of a safe database downgrade.

The candidate adds fields, an audit-scope relation, new audit rules and receipt uniqueness protection. Its policy rejects posted reset/cancel and posted bank statement mutation. Staff need a reversal/correction procedure; workflows relying on mutation of posted suspense entries must be rehearsed explicitly. Retained logs whose company cannot be established are not purged; platform staff must resolve access attribution from evidence.

## Evidence produced here

An isolated synthetic upgrade from 18.0.2.11.2 to 18.0.2.12.0 retained one posted 50.00 journal, its original name, attachment and five audit rows. A consistent ZIP of this quiescent database/filestore restored into `tcsi_alignment_restored`; comparisons are in `evidence/recovery-verification.json`. This is not a production-representative backup, remote-destination verification or a hosted scheduler test. The archive is a local rehearsal artifact, not the separate recovery destination.
