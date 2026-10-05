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
