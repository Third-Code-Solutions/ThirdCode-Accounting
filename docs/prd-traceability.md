# PRD traceability — full local implementation

Source: [Accounting System PRD v0.1](../../Accounting_System_PRD_v0.1.pdf), dated
19 September 2026, eight pages. The PRD is explicitly a review draft and says
it is not a build specification until the open questions are closed and v1.0 is
issued. This record preserves that boundary while mapping every defined
functional, report, migration, non-functional, regulatory, and acceptance item
to the local implementation.

Status vocabulary:

- **VERIFIED LOCALLY** — exercised against the local Odoo database with
  synthetic data and recorded by a named verifier.
- **PARTIAL** — a related technical surface works, but the complete PRD outcome
  or client-owned artifact is not proven.
- **IN PROGRESS** — implementation work is still active.
- **NOT TESTED** — the check needs data, hardware, or a workflow not run here.
- **BLOCKED — CLIENT DECISION** — implementation can be configured, but the
  required business, regulatory, sample, or ownership decision is absent.
- **ACCEPTED BY CLIENT** — not used in this repository; no client sign-off was
  performed.

## Baseline and evidence

- Odoo Community 18.0 and PostgreSQL 16 are pinned by image digest.
- OCA commits are pinned in `docker/odoo/Dockerfile`; installed modules are
  `auditlog`, `date_range`, `report_xlsx`, `report_xlsx_helper`,
  `account_financial_report`, `partner_statement`, `account_statement_base`,
  `account_reconcile_model_oca`, `account_reconcile_oca`, and
  `account_statement_reconcile_status`.
- Third Code behavior is isolated in `addons/thirdcode_accounting`.
- Verification uses Odoo ORM/XML-RPC and native posting/payment/reversal/
  reconciliation operations. It does not write accounting tables directly.
- Primary evidence is [`scripts/verify_full_scope.py`](../scripts/verify_full_scope.py),
  the Milestone 1 regression, migration scripts, backup scripts, and the actual
  results in [`docs/verification.md`](verification.md).
