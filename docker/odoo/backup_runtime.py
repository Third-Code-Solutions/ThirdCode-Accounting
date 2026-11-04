"""Opt-in daily paired recovery capture and independent bucket monitor."""
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

import hosted_backup as backup
from backup_store import Store, configuration

STATE = Path("/var/lib/odoo/recovery-state")


def required(environment, name):
    value = environment.get(name, "")
    if not value.strip() or any(c in value for c in "\r\n"):
        raise backup.BackupError("incomplete_backup_configuration")
    return value


def prepare(environment):
    """Validate before enabling; private recovery configuration never enters argv/logs."""
    if environment.get("TCSI_BACKUP_ENABLED") != "1":
        return None
    config = configuration(environment)
    revision = required(environment, "TCSI_RELEASE_SHA")
    image = required(environment, "TCSI_RELEASE_IMAGE")
    if not re.fullmatch(r"[0-9a-f]{40}", revision) or not re.fullmatch(r"[^\s]+@sha256:[0-9a-f]{64}", image):
        raise backup.BackupError("invalid_release_provenance")
    if environment.get("RAILWAY_GIT_COMMIT_SHA", revision) != revision:
        raise backup.BackupError("runtime_revision_mismatch")
    certificate = environment.get("TCSI_BACKUP_PUBLIC_CERTIFICATE", "")
    if not certificate.startswith("-----BEGIN CERTIFICATE-----") or "PRIVATE KEY" in certificate:
        raise backup.BackupError("invalid_public_certificate")
    operator = required(environment, "TCSI_BACKUP_OPERATOR")
    contact = required(environment, "TCSI_BACKUP_RESTORE_CONTACT")
    state = backup.private_directory(STATE)
    certificate_path = state / "recovery-public.pem"
    descriptor = os.open(certificate_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(certificate)
    backup.validate_certificate(certificate_path)
    backup.atomic_json(state / "adapter.json", config)
    policy = {"enabled": True, "writer_topology": "single_supervised_odoo",
              "database": required(environment, "PGDATABASE"), "data_dir": "/var/lib/odoo",
              "state_dir": str(state), "public_certificate": str(certificate_path),
              "destination": config["prefix"], "delivery_command": "/opt/tcsi/backup-delivery",
              "alert_command": "/opt/tcsi/backup-attention", "operator": operator, "deputy": contact,
              "retention_policy": "30 days; verified objects in dedicated prefix only",
              "schedule": "daily 03:00", "timezone": "Asia/Singapore", "rpo": "24 hours",
              "rto": "operator-led restore; rehearse and measure", "source_revision": revision,
              "image_reference": image, "max_pause_seconds": 120, "adapter_timeout_seconds": 900,
              "maximum_success_age_seconds": 27 * 3600}
    path = state / "policy.json"
    backup.atomic_json(path, policy)
    backup.load_policy(path)
    # Explicit release provenance supplies the existing capture guard on CLI deployments.
    environment["RAILWAY_GIT_COMMIT_SHA"] = revision
    return [sys.executable, "/opt/tcsi/backup_runtime.py", "schedule"]


def next_capture(now):
    local = now.astimezone(ZoneInfo("Asia/Singapore"))
    candidate = local.replace(hour=3, minute=0, second=0, microsecond=0)
    if candidate <= local:
        candidate += timedelta(days=1)
    return candidate.astimezone(timezone.utc)


def schedule():
    # No startup capture. The explicit capture command establishes initial evidence.
    due = next_capture(datetime.now(timezone.utc))
    while True:
        remaining = (due - datetime.now(timezone.utc)).total_seconds()
        if remaining > 0:
            time.sleep(min(remaining, 60))
            continue
        capture_with_retries()
        due = next_capture(datetime.now(timezone.utc))


def capture_with_retries():
    # Child is synchronous; existing flock also rejects overlapping manual runs.
    for attempt in range(3):
        result = subprocess.run([sys.executable, "/opt/tcsi/hosted_backup.py", "capture",
                                 "--config", str(STATE / "policy.json")], check=False)
        if result.returncode == 0:
            return
        print("Paired backup failed; independent monitor requires attention", flush=True)
        if attempt < 2:
            time.sleep(15 * 60)


def main():
    os.umask(0o077)
    try:
        action = sys.argv[1]
        if action == "monitor":
            Store(configuration(os.environ)).monitor()
            print('{"status":"success"}')
        elif action == "capture":
            backup.capture(backup.load_policy(STATE / "policy.json"))
            print('{"status":"success"}')
        elif action == "schedule":
            schedule()
        else:
            raise backup.BackupError("invalid_action")
    except Exception:
        print('{"status":"failed","error":"backup_attention_required"}', flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
