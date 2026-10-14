"""Opt-in versioned S3 recovery delivery, remote freshness and guarded retention.

No provider is contacted without a complete approved private policy. Capture and
watchdog ownership remain in hosted_backup.py; this module never opens ledger DBs.
"""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

import hosted_backup as capture

DEFAULT_POLICY = Path("/etc/tcsi/recovery-provider.json")
SHA256 = re.compile(r"[0-9a-f]{64}")


class ProviderError(Exception):
    """Fixed diagnostic codes; SDK/HTTP responses may contain secrets."""


def utcnow():
    return datetime.now(timezone.utc)


def timestamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ProviderError("timezone_required")
    return result.astimezone(timezone.utc)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def object_json(value, maximum=65536):
    if len(value) > maximum:
        raise ProviderError("json_too_large")
    result = json.loads(value)
    if not isinstance(result, dict):
        raise ProviderError("json_object_required")
    return result


def https_url(value):
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ProviderError("https_endpoint_required")
    return value


def load_policy(path=DEFAULT_POLICY):
    policy = object_json(capture.private_read(path))
    if policy.get("enabled") is not True:
        raise ProviderError("provider_not_enabled")
    for key in ("approval_reference", "operator", "deputy", "destination", "bucket", "prefix", "region", "credentials_file", "artifact_root"):
        if not isinstance(policy.get(key), str) or not policy[key].strip():
            raise ProviderError("incomplete_provider_policy")
    if policy.get("independent_destination_confirmed") is not True or policy.get("private_bucket_confirmed") is not True:
        raise ProviderError("destination_approval_required")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", policy["destination"]):
        raise ProviderError("invalid_destination")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", policy["bucket"]):
        raise ProviderError("invalid_bucket")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_/-]{2,120}/", policy["prefix"]) or "//" in policy["prefix"]:
        raise ProviderError("dedicated_prefix_required")
    for key in ("credentials_file", "artifact_root"):
        if not Path(policy[key]).is_absolute():
            raise ProviderError("absolute_private_paths_required")
    for key, low, high in (("maximum_success_age_seconds", 60, 604800), ("rpo_seconds", 60, 604800),
                           ("rto_seconds", 60, 604800), ("operation_timeout_seconds", 10, 3600),
                           ("maximum_artifact_bytes", 1, 5 * 1024 ** 3)):
        if type(policy.get(key)) is not int or not low <= policy[key] <= high:
            raise ProviderError("invalid_provider_bound")
    if policy["maximum_success_age_seconds"] > policy["rpo_seconds"]:
        raise ProviderError("freshness_exceeds_rpo")
    retention = policy.get("retention", {})
    if (not isinstance(retention, dict) or not isinstance(retention.get("approval_reference"), str)
            or not retention["approval_reference"].strip() or type(retention.get("days")) is not int
            or not 1 <= retention["days"] <= 36500 or type(retention.get("keep_minimum")) is not int
            or not 2 <= retention["keep_minimum"] <= 10000):
        raise ProviderError("approved_retention_required")
    if policy.get("endpoint_url"):
        parsed = urllib.parse.urlsplit(https_url(policy["endpoint_url"]))
        if parsed.path not in ("", "/") or parsed.query:
            raise ProviderError("s3_endpoint_origin_required")
    alert_policy = policy.get("alert", {})
    if (not isinstance(alert_policy, dict) or alert_policy.get("enabled") is not True
            or not alert_policy.get("recipient") or not alert_policy.get("approval_reference")
            or not Path(alert_policy.get("token_file", "")).is_absolute()):
        raise ProviderError("approved_alert_required")
    https_url(alert_policy.get("url", ""))
    if type(alert_policy.get("deduplication_seconds")) is not int or not 60 <= alert_policy["deduplication_seconds"] <= 86400:
        raise ProviderError("invalid_alert_repeat_bound")
    return policy


