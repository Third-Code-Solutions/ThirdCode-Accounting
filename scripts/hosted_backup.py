"""Fail-closed coordinated recovery capture for the single-writer hosted runtime.

This is an operator command, not an enabled scheduler. See RECOVERY-AUTOMATION.md.
No subprocess output or exception text containing recovery material is logged.
"""
import argparse
from contextlib import contextmanager
import configparser
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import select
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid


class BackupError(Exception):
    """Public error code only; never embed secrets or subprocess output."""


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def private_directory(path):
    path = Path(path)
    if not path.is_absolute() or path.is_symlink():
        raise BackupError("unsafe_directory")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.stat()
    if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise BackupError("unsafe_directory")
    return path


def private_read(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise BackupError("unsafe_private_file")
        return stream.read()


def atomic_json(path, value):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(json.dumps(value, sort_keys=True).encode())
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(temporary, path)
            directory = os.open(path.parent, os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)


def load_policy(path):
    policy = json.loads(private_read(path))
    required = ("database", "data_dir", "state_dir", "public_certificate", "destination",
                "delivery_command", "alert_command", "operator", "deputy", "retention_policy",
                "schedule", "timezone", "rpo", "rto", "source_revision", "image_reference")
    if policy.get("enabled") is not True or policy.get("writer_topology") != "single_supervised_odoo":
        raise BackupError("policy_not_enabled")
    if any(not isinstance(policy.get(key), str) or not policy[key].strip() for key in required):
        raise BackupError("incomplete_policy")
    if not re.fullmatch(r"[A-Za-z0-9_]+", policy["database"]):
        raise BackupError("invalid_database")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", policy["destination"]):
        raise BackupError("invalid_destination_alias")
    if not re.fullmatch(r"[0-9a-f]{40}", policy["source_revision"]):
        raise BackupError("invalid_revision")
    if not re.fullmatch(r"[^\s]+@sha256:[0-9a-f]{64}", policy["image_reference"]):
        raise BackupError("immutable_image_required")
    for key, low, high in (("max_pause_seconds", 5, 300), ("adapter_timeout_seconds", 1, 3600),
                           ("maximum_success_age_seconds", 60, 604800)):
        if type(policy.get(key)) is not int or not low <= policy[key] <= high:
            raise BackupError("invalid_time_bound")
    for key in ("data_dir", "state_dir", "public_certificate", "delivery_command", "alert_command"):
        if not Path(policy[key]).is_absolute():
            raise BackupError("absolute_paths_required")
    for key in ("delivery_command", "alert_command"):
        path = Path(policy[key])
        info = path.stat()
        if path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022 or not os.access(path, os.X_OK):
            raise BackupError("unsafe_adapter")
    return policy


def run(command, *, timeout, environment=None, input_data=None):
    """Bound child lifetime; never let raw stderr or CalledProcessError escape."""
    try:
        child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, env=environment, start_new_session=True)
    except OSError:
        raise BackupError("command_failed") from None
    try:
        output, _error = child.communicate(input=input_data, timeout=timeout)
        if child.returncode:
            raise BackupError("command_failed")
        return output
    except BaseException:
        # A wrapper may spawn the actual upload or dump. Own their session and
        # terminate its whole group, including when the operator is interrupted.
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            child.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            # A prohibited detached adapter must not hold our output pipes open.
            for pipe in (child.stdin, child.stdout, child.stderr):
                if pipe and not pipe.closed:
                    pipe.close()
        child.wait(timeout=5)
        raise BackupError("command_failed") from None


def process(pid):
    try:
        text = Path(f"/proc/{pid}/stat").read_text()
        fields = text[text.rfind(")") + 2:].split()
        return {"pid": pid, "state": fields[0], "parent": int(fields[1]),
                "group": int(fields[2]), "start": fields[19]}
    except (OSError, ValueError, IndexError):
        return None


def members(group):
    return [record for entry in Path("/proc").iterdir() if entry.name.isdigit()
            if (record := process(int(entry.name))) and record["group"] == group]


def identity_matches(record):
    current = process(record["pid"])
    return current and current["start"] == record["start"] and current["group"] == record["group"]


