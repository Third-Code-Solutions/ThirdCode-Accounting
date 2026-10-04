# TCSI Accounting
## Simple user guide

Manage customer invoices, supplier bills, payments, and reports in one company workspace. This guide follows the hosted accounting workspace reviewed on **3 October 2026**.

**Sign in:** https://tcsi-accounting-portal.vercel.app/web/login

### Start here

1. Use the login and password supplied by your company administrator. Each person should have a separate account.
2. Check the company name at the top of the workspace before entering any transaction. If your account has several companies, select the correct one first.
3. Open **Overview**. Choose **Customer invoice**, **Supplier bill**, **Payments**, or **Financial reports** for the task you need.
4. Prepare a draft, check the details, then let an Accountant or Administrator finalize it. Posting adds the transaction to your accounting records.

> **Using a trial company?** Documents can carry **TRIAL COPY** and reports can show **Trial copy** or **Draft layout**. These are expected review outputs. Your administrator and accountant must complete company approvals before using approved business documents.

### Find your task

| Task | Page |
| --- | --- |
| Find your way around and understand your role | 2 |
| Create, print, or correct a customer invoice | 3 |
| Enter supplier bills and record payments | 4 |
| Handle payment batches and bank reconciliation | 5 |
| Run and understand reports | 6 |
| Enter journals, recurring work, and period close | 7 |
| Manage employee accounts and company controls | 8 |
| Use ORVEXA and understand accounting terms | 9 |
| Resolve common problems | 10 |

---

# Your workspace

The **Current workspace** selector near the top of the left sidebar changes apps. Choose **TCSI Accounting** for the overview and controls, or **Revenue** for transaction lists and accounting reports.

### Where to go

| To do this | Open this |
| --- | --- |
| Review balances and recent entries | TCSI Accounting › Overview |
| Find or create customer invoices | Revenue › Customers › Invoices |
| Find or create supplier bills | Revenue › Vendors › Bills |
| Manage customers or suppliers | Revenue › Customers › Customers, or Vendors › Vendors |
| View customer or supplier payments | Revenue › Customers › Payments, or Vendors › Payments |
| Enter an accounting journal | Revenue › Ledger › Journal Entries |
| Export a balance sheet, profit and loss, or cash movement | TCSI Accounting › Financial statements |
| Run a trial balance or general ledger | Revenue › Reports › Reporting library |

### What your role allows

| Role | Everyday responsibility |
| --- | --- |
| Encoder | Prepare and edit drafts. Ask an Accountant to post them. Accounting report access is restricted. |
| Accountant | Review and post transactions; record payments; reconcile balances; run reports. |
| Administrator | Accounting work plus employee accounts, restricted approvals, and company controls. |
| Read-only | Review permitted records and reports without changing data. |

### Small controls that help

Use **Quick search** in the sidebar to find a menu. Use **Search…** inside a list to find records; remove active filters if a record seems missing. Open a row to see its details. **New** starts a record; **Save manually** saves edits; **Discard all changes** abandons unsaved edits.

Use **Attach files** on a saved record to keep its source documents. **Log note** adds internal context. The sidebar's **Dark mode** control changes appearance. Use the user menu to log out when finished, especially on a shared device.

---

# Customer invoices

**Who:** Encoder prepares; Accountant or Administrator reviews and posts.

**Open:** Revenue › Customers › Invoices › **New**. The Overview's **+ New invoice** and **Customer invoice** shortcuts also start an invoice.

### Create and finalize an invoice

1. Select **Customer**. Search existing contacts first. If the customer is new, use the field's create option when available, or add the contact under **Customers**. Check name, address, and billing details.
2. Enter **Invoice Date**, then **Due Date** or **Payment Terms**. Confirm the company, sales journal, and currency.
3. Under **Invoice Lines**, select **Add a line**. Enter the product or description, account, quantity, price, and approved taxes. Repeat for each item.
4. Check the line amounts, tax, and total against your source document. Select **Save manually** and attach supporting files. The record remains **Draft**.
5. An Accountant or Administrator reviews the complete record and selects **Confirm**. Check that the status becomes **Posted** and an invoice number appears.
6. Select **Third Code invoice** to generate the invoice output. Check the downloaded PDF before sharing it through your normal business channel.

> **Before Confirm:** Check company, customer, dates, account, quantity, price, taxes, total, and supporting documents. Use your accountant's approved tax choices; a prefilled value still needs review.

### What happens next

