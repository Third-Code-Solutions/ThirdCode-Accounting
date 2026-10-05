"""Fresh-target isolated PostgreSQL/Odoo recovery verification.

Consumes a verified decrypted payload, never its archived runtime credentials.
Retains the created database and private evidence on success or failure. It never
drops databases, overwrites existing directories, starts HTTP, or approves RTO.
Run on a dedicated recovery host with outbound traffic blocked except local DB.
"""
import argparse
import configparser
import ctypes
import json
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import sys
import time

import hosted_backup as capture
import recovery_fingerprint as fingerprints


class RestoreError(Exception):
    """Fixed public diagnostic codes only."""


def require(condition, code):
    if not condition:
        raise RestoreError(code)


def load_policy(path):
    policy = json.loads(capture.private_read(path))
    require(policy.get("format") == 1 and policy.get("isolated_host_confirmed") is True
            and policy.get("egress_isolation_confirmed") is True, "isolated_recovery_host_required")
    pg = validate_postgres(policy.get("postgres", {}))
    require(re.fullmatch(r"[0-9a-f]{40}", policy.get("source_revision", "")), "source_revision_required")
    require(re.fullmatch(r"[^\s]+@sha256:[0-9a-f]{64}", policy.get("image_reference", "")), "immutable_image_required")
    require(re.fullmatch(r"18\.0\.[0-9.]+", policy.get("addon_version", "")), "addon_version_required")
    require(type(policy.get("timeout_seconds")) is int and 30 <= policy["timeout_seconds"] <= 14400, "invalid_restore_deadline")
    paths = policy.get("addons_path")
    require(isinstance(paths, list) and paths and all(isinstance(p, str) and Path(p).is_absolute()
            and Path(p).is_dir() and not Path(p).is_symlink() and "," not in p and "\n" not in p for p in paths), "explicit_addons_required")
    return policy


def validate_postgres(pg):
    require(isinstance(pg, dict) and set(pg) == {"host", "port", "user", "password"}, "unexpected_postgres_options")
    require(pg.get("host") in ("127.0.0.1", "::1"), "loopback_postgres_required")
    require(type(pg.get("port")) is int and 1 <= pg["port"] <= 65535, "invalid_postgres_port")
    require(all(isinstance(pg.get(key), str) and pg[key] and "\n" not in pg[key]
                and "\r" not in pg[key] and "\x00" not in pg[key] for key in ("user", "password")), "private_postgres_credentials_required")
    require(not any(os.environ.get(name) for name in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGSYSCONFDIR")),
            "ambient_postgres_routing_forbidden")
    return pg


def validate_target(target, confirmation, source):
    require(bool(re.fullmatch(r"tcsi_alignment_restore_[0-9a-f]{32}", target))
            and confirmation == target and target != source, "fresh_disposable_target_confirmation_required")


def connect(policy, database, readonly=False):
    pg = validate_postgres(policy["postgres"])
    import psycopg2
    connection = psycopg2.connect(dbname=database, host=pg["host"], hostaddr=pg["host"],
        port=pg["port"], user=pg["user"], password=pg["password"], connect_timeout=5,
        sslmode="disable", options="-c statement_timeout=30000 -c lock_timeout=1000")
    try:
        connection.set_session(readonly=readonly, isolation_level="REPEATABLE READ")
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), inet_server_addr()::text, inet_server_port()")
            require(cursor.fetchone() == (database, pg["host"], pg["port"]), "postgres_endpoint_mismatch")
    except BaseException:
        connection.close()
        raise
    return connection


