# TCSI platform deployment

## Independent TCSI demonstration and future client copies

Current scope (11 October 2026): prepare one independent TCSI demonstration
system. After a sale, deploy a fresh copy into that client's hosting account.
Five companies in the shared pilot are not five independent installations.
White-label SaaS, shared customer hosting, subscriptions and the optional Node
worker are outside this delivery. The earlier hosted pilot below remains a
separate environment; do not convert or copy its customer books into a demo.

`docker-compose.independent.yml` runs one Odoo engine and one PostgreSQL server
per installation. Each Compose project owns separate database/filestore volumes
and its own network. The database has no published port; the engine binds only
to loopback for an operator-managed TLS reverse proxy. No Next.js portal,
Supabase project or Node worker is required for native `/workspace` accounting.
The existing system-owner console remains an operator tool, not a customer SaaS
signup flow. Demonstrate the business workspace with a company-role account.

1. Build `docker/odoo/Dockerfile` from the verified source revision. A local
   rehearsal may set `TCSI_ODOO_IMAGE` to Docker's immutable `sha256:<image-id>`.
   For turnover, publish the image and use
   `registry.example/accounting@sha256:<manifest-digest>`. Mutable tags are for
   development only. Retain the application image identity with the release;
   the base Odoo image digest is not the accounting application's identity.
   Keep that exact image available in the client's registry or an offline
   `docker image save` archive for the entire backup-retention period. Recording
   a digest alone cannot restore an image that has been removed. The restore
   procedure deliberately refuses a different image.
   The launcher refuses databases with an addon version newer than the image.
   Before upgrading an older hosted installation, install this startup guard
   in its current release first. That guarded release becomes the immediate
   fallback: it fails closed after a schema upgrade instead of serving older
   authorization code against newer permissions. Do not select older unguarded
   images for rollback. Prefer forward repair after customer writes resume.
2. Copy `config/independent.env.example` to protected storage outside Git. Set
   a unique project name, database name, loopback port and distinct random
   passwords (at least 24 characters). Set `TCSI_ODOO_IMAGE` to the built image
   digest. Use separate credentials for PostgreSQL administration, Odoo's
   restricted database role, initial system-owner login and database manager.
3. Start with `docker compose --env-file /private/tcsi.env -f
   docker-compose.independent.yml up -d`. The database initialization service
   creates the restricted application role before Odoo starts. Preserve both
   volumes across updates. Never run `down --volumes` against retained books.
4. Configure the external TLS proxy for the engine and WebSocket upgrades; it
   must replace untrusted forwarded host, scheme and client-address headers.
   Set Odoo's `web.base.url` to the approved HTTPS URL and
   `web.base.url.freeze=True`. Keep the database and internal worker ports private.
5. Using the operator account, provision only the intended demonstration company
   and named business-role users. Use trial mode for synthetic demonstrations;
   retain the visible TRIAL COPY marking. Do not invent statutory approvals.
   Run `check_company_readiness.py` as its company Administrator with
   `--expected-companies 1 --trial` and explicit expected country/currency.
6. Before sharing the demonstration, verify login, role denials, invoice/bill
   posting, receipts/payments, reversals, reports, recurrence and restart
   persistence against that installation. Rehearse a coordinated database plus
   filestore restore into an isolated target. Public hosting additionally needs
   TLS, verified backups, failure alerts and a named operator.

For a client sale, clone the verified application configuration and image, not
the TCSI demo database, filestore, session cookies or credentials. Start with
empty volumes in the client's account. Repeat identity/chart/tax/role setup,
approved migration and report acceptance, backup delivery and recovery tests.
Use the company preflight without `--trial` before real books. A demo pass does
not establish client accounting acceptance, a parallel month or statutory approval.

### Coordinated independent backup and isolated restore

Run this from the repository root on the Linux Docker host. It stops only the
selected installation's Odoo writer, always attempts to restart it through the
`EXIT` trap, captures a PostgreSQL custom archive and matching filestore, and
records deterministic accounting and physical-attachment evidence. Keep the
private env file and backup root outside Git.

