# Isolated performance evidence

This protocol measures native accounting paths in isolated environments. It does not close NF-02/NF-03/NF-04, client report approval, multi-role coverage or Windows/browser acceptance by itself. Keep raw results and financial PDFs in protected storage outside Git.

## Baseline and diagnostic

The 13.2 hosted baseline used two Odoo workers and one actor across independent loopback HTTP sessions. At 40 transactions per run, save/post p95 were 3011.16/1476.87 ms for two sessions and 11930.36/11294.73 ms for ten sessions. All 80 transactions succeeded; both runs missed targets. The global ORM prefetch experiment did not improve latency and remains excluded.

The private one-use 13.2 profiler performs three native save/post pairs with SQL call counts, SQL execution time, table/callsite groups and cProfile. It guards the fixed isolated database, source version, company-owned synthetic fixture, disabled cron/mail and idle database. It compares original isolated rows/files and fresh read-only production fingerprints, retaining failure evidence. Profile instrumentation adds overhead: these are diagnostic service-cost samples, not acceptance timings. Its first call follows registry and fixture loading; neither database nor filesystem caches are cleared.

The corrected profile completed six operations with original isolated records/files and fresh production fingerprints preserved. Warm instrumented saves took 3.583/3.502 seconds and posts 1.653/1.666 seconds. Snapshot reads dominated the measured cost. Source `096a980` keeps a narrow journal-item relation dependency batch: native fixture snapshot queries fell from 25 to 22, while invoice headers retain native behavior at 25 queries. All eight matched cold/warm audit-history replays were identical in CI `37301445442`. These query counts and instrumented timings do not establish an improved hosted p95.

After the exact candidate run, inspect its retained server logs for native transaction retries before increasing load. Higher concurrency on two workers may include admission delay, database lock contention, native retries or resource throttling. The existing evidence does not separate those causes. Any follow-up sampler must be bounded, restricted to the isolated database and owned workers, and avoid SQL parameters. Do not change production worker allocation as a diagnostic.

## Candidate 13.3 hosted observation

Candidate `40e501c` completed 40 calls per two/ten-session case on the retained isolated copy. Save/post p95 were 2815.54/1438.20 ms and 10831.28/9059.27 ms respectively. All 80 transactions succeeded with zero probe/cleanup errors; both cases remained `TARGET_MISSED`. Upgrade, generic Read-only monthly PDF, original-row/file conservation and final idle/cron/mail guards passed. Retained native server logs have no reported serialization retries or errors. Further request-cost analysis is required before changing worker allocation or claiming queue duration; these observations do not establish hosted browser or client-volume acceptance.

The retained database is now 13.3. Use its new verified configuration below, not the older 13.2 source/configuration directory. Never point an older addon copy at an already upgraded database.

## Save/post rerun and queue evidence

Use the existing isolated server ownership/watchdog procedure. Record exact source SHA, addon version, PostgreSQL version, worker count, machine allocation, actor/company, existing cardinality and background traffic. Never run synthetic writes against customer books. Credentials use `ODOO_LOGIN`/`ODOO_PASSWORD` in memory; no password argument.

Run separately for two and ten client workers, preserving each result even on exit 2:

```sh
python3 scripts/benchmark.py --url http://127.0.0.1:18068 \
  --database tcsi_alignment_hosted_20261005 \
  --confirm-isolated-database tcsi_alignment_hosted_20261005 \
  --company-id 1 --iterations 40 --workers 2 --min-samples 40 --post \
  --output /private/new-run-two.json
```

Repeat with `--workers 10` and another output path. A target equality fails; errors, insufficient samples and target misses have distinct nonzero exits. Results now retain every sample, per-RPC monotonic interval, authentication/scope time, cleanup time and local executor wait. Intervals show actual overlapping save/post requests. **Client executor wait is not Odoo queue time.** Authentication and cleanup still contribute server load outside the save/post timers.

