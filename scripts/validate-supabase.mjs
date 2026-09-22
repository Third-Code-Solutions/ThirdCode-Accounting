import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const migrationPath = resolve(root, "supabase/migrations/20260922000000_tcsi_foundation.sql");
const sql = await readFile(migrationPath, "utf8");
const portalMigrationPath = resolve(root, "supabase/migrations/20260922103000_portal_leads_and_platform_owner.sql");
const portalSql = await readFile(portalMigrationPath, "utf8");
const hardeningMigrationPath = resolve(root, "supabase/migrations/20260922150000_harden_platform_function_grants.sql");
const hardeningSql = await readFile(hardeningMigrationPath, "utf8");
const workspaceHardeningMigrationPath = resolve(root, "supabase/migrations/20260922152000_harden_workspace_function.sql");
const workspaceHardeningSql = await readFile(workspaceHardeningMigrationPath, "utf8");
const privateSchemaMigrationPath = resolve(root, "supabase/migrations/20260922153000_grant_private_schema_usage.sql");
const privateSchemaSql = await readFile(privateSchemaMigrationPath, "utf8");

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

const portalChecks = {
  demoRequestsTable: portalSql.includes("create table public.demo_requests"),
  platformOwnerTable: portalSql.includes("create table public.platform_owner_access"),
  demoRequestsRls: portalSql.includes("alter table public.demo_requests force row level security"),
  ownerRls: portalSql.includes("alter table public.platform_owner_access force row level security"),
  publicInsertOnly: portalSql.includes("grant insert on public.demo_requests to anon, authenticated") && !portalSql.includes("grant select on public.demo_requests"),
  analyticsAuthorization: portalSql.includes("Platform owner access required") && portalSql.includes("grant execute on function public.get_platform_analytics() to authenticated"),
};

const hardeningChecks = {
  explicitAnonRevoke: hardeningSql.includes("from anon, authenticated"),
  privateSchema: hardeningSql.includes("create schema if not exists private"),
  invokerWrapper: hardeningSql.includes("security invoker") && hardeningSql.includes("private.get_platform_analytics()"),
  denyPolicy: hardeningSql.includes("create policy platform_owner_access_deny"),
  workspaceInvokerWrapper: workspaceHardeningSql.includes("security invoker") && workspaceHardeningSql.includes("private.create_workspace"),
  workspacePrivateGrant: workspaceHardeningSql.includes("grant execute on function private.create_workspace(text, text) to authenticated"),
  privateSchemaUsage: privateSchemaSql.includes("grant usage on schema private to authenticated"),
};

if (Object.values(portalChecks).some((check) => !check)) {
  console.error(JSON.stringify({ portalMigration: portalMigrationPath, portalChecks }, null, 2));
  process.exit(1);
}

if (Object.values(hardeningChecks).some((check) => !check)) {
    console.error(JSON.stringify({ hardeningMigration: hardeningMigrationPath, workspaceHardeningMigration: workspaceHardeningMigrationPath, hardeningChecks }, null, 2));
  process.exit(1);
}

console.log(JSON.stringify({
  migration: migrationPath,
  tables: requiredTables.length,
  rlsTables: rlsCount,
  forcedRlsTables: forceRlsCount,
  policies: policyCount,
  portalChecks,
  hardeningChecks,
  status: "ok",
}, null, 2));