```bash
set -Eeuo pipefail
umask 077

SOURCE_ENV=/private/tcsi.env
BACKUP_ROOT=/private/tcsi-backups
source_compose=(docker compose --env-file "$SOURCE_ENV" -f docker-compose.independent.yml)

SOURCE_CONFIG="$("${source_compose[@]}" config --format json)"
SOURCE_PROJECT="$(printf '%s' "$SOURCE_CONFIG" | python3 -c 'import json,sys; print(json.load(sys.stdin)["name"])')"
SOURCE_DB="$(printf '%s' "$SOURCE_CONFIG" | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["odoo"]["environment"]["PGDATABASE"])')"
SOURCE_APP_ROLE="$(printf '%s' "$SOURCE_CONFIG" | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["odoo"]["environment"]["PGUSER"])')"
SOURCE_IMAGE="$(printf '%s' "$SOURCE_CONFIG" | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["odoo"]["image"])')"
SOURCE_PG_IMAGE="$(printf '%s' "$SOURCE_CONFIG" | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["db"]["image"])')"
unset SOURCE_CONFIG

case "$SOURCE_DB" in ''|*[!a-zA-Z0-9_]*) echo 'Unsafe database name' >&2; exit 64;; esac
SOURCE_ODOO_CONTAINER="$("${source_compose[@]}" ps -q odoo)"
test -n "$SOURCE_ODOO_CONTAINER"
CONFIG_IMAGE_ID="$(docker image inspect --format '{{.Id}}' "$SOURCE_IMAGE")"
LIVE_IMAGE_ID="$(docker inspect --format '{{.Image}}' "$SOURCE_ODOO_CONTAINER")"
if [ "$CONFIG_IMAGE_ID" != "$LIVE_IMAGE_ID" ]; then
  echo 'Refusing backup: configured Odoo image differs from running container image' >&2
  exit 65
fi
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
partial="$BACKUP_ROOT/${SOURCE_PROJECT}-${stamp}.partial"
final="$BACKUP_ROOT/${SOURCE_PROJECT}-${stamp}"
mkdir -p "$BACKUP_ROOT"
test ! -e "$final"
mkdir "$partial"

cat > "$partial/accounting-fingerprint.sql" <<'SQL'
\set ON_ERROR_STOP on
SET ROLE :"app_role";
SELECT jsonb_build_object('type','addon','state',state,'version',latest_version)::text
  FROM ir_module_module WHERE name = 'thirdcode_accounting';
SELECT jsonb_build_object('type','move','id',id,'company',company_id,'name',name,
                          'move_type',move_type,'state',state,'total',amount_total,
                          'residual',amount_residual)::text
  FROM account_move WHERE state = 'posted' ORDER BY id;
SELECT jsonb_build_object('type','balance','company',m.company_id,'account',l.account_id,
                          'lines',count(*),'debit',coalesce(sum(l.debit),0),
                          'credit',coalesce(sum(l.credit),0),'balance',coalesce(sum(l.balance),0))::text
  FROM account_move_line l JOIN account_move m ON m.id = l.move_id
 WHERE m.state = 'posted' GROUP BY m.company_id,l.account_id ORDER BY m.company_id,l.account_id;
SQL
cat > "$partial/attachment-inventory.sql" <<'SQL'
\set ON_ERROR_STOP on
SET ROLE :"app_role";
SELECT store_fname,checksum FROM ir_attachment
 WHERE store_fname IS NOT NULL ORDER BY store_fname,checksum;
SQL

source_stopped=0
restart_source() {
  if [ "$source_stopped" -eq 1 ]; then
    "${source_compose[@]}" start odoo >/dev/null || echo 'CRITICAL: restart Odoo manually' >&2
  fi
}
trap restart_source EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
source_stopped=1
"${source_compose[@]}" stop odoo

"${source_compose[@]}" exec -T db sh -ceu \
  'PGPASSWORD="$POSTGRES_PASSWORD" exec pg_dump --format=custom --no-owner --no-acl --username="$POSTGRES_USER" --dbname="$1"' \
  sh "$SOURCE_DB" > "$partial/database.dump"
"${source_compose[@]}" run --rm --no-deps --entrypoint sh odoo -ceu \
  'test -d "/var/lib/odoo/filestore/$1"; exec tar -C /var/lib/odoo/filestore -czf - -- "$1"' \
  sh "$SOURCE_DB" > "$partial/filestore.tar.gz"

"${source_compose[@]}" exec -T db sh -ceu \
  'PGPASSWORD="$POSTGRES_PASSWORD" exec psql -X -qAt --username="$POSTGRES_USER" --dbname="$2" --set=app_role="$1"' \
  sh "$SOURCE_APP_ROLE" "$SOURCE_DB" < "$partial/accounting-fingerprint.sql" \
  > "$partial/accounting-fingerprint.tsv"
"${source_compose[@]}" exec -T db sh -ceu \
  'PGPASSWORD="$POSTGRES_PASSWORD" exec psql -X -qAt -F "|" --username="$POSTGRES_USER" --dbname="$2" --set=app_role="$1"' \
  sh "$SOURCE_APP_ROLE" "$SOURCE_DB" < "$partial/attachment-inventory.sql" \
  > "$partial/attachment-inventory.tsv"
"${source_compose[@]}" run -T --rm --no-deps --entrypoint sh odoo -ceu '
  while IFS="|" read -r name expected; do
    case "$name" in ""|/*|*..*) exit 65;; esac
    file="/var/lib/odoo/filestore/$1/$name"
    test -f "$file"
    actual="$(sha1sum "$file" | cut -d " " -f 1)"
    test "$actual" = "$expected"
    printf "%s|%s\n" "$name" "$actual"
  done' sh "$SOURCE_DB" < "$partial/attachment-inventory.tsv" \
  > "$partial/attachment-files.tsv"

printf '%s\n' "$SOURCE_DB" > "$partial/database-name.txt"
printf '%s\n' "$SOURCE_IMAGE" > "$partial/image-reference.txt"
printf '%s\n' "$LIVE_IMAGE_ID" > "$partial/image-id.txt"
printf '%s\n' "$SOURCE_PG_IMAGE" > "$partial/postgres-image.txt"
(cd "$partial" && find . -maxdepth 1 -type f ! -name SHA256SUMS -printf '%P\0' \
  | sort -z | xargs -0 sha256sum > SHA256SUMS)

"${source_compose[@]}" start odoo
source_stopped=0
trap - EXIT INT TERM
mv "$partial" "$final"
printf 'Backup ready: %s\n' "$final"
```

