# Production alignment — 5 October 2026

This is the current continuation of the historical phase-1/phase-2 reports. It distinguishes deployed behavior, isolated regression evidence, and client acceptance. The [92-row requirements matrix](requirements.csv) retains every numbered requirement, objective, role, standard report and scope/discovery item. No overall completion percentage or production acceptance is claimed.

## Inspected baseline

PRs [#6](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/pull/6) and [#7](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/pull/7) merged into main `7a1bc57a680ba69cc993205f0e131a8f9fbec3f7`. Railway deployment `26fc1bc7-a18b-4b80-8f0b-7864da4cccf9` serves installed module `18.0.2.13.0`; Vercel production deployment `dpl_GRJmhifKS1XS7xBMWDtsnGfAmn4H` is READY at that revision. Portal readiness confirms the existing Supabase authentication and accounting-engine connections. PostgreSQL is 18.6; the application role has no superuser or database-creation privileges. The engine uses one replica and a persistent filestore.

The owner API inspected 11 allowed companies. A separate authorized demo administrator was used for the demo company; its access was not added to the owner's allowed-company list. All 48 inspected business accounts (four roles in each of 12 companies) authenticated, had exactly one company, and saw no foreign journal entries or periods. Six read/create/write ACL checks matched their intended roles. Those read-only checks are not proof of every supported workflow action; the isolated action matrix supplies separate evidence.

Eleven trial readiness checks pass structurally. They explicitly defer legal identity and client approval. The live inventory found no custom journal sequence regexes and no preassigned numbered drafts within the owner's 11-company scope. All 43 installed audit rules are subscribed. The recurring journal/invoice cron is active daily; its last inspected call was `2026-10-04 09:13:23 UTC`.

## Candidate 18.0.2.13.1

[PR #8](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/pull/8) contains these focused changes:

- Route normal HTTP and evented WebSocket traffic to their correct Odoo workers behind one supervised public listener. The live baseline returned HTTP500 for WebSocket upgrades. Either essential process failing stops its peer so Railway can restart the complete runtime.
- Preserve HTTP error status/body/protocol headers while applying existing security headers to Werkzeug exception responses.
- Make trial-balance source links retain the report's company, journal, partner, account, posted-state and date filters, including fiscal-year opening balances and carried earnings. Native rendered-link tests compare every displayed amount with the ledger lines selected by its actual domain.
- Recheck role and active-company scope at HTML/PDF/XLSX export time through the actual OCA export base, statement export and direct report-rendering entry points. A sibling mixin alone did not intercept native inherited methods.
- Hide reset/cancel controls on previously posted documents, matching the existing reversal-only server policy.
- Reject encoder reconciliation and settlement removal, including direct partial/full reconciliation operations reached through native sudo paths. Encoders remain draft-only; legitimate accountant and administrator reconciliation continues.

The expanded native role matrix covers draft creation/editing, posting, posted immutability, reversal, reconciliation/removal, report export, audit evidence, period close/reopen and employee administration. Fresh CI and the representative-copy upgrade are release gates. Candidate status is not yet a deployment claim.

## Live reports and accounting evidence

Twenty-five real PDFs rendered through authenticated production report actions: trial balance, general ledger, journal listing, customer/supplier ageing, customer/supplier unpaid balances, balance sheet, profit and loss, cash flow, VAT and withholding, each in two companies, plus a Statement of Account for an existing company-1 partner. Maximum observed end-to-end time was 9.413 seconds. This is the current small dataset, not agreed representative annual volume. Report wizards were transient; no synthetic accounting documents were posted and no customer balances were changed. PDFs contain private financial data and remain outside public Git.

Historical isolated evidence remains in [phase-2/REPORT.md](phase-2/REPORT.md): SOA opening/activity/running/ageing/closing values, comparative statements, classified cash-flow reconciliation, tax/refund signs, bank adjustment/reversal/rematch, settlement and cutover/archive invariants. These calculations use explicitly synthetic data. Client tax classifications, cash scope, statutory presentation and print formats remain provisional.

## Recovery and upgrade evidence

The first production-representative backup restored into a separate database and filestore in 70.406 seconds and upgraded to 13.0 in 43.142 seconds. Original posted documents, journal lines, per-company/account totals, audit actors/timestamps/old/new values, company scope and referenced attachment bytes matched. Production verification after that release preserved the same fingerprint.

A fresh coordinated encrypted bundle was captured at `2026-10-04T23:54:28Z` before 13.1. All accounting writers were paused for 3.163 seconds and resumed. The 19,155,566-byte encrypted bundle was downloaded outside Railway, decrypted successfully using a private key that never left the local machine, and all 1,283 archived hashes matched. It includes the database, matching filestore, addons, runtime/configuration and required recovery environment. Its SHA-256 is `3818b3a639288ea43c2d0e11be7b660210ebf73dbdc96201b65147364a2547db`. Secrets and raw evidence remain in private storage, never in this repository.

The new isolated target `tcsi_release_20261005b` restored in 69.049 seconds and upgraded to `18.0.2.13.1` in 28.184 seconds; the expanded report-access candidate was rehearsed again in 35.605 seconds. All 53 posted documents, 111 lines, 25 account/company groups, 635 original audit rows and 13,061 details, 837 business attachment records and 482 referenced attachment files matched. It has its own filestore and runs with HTTP, cron and outgoing mail disabled. The copy upgrade uses the candidate addon and the inspected production Odoo/OCA/PostgreSQL environment. The new nginx runtime is tested separately in the pinned CI image; it is not installed into the currently running production container for rehearsal.

Railway's two separate daily volume snapshots, with roughly six days of retention, are not a coordinated recovery bundle. The verified manual off-host bundle does not establish nightly remote delivery, failure alerts or an agreed RPO/RTO. See [HOSTED-OPERATIONS.md](HOSTED-OPERATIONS.md). After customers resume writing, preserve new transactions and prefer a forward correction; never blindly restore an older backup over current books.

## Acceptance and remaining owners

| Criterion | Current technical evidence | Required external outcome |
|---|---|---|
| AC-01 SOA | Native opening, running, closing and ageing calculations/PDF pass on synthetic data. | Client-approved sample and real customer-ledger comparison. |
| AC-02 Financial statements | Native comparative/cash reconciliation tests; live PDFs render. | Client chart/cash classifications, report format and representative TB approval. |
| AC-03 Monthly reconciliation | Standard bank summary and match/reversal exist. | RP-04 columns/calculations/grouping and approved sample; then implement exact custom output. |
| AC-04 Official Receipt | Native required-field, numbering and print guards exist. | Actual tax/control/signature values, stock and print approval. |
| AC-05 Migration | Native overlap, interruption/retry, residual cutover, control-account and retained archive tests pass. | Authorized MYOB extraction, approved mapping/retention/date, named finance owner and real line-by-line TB comparison. |
| AC-06 Parallel month | No shortened substitute claimed. | One complete real accounting month and reconciliation. |
| AC-07 Audit | Expanded immutable audit coverage, live subscriptions and production-copy preservation verified. | Client examination, long-term retention policy and operational access ownership. |
| AC-08 Roles | Live memberships/company isolation verified; expanded native matrix exposed and now guards encoder settlement. | Final candidate regression/deployed checks, client workflow examination and Windows Chrome/Edge. |
| AC-09 Recovery | Coordinated off-host bundle verified; production-copy restore and 13.1 upgrade pass. | Agree recovery objectives/operator/deputy and demonstrate client handover; the13.1 rehearsal now passes. |

The developer/product owner is the user. Client finance/accounting owners are not yet named. Pending questions ask for RP-04's exact definition and typical annual volume, plus the separate recovery destination and backup-failure alert recipient. No response or approval is inferred from elapsed time. Each client must also supply legal/tax/control values, CAS materials, EIS applicability decision, migration source/mapping and format approvals. Two-user historical timing met the proposed target; the ten-user run missed it. Representative hosted load validation and Windows testing remain engineering acceptance work, not a fabricated pass.