The posted invoice records what the customer owes. It does not mean the customer has paid. Record actual money received using the payment steps on page 4.

**Example:** If an invoice total is PHP 10,000 and you receive PHP 4,000, record a PHP 4,000 payment. The remaining amount due should be PHP 6,000.

### Correct a mistake

**Before posting:** Open the draft, edit the incorrect details, and save it.

**After posting:** Have your Accountant use the invoice's **Credit Note** action and follow the correction review. Check the credit note and remaining balance. If a replacement invoice is needed, create and review it separately. Keep the original transaction and correction together for a clear history.

---

# Bills and payments

An invoice records a customer sale. A supplier bill records a purchase you owe. Recording a payment updates the books; it does not itself send money from your bank.

### Enter a supplier bill

**Open:** Revenue › Vendors › Bills › **New**, or **Supplier bill** on Overview.

1. Select the supplier and enter the supplier's reference, **Bill Date**, and payment terms or due date. Confirm the purchase journal and company.
2. Add the purchased items or services, quantities, prices, expense accounts, and approved taxes. Compare the total with the supplier's bill.
3. Save the draft and attach the supplier's PDF or scan using **Attach files**.
4. An Accountant or Administrator reviews and selects **Confirm**. Check the posted bill and amount due. Use the payment workflow below when the supplier is paid.

### Record money received or paid

**Who:** Accountant or Administrator. Start from the posted invoice or bill so the payment is linked to the correct document.

1. Open the invoice or bill and select **Pay**.
2. Choose the bank or cash **Journal** and available **Payment Method**. Enter the actual **Amount**, **Payment Date**, and reference in **Memo**. Use the real amount for a partial payment.
3. Check the direction: incoming for a customer receipt; outgoing for a supplier payment. Confirm the details with the receipt, deposit, or bank evidence.
4. Select **Create Payment**. Return to the document and check the payment link and remaining amount due.
5. Review payments under **Revenue › Customers › Payments** or **Vendors › Payments**. Open the relevant customer payment and use **Official Receipt** when available to generate its receipt output.

> **Payment status:** A partial payment leaves a balance. **In Payment** can mean a payment is recorded but still needs bank clearing or reconciliation. Check the actual balance and bank evidence before treating it as settled. Do not enter the same payment twice.

### Send documents

The current hosted trial does not have outgoing email configured. Download and check PDFs, then share them through your usual approved email or messaging channel. Trial receipt output remains a **TRIAL COPY**, even though the button is named **Official Receipt**.

---

# Batches and bank checks

**Who:** Accountant or Administrator. An Administrator approves batches that require approval and reopens signed-off reconciliations.

### Record several payments together

**Open:** TCSI Accounting › **Payment batches** › **New**.

1. Select the company, bank/cash **Journal**, date, **Payment Type**, and **Partner Type**. Use **Outbound / Supplier** for supplier settlements or **Inbound / Customer** for collections.
2. Choose **Payment Instrument** and enter its reference. Select **Add a line**; choose the invoice or bill in **Move**, then check partner, amount, and communication/reference. Repeat for the remaining payments.
3. Review **Total Amount** and select **Submit**. If the batch shows **Pending approval**, an Administrator must select **Approve**.
4. An Accountant or Administrator selects **Post batch**. Check **Posted**, inspect each line's **Payment**, and compare the updated invoice/bill balances with the source evidence.

**Result:** Related accounting payments are recorded. Arrange any actual bank transfer through your normal banking process.

### Reconcile a bank or cash journal

**Open:** TCSI Accounting › **Bank reconciliations** › **New**.

1. Enter a clear name, company, journal, statement reference, start/end dates, and owner. Use the exact period covered by the statement.
2. Enter the statement's **Opening Balance** and **Closing Balance**. Record **Outstanding Deposits** and **Outstanding Payments**: amounts already in your books but not yet cleared by the bank.
3. Attach the statement in **Paper/PDF evidence**. Add relevant statement lines and explain adjustments in the record.
4. Select **Compute ledger balance**. Compare the calculated ledger and expected bank balances with the statement; investigate **Difference**.
5. Correct missing or duplicate entries and review outstanding items. Select **Sign off reconciliation** only when the difference is zero and the evidence agrees. Confirm the status becomes **Reconciled**.

> **Manual reconciliation:** This screen uses the statement and evidence you provide. It does not automatically connect to your bank. A zero difference must also be supported by the right journal, dates, and documents.

---

# Reports you can use

