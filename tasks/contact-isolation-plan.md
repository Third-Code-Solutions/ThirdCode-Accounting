# Company contact isolation

Objective: enforce company contact isolation in native ORM rules, preserving accounting, authorized multi-company and platform access; review shared records without deletion or guessed ownership; deploy and verify live.

Acceptance: two-company positive/negative read/search/name_search/API tests; no demo/user identity bypass; controlled shared grants; no tenant self-grant; accounting regressions green; reviewed upgrade and production verification.

Baseline (2026-10-06): upstream global partner rule shares all company-less contacts and internal-user identities. Tenant companies 4/5 see 70/69 contacts. Metadata audit identified shared identity records plus business contacts 89/90 with company 1 accounting links. No ownership changes made.

Plan:
- [x] Inspect native rules, production metadata and existing changes.
- [x] Implement global contact/bank restrictions, explicit shared access and identity scope.
- [ ] Test two-company isolation, authorized sharing/multi-company/owner and accounting workflows.
- [ ] Independent security/code review; resolve findings.
- [ ] Capture recovery evidence, rehearse upgrade, deploy and verify live.

Checkpoint: implementation beginning; source base 2ffc58f, clean dedicated branch codex/company-contact-isolation. Existing user documentation untouched. Shared historical accounting links can preserve read access; no inferred company ownership. Unassigned records without evidence require owner review.


Checkpoint (candidate a08f443): global partner/bank and delegated user rules implemented; protected explicit grants, stored identity membership, default normalization, target-company accounting checks, post-compute reference checks and owner-cache invalidation covered. Production metadata: 87 contacts; 69 unassigned = 67 identities + two business contacts linked to company 1. No contact ownership/deletion changes made. Fresh encrypted paired capture succeeded (77,404,734 bytes, 1,320 manifest files; baseline preserved). Isolated upgrade helper prepared, not executed. Hosted API and recovery tests passed on 1f54aea; full native setup revealed inherited partner access checks during user group writes, addressed by active-company Settings-admin identity writes in a08f443. Latest CI 37390429469 pending. Production still 18.0.2.14.0. PR18 remains draft. Next: final native failures if any, complete review, isolated upgrade, merge/deploy and live two-company verification.
