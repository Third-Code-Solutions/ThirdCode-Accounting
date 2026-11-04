# Platform console Settings entry

User reported Settings unavailable from platform console. Live owner reproduction: the workspace picker Settings app and Organization > People Accounts both load without browser errors. The console's main sidebar had a Workspace settings heading but no Settings action, only Organization account tools.

Correction: add the existing permission-filtered Settings app as a direct native menu button beneath Workspace settings. No action IDs, permission bypasses, configuration writes, or backend changes. The dropdown Settings path remains available.

Verification: new production-sidebar regression fails on the prior code (missing Settings button), passes after the four-line fix, and verifies native menu selection plus omission when Settings is not in the allowed app list. All 51 focused Node tests and 64 manifest resources pass. Next: CI, deployment, live direct-button verification. The user's exact failing Settings control has not yet been clarified; additional control-specific failures remain unproven.