The two-versus-ten difference suggests contention but does not prove queueing. For direct evidence, correlate an instrumented isolated server's request receipt, handler-entry and completion timestamps using unique request IDs; record bounded PostgreSQL activity/wait snapshots and CPU alongside them. Separate socket/server admission wait from service execution. No server queue depth or queue duration is currently claimed by this harness. Do not infer queue time by subtracting separately profiled runs.

For cache boundaries, restart only the owned isolated server, capture its first measured call separately, then run a documented warm-up and a steady-state sample. Preserve all samples rather than mixing first calls into a claimed warm p95. A process restart does not flush PostgreSQL or OS caches. Run a second session through the actual hosted browser/network path and measure UI action through successful saved/posted state; API timings cannot establish that boundary. Test current Chrome and Edge on an actual Windows machine before recording Windows acceptance.

## Annual engineering scenario

The PRD supplies no approved annual transaction, line, history or attachment volumes. Use the following explicit synthetic scenario pending client volume approval; never present it as client data:

- Small smoke: 24 documents across 12 calendar months, one customer invoice and supplier bill each month; settle every third document through the native payment wizard. Expected 32 posted moves/64 journal lines with a simple chart; always report actual counts.
- Capacity candidate: 3,750 documents with the same settlement interval estimates 10,000 journal lines. This is an engineering proposal, not an approved workload. It is not authorized as an unbounded load on the shared production host. Use dedicated CI/capacity infrastructure after reviewing a small run and its resource cost.
- Single company and currency, one authenticated native actor, tax-free one-line documents, existing scoped accounts/journals/payment methods. Existing history and attachment counts/bytes are measured; the scenario adds no attachments. It does not cover client tax complexity or attachment-heavy history.

The optional `.github/workflows/annual-capacity.yml` runs the fixed capacity candidate on a dedicated ephemeral GitHub runner with PostgreSQL 18.6. Add `run-capacity-benchmark` to a same-repository PR after review for the full capacity scenario, or `run-capacity-diagnostic` for the fixed 192-document diagnosis. Only those explicit label events trigger the workflow; source pushes do not repeat it automatically. Remove the label after the finite experiment. Manual dispatch is also available after the workflow reaches the default branch and defaults to the smaller diagnostic. The ordinary quality workflow continues to use the 24-document smoke.

The larger scenario requires an explicit engineering-only CI marker and rejects arbitrary volumes and database routing overrides before creating output or connecting. Its budgets are 3,300 seconds for seeding, 3,600 seconds for the driver and 75 minutes for the job. The 30-second PDF target remains unchanged. Independent SQL checks require 1,875 invoices, 1,875 bills, 1,250 settlements, 5,000 new posted moves and 10,000 new lines; debit and credit must each equal 500,000 units across all 12 months. Actual report outputs, source revision, failure logs and container/OOM state are retained without configuration files or filestore contents. An incomplete or failed run remains a failure; even a passing run is unapproved synthetic engineering capacity, not hosted or client-volume acceptance.

The first capacity run, [37304128567](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/actions/runs/37304128567), failed during native seeding at its 3,300-second limit. The last checkpoint showed 1,284 documents and 428 payments; the uncommitted scenario rolled back. No final SQL oracle or PDF measurement followed. Cleanup and artifact retention succeeded; the container exited 1 with no OOM flag. Available memory and disk after the run were ample, but those endpoint observations do not exclude transient pressure. Keep the failed artifact as evidence.

The smaller diagnostic creates 192 native documents and 64 settlements (256 moves/512 lines), with a 720-second seed budget and 900-second driver deadline. An independent SQL oracle expects 19,200 document units, 6,400 payment units and debit/credit totals of 25,600. Timestamped 12-document checkpoints retain create/post/payment wall time, Python-process CPU and available native cursor/thread SQL counters, including on failure. No SQL text or parameters are collected; unavailable metrics are null. This diagnostic does not replace the failed 10,000-line capacity requirement. No batch commits, cache changes or weakened audit/accounting controls are introduced.

