# Verified implementation lessons

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
