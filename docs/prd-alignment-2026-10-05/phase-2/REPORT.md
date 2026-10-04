# Accounting completion candidate — 5 October 2026, Asia/Manila

Candidate module **18.0.2.13.0** is implemented and published on the release branch in [draft PR #7](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/pull/7). **It is not deployed to production and is not client acceptance.** The fresh Vercel deployment metadata still identifies production SHA `25b91a7b68fc65b0d36618018cc48b86ca2672f3`, deployment `dpl_8jQqpmq39da1sFAUZaxe9uwUnHPg`, READY. Railway engine version, actual installed configuration/company scope and hosted backups remain inaccessible here. [The deployment attempt](../DEPLOYMENT.md) records the available access and exact blocker. The original build prompt and historical audit files on `/Users/hoon` remain unavailable; this work uses the uploaded PRD and implementation brief plus the inspected repository.

The accepted architecture remains Vercel portal/proxy, Railway Odoo Community/PostgreSQL with persistent filestore and existing Supabase responsibilities. On-premise/LAN-only mismatch findings remain withdrawn. No production accounts, transactions, identifiers, palette or architecture were changed.

## Implemented behavior

- **Continuous numbering:** the product owner explicitly selected continuity across fiscal years for each company/journal. New postings, including credit notes and reversals, share that journal's counter and use `CODE/C/00000001` format; the counter starts above the highest retained native numeric counter. Original names are retained. Native transactional sequence locking handles failed transactions and concurrent retries. Official receipts retain their separate company no-gap counter. Direct numbering/reset/identity changes are denied. Legacy custom sequence regexes and preassigned draft numbers require review before prospective posting; historical names must never be cleared or rewritten.
- **Audit:** attachment content replacement/removal retains SHA-256 evidence, actor, time and company scope without storing file bytes or credentials in audit detail. Coverage now includes users/groups, companies, attachments, products, fiscal mappings, payment methods, sequence configuration, migration rows/history and cash allocations. Required subscriptions cannot be disabled, excluded, renamed, deleted or unsubscribed through the application, including sudo. Database/platform operators remain an operational control boundary.
- **Bank matching:** posted statement amounts and accounts remain unchanged. A separately posted adjustment clears suspense against selected outstanding items, including partial allocations. Retry returns the same adjustment. Reversal reopens the source items and permits rematching; every original adjustment and native reversal remains traceable. Company currency only, with active-company, role, residual and period checks.
- **Cutover:** the explicit residual policy combines TB, open AR/AP and allocated/unallocated undeposited receipts in one atomic transaction. It rejects nonempty books and conflicting retention. Per-account reconciliation, fingerprinted retry, retained source/mapping files and non-posting queryable history are implemented. See [CUTOVER.md](CUTOVER.md).
- **Reports:** native configuration screens expose cash scope/classification, reviewed mixed-entry cash allocations and tax classification. Cash allocation totals must equal the entry's cash movement; unresolved/offsetting flows remain visible. VAT/withholding summaries use posted tax lines, preserve refund/deduction signs and disclose missing classifications. A standard bank-summary PDF includes evidence, line status, adjustments and a stale-ledger warning. The SOA prints a running balance including the opening balance, alongside OCA activity, ageing and closing balance. Client-specific formats remain provisional.

## Verified evidence

Runtime: Odoo Community `18.0-20260908`, PostgreSQL16, prepared `tcsi-cloud-dev` image `678275793ec0`, pinned repository OCA dependencies, bind-mounted candidate addon. Every accounting write used disposable `tcsi_alignment_*` databases and explicitly synthetic USD data. This does not establish equivalence to the uninspected Railway deployment.

| Check | Evidence and result |
|---|---|
| Native regression | `evidence/release-native.txt` **109 tests, zero failures/errors**, in one combined run. The later stronger 1–30-day SOA ageing assertion also passes in a targeted run. Covers earlier integrity/period/company controls plus numbering, attachment/credential audit, bank match/reversal/rematch, cutover/archive, mixed cash allocation, tax refunds, SOA, supplier settlement, petty cash/instruments and role boundaries. |
| Migration safety | Five legacy CSV policy tests pass; residual cutover, interruption/retry, later settlement/deposit and retention tests run natively. |
| Concurrent operations | Four committed journal postings receive unique consecutive numbers2–5; two new receipts receive OR5/OR6; concurrent recurring runs return one move. Concurrent close rejects a draft, and a posting retry observes a just-closed period. |
| Upgrade | `.12`→`.13` preserves 123 posted documents, 248 journal lines, all10 account balances, 1,536 audit rows/34,812 details, document metadata and441 existing filestore files. SHA comparisons in `upgrade-before.json` / `upgrade-after.json`. The later SOA/view refresh changes presentation only. |
| Restore | Native quiescent final ZIP is 7,792,111 bytes, SHA256 `1af799a93bda099a27847761d22e0ac41bdfc83d99eb71bbcd24dab881c060be`; restore 8.051 seconds. Target matches179 posted documents,363 lines,18 account balances,2,230 audit rows/50,129 details,5 document attachments,2 retained history rows,1 cutover result and447 existing filestore files. Original source bytes were retrieved and hashed after the first restore; final snapshot comparisons also preserve those exact file bytes and archive rows. See `release-recovery-before.json` and `release-recovery-after.json`. |
| Native UI | Chromium/Linux, actual Odoo assets. Light/dark tax and cash screens, bank grid, cutover and retained history inspected. Viewport/document width1280; bank first data cell x298..395.2 stays within its table. No palette changes. Windows Chrome/Edge remain untested. |
| Source/package | Addon Python/XML parsing,60 manifest resources and whitespace checks pass. Portal/contracts/worker code is unchanged; prior61-test result remains historical evidence, not a newly rerun suite. |

The backup is **local synthetic evidence**, not a hosted backup or an accepted RPO/RTO. It does not verify a remote destination, nightly schedule, retention, alert delivery, recovery credentials or production volume. The original ZIP remains outside Git at `/workspace/scratch/recovery-phase2-final/tcsi_alignment_phase2.zip`. Full local configuration remains outside evidence because it contains credentials; the pinned Docker/config templates describe the runtime. A complete hosted recovery bundle remains a release gate.

## Ledger/report results and performance

The original2025 fixture retains income1,200, customer AR1,050 and cash150. Comparative2024 is zero; balance-sheet and cash reconciliation differences are zero. Six new actual PDFs in `evidence/reports` render in2.17–3.51seconds. Synthetic VAT is12 and withholding−2 on base100; refund tests net these to zero. The bank statement50 matches a75 outstanding receipt, leaves25 residual, retains the original bank entry and reports a zero difference at closing book/statement balance200.

`evidence/standard-reports` adds actual OCA TB, GL, journal, ageing, unpaid and SOA output. The July–December2025 SOA opens at600, adds six100 invoices and subtracts payment150, closing at1,050. Its running balances and ageing are retained in JSON. Those older fixture invoices have due dates after the 2025 reporting date, so the retained PDF puts their residuals in Current; a separate explicit-due-date regression verifies the 1–30-day bucket. The tax-tag OCA VAT output still has no configured client tags; the separate positive ledger-tax PDFs establish calculation availability, not Philippine statutory acceptance. OCA journal rendering retains unused `t-eval` warnings; do not equate output generation with accountant format approval.

| Load,20 transactions | Save p95 | Post p95 | Interpretation |
|---|---:|---:|---|
| Two workers | 1,924.57ms | 317.01ms | Within proposed2-second p95 target on this small fixture; maximum save2,084.85ms. |
| Ten workers | 4,541.21ms | 2,509.01ms | Functional completion; misses that latency target. Production sizing/volume acceptance remains open. |

An initial benchmark selected the newly created empty migration company by name and stopped before transaction creation. The harness now uses an explicit/default-user company and refuses synthetic writes outside `tcsi_alignment_` databases. Both the failed setup log and measured results are retained. Initial SOA verification exposed that OCA's cumulative activity excludes the opening balance; the new printed running balance explicitly adds that opening, with a regression.

## AC-01 through AC-09 and release gates

| Criterion | Technical status | Remaining external acceptance |
|---|---|---|
| AC-01 SOA | Opening, period activity, running/closing balance, ageing and PDF verified on synthetic data. | Approved sample and real customer-ledger comparison. |
| AC-02 Financial statements | Balanced BS, P&L/comparatives and reconciled classified cash output; mixed-allocation test. | Client format, cash scope/classifications and representative TB comparison. |
| AC-03 Monthly reconciliation | Standard bank summary/matching verified. | RP-04 definition and approved custom sample; standard summary is not that deliverable. |
| AC-04 Official Receipt | Existing native receipt/invoice regression plus protected continuous numbering. | Tax/document/control/signatory values, stock and print acceptance. |
| AC-05 Opening migration | Synthetic line-by-line equality, residual receipts/open items, rollback/retry/archive verified. | Authorized MYOB extraction, mapping/retention/date/finance-owner approval and real comparison. |
| AC-06 Parallel run | No compressed substitute claimed. | One full real accounting month. |
| AC-07 Audit | Expanded actor/time/old-new and immutable evidence tests; retained through restore. | Client examination and hosted retention/recovery operations. |
| AC-08 Roles | Native role/company denial tests, including new APIs, pass. | Production membership review, complete deployed-role rehearsal and Windows browsers. |
| AC-09 Recovery | Richer synthetic database+filestore restored and compared. | Production-representative hosted copy, complete config/credential recovery and handover demonstration. |

Deployment is held by the user's explicit release gates: actual Railway version/configuration access, representative upgrade/recovery rehearsal, verified DB/filestore/config backup and a transaction-preserving recovery plan. Use [HOSTED-OPERATIONS.md](../HOSTED-OPERATIONS.md); never overwrite transactions accepted after release with an old snapshot. No push to main or deployment was performed.

The developer is the product owner. Future clients' finance/accounting owners remain unnamed. Each client must supply tax/registration/payment configuration, report samples/RP-04 definition, cash classifications, migration choices/source data, CAS documentation and EIS assessment, plus actual acceptance. Number continuity is now a resolved product decision, not an outstanding generic question. NF-03/NF-04 targets and production volumes still need agreement. There is no overall completion percentage or claim of production acceptance.
