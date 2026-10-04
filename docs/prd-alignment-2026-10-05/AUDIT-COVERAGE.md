> Latest implementation and acceptance status: [phase 2 report](phase-2/REPORT.md), module18.0.2.13.0. The material below records phase 1 audit coverage; superseded open engineering items are resolved only where the phase 2 evidence says so.

# Audit path inventory

Candidate `18.0.2.12.0`; source rules are in `data/auditlog_rule_data.xml`. Each listed rule subscribes full create/write/unlink capture. Approval/post/reverse actions are evidenced by their native state/metadata writes and created accounting records; OCA does not emit an independent business-action event for every method call. A failed transaction rolls its audit writes back too.

| Path | Captured models/effects | Verification and remaining work |
|---|---|---|
| Invoice, bill, journal create/edit/post/reverse | `account.move`, `account.move.line`; reversal links/new lines, permanent original | Native old/new line narration with actor/time, original immutability, reversal and RPC invoice trace pass. Check every client-specific extension. |
| Payments, settlement, undo | `account.payment`, partial/full reconcile, move/line | Partial payment and later-date reversal reconciliation pass; effective closed-period undo blocked. Verify native exchange/cash-basis extensions if supported; foreign currency outside current PRD baseline. |
| Period close/reopen | `thirdcode.accounting.period` actor/time/state | Accountant close, Administrator reopen, forbidden edits and real cursor race probes. |
| Scheduled journals/invoices | Recurring headers and both line models; generated move/lines | Retry and posted record constraints tested. Parallel scheduler worker behavior still needs representative rehearsal. |
| Payment approval/batch | Batch header and line; approving user/time/state; payment/move | Optional threshold and partial settlement native tests pass. Threshold remains optional. |
| Employee expense approval/reimbursement | `hr.expense`, `hr.expense.sheet`, resulting bill/payment/moves | Native complete expense-flow test in final results; added rules installed. Dedicated actor/old-new checks across every expense approval stage remain. |
| Manual bank reconciliation | Custom reconciliation record, native statement line, move/line | Ledger-derived difference/sign controls tested. Statement PDF attachment mutation not comprehensively audited. |
| Year-end transfer | Custom year-end record, move/line and native reversal | Retained earnings posting and P&L preservation tested. |
| Masters | Accounts, journals, partners, partner banks, taxes, tax repartition, payment terms/lines | Rules installed. Detailed actor/value regression currently samples journal lines, not every master. Shared-company attribution must be checked in production. |
| Migration / tax / report approvals | Migration batch, tax profile, report sample; generated move/lines | Synthetic guarded workflows tested. Migration row changes and attachment evidence are not fully covered by this rule set. |
| Retained evidence | `auditlog.log` and `auditlog.log.line` | Both reject write/unlink, even sudo. Read scopes follow recorded company; unknown history platform-only. Local recovery comparison includes actors, timestamps and old/new values in SHA-256. |

Uncovered or incomplete paths: user/role membership administration, company configuration, attachment replacement/unlink, products and other masters/extensions, migration-row changes, audit-rule subscription changes, and all-action completeness checks. Do not mark NF-05 complete. Rules are `noupdate`: production inventory must detect previously disabled or modified rules; a module upgrade alone does not prove they are active. Native database/host administrators can bypass ORM controls, so hosting permissions, off-system retention and recovery are separate obligations.

Historical logs are preserved. The migration adds company-attribution metadata from snapshots/surviving records; it does not reconstruct events that were never logged. A scope that cannot be established remains unavailable to tenant roles and available to platform staff for investigation. The local upgrade had five attributable audit parents and 108 detail rows; no historical production log population was inspected.
