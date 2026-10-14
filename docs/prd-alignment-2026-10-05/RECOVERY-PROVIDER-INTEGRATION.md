# Recovery provider integration — engineering proposal, disabled

This extends [the coordinated capture tool](RECOVERY-AUTOMATION.md); it does not replace its writer topology, pidfd watchdog, transaction checks or manifest. No bucket, credentials, notification recipient, job or production restore has been created or activated by this source change. Passing local tests does not establish NF-08–10 or AC-09 acceptance.

The proposed pilot uses a private AWS S3 bucket, preferably in a separate account, versioning and GOVERNANCE Object Lock; 35 days of operational backup retention; capture at 02:00 Asia/Manila; monthly full restore drills; a 24-hour RPO and 4-hour RTO target. The user authorized engineering recommendations. These are **not accepted client commitments, statutory record-retention decisions or achieved service levels**. Client Owner approval follows the Technical Adviser's recommendation; named people remain pending CEO designation. Keep the current decision/access checklist in [REMAINING-ACCEPTANCE.md](REMAINING-ACCEPTANCE.md), rather than inventing approvals in configuration.

## Components and boundaries

| Component | Implemented behavior | Still requires operational proof |
| --- | --- | --- |
| `scripts/hosted_recovery_delivery.py` | Synchronous, conditional encrypted upload; full readback SHA-256; exact locked payload/receipt versions; immutable run receipt | Real approved bucket, IAM boundaries, transport and readback evidence |
| `scripts/hosted_recovery_alert.py` | Approved HTTPS recipient, protected bearer token, bounded retry deduplication, matching acceptance acknowledgment; rejects redirects | Real receiver and acknowledged alert/failure exercise |
| `scripts/hosted_recovery_provider.py monitor` | Independent object-store freshness and exact-version lock check; no dependence on live engine/local status | External monitor and independent alert on its own failure/missed invocation |
| `retention-plan` / `retention-apply` | Policy-bound, expiring, explicitly approved exact-version deletion; legal-hold/lock refusal; durable progress journal | Approved operational retention, maintenance identity and reviewed first plan |
| `scripts/hosted_recovery_drill.py` | Off-host download, encrypted hash, local-key decryption, safe extraction, manifest verification and optional full isolated restore orchestration | Actual provider/host access, scheduled execution and operator/deputy exercise |
| `scripts/hosted_recovery_restore.py` and `recovery_fingerprint.py` | Fresh database restore, original ledger/audit/attachment conservation, offline Odoo registry validation and measured execution time | Independently verified running image, whole recovery RTO, business acceptance and handover |
| `deploy/recovery/*.example` | Disabled provider/restore policies and external systemd capture/monitor/full monthly drill templates | Real engine transport, provisioned isolated runtime, scheduler IDs and missed-job alarms |

The provider supports AWS general-purpose S3 buckets, or an explicitly selected HTTPS S3-compatible endpoint with equivalent conditional writes, versioning and Object Lock APIs. Do not substitute an unverified compatible provider. It requires an explicit private credentials file rather than an ambient credential chain. No SDK credentials or private key belong in the image or repository.

## Installation and private policy

Install the optional provider SDK in a dedicated operator environment using the fully pinned hash-checked dependency file:

```sh
python3 -m venv /opt/tcsi-recovery/venv
/opt/tcsi-recovery/venv/bin/python -m pip install --require-hashes --only-binary=:all: -r scripts/recovery-provider-requirements.txt
```

Copy `hosted_backup.py`, `recovery_fingerprint.py`, `hosted_recovery_provider.py`, both adapter scripts, `hosted_recovery_drill.py` and `hosted_recovery_restore.py` together under `/opt/tcsi-recovery/scripts/`. Hosted capture still requires the current runtime's `psycopg2`, PostgreSQL client and OpenSSL dependencies. The provider SDK environment is separate; full restore invokes the explicitly selected Python with the matching pinned Odoo and psycopg2 installation. Installing the provider dependencies does not alter the Odoo environment.

Copy `deploy/recovery/provider-policy.json.example` to `/etc/tcsi/recovery-provider.json` only in the selected environments. Fill real approved values and evidence references privately before enabling. Missing fields or `enabled:false` fail before a provider call. Policy, credentials and token files must be regular, owned by their invoking OS user and 0600. Private work directories must be 0700. On the engine this is `odoo`; on the external controller/monitor it is the dedicated `tcsi-recovery` user. Use different least-privilege identities and credentials in each environment. Example credentials schema, with intentionally empty secrets:

```json
{"access_key_id":"","secret_access_key":"","session_token":null}
```

