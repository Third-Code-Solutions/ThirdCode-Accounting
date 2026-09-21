# Implementation checklist

## Technical implementation

- [x] Read the complete PRD and pasted implementation brief.
- [x] Establish pinned Odoo Community/PostgreSQL foundation and OCA modules.
- [x] Keep all custom behavior in `thirdcode_accounting` and use native ledger
      and posting/reconciliation operations.
- [x] Implement provisional RBAC and server-side role/posting/period/audit
      controls.
- [x] Implement recurring journals/invoices, payment batches, advances,
      credit/debit notes, employee-expense surface, and bank reconciliation.
- [x] Implement guarded invoice/official-receipt reports, tax/report metadata,
      numbering controls, year-end retained earnings, and CAS template.
- [x] Implement migration validation/load/idempotency/reconciliation tooling.
- [x] Implement backup/verify/restore and synthetic performance tooling.
- [x] Run full-scope and Milestone 1 regression checks after implementation.
- [x] Update traceability, decisions, plan, verification, README, and addon
      documentation with actual evidence and boundaries.

## Client acceptance gates

- [ ] Issue approved PRD v1.0 / scope addendum.
- [ ] Supply signed SOA, financial-statement, invoice, official-receipt, and
      reconciliation samples.
- [ ] Confirm tax/withholding, BIR control, EIS, numbering, retention, and
      signatory decisions.
- [ ] Supply authorized MYOB export, mapping, opening-balance owner, archive
      decision, and cutover/rollback approval.
- [ ] Run the real parallel accounting month.
- [ ] Validate the final role matrix, infrastructure, browsers, backup device,
      restore owner, RPO/RTO, and full-year performance.
- [ ] Complete AC-01 through AC-09 and record named client sign-off.
