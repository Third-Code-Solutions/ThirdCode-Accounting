# Workspace UI design

The accounting workspace uses the existing sidebar's flat dashboard language:
white/gray surfaces, thin borders, violet actions, compact typography and
consistent spacing. Existing light and dark palette values are retained.

## Scope and ownership

`addons/thirdcode_accounting/static/src/scss/tcsi_routes.scss` is the shared
presentation layer for native Odoo workspace routes: forms, lists, kanban,
report renderers, reconciliation, settings, menus and dialogs. It replaces the
previous repeated route override blocks. It does not depend on the active
route being a form, so dialogs opened over lists receive the same styling.

The Next.js portal proxies these routes to Odoo; changing its React pages would
not update the screens shown in the redesign request. The existing sidebar,
finance overview and app catalog retain their dedicated components/styles.

- Form status actions occupy a separate toolbar above the document, with no
  negative sheet margins. Draft/posted states use rectangular status pills.
- Document surfaces use 24px padding, 24px headings, 12px labels and 36px inputs.
- Native many-to-one inputs and tag inputs have one border. Checkboxes retain
  native checked-state behavior and their compact size.
- Custom control forms use two equal section columns, stacking within narrow
  document containers. Inner Odoo groups still own field labels and modifiers.
- Invoice and journal source/opening-balance/schedule metadata is in the
  Document details tab; Document type remains beside the reference.
- Tables preserve numeric alignment and horizontal scrolling. Chatter takes
  360px only when Odoo places it beside a wide form; bottom chatter stays fluid.
- Financial-statement dialogs use content-driven height and full section width.
- Dark status selection, keyboard focus and reduced-motion styles are explicit.
- Breadcrumbs use 12px context and 16px record titles. Header updates preserve
  Owl-managed form fields and refresh when Odoo reuses a view controller.
- Notebook tables reset native negative margin variables, keeping the first
  account digits inside the document. Activity toolbar buttons wrap without
  altering the Follow button's native overlay label.

## Design tokens

`addons/thirdcode_accounting/static/src/scss/tcsi_tokens.scss` is the single
source of palette values for every TCSI surface. It is loaded first in both
`web.assets_backend` and `web.assets_frontend`, so a later layer can still
override a value deliberately. Light values come from the rendered finance
overview; dark values are the workspace dark theme.

| Token | Light | Dark |
| --- | --- | --- |
| `canvas` / `surface` / `surface-soft` / `surface-hover` | `#f7f7fa` / `#ffffff` / `#f8f8fb` / `#f3f2f8` | `#101720` / `#18222d` / `#1e2a36` / `#263442` |
| `ink` / `ink-muted` / `ink-soft` | `#151225` / `#6d6a7d` / `#9692a5` | `#edf2f8` / `#aab7c7` / `#91a3b5` |
| `line` / `line-strong` | `#e7e5ee` / `#d8d5e2` | `#344453` / `#485a6c` |
| `accent` / `accent-deep` / `accent-soft` | `#6944dc` / `#4d2daf` / `#f0ecff` | `#7353c4` / `#6343b3` / `#302947` |
| `positive` / `attention` / `danger` | `#20ad88` / `#d87542` / `#cc4e5b` | `#43d3ac` / `#e39a6a` / `#e2737f` |
| `radius-control` / `radius-surface` / `radius-panel` | `8px` / `11px` / `12px` | same |

`tcsi_routes.scss` consumes these tokens instead of local hex values, so the
workspace routes, the workspace dashboard and the public portal share one
palette. The portal (`apps/web/app/globals.css`) declares the same values under
`--tcsi-*` names and adds a `prefers-color-scheme: dark` theme built from the
dark column above, including the accent-as-text switch to `#bca6ff` that keeps
AA contrast on dark surfaces. `scripts/test-design-tokens.mjs` fails when the
two surfaces drift apart.

## Route coverage

Styling follows Odoo view types, not database-specific action numbers. All
routes rendered by a shared view receive the same design contract.

