"""Recovery controls tested with disposable files/processes; no hosted credentials."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("hosted_backup", Path(__file__).with_name("hosted_backup.py"))
backup = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = backup
SPEC.loader.exec_module(backup)


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.policy = {
            "enabled": True, "writer_topology": "single_supervised_odoo", "database": "isolated",
            "data_dir": str(self.root / "data"), "state_dir": str(self.root / "state"),
            "public_certificate": str(self.root / "public.pem"), "destination": "approved-vault",
            "delivery_command": str(self.root / "delivery"), "alert_command": str(self.root / "alert"),
            "operator": "test-owner", "deputy": "test-deputy", "retention_policy": "test-policy",
            "schedule": "test-schedule", "timezone": "UTC", "rpo": "test-rpo", "rto": "test-rto",
            "source_revision": "a" * 40, "image_reference": "test@sha256:" + "b" * 64,
            "max_pause_seconds": 5, "adapter_timeout_seconds": 5, "maximum_success_age_seconds": 60,
        }
        for name in ("delivery", "alert"):
            path = self.root / name
            path.write_text("#!/bin/sh\nexit 1\n")
            path.chmod(0o700)
        Path(self.policy["state_dir"]).mkdir(mode=0o700)

    def tearDown(self):
        self.temporary.cleanup()

    def policy_file(self, **changes):
        path = self.root / "policy.json"
        path.write_text(json.dumps({**self.policy, **changes}))
        path.chmod(0o600)
        return path

    def test_policy_requires_explicit_approvals_and_complete_destination(self):
        backup.load_policy(self.policy_file())
        for changes in ({"enabled": False}, {"destination": ""}, {"alert_command": ""},
                        {"writer_topology": "multi_replica"}, {"rpo": ""},
                        {"image_reference": "image:latest"}, {"max_pause_seconds": 301}):
            with self.subTest(changes=changes), self.assertRaises(backup.BackupError):
                backup.load_policy(self.policy_file(**changes))

    def test_private_policy_permissions_and_adapter_permissions(self):
        path = self.policy_file()
        path.chmod(0o644)
        with self.assertRaises(backup.BackupError):
            backup.load_policy(path)
        path.chmod(0o600)
        (self.root / "delivery").chmod(0o777)
        with self.assertRaises(backup.BackupError):
            backup.load_policy(path)

    def test_manifest_detects_modified_missing_extra_and_symlink_members(self):
        directory = self.root / "bundle"
        directory.mkdir()
        item = directory / "data"
        item.write_bytes(b"original")
        backup.write_manifest(directory, {"revision": "test"})
        self.assertEqual(backup.verify(directory), 1)
        item.write_bytes(b"tampered")
        with self.assertRaisesRegex(backup.BackupError, "bundle_hash_mismatch"):
            backup.verify(directory)
        item.unlink()
        with self.assertRaisesRegex(backup.BackupError, "bundle_members_mismatch"):
            backup.verify(directory)
        item.write_bytes(b"original")
        extra = directory / "extra"
        extra.write_text("extra")
        with self.assertRaisesRegex(backup.BackupError, "bundle_members_mismatch"):
            backup.verify(directory)
        extra.unlink()
        item.unlink()
        item.symlink_to(self.root / "outside")
        with self.assertRaisesRegex(backup.BackupError, "unsafe_bundle"):
            backup.verify(directory)

    def test_nested_manifest_is_not_ignored(self):
        directory = self.root / "bundle"
        (directory / "nested").mkdir(parents=True)
        (directory / "nested" / "manifest.json").write_text("stored content")
        backup.write_manifest(directory, {})
        self.assertEqual(backup.verify(directory), 1)
        (directory / "nested" / "manifest.json").unlink()
        with self.assertRaises(backup.BackupError):
            backup.verify(directory)

    def test_idle_rejects_open_unknown_and_foreign_sessions(self):
        class Cursor:
            def execute(self, *_args):
                pass
            def fetchone(self):
                return (0,)
            def fetchall(self):
                return self.rows
        cursor = Cursor()
        for row in (("active", None, True), ("idle", "transaction", True),
                    (None, None, True), ("idle", None, False)):
            cursor.rows = [row]
            with self.assertRaisesRegex(backup.BackupError, "database_not_idle"):
                backup.idle(cursor, "isolated")
        cursor.rows = [("idle", None, True)]
        backup.idle(cursor, "isolated")

    def test_filestore_rejects_symlinks_and_expired_capture(self):
        source = self.root / "filestore"
        source.mkdir()
        (source / "file").write_text("data")
        with self.assertRaisesRegex(backup.BackupError, "pause_timeout"):
            backup.copy_tree(source, self.root / "expired", time.monotonic() - 1)
        (source / "link").symlink_to(self.root)
        with self.assertRaisesRegex(backup.BackupError, "unsafe_filestore"):
            backup.copy_tree(source, self.root / "unsafe", time.monotonic() + 5)

    @unittest.skipUnless(shutil.which("openssl"), "OpenSSL required")
    def test_real_encryption_round_trip_and_private_key_rejection(self):
        private = self.root / "private.pem"
        public = self.root / "public.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                        "-subj", "/CN=Disposable recovery test/", "-keyout", str(private), "-out", str(public)],
                       check=True, capture_output=True)
        directory = self.root / "bundle"
        directory.mkdir()
        (directory / "data").write_bytes(b"private recovery content")
        backup.write_manifest(directory, {})
        artifact = self.root / "encrypted.p7m"
        backup.encrypt(directory, artifact, public)
        self.assertNotIn(b"private recovery content", artifact.read_bytes())
        restored = self.root / "restored.tar"
        subprocess.run(["openssl", "cms", "-decrypt", "-binary", "-inform", "DER", "-in", str(artifact),
                        "-recip", str(public), "-inkey", str(private), "-out", str(restored)], check=True, capture_output=True)
        import tarfile
        with tarfile.open(restored) as archive:
            self.assertEqual(archive.extractfile("data").read(), b"private recovery content")
        with self.assertRaisesRegex(backup.BackupError, "private_key_on_host"):
            backup.encrypt(directory, artifact, private)

    def fake_snapshot(self, _policy, directory):
        (directory / "database.dump").write_bytes(b"DISPOSABLE TEST DATA")

    def fake_encrypt(self, _directory, destination, _certificate):
        destination.write_bytes(b"TEST ENCRYPTED PAYLOAD")

    def test_success_requires_matching_durable_receipt(self):
        policy = backup.load_policy(self.policy_file())
        def delivery(_command, payload, _timeout):
            self.assertIn("captured_at", payload)
            self.assertEqual(payload["captured_at"], json.loads((Path(payload["artifact"]).parent / "bundle" / "manifest.json").read_text())["metadata"]["captured_at"])
            return {"durable": True, "sha256": payload["sha256"],
                    "destination": payload["destination"], "receipt_id": "test-receipt"}
        with patch.object(backup, "validate_certificate"), patch.object(backup, "encrypt", self.fake_encrypt), patch.object(backup, "adapter", side_effect=delivery):
            state = backup.capture(policy, self.fake_snapshot)
        self.assertEqual(state["status"], "success")
        self.assertIsNotNone(state["last_success"])
        self.assertEqual(state["last_success"]["at"], state["started_at"])
        self.assertEqual(state["last_success"]["receipt_id"], "test-receipt")
        self.assertEqual(state["last_success"]["run_id"], state["run_id"])
        self.assertEqual(list(Path(policy["state_dir"]).glob("capture-*")), [])
        self.assertEqual(backup.monitor(policy)["status"], "success")

    def test_failed_transport_preserves_previous_success_and_alerts(self):
        policy = backup.load_policy(self.policy_file())
        state_path = Path(policy["state_dir"]) / "status.json"
        previous = {"at": backup.now(), "sha256": "d" * 64}
        backup.atomic_json(state_path, {"last_success": previous})
        with patch.object(backup, "validate_certificate"), patch.object(backup, "encrypt", self.fake_encrypt), patch.object(backup, "adapter", return_value={}), patch.object(backup, "alert") as alert:
            with self.assertRaisesRegex(backup.BackupError, "delivery_not_verified"):
                backup.capture(policy, self.fake_snapshot)
            alert.assert_called_once()
        state = json.loads(state_path.read_text())
        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["last_success"], previous)

    def test_capture_exception_is_redacted_and_cleanup_occurs(self):
        policy = backup.load_policy(self.policy_file())
        def failure(_policy, _directory):
            raise ValueError("PASSWORD-MUST-NOT-LEAK")
        with patch.object(backup, "validate_certificate"), patch.object(backup, "alert", side_effect=RuntimeError("OTHER-SECRET")):
            with self.assertRaisesRegex(backup.BackupError, "^capture_failed$"):
                backup.capture(policy, failure)
        content = (Path(policy["state_dir"]) / "status.json").read_text()
        self.assertNotIn("SECRET", content)
        self.assertNotIn("PASSWORD", content)
        self.assertTrue(json.loads(content)["alert_failed"])
        self.assertEqual(list(Path(policy["state_dir"]).glob("capture-*")), [])

    def test_invalid_certificate_never_pauses_runtime(self):
        policy = backup.load_policy(self.policy_file())
        with patch.object(backup, "alert"), patch.object(backup, "capture_snapshot") as snapshot:
            with self.assertRaises(backup.BackupError):
                backup.capture(policy, snapshot)
            snapshot.assert_not_called()

    def test_corrupt_status_alerts_without_echoing_contents(self):
        policy = backup.load_policy(self.policy_file())
        path = Path(policy["state_dir"]) / "status.json"
        path.write_text("SECRET malformed state")
        path.chmod(0o600)
        with patch.object(backup, "alert") as alert:
            with self.assertRaises(backup.BackupError):
                backup.monitor(policy)
            self.assertEqual(alert.call_args.args[1], {"status": "failed"})

    def test_wrong_json_shapes_alert(self):
        policy = backup.load_policy(self.policy_file())
        path = Path(policy["state_dir"]) / "status.json"
        for value in (None, [], "unexpected"):
            backup.atomic_json(path, value)
            with self.subTest(value=value), patch.object(backup, "alert") as alert:
                with self.assertRaises(backup.BackupError):
                    backup.monitor(policy)
                alert.assert_called_once()

    def test_status_disk_failure_still_alerts(self):
        policy = backup.load_policy(self.policy_file())
        with patch.object(backup, "atomic_json", side_effect=OSError("private disk error")), patch.object(backup, "alert") as alert:
            with self.assertRaisesRegex(backup.BackupError, "^capture_failed$"):
                backup.capture(policy, self.fake_snapshot)
            alert.assert_called_once()
            self.assertTrue(alert.call_args.args[1]["status_write_failed"])

    def test_missing_and_overdue_success_alert(self):
        policy = backup.load_policy(self.policy_file())
        with patch.object(backup, "alert") as alert:
            with self.assertRaisesRegex(backup.BackupError, "backup_attention_required"):
                backup.monitor(policy)
            alert.assert_called_once()
        backup.atomic_json(Path(policy["state_dir"]) / "status.json", {
            "status": "running", "last_success": {"at": "2000-01-01T00:00:00+00:00"}})
        with patch.object(backup, "alert") as alert:
            with self.assertRaises(backup.BackupError):
                backup.monitor(policy)
            self.assertEqual(alert.call_args.args[1]["status"], "missed")


@unittest.skipUnless(sys.platform == "linux" and hasattr(os, "pidfd_open"), "Linux pidfds required")
class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.service = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
        self.master = backup.process(self.service.pid)

    def tearDown(self):
        self.service.send_signal(signal.SIGCONT)
        self.service.terminate()
        self.service.wait(timeout=5)

    def test_finally_resumes_on_capture_failure(self):
        with self.assertRaisesRegex(ValueError, "capture failure"):
            with backup.paused(self.master, 2):
                self.assertEqual(backup.process(self.service.pid)["state"], "T")
                raise ValueError("capture failure")
        self.assertNotEqual(backup.process(self.service.pid)["state"], "T")

    def test_independent_deadline_resumes_stalled_parent(self):
        with self.assertRaisesRegex(backup.BackupError, "pause_timeout"):
            with backup.paused(self.master, 0.15):
                time.sleep(0.4)
                self.assertNotEqual(backup.process(self.service.pid)["state"], "T")

    def test_watchdog_repeats_resume_if_parent_stops_after_deadline(self):
        original = signal.pidfd_send_signal
        def delayed_stop(handle, signum):
            if signum == signal.SIGSTOP:
                time.sleep(0.25)
                original(handle, signum)
                time.sleep(0.15)
                self.assertNotEqual(backup.process(self.service.pid)["state"], "T")
            else:
                original(handle, signum)
        with patch.object(backup.signal, "pidfd_send_signal", side_effect=delayed_stop):
            with self.assertRaisesRegex(backup.BackupError, "pause_timeout"):
                with backup.paused(self.master, 0.1):
                    self.fail("Expired pause must not yield a capture window")

    def test_command_timeout_stops_wrapper_child(self):
        with tempfile.TemporaryDirectory() as temporary:
            pid_file = Path(temporary) / "child.pid"
            program = "import subprocess,sys,time; from pathlib import Path; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(30)"
            with self.assertRaisesRegex(backup.BackupError, "command_failed"):
                backup.run([sys.executable, "-c", program, str(pid_file)], timeout=0.3)
            child = int(pid_file.read_text())
            deadline = time.monotonic() + 2
            record = backup.process(child)
            while record and record["state"] != "Z" and time.monotonic() < deadline:
                time.sleep(0.01)
                record = backup.process(child)
            self.assertTrue(record is None or record["state"] == "Z")

    def test_parent_kill_cannot_leave_service_paused(self):
        program = "import sys,time; sys.path.insert(0,sys.argv[1]); import hosted_backup as b; " + \
                  "exec(\"with b.paused(b.process(int(sys.argv[2])), 2):\\n print('paused', flush=True)\\n time.sleep(20)\")"
        parent = subprocess.Popen([sys.executable, "-c", program, str(Path(__file__).parent), str(self.service.pid)], stdout=subprocess.PIPE)
        try:
            self.assertEqual(parent.stdout.readline().strip(), b"paused")
            parent.kill()
            parent.wait(timeout=5)
            deadline = time.monotonic() + 3
            while backup.process(self.service.pid)["state"] == "T" and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertNotEqual(backup.process(self.service.pid)["state"], "T")
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.wait(timeout=5)
            parent.stdout.close()


@unittest.skipUnless(os.environ.get("TCSI_RECOVERY_TEST_PG") == "disposable-only", "Disposable PostgreSQL opt-in required")
class PostgreSQLCaptureTests(unittest.TestCase):
    """Opt-in CI fixture creates and drops only its own randomly named databases."""
    def setUp(self):
        import psycopg2
        from psycopg2 import sql
        if os.environ.get("PGHOST") != "127.0.0.1":
            raise RuntimeError("Recovery integration tests require loopback disposable PostgreSQL")
        self.psycopg2 = psycopg2
        self.sql = sql
        self.options = {"host": "127.0.0.1", "port": os.environ.get("PGPORT", "5432"),
                        "user": os.environ["PGUSER"], "password": os.environ["PGPASSWORD"]}
        self.admin = psycopg2.connect(dbname="postgres", **self.options)
        self.admin.autocommit = True
        self.database = "tcsi_recovery_test_" + uuid.uuid4().hex
        self.restored = self.database + "_restored"
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.service = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)
        with self.admin.cursor() as cursor:
            for name in (self.database, self.restored):
                cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        connection = psycopg2.connect(dbname=self.database, **self.options)
        with connection, connection.cursor() as cursor:
            cursor.execute("CREATE TABLE ledger (id integer PRIMARY KEY, amount numeric)")
            cursor.execute("INSERT INTO ledger VALUES (1, 123.45)")
            from recovery_fingerprint import REQUIRED
            for table in REQUIRED:
                columns = "id integer PRIMARY KEY"
                if table == "account_move_line":
                    columns += ", company_id integer, account_id integer, balance numeric, parent_state text"
                elif table == "ir_attachment":
                    columns += ", store_fname text, checksum text"
                cursor.execute(sql.SQL("CREATE TABLE {} ({})").format(sql.Identifier(table), sql.SQL(columns)))
            cursor.execute("INSERT INTO account_move_line VALUES (1, 1, 1, 123.450000000000001, 'posted')")
            import hashlib
            cursor.execute("INSERT INTO ir_attachment VALUES (1, 'attachment', %s)",
                           (hashlib.sha1(b"isolated attachment bytes").hexdigest(),))
        connection.close()
        filestore = self.root / "data" / "filestore" / self.database
        filestore.mkdir(parents=True)
        (filestore / "attachment").write_bytes(b"isolated attachment bytes")
        self.directory = self.root / "bundle"
        self.directory.mkdir()
        self.policy = {"database": self.database, "data_dir": str(self.root / "data"), "max_pause_seconds": 10}

    def tearDown(self):
        self.service.send_signal(signal.SIGCONT)
        self.service.terminate()
        self.service.wait(timeout=5)
        with self.admin.cursor() as cursor:
            for name in (self.database, self.restored):
                cursor.execute(self.sql.SQL("DROP DATABASE {} WITH (FORCE)").format(self.sql.Identifier(name)))
        self.admin.close()
        self.temporary.cleanup()

    def runtime(self):
        options = {"db_" + key: str(value) for key, value in self.options.items()}
        return backup.process(self.service.pid), options, b"[options]\n# disposable recovery fixture\n", {}

    def test_real_dump_restore_and_filestore_manifest(self):
        with patch.object(backup, "discover", return_value=self.runtime()):
            backup.capture_snapshot(self.policy, self.directory)
        self.assertNotEqual(backup.process(self.service.pid)["state"], "T")
        self.assertEqual((self.directory / "filestore" / "attachment").read_bytes(), b"isolated attachment bytes")
        backup.write_manifest(self.directory, {"database": self.database})
        self.assertEqual(backup.verify(self.directory), 5)
        baseline = json.loads((self.directory / "accounting-baseline.json").read_text())
        self.assertEqual(baseline["tables"]["account_move_line"]["count"], 1)
        self.assertEqual(baseline["files"]["attachment"]["size"], len(b"isolated attachment bytes"))
        environment = {**os.environ, "PGDATABASE": self.restored}
        backup.run(["pg_restore", "--no-owner", "--no-acl", "--dbname", self.restored,
                    str(self.directory / "database.dump")], timeout=10, environment=environment)
        connection = self.psycopg2.connect(dbname=self.restored, **self.options)
        with connection, connection.cursor() as cursor:
            cursor.execute("SELECT id, amount::text FROM ledger")
            self.assertEqual(cursor.fetchall(), [(1, "123.45")])
        connection.close()

    def test_open_transaction_prevents_pause(self):
        connection = self.psycopg2.connect(dbname=self.database, **self.options)
        try:
            with connection.cursor() as cursor:
                cursor.execute("UPDATE ledger SET amount = 456 WHERE id = 1")
            with patch.object(backup, "discover", return_value=self.runtime()), patch.object(backup, "paused") as paused:
                with self.assertRaisesRegex(backup.BackupError, "database_not_idle"):
                    backup.capture_snapshot(self.policy, self.directory)
                paused.assert_not_called()
        finally:
            connection.rollback()
            connection.close()


if __name__ == "__main__":
    unittest.main()
