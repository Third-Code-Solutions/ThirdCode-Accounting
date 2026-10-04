# Candidate revisions

The combined candidate through `8ff19d373f7c32893a90de73d0328b91104ad121` was pushed to `release/accounting-18.0.2.13.0` on 5 October 2026 (Asia/Manila) following the product owner's push/deploy instruction. [Draft PR #7](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/pull/7) targets `main`. Production has not been released; see [the deployment attempt](DEPLOYMENT.md).

| Revision | Change |
|---|---|
| `25b91a7b68fc65b0d36618018cc48b86ca2672f3` | Initial checkout and freshly observed Vercel production portal commit; addon source18.0.2.11.2. Installed Railway module unknown. |
| `e70d105` | Addon18.0.2.12.0: permanent posting/period/receipt/audit controls, native atomic import, comparative/cash reporting and corresponding native regressions. |
| `3fdf58e` | Migration CLI overlap/source-change validation and atomic-import integration; five policy unit tests. |
| `4ccd960` | Reproducible synthetic fixture, concurrent cursor probes, actual OCA report rendering and corrected closed-period workflow verification. |
| `8e27ba7` | Phase1 traceability, report evidence and hosted release gates. |
| `120d75d` | Candidate18.0.2.13.0 continuous journal numbering, protected audit subscriptions and attachment digests. |
| `b60e037` | Atomic residual cutover, retained original/mapping files, immutable queryable history and matching native tests. |
| `1788736` | Reversal-preserving statement matching, cash allocation/tax/bank/SOA output, native UI and workflow/role regressions. |
| `80a9684` | Reproducible cutover/report/concurrency/snapshot/restore scripts and isolated benchmark guard. |
| `8ff19d3` | Final phase 2 evidence, traceability, cutover policy and remaining hosted release gates. |

Final candidate application source is `1788736`; verification tooling is `80a9684`. These commits are a review sequence for one candidate and were tested together, not separately certified releases. Final native evidence is109 tests in one combined run plus the stronger SOA ageing assertion, as detailed in `phase-2/evidence/TEST-RESULTS.md`. Candidate runtime source was bind-mounted. The release branch is published; no production release identifier is claimed.
