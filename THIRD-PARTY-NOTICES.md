# Third-party notices

The accounting engine image (`docker/odoo/Dockerfile`) ships the software below
unmodified, at the pinned versions shown. Each component keeps its own licence.
TCSI's own code is covered by [LICENSE](LICENSE).

## Accounting engine image

| Component | Source | Pinned version | Licence |
| --- | --- | --- | --- |
| Odoo Community 18.0 (base image `odoo:18.0`) | https://github.com/odoo/odoo | image digest in `docker/odoo/Dockerfile` | LGPL-3.0 |
| `auditlog` | https://github.com/OCA/server-tools | `OCA_SERVER_TOOLS_COMMIT` | AGPL-3.0 |
| `date_range` | https://github.com/OCA/server-ux | `OCA_SERVER_UX_COMMIT` | LGPL-3.0 |
| `report_xlsx`, `report_xlsx_helper` | https://github.com/OCA/reporting-engine | `OCA_REPORTING_ENGINE_COMMIT` | AGPL-3.0 |
| `account_financial_report`, `partner_statement` | https://github.com/OCA/account-financial-reporting | `OCA_FINANCIAL_REPORTING_COMMIT` | AGPL-3.0 |
| `account_statement_base`, `account_reconcile_model_oca` | https://github.com/OCA/account-reconcile | `OCA_ACCOUNT_RECONCILE_COMMIT` | LGPL-3.0 |
| `account_reconcile_oca`, `account_statement_reconcile_status` | https://github.com/OCA/account-reconcile | `OCA_ACCOUNT_RECONCILE_COMMIT` | AGPL-3.0 |
| Backup SDK: `boto3`, `botocore`, `s3transfer` | https://github.com/boto | `docker/odoo/backup-requirements.txt` | Apache-2.0 |
| Backup SDK: `jmespath`, `six`, `urllib3` | PyPI | `docker/odoo/backup-requirements.txt` | MIT |
| Backup SDK: `python-dateutil` | PyPI | `docker/odoo/backup-requirements.txt` | Apache-2.0 / BSD-3-Clause |

The commit variables are the `ARG` values at the top of `docker/odoo/Dockerfile`.

Licence texts:

- AGPL-3.0: https://www.gnu.org/licenses/agpl-3.0.txt
- LGPL-3.0: https://www.gnu.org/licenses/lgpl-3.0.txt
- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0

## Portal and worker

The Node.js packages used by `apps/web` and `apps/worker` are listed, with
exact versions, in `package-lock.json`. Each package keeps the licence its
`package.json` declares.

## Hosted services

PostgreSQL, Supabase, Railway and Vercel are run as services and are not
distributed with this repository.
