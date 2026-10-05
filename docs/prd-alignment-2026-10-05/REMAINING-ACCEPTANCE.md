# Remaining acceptance work after release 18.0.2.13.1

This is an execution checklist, not a new acceptance claim. The current 92-row
requirements matrix and `release-13.1/FINAL-IMPLEMENTATION.md` in the primary
checkout remain the detailed evidence record. Historical phase-2 results do not
supersede the latest hosted latency failure. Keep financial source files, report
PDFs, credentials and raw recovery evidence outside public Git.

## Implemented benchmark safeguards; hosted measurement still required

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
separated. Preserve the existing 20-transaction failed baseline separately rather
than claiming an exact like-for-like comparison after changing this protocol.
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
queries. Preserve report hashes and timings privately. A new annual benchmark
mode is deliberately not included until this data/period contract is supplied;
existing small-fixture PDFs prove neither annual-volume performance nor client
format approval.

## Client reports, custom RP-04 and statutory configuration

RP-04/AC-03 is still undefined. Obtain one approved sample and a field-level
contract: source and meaning of every column, formula/sign/rounding, grouping,
opening and closing balances, date/cutoff rules, unmatched/timing items, totals,
bank-statement link, correction behavior and layout. Identify the approving
accountant and a real authorized example with expected reconciliation totals.
Then implement only that contract, with native company/role enforcement and
ledger/statement equality tests. The existing standard bank-summary report is
reusable source evidence, not the missing custom report. No speculative report or
approval flag is added while this definition is absent.

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

NF-05/06/10, AC-07, RG-05, O5 and role rows also require client audit examination,
retention and privileged-operator ownership. NF-08/09/10 and AC-09 require the
separate recovery destination, retention policy, failed/missed-run alert recipient,
operator/deputy, agreed RPO/RTO and demonstrated restore handover. One manual
backup/restore and separate volume snapshots do not constitute nightly coordinated
recovery. Track recurring recovery implementation and its isolated tests alongside
these remaining operational inputs; never fabricate successful off-host delivery.

## Closure record

For each affected one of the 92 matrix rows, retain: expected outcome, exact source
revision and environment, repeatable test/command, observed result, private evidence
reference, missing input with responsible owner, and acceptance decision when
actually supplied. Keep deployed engineering, local regressions, isolated hosted
results, production read-only observations and client acceptance distinct. No
completion percentage can replace the outstanding business, environment and
elapsed-time gates above.
