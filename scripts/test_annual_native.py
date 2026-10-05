"""Native annual smoke: CI-only clone, accounting operations and real PDFs.

Needs the pinned Odoo image, loopback disposable PostgreSQL, a persistent source
filestore and TCSI_ANNUAL_NATIVE_CI=disposable-only. Never accepts a production
source name or remote database host. Retains the clone and protected artifacts.
"""
from __future__ import annotations

import configparser
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

SOURCE = "tcsi_orvexa_ci"
HTTP_PORT = 18078
SCRIPTS = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def validate_ci_environment(environ):
    require(environ.get("TCSI_ANNUAL_NATIVE_CI") == "disposable-only", "Explicit disposable CI marker is required")
    require(environ.get("PGHOST") in ("127.0.0.1", "localhost", "::1"), "Native smoke requires loopback PostgreSQL")
    require(environ.get("PGDATABASE", SOURCE) == SOURCE, "Native smoke source must be tcsi_orvexa_ci")
    require(environ.get("PGUSER") == "odoo" and environ.get("PGPASSWORD"), "Disposable Odoo database credentials are required")


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, default=str) + "\n")
    os.replace(temporary, path)


def clone_database(target, data):
    import psycopg2
    from psycopg2 import sql
    connection = psycopg2.connect(dbname="postgres", connect_timeout=10)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=%s", (SOURCE,))
            require(cursor.fetchone()[0] == 0, "Source CI sessions still open; template clone must wait for prior jobs to exit")
            cursor.execute(sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(sql.Identifier(target), sql.Identifier(SOURCE)))
    finally:
        connection.close()
    connection = psycopg2.connect(dbname=target, connect_timeout=10)
    connection.set_session(readonly=True)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT state FROM ir_module_module WHERE name='thirdcode_accounting'")
            require(cursor.fetchone() == ("installed",), "Template does not have installed accounting module")
            cursor.execute("SELECT DISTINCT store_fname FROM ir_attachment WHERE store_fname IS NOT NULL")
            names = [r[0] for r in cursor.fetchall()]
    finally:
        connection.close()
    source = Path("/var/lib/odoo/filestore") / SOURCE
    destination = data / "filestore" / target
    destination.mkdir(parents=True)
    for name in names:
        path = source / name
        require(path.resolve().is_relative_to(source.resolve()) and path.is_file() and not path.is_symlink(),
                "Referenced CI source filestore file is absent or outside the source; preserve /var/lib/odoo across native steps")
        copied = destination / name
        copied.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, copied)
        require(hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(copied.read_bytes()).digest(), "Cloned filestore checksum mismatch")
    return len(names)


def write_configuration(path, database, data):
    config = configparser.ConfigParser(interpolation=None)
    config["options"] = {
        "db_host": os.environ["PGHOST"], "db_port": os.environ.get("PGPORT", "5432"),
        "db_user": os.environ["PGUSER"], "db_password": os.environ["PGPASSWORD"],
        "db_name": database, "dbfilter": f"^{database}$", "list_db": "False",
        "data_dir": str(data), "addons_path": "/opt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons",
        "http_interface": "127.0.0.1", "http_port": str(HTTP_PORT), "workers": "0", "max_cron_threads": "0",
        "smtp_server": "127.0.0.1", "smtp_port": "1", "smtp_user": "False", "smtp_password": "False", "smtp_ssl": "False",
    }
    with path.open("w") as handle:
        config.write(handle)


BOOTSTRAP = r'''
import json, os, runpy
from pathlib import Path
import odoo
from odoo import api
config, database, script, output, report_url = __import__('sys').argv[1:]
assert database.startswith('tcsi_alignment_annual_ci_')
odoo.tools.config.parse_config(['-c', config, '-d', database, '--no-http', '--max-cron-threads', '0'])
registry = odoo.registry(database)
with registry.cursor() as cursor:
    assert cursor.dbname == database
    env = api.Environment(cursor, 2, {'allowed_company_ids': [1]})
    assert env.ref('base.main_company').id == 1 and env.ref('base.user_admin').id == 2 and not env.su
    env['ir.cron'].search([('active', '=', True)]).write({'active': False})
    env['ir.mail_server'].search([('active', '=', True)]).write({'active': False})
    env['ir.config_parameter'].set_param('report.url', report_url)
    os.environ['ALIGNMENT_MODE'] = 'seed'
    runpy.run_path(script, init_globals={'env': env})
    cursor.commit()
    Path(output).write_text(json.dumps({'company_id': 1, 'actor_id': 2, 'database': database, 'fixture_ready': True}))
'''