`scripts/benchmark_annual.py` runs inside the deployed Odoo Python environment. It refuses production names, mismatched config/filter, superuser/sudo, multiple active companies, active cron/mail, incomplete chart/payment configuration and reused evidence directories. No chart, lock date, role, audit or report approval changes are made. Seed failure rolls back the uncommitted scenario. Successful seed commits once; reports run afterward, so a report failure leaves the committed synthetic scenario and explicit `seed_committed` evidence. Re-run measurement with `--seed-documents 0` after inspecting that evidence; do not blindly seed again.

For the retained hosted copy, wrap execution with the established original-row/file conservation and read-only production fingerprint checks. Keep an outer process deadline. The seed budget is checked between native operations and cannot interrupt a single blocked SQL call. Use the guarded owned server for PDF assets, verify it serves the isolated database, and set `report.url` on that isolated database only. The harness checks the exact supplied loopback URL but does not prove process ownership itself.

```sh
python3 scripts/benchmark_annual.py \
  --config /var/lib/odoo/tcsi-recovery-report-20261005-40e501c/isolated.conf \
  --database tcsi_alignment_hosted_20261005 \
  --confirm-isolated-database tcsi_alignment_hosted_20261005 \
  --company-id 1 --actor-id 2 --year 2025 --seed-documents 24 \
  --settle-every 3 --max-seed-seconds 180 --repeats 2 \
  --render-pdf --report-url http://127.0.0.1:18068 \
  --output-directory /private/new-annual-smoke
```

Use an open accounting year; a native date shift or period lock must fail rather than bypass controls. Balance-sheet equality, cash-flow reconciliation and repeated calculation equality are asserted. Actual full-year/all-history moves and lines, attachment counts/bytes, oldest/newest date, native addon version and currency are recorded. PDFs stay private; JSON retains hashes/size and timings.

Calculation and native PDF generation are timed separately. PDF rendering calculates the report again, so do not add the two durations. Missing PDF measurement returns exit 3 (`CALCULATION_ONLY`); a rendered sample at or above 30 seconds returns exit 2. Below-target small smoke results are smoke observations only. `acceptance_claim` and `approved_client_volume` remain false. First/subsequent report calls are labelled honestly; no cold-cache claim or browser/network timing follows.

Local checks:

```sh
python3 scripts/test_benchmark.py
python3 scripts/test_benchmark_annual.py
python3 -m py_compile scripts/benchmark.py scripts/benchmark_annual.py
```

## Observed native CI smoke and release gate

[CI run 37288677011](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/actions/runs/37288677011) passed all three jobs at source `d3da03e`. Its disposable Odoo/PostgreSQL clone executed the annual scenario through native invoice, bill and settlement operations: 24 documents and eight payments added 32 posted moves and 64 journal lines. The measured ledger, including its existing synthetic fixture, contained 45 posted moves, 90 lines and three attachments totaling 914 bytes.

The six actual financial-statement PDFs covered balance sheet, profit and loss, and cash flow twice each. Native PDF generation took 2.202–4.604 seconds; balance-sheet equality, cash-flow reconciliation and repeat-stable calculations passed. This verifies the small synthetic annual smoke. It does not establish representative client volume, hosted browser/network latency, a cold-cache result or a correction to the failed 13.2 save/post targets.

Source `db771e5` added a separate generic monthly reconciliation PDF smoke under the native Read-only role, checking company scope, ledger/statement values, PDF bytes and unchanged accounting evidence. It also marks rollback or cursor-close failures as failed benchmark runs. Those additions passed at `096a980` in [CI 37301445442](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/actions/runs/37301445442), along with 139 native tests and the recovery/portal gates. Its six annual PDFs took 2.181–4.076 seconds on the same 45-move/90-line fixture; its Read-only monthly PDF took 2.486 seconds and preserved accounting evidence. Retain each run's summary, logs and PDF hashes separately. These small-fixture results do not establish a hosted module upgrade, production deployment or client-volume acceptance.