Copy the completed directory to protected off-host storage using the operator's
approved encryption and retention controls. Never treat a `.partial` directory
as a backup. Test recovery with another private env file whose project name,
credentials and loopback port are unique. Keep `PGDATABASE` equal to the captured
name so the restored filestore path matches. The following refuses any existing
target containers, volumes or network, verifies the archive first, requires the
same application image and PostgreSQL image, and starts only PostgreSQL:

```bash
set -Eeuo pipefail
umask 077

BACKUP_DIR=/private/tcsi-backups/company-accounting-YYYYMMDDTHHMMSSZ
TARGET_ENV=/private/tcsi-restore.env
target_compose=(docker compose --env-file "$TARGET_ENV" -f docker-compose.independent.yml)
(cd "$BACKUP_DIR" && sha256sum -c SHA256SUMS)

TARGET_CONFIG="$("${target_compose[@]}" config --format json)"
TARGET_PROJECT="$(printf '%s' "$TARGET_CONFIG" | python3 -c 'import json,sys; print(json.load(sys.stdin)["name"])')"
TARGET_DB="$(printf '%s' "$TARGET_CONFIG" | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["odoo"]["environment"]["PGDATABASE"])')"
TARGET_APP_ROLE="$(printf '%s' "$TARGET_CONFIG" | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["odoo"]["environment"]["PGUSER"])')"
TARGET_IMAGE="$(printf '%s' "$TARGET_CONFIG" | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["odoo"]["image"])')"
TARGET_PG_IMAGE="$(printf '%s' "$TARGET_CONFIG" | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["db"]["image"])')"
TARGET_DB_VOLUME="$(printf '%s' "$TARGET_CONFIG" | python3 -c 'import json,sys; print(json.load(sys.stdin)["volumes"]["db-data"]["name"])')"
TARGET_ODOO_VOLUME="$(printf '%s' "$TARGET_CONFIG" | python3 -c 'import json,sys; print(json.load(sys.stdin)["volumes"]["odoo-data"]["name"])')"
TARGET_NETWORK="$(printf '%s' "$TARGET_CONFIG" | python3 -c 'import json,sys; print(json.load(sys.stdin)["networks"]["backend"]["name"])')"
unset TARGET_CONFIG

test "$TARGET_DB" = "$(cat "$BACKUP_DIR/database-name.txt")"
test "$TARGET_PG_IMAGE" = "$(cat "$BACKUP_DIR/postgres-image.txt")"
test "$(docker image inspect --format '{{.Id}}' "$TARGET_IMAGE")" = "$(cat "$BACKUP_DIR/image-id.txt")"
test -z "$("${target_compose[@]}" ps -aq)"
for volume in "$TARGET_DB_VOLUME" "$TARGET_ODOO_VOLUME"; do
  if docker volume inspect "$volume" >/dev/null 2>&1; then
    echo "Refusing pre-existing restore volume: $volume" >&2
    exit 65
  fi
done
if docker network inspect "$TARGET_NETWORK" >/dev/null 2>&1; then
  echo "Refusing pre-existing restore network: $TARGET_NETWORK" >&2
  exit 65
fi

target_created=1
restore_verified=0
RESTORE_WORK="$(mktemp -d)"
cleanup_failed_restore() {
  if [ "$target_created" -eq 1 ] && [ "$restore_verified" -eq 0 ]; then
    "${target_compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
  fi
  rm -rf -- "$RESTORE_WORK"
}
trap cleanup_failed_restore EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

"${target_compose[@]}" up -d --wait db
"${target_compose[@]}" run --rm --no-deps db-init
"${target_compose[@]}" exec -T db sh -ceu \
  'PGPASSWORD="$POSTGRES_PASSWORD" exec pg_restore --exit-on-error --single-transaction --no-owner --no-acl --role="$1" --username="$POSTGRES_USER" --dbname="$2"' \
  sh "$TARGET_APP_ROLE" "$TARGET_DB" < "$BACKUP_DIR/database.dump"
"${target_compose[@]}" run -T --rm --no-deps --entrypoint sh odoo -ceu \
  'test ! -e "/var/lib/odoo/filestore/$1"; mkdir -p /var/lib/odoo/filestore; exec tar -C /var/lib/odoo/filestore -xzf -' \
  sh "$TARGET_DB" < "$BACKUP_DIR/filestore.tar.gz"

"${target_compose[@]}" exec -T db sh -ceu \
  'PGPASSWORD="$POSTGRES_PASSWORD" exec psql -X -qAt --username="$POSTGRES_USER" --dbname="$2" --set=app_role="$1"' \
  sh "$TARGET_APP_ROLE" "$TARGET_DB" < "$BACKUP_DIR/accounting-fingerprint.sql" \
  > "$RESTORE_WORK/accounting-fingerprint.tsv"
"${target_compose[@]}" exec -T db sh -ceu \
  'PGPASSWORD="$POSTGRES_PASSWORD" exec psql -X -qAt -F "|" --username="$POSTGRES_USER" --dbname="$2" --set=app_role="$1"' \
  sh "$TARGET_APP_ROLE" "$TARGET_DB" < "$BACKUP_DIR/attachment-inventory.sql" \
  > "$RESTORE_WORK/attachment-inventory.tsv"
"${target_compose[@]}" run -T --rm --no-deps --entrypoint sh odoo -ceu '
  while IFS="|" read -r name expected; do
    case "$name" in ""|/*|*..*) exit 65;; esac
    file="/var/lib/odoo/filestore/$1/$name"
    test -f "$file"
    actual="$(sha1sum "$file" | cut -d " " -f 1)"
    test "$actual" = "$expected"
    printf "%s|%s\n" "$name" "$actual"
  done' sh "$TARGET_DB" < "$RESTORE_WORK/attachment-inventory.tsv" \
  > "$RESTORE_WORK/attachment-files.tsv"

cmp "$BACKUP_DIR/accounting-fingerprint.tsv" "$RESTORE_WORK/accounting-fingerprint.tsv"
cmp "$BACKUP_DIR/attachment-inventory.tsv" "$RESTORE_WORK/attachment-inventory.tsv"
cmp "$BACKUP_DIR/attachment-files.tsv" "$RESTORE_WORK/attachment-files.tsv"

"${target_compose[@]}" run -T --rm --no-deps --entrypoint sh odoo -ceu '
  exec odoo shell --no-http --max-cron-threads=0 \
    --db_host="$PGHOST" --db_port="$PGPORT" --db_user="$PGUSER" \
    --db_password="$PGPASSWORD" -d "$PGDATABASE" \
    --addons-path=/opt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons' <<'PY'
import json
module = env['ir.module.module'].search([('name', '=', 'thirdcode_accounting')], limit=1)
assert module.state == 'installed'
result = {
    'addon_version': module.latest_version,
    'companies': env['res.company'].search_count([]),
    'posted_moves': env['account.move'].search_count([('state', '=', 'posted')]),
    'payments': env['account.payment'].search_count([]),
}
print(json.dumps(result, sort_keys=True))
PY

restore_verified=1
trap - EXIT INT TERM
rm -rf -- "$RESTORE_WORK"
printf 'Verified isolated target: project=%s database=%s\n' "$TARGET_PROJECT" "$TARGET_DB"
```

