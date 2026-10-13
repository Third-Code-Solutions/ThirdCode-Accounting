# Verified implementation lessons

## Error branding must cover rendered and copied diagnostics — 6 October 2026

- Trigger: server errors still showed the upstream product name after dialog titles were branded.
- Cause: the native error template and both clipboard handlers read the original message and traceback; title-only patches missed those paths.
- Remedy: use branded presentation getters and clipboard formatting, retaining original payloads, exception identifiers and file paths. Apply native template inheritance to the title, message and diagnostic heading.
- Prevention: test display and clipboard together; only replace known branding phrases in raw diagnostics. Verify native rendering because class stubs and XML source checks cannot prove template compilation.
- Scope/evidence: `scripts/test-branding.mjs`, `scripts/test-branding.py`, and `docs/error-branding-2026-10-06/README.md`; synthetic native dialogs and copy behavior verified without accounting mutations.

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

## Railway console message size — 5 October 2026

- Trigger: a 36 KB reviewed helper bundle disconnected the browser terminal with `read limited at 32769 bytes`.
- Cause: one terminal input message exceeded the console transport limit; the shell never created the candidate input directory.
- Remedy: reconnect, inspect the intended destination for partial execution, then transfer separate commands below 32,768 bytes. Verify every decoded file against its independently reviewed SHA256 before execution.
- Prevention: check encoded command length before pasting; use smaller independent payloads with exclusive file creation. Never retry an oversized or possibly executed command unchanged.
- Scope/evidence: private 40e501c rehearsal helper and support bundle; both smaller transfers matched their hashes and the subsequent isolated upgrade, workload and cleanup completed. No browser permissions changed.

## Native JSON-RPC methods returning None — 5 October 2026

- Trigger: the private read-only production verifier marked session cleanup unconfirmed despite HTTP 200 from `/web/session/destroy`.
- Cause: native Odoo 18's `Session.destroy()` returns `None`; its JSON-RPC dispatcher can omit the `result` member. The generic decoder required that member.
- Remedy: accept absent/null result only for the exact empty-parameter destroy call, retaining HTTP 200, JSON-RPC 2.0, exact integer request-ID, no-error and applicable-cookie checks. Authentication and model reads still require their normal result.
- Prevention: test invalid envelopes, unexpected logout parameters, strict authentication/model decoding, valid session cleanup and the missing-cookie failure. HTTP 200 alone remains insufficient.
- Scope/evidence: independently reviewed private baseline verifier; fresh 12:19 UTC production read-only check and session cleanup passed. Original incomplete evidence remains retained.


## Public theme changes must cover destination pages — 6 October 2026

- Trigger: homepage passed light/dark checks, but its demo CTA opened a white form panel with pale text in dark mode; detail-page labels also failed contrast.
- Cause: public form surfaces and accent labels used fixed light/background or background-accent colors outside the shared theme tokens. Color transitions briefly interpolated text through low-contrast values during mode changes.
- Remedy: use surface/muted/accent-text tokens for form panels, fields, placeholders and public section labels; keep color changes immediate. Read active theme from the document when mounting a prefetched destination's toggle.
- Prevention: follow the primary CTA and check every public route in both themes, including typed input, keyboard toggles, reloads and prefetched navigation. Do not accept a homepage-only theme scan.
- Scope/evidence: Next.js public marketing; all 10 public route/theme combinations passed axe A/AA scans in `docs/landing-page-evidence/public-route-checks.json`; final width matrix in `responsive-checks.json`.

## ORM state and platform authorization — 6 October 2026

- Trigger: native tests found incident recurrence losing its state/count after direct SQL; a publication revision check read stale database state. Generic RPC also accepted a forged setup-context marker before the owner check was added.
- Cause: pending ORM values were not flushed before SQL, and a caller-controlled context marker had been treated as authorization.
- Remedy: flush incident rows before upsert and invalidate without another flush; flush publication revision before row locking. Require the full owner predicate before setup dispatch and keep internal user provisioning private to RPC.
- Prevention: retain recurrence/revision regressions, tenant/group-only/public denial tests, and forged-context tests. The controller's trusted identity and token check remain separate boundaries.
- Evidence: native CI 37381190163 passed 138 tests and 59 integration checks; hosted HTTP CI exercised owner/tenant denial, actual organization provisioning, snapshot publication isolation and capture after rollback.

## Tenant contacts and native elevated serializers — 6 October 2026

- Trigger: native partner rules exposed company-less contacts and internal-user identities; strict rules then uncovered automatic chat subscription assumptions.
- Cause: native shared-contact exceptions apply to ORM searches, while mail persona serializers deliberately use elevated access. Shared-channel broadcasts are constructed once under the sender, so sender-only filtering cannot protect receivers.
- Remedy: global contact/user/bank scope plus explicit shared grants; narrowly elevated automatic-membership lookup intersected with actor-visible contacts; actor-scoped Store serialization and recipient-scoped bus metadata filtering. Preserve message rows/IDs and prune dependent hidden call references.
- Prevention: two-company direct-read/search/export/dropdown, archived-identity, shared-accounting, native Store and receiver-bus regressions. Foreign-company test fixtures provision as installer; business assertions retain tenant users.
- Evidence: CI37392179294 contact/mail/shared-accounting cases passed; isolated 14.0-to-14.1 upgrade preserved selected business projections. Final full-suite/deployment status is tracked in `docs/contact-isolation-evidence/README.md`.


## Settings initialization through the hosted proxy — 7 October 2026

- Trigger: owner Settings click stayed on the console; browser reported `ConnectionLostError` for `/base_setup/data`.
- Cause: the native Settings initialization RPC prefix was absent from the portal rewrite and middleware bypass; its POST received portal HTML.
- Remedy: register `base_setup` with accounting routes and exclude it from portal middleware. Preserve private/no-store response headers.
- Prevention: explicit `/base_setup/data` rewrite, POST passthrough and no-cache regressions in `apps/web/proxy.test.ts`; verify Settings by clicking from the live console.
- Evidence: pre-fix browser error plus HTTP HTML response; 49 proxy tests pass locally. Live release verification recorded in `docs/console-navigation-fix-2026-10-07.md`.
