# Verified implementation lessons

## Editable amounts hidden by currency overlays — 5 October 2026

- Trigger: bank reconciliation and other monetary inputs appeared empty and unresponsive, although the live input was enabled, focused and held `0.00`.
- Cause: native Odoo renders a positioned `.o_input` currency/ghost span above the editable input. Shared light and dark input backgrounds made that span opaque.
- Remedy: make only `.o_field_monetary span.o_input.position-absolute` background and border transparent, with enough specificity to beat the later dark rules. Preserve its geometry and native pointer-event behavior.
- Prevention: `scripts/fixtures/form-inputs.html` loads captured native CSS; verify prefix/suffix/no-symbol fields across forms, tables and dialogs in both themes. Keep native invisible currency spacers in fixtures.
- Evidence: original production CSS failed transparency checks; candidate passed 55 checks at each of 1440/390px in light/dark (220 checks). Package validation and 25 branding/token tests passed. Live release verification is tracked separately.

## Native OCA report overrides — 5 October 2026

- Trigger: a transient report accepted an export after its company left the active scope; only the first trial-balance amount link received the new source domain.
- Cause: methods added to a sibling mixin did not override the native export base in Odoo's model MRO. An inherited view XPath modifies its first match, not every matching node.
- Remedy: override `account_financial_report_abstract_wizard` for HTML/PDF/XLSX exports; bind all 19 native trial-balance source spans explicitly against the pinned OCA template.
- Prevention: retain the active-company export regression and render actual QWeb HTML, then compare every displayed amount with the ledger lines selected by its emitted domain. Do not validate only source XML or one link.
- Scope/evidence: `tests/test_trial_balance_sources.py`; native CI runs 37245100651 and 37245853452. OCA template revision remains pinned in `docker/odoo/Dockerfile`.

## Draft-only roles and native reconciliation — 5 October 2026

- Trigger: the expanded business-role matrix let an encoder reconcile already-posted invoices and credits despite a posting guard.
- Cause: native settlement is a distinct operation and uses elevated access internally; denying `_post` does not deny reconciliation.
- Remedy: check the acting encoder role at the public settlement actions and partial/full reconciliation create/unlink boundaries, including sudo paths. Preserve native accountant/administrator operations.
- Prevention: retain positive accountant reconciliation/removal and negative encoder direct-ORM/elevated-path tests in `tests/test_role_matrix.py`.
- Scope/evidence: `models/reconciliation.py`; failure in CI37245263143, native regression passed in CI37245853452.

## Independent recovery watchdogs and subprocess deadlines — 5 October 2026

- Trigger: independent review found a deadline resume could finish before a stalled capture parent sent its last `SIGSTOP`; a timed-out adapter wrapper could leave its upload child alive.
- Cause: a one-shot watchdog does not cover a late stop, and timing out a direct subprocess does not terminate its descendants.
- Remedy: keep resuming the original pidfd-bound workers after deadline until the parent's pipe closes; run each adapter in an owned process group and terminate that group on interruption/timeout. Failure alerts must also run when writing local status fails.
- Prevention: retain late-stop, parent-death, descendant-timeout and status-storage-failure regressions in `scripts/test_hosted_backup.py`. Local POSIX timeout and storage-failure tests passed; Linux pidfd tests require CI and must not be described as passed on macOS.
- Scope: single-supervisor hosted recovery tooling. This does not establish actual off-host delivery, a nightly schedule or client recovery acceptance.


## Recovery provider clocks and Object Lock wire precision — 5 October 2026

- Trigger: principal review found a recently uploaded old snapshot could pass freshness, while valid S3 Object Lock replies could fail first delivery.
- Cause: upload time is not capture time; botocore serializes retention dates to whole seconds even when a mocked response preserves microseconds.
- Remedy: pass the manifest capture timestamp through delivery/receipts and use it for freshness; round requested lock deadlines upward to whole seconds before PUT and compare the exact returned version's lock. Keep lock duration anchored to provider creation time on retries.
- Prevention: retain recent-upload/stale-capture, retry timestamp conflict, shortened-lock and actual SDK serializer roundtrip tests in `scripts/test_hosted_recovery_provider.py`. Compare the decrypted manifest's timestamp with its receipt during drill preparation.
- Scope/evidence: pinned SDK provider suite 21/21 passed locally; these tests do not establish real destination access, active schedules, full database restore or client acceptance.

## Recovery connection identity across local container ports — 5 October 2026

- Trigger: native CI `37296882814` rejected the full restore at `create_database` with `postgres_endpoint_mismatch`; no target database was created.
- Cause: the guard compared `inet_server_addr()`/`inet_server_port()` with the explicitly selected client loopback endpoint. Those SQL functions describe the server's interface, which can differ behind container port mapping.
- Remedy: retain exact PostgreSQL option allowlisting, numeric loopback `host` and `hostaddr`, and ambient routing-override rejection; verify libpq's effective client host/hostaddr/port/database/user plus SQL `current_database()`/`current_user()` instead. Close rejected connections before any write.
- Prevention: `test_connected_client_endpoint_and_database_identity_are_verified` covers accepted loopback routing, endpoint/user/database mismatch, missing/redirected hostaddr and close-on-rejection. Native CI logs the synthetic client/server endpoints for diagnosis without credentials.
- Scope/evidence: all 12 restore tests passed in native CI `37297823382`; its diagnostic confirmed client `127.0.0.1:5432` and server `172.18.0.2/32:5432`. API contract: [Psycopg ConnectionInfo](https://www.psycopg.org/docs/extensions.html#psycopg2.extensions.ConnectionInfo). This correction does not establish completed recovery or production readiness.

## Comparable cache baselines for audit-history replay — 5 October 2026

- Trigger: diagnostic CI `37300335141` retained two native failures. The first native replay used warm fixture cache (six audit groups/29 details), while savepoint rollback left later replays cold (seven groups/30 details).
- Cause: comparing different starting cache states confused a replay-fixture difference with candidate audit-history behavior. Header relation batching also showed no query reduction (25 native/25 candidate).
- Remedy: establish the same cache baseline inside every replay; test cold and explicitly warmed native/candidate paths separately. Remove the ineffective header override and retain the scoped invoice-line relation batching (25 native/22 candidate queries).
- Prevention: `test_write_and_post_emit_identical_full_audit_history` compares four replays per cache mode and retains complete field/value, actor, company and control assertions. No broad ORM cache or prefetch override is introduced.
- Scope/evidence: source `096a980` passed all three jobs in CI `37301445442`, including 139 native tests with zero failures/errors. All eight controlled replays produced identical seven-group/30-detail histories. This proves the tested native equality/query boundary, not hosted latency or overall readiness.
