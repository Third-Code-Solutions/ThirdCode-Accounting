"""No network: versioned provider model, HTTPS contracts and real crypto drill."""
from datetime import timedelta
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import uuid

try:
    import boto3
except ImportError:
    boto3 = None

import hosted_backup as capture
import hosted_recovery_drill as drill
import hosted_recovery_provider as provider


class CloudError(Exception):
    def __init__(self, code):
        self.response = {"Error": {"Code": code}}


class FakeS3:
    def __init__(self):
        self.objects, self.deleted = {}, []
        self.enabled = self.locked = True
        self.corrupt_upload = False

    def get_bucket_versioning(self, **_args):
        return {"Status": "Enabled" if self.enabled else "Suspended"}

    def get_object_lock_configuration(self, **_args):
        return {"ObjectLockConfiguration": {"ObjectLockEnabled": "Enabled" if self.locked else "Disabled"}}

    def put_object(self, **args):
        key = args["Key"]
        if args.get("IfNoneMatch") != "*":
            raise AssertionError("Conditional create required")
        if key in self.objects:
            raise CloudError("PreconditionFailed")
        body = args["Body"].read() if hasattr(args["Body"], "read") else args["Body"]
        self.objects[key] = {"Body": body + (b"CORRUPT" if self.corrupt_upload else b""),
                             "VersionId": str(uuid.uuid4()), "Metadata": args.get("Metadata", {}),
                             "LastModified": provider.utcnow(), "Retention": {"Mode": args["ObjectLockMode"],
                             "RetainUntilDate": args["ObjectLockRetainUntilDate"].replace(microsecond=0)}, "LegalHold": {"Status": "OFF"}}
        return {"VersionId": self.objects[key]["VersionId"]}

    def head_object(self, **args):
        item = self.objects.get(args["Key"])
        if not item or args.get("VersionId", item["VersionId"]) != item["VersionId"]:
            raise CloudError("NoSuchVersion")
        return {**item, "ContentLength": len(item["Body"])}

    def get_object(self, **args):
        item = self.head_object(**args)
        return {**item, "Body": io.BytesIO(item["Body"])}

    def get_object_retention(self, **args):
        return {"Retention": self.head_object(**args)["Retention"]}

    def get_object_legal_hold(self, **args):
        return {"LegalHold": self.head_object(**args)["LegalHold"]}

    def list_objects_v2(self, **args):
        return {"IsTruncated": False, "Contents": [{"Key": key} for key in self.objects if key.startswith(args["Prefix"])]}

    def delete_object(self, **args):
        if "BypassGovernanceRetention" in args:
            raise AssertionError("Retention bypass forbidden")
        item = self.head_object(**args)
        if item["LegalHold"]["Status"] == "ON" or item["Retention"]["RetainUntilDate"] > provider.utcnow():
            raise CloudError("AccessDenied")
        self.deleted.append(args)
        del self.objects[args["Key"]]
        return {}


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.policy = {
            "enabled": True, "approval_reference": "test-approval", "operator": "test-owner", "deputy": "test-deputy",
            "independent_destination_confirmed": True, "private_bucket_confirmed": True,
            "destination": "test-vault", "bucket": "test-private-bucket", "prefix": "tcsi/test/",
            "region": "us-east-1", "credentials_file": str(self.root / "credentials.json"),
            "artifact_root": str(self.root), "maximum_success_age_seconds": 86400, "rpo_seconds": 86400,
            "rto_seconds": 14400, "operation_timeout_seconds": 900, "maximum_artifact_bytes": 10000000,
            "retention": {"approval_reference": "test-operations-policy", "days": 35, "keep_minimum": 2, "apply_enabled": True},
            "alert": {"enabled": True, "approval_reference": "test-alert", "recipient": "test-recipient",
                      "url": "https://alerts.example.invalid/recovery", "token_file": str(self.root / "token"), "deduplication_seconds": 3600},
        }
        (self.root / "token").write_text("private-test-token")
        (self.root / "token").chmod(0o600)
        self.client = FakeS3()
        self.artifact = self.root / "recovery.p7m"
        self.artifact.write_bytes(b"disposable encrypted fixture")
        self.artifact.chmod(0o600)
        self.payload = {"artifact": str(self.artifact), "sha256": capture.digest(self.artifact),
                        "destination": self.policy["destination"], "run_id": str(uuid.uuid4()),
                        "captured_at": provider.utcnow().isoformat()}

    def tearDown(self):
        self.temporary.cleanup()

    def delivery(self, payload=None):
        with patch.object(provider, "validate_envelope"):
            return provider.deliver(self.policy, payload or self.payload, self.client)

    def policy_file(self):
        path = self.root / "policy.json"
        capture.atomic_json(path, self.policy)
        return path

    def test_policy_requires_actual_approval_and_access_details(self):
        provider.load_policy(self.policy_file())
        for name, value in (("enabled", False), ("deputy", ""), ("bucket", ""), ("independent_destination_confirmed", False)):
            previous = self.policy[name]
            self.policy[name] = value
            with self.subTest(name=name), self.assertRaises(provider.ProviderError):
                provider.load_policy(self.policy_file())
            self.policy[name] = previous

    def test_paths_and_transport_are_restricted(self):
        for url in ("http://storage.invalid", "https://user:secret@storage.invalid", "https://storage.invalid/?token=secret"):
            self.policy["endpoint_url"] = url
            with self.subTest(url=url), self.assertRaises(provider.ProviderError):
                provider.load_policy(self.policy_file())
        for prefix in ("", "/", "../", "broad//prefix/", "bucket/"):
            self.policy.pop("endpoint_url", None)
            self.policy["prefix"] = prefix
            if prefix == "bucket/":
                provider.load_policy(self.policy_file())
            else:
                with self.assertRaises(provider.ProviderError):
                    provider.load_policy(self.policy_file())

    def test_delivery_checks_remote_bytes_and_exact_locked_versions(self):
        receipt = self.delivery()
        self.assertTrue(receipt["durable"])
        remote = provider.get_receipt(self.client, self.policy, self.payload["run_id"])
        self.assertEqual(remote["sha256"], self.payload["sha256"])
        self.assertEqual(len(self.client.objects), 2)
        self.assertEqual(self.delivery(), receipt)
        self.assertEqual(len(self.client.objects), 2)

    def test_corrupt_upload_never_yields_durable_receipt(self):
        self.client.corrupt_upload = True
        with self.assertRaises(provider.ProviderError):
            self.delivery()
        self.assertFalse(any("/receipts/" in key for key in self.client.objects))

    def test_plaintext_cannot_reach_provider(self):
        with self.assertRaisesRegex(provider.ProviderError, "encrypted_cms_required"):
            provider.deliver(self.policy, self.payload, self.client)
        self.assertEqual(self.client.objects, {})

    def test_missing_versioning_or_lock_fails_before_upload(self):
        for setting in ("enabled", "locked"):
            setattr(self.client, setting, False)
            with self.subTest(setting=setting), self.assertRaises(provider.ProviderError):
                self.delivery()
            self.assertEqual(self.client.objects, {})
            setattr(self.client, setting, True)

    def test_same_run_different_payload_is_not_overwritten(self):
        self.delivery()
        self.artifact.write_bytes(b"changed encrypted fixture")
        changed = {**self.payload, "sha256": capture.digest(self.artifact)}
        with self.assertRaises(provider.ProviderError):
            self.delivery(changed)
        self.assertEqual(len(self.client.objects), 2)

    def test_retries_do_not_refresh_original_recovery_time(self):
        earlier = provider.utcnow() - timedelta(days=2)
        self.payload["captured_at"] = earlier.isoformat()
        with patch.object(provider, "utcnow", return_value=earlier):
            self.delivery()
        self.delivery()
        receipt = provider.get_receipt(self.client, self.policy, self.payload["run_id"])
        self.assertEqual(provider.timestamp(receipt["verified_at"]), earlier)
        with patch.object(provider, "send_alert") as alert:
            with self.assertRaises(provider.ProviderError):
                provider.monitor(self.policy, self.client, notify=alert)
            alert.assert_called_once()

    def test_recent_upload_of_stale_capture_stays_overdue(self):
        self.payload["captured_at"] = (provider.utcnow() - timedelta(days=2)).isoformat()
        self.delivery()
        receipt = provider.get_receipt(self.client, self.policy, self.payload["run_id"])
        self.assertLess((provider.utcnow() - provider.timestamp(receipt["verified_at"])).total_seconds(), 60)
        with patch.object(provider, "send_alert") as alert:
            with self.assertRaises(provider.ProviderError):
                provider.monitor(self.policy, self.client, notify=alert)
            alert.assert_called_once()
        changed = {**self.payload, "captured_at": provider.utcnow().isoformat()}
        with self.assertRaisesRegex(provider.ProviderError, "receipt_conflict"):
            self.delivery(changed)

    def test_missing_or_future_capture_timestamp_cannot_upload(self):
        missing = {key: value for key, value in self.payload.items() if key != "captured_at"}
        with self.assertRaises(KeyError):
            self.delivery(missing)
        with self.assertRaisesRegex(provider.ProviderError, "future_capture_time"):
            self.delivery({**self.payload, "captured_at": (provider.utcnow() + timedelta(hours=1)).isoformat()})
        self.assertEqual(self.client.objects, {})

    def test_shortened_lock_rejected_on_retry_and_independent_monitor(self):
        self.delivery()
        key, _ = provider.keys(self.policy, self.payload["run_id"])
        self.client.objects[key]["Retention"]["RetainUntilDate"] = provider.utcnow() + timedelta(hours=1)
        with self.assertRaisesRegex(provider.ProviderError, "object_lock_horizon_too_short"):
            self.delivery()
        with patch.object(provider, "send_alert") as alert:
            with self.assertRaises(provider.ProviderError):
                provider.monitor(self.policy, self.client, notify=alert)
            alert.assert_called_once()

    def test_offhost_monitor_detects_absent_deleted_and_unreachable(self):
        with patch.object(provider, "send_alert") as alert:
            with self.assertRaises(provider.ProviderError):
                provider.monitor(self.policy, self.client, notify=alert)
        self.delivery()
        self.assertEqual(provider.monitor(self.policy, self.client)["status"], "fresh")
        key, _ = provider.keys(self.policy, self.payload["run_id"])
        del self.client.objects[key]
        with patch.object(provider, "send_alert") as alert:
            with self.assertRaises(provider.ProviderError):
                provider.monitor(self.policy, self.client, notify=alert)
            alert.assert_called_once()
        with patch.object(self.client, "list_objects_v2", side_effect=OSError("private provider failure")):
            with patch.object(provider, "send_alert") as alert:
                with self.assertRaises(provider.ProviderError):
                    provider.monitor(self.policy, self.client, notify=alert)
                alert.assert_called_once()

    def test_alert_requires_matching_ack_and_retains_no_raw_error(self):
        class Response:
            status = 202
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                pass
            def read(self, _maximum):
                return json.dumps({"accepted": True, "event_id": self.event_id}).encode()
        class Opener:
            def open(self, request, timeout):
                self.request, self.timeout = request, timeout
                response = Response()
                response.event_id = request.get_header("Idempotency-key")
                return response
        opener = Opener()
        event = {"status": "missed", "run_id": None}
        self.assertEqual(provider.send_alert(self.policy, event, opener), {"accepted": True})
        self.assertEqual(opener.request.get_header("Authorization"), "Bearer private-test-token")
        payload = json.loads(opener.request.data)
        self.assertEqual(payload["recipient"], "test-recipient")
        self.assertNotIn("token", opener.request.data.decode())
        with patch.object(Response, "read", return_value=b'{"accepted":true}'):
            with self.assertRaisesRegex(provider.ProviderError, "alert_not_acknowledged"):
                provider.send_alert(self.policy, event, opener)
        with self.assertRaisesRegex(provider.ProviderError, "alert_redirect_rejected"):
            provider.NoRedirect().redirect_request(None, None, None, None, None, None)

    def seed_history(self):
        current = provider.utcnow()
        for index, age in enumerate((0, 1, 50, 70)):
            with patch.object(provider, "utcnow", return_value=current - timedelta(days=age)):
                self.delivery({**self.payload, "run_id": str(uuid.UUID(int=index + 1)),
                               "captured_at": (current - timedelta(days=age)).isoformat()})

    def test_retention_requires_plan_policy_and_preserves_latest(self):
        self.seed_history()
        plan = provider.retention_plan(self.policy, self.client)
        self.assertEqual(len(plan["delete"]), 2)
        approved = hashlib.sha256(provider.canonical(plan)).hexdigest()
        self.policy["retention"]["apply_enabled"] = False
        with self.assertRaisesRegex(provider.ProviderError, "retention_apply_not_enabled"):
            provider.retention_apply(self.policy, self.client, plan, approved)
        self.policy["retention"]["apply_enabled"] = True
        with self.assertRaisesRegex(provider.ProviderError, "retention_plan_approval_mismatch"):
            provider.retention_apply(self.policy, self.client, plan, "0" * 64)
        result = provider.retention_apply(self.policy, self.client, plan, approved)
        self.assertEqual(len(result["deleted_run_ids"]), 2)
        self.assertEqual(len(self.client.objects), 4)
        self.assertTrue(all("VersionId" in entry and "BypassGovernanceRetention" not in entry for entry in self.client.deleted))

    def test_retention_journal_failure_prevents_first_delete(self):
        self.seed_history()
        plan = provider.retention_plan(self.policy, self.client)
        approved = hashlib.sha256(provider.canonical(plan)).hexdigest()
        def storage_failed(_value):
            raise OSError("disposable full state volume")
        with self.assertRaises(OSError):
            provider.retention_apply(self.policy, self.client, plan, approved, storage_failed)
        self.assertEqual(self.client.deleted, [])

    def test_retention_partial_failure_journal_identifies_exact_version(self):
        self.seed_history()
        plan = provider.retention_plan(self.policy, self.client)
        approved = hashlib.sha256(provider.canonical(plan)).hexdigest()
        progress = []
        original = self.client.delete_object
        def fail_second(**args):
            if self.client.deleted:
                raise CloudError("ServiceUnavailable")
            return original(**args)
        with patch.object(self.client, "delete_object", side_effect=fail_second), self.assertRaises(CloudError):
            provider.retention_apply(self.policy, self.client, plan, approved, progress.append)
        self.assertEqual(len(self.client.deleted), 1)
        self.assertEqual(progress[-1]["status"], "pending_delete")
        self.assertEqual(progress[-1]["key"], plan["delete"][0]["receipt_key"])
        self.assertEqual(progress[-1]["version_id"], plan["delete"][0]["receipt_version"])
        self.assertEqual(progress[-1]["completed_run_ids"], [])

    def test_tampered_arbitrary_key_and_legal_hold_cannot_delete(self):
        self.seed_history()
        plan = provider.retention_plan(self.policy, self.client)
        original = plan["delete"][0]["key"]
        plan["delete"][0]["key"] = "another-client/valuable.p7m"
        with self.assertRaises(provider.ProviderError):
            provider.retention_apply(self.policy, self.client, plan, hashlib.sha256(provider.canonical(plan)).hexdigest())
        self.assertEqual(self.client.deleted, [])
        plan["delete"][0]["key"] = original
        self.client.objects[original]["LegalHold"]["Status"] = "ON"
        with self.assertRaisesRegex(provider.ProviderError, "object_retention_protects_version"):
            provider.retention_apply(self.policy, self.client, plan, hashlib.sha256(provider.canonical(plan)).hexdigest())
        self.assertEqual(self.client.deleted, [])

    def test_retention_stops_if_latest_backup_missing(self):
        self.seed_history()
        key, _ = provider.keys(self.policy, str(uuid.UUID(int=1)))
        del self.client.objects[key]
        with self.assertRaises(CloudError):
            provider.retention_plan(self.policy, self.client)

    def test_archive_rejects_traversal_link_duplicate_and_limit(self):
        for index, variant in enumerate(("traversal", "link", "duplicate", "limit")):
            archive = self.root / f"{variant}.tar"
            with tarfile.open(archive, "w") as output:
                entry = tarfile.TarInfo("../escape" if variant == "traversal" else "data")
                entry.size = 4
                if variant == "link":
                    entry.type, entry.linkname, entry.size = tarfile.SYMTYPE, "/etc/passwd", 0
                output.addfile(entry, io.BytesIO(b"data") if entry.isfile() else None)
                if variant == "duplicate":
                    output.addfile(entry, io.BytesIO(b"data"))
            with self.subTest(variant=variant), self.assertRaises(provider.ProviderError):
                drill.extract_regular(archive, self.root / f"extract-{index}", 1 if variant == "limit" else 1000)

    @unittest.skipUnless(shutil.which("openssl"), "OpenSSL required")
    def test_real_offhost_decryption_and_manifest_drill(self):
        private, public = self.root / "key.pem", self.root / "public.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj",
                        "/CN=Disposable operator drill/", "-keyout", str(private), "-out", str(public)], check=True, capture_output=True)
        private.chmod(0o600)
        bundle = self.root / "bundle"
        bundle.mkdir()
        (bundle / "database.dump").write_bytes(b"synthetic test dump")
        capture.write_manifest(bundle, {"database": "disposable_fixture", "captured_at": self.payload["captured_at"]})
        capture.encrypt(bundle, self.artifact, public)
        self.payload["sha256"] = capture.digest(self.artifact)
        provider.deliver(self.policy, self.payload, self.client)
        output = self.root / "drill"
        result = drill.prepare(self.policy, self.client, self.payload["run_id"], output, private, public, confirm_offhost=True)
        self.assertEqual(result["verified_files"], 1)
        self.assertFalse(result["database_restore_verified"])
        self.assertIsNone(result["rto_met"])
        self.assertEqual((output / "payload/database.dump").read_bytes(), b"synthetic test dump")
        with self.assertRaisesRegex(provider.ProviderError, "new_private_output_required"):
            drill.prepare(self.policy, self.client, self.payload["run_id"], output, private, public, confirm_offhost=True)
        # Ciphertext identity matches, but an altered claimed capture timestamp
        # cannot become accepted restore evidence after decrypting the manifest.
        _key, receipt_key = provider.keys(self.policy, self.payload["run_id"])
        remote = self.client.objects[receipt_key]
        receipt = json.loads(remote["Body"])
        receipt["captured_at"] = (provider.timestamp(receipt["captured_at"]) - timedelta(seconds=1)).isoformat()
        remote["Body"] = provider.canonical(receipt)
        failed_output = self.root / "mismatched-capture"
        with self.assertRaisesRegex(provider.ProviderError, "capture_receipt_manifest_mismatch"):
            drill.prepare(self.policy, self.client, self.payload["run_id"], failed_output, private, public, confirm_offhost=True)
        self.assertFalse(failed_output.exists())
        self.assertEqual((output / "payload/database.dump").read_bytes(), b"synthetic test dump")
        with patch.dict(os.environ, {"RAILWAY_PROJECT_ID": "production-host"}):
            with self.assertRaisesRegex(provider.ProviderError, "separate_recovery_host_required"):
                drill.prepare(self.policy, self.client, self.payload["run_id"], self.root / "other", private, public, confirm_offhost=True)

    @unittest.skipUnless(boto3, "Install pinned recovery-provider-requirements.txt for SDK contract gate")
    def test_actual_sdk_accepts_conditional_locked_version_contract(self):
        from botocore.stub import ANY, Stubber
        from botocore.response import StreamingBody
        import base64
        credentials = Path(self.policy["credentials_file"])
        capture.atomic_json(credentials, {"access_key_id": "test-key", "secret_access_key": "test-secret"})
        self.policy["endpoint_url"] = "https://s3.example.invalid"
        client = provider.s3_client(self.policy)
        current = provider.utcnow()
        until = (current + timedelta(days=35, seconds=self.policy["operation_timeout_seconds"])).replace(microsecond=0) + timedelta(seconds=1)
        key, receipt_key = provider.keys(self.policy, self.payload["run_id"])
        size = self.artifact.stat().st_size
        receipt = {"format": 1, "run_id": self.payload["run_id"], "destination": self.policy["destination"],
                   "key": key, "version_id": "payload-v1", "sha256": self.payload["sha256"], "size": size,
                   "captured_at": self.payload["captured_at"], "verified_at": current.isoformat(),
                   "readback_verified_at": current.isoformat(), "retain_until": until.isoformat()}
        wire = client._serializer.serialize_to_request(
            {"Bucket": self.policy["bucket"], "Key": key, "Body": b"fixture", "ObjectLockMode": "GOVERNANCE",
             "ObjectLockRetainUntilDate": until}, client.meta.service_model.operation_model("PutObject"))
        self.assertEqual(provider.timestamp(wire["headers"]["x-amz-object-lock-retain-until-date"]), until)
        encoded = provider.canonical(receipt)
        bucket = self.policy["bucket"]
        with Stubber(client) as stubber:
            stubber.add_response("get_bucket_versioning", {"Status": "Enabled"}, {"Bucket": bucket})
            stubber.add_response("get_object_lock_configuration", {"ObjectLockConfiguration": {"ObjectLockEnabled": "Enabled"}}, {"Bucket": bucket})
            stubber.add_response("put_object", {"VersionId": "payload-v1"}, {
                "Bucket": bucket, "Key": key, "Body": ANY, "ContentLength": size, "ContentType": "application/pkcs7-mime",
                "ChecksumAlgorithm": "SHA256", "ChecksumSHA256": base64.b64encode(bytes.fromhex(self.payload["sha256"])).decode(), "IfNoneMatch": "*",
                "ObjectLockMode": "GOVERNANCE", "ObjectLockRetainUntilDate": until,
                "Metadata": {"sha256": self.payload["sha256"], "run-id": self.payload["run_id"]}})
            stubber.add_response("get_object", {"VersionId": "payload-v1", "ContentLength": size,
                "Body": StreamingBody(io.BytesIO(self.artifact.read_bytes()), size)}, {"Bucket": bucket, "Key": key, "VersionId": "payload-v1"})
            stubber.add_response("head_object", {"VersionId": "payload-v1", "LastModified": current}, {"Bucket": bucket, "Key": key, "VersionId": "payload-v1"})
            stubber.add_response("get_object_retention", {"Retention": {"Mode": "GOVERNANCE", "RetainUntilDate": until}}, {"Bucket": bucket, "Key": key, "VersionId": "payload-v1"})
            stubber.add_response("put_object", {"VersionId": "receipt-v1"}, {"Bucket": bucket, "Key": receipt_key,
                "Body": encoded, "ContentLength": len(encoded), "ContentType": "application/json", "IfNoneMatch": "*",
                "ChecksumAlgorithm": "SHA256", "ChecksumSHA256": base64.b64encode(hashlib.sha256(encoded).digest()).decode(),
                "ObjectLockMode": "GOVERNANCE", "ObjectLockRetainUntilDate": until})
            stubber.add_response("get_object", {"VersionId": "receipt-v1", "ContentLength": len(encoded),
                "Body": StreamingBody(io.BytesIO(encoded), len(encoded))}, {"Bucket": bucket, "Key": receipt_key})
            stubber.add_response("get_object_retention", {"Retention": {"Mode": "GOVERNANCE", "RetainUntilDate": until}}, {"Bucket": bucket, "Key": receipt_key, "VersionId": "receipt-v1"})
            with patch.object(provider, "utcnow", return_value=current), patch.object(provider, "validate_envelope"):
                self.assertTrue(provider.deliver(self.policy, self.payload, client)["durable"])
            stubber.assert_no_pending_responses()


if __name__ == "__main__":
    unittest.main()
