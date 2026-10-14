# White-label ownership and decision register

The user is the developer/technical owner. Engineering decisions belong to them;
they are not the client accounting or acceptance authority. The PRD is a review
draft, not an approved specification. Each client's finance lead/accountant
validates tax setup, document requirements, opening balances and reports. Client
Owner approval follows the Technical Adviser's recommendation; named people and
finance ownership remain pending CEO nomination. No MYOB source authorization or
client sample approval has been established. Current client intake is consolidated
in `REMAINING-ACCEPTANCE.md`.

| Decision / activity | Responsible party | Exact unresolved input |
|---|---|---|
| Technical release | Developer/technical owner (user) | Engineering and hosted gates; does not supply client accounting or acceptance approval. |
| Hosted operations | Hosting operator, not yet named | Actual Railway deployment/volume, backup job/timezone/destination, encryption/access, alerts, retention, RPO/RTO and recovery operator/deputy. |
| Numbering | Developer/technical owner (user), engineering decision received | **Engineering default implemented:** continuous across fiscal years per company/journal, including reversals/credit notes in that journal; official receipts retain their separate company counter. Prospective CODE/C/8-digit names start above the highest recorded counter. Existing posted names preserved. Production custom regexes and preassigned drafts require inventory; client accounting/statutory approval remains separate. |
| Chart/tax/payment setup | Each client's finance lead/accountant, not named | MYOB account mapping, AR/AP and cash/clearing accounts, TIN/registration, tax tags/rates/withholding treatment, payment instruments, petty cash and bank accounts. |
| Cash flow | Each client's accountant | Cash-equivalent account scope, operating/investing/financing mappings, mixed-entry allocation and non-cash treatment, accepted statement method/presentation. |
| Custom documents | Each client's finance lead and authorized signatory | SOA, comparative FS, invoice/receipt samples, RP-04 definition, stock dimensions, signatures, actual authorized control number and layout revision. |
| MYOB migration | Named individual at each client | Authorized extraction, cutover date, live history/archive period, non-overlap policy, undeposited receipt mapping, TB/AR/AP reconciliation and approval. |
| EIS / CAS | Each client's accountant and taxpayer | Taxpayer classification and applicability determination; registration pack, submission and actual certificate/control values. No legal applicability conclusion or transmission integration has been assumed. |
| Acceptance | Client Owner on Technical Adviser's recommendation; names pending CEO nomination | AC-01–09 evidence, full real parallel month, recovery demonstration and actual signatures. |
| White-label delivery | Developer and each client's contracting owner | Branding/domain/email, operator/support responsibilities, upgrade ownership, license obligations, access handover and client data export/retention. Keep platform administrator accounts separate from tenant administrators. |

Reusable onboarding sequence: deploy a verified product revision into the approved hosted structure; establish company/role isolation and operational recovery; configure client identity/chart/tax/numbering; collect and approve versioned samples; trial-load and reconcile authorized data; rehearse recovery and cutover; run client acceptance and the full parallel month; record actual sign-off before turnover. A trial company, checkbox or successful HTTP response cannot supply these outcomes.

AR-06 recurring invoices remains assumed and AP-07 payment threshold approval remains optional. The hosted architecture amendment changes deployment assumptions, not tax, migration, audit, recovery or acceptance requirements. Five named users/two typical users and headroom to ten remain the stated capacity baseline; volumes and proposed latency targets require agreement.