`artifact_root` on the engine must exactly encompass the capture policy's private `state_dir`. The capture `destination` must match the provider alias. Use `adapter_timeout_seconds:960` with the proposed provider `operation_timeout_seconds:900`, after measuring real transfer size and time. Capture pause remains independently bounded by `max_pause_seconds`; upload happens after writers resume. The single-PUT size ceiling is 5 GiB. Larger artifacts fail; multipart support is not implemented. Quotas, storage growth and duration must be reviewed before activation.

The capture core deliberately supplies only `/usr/bin:/bin` as adapter PATH. A virtualenv will therefore **not** be selected by the source adapter's `#!/usr/bin/env python3`. Install each executable adapter wrapper with an explicit interpreter, for example:

```sh
#!/bin/sh
exec /opt/tcsi-recovery/venv/bin/python /opt/tcsi-recovery/scripts/hosted_recovery_delivery.py --config /etc/tcsi/recovery-provider.json
```

Use the corresponding `hosted_recovery_alert.py` path for the alert wrapper. Wrappers are regular executable files, never group/world writable. They contain no credential values. Point capture `delivery_command`/`alert_command` to these absolute wrapper paths. Do not change the core's minimal environment to expose secrets.

## Destination isolation and receipt semantics

Provisioning remains an operator action against the approved account. Require block-public-access, TLS, bucket-owner-controlled access, enabled versioning, Object Lock and no automatic lifecycle deletion that bypasses the application's minimum-copy rule. Retain the exact deployed image and registry access throughout the same recovery period. The application writes already encrypted CMS EnvelopedData; only the separate recovery host holds the private key.

Separate permissions by identity. The capture identity needs bucket versioning/Object Lock reads, object GET/HEAD, conditional PUT and retention placement/read under the dedicated bundle/receipt prefix. The independent monitor needs bucket checks, receipt listing/reads and exact-version object/retention reads. The separate maintenance identity additionally needs exact-version deletion and legal-hold reads. **Never grant `s3:BypassGovernanceRetention` to these identities; never grant application delete, bucket-policy administration, legal-hold removal or Object Lock reconfiguration.** Restrict bucket-level listing to the approved prefix. Verify effective permissions, including inherited policies, before activation; source cannot establish IAM isolation.

