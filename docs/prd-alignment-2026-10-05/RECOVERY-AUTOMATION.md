# Hosted recovery capture and monitoring

`scripts/hosted_backup.py` implements coordinated capture, failed/missed-run monitoring, and decrypted-bundle hash verification. The hosted image includes **opt-in** automatic capture and private S3 delivery; independent installations remain disabled by default. Source availability or a verified one-off backup does not prove an active schedule or close NF-08–10 / AC-09. Record deployed configuration, successful delivery, real failure notifications and restore evidence separately.

## Opt-in hosted automation

The launcher starts a separately supervised process under `odoo` only when `TCSI_BACKUP_ENABLED=1` and all configuration validates. Its failure cannot stop Odoo/nginx. It runs once daily at **03:00 Asia/Singapore** (19:00 UTC on the preceding date), never immediately at boot. A failed attempt retries at most twice, 15 minutes apart. Captures are synchronous and the existing exclusive lock prevents overlap with manual capture. The writer pause is capped at 120 seconds; existing watchdog/resume, idle-session and single-writer checks remain unchanged. Busy or unsafe capture fails instead of weakening those checks. The target RPO is 24 hours; failures can exceed that target and require operator intervention. Actual recovery remains operator-led and must be measured in rehearsals.

Required engine and independent monitor variables:

| Variable | Value |
| --- | --- |
| `TCSI_BACKUP_S3_ENDPOINT` | HTTPS S3 endpoint from the dedicated private Railway bucket |
| `TCSI_BACKUP_S3_REGION` | Bucket region |
| `TCSI_BACKUP_S3_BUCKET` | Bucket name |
| `TCSI_BACKUP_S3_ACCESS_KEY_ID` | Bucket-only access key; never an account API token |
| `TCSI_BACKUP_S3_SECRET_ACCESS_KEY` | Bucket-only secret |
| `TCSI_BACKUP_PREFIX` | Unique installation prefix, 1–64 letters/digits/underscore/hyphen; starts alphanumeric |
| `TCSI_BACKUP_MONITOR_ID` | Actual separately configured monitor service ID |

Engine-only variables: `TCSI_BACKUP_ENABLED=1`, `TCSI_BACKUP_PUBLIC_CERTIFICATE` (PEM public certificate, never its private key), `TCSI_BACKUP_OPERATOR`, `TCSI_BACKUP_RESTORE_CONTACT`, `TCSI_RELEASE_SHA` (verified 40-character source revision), and `TCSI_RELEASE_IMAGE` (immutable image/deployment reference ending in `@sha256:<digest>`). When Railway exposes only a digest, record `railway://project/<project>/deployment/<deployment>@sha256:<actualdigest>` truthfully; this is a provider identity, not a public Docker pull address. Provider image availability/retention must be verified separately. A retained local rebuild from identical source is not proof of identical OCI bytes. A single verified person may be both contacts; that is **single-owner operation**, not an independent deputy or completed two-person handover. Keep the decryption key off the host and preserve it separately from the bucket. Existing PG configuration supplies the database; no second ledger worker is created.

These release values are trusted operator attestations, not in-container image introspection. For CLI releases without provider Git metadata, the launcher supplies the explicitly verified `TCSI_RELEASE_SHA` to its Odoo child's `RAILWAY_GIT_COMMIT_SHA`, retaining the existing process/policy equality check. A conflicting provider revision or missing/invalid immutable image fails backup configuration. Build/deploy disabled first, obtain the actual deployed image digest and verify source externally, then enable using that exact image; verify any provider redeploy reuses it. Never insert a guessed digest or empty revision.

Delivery uses the isolated, hash-pinned Boto3 SDK. It uploads the encrypted object, downloads and hashes its bytes, persists and reads back a receipt, then publishes durable status. Retention runs only after a new verified delivery and removes objects older than 30 days with valid matching receipts under this installation's prefix. Unreceipted objects and other prefixes are untouched. The bucket has no assumed object lock/versioning/lifecycle policy; it is outside live volumes but shares the Railway account/provider failure domain.

