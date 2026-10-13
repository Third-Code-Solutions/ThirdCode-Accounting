# Owner Dashboard navigation

Objective: make the workspace Dashboard entry open the owner console and move its six sections into the main sidebar. Preserve customer finance dashboards, access enforcement, native actions, and the existing palette.

Implemented: explicit owner session flag using the existing authority predicate; native console-menu routing; shared console navigation with in-place section switching and busy guards; grouped main navigation; removal of the inner sidebar; full-width console canvas. Existing Organization settings remain accessible.

Local evidence: 50 focused Node tests pass, seven Python branding tests pass, and 64 manifest resources validate. Actual Owl console and sidebar code rendered against captured native Odoo CSS: all six sections switch, one sidebar, desktop document width equals viewport, first table cell stays inside content bounds. Preview uses disposable fixtures, not production business records.

Next: full CI, production deployment, and live owner/customer verification.
