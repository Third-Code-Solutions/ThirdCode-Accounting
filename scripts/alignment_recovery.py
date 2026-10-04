"""Native ZIP recovery rehearsal, via offline odoo shell after stopping writers.

Only synthetic tcsi_alignment_ databases are accepted. The target must not exist.
Mount /tmp/alignment-recovery to retain the ZIP and timing result. This local
exercise does not establish hosted backup scheduling, retention or a remote copy.
"""
import hashlib
import json
import os
import time
from pathlib import Path

from odoo import tools
from odoo.service import db

source = env.cr.dbname
assert source.startswith("tcsi_alignment_")
target = os.environ.get("ALIGNMENT_RECOVERY_TARGET", source + "_restored")
assert target.startswith("tcsi_alignment_") and target != source
tools.config["list_db"] = True  # Offline shell only; no database-manager HTTP.
assert target not in db.list_dbs(force=True), "Recovery target already exists; never overwrite it"
output = Path("/tmp/alignment-recovery")
output.mkdir(exist_ok=True)
backup = output / (source + ".zip")
assert not backup.exists(), "Keep prior backup evidence intact"
env.cr.commit()
with backup.open("wb") as stream:
    db.dump_db(source, stream, backup_format="zip")
started = time.monotonic()
db.restore_db(target, str(backup), copy=True, neutralize_database=True)
result = {"source": source, "target": target, "restore_seconds": round(time.monotonic() - started, 3),
          "backup_bytes": backup.stat().st_size, "backup_sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
          "scope": "Quiescent isolated synthetic database and filestore; no hosted recovery claim"}
(output / "recovery.json").write_text(json.dumps(result, indent=2) + "\n")
print("RECOVERY_RESULT " + json.dumps(result))