def _watch_command(command, environment, timeout, log, lease, result_fd):
    """Independent owner: lease EOF covers an uncatchable caller SIGKILL."""
    child, status = None, "failed"
    try:
        os.setsid()
        # The watchdog must outlive its caller's signals to clean its own group.
        signal.signal(signal.SIGALRM, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        if select.select([lease], [], [], 0)[0] and os.read(lease, 1) == b"":
            return
        parent = os.getpid()
        libc = ctypes.CDLL(None, use_errno=True)
        def guard():
            if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0 or os.getppid() != parent:
                os._exit(121)
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                 env=environment, start_new_session=True, preexec_fn=guard)
        deadline = time.monotonic() + max(.01, timeout)
        while True:
            # Keep the leader unreaped until group cleanup, reserving its PID and
            # preventing an unrelated recycled process group from being signalled.
            exited = os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            if exited is not None:
                status = "success" if exited.si_code == os.CLD_EXITED and exited.si_status == 0 else "failed"
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                status = "timeout"
                break
            if select.select([lease], [], [], min(.05, remaining))[0] and os.read(lease, 1) == b"":
                status = "parent_gone"
                break
    except BaseException:
        status = "failed"
    finally:
        if child is not None:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                child.wait(timeout=5)
            except BaseException:
                status = "failed"
        try:
            os.write(result_fd, status.encode())
        except OSError:
            pass  # Caller may already be dead; cleanup above still ran.
        os._exit(0)


def run_owned(command, environment, timeout, log_path):
    """Bounded Linux process groups, independent parent-death cleanup, private log."""
    require(sys.platform == "linux", "linux_process_guards_required")
    with log_path.open("xb") as log:
        lease_read, lease_write = os.pipe2(os.O_CLOEXEC)
        result_read, result_write = os.pipe2(os.O_CLOEXEC)
        try:
            watcher = os.fork()
        except BaseException:
            for descriptor in (lease_read, lease_write, result_read, result_write):
                os.close(descriptor)
            raise
        if watcher == 0:
            os.close(lease_write)
            os.close(result_read)
            _watch_command(command, environment, timeout, log, lease_read, result_write)
        os.close(lease_read)
        os.close(result_write)
        try:
            ready = select.select([result_read], [], [], max(.01, timeout) + 10)[0]
            require(bool(ready), "isolated_watchdog_deadline")
            status = os.read(result_read, 32).decode()
            if status == "timeout":
                raise subprocess.TimeoutExpired(command[0], timeout)
            require(status == "success", "isolated_command_failed")
        finally:
            os.close(lease_write)
            os.close(result_read)
            deadline = time.monotonic() + 6
            while True:
                waited, _status = os.waitpid(watcher, os.WNOHANG)
                if waited:
                    break
                require(time.monotonic() < deadline, "isolated_watchdog_cleanup_failed")
                time.sleep(.02)


ODOO_PROBE = r'''
import json, smtplib, sys
def denied(*args, **kwargs):
    raise RuntimeError('recovery_outbound_mail_denied')
smtplib.SMTP = denied
smtplib.SMTP_SSL = denied
import odoo
from odoo import api
configuration, database, version, output = sys.argv[1:]
odoo.tools.config.parse_config(['-c', configuration, '-d', database, '--no-http', '--max-cron-threads', '0'])
assert odoo.tools.config['http_enable'] is False
assert odoo.tools.config['max_cron_threads'] == 0
registry = odoo.registry(database)
with registry.cursor() as cursor:
    env = api.Environment(cursor, 1, {})
    assert cursor.dbname == database
    assert env['ir.module.module'].search([('name', '=', 'thirdcode_accounting'), ('state', '=', 'installed')]).latest_version == version
    assert not env['ir.cron'].search_count([('active', '=', True)])
    assert not env['ir.mail_server'].search_count([('active', '=', True)])
    # Read actual ORM rows without performing business operations or upgrades.
    companies = env['res.company'].search_count([])
    moves = env['account.move'].search_count([])
    cursor.rollback()
with open(output, 'x') as stream:
    json.dump({'registry_loaded': True, 'companies': companies, 'moves': moves,
               'addon_version': version, 'http_started': False, 'outbound_mail_enabled': False}, stream)
'''


def neutralize(connection):
    with connection.cursor() as cursor:
        cursor.execute("UPDATE ir_cron SET active=false WHERE active")
        cursor.execute("UPDATE ir_mail_server SET active=false WHERE active")
    connection.commit()


