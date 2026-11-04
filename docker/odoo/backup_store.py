#!/usr/bin/python3
"""Private S3 delivery and asynchronous attention queue; never log provider errors."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
import uuid

import hosted_backup as backup


def configuration(environment):
    names = ("ENDPOINT", "REGION", "BUCKET", "ACCESS_KEY_ID", "SECRET_ACCESS_KEY")
    config = {name.lower(): environment.get("TCSI_BACKUP_S3_" + name, "") for name in names}
    config.update(prefix=environment.get("TCSI_BACKUP_PREFIX", ""),
                  monitor_id=environment.get("TCSI_BACKUP_MONITOR_ID", ""))
    if any(not isinstance(value, str) or not value.strip() or any(c in value for c in "\r\n")
           for value in config.values()):
        raise backup.BackupError("incomplete_backup_configuration")
    endpoint = urlsplit(config["endpoint"])
    if endpoint.scheme != "https" or not endpoint.hostname or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment or endpoint.path not in ("", "/"):
        raise backup.BackupError("invalid_backup_endpoint")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", config["prefix"]):
        raise backup.BackupError("invalid_backup_prefix")
    return config


def client(config):
    # Isolate the pinned SDK from Odoo's Python dependencies.
    sys.path.insert(0, "/opt/tcsi-backup-deps")
    import boto3
    from botocore.config import Config
    return boto3.client("s3", endpoint_url=config["endpoint"], region_name=config["region"],
                        aws_access_key_id=config["access_key_id"],
                        aws_secret_access_key=config["secret_access_key"],
                        config=Config(signature_version="s3v4", connect_timeout=10, read_timeout=30,
                                      retries={"total_max_attempts": 3, "mode": "standard"},
                                      request_checksum_calculation="when_required",
                                      response_checksum_validation="when_required",
                                      s3={"addressing_style": "virtual"}))


class Store:
    def __init__(self, config, s3=None):
        self.config = config
        self.s3 = s3 if s3 is not None else client(config)
        self.bucket = config["bucket"]
        self.prefix = config["prefix"] + "/"

    def read(self, key):
        response = self.s3.get_object(Bucket=self.bucket, Key=key)
        with response["Body"] as stream:
            content = stream.read(65537)
        if len(content) > 65536:
            raise backup.BackupError("invalid_remote_receipt")
        return json.loads(content)

    def write(self, key, value):
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=json.dumps(value, sort_keys=True).encode(),
                           ContentType="application/json")
        if self.read(key) != value:
            raise backup.BackupError("remote_receipt_mismatch")

    def object_key(self, run_id):
        if str(uuid.UUID(run_id)) != run_id:
            raise backup.BackupError("invalid_run_id")
        return self.prefix + "objects/" + run_id + ".p7m"

    def validate_receipt(self, receipt):
        if receipt["object"] != self.object_key(receipt["run_id"]) or receipt["format"] != 1 or receipt["status"] != "success":
            raise backup.BackupError("invalid_remote_receipt")
        if not re.fullmatch(r"[0-9a-f]{64}", receipt["sha256"]) or type(receipt["size"]) is not int or receipt["size"] <= 0:
            raise backup.BackupError("invalid_remote_receipt")
        captured = datetime.fromisoformat(receipt["at"])
        if captured.tzinfo is None:
            raise backup.BackupError("invalid_remote_receipt")
        return captured

    def verify_object(self, receipt, full=False):
        self.validate_receipt(receipt)
        head = self.s3.head_object(Bucket=self.bucket, Key=receipt["object"])
        if head["ContentLength"] != receipt["size"] or head.get("Metadata", {}).get("sha256") != receipt["sha256"]:
            raise backup.BackupError("remote_object_mismatch")
        if full:
            response = self.s3.get_object(Bucket=self.bucket, Key=receipt["object"])
            checksum = hashlib.sha256()
            with response["Body"] as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    checksum.update(chunk)
            if checksum.hexdigest() != receipt["sha256"]:
                raise backup.BackupError("remote_object_mismatch")

    def deliver(self, payload):
        if payload["destination"] != self.config["prefix"]:
            raise backup.BackupError("wrong_destination")
        artifact = Path(payload["artifact"])
        if artifact.is_symlink() or backup.digest(artifact) != payload["sha256"]:
            raise backup.BackupError("invalid_artifact")
        key = self.object_key(payload["run_id"])
        receipt = {"format": 1, "status": "success", "run_id": payload["run_id"],
                   "object": key, "sha256": payload["sha256"], "size": artifact.stat().st_size,
                   "at": backup.now()}
        with artifact.open("rb") as stream:
            self.s3.upload_fileobj(stream, self.bucket, key, ExtraArgs={
                "ContentType": "application/pkcs7-mime", "Metadata": {"sha256": payload["sha256"]}})
        self.verify_object(receipt, full=True)
        receipt_key = self.prefix + "receipts/" + payload["run_id"] + ".json"
        self.write(receipt_key, receipt)
        self.write(self.prefix + "status.json", receipt)
        # Retention only after this complete, independently downloaded backup is durable.
        self.retain(receipt)
        return {"durable": True, "sha256": payload["sha256"], "destination": payload["destination"],
                "receipt_id": receipt_key}

    def attention(self, payload):
        if payload.get("event") != "backup_attention" or payload.get("status") not in ("failed", "missed"):
            raise backup.BackupError("invalid_attention_event")
        event = {"format": 1, "status": payload["status"], "run_id": payload.get("run_id"),
                 "at": payload["at"], "monitor_id": self.config["monitor_id"]}
        self.write(self.prefix + "status.json", event)
        # Acknowledges durable queue acceptance, not notification delivery.
        return {"accepted": True, "channel": "durable_attention_queue"}

    def monitor(self, now=None):
        now = now or datetime.now(timezone.utc)
        status = self.read(self.prefix + "status.json")
        captured = self.validate_receipt(status)
        if not 0 <= (now - captured).total_seconds() <= 27 * 3600:
            raise backup.BackupError("backup_stale")
        receipt = self.read(self.prefix + "receipts/" + status["run_id"] + ".json")
        if receipt != status:
            raise backup.BackupError("remote_receipt_mismatch")
        self.verify_object(receipt)
        return {"status": "success"}

    def retain(self, current):
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        prefix = self.prefix + "receipts/"
        for page in self.s3.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                key = item["Key"]
                if not re.fullmatch(re.escape(prefix) + r"[0-9a-f-]{36}\.json", key):
                    continue
                receipt = self.read(key)
                captured = self.validate_receipt(receipt)
                if key != prefix + receipt["run_id"] + ".json" or receipt["run_id"] == current["run_id"] or captured >= cutoff:
                    continue
                try:
                    self.verify_object(receipt)
                except Exception as error:
                    # Resume a prior interrupted prune only for an explicit S3 missing object.
                    if getattr(error, "response", {}).get("Error", {}).get("Code") not in ("404", "NoSuchKey", "NotFound"):
                        raise
                self.s3.delete_object(Bucket=self.bucket, Key=receipt["object"])
                self.s3.delete_object(Bucket=self.bucket, Key=key)


def adapter_main():
    try:
        config = json.loads(backup.private_read("/var/lib/odoo/recovery-state/adapter.json"))
        store = Store(config)
        payload = json.load(sys.stdin)
        result = store.deliver(payload) if Path(sys.argv[0]).name == "backup-delivery" else store.attention(payload)
        print(json.dumps(result))
        return 0
    except Exception:
        print('{"error":"backup_adapter_failed"}')
        return 1


if __name__ == "__main__":
    sys.exit(adapter_main())