class OwnedProcess:
    """One new process group, bounded wait and explicit descendant cleanup."""
    def __init__(self, command, log):
        self.log = log.open("wb")
        try:
            self.process = subprocess.Popen(command, stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True)
        except BaseException:
            self.log.close()
            raise

    def wait(self, seconds):
        return self.process.wait(timeout=seconds)

    def live_group_pids(self):
        # Linux CI /proc lets us distinguish live descendants from unreaped zombies.
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                if int(fields[2]) == self.process.pid and fields[0] != "Z":
                    yield int(entry.name)
            except (FileNotFoundError, ProcessLookupError):
                pass

    def group_alive(self):
        return next(self.live_group_pids(), None) is not None

    def stop(self):
        try:
            for sig, seconds in ((signal.SIGTERM, 10), (signal.SIGKILL, 5)):
                if not self.group_alive():
                    break
                try:
                    os.killpg(self.process.pid, sig)
                except ProcessLookupError:
                    pass  # Group exited after the liveness snapshot.
                deadline = time.monotonic() + seconds
                while self.group_alive() and time.monotonic() < deadline:
                    self.process.poll()
                    time.sleep(.1)
            require(not self.group_alive(), "Owned process descendants remained alive after cleanup")
            self.process.wait(timeout=5)
        finally:
            self.log.close()


def listener_owned(server):
    listeners = []
    for row in Path("/proc/net/tcp").read_text().splitlines()[1:]:
        fields = row.split()
        if fields[1].split(":")[1] == f"{HTTP_PORT:04X}" and fields[3] == "0A":
            require(fields[1] == f"0100007F:{HTTP_PORT:04X}", "Annual HTTP listener is not loopback-only")
            listeners.append(f"socket:[{fields[9]}]")
    if not listeners:
        return False
    owned = set()
    for pid in server.live_group_pids():
        try:
            for fd in Path(f"/proc/{pid}/fd").iterdir():
                try:
                    owned.add(os.readlink(fd))
                except FileNotFoundError:
                    pass
        except FileNotFoundError:
            pass
    require(set(listeners).issubset(owned), "Loopback HTTP listener is not owned by this annual CI server")
    return True


def ready(server, database):
    deadline = time.monotonic() + 60
    url = f"http://127.0.0.1:{HTTP_PORT}/web/login?db={database}"
    while time.monotonic() < deadline:
        require(server.process.poll() is None, "Owned isolated HTTP server exited before readiness")
        if not listener_owned(server):
            time.sleep(.25)
            continue
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200 and b"login" in response.read().lower():
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(.25)
    raise RuntimeError("Owned isolated server did not become ready within 60 seconds")


def verify_smoke(result, directory):
    require(result.get("exit_code") == 0 and result.get("status") == "ENGINEERING_TARGET_OBSERVED", "Native annual target was not observed; retain failure evidence")
    require(result.get("acceptance_claim") is False and result.get("approved_client_volume") is False, "Smoke must not claim client acceptance")
    require(result.get("seed_committed") is True, "Native seed was not committed")
    seeded = result["seeded"]
    for key, expected in (("documents", 24), ("payments", 8), ("posted_moves", 32), ("posted_lines", 64), ("months", 12)):
        require(seeded[key] == expected, f"Unexpected native seed {key}: expected {expected}, got {seeded[key]}")
    require(result["measured_cardinality"]["year_posted_documents"] - result["before"]["year_posted_documents"] == 32, "Annual posted move delta differs from scenario")
    require(result["measured_cardinality"]["year_posted_lines"] - result["before"]["year_posted_lines"] == 64, "Annual line delta differs from scenario")
    require(len(result["samples"]) == 6, "Expected six annual report samples")
    for sample in result["samples"]:
        pdf = directory / f"{sample['report']}-{sample['repeat']}.pdf"
        body = pdf.read_bytes()
        require(body.startswith(b"%PDF") and len(body) == sample["pdf_bytes"] and
                hashlib.sha256(body).hexdigest() == sample["pdf_sha256"], "Rendered PDF evidence is missing or mismatched")
    require(len(list(directory.glob("*.pdf"))) == 6, "Expected six actual PDFs")