def s3_client(policy):
    import boto3
    from botocore.config import Config
    credentials = object_json(capture.private_read(policy["credentials_file"]))
    if not credentials.get("access_key_id") or not credentials.get("secret_access_key"):
        raise ProviderError("explicit_credentials_required")
    return boto3.client(
        "s3", region_name=policy["region"], endpoint_url=policy.get("endpoint_url"),
        aws_access_key_id=credentials["access_key_id"], aws_secret_access_key=credentials["secret_access_key"],
        aws_session_token=credentials.get("session_token"),
        config=Config(signature_version="s3v4", connect_timeout=10, read_timeout=30,
                      retries={"mode": "standard", "total_max_attempts": 3},
                      s3={"addressing_style": "path"}),
    )


def error_code(error):
    return getattr(error, "response", {}).get("Error", {}).get("Code")


def versioned(client, policy):
    if client.get_bucket_versioning(Bucket=policy["bucket"]).get("Status") != "Enabled":
        raise ProviderError("bucket_versioning_required")
    locked = client.get_object_lock_configuration(Bucket=policy["bucket"])
    if locked.get("ObjectLockConfiguration", {}).get("ObjectLockEnabled") != "Enabled":
        raise ProviderError("bucket_object_lock_required")


def run_uuid(value):
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ProviderError("invalid_run_id") from None
    return value


def keys(policy, run_id):
    run_uuid(run_id)
    return policy["prefix"] + "bundles/" + run_id + ".p7m", policy["prefix"] + "receipts/" + run_id + ".json"


def version(value):
    if not isinstance(value, str) or not value or value == "null" or len(value) > 1024:
        raise ProviderError("object_version_required")
    return value


def read_object(client, policy, key, version_id=None, maximum=65536):
    args = {"Bucket": policy["bucket"], "Key": key}
    if version_id:
        args["VersionId"] = version_id
    response = client.get_object(**args)
    body = response["Body"]
    try:
        content = body.read(maximum + 1)
        if len(content) > maximum:
            raise ProviderError("remote_object_too_large")
        return content, version(response.get("VersionId"))
    finally:
        body.close()


def verify_remote(client, policy, key, version_id, expected_hash, expected_size, output=None):
    response = client.get_object(Bucket=policy["bucket"], Key=key, VersionId=version_id)
    body = response["Body"]
    checksum, total = hashlib.sha256(), 0
    try:
        if response.get("VersionId") != version_id or response.get("ContentLength") != expected_size:
            raise ProviderError("remote_identity_mismatch")
        while chunk := body.read(1024 * 1024):
            total += len(chunk)
            if total > expected_size or total > policy["maximum_artifact_bytes"]:
                raise ProviderError("remote_size_mismatch")
            checksum.update(chunk)
            if output:
                output.write(chunk)
        if total != expected_size or checksum.hexdigest() != expected_hash:
            raise ProviderError("remote_hash_mismatch")
    finally:
        body.close()


def verify_locked(client, policy, key, version_id, retain_until):
    response = client.get_object_retention(Bucket=policy["bucket"], Key=key, VersionId=version_id)
    retention = response.get("Retention", {})
    if retention.get("Mode") != "GOVERNANCE" or retention.get("RetainUntilDate", utcnow()) < retain_until:
        raise ProviderError("object_lock_not_verified")


def validate_receipt(policy, receipt, run_id):
    payload_key, _receipt_key = keys(policy, run_id)
    if (receipt.get("format") != 1 or receipt.get("run_id") != run_id
            or receipt.get("destination") != policy["destination"] or receipt.get("key") != payload_key
            or not isinstance(receipt.get("sha256"), str) or not SHA256.fullmatch(receipt["sha256"])
            or type(receipt.get("size")) is not int or not 0 < receipt["size"] <= policy["maximum_artifact_bytes"]):
        raise ProviderError("invalid_remote_receipt")
    version(receipt.get("version_id"))
    captured_at = timestamp(receipt["captured_at"])
    if captured_at > timestamp(receipt["verified_at"]) + timedelta(seconds=60):
        raise ProviderError("capture_after_upload")
    return receipt


