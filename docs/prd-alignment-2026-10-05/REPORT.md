> Historical implementation record. PRs #6/#7 are now merged and module18.0.2.13.0 is live. The current audit, candidate fixes, recovery evidence and remaining acceptance gates are in [LIVE-IMPLEMENTATION.md](LIVE-IMPLEMENTATION.md). Statements below about unavailable Railway access or an undeployed13.0 candidate describe the earlier snapshot.

> Latest implementation and acceptance status: [phase 2 report](phase-2/REPORT.md), module18.0.2.13.0. The material below records phase 1 historical findings; superseded open engineering items are resolved only where the phase 2 evidence says so.

# PRD alignment candidate — 5 October 2026 (Asia/Manila)

The candidate improves accounting integrity, reporting calculations and migration safety. **It is not deployed and is not accepted for production or client turnover.** The required production-representative upgrade and hosted recovery gates could not be verified through the access available here. Remaining engineering gaps are listed separately from client decisions below. No alignment percentage is claimed.

## Sources, revisions and scope

The uploaded eight-page Accounting System PRD v0.1 (19 September 2026), the user's implementation request and white-label clarification govern this work. Embedded document instructions were treated as requirements/evidence. The original build prompt and historical production audit/matrix on the user's Mac remain unavailable in this cloud checkout; this is a fresh review, not a claim that every historical finding was reproduced.

- Baseline checkout: `25b91a7b68fc65b0d36618018cc48b86ca2672f3`, source module `18.0.2.11.2`, initially clean branch `work`.
- Fresh production evidence: Vercel deployment `dpl_8jQqpmq39da1sFAUZaxe9uwUnHPg`, READY, production alias `tcsi-accounting-portal.vercel.app`, baseline commit. This verifies portal deployment metadata only.
- Candidate module: `18.0.2.12.0`. Local review commits are in `REVISIONS.md`. No deployment branch was pushed.
- Railway installed module/image, actual companies/configuration, ledger, cron, backups and volume topology were not accessible. No customer records were inspected or changed. Production engineering acceptance remains unverified.
- Accepted architecture: Vercel portal/proxy, Railway Odoo Community and PostgreSQL authoritative ledger, persistent filestore and existing Supabase responsibilities. On-premise/client-owned-server/LAN-only mismatch findings are withdrawn. Isolation, recovery, retention and accounting obligations remain.

[requirements.csv](requirements.csv) covers all 66 numbered PRD requirements, plus six objectives, four roles, twelve standard reports and four scope/discovery rows (92 total). Its exact outcomes and evidence limits take precedence over older feature-presence claims. [BASELINE.md](BASELINE.md) records pre-change findings.

## Implemented changes

Posted moves and journal lines retain permanent posting history. Reset, cancellation, deletion, economic edits and inserted/reparented lines are blocked, including sudo and forged context tokens. Native reversals preserve the original; reconciliation receives only narrowly scoped metadata writes. Posted bank statement amounts cannot silently rewrite the ledger. Existing suspense-entry editing/reconciliation integrations therefore need representative rehearsal before release.

Closed periods are checked through native `_post`, move/line operations and reconciliation effective dates. Only the accounting Administrator can reopen. Shared accounting-writer locks and an exclusive close/reopen revision prevent concurrent posting from bypassing closure; close also checks drafts committed while it waited. Closure history cannot be forged through default context values. A later-dated payment/reversal can settle an older invoice without backdating the accounting effect.

Audit rules now include journal lines, reconciliations, accounting masters, recurring/batch lines and employee expense approvals. Both audit parents and field-history rows reject edits/purges. Recorded company scope and an upgrade backfill restrict tenant visibility without deleting unattributable historical evidence. The detailed coverage map and remaining scope are in [AUDIT-COVERAGE.md](AUDIT-COVERAGE.md).

Receipt numbering has company uniqueness, protected metadata and sequence configuration, private issuance, transactional no-gap consumption and a row lock for retries. Direct counter consumption/reset/deletion and renumbering are denied. This does **not** certify every invoice/journal series: native series boundaries and fiscal resets still require an explicit policy and further tests. No historical numbers were changed.

Financial reports now calculate comparative periods, preserve operating income across native year-end transfers, and show operating/investing/financing cash categories plus an explicit unresolved bucket and opening-to-closing reconciliation. Cash account/classification fields are available on `account.account` for controlled configuration; a complete accountant-reviewed classification/allocation workflow and presentation remain unfinished. A generic report-sample checkbox no longer makes output “approved”; a matching company/type/revision with attached sample and approval evidence is required. Synthetic approvals used in tests are not client approvals.

