"""Offline regression for paired-backup delivery, retention, scheduling and configuration."""
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docker/odoo"))
import backup_runtime as runtime
import backup_store as storage
import hosted_backup as backup


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.deleted = []
        self.fail_upload = False
        self.corrupt_upload = False

    def put_object(self, *, Bucket, Key, Body, **kwargs):
        self.objects[Key] = (Body, kwargs.get("Metadata", {}))

    def get_object(self, *, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[Key][0])}

    def head_object(self, *, Bucket, Key):
        body, metadata = self.objects[Key]
        return {"ContentLength": len(body), "Metadata": metadata}

    def upload_fileobj(self, stream, bucket, key, ExtraArgs):
        if self.fail_upload:
            raise OSError("private provider detail")
        body = stream.read()
        if self.corrupt_upload:
            body = b"x" * len(body)
        self.objects[key] = (body, ExtraArgs["Metadata"])

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        return self

    def paginate(self, *, Bucket, Prefix):
        return [{"Contents": [{"Key": key} for key in list(self.objects) if key.startswith(Prefix)]}]

    def delete_object(self, *, Bucket, Key):
        self.deleted.append(Key)
        del self.objects[Key]


def environment():
    return {"TCSI_BACKUP_ENABLED": "1", "TCSI_BACKUP_S3_ENDPOINT": "https://storage.example.invalid",
            "TCSI_BACKUP_S3_REGION": "test", "TCSI_BACKUP_S3_BUCKET": "private-test",
            "TCSI_BACKUP_S3_ACCESS_KEY_ID": "test-id", "TCSI_BACKUP_S3_SECRET_ACCESS_KEY": "test-secret",
            "TCSI_BACKUP_PREFIX": "test-installation", "TCSI_BACKUP_MONITOR_ID": "test-monitor",
            "TCSI_RELEASE_SHA": "a" * 40, "TCSI_RELEASE_IMAGE": "registry/test@sha256:" + "b" * 64,
            "TCSI_BACKUP_PUBLIC_CERTIFICATE": "-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----",
            "TCSI_BACKUP_OPERATOR": "Test operator", "TCSI_BACKUP_RESTORE_CONTACT": "Test operator",
            "PGDATABASE": "test_database"}


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.s3 = FakeS3()
        self.store = storage.Store(storage.configuration(environment()), self.s3)
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        artifact = self.directory / "encrypted.p7m"
        artifact.write_bytes(b"test encrypted artifact bytes")
        artifact.chmod(0o600)
        self.payload = {"artifact": str(artifact), "sha256": backup.digest(artifact),
                        "run_id": str(uuid.uuid4()), "destination": "test-installation"}

    def seed(self, days):
        run_id = str(uuid.uuid4())
        body = b"previous encrypted object"
        key = self.store.object_key(run_id)
        receipt = {"format": 1, "status": "success", "run_id": run_id, "object": key,
                   "sha256": hashlib.sha256(body).hexdigest(), "size": len(body),
                   "at": (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()}
        self.s3.objects[key] = (body, {"sha256": receipt["sha256"]})
        self.store.write(self.store.prefix + "receipts/" + run_id + ".json", receipt)
        return receipt

    def test_verified_delivery_receipt_and_monitor(self):
        result = self.store.deliver(self.payload)
        self.assertTrue(result["durable"])
        self.assertEqual(result["sha256"], self.payload["sha256"])
        self.assertEqual(self.store.monitor(), {"status": "success"})

    def test_upload_failure_preserves_prior_receipt_and_every_old_object(self):
        previous = self.seed(40)
        self.store.write(self.store.prefix + "status.json", previous)
        self.s3.fail_upload = True
        with self.assertRaises(OSError):
            self.store.deliver(self.payload)
        self.assertEqual(self.store.read(self.store.prefix + "status.json"), previous)
        self.assertEqual(self.s3.deleted, [])

    def test_remote_bytes_must_match_not_just_metadata(self):
        self.s3.corrupt_upload = True
        with self.assertRaisesRegex(backup.BackupError, "remote_object_mismatch"):
            self.store.deliver(self.payload)
        self.assertNotIn(self.store.prefix + "status.json", self.s3.objects)
        self.assertEqual(self.s3.deleted, [])

    def test_retention_only_verified_old_owned_objects_after_new_delivery(self):
        old = self.seed(31)
        recent = self.seed(29)
        unrelated = "other-installation/objects/unrelated.p7m"
        self.s3.objects[unrelated] = (b"unrelated", {})
        self.s3.objects[self.store.prefix + "objects/orphan.p7m"] = (b"unverified", {})
        self.store.deliver(self.payload)
        self.assertEqual(set(self.s3.deleted), {old["object"], self.store.prefix + "receipts/" + old["run_id"] + ".json"})
        self.assertIn(recent["object"], self.s3.objects)
        self.assertIn(unrelated, self.s3.objects)
        self.assertIn(self.store.prefix + "objects/orphan.p7m", self.s3.objects)

    def test_forged_retention_receipt_cannot_delete_foreign_object(self):
        old = self.seed(40)
        old["object"] = "other-installation/customer-data"
        self.store.write(self.store.prefix + "receipts/" + old["run_id"] + ".json", old)
        with self.assertRaises(backup.BackupError):
            self.store.deliver(self.payload)
        self.assertEqual(self.s3.deleted, [])

    def test_retention_resumes_only_explicit_missing_object_after_interruption(self):
        old = self.seed(40)
        error = RuntimeError("not found")
        error.response = {"Error": {"Code": "404"}}
        original = self.s3.head_object
        def head(**kwargs):
            if kwargs["Key"] == old["object"]:
                raise error
            return original(**kwargs)
        with mock.patch.object(self.s3, "head_object", side_effect=head):
            self.store.deliver(self.payload)
        self.assertNotIn(old["object"], self.s3.objects)

    def test_monitor_rejects_missing_old_future_and_deleted_objects(self):
        with self.assertRaises(KeyError):
            self.store.monitor()
        self.store.deliver(self.payload)
        status = self.store.read(self.store.prefix + "status.json")
        at = datetime.fromisoformat(status["at"])
        for moment in (at + timedelta(hours=28), at - timedelta(seconds=1)):
            with self.assertRaises(backup.BackupError):
                self.store.monitor(moment)
        del self.s3.objects[status["object"]]
        with self.assertRaises(KeyError):
            self.store.monitor(at)

    def test_attention_is_durable_queue_acceptance_and_monitor_fails(self):
        self.store.deliver(self.payload)
        result = self.store.attention({"event": "backup_attention", "status": "failed", "at": backup.now(), "run_id": self.payload["run_id"]})
        self.assertEqual(result, {"accepted": True, "channel": "durable_attention_queue"})
        with self.assertRaises((KeyError, backup.BackupError)):
            self.store.monitor()
        with mock.patch.object(self.store, "write", side_effect=OSError):
            with self.assertRaises(OSError):
                self.store.attention({"event": "backup_attention", "status": "failed", "at": backup.now()})

    def test_monitor_rejects_changed_receipt_or_metadata(self):
        self.store.deliver(self.payload)
        status = self.store.read(self.store.prefix + "status.json")
        body, _metadata = self.s3.objects[status["object"]]
        self.s3.objects[status["object"]] = (body, {"sha256": "0" * 64})
        with self.assertRaises(backup.BackupError):
            self.store.monitor()


class ConfigurationTests(unittest.TestCase):
    def test_disabled_requires_no_secrets(self):
        self.assertIsNone(runtime.prepare({}))

    def test_missing_secret_monitor_or_insecure_endpoint_fails_closed(self):
        for key in ("TCSI_BACKUP_S3_SECRET_ACCESS_KEY", "TCSI_BACKUP_MONITOR_ID", "TCSI_RELEASE_SHA"):
            env = environment()
            env.pop(key)
            with self.subTest(key=key), self.assertRaises(backup.BackupError):
                runtime.prepare(env)
        for endpoint in ("http://example.invalid", "https://user:secret@example.invalid", "https://example.invalid/?token=secret"):
            env = environment()
            env["TCSI_BACKUP_S3_ENDPOINT"] = endpoint
            with self.assertRaises(backup.BackupError):
                runtime.prepare(env)

    def test_revision_mismatch_or_private_key_rejected(self):
        for key, value in (("RAILWAY_GIT_COMMIT_SHA", "c" * 40), ("TCSI_RELEASE_IMAGE", "latest"),
                           ("TCSI_BACKUP_PUBLIC_CERTIFICATE", "-----BEGIN PRIVATE KEY-----")):
            env = environment()
            env[key] = value
            with self.assertRaises(backup.BackupError):
                runtime.prepare(env)

    def test_private_policy_exact_release_and_no_automatic_startup_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            env = environment()
            with mock.patch.object(runtime, "STATE", state), mock.patch.object(backup, "validate_certificate"), mock.patch.object(backup, "load_policy"):
                command = runtime.prepare(env)
            self.assertEqual(command[-1], "schedule")
            self.assertEqual(env["RAILWAY_GIT_COMMIT_SHA"], env["TCSI_RELEASE_SHA"])
            policy = json.loads(backup.private_read(state / "policy.json"))
            self.assertEqual(policy["max_pause_seconds"], 120)
            self.assertEqual(policy["source_revision"], env["TCSI_RELEASE_SHA"])
            self.assertEqual(policy["operator"], policy["deputy"])
            self.assertEqual((state / "adapter.json").stat().st_mode & 0o077, 0)

    def test_daily_0300_singapore_never_runs_at_startup_or_twice_at_boundary(self):
        before = datetime(2026, 10, 12, 18, 59, tzinfo=timezone.utc)
        boundary = datetime(2026, 10, 12, 19, 0, tzinfo=timezone.utc)
        self.assertEqual(runtime.next_capture(before), boundary)
        self.assertEqual(runtime.next_capture(boundary), boundary + timedelta(days=1))
        self.assertEqual(runtime.next_capture(boundary + timedelta(minutes=1)), boundary + timedelta(days=1))

    def test_monitor_cli_never_prints_secret_provider_exception(self):
        with mock.patch.object(sys, "argv", ["backup_runtime.py", "monitor"]), mock.patch.dict(os.environ, environment()), mock.patch.object(runtime, "Store", side_effect=RuntimeError("private-token")), mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(runtime.main(), 1)
            self.assertNotIn("private-token", output.getvalue())

    def test_bounded_capture_retries_stop_after_success(self):
        for statuses, expected_calls, expected_sleeps in (([0], 1, 0), ([1, 0], 2, 1), ([1, 1, 1], 3, 2)):
            with self.subTest(statuses=statuses), mock.patch.object(runtime.subprocess, "run", side_effect=[mock.Mock(returncode=status) for status in statuses]) as run, mock.patch.object(runtime.time, "sleep") as sleep, mock.patch("builtins.print"):
                runtime.capture_with_retries()
            self.assertEqual(run.call_count, expected_calls)
            self.assertEqual(sleep.call_args_list, [mock.call(900)] * expected_sleeps)

    def test_independent_compose_passes_optional_settings_disabled_by_default(self):
        compose = (ROOT / "docker-compose.independent.yml").read_text()
        example = (ROOT / "config/independent.env.example").read_text()
        self.assertIn("TCSI_BACKUP_ENABLED: ${TCSI_BACKUP_ENABLED:-0}", compose)
        self.assertIn("TCSI_BACKUP_ENABLED=0", example)
        for key in environment():
            if key.startswith(("TCSI_BACKUP_", "TCSI_RELEASE_")) and key != "TCSI_BACKUP_ENABLED":
                self.assertIn(f"{key}: ${{{key}:-}}", compose)
                self.assertIn(f"{key}=\n", example)


if __name__ == "__main__":
    unittest.main()