The source project and its volumes are never removed. The target Odoo service
remains stopped throughout verification, so HTTP, cron and queued mail do not
run. Review the exact move and per-account/company balance comparison plus every
attachment's database checksum and physical SHA-1 before acceptance. After
sign-off, either keep the isolated target for controlled recovery work or remove
only that target with `"${target_compose[@]}" down --volumes --remove-orphans`.
The legacy local `backup.ps1`/`restore.ps1` defaults are not an independent
recovery procedure. Schedule encrypted off-host copies, retention, failure
alerts, named operators and tested RPO/RTO before client production use.

The privileged `/tcsi/setup` endpoint is disabled in this package. Other
operator-controlled deployments may explicitly supply a per-installation
`TCSI_SETUP_TOKEN_SHA256` (64 lowercase hex characters) through their private
runtime environment. Never reuse the old repository-wide setup credential.
Remove the environment value and restart after provisioning. Existing owner
console provisioning remains available without enabling the anonymous endpoint.

> Historical hosted-pilot note (5 October 2026): the existing pilot uses Vercel,
> Railway and Supabase. It is separate from the independent TCSI demonstration
> and is not the target for future client-owned copies. Hosted sections below are
> retained as operator history, not independent-installation instructions. See
> [the historical release record](prd-alignment-2026-10-05/REPORT.md) and
> [hosted recovery procedure](prd-alignment-2026-10-05/HOSTED-OPERATIONS.md).


## Optional marketing contact intake

The independent Odoo package has no Supabase dependency. If retaining the
separate Next.js marketing portal, apply the full Supabase migration chain,
including `20261011151215_require_trusted_demo_intake.sql`, before deploying
the matching contact API. Direct anonymous/authenticated table inserts are
revoked. The API uses a narrow intake RPC, not a service-role credential.

Generate a dedicated random 32-byte token encoded as 64 lowercase hex
characters. Set it privately as `TCSI_DEMO_INTAKE_SECRET` on the web server;
insert the SHA-256 digest of that exact UTF-8 string into the singleton row of
`private.demo_intake_config` through the database administrator. Never commit
the secret or put it in a `NEXT_PUBLIC_` variable. Missing/mismatched
configuration returns an honest 503 and stores no lead. Rotate the private
digest and runtime secret together; delete the row to disable intake.

Database limits are three submissions per normalized email, five per trusted
client identity and 100 globally per hour, including concurrent requests.
On Vercel the server trusts only the provider-overwritten
`x-vercel-forwarded-for` header; elsewhere all requests share the bounded unknown
client bucket until a trusted ingress integration is implemented. Generic
forwarded headers cannot choose a new bucket. Verify one real form submission,
direct-write denial and rate-limit recovery after portal deployment. This
configuration is not needed for an accounting-only client installation.

## Customer app launcher

`/workspace/apps` lists the complete application-module catalog using one
permission-checked module read. Installed, uninstalled, unavailable and pending
states are explicit. Only installed apps with an accessible root menu have an
Open button; other cards explain setup or embedded features. Bundled TCSI icons
and local monograms replace vendor images. Search/category/status filtering is
local. No installation or permission changes occur when browsing the catalog.
Accounting Administrator is a business role, not `base.group_system`; this
release does not grant module-installation privileges. The technical module
manager remains at `/workspace/technical-modules` for system administration.
Marketplace/theme links are removed from customer navigation. Copyright and
license notices, dependency identities and technical diagnostics are retained.

