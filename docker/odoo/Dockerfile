FROM odoo:18.0@sha256:478065867b945579649373aa4cca3b56f7b74daf0522e5fdf85e7d1262e11d39

USER root

ARG INSTALL_ODOO_TEST_HELPER=false
ARG OCA_SERVER_TOOLS_COMMIT=60cd54e5ee8f6538a14266af8a7b3d1da0af08ec
ARG OCA_SERVER_UX_COMMIT=5a67ed407c07160ee1b4fc74b8d2e6eb5507fa2b
ARG OCA_REPORTING_ENGINE_COMMIT=7a156caae6558276408854ef26b729331e974361
ARG OCA_FINANCIAL_REPORTING_COMMIT=95c63a6930a174699148fc55fcdb334f54ad94df
ARG OCA_ACCOUNT_RECONCILE_COMMIT=8a24fc4dd6cc341120045a4330536866a9972d84

RUN apt-get update \
    && apt-get install --no-install-recommends --yes ca-certificates git \
    && rm -rf /var/lib/apt/lists/* \
    && git init /opt/oca-server-tools \
    && git -C /opt/oca-server-tools remote add origin https://github.com/OCA/server-tools.git \
    && git -C /opt/oca-server-tools fetch --depth 1 origin "${OCA_SERVER_TOOLS_COMMIT}" \
    && git -C /opt/oca-server-tools checkout --detach FETCH_HEAD \
    && git init /opt/oca-server-ux \
    && git -C /opt/oca-server-ux remote add origin https://github.com/OCA/server-ux.git \
    && git -C /opt/oca-server-ux fetch --depth 1 origin "${OCA_SERVER_UX_COMMIT}" \
    && git -C /opt/oca-server-ux checkout --detach FETCH_HEAD \
    && git init /opt/oca-reporting-engine \
    && git -C /opt/oca-reporting-engine remote add origin https://github.com/OCA/reporting-engine.git \
    && git -C /opt/oca-reporting-engine fetch --depth 1 origin "${OCA_REPORTING_ENGINE_COMMIT}" \
    && git -C /opt/oca-reporting-engine checkout --detach FETCH_HEAD \
    && git init /opt/oca-account-financial-reporting \
    && git -C /opt/oca-account-financial-reporting remote add origin https://github.com/OCA/account-financial-reporting.git \
    && git -C /opt/oca-account-financial-reporting fetch --depth 1 origin "${OCA_FINANCIAL_REPORTING_COMMIT}" \
    && git -C /opt/oca-account-financial-reporting checkout --detach FETCH_HEAD \
    && git init /opt/oca-account-reconcile \
    && git -C /opt/oca-account-reconcile remote add origin https://github.com/OCA/account-reconcile.git \
    && git -C /opt/oca-account-reconcile fetch --depth 1 origin "${OCA_ACCOUNT_RECONCILE_COMMIT}" \
    && git -C /opt/oca-account-reconcile checkout --detach FETCH_HEAD \
    && mkdir -p /opt/extra-addons \
    && cp -a /opt/oca-server-tools/auditlog /opt/extra-addons/auditlog \
    && cp -a /opt/oca-server-ux/date_range /opt/extra-addons/date_range \
    && cp -a /opt/oca-reporting-engine/report_xlsx /opt/extra-addons/report_xlsx \
    && cp -a /opt/oca-reporting-engine/report_xlsx_helper /opt/extra-addons/report_xlsx_helper \
    && cp -a /opt/oca-account-financial-reporting/account_financial_report /opt/extra-addons/account_financial_report \
    && cp -a /opt/oca-account-financial-reporting/partner_statement /opt/extra-addons/partner_statement \
    && cp -a /opt/oca-account-reconcile/account_statement_base /opt/extra-addons/account_statement_base \
    && cp -a /opt/oca-account-reconcile/account_reconcile_model_oca /opt/extra-addons/account_reconcile_model_oca \
    && cp -a /opt/oca-account-reconcile/account_reconcile_oca /opt/extra-addons/account_reconcile_oca \
    && cp -a /opt/oca-account-reconcile/account_statement_reconcile_status /opt/extra-addons/account_statement_reconcile_status

COPY addons /opt/extra-addons
COPY docker/odoo/cloud_start.py /opt/tcsi/cloud_start.py

RUN chown -R odoo:odoo /opt/extra-addons /opt/oca-server-tools /opt/oca-server-ux /opt/oca-reporting-engine /opt/oca-account-financial-reporting /opt/oca-account-reconcile

COPY docker/odoo/test-requirements.txt /tmp/tcsi-odoo-test-requirements.txt
RUN if [ "$INSTALL_ODOO_TEST_HELPER" = "true" ]; then \
        python3 -m pip install --disable-pip-version-check --no-cache-dir --no-deps --require-hashes --target /opt/tcsi-test-deps -r /tmp/tcsi-odoo-test-requirements.txt; \
    fi \
    && rm -f /tmp/tcsi-odoo-test-requirements.txt

USER odoo