def get_receipt(client, policy, run_id):
    _payload_key, receipt_key = keys(policy, run_id)
    content, receipt_version = read_object(client, policy, receipt_key)
    receipt = validate_receipt(policy, object_json(content), run_id)
    return {**receipt, "receipt_key": receipt_key, "receipt_version": receipt_version}


def validate_envelope(path):
    # DER CMS ContentInfo must identify EnvelopedData, not arbitrary plaintext or
    # SignedData. OpenSSL then validates the complete ASN.1 structure without a key.
    with path.open("rb") as stream:
        if b"\x06\x09\x2a\x86\x48\x86\xf7\x0d\x01\x07\x03" not in stream.read(32):
            raise ProviderError("encrypted_cms_required")
    capture.run(["openssl", "cms", "-cmsout", "-inform", "DER", "-in", str(path), "-out", os.devnull], timeout=30)


def deliver(policy, payload, client):
    if payload.get("destination") != policy["destination"] or not SHA256.fullmatch(payload.get("sha256", "")):
        raise ProviderError("delivery_scope_mismatch")
    run_id = run_uuid(payload.get("run_id"))
    captured_at = timestamp(payload["captured_at"])
    if captured_at > utcnow() + timedelta(seconds=60):
        raise ProviderError("future_capture_time")
    path = Path(payload.get("artifact", ""))
    if (not path.is_absolute() or path.is_symlink() or not path.resolve().is_relative_to(Path(policy["artifact_root"]).resolve())
            or path.suffix != ".p7m"):
        raise ProviderError("artifact_outside_private_staging")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077
                or not 0 < info.st_size <= policy["maximum_artifact_bytes"]):
            raise ProviderError("unsafe_artifact")
        checksum = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
        if checksum.hexdigest() != payload["sha256"]:
            raise ProviderError("local_hash_mismatch")
        validate_envelope(path)
        versioned(client, policy)
        key, receipt_key = keys(policy, run_id)
        # Protect a full policy horizon from the provider's creation timestamp,
        # including the bounded upload time (never shorten an existing horizon).
        retain_until = (utcnow() + timedelta(days=policy["retention"]["days"],
                         seconds=policy["operation_timeout_seconds"])).replace(microsecond=0) + timedelta(seconds=1)
        stream.seek(0)
        existing_payload = False
        try:
            response = client.put_object(Bucket=policy["bucket"], Key=key, Body=stream,
                                         ContentLength=info.st_size, ContentType="application/pkcs7-mime",
                                         ChecksumAlgorithm="SHA256", ChecksumSHA256=base64.b64encode(checksum.digest()).decode(), IfNoneMatch="*",
                                         ObjectLockMode="GOVERNANCE", ObjectLockRetainUntilDate=retain_until,
                                         Metadata={"sha256": payload["sha256"], "run-id": run_id})
            version_id = version(response.get("VersionId"))
        except Exception as error:
            if error_code(error) not in ("PreconditionFailed", "412"):
                raise
            existing_payload = True
            version_id = version(client.head_object(Bucket=policy["bucket"], Key=key).get("VersionId"))
        verify_remote(client, policy, key, version_id, payload["sha256"], info.st_size)
        stored = client.head_object(Bucket=policy["bucket"], Key=key, VersionId=version_id)
        created_at = stored.get("LastModified")
        if not isinstance(created_at, datetime) or created_at.tzinfo is None:
            raise ProviderError("provider_creation_time_required")
        if existing_payload:
            retention = client.get_object_retention(Bucket=policy["bucket"], Key=key, VersionId=version_id).get("Retention", {})
            retain_until = retention.get("RetainUntilDate")
            if not isinstance(retain_until, datetime) or retain_until <= utcnow():
                raise ProviderError("existing_object_lock_expired")
        minimum_until = created_at + timedelta(days=policy["retention"]["days"], seconds=-1)
        if retain_until < minimum_until:
            raise ProviderError("object_lock_horizon_too_short")
        verify_locked(client, policy, key, version_id, retain_until)
    receipt = {"format": 1, "run_id": run_id, "destination": policy["destination"], "key": key,
               "version_id": version_id, "sha256": payload["sha256"], "size": info.st_size,
               "captured_at": captured_at.isoformat(), "verified_at": created_at.isoformat(),
               "readback_verified_at": utcnow().isoformat()}
    receipt["retain_until"] = retain_until.isoformat()
    encoded = canonical(receipt)
    try:
        response = client.put_object(Bucket=policy["bucket"], Key=receipt_key, Body=encoded,
                                     ContentLength=len(encoded), ContentType="application/json", IfNoneMatch="*",
                                     ChecksumAlgorithm="SHA256", ChecksumSHA256=base64.b64encode(hashlib.sha256(encoded).digest()).decode(),
                                     ObjectLockMode="GOVERNANCE", ObjectLockRetainUntilDate=retain_until)
        version(response.get("VersionId"))
    except Exception as error:
        if error_code(error) not in ("PreconditionFailed", "412"):
            raise
    existing = get_receipt(client, policy, run_id)
    verify_locked(client, policy, receipt_key, existing["receipt_version"], retain_until)
    for field in ("key", "version_id", "sha256", "size", "retain_until", "captured_at"):
        if existing[field] != receipt[field]:
            raise ProviderError("receipt_conflict")
    return {"durable": True, "sha256": payload["sha256"], "destination": policy["destination"], "receipt_id": run_id}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise ProviderError("alert_redirect_rejected")


