# TCSI interface coverage inventory

Every user-facing surface in this repository, its rendering owner, and the
evidence behind its presentation status. Kept next to the redesign so a route
is never assumed covered because a shared stylesheet changed.

Status values:

- **rendered** — exercised in a real browser with the production CSS bundle.
- **source-verified** — presentation is defined by a shared layer that compiles
  and is asserted by tests, but the authenticated screen was not exercised.
- **blocked** — needs credentials, data, or an environment this session cannot
  reach. Never reported as verified.

## 1. Public portal — `apps/web` (Next.js App Router)

Rendering owner: the React route/component below. Presentation owner:
`apps/web/app/globals.css` (TCSI tokens + component patterns).

| Route | Rendered by | Type | Audience | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| `/` | `components/landing-page.tsx` | marketing landing | public | rendered | sweep 1440/834/390, light+dark |
| `/platform` | `components/marketing-layout.tsx` | marketing detail | public | rendered | sweep 1440/834/390, light+dark |
| `/controls` | `components/marketing-layout.tsx` | marketing detail | public | rendered | sweep 1440/834/390, light+dark |
| `/pilot` | `components/marketing-layout.tsx` | marketing detail | public | rendered | sweep 1440/834/390, light+dark |
| `/contact` | `components/demo-request-form.tsx` | public form | public | rendered | sweep; honeypot clip is intentional (`aria-hidden`, `tabIndex=-1`) |
| `/login` | `components/login-form.tsx` | authentication | public | rendered | sweep; `auth-visual` clip is the decorative pseudo-element |
| `/owner` | `components/platform-owner-view.tsx` | platform console | platform owner (Supabase-bound) | rendered (signed-out state) | sweep; signed-in state needs a bound owner account |
| `/dashboard` | `components/dashboard-view.tsx` + `app-shell.tsx` | workspace shell | signed-in member | rendered | sweep; reference screen for the token set |
| `/transactions` | `components/section-page.tsx` | workspace shell | signed-in member | rendered | sweep |
| `/invoices` | `components/section-page.tsx` | workspace shell | signed-in member | rendered | sweep |
| `/customers` | `components/section-page.tsx` | workspace shell | signed-in member | rendered | sweep |
| `/reports` | `components/section-page.tsx` | workspace shell | signed-in member | rendered | sweep |
| `/settings` | `components/section-page.tsx` | workspace shell | signed-in member | rendered | sweep |
| `loading.tsx` / `error.tsx` / `not-found.tsx` | app router boundaries | loading / error / 404 | any | rendered (404), source-verified (loading, error) | sweep of an unknown route |

Portal mode (`TCSI_PORTAL_ONLY=true`, the deployed configuration) redirects the
workspace routes to `/`; the redesign keeps them correct for the standalone
release without presenting them as shipped.

### Non-page endpoints (classified separately, no presentation to redesign)

`/api/health`, `/api/readiness`, `/api/dashboard`, `/api/demo-requests`,
`/api/platform/analytics`, `/api/workspaces`, `/auth/confirm`, `/websocket`,
`/icon.svg`. Assets and JSON only.

## 2. Hosted workspace — `addons/thirdcode_accounting` (Odoo 18)

Rendering owner: the Odoo web client (`/workspace/...`). Presentation owner:
`tcsi_tokens.scss` (canonical values) → `tcsi_brand.scss` (shell, sign-in,
Discuss), `tcsi_routes.scss` (native views, dialogs, report renderers),
`tcsi_dashboard.scss` (finance overview), `tcsi_apps.scss`, `tcsi_chat.scss`,
`orvexa.scss`, `tcsi_console.scss`, `tcsi_dark.scss` (dark mode),
`tcsi_portal.scss` (public portal, `web.assets_frontend`).

### Menus, client actions and windows

