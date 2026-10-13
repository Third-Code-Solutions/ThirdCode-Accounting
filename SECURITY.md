# Security Policy

## Supported versions

This repository ships the TCSI accounting platform: the Odoo 18 addon
`addons/thirdcode_accounting`, the hosted workspace portal (`apps/web`), the
background worker (`apps/worker`) and the shared contracts package
(`packages/contracts`).

Security fixes are applied to the `main` branch and released from there. Only
the latest released revision of the addon is supported; back-ports are
considered case by case for the independent release line.

## Reporting a vulnerability

**Do not open a public issue, pull request or Discord message for a suspected
vulnerability.**

Report privately through either channel:

1. GitHub private vulnerability reporting:
   <https://github.com/Third-Code-Solutions/ThirdCode-Accounting/security/advisories/new>
2. Email: **security@thirdcodesolutions.com**

Please include, as far as you can:

- the affected component (addon model / portal route / worker job / deployment),
- the revision or deployed URL where you observed it,
- reproduction steps or a proof of concept,
- the impact you believe it has (data exposure, privilege escalation,
  financial-integrity impact, denial of service),
- whether the issue is already public anywhere.

Never include real tenant data, live credentials, access tokens or personal
information of third parties in a report. Redact secrets; we will ask for them
through a secure channel if they are required to reproduce the issue.

## What to expect

- Acknowledgement of the report within 3 business days.
- An initial assessment (severity, affected versions, whether a fix is
  warranted) within 10 business days.
- Progress updates at least every 10 business days until the issue is closed.
- Credit in the release notes if you want it, once a fix has shipped.

We ask that you give us the timeframes above to ship a fix before any public
disclosure, and that you do not access, modify or exfiltrate data that is not
yours while testing.

## Scope

In scope:

- record-rule, group and access-control flaws in the Odoo addon
  (`addons/thirdcode_accounting`),
- authentication, session and authorization flaws in the portal and worker,
- token/secret handling, SSRF, injection and unsafe deserialization,
- multi-company or multi-tenant isolation failures,
- recovery/backup automation flaws that could corrupt or expose financial data.

Out of scope:

- findings that require a compromised administrator account or physical access,
- vulnerabilities in third-party dependencies with no exploitable path in this
  platform (report those to the upstream project, or let Dependabot track them),
- spam, social-engineering and physical-security reports,
- missing hardening headers with no demonstrated impact,
- automated-scanner output without a working reproduction.

## Handling secrets

Credentials are read from environment variables and are never committed. If you
find a secret committed anywhere in the repository or its history, report it
through the private channels above instead of opening an issue — it will be
rotated and purged.
