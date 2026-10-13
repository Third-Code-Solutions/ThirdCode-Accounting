# Settings UI and UX redesign

## Decision and design contract

Keep Settings: the console covers customer organizations, people, monitoring, audits, and publications. Native Settings additionally owns email-server configuration, password-recovery options, document layouts, languages, and installed integrations. Removing it would remove useful administration capabilities.

Use the established TCSI workspace palette and flat surfaces. Keep native Save/Discard, unsaved-change warnings, search, application tabs, field modifiers, permissions, and navigation guards. Add a clear administration header and save guidance, a section outline based only on visible native headings, focus-aware section jumps, compact mobile section selection, consistent setting surfaces and controls, and a restrained toolbar. The product's existing dashboard/sidebar is the visual reference. No settings values or backend behavior are changed.

## Verification checkpoint

- 56 focused Node tests pass, including visible-section discovery, stable unique anchors, search/module changes, focus/scroll behavior, and observer/listener cleanup.
- All three native template extensions match their actual deployed template targets exactly once.
- Sass compiles with the production libsass runtime; 66 addon resources validate.
- Actual native Settings DOM replayed with the real native SettingsPage component and the new patch. Personal values sanitized; fields are static replay fixtures, not a live ORM form. Search filtering is simulated in this preview; native search requires production verification.
- Eight native-CSS layout combinations (320/768/1024/1440px, light/dark) have no document or settings-pane horizontal overflow. Save remains within the viewport. Mobile Jump to section scrolls to and focuses the native heading; desktop section buttons work. Existing fields remain in their native locations.

Next: CI, deployment, native live search, section navigation, module switching where available, field preservation, and responsive light/dark checks. Do not save production configuration during UI verification.