def write_configuration(policy, output, target):
    config = configparser.ConfigParser(interpolation=None)
    pg = policy["postgres"]
    config["options"] = {
        "db_host": pg["host"], "db_port": str(pg["port"]), "db_user": pg["user"], "db_password": pg["password"],
        "db_name": target, "dbfilter": "^" + target + "$", "list_db": "False", "workers": "0",
        "max_cron_threads": "0", "http_enable": "False", "http_interface": "127.0.0.1",
        "data_dir": str(output / "data"), "addons_path": ",".join(policy["addons_path"]),
        "smtp_server": "127.0.0.1", "smtp_port": "1", "smtp_user": "False", "smtp_password": "False",
        "smtp_ssl": "False", "server_wide_modules": "base",
    }
    path = output / "isolated.conf"
    with path.open("x") as stream:
        config.write(stream)
    path.chmod(0o600)
    return path


def restore(policy, payload, output, target, confirmation, manifest_sha256):
    started, created = time.monotonic(), False
    result = {"status": "failed", "target": target, "database_created": False,
              "database_restore_verified": False, "ledger_conservation_verified": False,
              "attachment_conservation_verified": False, "odoo_registry_verified": False,
              "production_database_connected": False, "rto_met": None,
              "operator_handover_verified": False, "runtime_image_independently_verified": False}
    output, payload = Path(output), Path(payload)
    deadline = started + policy["timeout_seconds"]
    try:
        require(sys.platform == "linux", "linux_process_guards_required")
        require(not any(os.environ.get(name) for name in ("RAILWAY_PROJECT_ID", "RAILWAY_SERVICE_ID")), "separate_recovery_host_required")
        require(output.is_absolute() and not output.exists() and not output.is_symlink(), "new_private_output_required")
        require(payload.is_absolute() and payload.is_dir() and not payload.is_symlink(), "private_payload_required")
        capture.private_directory(output.parent)
        capture.private_directory(payload)
        require(re.fullmatch(r"[0-9a-f]{64}", manifest_sha256 or "")
                and capture.digest(payload / "manifest.json") == manifest_sha256, "verified_manifest_mismatch")
        result["verified_manifest_files"] = capture.verify(payload)
        manifest = json.loads(capture.private_read(payload / "manifest.json"))
        metadata = manifest.get("metadata", {})
        source = metadata.get("database")
        require(isinstance(source, str) and source, "source_database_metadata_required")
        validate_target(target, confirmation, source)
        require(all(metadata.get(key) == policy[key] for key in ("source_revision", "image_reference")), "capture_runtime_provenance_mismatch")
        require("accounting-baseline.json" in manifest["files"] and "database.dump" in manifest["files"], "recovery_baseline_required")
        baseline = fingerprints.validate_baseline(json.loads(capture.private_read(payload / "accounting-baseline.json")))
        output.mkdir(mode=0o700)
        created = True
        result.update(stage="create_database", manifest_sha256=manifest_sha256, source_revision=policy["source_revision"],
                      declared_image_reference=policy["image_reference"])
        # No archived source config/environment is parsed or applied. Only this
        # dedicated loopback connection is available to children.
        from psycopg2 import sql
        admin = connect(policy, "postgres")
        admin.rollback()
        admin.autocommit = True
        try:
            with admin.cursor() as cursor:
                cursor.execute("SELECT 1 FROM pg_database WHERE datname=%s", (target,))
                require(cursor.fetchone() is None, "target_database_already_exists")
                # CREATE is atomic, so a concurrent creator cannot be overwritten.
                cursor.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(target)))
                result["database_created"] = True
        finally:
            admin.close()
        pgpass = output / "pgpass"
        pg = policy["postgres"]
        def escaped(value):
            return str(value).replace("\\", "\\\\").replace(":", "\\:")
        pgpass.write_text(":".join(escaped(value) for value in (pg["host"], pg["port"], target, pg["user"], pg["password"])) + "\n")
        pgpass.chmod(0o600)
        environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
                       "PGHOST": pg["host"], "PGPORT": str(pg["port"]), "PGUSER": pg["user"],
                       "PGDATABASE": target, "PGPASSFILE": str(pgpass), "HOME": str(output)}
        result["stage"] = "restore_database"
        restore_started = time.monotonic()
        try:
            run_owned(["pg_restore", "--exit-on-error", "--no-owner", "--no-acl", "--single-transaction", "--dbname", target,
                       str(payload / "database.dump")], environment, deadline - time.monotonic(), output / "restore.log")
        finally:
            pgpass.unlink(missing_ok=True)
        target_files = output / "data" / "filestore" / target
        target_files.parent.mkdir(mode=0o700, parents=True)
        capture.copy_tree(payload / "filestore", target_files, deadline)
        result["restore_seconds"] = round(time.monotonic() - restore_started, 3)
        result["stage"] = "validate_restored_snapshot"
        connection = connect(policy, target, readonly=True)
        try:
            restored = fingerprints.fingerprint(connection, target_files, deadline)
            require(restored == baseline, "restored_accounting_conservation_failed")
            with connection.cursor() as cursor:
                cursor.execute("SELECT state, latest_version FROM ir_module_module WHERE name='thirdcode_accounting'")
                require(cursor.fetchone() == ("installed", policy["addon_version"]), "restored_addon_version_mismatch")
        finally:
            connection.close()
        capture.atomic_json(output / "restored-fingerprint.json", restored)
        result.update(database_restore_verified=True, ledger_conservation_verified=True, attachment_conservation_verified=True)
        result["stage"] = "offline_odoo_validation"
        connection = connect(policy, target)
        try:
            neutralize(connection)
        finally:
            connection.close()
        config = write_configuration(policy, output, target)
        probe = output / "odoo-probe.json"
        run_owned([sys.executable, "-c", ODOO_PROBE, str(config), target, policy["addon_version"], str(probe)],
                  environment, deadline - time.monotonic(), output / "odoo.log")
        require(json.loads(capture.private_read(probe)).get("registry_loaded") is True, "odoo_probe_evidence_missing")
        connection = connect(policy, target, readonly=True)
        try:
            after = fingerprints.fingerprint(connection, target_files, deadline)
            require(after == baseline, "odoo_startup_conservation_failed")
            with connection.cursor() as cursor:
                cursor.execute("SELECT (SELECT count(*) FROM ir_cron WHERE active), (SELECT count(*) FROM ir_mail_server WHERE active)")
                require(cursor.fetchone() == (0, 0), "restored_jobs_or_mail_active")
        finally:
            connection.close()
        capture.atomic_json(output / "after-odoo-fingerprint.json", after)
        result.update(status="ISOLATED_RESTORE_VERIFIED", stage="complete", odoo_registry_verified=True,
                      referenced_files=len(restored["files"]), restored_table_counts={k: v["count"] for k, v in restored["tables"].items()})
    except Exception as error:
        result["error"] = str(error) if isinstance(error, (RestoreError, capture.BackupError)) else "isolated_restore_failed"
    finally:
        result["restore_and_validation_seconds"] = round(time.monotonic() - started, 3)
        if created:
            capture.atomic_json(output / "restore-results.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--confirm-target", required=True)
    parser.add_argument("--verified-manifest-sha256", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    def interrupted(_signal, _frame):
        raise RestoreError("restore_interrupted")
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGALRM, interrupted)
    try:
        policy = load_policy(args.config)
        signal.alarm(policy["timeout_seconds"])
        result = restore(policy, args.payload, args.output, args.target, args.confirm_target, args.verified_manifest_sha256)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "ISOLATED_RESTORE_VERIFIED" else 1
    except Exception as error:
        print(json.dumps({"status": "failed", "error": str(error) if isinstance(error, (RestoreError, capture.BackupError)) else "isolated_restore_failed"}))
        return 1
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    sys.exit(main())