Invoice, journal and expense views disable synthetic sample records; empty
ledgers must not display generated amounts. Existing records are unaffected.
The launcher release updates menu/action metadata as well as inherited views.
To roll it back without touching transactions, deploy a corrective module upgrade:
move `action_tcsi_apps.path` away from `apps`, flush the client action, restore
`base.open_module_tree.path` to `apps`, and restore the previous root menu action
and groups. Restore changed menu names/icons/active flags from the previous
release and deactivate this release's inherited no-sample views as needed.
Redeploying an older image alone does not reverse database metadata. Never restore
a snapshot over new customer transactions just to revert a UI release.

## ORVEXA local task engine

ORVEXA presents supported commands in the native docked messaging window and
expanded Discuss conversation, with inline draft review/confirmation. Native
minimize, restore and close controls are retained. Enter sends a message;
Shift+Enter inserts a new line. The chat transcript is held in tab memory per
company until reload, surviving minimize/close/reopen, not stored in browser
storage. Existing server-side activity memory and task proposals remain persistent.
The chatbot interface does not add general language inference or change permissions.

ORVEXA uses deterministic, allowlisted commands inside the accounting server;
it does not call an AI provider or require a model. It is not an unrestricted
natural-language agent. Supported requests are `show overdue invoices`,
`find "customer or invoice reference"`, `show recent activity`, and
`draft invoice for "Customer" with 2 x "Product" at 100`. Exact customer and
product names and a single sales journal are required. Unsupported or compound
requests are not executed. The UI explains the supported forms.

Draft proposals expire after ten minutes and require an explicit confirmation.
Execution checks current role, company, record rules and referenced record versions;
confirmation retries are serialized and cannot create a second invoice. No tool
posts entries, transfers money, sends invoices or deletes business records.
Only proposal/activity metadata uses elevated access; accounting CRUD does not.
The session API is `POST /thirdcode_accounting/orvexa` (JSON-RPC), with a valid
session CSRF token and authorized `company_id`. Proposal confirmation takes only
the server-created ID, not client-supplied financial values.

Organization memory records committed invoice, bill and journal-entry changes
from deployment onward; it is not a retrospective archive or whole-application
surveillance. Each read rechecks current record access. Own task history persists
across sessions. Notifications contain invalidation hints only, refresh the open
panel after 250ms, and use the existing authenticated WebSocket relay. A 15-second
poll while visible recovers missed notifications. The UI shows snapshot time and
connection failure; exact one-second freshness is not guaranteed.

Version 18.0.2.6.0 adds two metadata tables. Startup upgrades the custom module
before accepting traffic when its numeric manifest version exceeds the installed
version. Take a database/filestore snapshot before this release. On failure, the
new instance must remain unready; roll back its image without dropping tables.
Existing financial data is preserved. Local and CI integration tests use disposable
databases; do not run synthetic write tests against customer books.

Version 18.0.2.6.1 adds global company-scoped rules for custom accounting
records and guarded workflow transitions. The selected integration suite and a
fresh synthetic install passed locally. The upgrade from an existing customer
database has not been rehearsed; take a paired database/filestore snapshot and
verify the exact release against a restored disposable copy before customer
cutover.

Versions 18.0.2.6.2 through 18.0.2.6.6 add active-company fiscal-year date
defaults for Trial Balance and Journal Ledger, and active-company reconcilable
account defaults for Open Items and Aged Partner Balance. Selecting neither the
receivable nor payable-only filter restores all reconcilable accounts for that
company. Each wizard still enforces the existing active-company report access
check.

Version 18.0.2.7.2 adds company-scoped rules and guarded workflow transitions for
accounting records, with regression coverage for financial controls. It also
retains the app launcher and Sass regression check introduced in 18.0.2.7.1.
Startup upgrades the custom module when its manifest version exceeds the
installed version. Take paired database and filestore snapshots before rollout;
verify startup upgrade, login, accounting access, and health routes afterward.

## Existing hosted pilot (separate historical architecture)

The customer pilot uses the existing TCSI-branded accounting engine. The new
portal is deployed separately; it is not the replacement ledger.

```text
Vercel portal -> Railway TCSI Accounting -> dedicated Railway Postgres + filestore
     |
     +-> Supabase Auth connectivity (no live accounting schema)
```

- Portal: https://tcsi-accounting-portal.vercel.app
- Customer login: https://tcsi-accounting-portal.vercel.app/web/login
- Railway origin (operations/recovery): https://tcsi-accounting-production.up.railway.app/web/login
- Railway project: `4af92f83-8aa1-4135-9eeb-c6bcf9f7cbc8`, production environment.
- Vercel team: `pavi-2e9809a4`, project `tcsi-accounting-portal`, root `apps/web`.
- Supabase project: `zcalwevgunkevwzficvm`.

Set `TCSI_PORTAL_ONLY=true` in Vercel. The portal links to `/web/login` on its
own domain. Engine paths use external CDN rewrites to Railway; they bypass
Next middleware body buffering and shared caching is disabled. Sessions remain
host-only on the customer domain. The origin still performs authentication and
authorization. Do not replace these rewrites with a catch-all that exposes the
unfinished standalone app. Portal mode blocks its API routes and redirects its
pages to the entry page. `/api/readiness` probes Supabase Auth and the Odoo
login endpoint; it detects basic availability but does not certify ledger
correctness or company setup. Public Supabase signup and workspace
self-provisioning are disabled for the hosted pilot. Do not switch portal mode
off for customer use until standalone accounting has passed its release gates.

