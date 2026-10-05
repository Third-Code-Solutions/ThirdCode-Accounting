"""Read-only, streaming accounting recovery fingerprints; no raw ledger export.

PostgreSQL renders numeric values as JSON text before the client sees them.
This avoids Odoo's global Decimal-to-float psycopg typecaster changing hashes.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import time

import hosted_backup as capture

REQUIRED = (
    "res_company", "account_move", "account_move_line", "account_partial_reconcile",
    "account_full_reconcile", "account_payment", "auditlog_log", "auditlog_log_line", "ir_attachment",
)
OPTIONAL = ("thirdcode_migration_archive_entry", "thirdcode_migration_batch")


def remaining(deadline):
    seconds = deadline - time.monotonic()
    if seconds <= 0:
        raise capture.BackupError("fingerprint_deadline")
    return max(1, int(seconds * 1000))


def query(cursor, statement, deadline, parameters=()):
    cursor.execute("SELECT set_config('statement_timeout', %s, true)", (str(remaining(deadline)),))
    cursor.execute(statement, parameters)


def hash_rows(rows):
    count, digest = 0, hashlib.sha256()
    for row in rows:
        # Length framing preserves row boundaries even when JSON contains newlines.
        text = row[0]
        if not isinstance(text, str):
            raise capture.BackupError("fingerprint_text_required")
        raw = text.encode("utf-8")
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)
        count += 1
    return {"count": count, "sha256": digest.hexdigest()}


def safe_file(directory, name):
    name_path = PurePosixPath(name)
    if (not name or name_path.is_absolute() or ".." in name_path.parts or "\\" in name
            or str(name_path) != name):
        raise capture.BackupError("unsafe_attachment_path")
    path = directory
    for part in name_path.parts:
        path = path / part
        if path.is_symlink():
            raise capture.BackupError("unsafe_attachment_path")
    if not path.is_file():
        raise capture.BackupError("attachment_file_missing")
    return path


def fingerprint(connection, filestore, deadline):
    """Use caller's locked or read-only repeatable-read transaction; never commit."""
    from psycopg2 import sql
    filestore = Path(filestore)
    if filestore.is_symlink() or not filestore.is_dir():
        raise capture.BackupError("unsafe_filestore")
    result = {"format": 1, "tables": {}, "files": {}}
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL TIME ZONE 'UTC'")
        cursor.execute("SET LOCAL DateStyle = 'ISO, YMD'")
        cursor.execute("SET LOCAL extra_float_digits = 3")
        for table in REQUIRED + OPTIONAL:
            query(cursor, "SELECT to_regclass(%s) IS NOT NULL", deadline, ("public." + table,))
            exists = cursor.fetchone()[0]
            if not exists:
                if table in REQUIRED:
                    raise capture.BackupError("recovery_schema_missing")
                continue
            # Named cursors keep large audit histories out of client memory.
            with connection.cursor(name="recovery_" + table) as stream:
                query(cursor, "SELECT 1", deadline)
                stream.execute(sql.SQL("SELECT row_to_json(t)::text FROM (SELECT * FROM {} ORDER BY id) t")
                               .format(sql.Identifier("public", table)))
                def rows():
                    while True:
                        cursor.execute("SELECT set_config('statement_timeout', %s, true)",
                                       (str(remaining(deadline)),))
                        chunk = stream.fetchmany(1000)
                        if not chunk:
                            return
                        yield from chunk
                result["tables"][table] = hash_rows(rows())
        query(cursor, """SELECT row_to_json(t)::text FROM (
            SELECT company_id, account_id, sum(balance) AS balance
            FROM account_move_line WHERE parent_state='posted'
            GROUP BY company_id, account_id ORDER BY company_id, account_id) t""", deadline)
        result["balances"] = hash_rows(cursor)
        query(cursor, "SELECT store_fname, checksum FROM ir_attachment WHERE store_fname IS NOT NULL ORDER BY id", deadline)
        for name, checksum in cursor:
            remaining(deadline)
            path = safe_file(filestore, name)
            sha256, sha1, size = hashlib.sha256(), hashlib.sha1(), 0
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    remaining(deadline)
                    sha256.update(block)
                    sha1.update(block)
                    size += len(block)
            if checksum and checksum != sha1.hexdigest():
                raise capture.BackupError("attachment_checksum_mismatch")
            value = {"sha256": sha256.hexdigest(), "size": size}
            if name in result["files"] and result["files"][name] != value:
                raise capture.BackupError("attachment_changed_during_fingerprint")
            result["files"][name] = value
    return result


def validate_baseline(value):
    if (not isinstance(value, dict) or value.get("format") != 1
            or not isinstance(value.get("tables"), dict)
            or not set(REQUIRED).issubset(value["tables"])
            or not isinstance(value.get("files"), dict) or not isinstance(value.get("balances"), dict)):
        raise capture.BackupError("recovery_baseline_required")
    # JSON-compatible deterministic comparison, independent of mapping insertion order.
    return json.loads(json.dumps(value, sort_keys=True))
