# TCSI Accounting addon

This addon contains Third Code Solutions Inc. extensions and the TCSI visual
identity layer. Odoo Community remains the authoritative ledger and OCA modules
remain upstream and unmodified.

The branding layer uses the official Th/rd Code mark and violet/lilac visual
language, with a branded login, favicon, navigation identity, modern enterprise
styling, and removal of Odoo promotional links from user-facing surfaces while
preserving the native accounting flows.

## Functional surfaces

- provisional business-role groups and server-side posting/report/close/reopen rules;
- immutable audit-log entries and posted-move protection;
- accounting periods, recurring journals, recurring invoices/bills, and
  idempotent scheduled runs;
- payment batches, advance payments, official-receipt metadata/numbering, and
  cash/cheque/transfer instrument fields;
- credit/debit note classification, native reversal support, and custom
  invoice/receipt reports guarded by accountant-owned configuration;
- paper/PDF bank reconciliation evidence, statement-line reconciliation status,
  and administrator-only reopen;
- tax-profile, report-sample, BIR/EIS, retention, backup-owner, and history
  policy configuration fields;
- provisional balance-sheet, profit-and-loss, and cash-movement reports from
  native move lines;
- year-end income/expense close to retained earnings through native journal
  entries;
- migration batches and line reconciliation records.

## Important boundaries

The role matrix, report layouts, tax/withholding rates, BIR acknowledgement
control values, EIS classification, history policy, payment thresholds, and
reconciliation definition are intentionally configurable and remain pending
client/accountant sign-off. Templates display a draft marker while report
samples are unapproved. Official-receipt printing is blocked until the
accountant-owned BIR acknowledgement control number is present and explicitly
approved.

The addon does not implement a second ledger, direct accounting-table writes,
Enterprise modules, payroll, purchasing, bank feeds, EIS transmission, or
external integrations.
