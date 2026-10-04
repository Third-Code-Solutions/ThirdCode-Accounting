# Verification record and reproduction

Candidate addon `18.0.2.12.0`. Tests ran 4 October 2026 UTC / 5 October Asia/Manila. Only `tcsi_alignment_*` databases were written. No production accounting credentials were available or used.

Committed plain-text log copies normalize trailing whitespace and line endings; event text and values are preserved. Original `.log` captures remain in the local evidence directory.

## Results

- `full-native-release-final.txt`: **93 native Odoo tests, 0 failures, 0 errors**. Includes the context-default, receipt rollback/retry/year-boundary and year-end income-statement regressions.
- `settlement-expenses.txt`: **2 additional native tests, 0 failures, 0 errors**, added after the 93-test run. They verify advance allocation/customer refund and complete employee/company-paid expense flows. Total distinct candidate native tests exercised: **95**. The two targeted tests ran against the same upgraded database/dependencies; a single combined 95-test execution is not claimed.
- `platform-tests.txt`: **61 passed**: contracts4, worker2, web55.
- `migration-policy.txt`: **5 passed**. Reproduction: `python -m unittest discover -s scripts -p test_migration_policy.py` from repository root.
- Package manifest resource validation, Python compilation and `git diff --check` passed; details in `source-validation.txt`.
- `baseline-native.txt`: 22 original financial-control tests passed before changes. Tests previously permitting reset/cancel, sudo economic edits and posted bank amount changes were replaced to match GL-08/RG-03.
- `milestone-workflows.txt`, `full-workflows.txt`: native RPC workflow results, synthetic records only. The latter originally checks employee expense draft surface; the additional native test supplies complete reimbursement evidence.
- `concurrency.txt`: two real concurrent cursor threads; closed-period race behavior and repeated receipt assignment pass. The PostgreSQL serialization error logged during the post/close race is expected; the retry observes closure and rejects posting. `concurrency-before-flush.txt` records the initial failure that led to the explicit ORM flush correction.
- `upgrade-rehearsal.txt`, `upgrade-check.txt`: module upgrade and retained journal/attachment/audit evidence.
- `backup-restore.txt`, `recovery-source.txt`, `recovery-target.txt`, `recovery-verification.json`: quiescent synthetic native ZIP dump/restore and source/target comparison. Raw snapshot labels mistakenly said “twelve-month”; the comparison JSON corrects this to one posted journal. Numbers/hashes are unchanged.
- `report-render.txt`, `reports/*`: twelve-month comparative financial calculations/PDFs. `standard-reports-final.txt`, `standard-reports/*`: actual OCA outputs. VAT output is empty of tax-tag data; availability only. Journal listing has OCA unused `t-eval` warnings.
- `report-wizard-light.png`, `report-wizard-dark.png`: actual native UI, Chromium on Linux, 1280px viewport/document with no horizontal overflow; modal width800/scrollwidth798. Browser closed after verification.
- `performance-*.json`: all measured runs, including failed latency targets; see REPORT.md. Do not combine quiet two-user results with ten-user performance claims.

## Runtime and reproduction boundaries

Prepared Docker image `tcsi-cloud-dev` (`678275793ec0`) contains Odoo `18.0-20260908` and repository-pinned OCA dependencies. PostgreSQL16 used disposable named volumes; the candidate addon was bind-mounted at `/opt/extra-addons/thirdcode_accounting`. The prepared test image uses `PYTHONPATH=/opt/tcsi-test-deps` for test dependencies. The environment required root inside the disposable test container because host source directories had mode0700; this is not a proposed production runtime identity.

Use the repository's Docker build/compose definition with an isolated database and separate filestore. Create an unmodified-baseline fixture for upgrade tests, then use the candidate image/addon and run Odoo with these arguments (configuration/database values must point only at the isolated stack):

```text
-c /etc/odoo/odoo.conf -d tcsi_alignment_upgrade -u thirdcode_accounting
--test-enable --test-tags /thirdcode_accounting --stop-after-init --no-http --max-cron-threads=0
```

Final additional test selector used:

```text
/thirdcode_accounting:TestFinancialControls.test_advance_later_allocation_and_customer_refund_reconcile,/thirdcode_accounting:TestFinancialControls.test_employee_reimbursement_and_company_paid_expense_post_to_ledger
```

`alignment_fixture.py`, `alignment_concurrency.py` and `alignment_standard_reports.py` run through `odoo shell`; each rejects a database name outside `tcsi_alignment_`. Fixture modes are `ALIGNMENT_MODE=seed`, `reports`, or `snapshot`. Seed uses synthetic2025 invoices; reports outputs PDFs/JSON into `/tmp/alignment-reports`. The concurrency probe requires seeded accounts/a posted receipt and chooses future dates beyond existing periods so it can be rerun. It commits synthetic records intentionally. Standard-report script writes to `/tmp/alignment-standard-reports`; a local HTTP report asset service must listen inside the container at8069. Never use these scripts against a client database.

The existing milestone/full-scope RPC scripts also create synthetic records. They were run against `127.0.0.1:8071`, `tcsi_alignment_candidate_v2`, with isolated test accounts. Preserve their exact dataset boundaries; do not run against production for verification. Benchmark invocation used `--iterations 20 --workers 2` or `10`, `--post`, the same local endpoint/database and explicit JSON output. The initial run had10 iterations.

Recovery used native Odoo `dump_db` / `restore_db` on a source with no HTTP/cron writers, with database-management permission enabled only in the offline shell. Restore neutralization was enabled. The resulting local ZIP was4,248,989bytes, SHA-256 `b9493cdb93065232211cc02267537dd10b1acf2b500074cd019ad4848c5f807f`; it is not a production backup or separate remote recovery destination. Read [HOSTED-OPERATIONS.md](../HOSTED-OPERATIONS.md) before any real rehearsal.

No production deployment, Railway version verification, Windows browser verification, real MYOB migration, full parallel month, real sample approval or hosted nightly scheduler verification is represented by these results.