Before allowing a company to post real entries, run the read-only structural
preflight as a company Administrator. The password is prompted without echo,
or supplied through `TCSI_ODOO_PASSWORD` in the operator's process. For a
five-company installation:

```powershell
python scripts/check_company_readiness.py --url https://tcsi-accounting-production.up.railway.app --database tcsi_pilot --login <administrator-login> --expected-companies 5
```

The preflight exits nonzero if the account cannot see the expected companies or
a company lacks its legal identity, chart, journals, current open period,
approved tax profile, document controls/samples, or named backup and restore
owners. Pass `--expected-companies 1` for the current single-company pilot, and
pass `--expected-country-code` and `--expected-currency-code` with approved
values to detect a default or wrong book currency. It makes no accounting
writes. Its `structurally_ready` result is only a configuration
gate; approved source balances, user isolation, a parallel month, actual
backup recovery, and client/legal sign-off still require independent evidence.

`/websocket` uses a small same-origin Vercel Function relay because external CDN
rewrites do not preserve the accounting WebSocket handshake. It forwards only
the existing session cookie to the fixed Railway origin, enforces Origin checks,
bounds buffers, and reconnects before the function duration limit. Railway remains
the authorization and subscription authority. This uses Vercel's beta WebSocket
API and requires Fluid Compute; verify a real handshake and notification delivery
after each runtime/provider change. `/websocket/*` HTTP endpoints still use rewrites.
The Railway URL remains available for operational recovery if Vercel is unavailable.
Legacy `/odoo` bookmarks redirect to `/workspace` at both the Vercel edge and
the accounting controller. Client-generated workspace links use the same prefix,
including query-only URLs. Routing/branding regression tests protect these paths.
Production `web.base.url` is `https://tcsi-accounting-portal.vercel.app` and
`web.base.url.freeze` is `True` so administrative origin logins do not change
generated customer links back to Railway.

Railway uses `docker/odoo/Dockerfile` and start command
`python3 /opt/tcsi/cloud_start.py`, with `/web/login` as its health check.
New Railway services no longer accept the legacy `railway.json` mechanism;
configure these service settings explicitly. Set `RAILWAY_DOCKERFILE_PATH`,
`RAILWAY_RUN_UID=0` (the bootstrap immediately drops to the odoo user),
`PORT=8069`, and mount a persistent volume at `/var/lib/odoo`.
The launcher supervises nginx and the Odoo master as one runtime. nginx owns
the public `PORT`; regular requests go to loopback HTTP port 8068 and
`/websocket` (including its HTTP subpaths) goes to loopback evented port 8072.
Keep `TCSI_WORKERS` at least 1 (default 2). The public port must differ from
8068 and 8072. Forwarded TLS/client headers and the original Host are preserved.
If either essential process exits, the launcher stops its peer and exits
nonzero so Railway restarts the complete service. The CI hosted-launcher gate
checks HTTP login, secure cookies, error status/headers and a real WebSocket
upgrade/ping/pong/close; production verification must also cover the Vercel relay.
Set `PGHOST`, `PGPORT`, `PGDATABASE=tcsi_pilot`, `PGUSER=tcsi_app`, and
`PGPASSWORD` in Railway. The application role must not be a superuser.
Provision `pg_trgm` and `unaccent` in its empty database using the database
administrator. Do not expose the database over public TCP.

`TCSI_ADMIN_LOGIN`, `TCSI_ADMIN_PASSWORD`, and `TCSI_MASTER_PASSWORD` live only
in Railway variables. Bootstrap initializes a fresh database and sets the
first administrator once; restarts do not reset credentials. Database listing
is disabled. No local customer records or shared demo credentials are copied.
Run `python scripts/validate-odoo-package.py` before uploading; module XML data
must not be excluded by `.gitignore` or the container build context.
Vercel enforces portal mode in code, including previews with no configured flag.

The reviewed Supabase portal migrations have been applied to the project:
the tenant foundation, website demo-request intake, platform-owner access
boundary, and explicit function-grant hardening. Never run an unreviewed bulk
migration push against this project. The event-trigger hardening revokes public
execution without disabling automatic RLS.

The repository migration files were reconciled with the applied project
history on 2 October 2026: the files now carry the versions recorded in the
project's `supabase_migrations.schema_migrations` table (20260922090204 ...
20260927172751), so `supabase db push --dry-run` reports `Remote database is
up to date` instead of replaying already-applied SQL. The migration validator
resolves files by suffix, so the renumbering cannot silently break the gate.

Live tenant verification: `SUPABASE_ACCESS_TOKEN=... npm run verify:rbac`
provisions two throwaway organizations and six probe users, then asserts the
cross-organization read/write isolation and the full owner/admin/accountant/
encoder/viewer matrix (25 checks) directly against the hosted database. Every
assertion runs inside a rolled-back transaction and the probe data is deleted
afterwards. Run it after any policy, function, or migration change and before
onboarding a customer organization.

Platform owner:
`SUPABASE_ACCESS_TOKEN=... node scripts/bootstrap-platform-owner.mjs --email <approved-address>`
creates or reuses the owner's Supabase Auth user through the supported GoTrue
admin API, verifies that password sign-in works, and points the single
`platform_owner_access` row at that user (re-running rotates the assignment).
With `--send-recovery` the script instead creates the account **without** a
password and emails a set-password link; the portal's `/auth/confirm` route
consumes `{{ .TokenHash }}` links from any device and lands the user on the
`/login` set-password screen (the hosted project's recovery and invite email
templates use that pattern, and `site_url`/allow-list include the portal
origin). Handle the emailed value only through the portal page itself.
The password is read from a hidden prompt and must go into the team password
manager; never paste it into chat, tickets, or email. Without this step the
`/login` and `/owner` console has no account that can sign in.