Migration now rejects overlapping populated accounting bases and unsupported undeposited receipt input. Native import is atomic create/map/post with a payload fingerprint: an identical retry returns the same posted move; changed or unverified historical content is rejected; failure leaves no skipped draft. This closes known duplication/retry hazards, but a coherent combined opening/subledger/history policy still must be implemented for real cutover. See [MIGRATION-DESIGN.md](MIGRATION-DESIGN.md).

Recurring journal and invoice retries no longer move scheduling progress backwards.

## Verification and actual accounting evidence

All accounting writes were in disposable `tcsi_alignment_*` databases. Runtime: Odoo Community `18.0-20260908`, PostgreSQL 16, prepared `tcsi-cloud-dev` image `678275793ec0`, repository-pinned OCA dependencies and mounted candidate addon. This is production-equivalent source/dependency testing, not proof of the unknown Railway installation. Synthetic chart/currency: USD, no claim of Philippine statutory acceptance.

| Evidence | Result and boundary |
|---|---|
| Baseline native controls | 22 tests passed on unmodified baseline; several encoded the now-rejected reset/cancel/edit policy. |
| Candidate native regression | Final counts/log in `evidence/TEST-RESULTS.md`; includes posting/history/context, periods, reversal, role/company isolation, audit old/new values, numbering, imports and reporting. |
| Portal/contracts/worker | 61 tests passed (55 web, 4 contracts, 2 worker); no portal or Supabase architecture change. |
| Migration policy unit suite | 5 passed: balanced overlapping inputs, changed source hashes, unsupported receipts, malformed numbers, duplicate/inconsistent history. |
| Native RPC workflow scripts | Passed synthetic sales/bills, partial settlements, AR/AP control matching, recurring retry, advance creation, payment batch, optional approval, year-end reversal, bank difference and period actions. Earlier full-scope script checks employee expense draft surface only; separate native expense tests cover the full flow. |
| Real concurrent database cursors | Concurrent draft blocks close; posting after concurrent close retries then fails correctly; repeated receipt assignment returns one number with unchanged counter. An initial failed lock probe exposed deferred ORM writes; explicit flush fixed it. |
| Upgrade | Baseline `18.0.2.11.2` to `18.0.2.12.0` retained journal `UPG/2025/01/0001`, 50.00 balance, 27-byte attachment and five audit rows; audit scope populated, original evidence preserved. Tiny synthetic dataset. |
| Backup/restore | Quiescent native database+filestore ZIP restored in 6.383 seconds; posted count, per-account balances, attachment hash and 5 audit rows/108 field-history rows matched. Separate hosted destination/schedule/retention/config-secret recovery and production volume NOT verified. |
| UI | Actual native Odoo financial wizard inspected in Chromium, light/dark screenshots retained; 1280px viewport/document with no horizontal overflow, comparison fields inside the modal. Windows Chrome/Edge not tested. |

The twelve-month 2025 fixture posted twelve 100.00 invoices and one 150.00 payment across two invoices. AR is 1,050.00, cash is 150.00, income/equity is 1,200.00; balance sheet difference and opening-cash + movement − closing-cash difference are zero. Comparative 2024 is zero. Actual PDFs and calculation JSON are under [evidence/reports](evidence/reports). This small fixture exercises a full-year date range, not representative annual volume.

The separate workflow fixture's 1,000.00 customer invoice has 600.00 residual, matched by its AR control; the 800.00 bill has 300.00 residual, matched by AP. Native TB totals were 4,070.00 debit/credit at that recorded snapshot. Later scripts add other synthetic records, so these are dated snapshots, not totals to combine with the twelve-month fixture.

Trial balance, GL, SOA and financial PDFs rendered through native report actions. Additional actual OCA journal listing, ageing and unpaid outputs are retained under [evidence/standard-reports](evidence/standard-reports): customer ageing 1,847.50 and supplier ageing −270.00 at that later synthetic snapshot. The VAT PDF rendered **without tax rows** because no approved tax tags were configured; this is only output availability, not VAT calculation acceptance. Withholding output and a bank reconciliation summary PDF remain unverified. OCA journal rendering reports unused `t-eval` warnings; inspect/reconcile the full output in representative rehearsal.

