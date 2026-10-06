# Company contact isolation

## Root cause

The native global contact rule admitted every contact without a company and every internal-user identity. TCSI's previous user rule applied only to selected business-role groups. Directory, relational searches and generic ORM APIs therefore inherited a cross-company visibility exception. Native mail also deliberately serializes personas with elevated access, so tightening contact search domains alone is insufficient.

## Server changes

- Replace the native global partner/bank rules with active, authorized company scope. Apply delegated user isolation globally.
- Store explicit identity scope from existing user-company memberships and company identity links; exclude platform owners from tenant identity scope.
- Preserve full platform-owner access and authorized multi-company selection. Scope an accounting reference to its document company, not every selected company.
- Default tenant-created contacts to their active company. Guard ownership changes, parent/child links, bank reassignment, context/default values and the native elevated `is_company` write path.
- Make existing shared business contacts read-only to tenants unless explicitly company-owned. Only platform owners can grant sharing.
- Scope native mail contact serialization and member responses. Filter shared broadcast Store payloads at the receiving session; retain message rows and notification IDs.

## Existing shared contacts

Read-only production review found 87 contacts, including 69 without company ownership: 67 explicit user/company identities and two business contacts referenced by company 1 accounting documents. No ambiguous unassigned business contacts were found in this snapshot.

The one-time migration adds read grants from existing invoice, journal line and payment references, including parent ancestors. It does not assign ownership, share siblings, delete contacts or infer ownership from names/email addresses. Re-running an upgrade does not restore revoked grants or grant access from later documents.

## Verification status

Implementation and independent review are in progress. Two-company ORM tests cover search, direct read, export, dropdowns, identity changes, bank records, owner access, sharing revocation, forged defaults and accounting reference boundaries. Accounting regressions include shared-vendor bills/invoices, refunds, reconciliation and company bank selection. Hosted HTTP tests provision disposable organizations and exercise native RPC isolation.

Fresh encrypted database/filestore capture completed before deployment. An isolated upgrade will compare the original eight selected accounting/contact/company table projections; this is a limited conservation check, not a claim that every database table or filestore byte is unchanged. Current fresh capture has not been verified off-host.

Production deployment and live verification are not yet complete. Final revision, CI results and live counts will be recorded here after they are observed.
