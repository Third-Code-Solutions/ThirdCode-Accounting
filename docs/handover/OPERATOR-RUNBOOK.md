# TCSI Accounting — operator runbook

For the client IT operator who runs one independent installation. It covers
install, first sign-in, daily checks, backup, upgrade, rollback, recovery and
credential rotation. It links to the detailed procedures in
[`platform-deployment.md`](../platform-deployment.md) instead of repeating them.

Hosted-pilot material elsewhere in `docs/` (Vercel, Railway, Supabase,
`tcsi-accounting-portal.vercel.app`) describes TCSI's own historical
environment. It does not apply to your installation.

## 1. What you receive

| Item | Where |
| --- | --- |
| Application image, pinned by digest (`registry/…@sha256:…`) or an offline `docker image save` archive | Release note from TCSI |
| Source revision (40-character Git SHA) matching that image | Release note from TCSI |
| Compose definition | `docker-compose.independent.yml` |
| Environment template | `config/independent.env.example` |
| Reference TLS proxy | `config/tls-proxy.nginx.example` |
| End-user guide | `docs/userguide.md` / `docs/userguide.pdf` |

Keep the exact image available for as long as you keep backups. The restore
procedure refuses a different image.

TCSI hands over source as a clean export of the released revision
(`git archive <sha>` or a fresh clone), never a copy of a working folder: local
folders can hold ignored test output and probe artefacts.

## 2. Host requirements

- 64-bit Linux host with Docker Engine and the Compose v2 plugin.
- At least 2 vCPU, 4 GB RAM and enough disk for the database, attachments,
  logs (bounded to 5 × 20 MB per container) and local backup staging.
- A DNS name and a TLS certificate for it.
- A second location (another device, site or object store) for backup copies.

`docker-compose.yml` and `config/odoo.conf` are a development stack with fixed
local passwords. Never use them for real books.

## 3. Install

1. Load the image (`docker pull <digest>` or `docker load -i <archive>`).
2. Copy `config/independent.env.example` to protected storage outside Git,
   for example `/private/tcsi.env` with mode `0600`. Set a unique
   `COMPOSE_PROJECT_NAME`, database name and loopback `ODOO_PORT`. Generate
   separate random passwords of at least 24 characters for
   `PG_ADMIN_PASSWORD`, `PGPASSWORD`, `TCSI_ADMIN_PASSWORD` and
   `TCSI_MASTER_PASSWORD`. Set `TCSI_ODOO_IMAGE` to the image digest.
3. Start: `docker compose --env-file /private/tcsi.env -f docker-compose.independent.yml up -d`.
   First boot installs the accounting modules and can take more than ten
   minutes. Wait until `docker compose … ps` shows `odoo` as `healthy`.
4. Install the TLS proxy from `config/tls-proxy.nginx.example`. It must
   overwrite `Host` and every `X-Forwarded-*` header, buffer request bodies,
   pass WebSocket upgrades on `/websocket`, and deny `/jsonrpc` and
   `/xmlrpc/db`. The engine trusts these headers for client addresses, so a
   proxy that passes client values through lets anyone fake their IP. Run
   `nginx -t`, then reload. If you use another proxy (Caddy, Traefik, a load
   balancer), reproduce the same rules.
5. Fix the public address: sign in (section 4) through the public HTTPS name,
   open `https://<your-host>/web?debug=1`, then **Settings → Technical →
   System Parameters**. Set `web.base.url` to `https://<your-host>` and create
   `web.base.url.freeze` = `True`. Links in emails and PDFs use this value.
6. Protect operator sign-in. After five failed attempts an account is locked
   for 15 minutes, whoever made them, so anyone who knows the system-owner
   login can keep it locked. In the same System Parameters screen set
   `tcsi.auth.allow_ips` to a comma-separated list of the fixed addresses your
   administrators sign in from. Those addresses skip the lockout.

Never run `docker compose … down --volumes`: it deletes the books.

## 4. First sign-in and company setup

