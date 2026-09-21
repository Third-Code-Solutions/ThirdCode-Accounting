# CAS control pack — implementation template

This document is a technical control-pack template for the proposed Odoo
Community installation. It is not a BIR certificate, legal opinion, or client
acceptance record. Fields marked `BLOCKED — CLIENT DECISION` require the named
owner and evidence before production use.

## 1. System boundary and ledger authority

| Control | Current implementation | Acceptance owner / evidence |
| --- | --- | --- |
| Ledger authority | Odoo Community `account.move` and native accounting reports | **BLOCKED — CLIENT DECISION:** accountant sign-off |
| Company/site scope | One company, one site, one currency in the local proof | **BLOCKED — CLIENT DECISION:** confirm scope and currency |
| External integrations | None enabled; no EIS/bank feed/MYOB live connector | **BLOCKED — CLIENT DECISION:** integration classification |
| Application version | Odoo 18.0 image digest plus pinned OCA commits | Implementation manifest and deployment record |
| Database | PostgreSQL 16 Alpine image digest | Infrastructure owner / production host record |

## 2. Users, authorization, and posting

| Control | Current implementation | Evidence / pending item |
| --- | --- | --- |
| Administrator | Custom application role mapped to Odoo account manager; not server superuser | Final role matrix and named-user list pending |
| Accountant | Native accounting user plus custom workflow rights | Final segregation-of-duties approval pending |
| Encoder | Draft document rights; server-side posting guard | Synthetic regression passed; client approval pending |
| Read-only | Native read-only group plus custom ACLs | Synthetic create/write/unlink probes passed |
| Posted move edits | Protected except controlled metadata/reversal paths | Full audit review and retention owner pending |
| Period close/reopen | Accountant/admin close; administrator-only reopen | Close calendar and exception owner pending |
| Payment approval | Optional threshold workflow in payment batch | Threshold and approver pending |

## 3. Numbering and official documents

| Control | Current implementation | Acceptance item |
| --- | --- | --- |
| Native document sequences | Odoo sequences remain the source of posted document names | Accountant verifies gap/void policy under failures and concurrency |
| Official receipts | No-gap local sequence, receipt metadata, amount words, TIN/VAT fields | BIR classification, control value, layout, signatory, and sample pending |
| Invoice report | Custom guarded template with visible draft marker and control field | Signed sample and accountant/legal review pending |
| Credit/debit corrections | Native credit/debit notes and reversals preserve source records | Client correction policy pending |

## 4. Audit and retention

- OCA `auditlog` is installed and an `account.move` rule is enabled in the
  local database.
- The custom model override blocks application writes and unlink operations on
  `auditlog.log`.
- The database backup includes audit records because they are normal database
  rows; restore verification must include an audit-row spot check.
- **BLOCKED — CLIENT DECISION:** statutory retention period, purge authority,
  legal hold procedure, audit review cadence, and restore/audit evidence owner.

## 5. Backup, restore, and archive

The operational scripts cover PostgreSQL custom-format dump, Odoo filestore,
read-only configuration, image metadata, manifest hashes, archive inspection,
and restore to a named disposable database. Before production:

- **BLOCKED — INFRASTRUCTURE OWNER:** second-device destination and access;
- **BLOCKED — INFRASTRUCTURE OWNER:** nightly schedule, RPO/RTO, retention;
- **BLOCKED — INFRASTRUCTURE OWNER:** restore test frequency and sign-off;
- **BLOCKED — CLIENT DECISION:** MYOB read-only archive location and retention.

## 6. Tax, reports, and regulatory data

- Tax profiles store VAT-registration state, native input/output tax mappings,
  withholding mappings, and an owner/basis note; no tax rate is invented.
- The company stores the BIR acknowledgement/control value, report sample
  revisions, EIS status, signatory, and retention configuration.
- Official-receipt rendering is blocked until the BIR control value exists.
- **BLOCKED — ACCOUNTANT/LEGAL:** VAT and withholding configuration, BIR books,
  official-document classification, EIS scope/transmission, and signed samples.

## 7. Migration and cutover controls

The migration package requires validated accounts, partners, taxes, open items,
transactions, and opening trial balance CSV files. It records deterministic
file hashes, source identifiers, duplicate-safe loads, balanced batches, and
reconciliation state. A real cutover must additionally record:

1. authorized MYOB export and mapping version;
2. source totals and line counts;
3. opening trial balance and subledger reconciliation;
4. live-history versus read-only archive decision;
5. parallel-month results and variance sign-off;
6. cutover backup, rollback window, and business owner approval.

All six real-world items are **BLOCKED — CLIENT DECISION / SOURCE ARTIFACT**.

## 8. Operational acceptance checklist

| Acceptance | Current state |
| --- | --- |
| AC-01 SOA | Local technical/report surface verified; client sample/sign-off pending |
| AC-02 financial statements | GL/TB and native surfaces verified; full signed set pending |
| AC-03 monthly reconciliation | Manual evidence workflow implemented; definition/owner pending |
| AC-04 official receipt | Guarded template and sequence verified; BIR/sample/signatory pending |
| AC-05 opening migration | Synthetic validation/load/idempotency verified; real MYOB data pending |
| AC-06 parallel month | Not tested; requires client data and users |
| AC-07 audit trail | Local immutability and audit rows verified; retention procedure pending |
| AC-08 roles | Provisional local role probes verified; client matrix pending |
| AC-09 backup/restore | Synthetic disposable restore verified; second-device production test pending |

Final CAS sign-off is **NOT STARTED / BLOCKED — CLIENT DECISION** until these
evidence fields are completed by the appropriate owners.