| Surface | Presentation owner |
| --- | --- |
| Invoices, credit notes, bills, refunds, journal entries/items, payments and journals | Shared forms, lists, statusbars, notebooks and dialogs in `tcsi_routes.scss` |
| Accounting periods, recurring entries/invoices, tax profiles, report samples, year-end close, batches, migrations and bank reconciliation controls | Shared styles plus sectioned XML forms |
| Companies, users, employees, contacts, departments, expenses and expense reports | Shared record forms, lists, kanban, hierarchy and search panels; company/user dialogs have sectioned XML |
| Financial statement and OCA report wizards | Shared modal forms, compact sections and report controls |
| OCA reconciliation, pivot, graph, calendar and activity views | Specialized renderer rules in `tcsi_routes.scss` |
| General/accounting settings, audit logs and date ranges | Settings tabs/sections plus shared native forms and lists |
| Finance overview, Insights and application catalog | `tcsi_dashboard.scss`, `tcsi_apps.scss` |
| Messages, chatter and ORVEXA | `tcsi_chat.scss`, `orvexa.scss`, shared chatter rules |
| Sign-in, signup and password recovery | Existing branded authentication templates plus shared form styles |
| Customer portal, invoices, profile, payment and payment status pages | `tcsi_portal.scss`, registered in `web.assets_frontend` |

Portal styling is screen-only. Invoice document iframes, PDFs and printed
reports retain their report layout. Palette and semantic alert colors remain
unchanged.

Do not hide `.o_control_panel_breadcrumbs`: Odoo 18 nests New and other page
actions inside it. Do not reintroduce borders on every level of relational
  widgets. Preserve Odoo's own scroll owners, field grids and semantic states.

- The token parity test (`scripts/test-design-tokens.mjs`, eight assertions)
  compares the portal and addon palettes in both modes, the shared radii, the
  bundle order, and the absence of the retired hex values in the route layer.
- Every addon stylesheet compiles standalone and as a bundle with libsass
  3.6.6, the runtime Odoo uses: ten stylesheets, 236,247 bytes of CSS, no
  errors. An SCSS error aborts the whole `web.assets_web` bundle, so this is the
  gate that matters for presentation changes.
- The production Next.js build passes with the portal token layer and dark
  theme, and a rendered sweep of every portal route at 1440x900, 834x1000 and
  390x844 in light and dark mode found no horizontal overflow, no clipped
  labels, no unlabeled buttons and no light surface leaking into the dark theme.
- The hosted sign-in screen was verified rendered against the live engine:
  computed styles in both themes, no horizontal overflow, branded shell intact.

The workspace routes in section 2 of `docs/workspace-ui-coverage.md` remain
source-verified, not rendered: no engine login was available to this session and
Docker is unavailable locally, so no authenticated Odoo screen was exercised.
Close that gap by signing in to the handover browser session and re-running the
sweep against `/workspace/...`.

## Earlier verification performed

- All view XML parsed; manifest resources validated.
- Account move notebook inheritance matches exactly one notebook in the
  official Odoo 18 `account.view_move_form` source.
- Three Python branding tests and sixteen JavaScript branding/app tests passed.
- Both backend and frontend addon SCSS compiled in manifest order.
- Local Chromium fixtures used native Odoo 18 form/group/widget classes and
  the compiled addon CSS. Invoice, list and report layouts were checked at
  320, 768, 1024, 1440 and 1920px, in light and dark themes (30 combinations).
  Assertions covered page overflow, report section widths, composite borders
  and statusbar bounds. Screenshots were visually reviewed.
- Independent code review verified native control-panel actions, tag border
  specificity and selected status visibility in both themes.
- Saved journal/Discuss DOM was replayed offline against the live Odoo CSS,
  replacing only this addon's styles. Scripts and network requests were blocked.
- A desktop list fixture inside that captured journal notebook passed twelve
  combinations (320, 390, 768, 1024, 1440 and 1920px, light/dark). Assertions
  checked first-cell bounds, table containment, page/toolbar overflow, Follow
  button height and title height. The original captured journal used mobile
  kanban rows; the desktop table check is a fixture, not a live desktop session.
- Native settings replay caught and resolved mobile tab clipping. Review also
  corrected dark selected-tab text contrast and the Follow label structure.

These earlier checks do not establish that every route has been manually exercised.
The fixtures are layout checks, not a full Odoo integration test. Docker/Odoo
was unavailable locally. Before release, upgrade `thirdcode_accounting` in a
staging database and smoke-test native creation, editing, dropdowns, tabs,
posting/reversal permissions, report export and attachment/chatter layouts.
The cloud startup script applies addon upgrades when the manifest version
exceeds the installed version. This change has not been deployed by this task.