1. Open `https://<your-host>/web/login` and sign in with `TCSI_ADMIN_LOGIN` /
   `TCSI_ADMIN_PASSWORD`. This is the system-owner account. It opens the
   **Platform Console** and is not a bookkeeping account.
2. Change that password in the user menu (**My Profile → Account Security**).
   The environment value is used only on the very first boot (section 9).
3. **Platform Console → Create organization**: legal name, country, book
   currency, first company Administrator. Give that person their credentials
   privately; no email is sent. New organizations start as trials (prints
   marked TRIAL COPY); use **Activate** before entering real books. The list
   also shows the installation's default company ("Third Code Solutions
   Inc.") as a trial with no people; it holds no books, so leave it unused.
4. The company Administrator signs in and creates one account per person
   (Accountant, Encoder, Read-only) under **Organizations → employees** or
   **People**. Details: [`platform-console.md`](../platform-console.md).
5. Run the read-only readiness check as the company Administrator. It prompts
   for the password, or reads `TCSI_ODOO_PASSWORD`:

   ```bash
   python3 scripts/check_company_readiness.py --url https://<your-host> \
     --database <PGDATABASE> --login <company-admin-login> \
     --expected-companies 1 --expected-country-code PH --expected-currency-code PHP
   ```

   Add `--trial` only for a demonstration company. Real books must pass
   without it. Legal, tax, BIR/EIS and report-sample approvals are client
   decisions; the check reports them, it does not make them.

## 5. Daily and weekly checks

| Check | How | Act when |
| --- | --- | --- |
| Engine health | `curl -fsS https://<your-host>/web/health` | non-200 or timeout |
| Containers | `docker compose … ps` | `odoo` not `healthy`, or restarting |
| Errors | **Platform Console → Sentry** (server incidents), `docker compose … logs --since 24h odoo` | new incident group or repeated tracebacks |
| Scheduled jobs | **Platform Console → Sentry → scheduled jobs** | job failing or not advancing |
| Disk | `df -h` on the Docker data root and backup staging | above 80 % |
| Certificate | expiry date of the TLS certificate | under 21 days |
| Backup | newest verified backup age (section 6) | older than your RPO |

Wire these into whatever monitoring you already run; the installation does
not page anyone by itself.

## 6. Backup

