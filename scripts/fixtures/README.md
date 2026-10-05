# Native form input regression

`form-inputs.html` is a browser regression fixture. Serve it beside:

- `native.css`: the deployed Odoo `web.assets_web` stylesheet, captured from the browser's stylesheet inventory.
- `tcsi.css`: the candidate `tcsi_routes.scss` followed by `tcsi_dark.scss`, compiled together with Sass. Loading dark last preserves production cascade order.

Use a temporary directory for generated CSS; do not commit vendor bundles.
The fixture uses the monetary markup captured from production and Odoo 18's
`addons/web/static/src/views/fields/monetary/monetary_field.xml`, including the
invisible currency spacers. It exercises no-symbol, prefix and suffix amounts
in form, editable-table and dialog containers, plus ordinary text controls.

Open `?baseline=1` to reproduce the deployed defect, then `?theme=light` and
`?theme=dark` with the candidate styles at desktop and mobile widths. The page
title and status report must show all 55 checks passing. Also type into the
controls and visually check numbers and currency symbols. The baseline should
fail the overlay transparency checks; a green baseline is not a reproduction.

This is a CSS/DOM regression fixture, not an Owl lifecycle or saved-record test.
After deployment, verify typing and formatting on real unsaved forms and discard
the test input without saving, posting, or signing off accounting records.