| Surface | Action | View type | Roles | Status |
| --- | --- | --- | --- | --- |
| Finance overview | `action_tcsi_dashboard` (client `tcsi_dashboard`) | Owl client action | all TCSI groups | source-verified (design reference) |
| Workspace apps catalog | `action_tcsi_apps` (client `tcsi_apps`) | Owl client action | internal users | source-verified |
| Platform console | `action_thirdcode_platform_console` (client) | Owl client action | platform owner only | source-verified |
| Accounting periods | `action_thirdcode_accounting_period` | list, form | all TCSI groups | source-verified |
| Recurring journals | `action_thirdcode_recurring_journal` | list, form | accountant, administrator | source-verified |
| Recurring invoices and bills | `action_thirdcode_recurring_invoice` | list, form | accountant, administrator | source-verified |
| Tax profiles | `action_thirdcode_tax_profile` | list, form | accountant, administrator | source-verified |
| Client report samples | `action_thirdcode_report_sample` | list, form | accountant, administrator | source-verified |
| Year-end retained earnings | `action_thirdcode_year_end_close` | list, form | accountant, administrator | source-verified |
| Payment batches | `action_thirdcode_payment_batch` | list, form | all TCSI groups | source-verified |
| Bank reconciliations | `action_thirdcode_bank_reconciliation` | list, form | all TCSI groups | source-verified |
| Financial statements | `action_thirdcode_financial_report` | form wizard → report | read-only, accountant, administrator | source-verified |
| Migration batches | `action_thirdcode_migration_batch` | list, form | accountant, administrator | source-verified |
| Employee Accounts | `action_thirdcode_employee_list` | list (`res.users`) | administrator | source-verified |
| New Employee Account | `action_thirdcode_employee_wizard` | form wizard | administrator | source-verified |
| Reset Password | `action_thirdcode_password_reset` | form wizard | administrator | source-verified |
| Revenue (native `account`), Directory (Contacts), Messages (Discuss), People (HR), Spend (expenses), Settings, Apps, Insights | renamed native menus | list, kanban, form, calendar, pivot, graph, activity, settings | by group | source-verified |

### Native Odoo view templates exercised by the shared layer

Invoice/bill/credit-note/refund and journal-entry forms (statusbar, notebook,
x2many tables, chatter, attachments), journal forms, payment forms and payment
register, list views with numeric alignment, kanban (including the accounting
dashboard kanban), calendar, pivot, graph, activity, hierarchy, OCA bank
reconciliation, base settings (tabs and app blocks), audit log and date ranges,
report/PDF renderers.

### Overlays

Dialogs and wizards (`.modal-content`, report wizard, employee and password
wizards), dropdowns (`.dropdown-menu`, `.o-dropdown--menu`), popovers, date
pickers, autocomplete dropdowns, search panel, notebook tabs, settings tabs
(fixed-height scroll container on mobile), chatter composer and follow button
(overlay label inside a button), toasts (`.o_notification`), confirmation
dialogs, kanban quick-create, list inline editing, and the theme toggle.

### Routes, controllers and endpoints

`/workspace` and `/workspace/<path>` (web client), `/dashboards` and
`/workspace/dashboards` (redirects to the finance overview), `/action-307`,
`/action-425`, `/web/login`, `/web/reset_password`, `/web/signup`,
`/thirdcode_accounting/dashboard` (JSON), `/thirdcode_accounting/orvexa`
(JSON), `/tcsi/setup` (token-gated provisioning), the web manifest,
`/report/*` PDF downloads, and the customer portal routes (`/my/*`,
`/portal/*`, invoice and payment pages). Report and PDF layouts are excluded
from presentation changes by contract; JSON, manifest and download endpoints
carry no presentation.

## 3. Verification status of the hosted workspace

Rendered verification of authenticated workspace screens is **blocked** in this
session: no stored login exists for the engine origin, the vault prompt was
declined, and Docker is unavailable locally, so no local Odoo could be started.
The sign-in screen and its frontend bundle were verified rendered (computed
styles, both themes, three widths). Everything else in section 2 is
source-verified: the stylesheets compile with the libsass runtime Odoo uses,
the manifest resources validate, and the token parity test asserts the shared
palette. That is not the same as exercising the screens, and this document does
not claim it is.

To close the gap: sign in once in the handover Chrome window (CDP :9222), then
re-run the sweep against `/workspace/...` for each row above.