[AWS Object Lock documentation](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html) explains that protection is version-specific and GOVERNANCE can be bypassed only with the separate bypass privilege and request header. The adapters neither request nor send that bypass. Per-version checks remain necessary even with a bucket default. [PutObject's documented checksum requirement](https://docs.aws.amazon.com/AmazonS3/latest/API/API_PutObject.html) is met explicitly with SHA256 algorithm/checksum headers on payload and receipt uploads.

For each UUID, the adapter conditionally creates `bundles/<UUID>.p7m` and `receipts/<UUID>.json`. It reads every encrypted payload byte back from the returned version, compares size/SHA-256, then verifies GOVERNANCE retention on both exact versions before acknowledging durability. It does not trust ETag or user metadata as a full-file checksum. SDK lock dates are rounded upward to whole seconds before upload; the horizon covers the approved days from provider creation with bounded upload headroom. Retry cannot shorten the original horizon or overwrite an existing run.

Receipt `captured_at` comes from the trusted capture invocation and matches the encrypted manifest timestamp; `verified_at` records provider object creation, and `readback_verified_at` records readback completion. **RPO freshness uses `captured_at`, never upload/retry time.** Off-host preparation checks the decrypted manifest timestamp against the receipt. Legacy delivery callers missing `captured_at` fail closed; third-party adapters that ignore the additional field remain compatible with the capture core.

A timeout may leave an encrypted, locked payload without its receipt. Inspect that run's keys and versions before retrying; do not invent a receipt or delete an orphan automatically. Repeating delivery for the same run requires the same bytes and capture timestamp. Core capture removes its local staging artifact after the synchronous adapter returns; retain any private incident evidence needed before recovery. The next normal capture gets a new UUID.

## Alerts and independent scheduling

The HTTPS receiver must accept JSON fields `event`, `status`, `run_id`, `destination`, `recipient`, `at`, `event_id`; authenticate the bearer token; honor `Idempotency-Key`; and return HTTP 200/201/202 with `{"accepted":true,"event_id":"<same event id>"}` only after its agreed notification channel accepts the message. A plain Slack webhook is not this acknowledgment protocol. IDs repeat within the configured deduplication window; persistent incidents become eligible for later reminders. The adapter never logs the token, request URL, raw SDK exception or HTTP response. A nonzero result remains a failed notification.

Templates have `.example` suffixes and no install targets. Nothing invokes `systemctl enable`, schedules uploads or sends alerts. Review them on the selected Linux controller with `systemd-analyze verify` and calendar expressions with `systemd-analyze calendar` before installing real unit names. The calendar expressions use explicit `Asia/Manila`; see the [systemd time syntax](https://www.freedesktop.org/software/systemd/man/latest/systemd.time.html) and [timer semantics](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html).

The capture controller must supply `/usr/local/libexec/tcsi-capture-in-engine`, using an approved authenticated transport to execute the existing capture command **inside the current engine container as `odoo`**. It must propagate exit status, bound the remote command, prevent detached work, and record the actual run ID. A separate Railway cron container does not share the primary process tree and cannot coordinate its Odoo writers. No new SSH server, broad remote shell credential or unverified Railway control API is supplied here. This transport still needs implementation/validation against the selected platform access; the missing executable makes the template fail visibly.

The independent monitor runs outside Railway **and outside the capture controller's host failure domain**. It lists trusted receipts, checks latest capture age against 24 hours, and verifies payload existence/size/hash metadata plus exact payload/receipt lock horizons. This periodic HEAD/retention check is not another full byte readback; full byte verification occurs at delivery and drill preparation. Missing, stale, invalid or unreachable storage triggers an approved alert and nonzero exit.

The external operations control plane must also detect a missing monitor invocation, controller/monitor host loss and alert-adapter failure. `OnFailure` is an additional attempted notification, not proof that a dead host can report itself. Record monitor/job IDs and that separate dead-man alarm during activation. Test disabled capture, failed upload, stale snapshot recently uploaded, unreachable bucket, lost engine, stopped scheduler and failed notification receiver. A 15-minute observation interval can discover a 24-hour threshold breach up to 15 minutes later; it does not improve the backup's recovery point. Daily scheduling plus processing/jitter can exceed a strict 24-hour maximum; client acceptance must either approve that measurement boundary or require more frequent capture.

## Guarded operational retention

Retention is disabled by default and belongs to the separate maintenance identity. After the operational policy is approved, set `retention.apply_enabled:true` only in that private maintenance policy. This alone deletes nothing. Generate a new private plan:

```sh
/opt/tcsi-recovery/venv/bin/python /opt/tcsi-recovery/scripts/hosted_recovery_provider.py retention-plan --config /etc/tcsi/recovery-provider.json --plan /private/recovery/retention-plan.json
```

Inspect every version and the returned plan digest. Explicitly approve that digest, then execute:

```sh
/opt/tcsi-recovery/venv/bin/python /opt/tcsi-recovery/scripts/hosted_recovery_provider.py retention-apply --config /etc/tcsi/recovery-provider.json --plan /private/recovery/retention-plan.json --approve-plan-sha256 <approved-plan-sha256>
```

The policy binding includes `apply_enabled`; set its approved maintenance value **before generating** the plan, otherwise generate a fresh plan after changing it. Plans expire after one hour. Apply revalidates the entire inventory before the first delete, requires a fresh protected latest backup, keeps at least two newest recovery points, and considers only objects older than the approved retention days. It checks legal holds and expired lock periods before each exact-version delete. No arbitrary keys, bucket-wide deletion, simple delete markers or bypass are used. A recent upload of an old snapshot cannot justify deleting existing recovery points.

Before each delete, `<plan>.journal.json` records the exact key/version and completed runs; storage failure prevents that delete. Every successful removal is checked by version-specific HEAD. A timeout or partial failure retains the pending version in the journal. Do not rerun blindly: inspect that exact provider version, preserve the journal, reconcile any orphan receipt/payload and create a newly reviewed plan. An existing journal intentionally blocks automatic reapplication. This is operational backup rotation, not authorization to delete statutory records or remove legal holds.

## Monthly full restore drill

The monthly template now invokes the implemented full drill. It selects the latest healthy captured snapshot, creates a unique private output directory and a fresh `tcsi_alignment_restore_<UUID>` database, restores the dump and filestore, compares accounting/attachment fingerprints, disables restored cron/mail, and loads Odoo offline before comparing again. The target database and evidence remain available on both success and failure; the tool never drops databases or reuses an existing target. Keep the template disabled until the actual dedicated recovery host, provider credentials, local PostgreSQL, pinned matching Odoo runtime and network isolation are provisioned and verified.

The current launcher requires a dedicated recovery host with a separately provisioned matching local Odoo interpreter and addons, outside the Railway engine image layout. Preparation rejects Railway environment identifiers and `/opt/tcsi/cloud_start.py`; that file is included in every engine image. Running the launcher inside the retained engine image is therefore not supported by this entry point. Do not remove the marker file or clear Railway variables to bypass the guard. A container-based recovery launcher needs an independently reviewed host/container identity and isolation contract before use; an absent engine process alone does not prove that the host is separate.

Copy `deploy/recovery/restore-policy.json.example` to a private mode-0600 `/etc/tcsi/recovery-restore.json`. Supply dedicated loopback PostgreSQL credentials and the captured revision/image/version. The tool never reads database credentials from the archived `odoo.conf` or recovery environment. Only explicit IPv4/IPv6 loopback endpoints are accepted; extra libpq options and ambient routing/service overrides are rejected. Effective libpq client host/hostaddr/port and database/user identity are checked before use. PostgreSQL's server-side address can legitimately differ behind a local container port mapping; it is not the client endpoint. Confirm the host's outbound network controls separately: retrieval needs the provider, while the restored Odoo process must have no external integration path. HTTP never starts; cron/mail are disabled before registry loading, SMTP is blocked in the validation process, and only owned subprocess groups are terminated on interruption or deadline.

On the separate recovery host, choose an actual receipt UUID and a new private output directory:

```sh
/opt/tcsi-recovery/venv/bin/python /opt/tcsi-recovery/scripts/hosted_recovery_drill.py --config /etc/tcsi/recovery-provider.json --run-id <receipt-UUID> --output /private/recovery/new-drill --private-key /private/keys/recovery.key --public-certificate /private/keys/recovery.crt --confirm-offhost-recovery
```

For an encrypted private key, use `--passphrase-file /private/keys/passphrase`, never a passphrase in argv/environment. Keys never upload to Railway. The command rejects recognized engine environments, downloads an exact version, verifies all encrypted bytes, decrypts locally, rejects traversal/link/special/duplicate archive members, bounds extraction and verifies every manifest member. A failed invocation removes only its exclusively created output directory. A successful output remains sensitive; preserve or dispose of it under the approved drill policy.

`drill-preparation.json` records preparation alone. Add `--full-restore --restore-config /etc/tcsi/recovery-restore.json --restore-python /usr/bin/python3` to perform the database/Odoo checks. For scheduled execution use `--run-id latest --output-root /private/tcsi-recovery/drills` instead of a fixed receipt/output. The resulting `drill-results.json` links preparation and restore results and measures retrieval through validation; `restore-results.json` records individual conservation flags and restore time. Secrets, raw subprocess logs, restored data and private configurations remain inside the protected drill directory and must not be published as CI artifacts.

New coordinated captures include `accounting-baseline.json`, generated inside the existing paused-writer/table-lock window and bounded by its remaining deadline. It hashes ordered accounting records, settlements, original audit history, company records, migration history when present, ledger balances, all attachment records and referenced file bytes. SQL produces canonical JSON text before psycopg numeric type conversion; Odoo's global Decimal-to-float caster cannot change the hash. Existing captures without this baseline are explicitly unsupported by the generic conservation verifier; preserve their separately recorded manual restore evidence instead of inventing a baseline after restore.

The actual running image is still an operator deployment proof: matching metadata alone is not image attestation. RTO remains unknown because these timings exclude provisioning, business reopening and operator handover. Follow [RECOVERY-AUTOMATION.md](RECOVERY-AUTOMATION.md#recovery-rehearsal-and-verification) and [HOSTED-OPERATIONS.md](HOSTED-OPERATIONS.md), execute the named operator/deputy runbook, and time the **whole** recovery against the proposed 4-hour target. Source or synthetic CI tests establish neither client acceptance nor measured production RTO.

## Verification

`python scripts/test_hosted_recovery_provider.py` uses disposable local files, a versioned provider model, real OpenSSL encrypt/decrypt and the pinned SDK's service model/serializer. It exercises changed bytes, stale snapshots uploaded recently, retry conflicts, shortened locks, whole-second wire dates, unavailable storage, alert acknowledgments, destructive plan boundaries, partial-deletion journals and archive traversal. Install the hash-pinned SDK first; a skipped SDK test is not a completed integration gate. `python scripts/test_hosted_backup.py` retains the core capture regressions. `python scripts/test_hosted_recovery_restore.py` verifies isolation guards and full-drill composition; with `TCSI_RECOVERY_RESTORE_TEST_PG=disposable-only` in native CI it clones only `tcsi_orvexa_hosted_ci` on loopback PostgreSQL 18, seeds synthetic invoices/settlement/attachment, performs a real dump/restore and native Odoo registry load, compares exact fingerprints across numeric typecaster changes, and rejects existing targets and altered ledger baselines. Native CI [37297823382](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/actions/runs/37297823382) passed all 12 restore tests on source `474994f`, including caller-SIGKILL/timeout cleanup, full PostgreSQL 18 restore, offline Odoo validation, existing-target refusal and altered-baseline refusal. The synthetic restore preserved 13 documents, 26 lines, 336 audit logs, 5,267 audit details and 426 referenced files; restore plus validation took 7.632 seconds. These are isolated fixture timings, not production RTO. No test contacts a real provider or notification recipient.

Remaining evidence: actual least-privilege account/bucket and independent monitoring access; named notification recipient/operator/deputy; client decision and policy references; retained immutable image; validated engine transport and scheduler IDs; live encrypted delivery/receipt and failure exercises; monthly full isolated restore, ledger conservation, timed recovery and handover. These remain explicit activation/acceptance work, not a claim that all recovery requirements are complete.