def resume(handles):
    # Linux pidfds bind identity, so PID/group reuse cannot signal a new service.
    for handle in handles.values():
        try:
            signal.pidfd_send_signal(handle, signal.SIGCONT)
        except ProcessLookupError:
            pass


def watchdog(handles, pipe, seconds):
    os.setsid()
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        # Parent death closes pipe; timeout is independent of a stalled parent.
        ready, _, _ = select.select([pipe], [], [], seconds)
        resume(handles)
        # The parent may have stalled between its deadline check and SIGSTOP.
        # Keep undoing any late stop until that parent exits or closes the pipe.
        while not ready:
            ready, _, _ = select.select([pipe], [], [], 0.05)
            resume(handles)
    finally:
        os.close(pipe)


@contextmanager
def paused(master, seconds):
    if not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
        raise BackupError("linux_pidfd_required")
    records = members(master["group"])
    if not identity_matches(master) or master["group"] != master["pid"] or master["group"] == os.getpgrp():
        raise BackupError("runtime_identity_changed")
    known = {record["pid"] for record in records}
    if any(record["pid"] != master["pid"] and record["parent"] not in known for record in records):
        raise BackupError("foreign_process_in_group")
    handles = {}
    try:
        for record in records:
            handles[record["pid"]] = os.pidfd_open(record["pid"])
            if not identity_matches(record):
                raise BackupError("runtime_identity_changed")
    except BaseException:
        for handle in handles.values():
            os.close(handle)
        raise
    read_end, write_end = os.pipe()
    try:
        child = os.fork()
    except BaseException:
        os.close(read_end)
        os.close(write_end)
        for handle in handles.values():
            os.close(handle)
        raise
    if not child:
        os.close(write_end)
        try:
            watchdog(handles, read_end, seconds)
        finally:
            os._exit(0)
    os.close(read_end)
    deadline = time.monotonic() + seconds
    try:
        if not identity_matches(master):
            raise BackupError("runtime_identity_changed")
        # Stop the master first, then every known descendant. An unexpected fork
        # changes membership and aborts capture; no unknown process is signalled.
        if time.monotonic() >= deadline:
            raise BackupError("pause_timeout")
        signal.pidfd_send_signal(handles[master["pid"]], signal.SIGSTOP)
        for pid, handle in handles.items():
            if pid != master["pid"]:
                if time.monotonic() >= deadline:
                    raise BackupError("pause_timeout")
                signal.pidfd_send_signal(handle, signal.SIGSTOP)
        while True:
            current = members(master["group"])
            if {record["pid"] for record in current} != known:
                raise BackupError("runtime_membership_changed")
            if all(record["state"] in ("T", "t") for record in current):
                break
            if time.monotonic() >= deadline:
                raise BackupError("pause_timeout")
            time.sleep(0.01)
        if time.monotonic() >= deadline:
            raise BackupError("pause_timeout")
        yield deadline
        if time.monotonic() >= deadline or not identity_matches(master):
            raise BackupError("pause_timeout")
    finally:
        try:
            resume(handles)
        finally:
            os.close(write_end)
            os.waitpid(child, 0)
            for handle in handles.values():
                os.close(handle)