def send_alert(policy, event, opener=None):
    alert = policy["alert"]
    token = capture.private_read(alert["token_file"]).decode().strip()
    if not token or "\n" in token or "\r" in token:
        raise ProviderError("invalid_alert_token")
    status = event.get("status")
    if status not in ("failed", "missed"):
        raise ProviderError("invalid_alert_status")
    run_id = event.get("run_id")
    if run_id is not None:
        run_uuid(run_id)
    payload = {"event": "backup_attention", "status": status, "run_id": run_id,
               "destination": policy["destination"], "recipient": alert["recipient"], "at": utcnow().isoformat()}
    stable = {key: value for key, value in payload.items() if key != "at"}
    stable["repeat_window"] = int(utcnow().timestamp()) // alert["deduplication_seconds"]
    event_id = hashlib.sha256(canonical(stable)).hexdigest()
    request = urllib.request.Request(https_url(alert["url"]), data=canonical({**payload, "event_id": event_id}), method="POST",
                                     headers={"Authorization": "Bearer " + token, "Content-Type": "application/json",
                                              "Idempotency-Key": event_id})
    opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=15) as response:
        body = object_json(response.read(65537))
        if response.status not in (200, 201, 202) or body.get("accepted") is not True or body.get("event_id") != event_id:
            raise ProviderError("alert_not_acknowledged")
    return {"accepted": True}


def catalog(client, policy):
    prefix = policy["prefix"] + "receipts/"
    token, entries = None, []
    while True:
        args = {"Bucket": policy["bucket"], "Prefix": prefix, "MaxKeys": 1000}
        if token:
            args["ContinuationToken"] = token
        response = client.list_objects_v2(**args)
        for item in response.get("Contents", []):
            name = item["Key"]
            if not name.startswith(prefix) or not name.endswith(".json"):
                raise ProviderError("unexpected_receipt_object")
            run_id = run_uuid(name[len(prefix):-5])
            entries.append(get_receipt(client, policy, run_id))
            if len(entries) > 10000:
                raise ProviderError("receipt_inventory_limit")
        if not response.get("IsTruncated"):
            break
        following = response.get("NextContinuationToken")
        if not following or following == token:
            raise ProviderError("invalid_inventory_pagination")
        token = following
    return sorted(entries, key=lambda entry: (timestamp(entry["captured_at"]), entry["run_id"]), reverse=True)


