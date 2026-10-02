# TCSI Accounting — team operations guide

How every person on the accounting team signs in, moves through the system,
and enters each kind of document. This describes the **production workspace**:

- Team sign-in (the books): <https://tcsi-accounting-portal.vercel.app/web/login>
- The workspace behind that page is the accounting system (Odoo-based). Everything
  under `/web/…` and `/workspace/…` on the portal is the live workspace.
- The other portal pages (`/`, `/platform`, `/controls`, `/pilot`, `/contact`) are
  product pages — they describe the system and take demo requests; they contain no
  ledger data.

Passwords are distributed to each person privately (never in this file, chat, or
email). Everyone gets their **own** login; administrator credentials are not
shared.

## 1. Team accounts and what each role may do

| Login | Role | Use it for |
| --- | --- | --- |
| `administrator@tcsi.local` | TCSI Accounting Administrator | Company setup, approvals, period close/reopen, year-end |
| `accountant@tcsi.local` | TCSI Accountant | Drafting, posting, payments, reconciliation, reports |
| `encoder@tcsi.local` | TCSI Encoder | Draft data entry only (cannot post or approve) |
| `readonly@tcsi.local` | TCSI Read-only | Reading and reviewing — cannot change anything |

Capability matrix (enforced by the system, not by convention):

| Action | Read-only | Encoder | Accountant | Administrator |
| --- | --- | --- | --- | --- |
| View entries and reports | Yes | Yes | Yes | Yes |
| Create / edit drafts | No | Yes | Yes | Yes |
| Post entries (touch the ledger) | No | No | Yes | Yes |
| Register / allocate payments | No | No | Yes | Yes |
| Close an accounting period | No | No | Yes | Yes |
| Reopen a closed period | No | No | No | Yes |
| Approve over-threshold payment batches | No | No | No | Yes |
| Configure company, journals, BIR values | No | No | No | Yes |
| Financial statements menu | Yes | Hidden | Yes | Yes |

Every user is assigned to the company **Third Code Solutions Inc.** If a person
ever sees no company, or the wrong one, stop and have the Administrator fix the
user's company assignment before entering anything.

## 2. Signing in and orientation

1. Open <https://tcsi-accounting-portal.vercel.app/web/login> and sign in with a
   named login.
2. Top bar: the **company switcher** (confirm "Third Code Solutions Inc."), the
   account menu, and the app grid. Left sidebar: the TCSI Accounting menu.
3. **Dark mode** — the toggle in the sidebar footer (and on the sign-in page).
   It is a per-browser display choice; it changes nothing in the books.
4. The workspace has one rule of framing: **drafts are editable, posted records
   are not.** Corrections to posted records always use the approved
   credit-note / reversal flow; nothing posted is ever deleted or silently edited.

## 3. Routes — what lives where

Workspace (after `/web/login`):

| Route / menu | What it is | Who |
| --- | --- | --- |
| **Overview** (TCSI Accounting home) | Receivables, payables, cash position, recent activity, quick "New invoice" | Everyone |
| **Controls → Accounting periods** | The list of periods; posting is only allowed inside an open period | Everyone sees; close = Accountant+; reopen = Administrator |
| **Controls → Recurring journals** | Recurring accrual/standard entries | Accountant, Administrator |
| **Controls → Recurring invoices and bills** | Scheduled repeat invoices/bills (e.g., monthly service) | Accountant, Administrator |
| **Controls → Tax profiles** | The approved VAT / withholding mapping per company | Accountant, Administrator |
| **Controls → Report samples** | Approved statement/invoice/receipt samples and revisions | Accountant, Administrator |
| **Controls → Year-end retained earnings** | Year-end close entry | Accountant, Administrator |
| **Payment batches** | Batched supplier/customer payments with approval threshold | Created by Accountant; approved by Administrator |
| **Bank reconciliations** | Manual bank/cash reconciliation with statement attachment and sign-off | Accountant; reopen = Administrator |
| **Financial statements** | Balance sheet / P&L / trial balance / GL exports for a date range | Read-only, Accountant, Administrator |
| **Migration batches** | Opening-balance / MYOB import batches with validation | Accountant, Administrator |
| **Workspace** (app grid, `/workspace/apps`) | The catalog of business apps; installs are a system-administration task, not a user action | Everyone sees the catalog |
| **Revenue** | Invoices, bills, credit notes, payments, journal entries, chart/journals config | Per role; config screens are Administrator |
| **Spend** | Expense claims and reimbursement flow | Per role |
| **Directory** | Customers, suppliers, contacts | Encoder+ (Accountant manages) |
| **Messages** | Team chat, chatter, and the ORVEXA command assistant | Everyone |
| **People** | Employee profiles / departments | Per role |
| **Insights** | Dashboards | Everyone |
| **Settings / Technical modules** | System administration (users, technical lists, module state) | Engine system administrator only |