| Timing run | Save p95 | Post p95 | Interpretation |
|---|---:|---:|---|
| Initial exclusive locking, 2 workers | 4,249.55 ms | 231.73 ms | Missed proposed save target. |
| Warm exclusive locking, 2 workers | 5,763.90 ms | 255.80 ms | Serialization contention; retained evidence. |
| Shared writer locking, 2 workers during other regression load | 2,249.17 ms | 379.30 ms | Still missed proposed save target under this load. |
| Shared writer locking, 10 workers | 4,770.19 ms | 2,790.14 ms | Functional run completed; latency needs representative load sizing. |
| Shared writer locking, quiet 2 workers | 804.77 ms | 304.41 ms | Within proposed 2-second target for this small local dataset only. |

All runs are retained. NF-03/NF-04 proposed targets and client transaction volumes still need agreement. Full-year synthetic financial PDFs rendered in approximately 2–3 seconds; representative annual-volume performance remains open.

## AC-01 through AC-09

| Criterion | Technical evidence | Client/production status |
|---|---|---|
| AC-01 SOA | Native activity statement PDF rendered; customer residual reconciles to AR. Complete opening/running/ageing sample comparison still required. | Approved format and client ledger comparison absent. |
| AC-02 Financial statements | Balanced synthetic BS, ledger-backed P&L/comparatives, year-end transfer regression and cash reconciliation. | Client presentation, classifications and representative TB comparison absent. |
| AC-03 Monthly reconciliation | Native bank reconciliation difference zero on synthetic fixture. This does not implement the undefined custom output. | Definition/sample and actual bank-statement reconciliation required. |
| AC-04 Official Receipt | Golden invoice/partial-payment tests, required-field HTML/PDF paths and guarded numbering. | Client stock, required documents, tax/control/signatory values and print approval absent. |
| AC-05 Opening migration | Overlap rejection, atomic retry/recovery and control-account mapping tests. | Complete economic policy, authorized MYOB extract, line-by-line cutover equality and owner sign-off absent. |
| AC-06 Parallel month | No substitute test claimed. | A full real accounting month remains outstanding. |
| AC-07 Audit | Sample line edit retains actor/time/old/new; immutable history survives isolated restore. | Technical sample passes; client examination and broader coverage/recovery review outstanding. |
| AC-08 Roles | Native four-role probes and ten-company isolation tests pass sampled actions. | Production memberships, all supported workflows and Windows validation outstanding. |
| AC-09 Recovery | Synthetic database and matching filestore restored and compared. | Production-representative hosted restore and handover demonstration outstanding. |

## Remaining engineering and external gates

Engineering still required before claiming full PRD completion:

1. Apply a documented numbering-series policy to invoice/journal boundaries, sequence overrides and all concurrent/failed/reversed workflows. Receipt tests do not certify the other series.
2. Finish cash classification/allocation configuration and reporting for mixed counterpart/non-cash movements; test accountant-approved cases. Verify withholding and bank-summary output; develop RP-04 once defined; compare SOA/report fields against approved samples.
3. Implement the selected combined opening/open-items/history/undeposited accounting treatment, archive retrieval and full line-by-line MYOB reconciliation. Current rejection is a safety control, not a completed migration design.
4. Extend audit verification to attachment replacement/removal, user/permission changes and every master/configuration path; review audit-rule administration and queryable retention. SQL/platform operators remain outside ORM guarantees.
5. Verify supported bank reconciliation integrations under reversal-only policy, scheduling concurrency, payment instruments/petty-cash configuration and client-volume performance. Complete production-role and browser coverage.

Access and operational gates: inspect actual Railway deployment/configuration/company scope; obtain a representative isolated copy; verify the coordinated DB/filestore/config recovery bundle and separate destination, nightly schedule, failure alerts, retention, named recovery operator, agreed RPO/RTO; rehearse the exact reviewed candidate; then release and perform read-only production verification. No permission was requested merely to continue reversible engineering. Deployment is held by the user's explicit release requirements.

Client-specific gates: each future client supplies report samples and RP-04 definition, accounting mappings and numbering interpretation, tax/registration/document values, EIS assessment, cutover/retention scope, real MYOB extraction and acceptance owners. The developer is the product owner; a client's finance lead/accountant is the person who confirms that client's balances and accounting decisions. No current client or finance approver is invented. [TURNOVER-DECISIONS.md](TURNOVER-DECISIONS.md) records that distinction.

[HOSTED-OPERATIONS.md](HOSTED-OPERATIONS.md) gives deployment and transaction-preserving recovery instructions. An old backup must never overwrite transactions accepted after release. Evidence hashes are in `evidence/SHA256SUMS`; reproduction notes are in `evidence/TEST-RESULTS.md`.