def healthy_latest(client, policy, entries, current):
    if not entries:
        raise ProviderError("no_remote_recovery_receipt")
    latest = entries[0]
    age = (current - timestamp(latest["captured_at"])).total_seconds()
    if age < -60 or age > policy["maximum_success_age_seconds"]:
        raise ProviderError("remote_recovery_overdue")
    head = client.head_object(Bucket=policy["bucket"], Key=latest["key"], VersionId=latest["version_id"])
    if head.get("VersionId") != latest["version_id"] or head.get("ContentLength") != latest["size"] or head.get("Metadata", {}).get("sha256") != latest["sha256"]:
        raise ProviderError("latest_remote_recovery_missing")
    minimum = timestamp(latest["verified_at"]) + timedelta(days=policy["retention"]["days"], seconds=-1)
    verify_locked(client, policy, latest["key"], latest["version_id"], minimum)
    verify_locked(client, policy, latest["receipt_key"], latest["receipt_version"], minimum)
    return latest


def monitor(policy, client, notify=send_alert):
    try:
        versioned(client, policy)
        latest = healthy_latest(client, policy, catalog(client, policy), utcnow())
    except Exception:
        notify(policy, {"status": "missed", "run_id": None})
        raise ProviderError("remote_recovery_attention_required") from None
    return {"status": "fresh", "run_id": latest["run_id"], "captured_at": latest["captured_at"], "verified_at": latest["verified_at"]}


def policy_binding(policy):
    return hashlib.sha256(canonical({key: policy.get(key) for key in (
        "approval_reference", "destination", "bucket", "prefix", "endpoint_url", "region", "retention")})).hexdigest()


def retention_plan(policy, client, current=None):
    current = current or utcnow()
    versioned(client, policy)
    entries = catalog(client, policy)
    healthy_latest(client, policy, entries, current)
    cutoff = current - timedelta(days=policy["retention"]["days"])
    selected = [entry for entry in entries[policy["retention"]["keep_minimum"]:] if timestamp(entry["verified_at"]) < cutoff]
    return {"format": 1, "created_at": current.isoformat(), "policy_sha256": policy_binding(policy), "delete": selected}


def missing(error):
    return error_code(error) in ("NoSuchKey", "NoSuchVersion", "404", "NotFound")