def discover(policy):
    candidates = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        record = process(int(entry.name))
        if not record or record["group"] != record["pid"]:
            continue
        try:
            args = (entry / "cmdline").read_bytes().decode().rstrip("\0").split("\0")
            parent_args = Path(f"/proc/{record['parent']}/cmdline").read_bytes().split(b"\0")
            if b"/opt/tcsi/cloud_start.py" not in parent_args or "-c" not in args:
                continue
            if not any(Path(arg).name == "odoo" for arg in args[:2]):
                continue
            config_path = Path(args[args.index("-c") + 1])
            config_bytes = private_read(config_path)
            config = configparser.ConfigParser(interpolation=None)
            config.read_string(config_bytes.decode())
            options = dict(config["options"])
            if options.get("db_name") != policy["database"] or Path(options["data_dir"]).resolve() != Path(policy["data_dir"]).resolve():
                continue
            environment = dict(value.split(b"=", 1) for value in (entry / "environ").read_bytes().split(b"\0") if b"=" in value)
            if environment.get(b"RAILWAY_GIT_COMMIT_SHA", b"").decode() != policy["source_revision"]:
                raise BackupError("runtime_revision_mismatch")
            # Explicit recovery keys only. Host/session credentials unrelated to
            # rebuilding this runtime must not be collected opportunistically.
            keys = ("PGHOST", "PGPORT", "PGUSER", "PGPASSWORD", "PGDATABASE", "TCSI_ADMIN_LOGIN",
                    "TCSI_ADMIN_PASSWORD", "TCSI_MASTER_PASSWORD", "TCSI_WORKERS", "PORT",
                    "TCSI_DB_MAXCONN", "TCSI_LIMIT_TIME_REAL")
            recovery_environment = {key: environment[key.encode()].decode() for key in keys if key.encode() in environment}
            candidates.append((record, options, config_bytes, recovery_environment))
        except (OSError, ValueError, KeyError, configparser.Error):
            continue
    if len(candidates) != 1:
        raise BackupError("single_runtime_not_found")
    return candidates[0]


def idle(cursor, database):
    cursor.execute("SELECT count(*) FROM pg_prepared_xacts WHERE database = %s", (database,))
    if cursor.fetchone()[0]:
        raise BackupError("prepared_transactions_present")
    cursor.execute("""SELECT state, xact_start, usename = current_user FROM pg_stat_activity
                      WHERE datname = %s AND pid <> pg_backend_pid() AND backend_type = 'client backend'""", (database,))
    if any(state != "idle" or transaction is not None or same_user is not True
           for state, transaction, same_user in cursor.fetchall()):
        raise BackupError("database_not_idle")


def copy_tree(source, destination, deadline):
    destination.mkdir(mode=0o700)
    if source.is_symlink() or not source.is_dir():
        raise BackupError("unsafe_filestore")
    for item in source.rglob("*"):
        if time.monotonic() >= deadline:
            raise BackupError("pause_timeout")
        target = destination / item.relative_to(source)
        if item.is_symlink():
            raise BackupError("unsafe_filestore")
        if item.is_dir():
            target.mkdir(mode=0o700)
        elif item.is_file():
            shutil.copyfile(item, target, follow_symlinks=False)
            target.chmod(0o600)
        else:
            raise BackupError("unsafe_filestore")


def capture_snapshot(policy, directory):
    import psycopg2
    from psycopg2 import sql
    master, options, config_bytes, environment = discover(policy)
    connection = psycopg2.connect(host=options["db_host"], port=options["db_port"],
                                  user=options["db_user"], password=options["db_password"],
                                  dbname=policy["database"], connect_timeout=5)
    try:
        with connection.cursor() as cursor:
            idle(cursor, policy["database"])
        connection.rollback()
        with paused(master, policy["max_pause_seconds"]) as deadline:
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '1000ms'")
                cursor.execute("SET LOCAL statement_timeout = '2000ms'")
                # If the parent stalls after acquiring table locks, the independent
                # watchdog resumes Odoo and PostgreSQL bounds those locks too.
                cursor.execute("SELECT set_config('idle_in_transaction_session_timeout', %s, true)",
                               (str((policy["max_pause_seconds"] + 2) * 1000),))
                idle(cursor, policy["database"])
                cursor.execute("SELECT schemaname, tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema')")
                tables = cursor.fetchall()
                if not tables:
                    raise BackupError("empty_database")
                cursor.execute(sql.SQL("LOCK TABLE {} IN SHARE MODE").format(
                    sql.SQL(",").join(sql.Identifier(schema, table) for schema, table in tables)))
                pgpass = directory.parent / "pgpass"
                def escape(value):
                    return value.replace("\\", "\\\\").replace(":", "\\:")
                pgpass.write_text(":".join(escape(value) for value in (
                    options["db_host"], options["db_port"], policy["database"], options["db_user"], options["db_password"])) + "\n")
                pgpass.chmod(0o600)
                child_env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PGPASSFILE": str(pgpass),
                             "PGHOST": options["db_host"], "PGPORT": options["db_port"],
                             "PGUSER": options["db_user"], "PGDATABASE": policy["database"]}
                try:
                    run(["pg_dump", "--format=custom", "--no-owner", "--no-acl", "--file", str(directory / "database.dump")],
                        environment=child_env, timeout=max(0.01, deadline - time.monotonic()))
                finally:
                    pgpass.unlink(missing_ok=True)
                copy_tree(Path(policy["data_dir"]) / "filestore" / policy["database"], directory / "filestore", deadline)
                # Same paused writers, table locks and deadline as the dump/copy.
                # Store hashes only; never export raw accounting rows into logs.
                from recovery_fingerprint import fingerprint
                atomic_json(directory / "accounting-baseline.json",
                            fingerprint(connection, directory / "filestore", deadline))
                (directory / "odoo.conf").write_bytes(config_bytes)
                atomic_json(directory / "recovery-environment.json", environment)
                idle(cursor, policy["database"])
                if any(record["state"] not in ("T", "t") for record in members(master["group"])):
                    raise BackupError("writers_resumed_early")
        # Release locks after resuming. Queued work waits at most until this rollback.
    finally:
        connection.rollback()
        connection.close()
    run(["pg_restore", "--list", str(directory / "database.dump")], timeout=30)


