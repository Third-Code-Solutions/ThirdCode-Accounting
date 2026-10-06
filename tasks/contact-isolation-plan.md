# Company contact isolation

Objective: enforce company contact isolation in native ORM rules, preserving accounting, authorized multi-company and platform access; review shared records without deletion or guessed ownership; deploy and verify live.

Acceptance: two-company positive/negative read/search/name_search/API tests; no demo/user identity bypass; controlled shared grants; no tenant self-grant; accounting regressions green; reviewed upgrade and production verification.

Baseline (2026-10-06): upstream global partner rule shares all company-less contacts and internal-user identities. Tenant companies 4/5 see 70/69 contacts. Metadata audit identified shared identity records plus business contacts 89/90 with company 1 accounting links. No ownership changes made.

Plan:
- [x] Inspect native rules, production metadata and existing changes.
- [x] Implement global contact/bank restrictions, explicit shared access and identity scope.
- [x] Test two-company isolation, authorized sharing/multi-company/owner and accounting workflows.
- [x] Independent security/code review; resolve findings.
- [x] Capture recovery evidence, rehearse upgrade, deploy and verify live.

Checkpoint: implementation beginning; source base 2ffc58f, clean dedicated branch codex/company-contact-isolation. Existing user documentation untouched. Shared historical accounting links can preserve read access; no inferred company ownership. Unassigned records without evidence require owner review.


Checkpoint (candidate a08f443): global partner/bank and delegated user rules implemented; protected explicit grants, stored identity membership, default normalization, target-company accounting checks, post-compute reference checks and owner-cache invalidation covered. Production metadata: 87 contacts; 69 unassigned = 67 identities + two business contacts linked to company 1. No contact ownership/deletion changes made. Fresh encrypted paired capture succeeded (77,404,734 bytes, 1,320 manifest files; baseline preserved). Isolated upgrade helper prepared, not executed. Hosted API and recovery tests passed on 1f54aea; full native setup revealed inherited partner access checks during user group writes, addressed by active-company Settings-admin identity writes in a08f443. Latest CI 37390429469 pending. Production still 18.0.2.14.0. PR18 remains draft. Next: final native failures if any, complete review, isolated upgrade, merge/deploy and live two-company verification.

Checkpoint: 7d0fc53 passed isolated upgrade with 87 contacts and unchanged selected accounting/contact/company projections; grants only 89/90 to company1. Independent review found no remaining code blockers. CI37392179294: hosted/web/recovery green; native161 tests, zero assertion failures, one foreign-user fixture setup error corrected. Runtime unchanged after rehearsal. Next: final CI, merge PR18, deploy and run private live verifier plus native Directory/dropdown checks.

Checkpoint (final candidate da20551): runtime db34ee7 reviewed with no remaining blockers and re-upgraded successfully in neutralized copy; record projections and grants unchanged. CI37392855551 passed 161 native + 59 integration tests and hosted/web gates. Added raw mail metadata hardening subsequently; CI37393193643 found only an incorrect web_read expectation: native nested foreign contact expansion correctly raises AccessError. Test now requires that denial; no runtime change. Final CI37393835955 running. PR18 still draft, production14.0 unchanged. Tenant01 browser session prepared on Directory; private verifier ready. Next: green final CI, mark PR ready/merge exact head, observe Railway deployment14.1, private two-company API verification and native UI checks. No additional scope or features needed.


Completion (2026-10-06): final candidate 7f9829c passed CI37394563884 (161 native tests, 59 overlapping integration checks; zero failures/errors; hosted HTTP/recovery/web gates green). Independent source reviews cleared. PR18 merged as 772208c; Railway deployment3e081eb8 active with18.0.2.14.1. Live read-only two-company API checks passed: contacts70 to9 and69 to7; five own reads succeed, eleven foreign reads denied, zero foreign dropdown matches. Owner sees87 active/archived contacts;71 baseline active records retain company/parent links; historical grants89/90 restricted tocompany1. Native Directory, invoice customer and bill vendor selectors confirmed isolation and own customer availability. No production accounting record saved or posted. Detailed evidence and limits: docs/contact-isolation-evidence/README.md. No remaining implementation blocker.
