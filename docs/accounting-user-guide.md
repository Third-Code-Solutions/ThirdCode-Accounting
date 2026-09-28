# Accounting system user guide and five-company go-live path

This guide is for the hosted pilot at
<https://tcsi-accounting-portal.vercel.app/web/login>. The accounting workspace is
Odoo. The separate portal pages describe the product; they are not another
ledger. Use a named login for each person. Select the legal company whose books
you are working on before entering or approving anything.

## Potential-client demonstration on this workstation

The local demonstration at <http://localhost:8077/web/login> uses a separate
`tcsi_demo` database and five clearly named fictional companies. It does not
write to the hosted pilot. Keep the URL on the presenter's workstation and
screen-share the browser; `localhost` is not a public client link. The named
presenter and five restricted accountant logins are in
`D:\thirdcode\accounting-system\private-demo-access\credentials.json`, outside
the Git checkout. Do not show or send that file to a prospect.
After a workstation restart, run `./scripts/start_client_demo.ps1` from the
demo checkout. It starts the existing isolated containers, checks the local
login endpoint, and reruns the read-only demo acceptance check. Allow several
minutes for the five named-account and report checks before the client call.
The saved fictional transactions retain their original demo date after a
restart. The acceptance check reports that date and validates the related
invoices, recurring entries, and reports against it; it does not imply that
new transactions were posted today.

For a sales walkthrough:

Use **Dark mode** in the workspace sidebar footer to switch the interface.
The sign-in page has the same control. The choice is saved in this browser;
it changes presentation only and does not affect company data or permissions.

1. Sign in as `demo.presenter@example.invalid` using the private credential
   file. Start on **Overview** for **DEMO | Meridian Design Studio**. Show the
   current receivables, payables, cash position, and recent entries.
2. Open the posted customer invoice and supplier bill. The invoice has a
   partial receipt, so compare its original amount with the unpaid balance.
3. Open **Payment batches** and the fictional Meridian customer receipt and
   supplier settlement. Show that the configured threshold required approval
   before each batch posted, then compare both remaining balances.
4. Open **Bank reconciliations** and the Meridian example. Open the attached
   PDF marked fictional; check the bank ledger, statement balance, zero
   difference, and sign-off. This is a manual reconciliation, not a bank feed.
   The two batch payments remain pending bank clearing, so the sample bank
   balance still reflects the fictional opening entry.
5. In **Controls**, show the open period, configured demo tax disclosure, the
   recurring monthly service invoice, and the balanced recurring accrual
   journal. The sample tax profile makes no statutory determination for a
   real company.
6. Open **Financial statements**, select a date range and posted entries, and
   export the balance sheet or profit and loss PDF. The draft-layout warning is
   deliberate: no client has approved an actual financial report format.
7. Ask ORVEXA to “show recent activity.” It is a private, rule-based command
   assistant and identifies its own limits in the chat. It is not a general AI
   accounting agent.
8. Switch to the other four fictional companies and show their separate
   invoice, bill, period, and reports. The five accountant logins each have
   only their own company assigned. Do not use the presenter login as proof of
   restricted employee access.

On this workstation, `scripts/seed_client_demo.py` provisions the isolated
records and `scripts/check_client_demo.py` checks the five companies, named
accountant isolation, payment, reconciliation, and report totals. The seeder
requires an explicit `--apply`, a database name containing `demo`, a loopback
HTTP URL, and a credential file outside the checkout. Re-running it is
idempotent for accounting records but rotates the demo user passwords in that
file. Keep the Docker database and Odoo filestore together when backing up or
resetting this demo. A paired snapshot from 28 September 2026 is stored in
`private-demo-access` beside the credentials file as
`tcsi_demo_20260928.dump` and `tcsi_demo_filestore_20260928.tgz`; these files
are local and outside Git.

**Current live state (28 September 2026):** the read-only production preflight
found one company with no country or legal identifier recorded, USD as its
current book currency, and no chart of accounts, sales/purchase/general/bank
journals, current open period, configured tax profile, approved document
samples, or assigned backup/restore owners. Login and server health work, but
real posting is not accepted. Confirm the intended legal country, book currency,
and registration details before changing them. Do not treat a green
`/api/readiness` response as financial readiness; it checks only service
availability.