def write_manifest(directory, metadata):
    files = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink() or (not path.is_file() and not path.is_dir()):
            raise BackupError("unsafe_bundle")
        if path.is_file():
            files[path.relative_to(directory).as_posix()] = {"size": path.stat().st_size, "sha256": digest(path)}
    atomic_json(directory / "manifest.json", {"format": 1, "metadata": metadata, "files": files})


def verify(directory):
    directory = Path(directory)
    if directory.is_symlink() or (directory / "manifest.json").is_symlink():
        raise BackupError("unsafe_bundle")
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest.get("format") != 1 or not isinstance(manifest.get("files"), dict):
        raise BackupError("invalid_manifest")
    actual = set()
    for path in directory.rglob("*"):
        if path.is_symlink() or (not path.is_file() and not path.is_dir()):
            raise BackupError("unsafe_bundle")
        if path.is_file() and path != directory / "manifest.json":
            actual.add(path.relative_to(directory).as_posix())
    if actual != set(manifest["files"]):
        raise BackupError("bundle_members_mismatch")
    for name, expected in manifest["files"].items():
        path = directory / name
        if path.stat().st_size != expected["size"] or digest(path) != expected["sha256"]:
            raise BackupError("bundle_hash_mismatch")
    return len(actual)


def validate_certificate(certificate):
    certificate = Path(certificate)
    if b"PRIVATE KEY" in certificate.read_bytes():
        raise BackupError("private_key_on_host")
    run(["openssl", "x509", "-in", str(certificate), "-noout", "-checkend", "0"], timeout=10)


def encrypt(directory, destination, certificate):
    validate_certificate(certificate)
    archive = directory.parent / "bundle.tar"
    try:
        with tarfile.open(archive, "w") as stream:
            for path in sorted(directory.rglob("*")):
                if path.is_file():
                    stream.add(path, arcname=path.relative_to(directory).as_posix(), recursive=False)
        run(["openssl", "cms", "-encrypt", "-binary", "-aes-256-cbc", "-in", str(archive),
             "-outform", "DER", "-out", str(destination), str(certificate)], timeout=300)
        destination.chmod(0o600)
    finally:
        archive.unlink(missing_ok=True)


