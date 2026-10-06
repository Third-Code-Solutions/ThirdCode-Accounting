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

## Verification

Independent security and native-mail reviews completed with no remaining source blockers. Final candidate `7f9829ce629fc99266c81c1de44dec6f2719d734` passed [CI37394563884](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/actions/runs/37394563884): 161 native tests and 59 integration checks, zero failures/errors; hosted HTTP, coordinated-recovery and web quality gates also passed. The integration checks overlap native test coverage and are not 59 additional unique business cases.

Tests cover two-company search/read/export/dropdown denial, identity changes, sharing/revocation, forged defaults, bank references, owner/multi-company access, shared-contact invoice/bill posting, refunds and reconciliation. Native mail tests cover Store responses, recipient WebSocket payloads, raw metadata reads and real nested exports. Nested `web_read` expansion of a foreign contact correctly raises `AccessError`; permitted message body reads remain available.

Fresh encrypted database/filestore capture completed before deployment (77,404,734 bytes; 1,320 manifest files). Current fresh capture has not been verified off-host. Initial 14.0-to-14.1 upgrade and final runtime re-upgrade both passed in an existing neutralized restored database. Conservation evidence covers only eight listed table projections, excluding partner/company write timestamps, added fields, other tables and filestore. See `isolated-upgrade.json`.

[PR18](https://github.com/Third-Code-Solutions/ThirdCode-Accounting/pull/18) merged as `772208cb9eb6c525f7a0a98b37840e1f4719f102` at 2026-10-06 00:39:45 UTC. Railway deployment `3e081eb8-4417-4fc5-94cd-17a1c2e03770` is active. Production API confirms addon `18.0.2.14.1`. Container digest: `sha256:9459d08d1ff181cf787dac2578d2e6948260f097cbfe1a15e3a7ebd5ecdf76a3`.


## Live verification, 2026-10-06

Read-only production checks at 00:43 UTC passed:

| Account scope | Contacts before | Contacts after | Own contact reads | Foreign direct reads denied | Foreign dropdown matches |
| --- | ---: | ---: | ---: | ---: | ---: |
| Company 4 accountant | 70 | 9 | 3 | 5 | 0 |
| Company 5 accountant | 69 | 7 | 2 | 6 | 0 |

Every visible contact had explicit ownership, identity membership or an approved grant for the requesting company. Both accounts had zero visible partner-bank records; live bank isolation is therefore an empty-set check, with positive/negative bank behavior covered by native regression tests.

Platform owner could retrieve all 87 active/archived contacts. All 71 active contacts captured by the pre-deployment API snapshot remain present with unchanged company and parent links. The broader 87-contact preservation check belongs to the isolated upgrade rehearsal, not this 71-record live comparison. Historical company-less business contacts 89 and 90 have grants only for company 1. No ownership reassignment or record deletion was performed.

Native browser verification as the company 4 accountant confirmed Directory shows 9 contacts, comprising its own identities and customer records. The unsaved invoice customer and bill vendor selectors returned no existing match for `Trial Client 02`, while all three own `Trial E2E Customer` entries remained searchable. Both unsaved forms were discarded. No invoice or bill was saved or posted during production verification. Evidence payload: `live-verification.json`. Screenshots remain private under `/Users/hoon/tcsi-private/` (`contact-directory-before.png`, `contact-directory-after.png`, `contact-customer-foreign-search.png`, `contact-customer-own-search.png`, `contact-vendor-foreign-search.png`).

Accounting posting, reversal and reconciliation were exercised in isolated automated tests, not by creating financial transactions in production. Security review and CI establish the tested boundaries; they are not a claim that every possible attack or accounting workflow has been tested.
