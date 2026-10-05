# Remaining implementation checkpoint — 5 October 2026

## Objective and baseline

Continue the 92-row PRD alignment matrix through measured engineering fixes and release-gated deployment. Hosted architecture remains accepted. Main `c7415c2e191af98d972712bb37746ae1f01d0e3d` / addon `18.0.2.13.1` is verified live. Work continues from that revision on `codex/accounting-remaining-todos` in the existing attached worktree. Unrelated files in the primary checkout remain untouched.

## Parallel ownership

- Audit performance: focused audit metadata/snapshot optimization and native equivalence/query regression tests.
- Hosted recovery: consistent encrypted capture, bounded writer resume, explicit transport/monitor interfaces and isolated tests.
- Benchmark and acceptance: company-scoped synthetic benchmark correctness, environment-based credentials, valid measurements and remaining acceptance dependencies.
- Integration lead: shared wiring, independent reviews, CI, isolated hosted experiments, upgrade/recovery evidence, production release and final traceability.

Each implementer owns separate files. Only the integration lead changes shared package/version/CI files, commits, deploys or operates hosted environments. Review findings must be resolved before release.

## Acceptance and boundaries

Audit improvements must retain exact field coverage, old/new values, actors, company scope and immutable history while demonstrating lower repeated query cost. Benchmark targets remain provisional until client acceptance; preserve the failed two-/ten-client baseline. Recovery must fail closed on missing destination/recipient/configuration and resume writers on every failure path. Build independent tooling before activating actual delivery or notifications.

Use native isolated accounting tests, relevant regressions, production-equivalent dependencies, representative upgrade rehearsal and recoverable coordinated database/filestore backup before deployment. Production verification is read-only. No synthetic customer-book transactions, unapproved real migration, official-document issuance, fabricated tax values or client approvals.

## External dependencies still open

RP-04 exact report definition/sample; annual transaction volume; approved recovery destination/alert recipient, retention, named operator/deputy and RPO/RTO; actual Windows Chrome/Edge environment; authorized MYOB extraction, mapping/cutover/retention and finance owner; client samples/classification/tax/control/signatures/CAS/EIS decisions; full real parallel month and accountant examination/sign-off. Continue independent engineering while these remain unresolved.

## Progress

- Refreshed clean release worktree and remote main; created the continuation branch from main.
- Dispatched three bounded implementation workstreams with separate file ownership.
- Audit metadata batching and five native equivalence/query/access regressions are in `dbe5a0f`; independent principal/Python source reviews passed. Native CI is running; improvement is not yet measured.
- Benchmark safety, company scope, environment credentials, correct percentiles/failure exits and 14 local regressions are in `a88b368`. Updated acceptance guide preserves external dependencies.
- Recovery capture/monitor/verify and 22 regressions implemented; 15 applicable macOS tests pass, five Linux watchdog/process tests and two PostgreSQL capture/restore tests await CI. Independent review fixed deadline/process cleanup and alert failure paths. Provider adapters and actual scheduling remain inactive pending approved operational inputs.
- A process-local prefetch experiment on the isolated hosted copy reduced warm-save query count from 846 to 730 but did not demonstrate a latency gain. That global prototype is excluded from source/release. Synthetic writes were confined to the isolated database.
- Next: finish native CI, review/run the isolated candidate upgrade and benchmark, retain conservation evidence, then release only the changes whose gates pass.
