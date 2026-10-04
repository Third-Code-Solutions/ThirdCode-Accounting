"""Review or explicitly apply an existing residual-cutover batch through native RPC.

Create the draft batch and retain its source/mapping files in Migration Batches.
Preview is read-only. Credentials come from ODOO_URL, ODOO_DB, ODOO_LOGIN and
ODOO_PASSWORD, never command-line arguments or evidence output.
"""
import argparse
import json
import os
from pathlib import Path

from verify_milestone1 import Odoo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", type=int, required=True)
    parser.add_argument("--company-id", type=int, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--archive-history", type=Path, help="Optional balanced non-posting history JSON; requires --apply")
    args = parser.parse_args()
    if args.archive_history and not args.apply:
        parser.error("--archive-history requires --apply; it retains source evidence without posting history")
    client = Odoo(*(os.environ[key] for key in ("ODOO_URL", "ODOO_DB", "ODOO_LOGIN", "ODOO_PASSWORD")))
    context = {"context": {"allowed_company_ids": [args.company_id]}}
    method = "action_apply_cutover" if args.apply else "action_preview_cutover"
    result = client.call("thirdcode.migration.batch", method, [[args.batch_id]], context)
    if args.archive_history:
        rows = json.loads(args.archive_history.read_text(encoding="utf-8"))
        result["archive"] = client.call("thirdcode.migration.batch", "action_archive_source_history", [[args.batch_id], rows], context)
    print(json.dumps({"mode": "apply" if args.apply else "read-only preview", "result": result}, indent=2))


if __name__ == "__main__":
    main()
