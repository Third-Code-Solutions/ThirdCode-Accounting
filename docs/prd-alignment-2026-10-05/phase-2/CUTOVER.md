# Residual cutover policy and operator procedure

`residual_cutover_v1` loads one opening snapshot into an empty company ledger. It combines source trial balance, remaining AR/AP items and undeposited receipts without counting the same balance twice. It requires the explicit retention choice **Open items only; older history archived**. A client requiring live historical accounting must approve a different complete migration plan; this importer must not be used to imply that historical transactions have been posted.

The original file, its SHA-256, approved mapping, cutover date and named opening-balance owner remain client inputs. All supplied evidence here is synthetic. A successful technical comparison leaves the batch **Loaded**, not signed off.

## Accounting treatment

| Input | Posted treatment |
|---|---|
| Unpaid customer/supplier invoice or credit | Remaining amount only, on native partner AR/AP lines with original reference, original document date and due date; opposite side is dedicated opening equity clearing. No historical revenue, expenses or taxes are re-created. |
| Receipt already allocated in MYOB | Debit undeposited cash; credit opening clearing. Retain original allocation reference. Do not credit AR again. |
| Unallocated customer receipt | Debit undeposited cash; credit customer AR. It remains available for native later allocation. |
| Residual opening | Source TB minus the above components, account by account. All AR/AP controls and undeposited account totals must already match their detail. Opening clearing must end at zero. |
| Historical transactions | Balanced, dated, immutable, queryable source archive rows linked to the retained original file. They create no journal entries and do not populate historical financial statements. |

The native synthetic proof uses source balances: assets100, AR50, undeposited50, AP−30 and equity−170. The open customer item is60, the open supplier item30, an already-allocated receipt40 and an unallocated receipt10. Five posted components reproduce every source account; clearing is0. Allocating the remaining receipt reduces the customer item60→50; later depositing50 clears undeposited cash without changing AR.

## Mapping package

Prepare UTF-8 JSON with this structure. IDs are **mapped records in the selected company**, not source MYOB IDs. Decimal amounts should be strings. Keep source identifiers unique and retain mapping review evidence outside the JSON as well.

```json
{
  "policy": "residual_cutover_v1",
  "journal_id": 10,
  "clearing_account_id": 399,
  "trial_balance": [
    {"account_id": 110, "debit": "60.00", "credit": "0.00"},
    {"account_id": 300, "debit": "0.00", "credit": "60.00"}
  ],
  "open_items": [
    {"source_id": "MYOB-INV-123", "reference": "INV-123", "account_id": 110,
     "partner_id": 25, "move_type": "out_invoice", "residual": "60.00",
     "document_date": "2024-12-01", "due_date": "2025-01-15"}
  ],
  "undeposited_receipts": []
}
```

Supported item types: `out_invoice`, `out_refund`, `in_invoice`, `in_refund`. Each receipt requires `source_id`, `cash_account_id`, `partner_id`, positive `amount`, `document_date` and `disposition`. `already_allocated` also requires `source_allocation_reference`; `unallocated` requires `receivable_account_id`. Populated `history` in this posting package is rejected. Empty/zero-only packages, duplicate identifiers, wrong companies, excessive decimal precision, control differences and existing draft/posted books are rejected.

1. In the isolated client rehearsal, configure the reviewed chart, partners, general journal, dedicated equity clearing account and retention choice. Reconcile the authorized source extraction before mapping it.
2. Create a draft Migration Batch. Record source hash, cutover date and opening-balance owner; upload the unchanged original file and mapping JSON.
3. Select **Check mapping package**. Review the displayed per-account expected balances. This is technical validation, not accountant approval.
4. After the real mapping is approved and the production release/import gates are satisfied, an Administrator may select **Apply cutover snapshot**. The server locks company period state, rejects existing books, posts every component in one transaction and compares all account balances. An error rolls back the RPC transaction.
5. A lost response can be retried on the same batch. The same fingerprint returns the existing move IDs; changed content is rejected. Do not catch an internal ORM exception and commit the cursor; callers must preserve the normal RPC rollback boundary.
6. Review the retained source and reconciliation rows, native partner residuals and opening reports. Record client sign-off separately, then complete the full parallel month.

`scripts/cutover_load.py --batch-id ID --company-id ID` previews an existing batch without posting. `--apply` invokes the same native action. Connection credentials are supplied through `ODOO_URL`, `ODOO_DB`, `ODOO_LOGIN`, `ODOO_PASSWORD`; do not include them in evidence. `--archive-history path.json --apply` adds the non-posting archive after the snapshot. History rows require `source_entry_id`, `source_line_id`, `date`, `account_code`, `debit`, `credit`, with optional partner reference/description. Every supplied entry must balance and have one date at/before cutover. Identical retry is harmless; changed or additional lines for an existing entry are rejected.

The legacy CSV loader remains a separate single-basis workflow and still rejects overlapping populated inputs. Use this explicit residual policy for combined snapshot/open-item/receipt cutover; never run both loaders against the same economic opening.

## Evidence and remaining acceptance

Native tests cover retained-source integrity, retry, injected interruption after the second component, full rollback/retry, overlapping history, mismatched control accounts, incompatible retention, later allocation/deposit and immutable archive history. `evidence/cutover-fixture.txt` records the five-entry synthetic load; `archive-retrieval.txt` proves the original bytes and two historical rows were retrieved after restore.

Real MYOB extraction, mapping approval, retention scope, cutover date, named client finance owner, line-by-line real TB comparison and the full parallel accounting month remain outstanding. No source file was supplied or imported into customer books.