## The basic model

- A **company** is one legal set of books. It needs its own approved accounts,
  journals, tax treatment, opening balances, periods, documents, and reports.
- A **user** is one employee's login. An Administrator assigns that user to one
  or more companies and an appropriate role. Creating five logins does **not**
  create or configure five companies. Giving one employee access to five
  companies does **not** merge their books.
- A **journal** groups transactions, such as sales, purchases, bank, cash, or
  general entries. An **account** is a line in the chart of accounts. A
  **period** controls when entries may be posted.
- **Draft** means reviewable and editable. **Posted** means entered into the
  ledger. Correct posted mistakes by the approved reversal/credit-note flow;
  do not delete or silently edit the original.

## 1. Set up each company before giving staff posting access

The Administrator and lead Accountant repeat these steps for **each** legal
company. Keep the approved source documents and owner decision with the
company's setup record. Do not copy another company's tax, balances, or BIR
values merely to make a check pass.

1. Create the legal company in Odoo and select it in the company switcher.
   Confirm legal name, address, currency, fiscal year, and registration details.
2. Approve and load that company's chart of accounts. Create its sales,
   purchase, general, and every bank/cash journal, with the correct default
   accounts and numbering policy. Test that entries and reports stay in the
   selected company.
3. In **TCSI Accounting → Controls → Accounting periods**, create the current
   period and set it open. Keep the preceding period closed when its close is
   approved. Reopening is an Administrator action with a recorded reason.
4. In **TCSI Accounting → Controls → Tax profiles**, map approved native VAT
   and withholding taxes, enter the effective date and accountant owner, and
   select **Configure** only after reviewing the basis. The software does not
   choose tax rates for the business.
5. In the company form's **Third Code Accounting** tab, record the assessed BIR
   acknowledgement/control number, EIS classification, signatory, numbering
   owner, retention setting, and backup/restore owners. Use **Validate
   configuration** to surface missing fields. Official invoice/receipt output
   remains guarded until required company approvals exist.
6. In **TCSI Accounting → Controls → Report samples**, attach the approved
   statement, financial, invoice, receipt, and reconciliation samples with
   revisions. The Administrator uses **Approve sample** after the actual
   document review. Then mark the company report approval flag. Generic
   financial statements remain visibly provisional until this is done.
7. Decide whether historical MYOB transactions are migrated or retained in a
   read-only archive. Validate the approved export and mapping before loading.
   Load opening balances and open items only against the correct company and
   journals. Reconcile every source count and balance. A real cutover requires
   an authorized source export and accountant sign-off.
8. Create a separate named user for each employee. Assign only that employee's
   approved company list and role: **Administrator** for configuration and
   restricted approvals, **Accountant** for posting/reconciliation, **Encoder**
   for draft entry, or **Read-only** for review. Test the login with the user's
   own account. Do not share the Administrator login.
9. Run the read-only preflight from an operator workstation as an Administrator
   who should see every legal company. For the current one-company pilot, use:

   ```powershell
   python scripts/check_company_readiness.py --url https://tcsi-accounting-production.up.railway.app --database tcsi_pilot --login <administrator-login> --expected-companies 1 --expected-country-code <approved-country-code> --expected-currency-code <approved-currency-code>
   ```

   The command prompts for the password without displaying it. Every company
   check must pass. Use only accountant-approved country and currency codes;
   the preflight checks their presence and the expected values, without
   asserting that the approved values are legally correct. It does not prove
   source balances or tax/legal approval.

## 2. Daily accounting work

1. **Start:** sign in, select the legal company, and check the open period.
   If the wrong company appears, stop and have the Administrator fix access.
2. **Customer billing:** create or find the customer, create a customer invoice
   in Odoo Accounting, check company, date, terms, account, tax, amounts, and
   attachment, then save a draft. An Accountant reviews and posts it. Use the
   guarded invoice print only after that company's document approval is real.
3. **Customer collections:** register a payment against the posted invoice.
   Check the bank/cash journal, instrument, reference, date, and amount.
   Partial payment should leave the correct unpaid balance. Record an advance
   as an advance and allocate it later; do not invent an invoice to hold it.
4. **Supplier bills:** create or find the supplier, attach the source bill,
   enter a draft bill with the proper company, account, tax, and due date, and
   have an Accountant review and post it. Correct a posted bill through the
   authorized credit/debit or reversal flow.
