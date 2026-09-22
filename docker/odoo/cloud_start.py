"""Start a single-database pilot with secrets supplied by the hosting platform."""
import configparser
import os
import pathlib
import pwd
import re
import subprocess
import tempfile
import time

import psycopg2


def required(name):
    value = os.environ.get(name, "").strip()
    if not value or "\n" in value or "\r" in value:
        raise RuntimeError(f"Missing or invalid {name}")
    return value


def main():
    database = required("PGDATABASE")
    if not re.fullmatch(r"[a-zA-Z0-9_]+", database):
        raise RuntimeError("Invalid database name")
    admin_password = required("TCSI_ADMIN_PASSWORD")
    required("TCSI_ADMIN_LOGIN")
    master_password = required("TCSI_MASTER_PASSWORD")
    if min(len(admin_password), len(master_password)) < 24:
        raise RuntimeError("Production passwords must be at least 24 characters")
    data = pathlib.Path("/var/lib/odoo")
    data.mkdir(parents=True, exist_ok=True)
    if os.getuid() == 0:
        account = pwd.getpwnam("odoo")
        os.chown(data, account.pw_uid, account.pw_gid)
        os.setgroups([])
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
    options = {
        "db_host": required("PGHOST"),
        "db_port": os.environ.get("PGPORT", "5432"),
        "db_user": required("PGUSER"),
        "db_password": required("PGPASSWORD"),
        "db_name": database,
        "dbfilter": f"^{database}$",
        "admin_passwd": master_password,
        "data_dir": str(data),
        "addons_path": "/opt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons",
        "list_db": "False",
        "proxy_mode": "True",
        "workers": "0",
        "max_cron_threads": "1",
        "db_maxconn": "16",
        "http_port": os.environ.get("PORT", "8069"),
        "without_demo": "all",
        "log_level": "info",
    }
    config = configparser.ConfigParser(interpolation=None)
    config["options"] = options
    with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as output:
        config.write(output)
        config_path = output.name
    os.chmod(config_path, 0o600)
    connection = None
    for attempt in range(30):
        try:
            connection = psycopg2.connect(
                host=options["db_host"], port=options["db_port"],
                user=options["db_user"], password=options["db_password"],
                dbname=database, connect_timeout=5,
            )
            break
        except psycopg2.OperationalError:
            if attempt == 29:
                raise RuntimeError("Database connection unavailable") from None
            time.sleep(2)
    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('public.ir_module_module')")
        installed = cursor.fetchone()[0] is not None
        if installed:
            cursor.execute("SELECT state FROM ir_module_module WHERE name = %s", ("thirdcode_accounting",))
            module = cursor.fetchone()
            installed = module is not None and module[0] == "installed"
    connection.close()
    base = ["odoo", "-c", config_path, "-d", database]
    if not installed:
        subprocess.run(base + ["-i", "thirdcode_accounting", "--without-demo=all", "--no-http", "--stop-after-init"], check=True)
    # Persist the first-admin marker in the database, so restarts and restores
    # never reset an existing administrator's credentials.
    bootstrap = '''
import os
params = env['ir.config_parameter'].sudo()
if not params.get_param('tcsi.cloud_bootstrapped'):
    admin = env.ref('base.user_admin')
    admin.write({'login': os.environ['TCSI_ADMIN_LOGIN'], 'password': os.environ['TCSI_ADMIN_PASSWORD']})
    group = env.ref('thirdcode_accounting.group_thirdcode_administrator')
    admin.write({'groups_id': [(4, group.id)]})
    params.set_param('auth_signup.invitation_scope', 'b2b')
    params.set_param('tcsi.cloud_bootstrapped', '1')
    env.cr.commit()
'''
    subprocess.run(["odoo", "shell", "-c", config_path, "-d", database, "--no-http"], input=bootstrap, text=True, check=True)
    os.execvp("odoo", base)


if __name__ == "__main__":
    main()
