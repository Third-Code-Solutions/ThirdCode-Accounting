# Company contact isolation

Objective: enforce company contact isolation in native ORM rules, preserving accounting, authorized multi-company and platform access; review shared records without deletion or guessed ownership; deploy and verify live.

Acceptance: two-company positive/negative read/search/name_search/API tests; no demo/user identity bypass; controlled shared grants; no tenant self-grant; accounting regressions green; reviewed upgrade and production verification.

Baseline (2026-10-06): upstream global partner rule shares all company-less contacts and internal-user identities. Tenant companies 4/5 see 70/69 contacts. Metadata audit identified shared identity records plus business contacts 89/90 with company 1 accounting links. No ownership changes made.

Plan:
- [x] Inspect native rules, production metadata and existing changes.
- [ ] Implement global contact/bank restrictions, explicit shared access and identity scope.
- [ ] Test two-company isolation, authorized sharing/multi-company/owner and accounting workflows.
- [ ] Independent security/code review; resolve findings.
- [ ] Capture recovery evidence, rehearse upgrade, deploy and verify live.

Checkpoint: implementation beginning; source base 2ffc58f, clean dedicated branch codex/company-contact-isolation. Existing user documentation untouched. Shared historical accounting links can preserve read access; no inferred company ownership. Unassigned records without evidence require owner review.
