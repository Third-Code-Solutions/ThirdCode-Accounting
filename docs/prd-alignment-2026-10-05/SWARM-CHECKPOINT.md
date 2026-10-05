# Remaining implementation checkpoint — 5 October 2026

## Verified release and current work

PR #9 is merged and deployed at main
`4038c8db86ac7d794ca42fc65fa3a4cc68fae769`, addon `18.0.2.13.2`. Railway and Vercel
serve that revision. The released candidate is
`24c8d46659b186559cc1edd32d75bde6a73cd1aa`; source is unchanged in the merge.
This is the verified baseline for continuation on
`codex/accounting-recovery-performance`. New work on that branch is not yet a
release or an acceptance result. Unrelated primary-checkout files remain outside
this workstream.

Candidate CI `37277537109` and main-merge CI `37282043406` passed all jobs:
125 native Odoo tests, 59 integration checks, 22 recovery tests, 14 benchmark
safeguards, 60 portal unit tests and package, lint, typecheck, build, migration,
security and hosted-runtime gates. Independent principal and Python reviews
completed. Source/CI results do not substitute for business acceptance.

For the unreleased 13.3 work in [PR #10](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/pull/10),
[CI 37288677011](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/actions/runs/37288677011)
passed all three jobs at `d3da03e`: 134 native Odoo tests, including the nine new
monthly-report regressions; 59 integration checks; 22 hosted recovery tests;
21 provider tests; 15 benchmark and eight annual safeguards; 60 portal tests;
and the package, lint, typecheck, build, migration, security and hosted-runtime
gates. The provider tests use a controlled provider model and the pinned SDK;
they do not contact or activate a real backup destination.

The native annual smoke added 24 documents and eight settlements, producing
32 posted moves and 64 lines. Its measured synthetic ledger totaled 45 moves,
90 lines and three attachments totaling 914 bytes. Six actual financial-statement
PDFs took 2.202–4.604 seconds; balance-sheet equality, cash-flow reconciliation
and repeated calculation equality passed. This is small-volume CI evidence,
not an NF-04 client-volume or hosted performance acceptance result.

The later recovery baseline `474994f` passed all three jobs in
[CI 37297823382](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/actions/runs/37297823382).
This includes the actual monthly PDF rendered by the Read-only role, first added
at `db771e5`, and all 12 restore tests. Those restore tests include a real
PostgreSQL 18/Odoo dump and fresh-target restore, accounting/audit/attachment
conservation, offline registry loading, rejected existing targets and altered
baselines, and Linux timeout/parent-SIGKILL descendant cleanup. The generic full
restore implementation is therefore native-tested; it is not an active provider
or monthly operational service.

Earlier audit snapshot relation batching at `cfdbc80` failed two native tests.
Diagnostic revision `7865707` also finished with two failures in
[CI 37300335141](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/actions/runs/37300335141).
It exposed different replay cache states: the first warm native replay had six
audit groups/29 details; native cold replay and candidate cold replay matched
exactly at seven groups/30 details. Both failed runs remain historical diagnostic
evidence.

Corrected executable source `096a98030dfe26a9181544d1c8791ff708c01677` passed all
three jobs in [CI 37301445442](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/actions/runs/37301445442):
139 native tests with zero failures/errors, 59 integration checks, 12 restore
tests, portal gates and the monthly/annual PDF checks. The header override was
removed; invoice-header queries remain 25/25, while invoice-line queries are 25
native versus 22 candidate. Every cold and explicitly warmed native/candidate
replay matched: four replays per mode, each with seven audit groups/30 details and
SHA256 `73d5b8d2fc5326b1a709aa265785d8916780a2148fb7b56ded2aea066d44d71b`.
The test establishes a common cache baseline inside every replay and retains
full-history equality, actor, company and control assertions.

Source CI is green; no new hosted latency result, fresh predeploy backup,
candidate upgrade rehearsal, merge or deployment is established by that result.
Railway console access and those hosted release gates remain open. Future source
changes require their own [PR #10 checks](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/pull/10/checks).
Verified production remains 13.2 at `4038c8d`; native query reduction is not a
hosted performance or client acceptance claim.

Read-only postdeployment checks passed installed-version, portal readiness,
engine login, both WebSocket upgrade/ping/pong/session-expiry paths, six encoder
settlement denials and 35 trial-balance source-link comparisons. Original
production ledger/audit evidence and referenced file bytes remained preserved.
Private summary references: `swarm-release-live-results.json`,
`swarm-release-health.json` and `tcsi-swarm-production-after.json`. Raw financial
records, PDFs, credentials, backup material and personal filesystem paths do not
belong in public Git.

## Delivered foundations and measured limits

Audit metadata batching preserves native metadata selection, full field/value
snapshots, actors, company scope and immutable history. A global ORM prefetch
experiment did not establish a latency benefit and was excluded from source and
release. Do not revive it without a new evidence-backed hypothesis.

The isolated benchmark enforces an explicit disposable database and company,
environment credentials, correct percentile calculation, sample adequacy and
meaningful failure/target exits. The released candidate completed 40 save/post
transactions per case, two Odoo workers, one account across independent sessions,
PostgreSQL18.6, loopback RPC and shared-host resources:

| Concurrent sessions | Save p95 | Post p95 | Result |
| --- | ---: | ---: | --- |
| 2 | 3011.16 ms | 1476.87 ms | TARGET_MISSED |
| 10 | 11930.36 ms | 11294.73 ms | TARGET_MISSED |

All 80 transactions succeeded, with zero probe or cleanup errors. Original
isolated evidence and fresh/historical production comparisons passed. The
existing copy upgraded in 35.491 seconds. Private summary reference:
`tcsi-swarm-candidate-resume-results.json`. The earlier 20-sample protocol differs;
no controlled speedup percentage follows. NF-02/NF-03 remain open, with no
browser/network, cold/warm, multi-role or representative annual-volume acceptance.

Guarded recovery capture, monitoring and manifest verification are delivered:
bounded writer pause, pidfd identities, an independent resume watchdog, child
process cleanup, encryption, durable-receipt contract and failed/missed-run
monitoring. A fresh coordinated manual snapshot was encrypted and downloaded;
all 1,397 manifest files were decrypted and hash-verified off-host. Its exact
payload restored into a fresh isolated database in 72.508 seconds and upgraded
in 32.682 seconds, with restored and production baselines preserved. Private
summary references: `offhost-verification.json` and `restore-results.json`.

That restore is complete; operator/deputy handover and recurring recovery are not.
No approved provider delivery/alert integration, external nightly schedule,
retention policy or missed-run notification is activated. Separate Railway volume
snapshots do not establish coordinated recovery. An identified deployed-image
digest does not establish long-term registry retention.

Unreleased recovery source now supplies the complete generic isolated drill:
`hosted_recovery_drill.py` can invoke `hosted_recovery_restore.py`, backed by
capture-time `recovery_fingerprint.py` hashes. It creates a fresh private target,
uses explicit local database credentials, preserves evidence on failure, prevents
target overwrite and never starts public HTTP. Source `474994f` passed the native
checks above. Actual provider delivery, external capture transport/schedules,
recipient alerts, retention execution, independently retained image and named
operator/deputy handover remain unactivated or unproven. Neither historical
manual recovery nor synthetic full-drill CI closes those operational requirements.

## Current parallel ownership

- Recovery engineer: provider delivery/alert integration, retention and external
  scheduler/monitor tooling using the existing capture foundation.
- Performance engineer: isolated profiling, request/queue timing evidence and
  focused changes that preserve accounting and audit controls.
- Report engineer: public traceability reconciliation and an additive generic
  monthly bank-to-ledger report; independent Python/principal review is separate.
- Integration lead: shared wiring, CI, hosted operations, external input gathering,
  private evidence, final release and requirement-by-requirement status.

Owners work on separate files. The integration lead alone coordinates shared
package/version/CI changes, commits and production operations. Preserve other
agents' and user edits. Resolve concrete review findings before release.

## Acceptance criteria and next gates

Preserve exact audit field coverage, old/new values, actor, timestamp, company
scope and immutable history. Profile the remaining save cost and queueing first;
change one grounded cause, verify native equality/permission regressions, then
repeat a documented protocol. Retain failed targets. Annual-volume and actual
hosted browser/network measurements need their own explicit evidence.

Recovery integration must prove real independent delivery, verified receipts,
failed/missed-run alerts, safe policy-controlled retention and restore drills.
Build adapters and scheduling support independently; activation requires the
approved destination, recipient, policy, operators and recovery objectives.
Never fabricate a destination, receipt, legal retention period or alert success.

The new generic monthly report is implemented with nine native regression
tests, an additive report action and a form button. It reads posted bank-account
activity, linked statement rows and recorded reconciling totals, shows unresolved
differences and evidence gaps, and distinguishes current matching state from
month-end ledger balances. Its nine native tests, including direct HTML rendering
and non-mutation checks, passed in CI 37288677011. The actual PDF rendered by the
Read-only role on the isolated clone passed at `474994f` in CI 37297823382 and
again with corrected audit source `096a980` in CI 37301445442.
Generating the report changes no reconciliation state or ledger entries. Its
format is explicitly provisional; it does not complete the client-specific
RP-04/AC-03 contract.

Before a new deployment: pass relevant native accounting, permission, migration
and report tests; rehearse the candidate module/database upgrade against an
isolated representative copy; verify a recoverable coordinated backup; and retain
a rollback or forward-recovery plan that preserves new customer transactions.
Postdeployment verification is read-only. No synthetic customer-book transactions,
real balance edits, official-document issuance or unapproved MYOB import.

## External decisions and acceptance still open

All 92 IDs remain in `requirements.csv`; `REMAINING-ACCEPTANCE.md` contains the
single consolidated client checklist and execution boundaries. The PRD is a review
draft. The user is the developer/technical owner; Client Owner approval follows
the Technical Adviser's recommendation. Named people and finance ownership remain
pending CEO nomination. Do not treat deployed engineering as full PRD acceptance.

- RP-04/AC-03: approved monthly reconciliation sample, columns, formulas, grouping,
  totals and source tie-out; finance lead validates and Client Owner approves on
  the Technical Adviser's recommendation. Names remain pending. Generic report
  development does not authorize client-specific implementation before samples.
- Reports/statutory configuration: actual SOA/financial statement/Official Receipt
  samples, print stock, tax/cash classifications, authorized control/signature
  values, CAS documentation and EIS applicability; client accountant decisions.
- Migration/parallel month: authorized MYOB extraction, mappings, cutover and
  retention policy, named finance owner, real line-by-line reconciliation and a
  complete real accounting month in both systems.
- Windows: actual supported Windows with current Chrome and Edge, supported roles
  and company scope; Mac/Linux results do not close NF-12/AC-08.
- Volume and recovery operations: agreed annual workload, independent destination,
  alert recipient, retention, schedule, operator/deputy, RPO/RTO and handover.

Recurring customer invoices remain assumed; payment-threshold approval remains
optional until confirmed. Continue independent engineering while these inputs are
pending. No completion percentage or healthy HTTP response closes an outstanding
business, environment or elapsed-time gate.