Configure a **separate Railway cron service** using this image/source with start command `python3 /opt/tcsi/backup_runtime.py monitor`, hourly UTC schedule, no HTTP healthcheck, and restart policy `NEVER`. It needs only the shared bucket/monitor variables above, no PG credentials or live-volume mount. Configure native failed/crashed execution notifications to the verified operator. The checker fails on absent/malformed/failed status, receipt mismatch, age over 27 hours (or future timestamps), missing encrypted object, or mismatching size/SHA metadata. Full remote bytes are verified at delivery; the hourly checker verifies existence and recorded digest metadata, not another full download.

The capture alert adapter acknowledges **durable asynchronous attention status acceptance** only after the bucket writes and reads back the failure state. `accepted:true` is not a claim that email arrived. The independent checker turns that state into a failed execution routed through provider notifications. Its hourly polling can delay notification by up to an hour; subsequent successful capture supersedes failed status. Test an actual failed monitor execution and its provider notification before enabling the scheduler. If bucket delivery of attention also fails, no acknowledgment is returned; capture fails and freshness still detects a missing backup. A same-provider monitor cannot report complete Railway/control-plane loss or its own skipped invocations. External dead-man monitoring requires a separately configured account/heartbeat and remains an explicit coverage limit.

Activation gates: provision dedicated private bucket and actual monitor; validate real notification delivery; deploy with capture disabled; verify source/image provenance and single-writer topology; enable exact image; run `python3 /opt/tcsi/backup_runtime.py capture` once as `odoo`; run the independent checker; decrypt and verify/rehearse that delivered bundle; confirm the next scheduled run. Protect generated `/var/lib/odoo/recovery-state` (0700) and its policy/credential files (0600). The public certificate is stored there; the private key never is. Do not configure the main accounting service itself as a Railway cron service.

## Implemented boundary

- Linux only, using `pidfd_open` and `pidfd_send_signal` to bind process identities. The command discovers the Odoo master beneath `/opt/tcsi/cloud_start.py`, checks database, data path and deployed Git revision, then validates its dedicated process group. It never assumes PID 1 is Odoo and never signals the nginx/supervisor group.
- The master and every known child are stopped. Unexpected membership changes abort capture. A detached watchdog resumes those exact process identities after parent death or the configured pause deadline, then keeps resuming until the parent closes its pipe so a delayed stop cannot strand a worker. The normal `finally` path resumes them on success/failure too. PID reuse cannot target unrelated processes.
- PostgreSQL checks reject prepared transactions, active/open transactions, unknown session state and sessions belonging to other roles. Tables are read-locked during capture; dump uses custom format and includes accounting/audit tables. A server-side idle-transaction timeout bounds the backup connection's locks if its parent stalls after the watchdog resumes Odoo. Existing read-lock waits also have a short timeout.
- Database dump, matching complete filestore, Odoo runtime configuration and explicitly selected recovery environment values are captured into a private staging directory. Symbolic links/special filestore members are rejected. If capture overruns or writers resume early, it fails and nothing is delivered.
- After writers resume, `pg_restore --list` validates dump structure; a manifest records every file size/SHA-256 plus database, capture time, immutable image reference and source revision. The entire bundle is encrypted with the recovery public certificate. A private key is never supplied to the hosted tool. Temporary plaintext is removed on ordinary success/failure.
- Delivery must acknowledge the exact encrypted digest, destination and durable receipt. Only then is atomic `status.json` marked successful. A failed attempt preserves its preceding successful timestamp. The monitor reports missing, old, corrupt or failed recovery status through the approved alert adapter.

These checks are not proof that external writers do not exist. **Activation requires a verified, documented single-writer topology:** one supervised Odoo runtime owns all database and filestore writes; no second replica, SQL import, external integration writer or attachment job runs outside that process tree. The tool refuses any different configured topology. It cannot discover another container reliably. If that topology changes, disable this command until a provider-level coordinated snapshot or a complete writer coordination scheme is validated.

## Prerequisites and configuration

Run as the same `odoo` OS user as the hosted runtime. The generated Odoo configuration is private and owned by that user; invoking this tool as root intentionally does not bypass ownership checks. The current image supplies Python, psycopg2, PostgreSQL client tools, OpenSSL and the opt-in backup tools. Linux kernel/Python must support pidfds. Activation remains a separate verified release operation.

