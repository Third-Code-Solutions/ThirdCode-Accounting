"""Recovery guards plus opt-in real PG18/Odoo fixture restore; no real books."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
import uuid

import hosted_backup as capture
import hosted_recovery_restore as restore
import hosted_recovery_drill as drill
import recovery_fingerprint as fingerprints


class RestoreGuardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.policy = {"format": 1, "isolated_host_confirmed": True, "egress_isolation_confirmed": True,
                       "postgres": {"host": "127.0.0.1", "port": 5432, "user": "fixture", "password": "disposable"},
                       "source_revision": "a" * 40, "image_reference": "test@sha256:" + "b" * 64,
                       "addon_version": "18.0.2.13.3", "timeout_seconds": 60, "addons_path": [str(self.root)]}

    def tearDown(self):
        self.temporary.cleanup()

    def policy_file(self):
        path = self.root / "policy.json"
        capture.atomic_json(path, self.policy)
        return path

    def test_only_explicit_private_loopback_policy(self):
        self.assertEqual(restore.load_policy(self.policy_file()), self.policy)
        for host in ("localhost", "database.internal", "10.0.0.1", "/tmp/postgres"):
            self.policy["postgres"]["host"] = host
            with self.subTest(host=host), self.assertRaisesRegex(restore.RestoreError, "loopback"):
                restore.load_policy(self.policy_file())
        self.policy["postgres"]["host"] = "127.0.0.1"
        self.policy["egress_isolation_confirmed"] = False
        with self.assertRaisesRegex(restore.RestoreError, "isolated_recovery_host"):
            restore.load_policy(self.policy_file())

    def test_target_confirmation_and_exact_uuid_guard(self):
        target = "tcsi_alignment_restore_" + uuid.uuid4().hex
        restore.validate_target(target, target, "archived_source")
        for candidate, confirmation, source in (("tcsi_pilot", "tcsi_pilot", "source"),
                (target, "yes", "source"), (target, target, target),
                ("tcsi_alignment_restore_existing", "tcsi_alignment_restore_existing", "source")):
            with self.subTest(target=candidate), self.assertRaises(restore.RestoreError):
                restore.validate_target(candidate, confirmation, source)

    def test_libpq_routing_overrides_fail_before_connection(self):
        for name, value in (("hostaddr", "203.0.113.1"), ("service", "production"), ("dbname", "production")):
            altered = {**self.policy["postgres"], name: value}
            with self.subTest(name=name), self.assertRaisesRegex(restore.RestoreError, "unexpected_postgres_options"):
                restore.validate_postgres(altered)
        for name in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGSYSCONFDIR"):
            with patch.dict(os.environ, {name: "untrusted"}), self.subTest(name=name), \
                    self.assertRaisesRegex(restore.RestoreError, "ambient_postgres_routing_forbidden"):
                restore.connect(self.policy, "postgres")

    def test_connected_client_endpoint_and_database_identity_are_verified(self):
        def connection(**changes):
            result = MagicMock()
            values = {"host": "127.0.0.1", "port": 5432, "dbname": "postgres", "user": "fixture",
                      "dsn_parameters": {"hostaddr": "127.0.0.1"}}
            values.update(changes)
            result.info = SimpleNamespace(**values)
            result.cursor.return_value.__enter__.return_value.fetchone.return_value = ("postgres", "fixture")
            return result
        fake = SimpleNamespace(connect=MagicMock())
        good = connection()
        fake.connect.return_value = good
        with patch.dict(sys.modules, {"psycopg2": fake}):
            self.assertIs(restore.connect(self.policy, "postgres", readonly=True), good)
            self.assertEqual(fake.connect.call_args.kwargs["hostaddr"], "127.0.0.1")
            self.assertEqual(fake.connect.call_args.kwargs["host"], "127.0.0.1")
            good.set_session.assert_called_once_with(readonly=True, isolation_level="REPEATABLE READ")
            # A port-forwarded server may report a bridge address. The guard
            # deliberately queries logical DB identity, not server-side routing.
            good.cursor.return_value.__enter__.return_value.execute.assert_called_once_with("SELECT current_database(), current_user")
            good.close.assert_not_called()
            for changes in ({"host": "203.0.113.1"}, {"port": 5433}, {"dbname": "other"}, {"user": "other"},
                            {"dsn_parameters": {"hostaddr": "203.0.113.1"}}, {"dsn_parameters": {}}):
                rejected = connection(**changes)
                fake.connect.return_value = rejected
                with self.subTest(changes=changes), self.assertRaisesRegex(restore.RestoreError, "postgres_endpoint_mismatch"):
                    restore.connect(self.policy, "postgres")
                rejected.close.assert_called_once()
            wrong_database = connection()
            wrong_database.cursor.return_value.__enter__.return_value.fetchone.return_value = ("other", "fixture")
            fake.connect.return_value = wrong_database
            with self.assertRaisesRegex(restore.RestoreError, "postgres_database_identity_mismatch"):
                restore.connect(self.policy, "postgres")
            wrong_database.close.assert_called_once()

    def test_existing_output_refused_before_database_access(self):
        with patch.object(restore.sys, "platform", "linux"), patch.object(restore, "connect") as connect:
            result = restore.restore(self.policy, self.root / "payload", self.root, "irrelevant", "irrelevant", "a" * 64)
        self.assertEqual(result["error"], "new_private_output_required")
        connect.assert_not_called()

    def test_legacy_baseline_rejected_and_json_text_hashes_stable(self):
        for value in ({}, {"records": {}}, {"format": 1, "tables": {}, "files": {}, "balances": {}}):
            with self.assertRaisesRegex(capture.BackupError, "baseline_required"):
                fingerprints.validate_baseline(value)
        rows = [('{"balance":1234567890.123456789}',), ('{"balance":0.000000001}',)]
        self.assertEqual(fingerprints.hash_rows(rows), fingerprints.hash_rows(iter(rows)))
        with self.assertRaisesRegex(capture.BackupError, "text_required"):
            fingerprints.hash_rows([(1.01,)])

    def test_attachment_traversal_and_checksum_failure_paths(self):
        (self.root / "blob").write_bytes(b"synthetic attachment")
        self.assertEqual(fingerprints.safe_file(self.root, "blob"), self.root / "blob")
        (self.root / "link").symlink_to(self.root)
        for name in ("../blob", "/blob", "link/blob", "a\\blob", "./blob"):
            with self.subTest(name=name), self.assertRaises(capture.BackupError):
                fingerprints.safe_file(self.root, name)

    def test_offline_configuration_never_uses_archived_credentials(self):
        target = "tcsi_alignment_restore_" + uuid.uuid4().hex
        path = restore.write_configuration(self.policy, self.root, target)
        content = path.read_text()
        self.assertIn("http_enable = False", content)
        self.assertIn("max_cron_threads = 0", content)
        self.assertIn("smtp_port = 1", content)
        self.assertIn("db_name = " + target, content)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_full_drill_composes_preparation_with_unique_isolated_target(self):
        output = self.root / "complete"
        interpreter = self.root / "python"
        interpreter.write_text("#!/bin/sh\nexit 1\n")
        interpreter.chmod(0o700)
        def prepare(*_args, **_kwargs):
            output.mkdir(mode=0o700)
            return {"status": "DECRYPTED_MANIFEST_VERIFIED", "manifest_sha256": "c" * 64}
        commands = []
        def run(command, environment, timeout, log):
            commands.append(command)
            self.assertNotIn("PGPASSWORD", environment)
            target = command[command.index("--target") + 1]
            restore.validate_target(target, command[command.index("--confirm-target") + 1], "source")
            restored = output / "restore"
            restored.mkdir(mode=0o700)
            capture.atomic_json(restored / "restore-results.json", {"status": "ISOLATED_RESTORE_VERIFIED"})
        arguments = ["drill", "--config", str(self.root / "provider.json"), "--run-id", str(uuid.uuid4()),
                     "--output", str(output), "--private-key", str(self.root / "key"),
                     "--public-certificate", str(self.root / "cert"), "--confirm-offhost-recovery",
                     "--full-restore", "--restore-config", str(self.policy_file()), "--restore-python", str(interpreter)]
        with patch.object(sys, "argv", arguments), patch.object(drill.provider, "load_policy", return_value={"operation_timeout_seconds": 60}), \
                patch.object(drill.provider, "s3_client"), patch.object(drill, "prepare", side_effect=prepare), \
                patch.object(restore, "run_owned", side_effect=run), patch("builtins.print") as printer:
            code = drill.main()
            self.assertEqual(code, 0, printer.call_args_list)
        self.assertEqual(len(commands), 1)
        result = json.loads((output / "drill-results.json").read_text())
        self.assertEqual(result["status"], "FULL_ISOLATED_DRILL_VERIFIED")
        self.assertIsNone(result["rto_met"])

    @unittest.skipUnless(sys.platform == "linux", "Linux parent-death guard required")
    def test_owned_descendants_are_killed_on_timeout(self):
        pid_path = self.root / "child.pid"
        code = "import pathlib,subprocess,time,sys; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); pathlib.Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(60)"
        import subprocess
        with self.assertRaises(subprocess.TimeoutExpired):
            restore.run_owned([sys.executable, "-c", code, str(pid_path)], {"PATH": os.environ["PATH"]}, .5, self.root / "timeout.log")
        pid = int(pid_path.read_text())
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            stat = Path(f"/proc/{pid}/stat")
            if not stat.exists() or stat.read_text().rsplit(")", 1)[1].split()[0] == "Z":
                break
            time.sleep(.05)
        else:
            self.fail("Owned descendant survived timeout")

    @unittest.skipUnless(sys.platform == "linux", "Linux independent watchdog required")
    def test_sigkill_of_caller_still_kills_command_and_grandchild(self):
        import subprocess
        pid_path = self.root / "owned-pids.json"
        command = "import json,os,pathlib,subprocess,sys,time; child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); pathlib.Path(sys.argv[1]).write_text(json.dumps([os.getpid(),child.pid])); time.sleep(60)"
        caller = "import sys; from pathlib import Path; import hosted_recovery_restore as r; r.run_owned([sys.executable,'-c',sys.argv[1],sys.argv[2]],{'PATH':'/usr/bin:/bin'},60,Path(sys.argv[3]))"
        process = subprocess.Popen([sys.executable, "-c", caller, command, str(pid_path), str(self.root / "parent-death.log")],
                                   env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent)})
        try:
            deadline = time.monotonic() + 5
            while not pid_path.exists() and time.monotonic() < deadline:
                self.assertIsNone(process.poll())
                time.sleep(.02)
            self.assertTrue(pid_path.exists(), "Owned descendants did not start")
            pids = json.loads(pid_path.read_text())
            process.kill()
            process.wait(timeout=5)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                live = []
                for pid in pids:
                    stat = Path(f"/proc/{pid}/stat")
                    if stat.exists() and stat.read_text().rsplit(")", 1)[1].split()[0] != "Z":
                        live.append(pid)
                if not live:
                    break
                time.sleep(.05)
            else:
                self.fail("Command descendants survived caller SIGKILL")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)


@unittest.skipUnless(os.environ.get("TCSI_RECOVERY_RESTORE_TEST_PG") == "disposable-only", "Disposable PG18/Odoo opt-in required")
class NativeRestoreTests(unittest.TestCase):
    def test_real_dump_restore_native_registry_and_tamper_rejection(self):
        import psycopg2
        from psycopg2 import sql
        self.assertEqual(sys.platform, "linux")
        self.assertEqual(os.environ.get("PGHOST"), "127.0.0.1")
        self.assertEqual(os.environ.get("PGDATABASE"), "tcsi_orvexa_hosted_ci")
        self.assertEqual(os.environ.get("PGUSER"), "odoo")
        root = Path(tempfile.mkdtemp(prefix="tcsi-recovery-native-"))
        root.chmod(0o700)
        source = "tcsi_alignment_restore_fixture_" + uuid.uuid4().hex
        target = "tcsi_alignment_restore_" + uuid.uuid4().hex
        pg = {"host": "127.0.0.1", "port": int(os.environ.get("PGPORT", "5432")),
              "user": os.environ["PGUSER"], "password": os.environ["PGPASSWORD"]}
        admin = psycopg2.connect(dbname="postgres", **pg)
        admin.autocommit = True
        try:
            with admin.cursor() as cursor:
                cursor.execute("SHOW server_version_num")
                self.assertGreaterEqual(int(cursor.fetchone()[0]), 180000)
                cursor.execute("SELECT inet_server_addr()::text, inet_server_port()")
                server_address, server_port = cursor.fetchone()
                print("RECOVERY_NATIVE_ENDPOINT " + json.dumps({"client_host": admin.info.host,
                      "client_port": admin.info.port, "server_address": server_address, "server_port": server_port}))
                cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE datname='tcsi_orvexa_hosted_ci'")
                self.assertEqual(cursor.fetchone()[0], 0, "Previous hosted CI process must have stopped")
                cursor.execute(sql.SQL("CREATE DATABASE {} TEMPLATE tcsi_orvexa_hosted_ci").format(sql.Identifier(source)))
        finally:
            admin.close()
        # No real source may enter this path. This clone and every created target
        # remain for the ephemeral CI environment to dispose of; never DROP.
        data = root / "fixture" / "data" / "filestore" / source
        data.parent.mkdir(mode=0o700, parents=True)
        capture.copy_tree(Path("/var/lib/odoo/filestore/tcsi_orvexa_hosted_ci"), data, time.monotonic() + 60)
        connection = psycopg2.connect(dbname=source, **pg)
        with connection.cursor() as cursor:
            cursor.execute("SELECT latest_version FROM ir_module_module WHERE name='thirdcode_accounting' AND state='installed'")
            version = cursor.fetchone()[0]
        connection.close()
        policy = {"format": 1, "isolated_host_confirmed": True, "egress_isolation_confirmed": True,
                  "postgres": pg, "source_revision": "a" * 40, "image_reference": "ci-fixture@sha256:" + "b" * 64,
                  "addon_version": version, "timeout_seconds": 180,
                  "addons_path": ["/opt/extra-addons", "/usr/lib/python3/dist-packages/odoo/addons"]}
        config = restore.write_configuration(policy, root / "fixture", source)
        environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        seed = """
