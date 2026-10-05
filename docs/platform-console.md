# Platform owner operations

The hosted owner console is at `/workspace/console`, opened through **Platform Console** after signing in at `/web/login`. Use `superadmin@tcsi.local` only for platform operations. Company staff receive separate named accounts.

## Identity and access

Odoo requires each internal user to have a home company. The private **TCSI Platform Operations** company holds platform owners; it is excluded from customer organization directories and analytics. The module upgrade removes all customer memberships from flagged owners and removes their tenant accounting roles. It does not delete client users or accounting records. Sign out and sign back in after the upgrade to refresh old company selections.

The owner flag, system administrator group and dedicated console group must all be present. Every public console operation checks these on the server before cross-company access. A company Administrator or console group alone cannot use these operations. Internal setup provisioning cannot be called through generic RPC; the setup endpoint retains its separate operator-token checks. Hosting, database administrators and the trusted setup operator remain privileged recovery boundaries.

## First company onboarding

1. Open **Platform Console → Create organization**.
2. Enter legal company name, Philippines, approved book currency, first administrator name, work email and an initial password of 12–256 characters.
3. Select **Create organization & administrator**. One transaction creates the company, Philippine chart baseline, journals, current annual period and first Administrator. A retry of the same request does not create another company.
4. Give the administrator their credentials privately. This flow does not send email. They sign in at `/web/login` and receive only their company membership.
5. Use **Organizations → employees** or **People**, select the company, then **Create employee** for each accountant, encoder or read-only user. Use one account per person. Existing employee access and role can be changed here.
6. The client's accountant must verify legal/tax details, chart, currency, tax profile, controls, opening balances and document samples before posting live entries. Automatic baseline setup is not financial acceptance. Other countries need an approved localization before automatic onboarding is extended.

**Organizations** supports searchable, paginated trial/active/suspended status. Suspending preserves books and disables customer employee access; resuming restores accounts disabled by that suspension. It preserves accounts that were disabled beforehand.

## Analytics, audit and monitoring

**Overview** counts posted documents, customer accounts, organizations and trials. Activity charts count documents created in the selected 7/30/90-day UTC window. Counts are not combined financial revenue across unrelated currencies. Totals cover all customer organizations; detailed alerts and quick company selectors cover the first 200. The Organizations directory remains paginated across all customers.

**Audit trail** shows immutable platform-operation events and existing accounting audit history, with actor, time, action and target. Direct client access and ordinary editing/deletion of platform events are denied. Database operators are outside that application-level immutability guarantee.

**Sentry** is the first-party server incident monitor. Unexpected request failures survive rollback in a separate transaction and are grouped by exception class and route family. It stores no request bodies, exception messages, credentials or traceback contents. Owners acknowledge, resolve or reopen groups; recurrence reopens resolved incidents. Grouped telemetry expires after 90 days. The screen also shows scheduled jobs, active sign-in lockout count and runtime inventory. It does not claim browser-error coverage, external uptime, host CPU, or alert delivery. Latest 100 incident groups and 50 scheduled jobs are displayed.

## Website changes

Open **Website & updates**. Save a **Homepage SEO** draft or create a **Product update**. Preview plain text, then explicitly select **Publish saved draft**. Saving alone does not change public pages. SEO controls the homepage title, description and social preview text; canonical URLs remain fixed. Product updates appear at `/updates`.

**Unpublish** removes the public item without deleting its history. **Restore previous** swaps back to the previous published snapshot. Concurrent edits fail with a refresh message rather than overwriting newer content. Homepage SEO remains available on every editor page; updates are paginated. Public responses expose only published fields and the latest 100 unarchived releases. The public site retains reviewed default SEO if the content service is unavailable.

## Release and recovery

Version `18.0.2.14.0` adds platform company metadata, event/incident/publication tables and owner isolation. Take a paired database/filestore recovery capture before rollout. The hosted launcher applies the module upgrade before serving requests. Do not restore an old database over subsequent customer transactions to undo a UI issue; preserve current data and prefer a forward correction.

No application can guarantee immunity to attackers. Keep owner credentials private, use available account security controls and restrict hosting/recovery access. Tenant denial tests, forged-context tests, native ORM tests and hosted HTTP tests are release gates; they are not a substitute for operational monitoring or a full penetration test.