Use the coordinated procedure in
[platform-deployment.md → Coordinated independent backup and isolated restore](../platform-deployment.md#coordinated-independent-backup-and-isolated-restore).
It pauses only the Odoo writer, captures the database and the matching
attachment filestore, records accounting fingerprints, then restarts Odoo.

Schedule it yourself. Save the backup block as a root-owned script, for example
`/usr/local/sbin/tcsi-backup`, and run it nightly from cron or a systemd timer
outside business hours. Then:

1. Encrypt each completed backup directory before it leaves the host (for
   example `tar -C <root> -cf - <dir> | gpg --encrypt --recipient <key>`),
   and keep the private key off the host.
2. Copy the encrypted file to the second location and verify its checksum.
3. Alert when the job exits non-zero or the newest copy is older than your RPO.
4. Delete local and remote copies only by your approved retention policy.
   Statutory retention for accounting records is a client decision.
5. Rehearse an isolated restore (same section) at least quarterly.

An optional built-in encrypted S3 schedule exists (`TCSI_BACKUP_*` variables,
[RECOVERY-AUTOMATION.md](../prd-alignment-2026-10-05/RECOVERY-AUTOMATION.md)).
It runs daily at 03:00 Asia/Singapore with 30-day retention. If you enable it,
also run its freshness check hourly from the host and alert on a non-zero exit:

```bash
docker compose --env-file /private/tcsi.env -f docker-compose.independent.yml \
  run --rm --no-deps odoo python3 /opt/tcsi/backup_runtime.py monitor
```

## 7. Upgrade

The launcher upgrades the accounting module automatically before serving
requests, and refuses to start an image older than the database.

1. Read the release note: new image digest, source revision, any manual steps.
2. Take a coordinated backup (section 6) and confirm it completed.
3. Set the new `TCSI_ODOO_IMAGE` (and `TCSI_RELEASE_*` if used) in the env file.
4. `docker compose --env-file /private/tcsi.env -f docker-compose.independent.yml up -d odoo`
5. Wait for `healthy`. The module upgrade runs first; a failed upgrade keeps
   the engine unhealthy instead of serving requests.
6. Run the readiness check (section 4), sign in as each role, and open an
   invoice PDF and a financial report.

Upgrade PostgreSQL only within the same major version unless TCSI supplies a
migration procedure. Restores compare the exact PostgreSQL image recorded with
each backup, so keep the previous image until older backups expire.

## 8. Rollback and disaster recovery

**Rollback after a failed upgrade.** Older images refuse a database that has
already been upgraded, so pointing `TCSI_ODOO_IMAGE` back is not a rollback.
If no one has entered transactions since the upgrade, restore the pre-upgrade
backup with the previous image. If transactions were entered, keep the data
and ask TCSI for a forward fix; never restore over newer accounting entries.

**Recover from a lost or damaged installation.**

1. Restore the newest verified backup into a new, isolated project with the
   procedure in `platform-deployment.md`. Its Odoo service stays stopped.
2. Review the move, per-account balance and attachment comparison it prints.
3. Promote it: give the target env file the production `ODOO_PORT` (stop the
   old project first if it still runs), then start it with
   `docker compose --env-file /private/target.env -f docker-compose.independent.yml up -d`.
4. Wait for `healthy`, confirm `web.base.url` (section 3, step 5), and run the
   readiness check.
5. Keep the old project's volumes until the client accepts the recovered books.

## 9. Credentials and rotation

| Secret | Used | Rotate by |
| --- | --- | --- |
| `TCSI_ADMIN_PASSWORD` | First boot only, sets the system-owner password | Change the password in the application. Keep a value of at least 24 characters in the env file; the launcher refuses shorter ones |
| `TCSI_MASTER_PASSWORD` | Database manager (`/web/database`), regenerated into the config at every start | Edit the env file, then `up -d odoo` |
| `PGPASSWORD` | Odoo's restricted database role, reconciled by `db-init` at every start | Edit the env file, then `up -d` |
| `PG_ADMIN_PASSWORD` | PostgreSQL bootstrap administrator | `ALTER ROLE … PASSWORD …` inside the `db` container, then update the env file |
| User passwords | Each person | Company Administrator: **People → Reset password** |
| `TCSI_BACKUP_S3_*` | Optional S3 backup | Issue a new bucket-only key, update the env file, `up -d odoo`, revoke the old key |

Store the env file and backup decryption key in your password manager or
secret store. Do not reuse credentials between installations.

## 10. Support and escalation

The client names its two rows at kickoff; TCSI names the deputy before
go-live. Keep this table with the runbook.

| Role | Name | Contact | Hours |
| --- | --- | --- | --- |
| Client system owner | Named by the client at kickoff | | |
| Client accounting lead | Named by the client at kickoff | | |
| Backup and restore owner | Kurt Gavin (TCSI) | Through TCSI support | Agreed at kickoff |
| Backup and restore deputy | Named by TCSI before go-live | Through TCSI support | Agreed at kickoff |
| TCSI support | Third Code Solutions Inc. | https://www.thirdcodesolutions.com; security issues: security@thirdcodesolutions.com | Agreed at kickoff |

When reporting a problem, include the time, the user and role, the screen URL,
the exact message, and the incident reference from **Platform Console →
Sentry** if one exists. Never send passwords, env files or backup keys.

## 11. Licences

TCSI's own code is proprietary; see [LICENSE](../../LICENSE). The accounting
addon (`addons/thirdcode_accounting`) is the exception: it is AGPL-3, as its
`__manifest__.py` declares, because it extends AGPL-3 OCA modules. Odoo
Community, the pinned OCA modules and their licences are listed in
[THIRD-PARTY-NOTICES.md](../../THIRD-PARTY-NOTICES.md). Review these
obligations before redistributing the image or offering it as a hosted
service.