def verify_monthly_smoke(result, directory):
    require(result.get("status") == "PASSED" and result.get("acceptance_claim") is False,
            "Monthly smoke failed or incorrectly claimed client acceptance")
    require(result.get("company_id") == 1 and result.get("render_role") == "readonly" and
            result.get("render_actor_id", 0) > 1 and result.get("sudo") is False,
            "Monthly PDF was not rendered with the expected native role/company scope")
    require(result.get("report") == "thirdcode_accounting.action_report_monthly_bank_reconciliation",
            "Monthly smoke rendered an unexpected report")
    require(result.get("ledger_closing") == 100 and result.get("statement_closing") == 100 and
            result.get("difference") == 0 and result.get("unmatched_count") == 1,
            "Monthly smoke accounting evidence differs from its native statement fixture")
    require(result.get("render_preserved_accounting") is True, "Monthly PDF changed accounting evidence")
    body = (directory / "monthly-reconciliation.pdf").read_bytes()
    require(body.startswith(b"%PDF") and len(body) == result.get("pdf_bytes") and len(body) > 5 and
            hashlib.sha256(body).hexdigest() == result.get("pdf_sha256"),
            "Monthly rendered PDF evidence is missing or mismatched")


def monthly_child(config_path, database, directory):
    """Native Read-only PDF smoke; the parent owns the isolated asset server."""
    import base64
    validate_ci_environment(os.environ)
    require(database.startswith("tcsi_alignment_annual_ci_"), "Unexpected monthly smoke database")
    config = configparser.ConfigParser(interpolation=None)
    require(config.read(config_path) == [config_path], "Monthly isolated configuration missing")
    require(config["options"].get("db_name") == database and config["options"].get("dbfilter") == f"^{database}$",
            "Monthly isolated configuration identity mismatch")
    options = config["options"]
    require(options.get("db_host") == os.environ["PGHOST"] and options.get("db_user") == "odoo" and
            options.get("db_port") == os.environ.get("PGPORT", "5432") and
            options.get("db_password") == os.environ["PGPASSWORD"], "Monthly config does not use the guarded disposable connection")
    os.umask(0o077)
    output = Path(directory)
    output.mkdir(mode=0o700)
    report = "thirdcode_accounting.action_report_monthly_bank_reconciliation"
    result = {"status": "FAILED", "database": database, "company_id": 1, "report": report,
              "period": ["2025-01-01", "2025-01-31"], "acceptance_claim": False,
              "scope": "Synthetic January review and real PDF; client-specific format and approval remain pending"}
    try:
        import odoo
        from odoo import api
        odoo.tools.config.parse_config(["-c", config_path, "-d", database, "--no-http", "--max-cron-threads", "0"])
        registry = odoo.registry(database)
        with registry.cursor() as cursor:
            require(cursor.dbname == database, "Monthly native cursor identity mismatch")
            env = api.Environment(cursor, 2, {"allowed_company_ids": [1]})
            require(not env.su and env.company.id == 1 and env.companies.ids == [1], "Monthly fixture actor escaped company scope")
            require(env.user.has_group("thirdcode_accounting.group_thirdcode_administrator"), "Native administrator fixture role missing")
            require(not env["ir.cron"].search_count([("active", "=", True)]) and
                    not env["ir.mail_server"].search_count([("active", "=", True)]), "Monthly clone cron or outbound mail is active")
            require(env["ir.config_parameter"].get_param("report.url") == f"http://127.0.0.1:{HTTP_PORT}", "Monthly report assets escaped owned loopback server")
            suspense = env["account.account"].create({"name": "Synthetic monthly PDF suspense", "code": "MPCSUSP",
                "account_type": "asset_current", "company_ids": [(6, 0, [1])], "reconcile": True})
            bank = env["account.journal"].create({"name": "Synthetic monthly PDF bank", "code": "MPC",
                "type": "bank", "company_id": 1, "suspense_account_id": suspense.id})
            record = env["thirdcode.bank.reconciliation"].create({
                "name": "Synthetic January 2025 PDF review", "company_id": 1, "journal_id": bank.id,
                "statement_reference": "SYNTHETIC-MONTHLY-PDF-2025-01", "date_start": "2025-01-01", "date_end": "2025-01-31",
                "opening_balance": 0, "closing_balance": 100,
                "evidence_file": base64.b64encode(b"Synthetic January statement: opening 0, receipt 100, closing 100. Not client evidence."),
                "evidence_filename": "synthetic-monthly-statement.txt",
            })
            statement = env["account.bank.statement.line"].create({
                "journal_id": bank.id, "date": "2025-01-10", "amount": 100,
                "payment_ref": "Synthetic monthly PDF receipt", "thirdcode_reconciliation_id": record.id,
            })
            require(statement.move_id.state == "posted" and str(statement.date) == "2025-01-10",
                    "Monthly native statement did not post in the expected period")
            record.action_compute_ledger_balance()
            reader = env["res.users"].with_context(no_reset_password=True).create({
                "name": "Synthetic monthly PDF reader", "login": "tcsi-monthly-pdf-reader-ci",
                "company_id": 1, "company_ids": [(6, 0, [1])],
                "groups_id": [(6, 0, env.ref("thirdcode_accounting.group_thirdcode_readonly").ids)],
            })
            cursor.commit()
            result.update(fixture_committed=True, record_id=record.id, render_actor_id=reader.id, render_role="readonly", sudo=False)
            save(output / "results.json", result)
            visible = record.with_user(reader).with_context(allowed_company_ids=[1])
            require(not visible.env.su and visible.env.companies.ids == [1] and
                    visible.env.user.has_group("thirdcode_accounting.group_thirdcode_readonly") and
                    not any(visible.env.user.has_group("thirdcode_accounting.group_thirdcode_" + role)
                            for role in ("accountant", "administrator", "encoder")), "Monthly PDF reader role is not Read-only")

            def accounting_snapshot():
                env.flush_all()
                fields = ["state", "ledger_balance", "opening_balance", "closing_balance", "difference", "reconciled_by", "reconciled_at", "write_date"]
                return {
                    "record": record.read(fields),
                    "posted_lines": env["account.move.line"].search([
                        ("company_id", "=", 1), ("parent_state", "=", "posted")], order="id").read([
                            "move_id", "account_id", "debit", "credit", "balance", "amount_residual"]),
                    "counts": {name: env[name].search_count([]) for name in (
                        "account.move", "account.move.line", "account.partial.reconcile", "account.full.reconcile", "auditlog.log", "auditlog.log.line")},
                }

            before = accounting_snapshot()
            data = visible.get_monthly_report_data()
            require(data["ledger"]["opening"] == 0 and data["ledger"]["closing"] == 100 and
                    data["statement"]["calculated_closing"] == 100 and data["difference"] == 0,
                    "Monthly native ledger/statement arithmetic differs from the fixture")
            require(data["statement"]["unmatched_count"] == 1 and any("remain unmatched" in warning for warning in data["warnings"]),
                    "Monthly report omitted the unmatched statement warning")
            require(record.state == "draft" and not record.reconciled_by and not record.reconciled_at,
                    "Monthly smoke must not create an accounting sign-off")
            action = visible.action_print_monthly_report()
            require(action.get("report_name") == "thirdcode_accounting.report_monthly_bank_reconciliation", "Unexpected native print action")
            started = time.perf_counter()
            pdf, _ = env["ir.actions.report"].with_user(reader).with_context(allowed_company_ids=[1])._render_qweb_pdf(report, record.ids)
            result["pdf_seconds"] = time.perf_counter() - started
            require(pdf.startswith(b"%PDF") and len(pdf) > 5, "Monthly renderer returned no PDF")
            (output / "monthly-reconciliation.pdf").write_bytes(pdf)
            after = accounting_snapshot()
            require(before == after, "Monthly PDF rendering changed ledger, audit, settlement or review state")
            result.update(ledger_closing=data["ledger"]["closing"],
                          statement_closing=data["statement"]["calculated_closing"], difference=data["difference"],
                          unmatched_count=data["statement"]["unmatched_count"], render_preserved_accounting=True,
                          accounting_snapshot_sha256=hashlib.sha256(json.dumps(before, sort_keys=True, default=str).encode()).hexdigest(),
                          pdf_bytes=len(pdf), pdf_sha256=hashlib.sha256(pdf).hexdigest())
            cursor.rollback()
        result["status"] = "PASSED"
    except BaseException as exc:
        result["status"] = "FAILED"
        result["error"] = f"{type(exc).__name__}: {exc}".replace(os.environ["PGPASSWORD"], "[redacted]")
    finally:
        save(output / "results.json", result)
    print("MONTHLY_NATIVE", json.dumps(result, sort_keys=True), flush=True)
    return 0 if result["status"] == "PASSED" else 1


