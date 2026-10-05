"""Off-host retrieval, decryption and safe manifest verification for restore drills.

Produces a private payload for the documented isolated database restore procedure.
It does not restore a database, approve ledger equality or certify the agreed RTO.
"""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import signal
import sys
import tarfile
import time

import hosted_backup as capture
import hosted_recovery_provider as provider


def extract_regular(archive_path, directory, maximum_bytes, maximum_files=100000):
    directory.mkdir(mode=0o700)
    seen, total = set(), 0
    with tarfile.open(archive_path, "r:") as archive:
        for member in archive:
            name = PurePosixPath(member.name)
            if (not member.isfile() or name.is_absolute() or not name.parts or ".." in name.parts
                    or "\\" in member.name or str(name) != member.name or member.name in seen):
                raise provider.ProviderError("unsafe_recovery_archive")
            seen.add(member.name)
            total += member.size
            if len(seen) > maximum_files or member.size < 0 or total > maximum_bytes:
                raise provider.ProviderError("recovery_archive_limit")
            path = directory.joinpath(*name.parts)
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise provider.ProviderError("recovery_archive_member_missing")
            with source, path.open("xb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
            path.chmod(0o600)
    return len(seen)


def prepare(policy, client, run_id, output, private_key, certificate, *, confirm_offhost=False, passphrase_file=None):
    if (not confirm_offhost or any(os.environ.get(key) for key in ("RAILWAY_PROJECT_ID", "RAILWAY_SERVICE_ID"))
            or Path("/opt/tcsi/cloud_start.py").exists()):
        raise provider.ProviderError("separate_recovery_host_required")
    output = Path(output)
    if not output.is_absolute() or output.exists() or output.is_symlink():
        raise provider.ProviderError("new_private_output_required")
    capture.private_directory(output.parent)
    key_bytes = capture.private_read(private_key)
    if b"PRIVATE KEY" not in key_bytes:
        raise provider.ProviderError("private_key_required")
    del key_bytes
    capture.validate_certificate(certificate)
    if passphrase_file:
        capture.private_read(passphrase_file)
    provider.versioned(client, policy)
    receipt = provider.get_receipt(client, policy, provider.run_uuid(run_id))
    started = time.monotonic()
    output.mkdir(mode=0o700)
    try:
        encrypted = output / "recovery.p7m"
        with encrypted.open("xb") as stream:
            provider.verify_remote(client, policy, receipt["key"], receipt["version_id"], receipt["sha256"], receipt["size"], stream)
        encrypted.chmod(0o600)
        archive = output / "decrypted.tar"
        command = ["openssl", "cms", "-decrypt", "-binary", "-inform", "DER", "-in", str(encrypted),
                   "-recip", str(certificate), "-inkey", str(private_key), "-out", str(archive)]
        if passphrase_file:
            command.extend(["-passin", "file:" + str(passphrase_file)])
        capture.run(command, timeout=300)
        payload = output / "payload"
        extract_regular(archive, payload, policy["maximum_artifact_bytes"] * 10)
        files = capture.verify(payload)
        manifest = json.loads((payload / "manifest.json").read_text())
        if manifest.get("metadata", {}).get("captured_at") != receipt["captured_at"]:
            raise provider.ProviderError("capture_receipt_manifest_mismatch")
        archive.unlink()
        report = {"status": "DECRYPTED_MANIFEST_VERIFIED", "run_id": run_id, "artifact_sha256": receipt["sha256"],
                  "artifact_version": receipt["version_id"], "manifest_sha256": capture.digest(payload / "manifest.json"),
                  "verified_files": files, "prepared_at": provider.utcnow().isoformat(),
                  "preparation_seconds": round(time.monotonic() - started, 3),
                  "database_restore_verified": False, "ledger_conservation_verified": False,
                  "rto_met": None, "operator_handover_verified": False}
        capture.atomic_json(output / "drill-preparation.json", report)
        capture.atomic_json(output / "remote-receipt.json", receipt)
        return report
    except BaseException:
        # The directory was created exclusively by this invocation. Never delete
        # a supplied pre-existing recovery directory or suppress the original error.
        shutil.rmtree(output)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=provider.DEFAULT_POLICY)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--public-certificate", type=Path, required=True)
    parser.add_argument("--passphrase-file", type=Path)
    parser.add_argument("--confirm-offhost-recovery", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        policy = provider.load_policy(args.config)
        def deadline(_number, _frame):
            raise provider.ProviderError("recovery_drill_deadline")
        signal.signal(signal.SIGTERM, deadline)
        signal.signal(signal.SIGALRM, deadline)
        signal.alarm(policy["operation_timeout_seconds"])
        report = prepare(policy, provider.s3_client(policy), args.run_id, args.output, args.private_key,
                         args.public_certificate, confirm_offhost=args.confirm_offhost_recovery, passphrase_file=args.passphrase_file)
        print(json.dumps(report, sort_keys=True))
        return 0
    except Exception as error:
        print(json.dumps({"status": "failed", "error": str(error) if isinstance(error, (provider.ProviderError, capture.BackupError)) else "recovery_drill_failed"}))
        return 1
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    sys.exit(main())
