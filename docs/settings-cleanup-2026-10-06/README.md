# TCSI Settings cleanup

## Scope and acceptance

Curate the General Settings application to users, languages, companies and document layouts, email, activities, permissions, sign-in protection, and About TCSI. Remove weight/volume preferences, digest controls, paid contact services, calling infrastructure, GIF/translation options, mail-plugin/image/geolocation extras, developer shortcuts, and upstream edition/mobile-store promotions from this Settings UI. Preserve installed modules, stored configuration, security controls, native actions, and accounting application settings. Keep source licensing notices.

The server prepares a copy of the completed native view after inheritance, so other addons retain their inheritance anchors. The removed controls are omitted before native form compilation, including search; no DOM deletion of live Owl fields and no global text replacement. Retained fields keep native modifiers and actions. External provider names remain accurate where needed for email or authentication.

## Verification checkpoint

- 56 focused Node tests pass; Python files compile.
- Curation against the captured deployed native architecture removes 21 optional fields, contains no upstream product branding, leaves no references to removed fields in retained modifiers, and is idempotent.
- Native regression tests cover the resolved form view, retained security/document controls, removal of optional features and promotions, isolation from accounting applications, preservation of modifiers/actions, and source-tree immutability.
- Next: native CI, deployment, live search/branding/navigation verification. Do not change production configuration during UI checks.