import os, runpy, sys, odoo
from odoo import api
odoo.tools.config.parse_config(['-c', sys.argv[1], '--no-http', '--max-cron-threads', '0'])
registry = odoo.registry(sys.argv[2])
with registry.cursor() as cursor:
    env = api.Environment(cursor, 2, {'allowed_company_ids': [1]})
    env['ir.cron'].search([]).write({'active': False})
    env['ir.mail_server'].search([]).write({'active': False})
    os.environ['ALIGNMENT_MODE'] = 'seed'
    runpy.run_path(sys.argv[3], init_globals={'env': env})
    cursor.commit()
"""
        restore.run_owned([sys.executable, "-c", seed, str(config), source, str(Path(__file__).with_name("alignment_fixture.py"))],
                          environment, 180, root / "seed.log")
        payload = root / "payload"
        payload.mkdir(mode=0o700)
        capture.copy_tree(data, payload / "filestore", time.monotonic() + 60)
        connection = psycopg2.connect(dbname=source, **pg)
        connection.set_session(readonly=True, isolation_level="REPEATABLE READ")
        try:
            baseline = fingerprints.fingerprint(connection, payload / "filestore", time.monotonic() + 60)
            # Odoo registers NUMERIC as float process-wide. Canonical SQL text
            # must preserve the exact same checksum before and after that change.
            caster = psycopg2.extensions.new_type(psycopg2.extensions.DECIMAL.values, "RECOVERY_TEST_FLOAT",
                                                lambda value, cursor: None if value is None else float(value))
            psycopg2.extensions.register_type(caster, connection)
            self.assertEqual(fingerprints.fingerprint(connection, payload / "filestore", time.monotonic() + 60), baseline)
        finally:
            connection.close()
        self.assertGreaterEqual(baseline["tables"]["account_move"]["count"], 13)
        self.assertGreater(baseline["tables"]["auditlog_log_line"]["count"], 0)
        self.assertGreater(len(baseline["files"]), 0)
        capture.atomic_json(payload / "accounting-baseline.json", baseline)
        capture.run(["pg_dump", "--format=custom", "--no-owner", "--no-acl", "--file", str(payload / "database.dump")],
                    environment={**environment, "PGDATABASE": source}, timeout=60)
        # A poisoned archived config must not influence any target connection.
        (payload / "odoo.conf").write_text("[options]\ndb_host=production.invalid\ndb_name=DO_NOT_CONNECT\n")
        (payload / "odoo.conf").chmod(0o600)
        capture.write_manifest(payload, {"database": source, "source_revision": policy["source_revision"],
                                        "image_reference": policy["image_reference"], "captured_at": capture.now()})
        manifest_hash = capture.digest(payload / "manifest.json")
        result = restore.restore(policy, payload, root / "restored", target, target, manifest_hash)
        self.assertEqual(result["status"], "ISOLATED_RESTORE_VERIFIED", result)
        self.assertTrue(result["ledger_conservation_verified"])
        self.assertTrue(result["attachment_conservation_verified"])
        self.assertTrue(result["odoo_registry_verified"])
        self.assertFalse(result["production_database_connected"])
        self.assertIsNone(result["rto_met"])
        duplicate = restore.restore(policy, payload, root / "duplicate", target, target, manifest_hash)
        self.assertEqual(duplicate["error"], "target_database_already_exists")
        self.assertFalse(duplicate["database_created"])
        altered = json.loads(json.dumps(baseline))
        altered["tables"]["account_move"]["sha256"] = "0" * 64
        capture.atomic_json(payload / "accounting-baseline.json", altered)
        # Manifest covers every member except itself; remove it only in this
        # synthetic payload before rebuilding the intentionally bad baseline.
        (payload / "manifest.json").unlink()
        capture.write_manifest(payload, {"database": source, "source_revision": policy["source_revision"],
                                        "image_reference": policy["image_reference"], "captured_at": capture.now()})
        other = "tcsi_alignment_restore_" + uuid.uuid4().hex
        bad = restore.restore(policy, payload, root / "mismatched", other, other, capture.digest(payload / "manifest.json"))
        self.assertEqual(bad["error"], "restored_accounting_conservation_failed")
        self.assertFalse(bad["odoo_registry_verified"])
        # Publish only synthetic summary; protected configs/filestore stay local.
        print("RECOVERY_NATIVE_RESULT " + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    os.umask(0o077)
    unittest.main()