The marketing routes are `/`, `/platform`, `/controls`, `/pilot`, and
`/contact`; each is a real page rather than a hash-scroll section. `/contact`
accepts a company demo request and writes only a `new` website lead. The
separate `/login` route is the Supabase platform-owner sign-in; `/web/login`
remains the customer accounting-engine sign-in.

The database normalizes public lead addresses and caps one address at three
submissions per rolling hour, including direct Data API inserts. Field-length
checks apply to new rows without rejecting older rows during migration. This
limits repeat abuse; provider-edge throttling remains necessary for attacks
that rotate addresses.

The future standalone dashboard's limited receivables metric is the gross open
balance of issued or partially paid PHP sales invoices. It excludes drafts,
paid/void documents, purchases, credit/debit notes, and foreign currencies; it
is not a net accounts-receivable ledger or an FX conversion.

Platform ownership is deliberately singleton and server-enforced. The
`platform_owner_access` table can contain one assigned Supabase user, and the
analytics RPCs require that authenticated user before returning cross-tenant
metrics. Customer organization owners remain limited to their own workspace.
Create the owner's Supabase Auth user first, then assign that user through a
reviewed administrative database operation. Do not add a service-role key to
Vercel or the browser.

### Pilot provisioning endpoint (`/tcsi/setup`)

The addon exposes a token-gated POST endpoint on the engine (`/tcsi/setup`,
controller `thirdcode_accounting/controllers/setup.py`, service
`thirdcode.setup.service`) used to provision pilot companies, charts of
accounts, journals, open periods and named users idempotently. The plaintext
token is held by the operator outside the repository; only its SHA-256 lives in
the controller. Unauthorized attempts are logged and answered with 401; every
executed action is logged. Rotate the token or remove the endpoint once pilot
provisioning is finished.

Rollback: restore the last verified application deployment through the provider.
Keep database and filestore volumes intact. A code rollback does not roll back
database changes. Before customer onboarding, configure paired database and
filestore backups, test restoration into an isolated environment, and approve
retention/RPO/RTO. Do not import real company records until those gates pass.

## Future standalone architecture (not released)

### Verified pilot infrastructure — 2026-09-22

Railway's GitHub-linked engine deployment and GitHub quality gates passed.
Administrator authentication passed on the fresh pilot database. The separate
portal returned healthy responses; unfinished ledger APIs returned 404 and
unfinished pages redirected to the portal. Eight portal-boundary tests cover
the hosted restrictions, including missing preview configuration.

Both Railway volumes have DAILY backups with six-day retention, and manual
`Pilot launch baseline` snapshots exist. A logical database dump was restored
to an isolated database with the TCSI module installed and zero accounting
entries. A filestore archive was extracted and byte-compared successfully.
Only the disposable verification database and scratch files were removed.
The temporary deployment SSH key was revoked and deleted after verification.
These checks do not constitute a full on-premise recovery rehearsal or client
accounting acceptance.

The release author email must match an authorized Vercel team identity. The
owner confirmed `kurtgavin.design@gmail.com` for release commits; do not rewrite
shared Git history to change older authors. Keep concurrent frontend debugging
changes out of deployment until reviewed and tested. Customer acceptance and
the reported local interaction-freeze fix remain separate release gates.

The planned standalone product path is:

```text
Vercel (apps/web)  ->  Supabase Auth / Postgres / Storage
                           ^
Railway (apps/worker) -----+
```

The existing accounting engine remains the pilot's system of record until
the standalone workflows have accounting parity and receive acceptance.

## Supabase

For future standalone environments only, create a project per environment. Review the files in
`supabase/migrations/` using the Supabase CLI or the project SQL editor. The
foundation migration creates tenant-scoped accounting tables, membership
checks, role-aware write policies, immutable audit reads, and an idempotent job
run table.

Required web values:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