- Odoo Community accounting security is based on the upstream
  [account security source](https://raw.githubusercontent.com/odoo/odoo/18.0/addons/account/security/account_security.xml).
  The selected OCA surfaces are documented by the upstream
  [account-financial-reporting manifest](https://raw.githubusercontent.com/OCA/account-financial-reporting/18.0/account_financial_report/__manifest__.py),
  [partner-statement manifest](https://raw.githubusercontent.com/OCA/account-financial-reporting/18.0/partner_statement/__manifest__.py),
  [auditlog manifest](https://raw.githubusercontent.com/OCA/server-tools/18.0/auditlog/__manifest__.py),
  and pinned reconciliation manifests.

## Scope, objectives, users, and roles

| Source | Draft status | Proposed implementation / dependency | Acceptance and evidence | Status |
| --- | --- | --- | --- | --- |
| p1: one company/site, no branches/consolidation/foreign currency/integrations | Assumption | Odoo single-company local configuration; no external connector | Confirm company, currency, volume, modules, and integrations | **BLOCKED — CLIENT DECISION** |
| p1: five named users, two concurrent, on-premise | Assumption | Odoo users/groups; Docker proof environment | Test named users on client hardware/network | **PARTIAL** |
| p1: replace MYOB / faster / reproduce reports / preserve history / accountability / BIR registration | Objectives | Native ledger, OCA reports, controls, migration/backup tooling | AC-01–AC-09 and client discovery evidence | **PARTIAL** |
| p2: Administrator | Working assumption | `group_thirdcode_administrator`, native account manager, no server superuser; post/reverse/close/reopen | Test all allowed/forbidden actions and approve SoD | **VERIFIED LOCALLY / BLOCKED — CLIENT DECISION** |
| p2: Accountant | Working assumption | `group_thirdcode_accountant`, native accounting/report/reconcile rights | Post/reconcile/reports; cannot reopen or permissions; configuration validation is server-guarded | **VERIFIED LOCALLY / BLOCKED — CLIENT DECISION** |
| p2: Encoder | Working assumption | `group_thirdcode_encoder` plus server-side `action_post` and transient report-wizard guards | Draft create works; posting and accounting-report wizard creation are blocked | **VERIFIED LOCALLY / BLOCKED — CLIENT DECISION** |
| p2: Read-only | Working assumption | Native read-only plus custom ACLs | Create/write/unlink/post probes blocked | **VERIFIED LOCALLY / BLOCKED — CLIENT DECISION** |
| p2: approval beyond posting | Unresolved; assumed none | Optional payment-batch threshold approval is configurable | Confirm actions requiring approval trail | **PARTIAL / BLOCKED — CLIENT DECISION** |

## General ledger

| ID / page | Requirement status | Proposed implementation and dependencies | Acceptance test / local evidence | Status |
| --- | --- | --- | --- | --- |
| GL-01 p2 | Launch | Native chart of accounts plus migration validator/loader; real MYOB mapping required | Load real chart and reconcile to source | **PARTIAL** — synthetic migration applied; real source absent |
| GL-02 p2 | Launch | Native manual journal entries, narration, attachments | Create/edit draft, attach source, post, audit | **PARTIAL** — native surface installed; attachment-specific acceptance not separately run |
| GL-03 p2 | Launch | `thirdcode.recurring.journal`, balanced lines, scheduler, unique source/date key | Run due entry twice; one posted move | **VERIFIED LOCALLY** |
| GL-04 p2 | Launch | Native invoices, bills, payments, receipts and batch posting | Posted moves balance and source documents produce ledger entries | **VERIFIED LOCALLY** |
| GL-05 p2 | Launch | `thirdcode.accounting.period`, actual `action_post` restriction, accountant/admin close, admin reopen | Post in closed period is rejected; reopen only Administrator | **VERIFIED LOCALLY** — closed posting blocked, Read-only reopen blocked, Administrator reopened and reclosed |
| GL-06 p2 | Launch | Native/OCA trial balance, general ledger, drilldown/source documents | Render GL/TB PDF and inspect balanced totals | **VERIFIED LOCALLY** |
| GL-07 p2 | Launch | `thirdcode.year.end.close` creates native income/expense to retained earnings entry | Close year and reverse through native reversal | **VERIFIED LOCALLY** |
| GL-08 p2 | Launch | Posted move write/unlink guards; native reversal and credit/debit notes | Attempt edit/delete; preserve source and post reversal | **VERIFIED LOCALLY** |

## Accounts receivable

| ID / page | Requirement status | Proposed implementation and dependencies | Acceptance test / local evidence | Status |
| --- | --- | --- | --- | --- |
| AR-01 p3 | Launch | Native `res.partner` with terms, VAT/TIN, contact fields | Create customer and verify statement identity | **VERIFIED LOCALLY** for synthetic path |
| AR-02 p3 | Launch | Native customer invoice plus guarded Third Code invoice QWeb report | Post/render against signed client sample | **PARTIAL** — server report exists; sample/layout acceptance pending |
| AR-03 p3 | Launch | Native payment register/reconciliation and partial allocation | Pay less than invoice; residual equals control account | **VERIFIED LOCALLY** |
| AR-04 p3 | Launch | Native advance payment via payment batch; receipt metadata | Post unallocated customer advance and reconcile later | **VERIFIED LOCALLY** for advance posting |
| AR-05 p3 | Launch | Native payment plus no-gap local OR sequence, amount words, VAT/TIN/signatory fields, BIR guard | Print on approved stock with control number | **PARTIAL / BLOCKED — CLIENT DECISION** |
| AR-06 p3 | Assumed | `thirdcode.recurring.invoice` customer mode and daily idempotent scheduler | Generate repeat invoice; confirm launch decision | **VERIFIED LOCALLY / BLOCKED — CLIENT DECISION** |
| AR-07 p3 | Launch | Native `out_refund` credit note and native refund/reversal paths | Post credit note and verify classification/source preservation | **VERIFIED LOCALLY** |
| AR-08 p3 | Launch | Native/OCA aged partner balance, unpaid listings, partner statement | Render ageing/unpaid and reconcile to ledger | **PARTIAL** — report surface installed; full client sample/dunning policy pending |

## Accounts payable

| ID / page | Requirement status | Proposed implementation and dependencies | Acceptance test / local evidence | Status |
| --- | --- | --- | --- | --- |
| AP-01 p3 | Launch | Native supplier partner, terms, VAT/TIN/contact | Create supplier and verify payable identity | **VERIFIED LOCALLY** for synthetic path |
| AP-02 p3 | Launch | Native supplier bill with attachment support | Post bill and verify source attachment | **PARTIAL** — bill path verified; attachment-specific acceptance not separately run |
| AP-03 p3 | Launch | Native `hr_expense` employee-expense surface; payment batch/petty-cash journals | Create expense and post/reimburse through approved flow | **PARTIAL** — draft expense surface verified; full reimbursement policy pending |
| AP-04 p3 | Launch | `thirdcode.payment.batch`, native payment register, instrument fields | Submit/post multiple lines and verify one native payment per line | **VERIFIED LOCALLY** |
| AP-05 p3 | Launch | Native/OCA aged payable and unpaid listings | Render supplier ageing and reconcile to ledger | **PARTIAL** — surface installed; client report sample pending |
| AP-06 p3 | Launch | Native `in_refund` debit note/supplier credit | Post debit note and verify classification | **VERIFIED LOCALLY** |
| AP-07 p3 | Optional | Company threshold fields and Administrator-only payment-batch approval | Exceed threshold, block posting, approve, post | **VERIFIED LOCALLY / BLOCKED — CLIENT DECISION** |

## Cash and bank

| ID / page | Requirement status | Proposed implementation and dependencies | Acceptance test / local evidence | Status |
| --- | --- | --- | --- | --- |
| CB-01 p3 | Launch | Native bank/cash journals and default accounts; petty cash uses cash journal/expense | Configure every client account and reconcile balances | **PARTIAL** — synthetic bank/cash path verified; number of accounts open |
| CB-02 p3 | Launch | Native payments plus cash/cheque/transfer instrument/reference fields | Post each instrument type and audit reference | **VERIFIED LOCALLY** for batch/payment surfaces |
| CB-03 p3 | Launch | Manual reconciliation record with paper/PDF evidence, balances, difference, sign-off | Attach statement, compute ledger, zero-difference reconcile | **VERIFIED LOCALLY** synthetically; definition/owner pending |
| CB-04 p3 | Launch | Stored statement-line status from native reconciliation state | Show reconciled/unreconciled per line | **VERIFIED LOCALLY** |
| p3 Q19/Q20 | Unresolved | Multiple accounts and delivery/source format require client discovery | Configure all bank/cash accounts and statement inputs | **BLOCKED — CLIENT DECISION** |

## Reports

| ID / page | Requirement status | Proposed implementation and dependencies | Acceptance test / local evidence | Status |
| --- | --- | --- | --- | --- |
| RP-01 p4 | Custom; client sample required | OCA partner statement plus guarded custom configuration fields | Opening, invoices, payments, running balance, ageing, closing balance; signed sample | **PARTIAL** — local statement surface rendered |
| RP-02 p4 | Custom; client sample required | OCA GL/TB plus Third Code provisional balance-sheet, profit-and-loss, and cash-movement PDFs derived from native move lines; client layout fields | Balance sheet balances, P&L ties to TB, comparatives, signed sample | **PARTIAL** — generic statements rendered locally; the synthetic balance-sheet check is `0.00` and P&L net result is derived from native lines, while signed layout/comparatives remain pending |
| RP-03 p4 | Custom; BIR-dependent | Guarded OR report with serial, control, payer/TIN, amount figures/words, VAT, signature | Render on approved stock with accountant-owned value | **PARTIAL / BLOCKED — CLIENT DECISION** |
| RP-04 p4 | Undefined; provisional sum | Manual reconciliation evidence model; no invented report layout | Define format/source/owner/cadence, then implement signed sample | **PARTIAL / BLOCKED — CLIENT DECISION** |
| p4 standard reports | Defined standard | OCA/native GL, journal listing, TB, Third Code provisional balance sheet/P&L/cash movement, ageing, VAT/withholding, bank surfaces | Render and reconcile each required output | **PARTIAL** — OCA report set and generic financial statements rendered locally; client-format reconciliation and statutory sample acceptance remain pending |

## Data migration

| ID / page | Requirement status | Proposed implementation and dependencies | Acceptance test / local evidence | Status |
| --- | --- | --- | --- | --- |
| DM-01 p4 | Launch | CSV accounts/partners/taxes validator and native ORM loader with persisted source identifiers on imported masters | Validate/load real MYOB masters and reconcile counts | **PARTIAL** — synthetic fixture applied/idempotent; real source absent |
| DM-02 p4 | Launch | Open items including customer/supplier moves and undeposited receipt input | Source-level open-item reconciliation without double counting | **PARTIAL** — tooling exists; real extract/open-item mapping pending |
| DM-03 p4 | Launch | Balanced opening-TB CSV to configured opening journal | Reconcile every account at cutover and obtain owner sign-off | **PARTIAL** — synthetic opening rows applied; owner/source absent |
| DM-04 p4 | Launch | Persisted source identifiers and transaction-history load with explicit journals | Load approved retention window and verify no duplicates | **PARTIAL** — synthetic history only; live/archive decision pending |
| DM-05 p4 | Launch | Migration batch rows, counts, source/file hashes, match state | Line-by-line source/target reconciliation | **VERIFIED LOCALLY** for synthetic fixture; real evidence pending |
| DM-06 p4/p5 | Launch | Parallel-run checklist/runbook only until client data exists | One full real accounting month agrees in both systems | **NOT TESTED** |
| DM-07 p4/p5 | Launch | Backup/archive tooling and documented archive policy fields | Preserve original MYOB read-only file and query/archive access | **BLOCKED — CLIENT DECISION** |

## Non-functional requirements

| ID / page | Requirement status | Proposed implementation / evidence | Status |
| --- | --- | --- | --- |
| NF-01 p5 | Launch | Docker/on-prem-compatible Odoo/PostgreSQL compose baseline | **PARTIAL** — local Docker only; client host pending |
| NF-02 p5 | Launch | Four synthetic role users plus local administrator; Odoo supports named users | **PARTIAL** — client five-user/concurrency test pending |
| NF-03 p5 | Proposed target | `scripts/benchmark.py`, two workers, native save/post | **VERIFIED LOCALLY** for synthetic run; client hardware/data not tested |
| NF-04 p5 | Proposed target | Native/OCA report surfaces plus provisional financial-statement PDFs; full-year synthetic render benchmark | **VERIFIED LOCALLY** for synthetic 2026 data; client volume not tested |
| NF-05 p5 | Launch | OCA auditlog plus immutable custom override; native chatter/tracking | **PARTIAL** — local audit rows/immutability verified; every approval/edit path not fully sampled |
| NF-06 p5 | Launch | `auditlog.log` write/unlink blocked for application users | **VERIFIED LOCALLY** |
| NF-07 p5 | Launch | Odoo sequences, no-gap OR sequence, journal numbering validation | **PARTIAL** — observed synthetic gaps absent; failure/concurrency/period policy pending |
| NF-08 p5 | Launch | `scripts/backup.ps1`, explicit output root, hash manifest | **PARTIAL** — local backup verified; nightly second device pending |
| NF-09 p5 | Launch | `scripts/restore.ps1` and verification to disposable DB/filestore | **VERIFIED LOCALLY** synthetically; handover test pending |
| NF-10 p5 | Launch | Retention field, archive/CAS pack, backup includes audit data | **BLOCKED — CLIENT DECISION** on statutory policy/owner |
| NF-11 p5 | Launch | Local compose binding/URL; no external exposure configured | **PARTIAL** — production network/TLS pending |
| NF-12 p5 | Launch | Odoo web UI is browser-based | **NOT TESTED** visually; browser automation kernel blocked |

## Philippine regulatory requirements

| ID / page | PRD requirement | Proposed implementation / dependency | Status |
| --- | --- | --- | --- |
| RG-01 p6 | BIR books in acceptable format | Native/OCA journal, ledger, sales/purchase/cash report surfaces; CAS pack | **PARTIAL / BLOCKED — ACCOUNTANT/LEGAL** |
| RG-02 p6 | Sequential, unbroken, non-resettable numbering | Native sequences, OR no-gap sequence, observed numbering control | **PARTIAL / BLOCKED — ACCOUNTANT/LEGAL** |
| RG-03 p6 | No deletion; reversal correction | Server-side posted immutability and native reversal/notes | **VERIFIED LOCALLY** technically; statutory acceptance pending |
| RG-04 p6 | Control number on invoices/receipts | Company-owned control field and print guards require both a value and explicit approval; no value fabricated | **PARTIAL / BLOCKED — CLIENT DECISION** |
| RG-05 p6 | Audit retained/available | OCA auditlog, immutable override, backup/restore inclusion | **PARTIAL** — local control verified; legal retention pending |
| RG-06 p6 | VAT/withholding per Philippine rules | Explicit tax-profile mappings and owner/basis note; no rates invented | **BLOCKED — ACCOUNTANT/LEGAL** |
| RG-07 p6 | CAS documentation pack | [`docs/cas-control-pack.md`](cas-control-pack.md) template | **PARTIAL / BLOCKED — CLIENT DECISION** |
| p6 EIS question | Coverage unresolved | EIS status field; no transmission/integration implemented | **BLOCKED — CLIENT DECISION** |

## Acceptance criteria

| ID / page | Pass condition from PRD | Local evidence | Status |
| --- | --- | --- | --- |
| AC-01 p7 | SOA matches approved format and customer ledger | OCA partner statement/local ledger render; sample absent | **PARTIAL / BLOCKED — CLIENT DECISION** |
| AC-02 p7 | Balance sheet balances, P&L ties to TB, sample matches | Native/OCA GL/TB render; full signed sample absent | **PARTIAL / BLOCKED — CLIENT DECISION** |
| AC-03 p7 | Monthly reconciliation in agreed format agrees with bank statement | Zero-difference evidence model verified; format/owner absent | **PARTIAL / BLOCKED — CLIENT DECISION** |
| AC-04 p7 | OR prints correctly on client stock with required fields | Guarded report, sequence, amount words/TIN/VAT/signature fields; BIR/sample absent | **PARTIAL / BLOCKED — CLIENT DECISION** |
| AC-05 p7 | Opening TB equals MYOB line-by-line at cutover | Synthetic migration validator/load/idempotency passed; MYOB absent | **PARTIAL / BLOCKED — CLIENT DECISION** |
| AC-06 p7 | One full month agrees in both systems | No real parallel month available | **NOT TESTED** |
| AC-07 p7 | Sample transaction traceable to user/time/prior value | Auditlog and immutability probes passed locally | **VERIFIED LOCALLY / BLOCKED — CLIENT DECISION** on operational retention |
| AC-08 p7 | Each role allowed/forbidden actions work | Full synthetic role probes and guards passed | **VERIFIED LOCALLY / BLOCKED — CLIENT DECISION** on final matrix |
| AC-09 p7 | Backup restores to test environment | Backup hash/manifest, PostgreSQL restore, filestore inspection passed | **VERIFIED LOCALLY** synthetically; production handover pending |

## Assumptions and scope boundaries

Pages 7–8 list unconfirmed modules, volume, end-to-end customer/supplier flows,
bank count/statement source, approval trail, samples, BIR/opening-balance owner,
EIS mandate, live/archive years, server, backup device, and restore owner. They
remain in [docs/decisions-and-blockers.md](decisions-and-blockers.md). The local
implementation does not silently promote them to approved requirements.