def adapter(command, payload, timeout):
    output = run([command], timeout=timeout, input_data=json.dumps(payload).encode(),
                 environment={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
    try:
        return json.loads(output)
    except (ValueError, UnicodeError):
        raise BackupError("invalid_adapter_receipt") from None


def alert(policy, state):
    response = adapter(policy["alert_command"], {"event": "backup_attention", "status": state["status"],
                       "run_id": state.get("run_id"), "at": now()}, policy["adapter_timeout_seconds"])
    if response.get("accepted") is not True:
        raise BackupError("alert_not_accepted")


def capture(policy, snapshot=capture_snapshot):
    state = {"status": "running", "run_id": str(uuid.uuid4()), "started_at": now(), "last_success": None}
    state_path, lock = None, None
    try:
        state_dir = private_directory(policy["state_dir"])
        lock = (state_dir / "capture.lock").open("a")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise BackupError("capture_already_running") from None
        state_path = state_dir / "status.json"
        previous = json.loads(private_read(state_path)) if state_path.exists() else {}
        if not isinstance(previous, dict):
            raise BackupError("invalid_previous_status")
        state["last_success"] = previous.get("last_success")
        atomic_json(state_path, state)
        validate_certificate(policy["public_certificate"])
        with tempfile.TemporaryDirectory(prefix="capture-", dir=state_dir) as temporary:
            directory = Path(temporary) / "bundle"
            directory.mkdir(mode=0o700)
            snapshot(policy, directory)
            write_manifest(directory, {"captured_at": state["started_at"], "database": policy["database"],
                                      "source_revision": policy["source_revision"], "image_reference": policy["image_reference"]})
            verify(directory)
            artifact = Path(temporary) / "recovery.p7m"
            encrypt(directory, artifact, policy["public_certificate"])
            checksum = digest(artifact)
            receipt = adapter(policy["delivery_command"], {"artifact": str(artifact), "sha256": checksum,
                              "destination": policy["destination"], "run_id": state["run_id"],
                              "captured_at": state["started_at"]}, policy["adapter_timeout_seconds"])
            receipt_id = receipt.get("receipt_id")
            if receipt.get("durable") is not True or receipt.get("sha256") != checksum or receipt.get("destination") != policy["destination"] or not isinstance(receipt_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}", receipt_id):
                raise BackupError("delivery_not_verified")
            state.update(status="success", finished_at=now(), last_success={"at": state["started_at"], "sha256": checksum,
                         "run_id": state["run_id"], "destination": policy["destination"], "receipt_id": receipt_id})
            atomic_json(state_path, state)
    except BaseException as error:
        if isinstance(error, BackupError) and str(error) == "capture_already_running":
            raise
        code = str(error) if isinstance(error, BackupError) else "capture_failed"
        state.update(status="failed", finished_at=now(), error=code)
        try:
            if state_path:
                atomic_json(state_path, state)
        except Exception:
            state["status_write_failed"] = True
        try:
            alert(policy, state)
        except Exception:
            state["alert_failed"] = True
            try:
                if state_path:
                    atomic_json(state_path, state)
            except Exception:
                pass  # Alert and persistence failed; nonzero exit remains authoritative.
        raise BackupError(code) from None
    finally:
        if lock:
            lock.close()
    return state


def monitor(policy):
    path = Path(policy["state_dir"]) / "status.json"
    try:
        state = json.loads(private_read(path)) if path.exists() else {"status": "missed"}
        if not isinstance(state, dict) or state.get("status") not in ("running", "success", "failed", "missed"):
            raise ValueError("invalid status")
        success = state.get("last_success")
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(success["at"])).total_seconds() if success else float("inf")
    except (OSError, ValueError, KeyError, TypeError, BackupError):
        state, age = {"status": "failed"}, 0
    if age < 0 or age > policy["maximum_success_age_seconds"]:
        state = {**state, "status": "missed"}
    if state["status"] in ("failed", "missed"):
        alert(policy, state)
        raise BackupError("backup_attention_required")
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("capture", "monitor", "verify"))
    parser.add_argument("--config", type=Path)
    parser.add_argument("--directory", type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    def interrupted(_signal, _frame):
        raise BackupError("interrupted")
    signal.signal(signal.SIGTERM, interrupted)
    try:
        if args.action == "verify":
            if not args.directory:
                raise BackupError("directory_required")
            print(json.dumps({"verified_files": verify(args.directory)}))
        else:
            if not args.config:
                raise BackupError("config_required")
            policy = load_policy(args.config)
            result = capture(policy) if args.action == "capture" else monitor(policy)
            print(json.dumps({"status": result["status"]}))
    except Exception as error:
        print(json.dumps({"status": "failed", "error": str(error) if isinstance(error, BackupError) else "operation_failed"}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
