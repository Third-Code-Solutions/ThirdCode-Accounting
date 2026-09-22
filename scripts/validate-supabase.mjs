import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const migrationPath = resolve(root, "supabase/migrations/20260922000000_tcsi_foundation.sql");
const sql = await readFile(migrationPath, "utf8");

const requiredTables = [
  "workspaces",
  "workspace_members",
  "accounts",
  "journals",
  "accounting_periods",
  "journal_entries",
  "journal_entry_lines",
  "counterparties",
  "invoices",
  "invoice_lines",
  "audit_events",
  "job_runs",
];

const missingTables = requiredTables.filter((table) => !sql.includes(`create table public.${table}`));
const rlsCount = (sql.match(/enable row level security/g) ?? []).length;
const forceRlsCount = (sql.match(/force row level security/g) ?? []).length;
const policyCount = (sql.match(/create policy/g) ?? []).length;
const hasAnonRevoke = sql.includes("from anon");
const hasServiceRoleComment = sql.includes("service role") && sql.includes("never sent to the browser");

if (missingTables.length || rlsCount < requiredTables.length || forceRlsCount < requiredTables.length || policyCount < 20 || !hasAnonRevoke || !hasServiceRoleComment) {
  console.error(JSON.stringify({ missingTables, rlsCount, forceRlsCount, policyCount, hasAnonRevoke, hasServiceRoleComment }, null, 2));
  process.exit(1);
}

console.log(JSON.stringify({
  migration: migrationPath,
  tables: requiredTables.length,
  rlsTables: rlsCount,
  forcedRlsTables: forceRlsCount,
  policies: policyCount,
  status: "ok",
}, null, 2));
