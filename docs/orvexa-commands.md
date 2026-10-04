# ORVEXA commands (18.0.2.11.x)

ORVEXA is the deterministic assistant inside the TCSI workspace. It uses explicit
command rules only — no AI services, no language-model APIs, no probabilistic
interpretation. Every answer comes from live, permission-checked application data.

Open it from the ORVEXA button in the top bar of the workspace.

## Supported commands

| Command | Natural phrasing (kept working) | What it does |
| --- | --- | --- |
| `/help` | `help` | Lists every command with its parameters and an example, plus the runtime boundaries. |
| `/summary` | `read everything in my dashboard` | Reads the whole finance overview: cash, receivables, payables, net result, invoices, bills, payments, entries, periods, activity memory. Restricted sections are marked, never silently dropped. |
| `/overdue` | `show overdue invoices` | Lists up to 20 posted customer invoices past their due date. |
| `/find "Acme"` | `find "Acme"` | Searches customer invoices by customer name or document reference. |
| `/draft "Acme Corp" 2 x "Consulting" at 100` | `draft invoice for "Acme Corp" with 2 x "Consulting" at 100` | Prepares ONE draft-invoice preview with a confirmation step. Nothing is posted, sent or paid. |
| `/activity` | `show recent activity` | Recent authorized accounting activity plus your saved task proposals. |

### Validation rules

- Incomplete or unknown input returns a precise usage message and executes nothing.
  Missing customers, products, amounts, dates or companies are **never** inferred.
- `/find` requires the search phrase in double quotes; `/draft` requires the quoted
  customer, a quantity, the quoted product and a unit price.
- Customer, product and sales journal must resolve to exactly one existing record;
  ambiguous names are refused with the reason.
- Proposal confirmations re-check permissions, record versions and expiry, and are
  idempotent: retrying the same confirmation never creates a second invoice.
- Every response carries its status (`help`, `complete`, `confirmation_required`,
  `cancelled`, `invalid`, `error`), and data reads disclose their source, result
  limit and UTC snapshot time.

## Runtime boundaries

ORVEXA runs inside this deployment only. It cannot access the user's computer or
local files, cannot call external AI services, and cannot post, pay, send, delete
or execute anything outside its registered, audited actions.

## Verification (2026-10-05, live production)

- CI: `verify` + `orvexa-integration` jobs green for 18.0.2.11.0 and 18.0.2.11.1.
- Live RPC matrix 19/19: help registry, invalid/unknown validation, summary,
  overdue source/limit disclosure, activity memory, company isolation, role
  restrictions (encoder/read-only), encoder read parity on all control models.
- Live UI: `/help` renders the command list (6 entries) and boundaries block;
  encoder landing is the Finance overview; control pages open without Access
  Error for the encoder role.

## Remaining limitations

- Invoice search returns at most 20 rows per request; the response says when more
  matches exist.
- Draft-invoice creation needs exactly one sales journal configured; with several
  journals it directs the user to the invoice form.
- The assistant language is English; commands are matched exactly (case-insensitive).
