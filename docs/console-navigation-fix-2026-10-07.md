# Console navigation repair

Objective: fix Settings from the owner console, remove Settings from the workspace picker, consolidate organization navigation, and preserve organization/user creation.

Live reproduction: Settings click produced an Owl lifecycle failure whose cause was `ConnectionLostError` for `/base_setup/data`. A POST to that URL returned portal HTML instead of engine JSON. The app root does have action 93 in production; missing proxy routing is the observed cause. Selecting the authorized General Settings leaf additionally avoids relying on the app root default action.

Changes: proxy the native base_setup prefix with private/no-store headers and middleware bypass; select the permission-filtered Settings leaf; hide Settings in the picker; omit the redundant Organization tree only for platform owners. People offers Create user with explicit organization guidance and a guarded, scoped native wizard.

Checkpoint: 60 focused browser-controller/menu tests, 49 proxy tests, 7 Python branding checks, package validation, and targeted lint pass. Native CI and live deployment verification pending. Added native owner-to-customer user provisioning regression; existing provisioning tests cover organization creation and atomic retry.

CI run 37494716323 passed app tests and builds but blocked on newly published GHSA-wq5f-xc86-pv6w in the existing sharp 0.35.4. Updated only sharp and its platform image binaries to 0.35.5 via lockfile; production dependency audit now reports zero vulnerabilities. Full CI rerun required.
