# Platform operations console — 6 October 2026

## Objective and architecture
Extend the deployed Odoo workspace and Next.js public portal. Keep the prior migration plan intact. User authorization covers owner separation, organization administration, analytics, monitoring, audit inspection, SEO and changelog management.

Odoo requires a home company. A private, non-customer platform company holds owner identities; owners have no pilot/customer memberships. Cross-company reads and operations run only after a server-side owner check. Tenant roles never imply platform access. No new identity provider, external telemetry service, arbitrary code editor, or automatic public publishing.

## Acceptance and ordered slices
1. Owner identity: private home company, no tenant membership or appearance in client employee lists; forged owner flags/groups/context do not grant console access. Verify native ORM authorization and upgrade migration tests.
2. Operations: real organization creation with validated country/currency, baseline and first-admin creation; searchable organizations/users; bounded analytics, audit history and immutable operator events. Test success, denied roles, invalid targets and atomic rollback.
3. Sentry: grouped server failures captured without bodies, credentials, financial contents or tracebacks; acknowledge/resolve/reopen incidents; actual cron/security signals and timestamps. Test capture, aggregation, redaction, lifecycle and owner-only access.
4. Publishing: owner-only draft/save/publish/revert SEO; draft/publish/archive changelog; public API serves only explicit published fields. Next.js consumes the published data with bounded fetches and safe text rendering. Test unpublished-data isolation, input validation and metadata rendering.
5. UI: responsive owner workspace with Overview / Organizations / People / Sentry / Audit / Website sections; existing palette; loading, empty, errors, confirmation and keyboard states. Verify native Odoo runtime, desktop/mobile, light/dark.
6. Release: Python/package checks, native Odoo CI, web lint/types/tests/build, dependency audit, independent security/code review. Verify live isolation and owner account after release. Do not claim hosted changes from local tests.

## Threat boundaries
Authenticated tenant RPC, forged context/default values, generic ORM CRUD, company IDs, publishing payloads, exception text and public content endpoints are untrusted. Require owner checks before sudo; validate allowlists/lengths; retain immutable actor/time/target operation evidence; publish text only; keep secrets out of logs; do not weaken authentication throttling. Platform/DB operators remain an operational trust boundary; no claim of hacker-proof security.

## Design contract
Use existing TCSI light/dark tokens. Prioritize service health, tenant activity and actionable incidents, with compact charts and tables. Organization creation is the main action. Use measured data and explicit unavailable/empty states; no fabricated revenue, uptime or traffic. Charts include labels/counts. Filtered tables scroll within their panel on narrow screens. Publishing has draft preview and explicit publish controls.

## Checkpoint
- Base: origin/main 9f76a34; worktree codex/platform-operations.
- Original checkout and user documents preserved.
- Local Docker and Railway CLI unavailable; native tests will use repository CI. Existing GitHub CLI authenticated.
- Completed: current architecture/source and native authorization inspection.
- Next: implement owner isolation and guarded operations; then focused native tests.
