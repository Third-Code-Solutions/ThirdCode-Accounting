# Remaining acceptance work after release 18.0.2.13.2

This is an execution checklist, not a new acceptance claim. The 92-row
`requirements.csv` and `SWARM-CHECKPOINT.md` in this directory record the verified
release at main `4038c8db86ac7d794ca42fc65fa3a4cc68fae769`, addon `18.0.2.13.2`.
Private raw evidence remains in the protected release record. New recovery,
performance and generic report work is not represented as released here.
Historical phase-2 results do not supersede the latest hosted latency failure.
Keep financial source files, report PDFs, credentials and raw recovery evidence
outside public Git.

The unreleased 13.3 work at `d3da03e` passed all three jobs in
[CI 37288677011](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/actions/runs/37288677011),
including native monthly-report regressions and the annual synthetic PDF smoke.
[PR #10 checks](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/pull/10/checks)
are the release gate for subsequent changes, including the separate Read-only
monthly PDF smoke added at `db771e5`. A green earlier revision does not establish
that added check, a hosted upgrade rehearsal or a production deployment.

The PRD is a review draft, not an approved client specification. The user is the
developer/technical owner. Client Owner approval follows the Technical Adviser's
recommendation; named people and the finance lead remain pending CEO nomination.
Engineering authorization does not establish client sample, accounting or
migration approval. The consolidated client checklist below is the single intake
for those outstanding decisions; continue generic engineering independently.

## Deployed benchmark safeguards and observed hosted target failures

The released candidate completed 40 save/post transactions per case on the
isolated hosted copy: two concurrent sessions produced save/post p95 of
3011.16/1476.87 ms; ten sessions produced 11930.36/11294.73 ms. All 80 transactions
succeeded without probe or cleanup errors, with original isolated and production
evidence preserved. Both cases retain `TARGET_MISSED`. This used two Odoo workers,
one authenticated account and loopback RPC on a shared host. It does not establish
browser/network, cold/warm, multi-role or representative annual-volume acceptance.
The private summary reference is `tcsi-swarm-candidate-resume-results.json`.

`scripts/benchmark.py` now requires an explicit `tcsi_alignment_` database name,
an identical `--confirm-isolated-database` value, an explicit company and supplied
credentials. The selected company must belong to the authenticated user. Every
subsequent RPC is restricted to that company. Chart selection uses account types,
not US account codes; each run creates its own company-owned partner. There is no
sudo or cross-company partner reuse. Successful posted probes remain only in the
disposable database; failed drafts are removed when their IDs are known. A timed
out create may have committed remotely without returning an ID, so dispose of the
whole isolated database after retaining evidence rather than assuming cleanup is
complete. Sessions are ended on success and failure; cleanup failures remain in
the report.

Passwords are read only from `ODOO_PASSWORD`. Use `ODOO_LOGIN` or `--login` for the
actual operator. There is no default login/password and no `--password` argument.
Old command examples containing password arguments are historical and must not
be reused. The operator account's native permissions apply unchanged.

Local verification, from the repository root:

```sh
python3 scripts/test_benchmark.py
python3 -m py_compile scripts/benchmark.py scripts/test_benchmark.py
```

Before a hosted run, identify the disposable database, its separate filestore,
configuration and owned process tree; disable its cron and outbound email. Verify
that the native service and all report-asset requests resolve to that isolated
runtime. Retain the source revision, installed addon version, database snapshot
age, actual ledger/attachment volumes, PostgreSQL/Odoo worker settings, CPU/memory
limits, execution host and concurrent background load. Verify production
fingerprints before and after the run. Do not run synthetic probes against
production or customer books.

With an already prepared isolated database named `tcsi_alignment_acceptance`,
company `1` verified in that copy, and credentials injected into the process
environment, the commands are:

```sh
python3 scripts/benchmark.py --url http://127.0.0.1:18068 \
  --database tcsi_alignment_acceptance \
  --confirm-isolated-database tcsi_alignment_acceptance --company-id 1 \
  --iterations 100 --min-samples 100 --workers 2 --post \
  --output /private/evidence/benchmark-two-sessions.json

python3 scripts/benchmark.py --url http://127.0.0.1:18068 \
  --database tcsi_alignment_acceptance \
  --confirm-isolated-database tcsi_alignment_acceptance --company-id 1 \
  --iterations 100 --min-samples 100 --workers 10 --post \
  --output /private/evidence/benchmark-ten-sessions.json
```

Replace the example database, company, URL and existing private output directory
with verified isolated values. A hundred samples is a proposed measurement size,
not an agreed client volume. Run commands separately: a threshold failure returns
nonzero **after** saving the evidence and must not suppress the other load case.

The JSON retains `save`, `post`, `targets_ms` and `target_observed` for existing
readers. New fields include actual phase sample counts, failure rate, failed-probe
and cleanup errors, sample adequacy, actor UID and an exit code. Exit `0` means the
specified isolated RPC target was observed; `1` means execution or cleanup failed;
`2` means a latency target was missed; `3` means insufficient samples. Invalid CLI
configuration exits before authentication. The p95 uses nearest rank
`ceil(n * 0.95)`. Empty phases report `null`, not zero. Targets use strict `<`, as
the proposed PRD target says “under two seconds.” The default 20 samples is only a
directional check, not a statistical confidence claim.

This workload uses independent sessions for one authenticated account. It does
not establish a five-user role mix. Authentication, setup and cleanup are outside
each timed call but still contribute server load; cold/warm calls are not
separated. Preserve both the older 20-sample and released 40-sample failed
measurements. A future run using these proposed 100-sample commands changes the
protocol; do not claim a controlled speedup percentage across different protocols.
Retain full end-user save/post measurements through the hosted `/workspace` path
on agreed normal load, including browser and network time, as separate evidence
for NF-02/NF-03 and O2. A loopback RPC pass does not close those requirements.

## Annual report performance and correctness

NF-04 remains open. Needed input: annual posted-entry/line counts, retained years,
account/customer/supplier counts, attachment volume, fiscal dates, comparative
period and required report formats. The proposed target is a full-year financial
statement below 30 seconds. Measure separate cold and warm runs, output size and
errors against the agreed representative volume; do not choose a small volume to
make the target pass.

The grounded native path is `thirdcode.financial.report.wizard` with `company_id`,
`report_type` (`balance_sheet`, `profit_loss`, `cash_flow`), `date_from`, `date_to`
and comparison dates; `get_report_data()` computes the statement, and report
`thirdcode_accounting.action_report_thirdcode_financial_statement` renders it.
See `addons/thirdcode_accounting/models/financial_report.py` and
`scripts/alignment_completion_reports.py`. The latter **creates synthetic ledger
fixtures** and is not a production or arbitrary-copy performance command.
Likewise, `alignment_standard_reports.py` assumes a specific synthetic fixture.
Do not run either merely to obtain a timing on customer books.

Once the representative isolated ledger exists, measure actual native PDF
rendering and the browser download separately with the correct accountant and
company context. Compare balance-sheet equality, profit-and-loss/TB agreement,
cash opening/movements/closing and comparative dates to independent ledger
queries. Preserve report hashes and timings privately. A parameterized measurement
harness is implemented in `scripts/benchmark_annual.py`, but no annual-volume
acceptance is possible until the data/period contract is supplied.

At `d3da03e`, CI 37288677011 executed 24 native invoices/bills and eight settlements
in an isolated clone, adding 32 posted moves and 64 lines. Including the initial
synthetic fixture, the measured ledger contained 45 moves, 90 lines and three
attachments totaling 914 bytes. Six full-year financial-statement PDFs took
2.202–4.604 seconds; balance-sheet equality, cash-flow reconciliation and repeated
calculation equality passed. See
[`ISOLATED-PERFORMANCE-PROTOCOL.md`](../performance/ISOLATED-PERFORMANCE-PROTOCOL.md)
for the protocol and CI reference. These small-fixture observations do not prove
annual client-volume performance, hosted end-user latency or client format approval.

## Client reports, custom RP-04 and statutory configuration

RP-04/AC-03 remains undefined and unaccepted. Obtain one approved sample and a field-level
contract: source and meaning of every column, formula/sign/rounding, grouping,
opening and closing balances, date/cutoff rules, unmatched/timing items, totals,
bank-statement link, correction behavior and layout. Identify the approving
accountant and a real authorized example with expected reconciliation totals.
Then implement the client-specific contract, with native company/role enforcement
and ledger/statement equality tests. No client-specific layout or approval flag is
implemented before sample approval.

The unreleased generic monthly bank-to-ledger report is independent of that
custom contract. Its source is
`addons/thirdcode_accounting/models/monthly_reconciliation.py`, with QWeb in
`addons/thirdcode_accounting/report/monthly_reconciliation.xml`. Select a complete
calendar month on an existing bank reconciliation record and use **Monthly
bank-to-ledger report**. It supports company-currency bank/cash journals and reads
the current posted ledger across all journals without changing stored balances.
It displays opening/closing balances, posted debits/credits, statement activity,
current matched/unmatched rows, recorded matching adjustments/reversals,
operator-entered outstanding totals, coverage gaps and unresolved differences.
Unmatched bank amounts are not automatically classified as book-side outstanding
items, and current matching status is not represented as a historic month-end
snapshot. Foreign-currency journals require a separately defined reconciliation
basis and are rejected explicitly.

Nine native regressions in
`addons/thirdcode_accounting/tests/test_monthly_reconciliation.py` cover arithmetic,
matching/reversal, scope, role/direct-render controls and non-mutation. Local
compilation, XML parsing and package validation passed, and all nine native tests
passed in CI 37288677011. Source `db771e5` adds an actual PDF smoke using the
Read-only role in the isolated CI clone; require it in the latest PR #10 checks.
[CI 37289593569](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/actions/runs/37289593569)
is the first run containing that addition, distinct from the previously observed
six financial-statement PDFs. This generic output does not close RP-04 or AC-03
and does not establish client format approval.

RP-01–03, AC-01/02/04, AR-02/05, STD-01–12 and RG-01/04/06/07 need client formats,
account mappings, cash-flow classifications, payment terms, tax/withholding
rules, authorized control/signature values and actual print stock. The accountant
must approve SOA opening/running/closing balances and ageing; financial statements
and comparatives; invoice/Official Receipt placement; statutory books/tax outputs;
and the CAS documentation pack. EIS applicability is a client-accountant decision,
not an inferred integration requirement. Keep developer previews provisional.

Independent work already available: native calculation and scope regressions,
rendering paths and retained sample evidence. Apply additional format changes
only against the supplied samples. Do not insert fake tax/control values, mark
samples approved, change numbering or issue official documents to complete this
checklist. Confirm recurring customer invoices (AR-06, assumed) and payment
threshold approvals (AP-07, optional) before treating either as a mandatory client
workflow.

## MYOB migration and the real parallel month

GL-01, DM-01–07, AC-05/06 and O4 need an authorized original MYOB file/export, the
extractor/version and file hashes; named finance owner; complete master mapping;
cutover date; open items and undeposited receipts; authoritative source trial
balance; and an approved history/retention policy. Preserve originals read-only
with independently retrievable storage. Archive-only history is the existing
non-overlap design. Requested live historical posting requires a separately
reviewed complete migration design before any import.

Validate a supplied six-CSV package without contacting Odoo:

```sh
python3 scripts/migration_validate.py \
  --input /private/authorized-myob/package \
  --report /private/evidence/myob-package-validation.json
```

This validator deliberately rejects overlapping economic bases. Do not weaken it
to mix opening TB and already represented transactions. The residual cutover
route is documented in `phase-2/CUTOVER.md`. After authorized source and mappings
have been retained in a **draft batch in the isolated rehearsal**, run its
read-only preview using environment credentials:

```sh
python3 scripts/cutover_load.py --batch-id 123 --company-id 1
```

Replace IDs with the verified rehearsal batch/company. Do not add `--apply` until
that rehearsal's approved mapping and source evidence have been checked. Compare
every TB line and AR/AP control balance, receipts and open-item residuals; exercise
interruption, retry/idempotency and archive retrieval. Record differences rather
than silently balancing them. A later production import needs explicit separate
authorization and a coordinated cutover backup.

AC-06/DM-06 requires one real accounting month posted in both systems and compared,
with opening and closing reconciliation, report comparison, discrepancy resolution
and the finance owner's decision. Synthetic fixtures, a compressed simulation or a
short live test cannot replace that elapsed period.

## Windows, roles and handover

NF-12/AC-08 requires actual supported Windows with current Chrome and Edge. Record
Windows build, exact browser versions, display scale, viewport and deployed
revision. Existing Mac/Linux evidence does not count as Windows coverage. A remote
Windows host/session has not been supplied, so this remains an environment input.

For each browser, use the native Odoo markup through the hosted `/workspace`
route, light and dark themes, and the real supported Administrator, Accountant,
Encoder and Read-only roles in an isolated copy. Rehearse login/company switching,
invoices/bills and drafts, posting/reversal/period controls, bank settlement,
exports/PDF/download/print, attachment retrieval and audit examination. Confirm
positive supported actions and negative cross-company/role cases; specifically
check encoder settlement/export denial and posted Reset/Cancel hiding. Record
first native table-cell bounds as well as viewport overflow, focus/keyboard
behavior and report output. Do not use Bootstrap-only fixtures or manipulate
production documents to demonstrate write paths.

The fresh release backup has already been downloaded, decrypted and hash-verified
off-host. Its exact payload restored into a fresh isolated database in 72.508
seconds and upgraded in 32.682 seconds, with restored and production baselines
preserved. Summary references are `offhost-verification.json` and
`restore-results.json`, held in the protected recovery evidence store. This
completed rehearsal must not be described as an in-progress task or repeated
merely to update this checklist. A future release still needs its own recovery
gates.

NF-05/06/10, AC-07, RG-05, O5 and role rows also require client audit examination,
retention and privileged-operator ownership. NF-08/09/10 and AC-09 require the
separate recovery destination, retention policy, failed/missed-run alert recipient,
operator/deputy, agreed RPO/RTO and demonstrated restore handover. One manual
backup/restore and separate volume snapshots do not constitute nightly coordinated
recovery. Track recurring recovery implementation and its isolated tests alongside
these remaining operational inputs; never fabricate successful off-host delivery.

## Closure record

### Consolidated client decision checklist

No decision below is presumed approved. Existing generic code, proposed defaults,
synthetic tests and developer previews are preparation only. Retain the actual
decision, sample revision and approver privately when supplied.

| Required decision or evidence | Present boundary / responsible party | Relevant source paths |
| --- | --- | --- |
| Name Client Owner, Technical Adviser, finance lead, five intended users and acceptance signatories; agree baseline scope and provisional role matrix | CEO nominations pending. Client Owner approves on Technical Adviser recommendation; developer owns technical implementation only. AR-06 recurring invoices is assumed; AP-07 threshold approval is optional until confirmed. | `TURNOVER-DECISIONS.md`; `requirements.csv` ROLE rows, AR-06, AP-07; `addons/thirdcode_accounting/security/thirdcode_groups.xml` |
| Approve versioned client report samples and meaning of every amount: SOA, financial statements/comparatives, invoice/receipt and RP-04 monthly reconciliation | Finance lead validates sources, dates, signs, rounding, totals and layout; Client Owner approval follows adviser recommendation. RP-04 sample/contract absent; generic monthly report is provisional. | `requirements.csv` RP-01–04, AC-01–04; `addons/thirdcode_accounting/models/report_sample.py`; `addons/thirdcode_accounting/models/monthly_reconciliation.py`; `addons/thirdcode_accounting/report/monthly_reconciliation.xml` |
| Provide authorized original MYOB extraction and authority to use it; agree source hashes/version, mappings, cutover date, history/retention and expected TB/open items | No authorized source or migration approval established. Named finance owner must approve source and accounting mapping. Archive-only history is the implemented non-overlap proposal, not assumed client approval. No production import is authorized by a development test. | `MIGRATION-DESIGN.md`; `phase-2/CUTOVER.md`; `scripts/migration_validate.py`; `scripts/cutover_load.py`; `requirements.csv` GL-01, DM-01–07, AC-05/06 |
| Confirm chart/tax/withholding/cash-flow mappings, payment terms/instruments, document stock/signatures/control values and EIS/CAS applicability | Client finance/tax decisions pending. No fabricated statutory values, issued documents or inferred EIS integration. | `docs/cas-control-pack.md`; `addons/thirdcode_accounting/models/tax_profile.py`; `addons/thirdcode_accounting/models/financial_report.py`; `requirements.csv` RG and STD rows |
| Supply actual recovery account/destination/access, alert recipient, operator/deputy; accept operational schedule, retention, RPO/RTO and demonstrate handover | Engineering defaults and adapters do not establish client operations acceptance or statutory retention. Actual provider delivery, failure/missed-run alerts and operator handover need evidence. | `RECOVERY-AUTOMATION.md`; `HOSTED-OPERATIONS.md`; `requirements.csv` NF-08/09/10, AC-09 |
| Supply representative annual workload and agreed performance protocol; provide supported Windows Chrome/Edge environment | Current small-dataset and loopback results do not prove proposed annual-volume, end-user latency or Windows targets. | `requirements.csv` NF-02/03/04/12, O2, AC-08; `scripts/benchmark.py`; `addons/thirdcode_accounting/models/financial_report.py` |
| Schedule and complete the real parallel accounting month, resolve discrepancies, examine audit evidence and record acceptance | Actual elapsed month and client review remain open. Synthetic fixtures and deployment health do not replace this evidence. | `requirements.csv` AC-05–09, DM-05/06, O4/O5; `AUDIT-COVERAGE.md`; `SWARM-CHECKPOINT.md` |

Paths without a `docs/`, `addons/` or `scripts/` prefix are relative to this
checklist's directory. `docs/`, `addons/` and `scripts/` paths are repository-relative.

For each affected one of the 92 matrix rows, retain: expected outcome, exact source
revision and environment, repeatable test/command, observed result, private evidence
reference, missing input with responsible owner, and acceptance decision when
actually supplied. Keep deployed engineering, local regressions, isolated hosted
results, production read-only observations and client acceptance distinct. No
completion percentage can replace the outstanding business, environment and
elapsed-time gates above.
