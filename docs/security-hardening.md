# Security hardening (production audit remediation)

This document records the fixes for the unauthenticated production audit of the
live TCSI accounting surface (`dogfood-output/prod-2026-10-04/REPORT.md`).
Findings are numbered as in that report.

The fixes live in two places:

- the accounting engine, `addons/thirdcode_accounting` (Odoo 18 addon);
- the public portal, `apps/web` (Next.js).

Nothing was applied to the live systems from the audit workspace: the engine
changes need an addon upgrade, and the portal changes need a deployment.

## What changed, per finding

| # | Finding | Fix |
| --- | --- | --- |
| H1 | Unknown login answered faster than a known one (account oracle) | `models/res_users.py` overrides `_login`: an unknown login is looked up first and, when absent, the credential is checked against a dummy hash so both paths pay one password hash |
| H2 | Reset/signup leaked whether an account exists, and printed the user's display name | `models/res_users.py` `reset_password` never raises (one uniform answer, detail logged); `controllers/auth.py` no longer redirects on a GET carrying `signup_email` |
| H3 | No login throttling; the stock cooldown is per worker process | `models/tcsi_auth_throttle.py` (new model `thirdcode.auth.throttle`) counts failures per address and per login in the database, committed on a cursor of its own; `res_users._assert_can_auth` enforces it before the password check |
| H4 | Session cookie without `Secure`/`SameSite` | `models/tcsi_cookie_policy.py` wraps both Odoo `set_cookie` implementations (`FutureResponse` and `_Response`), because the session cookie is written *after* the dispatcher and a header rewrite can never reach it; it forces `HttpOnly`, `SameSite=Lax` and - over TLS, proxy aware - `Secure`. `models/ir_http.py` keeps the header rewrite as defence in depth and shares the one "was this hop secure" helper |
| H5 | `/web/database/*` write endpoints answered 500 | `models/ir_http.py` refuses every `/web/database/*` path with a clean 404 before dispatch |
| H6 | Database manager UI reachable | same refusal, plus `list_db = False` and `proxy_mode = True` in `config/odoo.conf` |
| M1 | Portal soft-404s (unknown paths returned the home page with 200) | `apps/web/proxy.ts` lets unknown paths fall through to Next's real 404; `apps/web/app/not-found.tsx` renders it |
| M2 | Portal served HTML for `/robots.txt`, `/sitemap.xml`, `/apple-touch-icon.png` | `apps/web/app/robots.ts`, `apps/web/app/sitemap.ts`, `apps/web/public/apple-touch-icon.png` |
| M3 | No CSP on the portal, no HSTS/`Referrer-Policy`/`Permissions-Policy` on the engine | portal CSP with a per-request nonce in `apps/web/proxy.ts`; engine headers in `models/ir_http.py` (`Strict-Transport-Security` only over TLS) |
| M4 | `/api/readiness` took ~2 s | `apps/web/app/api/readiness/route.ts` probes the engine and the portal in parallel |
| M5 | `/tcsi/setup` accepted any caller with the token, no rate limit, echoed tracebacks | `controllers/setup.py`: optional address allowlist (`tcsi.setup_allow_ips`), shared failure throttle, token comparison on a digest, and a traceback only when `tcsi.setup_allow_debug` is enabled |
| M6 | Branding redirect carried a stray `?` and disagreed on the trailing slash | `controllers/webclient.py` normalises the redirect target to `/workspace` |
| M7 | Refused database-manager actions answered 200 | now a 404 like the rest of the path (see H5) |
| M8 | Portal `/favicon.ico` was a 404 | `apps/web/public/favicon.ico` |
| L1 | `/web/database/neutralize` answered 404 while its siblings answered 200/500 | uniform 404 (see H5) |
| L2 | `/websocket` answers 403 on the portal and 400 on the engine | informational; the engine answer comes from the websocket handler itself and is left as is |
| L3 | `/api/contact` 404 on the portal | no stale reference: the contact page posts to `/api/demo-requests` (verified) |
| L4 | Engine answered the branded HTML 404 for `/favicon.ico`, `/robots.txt`, `/sitemap.xml`, `/apple-touch-icon.png` | `controllers/assets.py` serves the real assets from `static/src/img/` and answers `/robots.txt` (disallow all) and an empty `/sitemap.xml` inline |