Portal pages (no ledger data): `/` product home · `/platform` capability
overview · `/controls` published control description · `/pilot` how the hosted
pilot runs · `/contact` request a demo · `/login` + `/owner` the platform-owner
console (owner only).

## 4. Company setup — status and the finish line

The company was already created and the four named logins are assigned to it.
The remaining setup was executed through the engine administrator with
`scripts/configure_company_setup.py` (chart of accounts, journals, open
period). Checklist for a company that is ready to post:

1. Legal details approved (name, address, TIN, currency **PHP**, fiscal year).
2. Chart of accounts loaded; sales, purchase, general, bank and cash journals
   created with their default accounts.
3. Current period created and **Open** in Controls → Accounting periods.
4. Tax profile mapped and marked Configured by the Accountant (VAT /
   withholding). The software never invents statutory rates — the approved
   values come from the company's accountant.
5. Company form → **Third Code Accounting** tab: BIR acknowledgement control
   number, EIS status, signatory, numbering owner, retention, backup owners.
   **Validate configuration** surfaces what is missing. Invoice/receipt output
   stays guarded until these approvals are real.
6. Report samples approved, then "Client report samples approved" on the
   company — until then, custom statements print with a provisional marking.
7. Opening balances / open items loaded through Migration batches, reconciled
   to source counts.

**Trial mode (current pilot use).** The pilot company and the ten trial
organisations are provisioned structurally (items 1–3 above) through the
token-gated provisioning endpoint: PHP currency, PH chart of accounts,
journals, an open FY 2026 period and a report layout. With **Trial mode**
enabled on the company (company form → Regulatory configuration), items 4–6
are deferred by design: invoices and receipts print without BIR control values
and every output is watermarked "TRIAL COPY" until real approvals exist.
Receipt numbering is per company (`OR/…`, sequence created on first receipt).
There is no email sending configured for the trial: distribute and rotate
logins out-of-band from the engine.

## 5. Daily input workflows

**5.1 Customer invoice (Encoder or Accountant drafts; Accountant posts)**
Revenue → Invoices → **New** → select customer → invoice date, payment terms →
add lines (description, quantity, unit price, taxes) → attach the source
document with the paperclip → **Save** (draft) → review: company, dates,
account, tax, totals, attachment → Accountant presses **Post**. Printing uses
the guarded TCSI invoice layout; it stays blocked with a visible notice until
the company's BIR/document approvals exist.

**5.2 Customer collections (Accountant)**
Open the posted invoice → **Register Payment** → choose the bank/cash journal,
amount (partial allowed), date, reference/instrument → Post. The unpaid balance
updates correctly. Advances are recorded as advances and allocated later —
never invent an invoice to hold money.

**5.3 Supplier bill (Encoder or Accountant drafts; Accountant posts)**
Revenue → Bills → **New** → supplier, bill date, due date, reference → lines
and taxes → attach the supplier's bill (PDF/scan) → Save → review → **Post**.
Correct a posted bill only through a debit note / reversal.

**5.4 Payment batches (Accountant + Administrator approval)**
TCSI Accounting → **Payment batches** → New → add lines (partner, journal,
amount, reference) → choose cash / cheque / transfer → **Submit**. If the
amount crosses the company's approval threshold, an Administrator presses
**Approve**; the Accountant then **Post batch**. Compare created payments to
the source bills and the bank evidence afterwards.

**5.5 Manual journal entries (Accountant)**
Revenue → Accounting → Journal Entries → New → pick the general journal and
date (inside the open period) → balanced debit/credit lines → Save → Post.
Out-of-balance entries and closed-period dates are refused — that is the guard
working, not an error to work around.

**5.6 Bank / cash reconciliation (Accountant)**
TCSI Accounting → **Bank reconciliations** → New → journal, period dates →
attach the statement (paper/PDF) → enter opening and closing balances and
outstanding items → **Compute ledger balance** → investigate any difference →
**Sign off** only when the difference is zero and the evidence agrees.
Reopening a signed-off reconciliation is an Administrator action.