**Who:** Accountant, Administrator, or Read-only user with report access.

### Export a financial statement

1. Open **TCSI Accounting › Financial statements**.
2. Select **Report Type** and confirm **Company**.
3. Set **Date From** and **Date To**. Keep **Include entries** on **Posted entries only** for finalized accounting records. **All entries** also includes drafts.
4. Review **Layout status**, then select **Export PDF**. Open the downloaded file and check company context, dates, totals, and any trial/draft notice before sharing.

| Report | What it answers |
| --- | --- |
| Balance sheet | What does the business own and owe, and what is its equity? |
| Profit and loss | What income and expenses are recorded for the selected period? |
| Cash movement | What movements are recorded in cash and bank accounts for the period? |

### Detailed accounting reports

Open **Revenue › Reports › Reporting library**, choose the report, set its company and dates, and review its filters. Use the report's PDF/export action to download the result.

| Report | Use it for |
| --- | --- |
| Trial Balance | Compare account balances and total debits with total credits. |
| General Ledger / Journal Ledger | Inspect the entries behind an account or journal balance. |
| Open Items | Review amounts that remain unsettled. |
| Aged Partner Balance | Review outstanding customer or supplier balances by age. |
| VAT Report | Review tax-related accounting figures with your Accountant. |

### Read the overview correctly

**Receivables** are open customer balances; **Payables** are open supplier balances. **Cash position** comes from posted cash-account balances. **Net result** compares posted income with expenses. These figures do not replace a bank statement. Select **Refresh dashboard** after recent changes.

> **Before relying on a report:** Use the right company, reporting dates, and posted-entry filter. Trial/draft layout notices mean the output still needs the company's approval process. Tax working reports do not submit a tax return.

---

# Journals and period close

**Who:** Accountant or Administrator. Recurring schedules and period controls require careful review because they affect accounting records.

### Enter a manual journal

1. Open **Revenue › Ledger › Journal Entries › New**.
2. Choose the company, general journal, accounting date, and a clear reference. The date must fall inside an open accounting period.
3. Add **Journal Items** with an account, label, and debit or credit for each line. The total debits must equal total credits.
4. Save the draft and attach supporting calculations or documents. Review the entry, then select **Post**. Check its number and **Posted** status.

Use the approved **Reverse Entry** workflow to correct a posted journal. Keep the original and reversal; do not overwrite accounting history.

### Schedule repeat transactions

Open **TCSI Accounting › Controls › Recurring invoices and bills** or **Recurring journals**, then select **New**. Enter a name, company, journal, start date, next run, and interval. For invoices/bills, choose the document type and partner; for journals, enter balanced debit/credit lines.

**Review the full template before activating or running it.** Successful runs create and post transactions. **Run now** executes a run; **Run due periods** catches up due dates and can create several transactions. Check **Generated documents** or **Generated entries**, the last run, and the next run afterward. Do not treat these buttons as a preview.

### Finish an accounting period

1. Reconcile bank/cash balances and review unpaid customer and supplier items. Check recurring results and investigate unresolved differences.
2. Review every remaining draft in the period. Resolve each one through your team's approved process; drafts can prevent period closure.
3. Export the required reports and obtain the Accountant's sign-off.
4. Ask the Administrator to open **Controls › Accounting periods**, select the intended period, check its exact start/end dates, and select **Close**. Confirm **Closed**.

> **Check the date range:** Closing an annual period locks that entire range, not just one month. Closed dates block posting. An approved exception requires an Administrator to use **Reopen** and record the reason.

**Year-end:** **Controls › Year-end retained earnings** is an Accountant-led closing task. Confirm the year, retained-earnings account, journal, and approved final balances before creating a closing entry.

---

# Administrator essentials

Your Administrator manages the company's employee logins and restricted approvals. Each employee receives only the role and company access they need.

### Create an employee account

1. Open **TCSI Accounting › Organization › New Employee Account**.
2. Enter **Full name**, **Login email**, password, and the appropriate role. Check the spelling of the login before creating it.
3. Select **Create Account**. Give the employee the sign-in URL and credentials privately; the hosted trial does not send account emails.
4. Have the employee sign in and confirm the correct company and available menus. An Encoder should prepare drafts; an Accountant should finalize them.

### Reset or disable access

Open **Organization › Employee Accounts**. Find the employee by name or login. Use **Reset Password**, enter the replacement, and select **Set Password**. Share the replacement privately.