## Engine parameters

Set under *Settings → Technical → System Parameters* (or via the data file
`data/tcsi_security_data.xml`, loaded with `noupdate="1"`). `0` disables a limit;
an empty address list means "not restricted".

| Parameter | Default | Meaning |
| --- | --- | --- |
| `tcsi.auth.max_failures` | `10` | Failed logins per address before the cooldown |
| `tcsi.auth.window_seconds` | `900` | Observation window; `0` never resets the count |
| `tcsi.auth.block_seconds` | `900` | Cooldown length per address |
| `tcsi.auth.login_max_failures` | `5` | Failed logins per login name before the cooldown |
| `tcsi.auth.login_block_seconds` | `900` | Cooldown length per login name |
| `tcsi.auth.allow_ips` | empty | Addresses exempt from the throttle (health checks, office NAT) |
| `tcsi.db_manager_enabled` | `0` | Enables `/web/database/*` at all |
| `tcsi.db_manager_allow_ips` | empty | Addresses allowed to use the database manager when enabled |
| `tcsi.setup_allow_ips` | empty | Addresses allowed to call `/tcsi/setup` |
| `tcsi.setup.max_failures` / `tcsi.setup.block_seconds` | `10` / `3600` | Throttle for rejected `/tcsi/setup` calls |
| `tcsi.setup_allow_debug` | `0` | Returns a traceback with a failed `/tcsi/setup` call |
| `tcsi.security.hsts_max_age` | `31536000` | HSTS `max-age` when the request arrived over TLS |

## Deploying the engine fixes

1. Update the addon: `odoo -u thirdcode_accounting --stop-after-init`.
2. Keep `list_db = False` and `proxy_mode = True` in the runtime configuration,
   and set a real `admin_passwd` (the repository value is a local default).
3. The throttle needs one table (`thirdcode_auth_throttle`) and no cron: counters
   are written on the login path and pruned opportunistically.
4. Keep the engine behind the TLS-terminating proxy with `proxy_mode = True`: the
   throttle keys on the client address, and without it every request carries the
   proxy's address, so one attacker's failures would lock out all users. The same
   setting is what makes `X-Forwarded-Proto` trustworthy for the cookie and HSTS
   logic (the code reads it directly as well, so the headers hold either way).

## Verifying

Locally, with the pinned runtime image (the same one CI uses):

```
docker compose build odoo
docker network create tcsi-verify
docker run -d --name tcsi-verify-db --network tcsi-verify \
  -e POSTGRES_USER=odoo -e POSTGRES_PASSWORD=verify-only -e POSTGRES_DB=postgres \
  postgres:16-alpine
docker run --rm --network tcsi-verify --entrypoint odoo accounting-system-odoo:latest \
  --db_host=tcsi-verify-db --db_user=odoo --db_password=verify-only \
  -d tcsi_verify --addons-path=/opt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons \
  -i thirdcode_accounting --without-demo=all --test-enable \
  --test-tags /thirdcode_accounting --stop-after-init --no-http --max-cron-threads=0
```

`addons/thirdcode_accounting/tests/test_auth_hardening.py` covers the throttle
(counting, blocking, clearing, window reset, disabled limit), the login oracle
helpers, the silent password reset, and the header/cookie helpers. The HTTP
behaviour that needs a live server (database-manager refusal, header and cookie
rewriting, `/favicon.ico`, `/robots.txt`) is checked by hand against a running
instance; CI installs with `--no-http`, so it cannot assert it there.

Portal checks: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`
in the repository root.