**5.7 Recurring work (Accountant)**
Controls → Recurring journals / Recurring invoices and bills → set cadence and
template → the scheduler creates the drafts; review drafts before posting.
Check the menu weekly for failed or skipped runs.

**5.8 Reports (Read-only, Accountant, Administrator)**
TCSI Accounting → **Financial statements** → choose statement, dates, and
posted only → export. Native reports (trial balance, general ledger, aged
receivables/payables, partner statements) live in Revenue → Reporting. A PDF
with the provisional warning is not an approved client-format report yet.

**5.9 Month-end / year-end**
Reconcile every bank/cash journal, customer and supplier open items, and
control accounts → review drafts and failed runs → approve the month → close
its period in Controls → at year-end use **Year-end retained earnings** →
verify the paired database + filestore backup.

**5.10 Migration / opening balances (Accountant)**
TCSI Accounting → **Migration batches** → New → attach the approved export →
map accounts and validate → load only against the correct company/journals →
reconcile every source count and balance before sign-off.

**5.11 ORVEXA**
Open **Messages** and address ORVEXA in chat for rule-based status answers
("show recent activity"). It identifies its own limits; it is not a general AI
agent and never posts entries.

## 6. Working rules for the team

- One named login per person. The Administrator login stays with the
  Administrator; the encoder never borrows the accountant's session.
- Draft → review → post. Review means checking company, dates, accounts, tax,
  amounts, and the attached source document.
- Posted = permanent. Corrections via credit note / debit note / reversal.
- Closed period = locked. Only the Administrator reopens, with a recorded
  reason, and only for an approved exception.
- Attachments are part of the record: every bill, statement, and reconciliation
  keeps its source document.
- Backups are paired (database **and** filestore). The named restore owner
  verifies a recent restore; a database-only backup is incomplete.

## 7. Troubleshooting

| Symptom | Meaning and next action |
| --- | --- |
| Cannot sign in | Use the exact login email; ask the Administrator to reset access if needed. Never share passwords to "test". |
| Signed in but no company visible | The user's company assignment is missing — Administrator fixes it. |
| “No journal could be found … for any of those types: sale” | The company setup (chart/journals/period) is not complete yet. This is being finished via the engine administrator; until then, only drafts requiring journals will refuse. |
| Cannot post | Check role, selected company, open period, balanced entry, journal, and account. Do not try to bypass the guard. |
| Invoice/receipt print blocked or marked draft | The company's BIR control number / approved samples are missing. Obtain the real approval first. |
| Payment batch waits | Its amount crossed the approval threshold — Administrator approves, then Accountant posts. |
| Reconciliation will not sign off | Difference is not zero, evidence missing, or wrong journal/period. Fix the mismatch; do not force sign-off. |
| Report shows a provisional watermark | Report samples are not approved for the company yet. |
| Something is unavailable | Note company, user, time, page, and the exact message, then report it. Do not retry a posting blindly until you know its result. |

## 8. Organization and employee account management

- One client = one organization (Odoo company). Organizations are fully
  isolated: accounting data, reports, and even user lists.
- Org administrators manage their own people inside
  `TCSI Accounting → Organization`:
  - *New Employee Account* — create logins for their staff (Accountant,
    Encoder, Read-only, or another Administrator).
  - *Employee Accounts* — list own users, reset passwords, enable/disable
    accounts. Everything is company-scoped; a tenant administrator can
    never see or touch another organization.
- The platform owner holds the system superadmin (`superadmin@tcsi.local`,
  credentials outside the repo) with the whole-system console:
  - Create a new organization: *Settings → Companies → New*, then click
    *Provision TCSI Baseline* on the company form (chart, journals, taxes,
    open period, trial mode).
  - Create any organization's first administrator from
    *Organization → New Employee Account* (the Company selector is
    superadmin-only).
- The `res.users` visibility rule scopes role users to their own
  companies; base Odoo would otherwise expose every internal user record
  (names and logins) across tenants.

## 9. Related documents

- `docs/accounting-user-guide.md` — setup sequence and the five-company
  acceptance checklist in full detail.
- `docs/cas-control-pack.md` — the control descriptions the system enforces.
- `docs/decisions-and-blockers.md` — open regulatory / retention decisions.
- `docs/verification.md` — evidence of what has been verified on the hosted
  system, and when.
