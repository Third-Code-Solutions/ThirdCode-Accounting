# Workspace controls — 6 October 2026

## Completed implementation

- Organization creation has a Generate password button beside Initial password. It generates 24 characters with `crypto.getRandomValues`, covering uppercase, lowercase, digits and symbols. Generated values are revealed for private handover; Show/Hide also works with manually entered values.
- Generation stays in the dialog's existing unsaved state. It makes no network request or clipboard write. Submission disables generation and editing; unavailable cryptographic randomness reports an error without replacing existing input.
- The workspace dropdown is 340px wide, bounded by the viewport. Labels can wrap. Its sidebar allows overflow only while the dropdown is open.
- Insights and People are removed from this dropdown. Dashboard replaces the TCSI Accounting menu label and uses the same authorized menu object/action. Other menus and the console's own People section are unchanged.

## Verification

- 46 JavaScript cases passed: `node --test scripts/test-platform-console.mjs scripts/test-branding.mjs scripts/test-apps.mjs scripts/test-design-tokens.mjs`.
- Seven Python branding cases passed: `python3 scripts/test-branding.py`.
- All 63 manifest resources passed `python3 scripts/validate-odoo-package.py`.
- Changed JavaScript passed syntax checks; changed test scripts passed the existing ESLint configuration. The isolated checkout reused the primary checkout's installed dependencies via `NODE_PATH` for linting.
- Candidate styles compiled with libsass, including the actual tokens, branding, routes, dark theme and console cascade.
- Local browser preview used captured native Odoo CSS, the hosted Owl runtime, the actual organization form XML and dialog component, and the actual workspace button/filter/label functions. Its outer Dialog wrapper and menu service were test doubles; no account creation, authentication change or accounting mutation was performed.
- Desktop menu measured 340px. At 390px it ended at x=352; at 320px it narrowed to 288px and ended at x=300. All six labels fit. Clicking Dashboard selected the original fixture menu ID and closed the dropdown.
- Generate and Show/Hide rendered and responded through Owl. Password controls fit at 390px and 320px without horizontal page overflow. Light and dark surfaces were inspected; dark dialog and input backgrounds were both `rgb(24, 34, 45)`. No browser JavaScript errors were recorded.

Screenshots: `menu-light.jpg`, `password-light.jpg`, `password-dark-desktop.jpg`, `menu-dark-mobile.jpg`, `password-dark-mobile.jpg`. They show the local preview, not a production deployment.

## Remaining boundary

Implementation and local verification are complete. No push, merge, production deployment, full native Odoo test suite, or live organization submission is claimed. The user's primary checkout and pre-existing local documents were preserved; changes are on `codex/password-workspace-menu` in the attached worktree.