The policy and state directory must be owned by the invoking user and inaccessible to group/other users (0600 files, 0700 directories). Adapter programs must be absolute, executable regular files, never group/world-writable. Public certificate may be distributed to the host; keep its private key on the approved recovery system. Policy files, credentials, raw archives, financial material and private keys never belong in public Git.

The following schema is deliberately disabled and incomplete. Empty values are unresolved inputs, not defaults or approvals:

```json
{
  "enabled": false,
  "writer_topology": "single_supervised_odoo",
  "database": "",
  "data_dir": "/var/lib/odoo",
  "state_dir": "/var/lib/odoo/recovery-state",
  "public_certificate": "",
  "destination": "",
  "delivery_command": "",
  "alert_command": "",
  "operator": "",
  "deputy": "",
  "retention_policy": "",
  "schedule": "",
  "timezone": "",
  "rpo": "",
  "rto": "",
  "source_revision": "",
  "image_reference": "",
  "max_pause_seconds": 30,
  "adapter_timeout_seconds": 60,
  "maximum_success_age_seconds": 86400
}
```

Time values above illustrate field types only; choose them against measured capture duration, the approved maintenance window and RPO. `max_pause_seconds` is bounded to 5–300 seconds. Identify the complete deployed image with an immutable reference ending in `@sha256:<64 hex>`; a mutable tag or base-image digest alone is insufficient. The 40-character Git revision must match the runtime's `RAILWAY_GIT_COMMIT_SHA`, using the explicitly verified CLI operator attestation described above when provider metadata is absent.

Selected recovery environment variables are PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE, TCSI_ADMIN_LOGIN, TCSI_ADMIN_PASSWORD, TCSI_MASTER_PASSWORD, TCSI_WORKERS, PORT, TCSI_DB_MAXCONN and TCSI_LIMIT_TIME_REAL. The Odoo config itself preserves current database, addon and process settings. The immutable deployed image preserves the pinned Odoo/OCA/addon/runtime versions; ensure that image and its registry access remain available for the entire retention period. Portal/Supabase/platform secrets and other external services require their own protected recovery inventory; this command does not opportunistically collect them.

## Delivery and alert interfaces

Adapters are explicit executable paths, launched without a shell and with only a minimal PATH/LANG environment. Credentials must come from their own protected configuration. Each command runs in an owned process session; timeout or interruption terminates its process group. Adapters must remain synchronous, must not detach/daemonize, and must terminate their child processes when cancelled. The opt-in S3 adapter reads its generated private configuration; other destinations need an explicit adapter.

Delivery receives this JSON on stdin:

```json
{"artifact":"/private/staging/recovery.p7m","sha256":"<encrypted artifact hash>","destination":"<approved alias>","run_id":"<UUID>"}
```

The adapter must upload outside the live database/volume failure domain, enforce the approved encryption/access/retention policy, verify the remote object's digest, and return:

```json
{"durable":true,"sha256":"<same hash>","destination":"<same alias>","receipt_id":"<provider receipt>"}
```

An exit code alone is insufficient. The adapter owns provider-specific verification and safe idempotent retry using `run_id`. A timeout has an unknown remote outcome; inspect that run ID at the destination before retrying a side effect. A new capture uses a new run ID. The staging artifact is removed when its synchronous adapter finishes or fails; the adapter must not acknowledge queued/asynchronous upload. Application status preserves the digest, run ID, approved destination alias and opaque receipt ID. Receipt IDs permit only 1–256 alphanumeric or `_.:/-` characters, never signed URLs, query tokens or credentials. Keep complete provider verification evidence in protected operator logs indexed by those identifiers.

The alert adapter receives `{"event":"backup_attention","status":"failed or missed","run_id":"UUID or null","at":"UTC timestamp"}` on stdin and must return `{"accepted":true}` only after the agreed notification channel accepts it. It must deduplicate repeated monitor observations as appropriate. Recipient configuration remains outside application source. State-storage failure does not skip the alert attempt. Failure to alert remains a failing command; capture status also records `alert_failed` when its storage remains writable.

## Scheduling and missed-run checks

For installations using their own scheduler instead of the hosted daily process, after validation configure it to invoke:

