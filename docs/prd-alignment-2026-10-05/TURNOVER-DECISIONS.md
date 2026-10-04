# White-label ownership and decision register

The user is the developer and product owner. Product engineering decisions belong to them. Each future client's finance lead/accountant validates that client's tax setup, document requirements, opening balances and reports. “Owner” means the accountable decision-maker for a particular result; it does not imply that the developer must already employ an accountant or have a client selected.

| Decision / activity | Responsible party | Exact unresolved input |
|---|---|---|
| Product release | Developer/product owner (user) | Engineering gaps and hosted gates in REPORT.md. |
| Hosted operations | Hosting operator, not yet named | Actual Railway deployment/volume, backup job/timezone/destination, encryption/access, alerts, retention, RPO/RTO and recovery operator/deputy. |
| Numbering | Product owner with each client's accountant | Is continuity per company/document type/journal, or one global series? Must counters continue across fiscal years, or may a newly authorized series begin? How are invoice/credit-note and payment/journal series separated? What constitutes an approved prospective new series? No historical renumbering. Current native invoice/journal fiscal resets are not certified. |
| Chart/tax/payment setup | Each client's finance lead/accountant, not named | MYOB account mapping, AR/AP and cash/clearing accounts, TIN/registration, tax tags/rates/withholding treatment, payment instruments, petty cash and bank accounts. |
| Cash flow | Each client's accountant | Cash-equivalent account scope, operating/investing/financing mappings, mixed-entry allocation and non-cash treatment, accepted statement method/presentation. |
| Custom documents | Each client's finance lead and authorized signatory | SOA, comparative FS, invoice/receipt samples, RP-04 definition, stock dimensions, signatures, actual authorized control number and layout revision. |
| MYOB migration | Named individual at each client | Authorized extraction, cutover date, live history/archive period, non-overlap policy, undeposited receipt mapping, TB/AR/AP reconciliation and approval. |
| EIS / CAS | Each client's accountant and taxpayer | Taxpayer classification and applicability determination; registration pack, submission and actual certificate/control values. No legal applicability conclusion or transmission integration has been assumed. |
| Acceptance | Client owner on technical adviser's recommendation, both to be named in contract | AC-01–09 evidence, full real parallel month, recovery demonstration and signatures. |
| White-label delivery | Developer and each client's contracting owner | Branding/domain/email, operator/support responsibilities, upgrade ownership, license obligations, access handover and client data export/retention. Keep platform administrator accounts separate from tenant administrators. |

Reusable onboarding sequence: deploy a verified product revision into the approved hosted structure; establish company/role isolation and operational recovery; configure client identity/chart/tax/numbering; collect and approve versioned samples; trial-load and reconcile authorized data; rehearse recovery and cutover; run client acceptance and the full parallel month; record actual sign-off before turnover. A trial company, checkbox or successful HTTP response cannot supply these outcomes.

AR-06 recurring invoices remains assumed and AP-07 payment threshold approval remains optional. The hosted architecture amendment changes deployment assumptions, not tax, migration, audit, recovery or acceptance requirements. Five named users/two typical users and headroom to ten remain the stated capacity baseline; volumes and proposed latency targets require agreement.