Required worker values:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` (Railway secret only; never a Vercel/browser value)

Run the Supabase security advisors after applying migrations. Every exposed
table must remain RLS-enabled, and policy changes must be reviewed with a
member of each workspace role. Configure point-in-time recovery and an
encrypted external backup destination before production acceptance; a database
being hosted by Supabase is not, by itself, an external backup plan.

## Vercel

Configure the project with root `apps/web` and these build settings:

- Install command: `cd ../.. && npm ci`
- Build command: `cd ../.. && npm run build:web`
- Node.js: `22.12` or newer
- Framework: Next.js

Set `NEXT_PUBLIC_APP_ENV`, `NEXT_PUBLIC_APP_URL`, and the two publishable
Supabase values in the Vercel environment settings. Preview and production
should use separate Supabase projects or explicit isolated environments.
Do not add `SUPABASE_SERVICE_ROLE_KEY` to Vercel. Attach the approved custom
domain so Vercel terminates HTTPS, then verify `/api/health` and
`/api/readiness` after each promotion. Pushes to `main` deploy through the
provider Git integrations: every commit produces a Vercel Production
deployment and a Railway engine deployment, both reported on the commit's
status. `/api/health` returns the deployed `commit` (the first 12 characters
of `VERCEL_GIT_COMMIT_SHA`), so an operator can confirm which revision is
serving without provider access; after a promotion, compare it with `git
rev-parse main`.

## Railway

Do not deploy the unfinished worker for the pilot. A future worker service uses
`docker/worker/Dockerfile`; it is a long-running Node 22
service, not a serverless request handler.

Set:

- `WORKER_ENV=production`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `WORKER_POLL_INTERVAL_MS`

Railway should probe `/health`, restart on failure, and keep `/ready` private
or protected by the platform network. The worker refuses to start in
production when its Supabase secrets are missing. `/ready` probes database
access with a 2.5-second timeout and no retries; it returns 503 on missing or
invalid configuration, dependency failure, or `scheduler_disabled`. There are
no released Node job handlers, so a reachable database is not enough to report
readiness. The former logging-only scheduler has been removed; the poll interval
setting is retained for configuration compatibility but currently does no work.
Odoo continues to own recurring accounting. Additional Node job actions,
schedules/timezones, company scope and destinations must be specified only if
the future standalone product acquires a requirement that Odoo does not already
serve. The current pilot requires no additional Node jobs; do not duplicate its
accounting schedules in this service.

Job claims use unique `(workspace_id, job_name, run_key)` values, with NULL
workspace IDs treated as one global scope. Retries must treat a duplicate key
in the same scope as an already-claimed run. Apply the job-claim migration
before deploying any future worker that uses this contract.

### Automation ownership for the current pilot

| Work | Owner and schedule | Scope and destination |
| --- | --- | --- |
| Configured recurring journals, customer invoices and supplier bills | Odoo's `Third Code: run recurring entries and invoices`, daily. Its actual next execution is the installed `ir.cron.nextcall`; the source does not promise a fixed local hour. | Active, due definitions; generated documents stay in each definition's company ledger. Existing accountant/administrator configuration and posting controls apply. No automatic customer email is added. |
| Grouped operational incident retention | Odoo's `TCSI Sentry: 90-day incident retention`, daily. | Removes expired diagnostic groups only; financial and operator audit records are retained. |
| Coordinated encrypted database and attachment backup | Existing `scripts/hosted_backup.py`, run by an external operator scheduler after recovery configuration. | Complete engine recovery bundle to a separate approved storage destination. Requires encryption certificate, storage, retention, operator/deputy and a maintenance window. A second ledger worker cannot capture the engine's filestore/process state safely. |
| Failed/missed backup and engine outage monitoring | Existing recovery monitor plus an independent external monitor. | Operator alert channel. The alert recipient and provider configuration are required; a process on the failed engine cannot establish that the engine is down. |

The hosted launcher enables one Odoo cron thread. The configured UTC timestamp
and scheduler user's timezone must be inspected in the deployed instance before
asserting a local execution hour. Recurrence intervals and due dates remain
definition-specific; no new templates, payments, reminders, tax submissions or
automatic period closes are created by this decision.

This resolves the worker-scope question for the current pilot. It does not prove
that hosted cron or external recovery jobs are enabled and running. Verify actual
job state, last/next runs, failures, recovery receipts and a failed-run alert at
release. A passing worker health endpoint is not evidence of those operations.

## CI and release gates

`.github/workflows/ci.yml` runs install, lint, typecheck, tests, migration
structure validation, the complete migration chain plus RLS/intake behavior in
disposable PostgreSQL, web/worker builds, and high-severity dependency audit.
Store deployment tokens only in provider/GitHub secret stores. A release is
not accepted until health/readiness for every deployed service, auth flow,
tenant isolation, responsive journeys, scheduled-job state and migration status
are checked. The intentionally undeployed Node worker is not a pilot service.

## Still required before client cutover

This repository now contains deployable foundations, but the following need
real client/provider decisions and cannot be invented in code:

- Supabase, Vercel, and Railway project IDs, domains, owners, and secrets;
- external encrypted backup destination, retention, RPO/RTO, and restore proof;
- tax/BIR/EIS configuration and signed report samples;
- authorized MYOB export, mapping, opening-balance reconciliation, and a
  parallel accounting month;
- production role matrix, named-user acceptance, security review, and go-live
  approval;
- approved ten-company topology and repeatable fresh-company/user provisioning;
- rerun the selected Odoo regression and synthetic full-scope checks against the
  exact reviewed release image before any customer cutover. Local synthetic
  invoice, payment, reconciliation, recurring, report, migration, and period
  workflows have been exercised; client acceptance and customer-host evidence
  remain separate gates.
# Customer-facing branding releases

The accounting engine retains its upstream package names, exception identifiers,
diagnostic traces, and license notices. TCSI branding is implemented through the
custom addon's inherited views and client patches, not by renaming engine code.
Customer-authored accounting records and messages must not be rewritten.

After deploying a branding manifest version change, upgrade only
`thirdcode_accounting` using the module administration API, after taking database
and filestore snapshots. Verify inherited views, login, menus, and report/email
templates afterward. A source deployment alone does not apply database view changes.
To roll back these view-only changes, deactivate the affected `thirdcode_accounting`
inherited views and redeploy the previous release; do not restore the database over
new customer transactions. Keep diagnostic error details intact for support.

Run `node --test scripts/test-branding.mjs` to check the branding mutation-loop
regression before deploying. The workspace observer must never rewrite unchanged
text, and human chat windows must retain their original identities.
