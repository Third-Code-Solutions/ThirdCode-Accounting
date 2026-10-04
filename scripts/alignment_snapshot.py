"""Read-only DB/filestore fingerprint for isolated upgrade/recovery comparisons.

Run on the prepared Docker fixture. --baseline retains the original audit ID
boundary so additional upgrade audit events do not hide altered older evidence.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database")
    parser.add_argument("output", type=Path)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    if not args.database.startswith("tcsi_alignment_") or not args.database.replace("_", "").isalnum():
        parser.error("Only isolated tcsi_alignment_ fixture databases are supported")
    def sql(query):
        raw = subprocess.check_output(["docker", "exec", "tcsi-cloud-db-1", "psql", "-U", "odoo", "-d", args.database,
                                       "-At", "-v", "ON_ERROR_STOP=1", "-c", query], text=True)
        return json.loads(raw)
    prior = json.loads(args.baseline.read_text()) if args.baseline else None
    limits = prior["audit_limits"] if prior else sql("SELECT json_build_array(coalesce((SELECT max(id) FROM auditlog_log),0), coalesce((SELECT max(id) FROM auditlog_log_line),0))")
    queries = {
        "posted_documents": "SELECT id,name,date,journal_id,company_id,move_type,state FROM account_move WHERE state='posted' ORDER BY id",
        "posted_lines": "SELECT l.id,l.move_id,l.account_id,l.partner_id,l.debit,l.credit,l.amount_currency,l.amount_residual,l.date FROM account_move_line l JOIN account_move m ON m.id=l.move_id WHERE m.state='posted' ORDER BY l.id",
        "account_balances": "SELECT company_id,account_id,sum(balance) balance FROM account_move_line WHERE parent_state='posted' GROUP BY company_id,account_id ORDER BY company_id,account_id",
        "original_audits": f"SELECT id,model_id,res_id,user_id,method,create_date FROM auditlog_log WHERE id<={int(limits[0])} ORDER BY id",
        "original_audit_details": f"SELECT id,log_id,field_id,old_value,new_value FROM auditlog_log_line WHERE id<={int(limits[1])} ORDER BY id",
        "document_attachments": "SELECT id,res_model,res_id,res_field,name,checksum,store_fname,file_size FROM ir_attachment WHERE res_model IN ('account.move','thirdcode.migration.batch','thirdcode.bank.reconciliation') ORDER BY id",
    }
    if (prior and "retained_history" in prior["records"]) or (not prior and sql("SELECT to_json(to_regclass('public.thirdcode_migration_archive_entry') IS NOT NULL)")):
        queries["retained_history"] = "SELECT id,batch_id,source_entry_id,source_line_id,date,account_code,debit,credit,source_fingerprint FROM thirdcode_migration_archive_entry ORDER BY id"
        queries["cutover_results"] = "SELECT id,company_id,source_file_hash,cutover_fingerprint,cutover_payload,cutover_result FROM thirdcode_migration_batch WHERE cutover_fingerprint IS NOT NULL ORDER BY id"
    result = {"scope": "Isolated synthetic database; not hosted production evidence", "audit_limits": limits, "records": {}}
    for label, query in queries.items():
        rows = sql("SELECT coalesce(json_agg(t),'[]'::json) FROM (" + query + ") t")
        result["records"][label] = {"count": len(rows), "sha256": hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()}
    code = "import pathlib,hashlib,json; p=pathlib.Path('/data/filestore/" + args.database + "'); print(json.dumps({str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(p.rglob('*')) if f.is_file() and 'checklist' not in f.parts},sort_keys=True))"
    files = json.loads(subprocess.check_output(["docker", "run", "--rm", "--user", "root", "-v", "tcsi-cloud_odoo-data:/data:ro", "--entrypoint", "python3", "tcsi-cloud-dev", "-c", code], text=True))
    result["filestore"] = files
    if prior:
        assert result["records"] == prior["records"], "Existing accounting/audit/document fingerprints changed"
        assert all(files.get(name) == digest for name, digest in prior["filestore"].items()), "Existing filestore bytes changed or disappeared"
        result["baseline_preserved"] = True
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "records": result["records"], "files": len(files), "baseline_preserved": result.get("baseline_preserved")}))


if __name__ == "__main__":
    main()
