# Candidate 18.0.2.13.0 verification

All accounting writes used isolated synthetic `tcsi_alignment_*` databases. Runtime: Odoo Community18.0-20260908, PostgreSQL16, prepared `tcsi-cloud-dev` image678275793ec0 and pinned repository OCA dependencies. Candidate addon mounted read-only into disposable containers. No Railway or customer-book accounting test is represented here.

- `release-native.txt`: **109 native tests, zero failures/errors**, one combined module run. `soa-ageing-final.txt`: the subsequently strengthened SOA assertion also verifies90 in the1–30-day bucket, zero failures/errors. Same application source; explicit test due dates added after the combined run.
- `migration-policy.txt`: **five** legacy CSV validation tests pass. Combined residual cutover tests belong to the native suite, not this count.
- `concurrency.txt`: real committed cursors; four consecutive journal numbers, two consecutive receipt numbers, one recurring result for two simultaneous runs, plus period-close races and receipt retry. Expected serialization conflicts are retried; these are not hidden failures.
- `upgrade-before.json` / `upgrade-after.json`: identical original posted documents/lines/balances/audit details/document metadata/filestore hashes across the `.12`→`.13` upgrade. `rich-upgrade.txt` records the upgrade; `final-view-upgrade.txt` records the later SOA/view refresh.
- `release-recovery*.json` / `release-recovery.txt`: final quiescent database+filestore ZIP restored to a new isolated database and compared. Earlier `recovery*.json` / `recovery.txt` are retained historical rehearsals. `archive-retrieval.txt` verifies the original source bytes and historical rows in the first restored database. Final snapshot fingerprints preserve those same archive rows and bytes.
- `cutover-fixture.txt`: five-entry residual opening, per-account equality, retained source and two non-posting history rows. `cutover-policy-review.txt`: explicit archive-only setting and retry returns the same moves. This is synthetic configuration, not client approval.
- `reports/*`: actual VAT, withholding, standard bank summary, comparative BS/P&L/cash PDFs and calculation JSON. `standard-reports/*`: actual OCA TB, GL, journal, ageing, unpaid, empty tax-tag VAT and SOA PDFs. OCA journal `t-eval` warnings remain visible. Ledger tax summaries are separate positive VAT/withholding evidence.
- `performance-2.json` and `performance-10.json`:20 posted invoices each. Two-user p95 meets the proposed2-second target; ten-user latency does not. `performance-2.txt` is the initial fixture-selection error before posting; corrected harness selects an explicit/default company and rejects non-isolated DB names.
- `ui/*`: actual native Odoo markup/CSS in Chromium/Linux, light/dark report/configuration pages and first-cell/overflow metrics. The `cutover-before-view-fix.png` screenshot is historical evidence of misleading editable controls; the final view removes them while retaining backend immutability. No Windows browser acceptance is claimed.
- Earlier first/second/third test logs are retained: they exposed attachment inverse timing, cutover state ordering, numeric journal codes interpreted as years, invalid QWeb `t-field` placement, a test fixture's missing user-administration rights, and SOA activity totals excluding opening. Later named final runs establish the fixes; failed historical logs are not counted as passes.
- No portal/worker/contracts changes: the earlier61 tests are inherited historical evidence. Python/XML/package and whitespace results are in `source-validation.txt`; source/evidence hashes are retained for review.

## Reproduction

Build the pinned Docker configuration in an isolated environment. Run the candidate module with an isolated database/filestore:

```text
odoo -c /etc/odoo/odoo.conf -d tcsi_alignment_upgrade -u thirdcode_accounting
     --test-enable --test-tags /thirdcode_accounting
     --stop-after-init --no-http --max-cron-threads=0
```

The prepared cloud test container needed `PYTHONPATH=/opt/tcsi-test-deps` and root to read mode0700 host source mounts. This is a fixture accommodation, not a production identity recommendation.

`scripts/alignment_concurrency.py`, `alignment_completion_reports.py`, `alignment_standard_reports.py` and `alignment_recovery.py` execute through native `odoo shell`. They reject DB names outside `tcsi_alignment_`. `alignment_cutover_fixture.py` creates a fresh synthetic company specifically in `tcsi_alignment_phase2`; it reproduces the retained opening/archive proof. The concurrency and completion-report scripts also intentionally post synthetic transactions. Report scripts need the seeded chart/partner and an HTTP asset service on localhost8069 inside the report container. They write PDFs/JSON under `/tmp/alignment-completion-reports` or `/tmp/alignment-standard-reports`.

The standalone `alignment_snapshot.py DATABASE OUTPUT [--baseline PATH]` uses the prepared Docker fixture read-only. It hashes original audit rows up to the baseline ID boundary, so new upgrade audit events cannot conceal edits to old evidence. It checks posted document identity/economics, account balances, attachments, retained cutover/history content and actual filestore bytes.

Before `alignment_recovery.py`, stop HTTP/cron/background writers. Mount `/tmp/alignment-recovery` to retain the ZIP. An optional `ALIGNMENT_RECOVERY_TARGET` must be a different, nonexistent `tcsi_alignment_` database. The script refuses overwrites, uses native ZIP dump/neutralized restore, and records duration/hash; separately compare snapshots afterward. Real hosted configuration, secrets, remote storage, retention and operational monitoring require the production procedure in `HOSTED-OPERATIONS.md`.

The stronger SOA test can be reproduced with selector:

```text
/thirdcode_accounting:TestAccountingCompletion.test_soa_opening_activity_running_balance_and_ageing
```

No real MYOB migration, full parallel month, actual sample approval, statutory acceptance, nightly hosted scheduler verification or production deployment is represented by this evidence.