```sh
python3 /approved/path/hosted_backup.py capture --config /private/path/recovery-policy.json
```

Configure an independent monitor job to invoke:

```sh
python3 /approved/path/hosted_backup.py monitor --config /private/path/recovery-policy.json
```

Concurrent captures are rejected by an exclusive lock. Schedule and timezone strings document the agreed external job; the script does not itself create jobs, interpret cron expressions, or claim those strings prove an active schedule. `maximum_success_age_seconds` is the monitor's actual freshness threshold. A capture's running state never resets the last-success age. Configure the external monitoring service to alert on nonzero exit/missed monitor invocation and complete engine/volume loss; an on-host monitor cannot report its own host's disappearance. Persist/export status to the separately monitored location as part of the approved operator integration.

SIGTERM follows cleanup; SIGKILL causes watchdog resume and leaves running state, which subsequently fails the freshness check. A killed parent may leave a private plaintext staging directory. Only the operator may remove that abandoned directory after confirming its capture process is gone; do not expose/reuse it as a verified backup. The script does not silently purge recovery material or implement unapproved retention deletion.

## Recovery rehearsal and verification

1. Retrieve an encrypted object and verify its SHA-256 against the trusted delivery record/status, not a checksum obtained from an untrusted copy of the same object. CMS encryption and internal hashes do not replace trusted transport/object integrity evidence.
2. On the separate recovery system, decrypt with its protected private key into a new 0700 directory. Keep all output, environment/configuration and recovered financial records private. Inspect archive members and extract only regular files into that directory; reject absolute/traversal/link members.
3. Run `python3 /approved/path/hosted_backup.py verify --directory /private/unpacked/bundle`. This rejects changed, missing, extra or linked files. The reported count proves bundle hashes, not ledger correctness or successful restore.
4. Provision a separate PostgreSQL database, least-privilege application role and separate filestore with correct Odoo ownership. Restore `database.dump` with `pg_restore`, put `filestore/` under the new database's filestore path, and recreate the exact immutable image. Adapt the protected runtime configuration to the isolated database/paths. Never start the recovery config unchanged against production.
5. Disable HTTP/customer access, cron, outgoing mail and external integrations in the copy before loading Odoo. Use existing accounting recovery comparisons in `scripts/alignment_snapshot.py` and the procedure in `HOSTED-OPERATIONS.md` to compare original IDs, names, balances, residuals, audit actors/times/old/new values and attachment bytes. Measure restore time and compare with approved RTO. Rehearse the candidate module upgrade there before release.
6. Record operator/deputy execution, receipts, comparison results, failure exercise and restore cadence. After customer writes resume, preserve those new transactions and prefer forward correction; never blindly replace live books with an older bundle.

Automated production restore is deliberately absent: restoring bytes cannot approve company scope, customer transaction preservation, integrations, acceptance or reopening access.

## Verification and remaining activation gates

`python3 scripts/test_hosted_backup.py` tests private policy validation, explicit prerequisites, manifest tampering/missing/extra files, filestore links/deadlines, certificate failure before pause, actual public-certificate encryption/decryption, durable delivery acknowledgment, redacted failures, missed/corrupt status and cleanup. Linux-only tests use disposable processes to prove normal failure, timeout and killed-parent resume. An opt-in `TCSI_RECOVERY_TEST_PG=disposable-only` fixture requires loopback PostgreSQL and creates/drops only its UUID-prefixed databases; it verifies real dump/restore, matching filestore/hashes and refusal of an open transaction. Set PGHOST=127.0.0.1, PGPORT, PGUSER and PGPASSWORD in the disposable CI environment.

`python3 scripts/test_backup_automation.py` covers configuration boundaries, daily schedule/retry behavior, remote byte verification, failed delivery, freshness, durable attention acceptance and scoped retention. `python3 scripts/test_hosted_runtime.py` covers optional backup process failure without accounting shutdown. Offline tests do not prove provider notification delivery.

Remaining activation evidence per installation: configured destination/policy/recipients, immutable deployed-image retention, actual scheduler and monitor, remote receipts, representative native restore, contact handover and real failure drill. Same-provider monitoring and single-owner operation remain explicit limits unless independently addressed. None is represented by invented approvals, placeholders or unit-test success.