def main():
    validate_ci_environment(os.environ)  # No directory, subprocess or DB access before guard.
    require(sys.platform == "linux", "Native CI process ownership requires Linux /proc")
    os.umask(0o077)
    root = Path(os.environ.get("TCSI_ANNUAL_EVIDENCE", "/tmp/tcsi-annual-native"))
    root.mkdir(mode=0o700)  # Preserve prior success or failure evidence.
    database = "tcsi_alignment_annual_ci_" + uuid.uuid4().hex[:12]
    data = root / "data"
    data.mkdir()
    config = root / "isolated.conf"
    summary = {"database": database, "source_database": SOURCE, "status": "FAILED", "source": "Disposable CI clone; not production or client-volume acceptance"}
    processes = []
    def interrupted(signum, frame):
        raise RuntimeError(f"Native annual smoke interrupted by signal {signum}")
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, interrupted)
    try:
        with socket.socket() as check:
            check.bind(("127.0.0.1", HTTP_PORT))
        summary["copied_filestore_files"] = clone_database(database, data)
        write_configuration(config, database, data)
        bootstrap = OwnedProcess([sys.executable, "-c", BOOTSTRAP, str(config), database,
            str(SCRIPTS / "alignment_fixture.py"), str(root / "bootstrap.json"), f"http://127.0.0.1:{HTTP_PORT}"], root / "bootstrap.log")
        processes.append(bootstrap)
        require(bootstrap.wait(180) == 0, "Native fixture bootstrap failed; inspect bootstrap.log")
        bootstrap.stop()
        server = OwnedProcess(["odoo", "-c", str(config), "-d", database, "--max-cron-threads=0"], root / "server.log")
        processes.append(server)
        ready(server, database)
        output = root / "annual-results"
        benchmark = OwnedProcess([sys.executable, str(SCRIPTS / "benchmark_annual.py"), "--config", str(config),
            "--database", database, "--confirm-isolated-database", database, "--company-id", "1", "--actor-id", "2",
            "--year", "2025", "--seed-documents", "24", "--settle-every", "3", "--max-seed-seconds", "180",
            "--repeats", "2", "--render-pdf", "--report-url", f"http://127.0.0.1:{HTTP_PORT}",
            "--output-directory", str(output)], root / "benchmark.log")
        processes.append(benchmark)
        code = benchmark.wait(300)
        summary["benchmark_exit"] = code
        require((output / "results.json").is_file(), "Benchmark did not preserve results.json")
        result = json.loads((output / "results.json").read_text())
        verify_smoke(result, output)
        require(code == 0, "Benchmark process failed despite result evidence")
        summary.update(seeded=result["seeded"], measured_cardinality=result["measured_cardinality"], samples=result["samples"])
        require(server.process.poll() is None and listener_owned(server), "Isolated PDF server no longer owns its listener")
        monthly_output = output / "monthly"
        monthly = OwnedProcess([sys.executable, str(Path(__file__).resolve()), "--monthly-child", str(config), database,
                                str(monthly_output)], root / "monthly.log")
        processes.append(monthly)
        monthly_code = monthly.wait(150)
        summary["monthly_exit"] = monthly_code
        require((monthly_output / "results.json").is_file(), "Monthly smoke did not preserve results.json")
        monthly_result = json.loads((monthly_output / "results.json").read_text())
        verify_monthly_smoke(monthly_result, monthly_output)
        require(monthly_code == 0, "Monthly process failed despite result evidence")
        summary.update(status="PASSED", monthly=monthly_result)
    except BaseException as exc:
        message = f"{type(exc).__name__}: {exc}"
        summary["error"] = message.replace(os.environ["PGPASSWORD"], "[redacted]")
    finally:
        errors = []
        for process in reversed(processes):
            try:
                process.stop()
            except BaseException as exc:
                errors.append(f"{type(exc).__name__}: {exc}")
        if errors:
            summary.update(status="FAILED", cleanup_errors=errors)
        save(root / "summary.json", summary)
    print("ANNUAL_NATIVE", json.dumps(summary, sort_keys=True), flush=True)
    return 0 if summary["status"] == "PASSED" else 1


if __name__ == "__main__":
    if sys.argv[1:2] == ["--monthly-child"]:
        require(len(sys.argv) == 5, "Expected config, isolated database and new monthly output directory")
        raise SystemExit(monthly_child(*sys.argv[2:]))
    raise SystemExit(main())
