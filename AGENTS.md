# Accounting workspace UI

- The hosted `/workspace` screens are served by the Odoo addon in
  `addons/thirdcode_accounting`; Next.js proxies those screens.
- Preserve the existing light/dark palette. Keep native view presentation in
  `tcsi_routes.scss` and public portal presentation in `tcsi_portal.scss`.
- Verify layout against native Odoo CSS, not Bootstrap-only fixtures. Native
  notebook tables use negative margin variables; test the first table cell's
  bounds as well as page overflow.
- Inspect rendered markup before changing widget layout. In particular,
  `.o-mail-Chatter-follow` is an overlay label inside a button, and mobile
  settings tabs have a fixed-height scroll container.
- Preserve Owl-managed form descendants, field modifiers, permissions,
  accounting actions and report/PDF layouts during presentation changes.