5. **Payables and bulk payments:** use native payment registration for a single
   bill. For a batch, open **TCSI Accounting → Payment batches**, add lines,
   select cash/cheque/transfer and references, then **Submit**. If the
   company's approval threshold applies, an Administrator must **Approve**.
   An Accountant then uses **Post batch**. Compare the created payments with
   the source bills and bank evidence.
6. **Employee expenses:** assign each employee a named expense manager in the
   employee record before using **Expenses**. The employee submits an expense
   report with the receipt attached. That employee's assigned expense manager
   reviews and approves it; an Accountant posts the approved report and
   registers reimbursement through the correct bank/cash journal. An
   Accountant who is not the assigned manager cannot approve that employee's
   report merely because of the Accountant role. Agree the real expense and
   reimbursement policy before staff use this for company money.
7. **Manual journal entries:** enter balanced debits and credits in the right
   general journal and period. An Accountant posts only after review. The
   system blocks out-of-balance entries and posting into closed periods.
8. **Bank/cash reconciliation:** in **TCSI Accounting → Bank reconciliations**,
   choose the correct journal and dates, attach the paper/PDF statement,
   record opening/closing balances and outstanding items, then **Compute ledger
   balance**. Investigate any difference. **Sign off reconciliation** only
   when the calculated difference is zero and evidence agrees. Reopening is
   restricted to an Administrator.

## 3. Month-end and year-end

1. Reconcile every bank/cash journal, customer and supplier open items, and
   control accounts against approved evidence. Review draft entries, failed
   recurring runs, and unmatched payments.
2. Use **TCSI Accounting → Financial statements** and native Accounting reports
   for the trial balance, general ledger, profit and loss, balance sheet,
   cash movement, aged receivables/payables, and partner statements. Set the
   company, date range, and **posted** target. Tie totals to the ledger and
   approved source reports. A PDF with a provisional warning is not an
   accepted client-format report.
3. Approve the month, then close its accounting period. After close, changes
   use the approved exception/reversal procedure. At year-end, the Accountant
   reviews the retained-earnings account and journal before using **TCSI
   Accounting → Controls → Year-end retained earnings**.
4. Check the scheduled paired database **and** filestore backup. The recovery
   owner restores a recent pair to an isolated target and verifies attachments,
   reports, and ledger totals. A database-only backup misses Odoo attachments.

## 4. Problems staff may encounter

| Symptom | Meaning and next action |
| --- | --- |
| Can sign in but cannot see a company | Administrator must assign the user to the legal company and correct role. A login alone does not grant company access. |
| Cannot post | Check role, selected company, open period, balanced entry, journal, account, and required tax configuration. Do not disable the guard. |
| Invoice/receipt print is blocked or marked draft | The company's BIR control or approved sample is absent. Obtain the real approval and value, then configure them. |
| Payment batch waits for approval | Its amount crossed the configured threshold. The named approver must approve before the Accountant posts. |
| Employee expense cannot be approved | Check the employee's assigned expense manager and the selected company. An unrelated Accountant cannot approve that employee's report. |
| Reconciliation cannot sign off | The difference is nonzero, statement evidence is missing, or journal/period is wrong. Resolve the underlying mismatch. |
| Portal says “ready” but books are empty | Portal health means the services answer. Run the company preflight and financial acceptance checks. |
| System or report unavailable | Record the company, user, time, page, and error; check the Railway origin and backup status. Do not retry a posting blindly until its result is known. |

## 5. Five-company acceptance before real use

Each company must have: its legal setup and approved chart/journals/taxes,
correct opening balances and open items, current period, accepted document
samples, named staff and role tests, a reconciled trial balance, one real
parallel accounting month, bank/report sign-off, and a recent paired restore.
Also settle the retention, regulatory, license, and support decisions in
[`decisions-and-blockers.md`](decisions-and-blockers.md) and
[`cas-control-pack.md`](cas-control-pack.md).

The technical suite has tested ten **synthetic** isolated companies, including
posted entries, migration batches, attachments, and company-specific reports.
It does not replace the five companies' actual accounting acceptance. The
standalone Supabase ledger pages remain unreleased; use the Odoo workspace.