def retention_apply(policy, client, plan, expected_sha256, record_progress=None):
    if policy["retention"].get("apply_enabled") is not True:
        raise ProviderError("retention_apply_not_enabled")
    if not SHA256.fullmatch(expected_sha256) or hashlib.sha256(canonical(plan)).hexdigest() != expected_sha256:
        raise ProviderError("retention_plan_approval_mismatch")
    age = (utcnow() - timestamp(plan["created_at"])).total_seconds()
    if plan.get("format") != 1 or plan.get("policy_sha256") != policy_binding(policy) or not 0 <= age <= 3600:
        raise ProviderError("retention_plan_stale")
    allowed = {entry["run_id"]: entry for entry in retention_plan(policy, client)["delete"]}
    seen, removed = set(), []
    record_progress = record_progress or (lambda _value: None)
    # Check the entire plan before its first irreversible operation.
    for entry in plan["delete"]:
        validate_receipt(policy, entry, entry["run_id"])
        if entry["run_id"] in seen or entry.get("receipt_key") != keys(policy, entry["run_id"])[1]:
            raise ProviderError("invalid_retention_plan")
        seen.add(entry["run_id"])
        version(entry.get("receipt_version"))
        if allowed.get(entry["run_id"]) != entry:
            raise ProviderError("retention_inventory_changed")
    for entry in plan["delete"]:
        # Explicit versions prevent deleting a later replacement. Object-lock or
        # legal-hold refusal remains an error; no bypass header is ever sent.
        for key, version_id in ((entry["key"], entry["version_id"]), (entry["receipt_key"], entry["receipt_version"])):
            hold = client.get_object_legal_hold(Bucket=policy["bucket"], Key=key, VersionId=version_id)
            retention = client.get_object_retention(Bucket=policy["bucket"], Key=key, VersionId=version_id).get("Retention", {})
            if hold.get("LegalHold", {}).get("Status") != "OFF" or retention.get("RetainUntilDate", utcnow() + timedelta(days=1)) > utcnow():
                raise ProviderError("object_retention_protects_version")
            record_progress({"status": "pending_delete", "plan_sha256": expected_sha256,
                             "key": key, "version_id": version_id, "completed_run_ids": removed[:]})
            client.delete_object(Bucket=policy["bucket"], Key=key, VersionId=version_id)
            try:
                client.head_object(Bucket=policy["bucket"], Key=key, VersionId=version_id)
            except Exception as error:
                if not missing(error):
                    raise
            else:
                raise ProviderError("retention_delete_not_verified")
        removed.append(entry["run_id"])
        record_progress({"status": "run_deleted", "plan_sha256": expected_sha256, "completed_run_ids": removed[:]})
    record_progress({"status": "complete", "plan_sha256": expected_sha256, "completed_run_ids": removed[:]})
    return {"status": "retention_applied", "deleted_run_ids": removed}


def main(default_action=None):
    parser = argparse.ArgumentParser(description=__doc__)
    if default_action is None:
        parser.add_argument("action", choices=("deliver", "alert", "monitor", "retention-plan", "retention-apply"))
    parser.add_argument("--config", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--approve-plan-sha256")
    parser.add_argument("--status", choices=("failed", "missed"))
    args = parser.parse_args()
    action = default_action or args.action
    os.umask(0o077)
    try:
        policy = load_policy(args.config)
        def deadline(_signum, _frame):
            raise ProviderError("provider_deadline")
        signal.signal(signal.SIGALRM, deadline)
        signal.alarm(policy["operation_timeout_seconds"])
        if action == "alert":
            result = send_alert(policy, {"status": args.status, "run_id": None} if args.status else object_json(sys.stdin.buffer.read(65537)))
        else:
            client = s3_client(policy)
            if action == "deliver":
                result = deliver(policy, object_json(sys.stdin.buffer.read(65537)), client)
            elif action == "monitor":
                result = monitor(policy, client)
            elif action == "retention-plan":
                if not args.plan or args.plan.exists():
                    raise ProviderError("new_private_plan_path_required")
                capture.private_directory(args.plan.parent)
                result = retention_plan(policy, client)
                capture.atomic_json(args.plan, result)
                result = {"planned_deletions": len(result["delete"]), "plan_sha256": hashlib.sha256(canonical(result)).hexdigest()}
            else:
                if not args.plan or not args.approve_plan_sha256:
                    raise ProviderError("explicit_retention_plan_required")
                journal = args.plan.with_name(args.plan.name + ".journal.json")
                if journal.exists() or journal.is_symlink():
                    raise ProviderError("inspect_existing_retention_journal")
                capture.private_directory(journal.parent)
                # Record intent before any delete. Failed/unknown outcomes retain
                # the exact object version for inspection before a new plan.
                with journal.open("x") as stream:
                    json.dump({"status": "starting", "plan_sha256": args.approve_plan_sha256}, stream)
                result = retention_apply(policy, client, object_json(capture.private_read(args.plan), 16 * 1024 * 1024),
                                         args.approve_plan_sha256, lambda value: capture.atomic_json(journal, value))
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        print(json.dumps({"status": "failed", "error": str(error) if isinstance(error, (ProviderError, capture.BackupError)) else "provider_operation_failed"}))
        return 1
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    sys.exit(main())