Use **Enable/Disable** to change an employee's active status. Check the current status first: the same action can enable or disable. Confirm the result. Ask the system owner for role changes or access issues the available form does not support.

### Controls your Accountant maintains

| Control | What needs to be reviewed |
| --- | --- |
| Accounting periods | Correct date ranges and open/closed status. |
| Tax profiles | Company-approved tax mappings, effective dates, and owner. |
| Report samples | The actual approved client layouts and their revisions. |
| Company configuration | Legal details, accounts, journals, document settings, and authorized owners. |

A trial baseline supplies initial configuration. The Accountant must still confirm it fits the actual business before operational use. Changing trial status alone does not approve tax treatment or document layouts.

### Opening balances and old records

**Migration batches** tracks source-to-target references, validation totals, and reconciliation sign-off. It is an Accountant-led cutover control, not a one-click import of arbitrary files. Agree the source export and mappings first; load through the agreed migration process, validate counts and balances, then sign off. Staff should not recreate old balances as ordinary invoices just to populate the system.

The platform owner's organization and trial-management console is separate from day-to-day employee work.

---

# ORVEXA and key terms

### Ask ORVEXA

Select **Ask ORVEXA** in the top bar or open its floating assistant. It supports specific accounting commands within your current company and permissions.

| Type this | What it does |
| --- | --- |
| show overdue invoices | Lists posted customer invoices that are past due and still have an unpaid balance. |
| find "customer or reference" | Searches invoice/customer text. Replace the quoted words with your search. |
| show recent activity | Shows authorized accounting activity and your task history. |

To prepare a draft, use this format with existing, unique customer and product names:

`draft invoice for "Customer" with 2 x "Product" at 100`

Replace the quoted names, quantity, and unit price. Review the proposed company, customer, product, amounts, and tax treatment. Confirm only if correct, or cancel the proposal. Open the resulting draft and complete the normal invoice review on page 3.

**ORVEXA does not post, send, pay, or delete records.** It is a limited command assistant. For unsupported requests, use the relevant accounting screen or ask your Accountant.

### Words used throughout the workspace

| Term | Plain meaning |
| --- | --- |
| Company | The legal business whose books you are viewing. |
| Draft / Posted | Draft is work awaiting finalization. Posted is recorded in the ledger. |
| Invoice / Bill | Invoice: a customer owes you. Bill: you owe a supplier. |
| Amount due | The part of an invoice or bill that remains unsettled. |
| Credit note / Reversal | A linked correction to a previously posted transaction. |
| Journal / Account | Journal groups transactions; account classifies their financial effect. |
| Reconciliation | Checking that recorded amounts agree with payments, statements, or other evidence. |
| Accounting period | A date range that can be open for posting or closed. |

---

# When something needs fixing

Use the exact message shown on screen. First check your company, role, document status, and dates.

| What you see | What to do |
| --- | --- |
| Cannot sign in | Check the assigned login and password. Ask your company Administrator to check account status or reset access. |
| Wrong company or missing menu | Ask the Administrator to check your role and company access. Some menus are intentionally role-restricted. |
| Cannot find a record | Check the company, list search, and active filters. Clear filters and search by its document number or partner. |
| Cannot Confirm or Post | Check role, open period, journal, required fields, account/tax choices, and balanced journal lines. Ask an Accountant to review the message. |
| Missing account or journal | Company setup needs attention. Ask the Administrator and Accountant to complete or correct it. |
| Payment still shows a balance | Compare the amount recorded with the amount due. Check allocation and bank clearing before entering another payment. |
| Batch is Pending approval | Ask the designated Administrator to approve; then the Accountant can post the batch. |
| Reconciliation will not sign off | Check dates, journal, statement attachment, outstanding items, and Difference. Resolve the mismatch. |
| PDF is blocked or marked trial/draft | Check company document approvals and report layout status. Trial labels are expected in trial mode. |
| PDF did not appear | Check browser downloads and blocked-download notices. Reopen the report with the correct dates and filters. |
| The page is out of date | Save your work, then use Refresh. If saving fails, record the message before leaving the page. |
| An action times out | Reopen the record and inspect its status/history before repeating a posting or payment. It may already have completed. |

### Ask for help with enough detail

Send your company Administrator or designated TCSI contact the company name, document number, page, time, exact error, and steps taken. Include a screenshot when useful. Never include a password.

### A reliable daily routine

Check the company. Enter accurate drafts. Review before posting. Record each payment once. Keep supporting evidence. Reconcile balances. Check report dates and status before sharing.
