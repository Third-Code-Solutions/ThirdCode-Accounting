import { readdir, readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const databaseUrl = process.env.SUPABASE_TEST_DATABASE_URL;
const psqlContainer = process.env.SUPABASE_TEST_PSQL_DOCKER_CONTAINER;
const psqlImage = process.env.SUPABASE_TEST_PSQL_IMAGE;
if (!databaseUrl) {
  console.error("SUPABASE_TEST_DATABASE_URL is required and must point to a disposable PostgreSQL database.");
  process.exit(2);
}

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const migrationsDir = resolve(root, "supabase/migrations");

function psql(sql, label) {
  const command = psqlContainer || psqlImage ? "docker" : "psql";
  const args = psqlContainer
    ? ["exec", "-i", psqlContainer, "psql", databaseUrl, "--no-psqlrc", "--set", "ON_ERROR_STOP=1", "--quiet", "--tuples-only", "--no-align"]
    : psqlImage
      ? ["run", "--rm", "-i", "--network", "host", psqlImage, "psql", databaseUrl, "--no-psqlrc", "--set", "ON_ERROR_STOP=1", "--quiet", "--tuples-only", "--no-align"]
      : [databaseUrl, "--no-psqlrc", "--set", "ON_ERROR_STOP=1", "--quiet", "--tuples-only", "--no-align"];
  const result = spawnSync(command, args, {
    input: sql,
    encoding: "utf8",
  });
  if (result.status !== 0) {
    console.error(`${label} failed`);
    if (result.stdout) console.error(result.stdout.trim());
    if (result.stderr) console.error(result.stderr.trim());
    process.exit(result.status ?? 1);
  }
  return result.stdout.trim();
}

const preflight = psql(
  `select current_database() || '|' || count(*)
   from pg_catalog.pg_class as relation
   join pg_catalog.pg_namespace as namespace on namespace.oid = relation.relnamespace
   where relation.relkind in ('r', 'p', 'v', 'm', 'S', 'f')
     and namespace.nspname not in ('pg_catalog', 'information_schema')
     and namespace.nspname not like 'pg_toast%';`,
  "disposable database preflight",
);
const [databaseName, publicTableCount] = preflight.split("|").map((value) => value.trim());
const disposableName = (databaseName ?? "").split("_").some((part) => ["test", "ci", "audit", "disposable"].includes(part.toLowerCase()));
if (!disposableName || publicTableCount !== "0") {
  console.error(`Refusing migration test against non-disposable or nonempty database: ${databaseName || "unknown"}`);
  process.exit(2);
}

psql(`
do $$ begin create role anon nologin; exception when duplicate_object then null; end $$;
do $$ begin create role authenticated nologin; exception when duplicate_object then null; end $$;
do $$ begin create role service_role nologin bypassrls; exception when duplicate_object then null; end $$;
create schema auth;
create table auth.users (id uuid primary key);
create or replace function auth.uid() returns uuid language sql stable as $$
  select nullif(current_setting('request.jwt.claims', true)::jsonb ->> 'sub', '')::uuid
$$;
grant usage on schema auth to anon, authenticated, service_role;
grant execute on function auth.uid() to anon, authenticated, service_role;
create or replace function public.rls_auto_enable() returns event_trigger language plpgsql as $$ begin end $$;
`, "Supabase compatibility bootstrap");

const migrationNames = (await readdir(migrationsDir)).filter((name) => name.endsWith(".sql")).sort();
for (const migrationName of migrationNames) {
  psql(await readFile(resolve(migrationsDir, migrationName), "utf8"), migrationName);
}

psql(`
insert into auth.users (id) values
  ('11111111-1111-4111-8111-111111111111'),
  ('22222222-2222-4222-8222-222222222222');
insert into public.workspaces (id, name, slug, created_by) values
  ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'Workspace A', 'migration-check-a', '11111111-1111-4111-8111-111111111111'),
  ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'Workspace B', 'migration-check-b', '22222222-2222-4222-8222-222222222222');
insert into public.workspace_members (workspace_id, user_id, role) values
  ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', '11111111-1111-4111-8111-111111111111', 'owner'),
  ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '22222222-2222-4222-8222-222222222222', 'owner');
insert into public.invoices
  (workspace_id, invoice_number, invoice_type, status, invoice_date, total_amount, balance_due, created_by)
select 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'INV-' || value, 'sales', 'issued', current_date,
       10, 10, '11111111-1111-4111-8111-111111111111'
from generate_series(1, 75) as value;
insert into public.invoices
  (workspace_id, invoice_number, invoice_type, status, invoice_date, total_amount, balance_due, created_by)
values ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'INV-B', 'sales', 'issued', current_date,
        25, 25, '22222222-2222-4222-8222-222222222222');
insert into public.invoices
  (workspace_id, invoice_number, invoice_type, status, invoice_date, currency, total_amount, balance_due, created_by)
values
  ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'EXCLUDED-DRAFT', 'sales', 'draft', current_date, 'PHP', 100, 100, '11111111-1111-4111-8111-111111111111'),
  ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'EXCLUDED-PURCHASE', 'purchase', 'issued', current_date, 'PHP', 100, 100, '11111111-1111-4111-8111-111111111111'),
  ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'EXCLUDED-USD', 'sales', 'issued', current_date, 'USD', 100, 100, '11111111-1111-4111-8111-111111111111'),
  ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'EXCLUDED-PAID', 'sales', 'paid', current_date, 'PHP', 100, 0, '11111111-1111-4111-8111-111111111111');

begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"11111111-1111-4111-8111-111111111111"}';
do $$
begin
  if public.get_workspace_receivables_due('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa') <> 750 then
    raise exception 'receivables summary truncated or incorrect';
  end if;
  if public.get_workspace_receivables_due('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb') <> 0 then
    raise exception 'cross-workspace receivables leaked';
  end if;
  begin
    perform public.create_workspace('Forbidden', 'forbidden');
    raise exception 'workspace self-provisioning remained executable';
  exception when insufficient_privilege then null;
  end;
end $$;
rollback;

begin;
set local role anon;
insert into public.demo_requests (company_name, contact_name, email, team_size, message, created_at, updated_at)
values
  ('Direct One', 'Test Contact', ' RATE@example.test ', '1-5', 'First direct request', '2000-01-01', '2000-01-01'),
  ('Direct Two', 'Test Contact', 'rate@EXAMPLE.test', '1-5', 'Second direct request', '2000-01-01', '2000-01-01'),
  ('Direct Three', 'Test Contact', 'rate@example.test', '1-5', 'Third direct request', '2000-01-01', '2000-01-01');
reset role;
do $$
begin
  if (select count(*) from public.demo_requests where email = 'rate@example.test' and created_at > now() - interval '1 minute') <> 3 then
    raise exception 'client-supplied demo request timestamps were retained';
  end if;
end $$;
set local role anon;
do $$
begin
  begin
    perform public.get_workspace_receivables_due('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
    raise exception 'anonymous receivables access remained executable';
  exception when insufficient_privilege then null;
  end;
  begin
    insert into public.demo_requests (company_name, contact_name, email, team_size, message, created_at, updated_at)
    values ('Direct Four', 'Test Contact', 'rate@example.test', '1-5', 'Fourth direct request', '2000-01-01', '2000-01-01');
    raise exception 'direct insert rate limit was bypassed';
  exception when sqlstate 'P0001' then
    if sqlerrm <> 'Demo request rate limit exceeded' then raise; end if;
  end;
  begin
    insert into public.demo_requests (company_name, contact_name, email, phone, team_size, message)
    values ('Oversized', 'Test Contact', 'other@example.test', repeat('1', 41), '1-5', 'Oversized phone request');
    raise exception 'phone length contract was bypassed';
  exception when check_violation then null;
  end;
  begin
    insert into public.demo_requests (company_name, contact_name, email, team_size, message)
    values ('Oversized', 'Test Contact', repeat('a', 243) || '@example.test', '1-5', 'Oversized email request');
    raise exception 'email length contract was bypassed';
  exception when check_violation then null;
  end;
end $$;
rollback;

insert into public.job_runs (workspace_id, job_name, run_key) values
  ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'recurring', '2026-10-10T00:00:00Z'),
  ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'recurring', '2026-10-10T00:00:00Z'),
  (null, 'global', '2026-10-10T00:00:00Z');
do $$
begin
  begin
    insert into public.job_runs (workspace_id, job_name, run_key)
    values (null, 'global', '2026-10-10T00:00:00Z');
    raise exception 'global job claim uniqueness was bypassed';
  exception when unique_violation then null;
  end;
end $$;
`, "migration behavior assertions");

console.log(`Applied ${migrationNames.length} migrations and passed isolated RLS/intake/aggregation assertions.`);
