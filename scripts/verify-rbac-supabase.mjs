#!/usr/bin/env node
/**
 * Verify Row Level Security and the role matrix of the TCSI Supabase project
 * against the live database, across two organizations (workspaces).
 *
 * The check creates two throwaway organizations, six probe users (one per
 * role in organization A, one owner in organization B), and a small seed of
 * accounting rows. Every assertion runs as the simulated role inside a
 * transaction that is rolled back, so no business data is left behind. The
 * probe users and organizations are deleted at the end, including when a
 * check fails.
 *
 * Requirements:
 *   SUPABASE_ACCESS_TOKEN  a Supabase personal access token (sbp_...)
 *   SUPABASE_PROJECT_REF   optional, defaults to the hosted pilot project
 *
 * Usage:
 *   SUPABASE_ACCESS_TOKEN=sbp_... npm run verify:rbac
 *   SUPABASE_ACCESS_TOKEN=sbp_... node scripts/verify-rbac-supabase.mjs --json report.json
 */
import { writeFile } from "node:fs/promises";

const PROJECT_REF = process.env.SUPABASE_PROJECT_REF ?? "zcalwevgunkevwzficvm";
const ACCESS_TOKEN = process.env.SUPABASE_ACCESS_TOKEN;
const jsonFlagIndex = process.argv.indexOf("--json");
const jsonPath = jsonFlagIndex >= 0 ? process.argv[jsonFlagIndex + 1] : null;

if (!ACCESS_TOKEN) {
  console.error("SUPABASE_ACCESS_TOKEN is required (Supabase personal access token).");
  process.exit(2);
}

const USER = {
  ownerA: "11111111-1111-4111-8111-000000000001",
  adminA: "11111111-1111-4111-8111-000000000002",
  accountantA: "11111111-1111-4111-8111-000000000003",
  encoderA: "11111111-1111-4111-8111-000000000004",
  viewerA: "11111111-1111-4111-8111-000000000005",
  ownerB: "11111111-1111-4111-8111-000000000006",
};
const WORKSPACE_A = "22222222-2222-4222-8222-000000000001";
const WORKSPACE_B = "22222222-2222-4222-8222-000000000002";
const ACCOUNT_A = "33333333-3333-4333-8333-000000000001";
const ACCOUNT_B = "33333333-3333-4333-8333-000000000002";
const JOURNAL_A = "44444444-4444-4444-8444-000000000001";
const JOURNAL_B = "44444444-4444-4444-8444-000000000002";
const PERIOD_A = "55555555-5555-4555-8555-000000000001";
const PERIOD_B = "55555555-5555-4555-8555-000000000002";
const ENTRY_A = "66666666-6666-4666-8666-000000000001";
const INVOICE_A = "77777777-7777-4777-8777-000000000001";
const INVOICE_B = "77777777-7777-4777-8777-000000000002";
const PROBE_EMAILS = Object.values(USER).map((id) => `rbac-probe-${id.slice(-1)}@tcsi-rbac-check.test`);

async function runSql(query) {
  const response = await fetch(
    `https://api.supabase.com/v1/projects/${PROJECT_REF}/database/query`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${ACCESS_TOKEN}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ query }),
    },
  );
  const text = await response.text();
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    body = text;
  }
  if (!response.ok) {
    const message = typeof body === "object" && body !== null ? body.message ?? text : text;
    const error = new Error(String(message));
    error.status = response.status;
    throw error;
  }
  return body;
}

function identitySql(userId) {
  return `
begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"${userId}","role":"authenticated","aud":"authenticated"}';
`;
}

const DENIED_MATCHERS = [
  /row-level security/i,
  /permission denied/i,
  /not authorized/i,
  /platform owner/i,
  /violates row-level security/i,
];

const checks = [
  {
    id: "workspace-read-own",
    description: "Owner A reads only workspace A through membership policy",
    sql: `${identitySql(USER.ownerA)}
select count(*)::int as visible from public.workspaces;
rollback;`,
    expect: "allowed",
    assert: (rows) => rows[0]?.visible === 1 || `visible=${rows[0]?.visible}`,
  },
  {
    id: "workspace-cross-org-read",
    description: "Owner A cannot see organization B workspace",
    sql: `${identitySql(USER.ownerA)}
select count(*)::int as visible from public.workspaces where id = '${WORKSPACE_B}';
rollback;`,
    expect: "allowed",
    assert: (rows) => rows[0]?.visible === 0 || `visible=${rows[0]?.visible}`,
  },
  {
    id: "accounts-cross-org-read",
    description: "Owner B cannot read organization A chart of accounts",
    sql: `${identitySql(USER.ownerB)}
select count(*)::int as visible from public.accounts where workspace_id = '${WORKSPACE_A}';
rollback;`,
    expect: "allowed",
    assert: (rows) => rows[0]?.visible === 0 || `visible=${rows[0]?.visible}`,
  },
  {
    id: "invoices-cross-org-read",
    description: "Owner B cannot read organization A invoices",
    sql: `${identitySql(USER.ownerB)}
select count(*)::int as visible from public.invoices where workspace_id = '${WORKSPACE_A}';
rollback;`,
    expect: "allowed",
    assert: (rows) => rows[0]?.visible === 0 || `visible=${rows[0]?.visible}`,
  },
  {
    id: "cross-org-write",
    description: "Owner B cannot insert an account into organization A",
    sql: `${identitySql(USER.ownerB)}
insert into public.accounts (workspace_id, code, name, account_type, created_by)
values ('${WORKSPACE_A}', '9999', 'Cross org', 'asset', '${USER.ownerB}');
rollback;`,
    expect: "denied",
  },
  {
    id: "viewer-write-denied",
    description: "Viewer cannot insert accounts",
    sql: `${identitySql(USER.viewerA)}
insert into public.accounts (workspace_id, code, name, account_type, created_by)
values ('${WORKSPACE_A}', '9998', 'Viewer attempt', 'asset', '${USER.viewerA}');
rollback;`,
    expect: "denied",
  },
  {
    id: "encoder-account-insert",
    description: "Encoder can insert an account",
    sql: `${identitySql(USER.encoderA)}
insert into public.accounts (workspace_id, code, name, account_type, created_by)
values ('${WORKSPACE_A}', '1001', 'Encoder cash', 'asset', '${USER.encoderA}')
returning code;
rollback;`,
    expect: "allowed",
    assert: (rows) => rows[0]?.code === "1001" || `code=${rows[0]?.code}`,
  },
  {
    id: "encoder-account-update-denied",
    description: "Encoder cannot update accounts (accountant and up only)",
    sql: `${identitySql(USER.encoderA)}
with mutated as (
  update public.accounts set name = 'Encoder rename' where id = '${ACCOUNT_A}' returning 1
)
select count(*)::int as affected from mutated;
rollback;`,
    expect: "noop",
  },
  {
    id: "accountant-account-update",
    description: "Accountant can update accounts",
    sql: `${identitySql(USER.accountantA)}
update public.accounts set name = 'Accountant renamed' where id = '${ACCOUNT_A}'
returning name;
rollback;`,
    expect: "allowed",
    assert: (rows) => rows[0]?.name === "Accountant renamed" || `name=${rows[0]?.name}`,
  },
  {
    id: "encoder-entry-draft",
    description: "Encoder can create a draft journal entry as themselves",
    sql: `${identitySql(USER.encoderA)}
insert into public.journal_entries (workspace_id, journal_id, period_id, entry_date, description, created_by)
values ('${WORKSPACE_A}', '${JOURNAL_A}', '${PERIOD_A}', '2026-02-01', 'Encoder draft', '${USER.encoderA}')
returning status;
rollback;`,
    expect: "allowed",
    assert: (rows) => rows[0]?.status === "draft" || `status=${rows[0]?.status}`,
  },
  {
    id: "encoder-entry-forged-author-denied",
    description: "Encoder cannot create an entry attributed to another user",
    sql: `${identitySql(USER.encoderA)}
insert into public.journal_entries (workspace_id, journal_id, period_id, entry_date, description, created_by)
values ('${WORKSPACE_A}', '${JOURNAL_A}', '${PERIOD_A}', '2026-02-01', 'Forged author', '${USER.ownerA}');
rollback;`,
    expect: "denied",
  },
  {
    id: "viewer-entry-update-denied",
    description: "Viewer cannot update journal entries",
    sql: `${identitySql(USER.viewerA)}
with mutated as (
  update public.journal_entries set status = 'posted' where id = '${ENTRY_A}' returning 1
)
select count(*)::int as affected from mutated;
rollback;`,
    expect: "noop",
  },
  {
    id: "accountant-entry-post",
    description: "Accountant can post a journal entry",
    sql: `${identitySql(USER.accountantA)}
update public.journal_entries set status = 'posted', posted_by = '${USER.accountantA}', posted_at = now()
where id = '${ENTRY_A}' returning status;
rollback;`,
    expect: "allowed",
    assert: (rows) => rows[0]?.status === "posted" || `status=${rows[0]?.status}`,
  },
  {
    id: "owner-delete-denied",
    description: "Owners cannot delete accounts (no delete policy)",
    sql: `${identitySql(USER.ownerA)}
with mutated as (
  delete from public.accounts where id = '${ACCOUNT_A}' returning 1
)
select count(*)::int as affected from mutated;
rollback;`,
    expect: "noop",
  },
  {
    id: "anon-accounts-denied",
    description: "Anonymous visitors cannot read accounts",
    sql: `begin;
set local role anon;
select count(*) from public.accounts;
rollback;`,
    expect: "denied",
  },
  {
    id: "anon-demo-request-insert",
    description: "Anonymous visitors can submit a website demo request",
    sql: `begin;
set local role anon;
insert into public.demo_requests (company_name, contact_name, email, team_size, message, source, status)
values ('RBAC Check Co', 'Probe', 'probe@tcsi-rbac-check.test', '1-5', 'rbac verification probe', 'website', 'new');
rollback;`,
    expect: "allowed",
  },
  {
    id: "anon-demo-request-read-denied",
    description: "Anonymous visitors cannot read demo requests",
    sql: `begin;
set local role anon;
select count(*) from public.demo_requests;
rollback;`,
    expect: "denied",
  },
  {
    id: "workspace-self-provision-revoked",
    description: "Authenticated users cannot self-provision workspaces",
    sql: `${identitySql(USER.ownerA)}
select public.create_workspace('RBAC Check Sneaky', 'rbac-check-sneaky');
rollback;`,
    expect: "denied",
  },
  {
    id: "platform-analytics-non-owner-denied",
    description: "Customer accounts cannot read platform analytics",
    sql: `${identitySql(USER.ownerA)}
select public.get_platform_analytics();
rollback;`,
    expect: "denied",
  },
  {
    id: "platform-owner-table-denied",
    description: "Customer accounts cannot read the platform owner table",
    sql: `${identitySql(USER.ownerA)}
select count(*) from public.platform_owner_access;
rollback;`,
    expect: "denied",
  },
  {
    id: "audit-insert-denied",
    description: "Authenticated users cannot forge audit events",
    sql: `${identitySql(USER.ownerA)}
insert into public.audit_events (workspace_id, actor_id, action, entity_type)
values ('${WORKSPACE_A}', '${USER.ownerA}', 'forged', 'account');
rollback;`,
    expect: "denied",
  },
  {
    id: "audit-read-member",
    description: "Workspace members can read audit events of their organization",
    sql: `${identitySql(USER.encoderA)}
select count(*)::int as visible from public.audit_events where workspace_id = '${WORKSPACE_A}';
rollback;`,
    expect: "allowed",
  },
  {
    id: "members-self-only",
    description: "Members can only list their own membership rows",
    sql: `${identitySql(USER.viewerA)}
select count(*)::int as visible from public.workspace_members where workspace_id = '${WORKSPACE_A}';
rollback;`,
    expect: "allowed",
    assert: (rows) => rows[0]?.visible === 1 || `visible=${rows[0]?.visible}`,
  },
  {
    id: "workspace-update-owner",
    description: "Owner can rename their organization",
    sql: `${identitySql(USER.ownerA)}
update public.workspaces set name = 'RBAC Check A renamed' where id = '${WORKSPACE_A}' returning name;
rollback;`,
    expect: "allowed",
  },
  {
    id: "workspace-update-cross-org-denied",
    description: "Owner B cannot rename organization A",
    sql: `${identitySql(USER.ownerB)}
with mutated as (
  update public.workspaces set name = 'Taken over' where id = '${WORKSPACE_A}' returning 1
)
select count(*)::int as affected from mutated;
rollback;`,
    expect: "noop",
  },
];

const setupSql = `
delete from public.workspaces where slug in ('rbac-check-a', 'rbac-check-b');
delete from public.demo_requests where email = 'probe@tcsi-rbac-check.test';
delete from auth.users where email like '%@tcsi-rbac-check.test';

insert into auth.users (id, instance_id, aud, role, email, email_confirmed_at, raw_app_meta_data, raw_user_meta_data, created_at, updated_at)
values
  ('${USER.ownerA}', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', '${PROBE_EMAILS[0]}', now(), '{"provider":"email","providers":["email"]}', '{}', now(), now()),
  ('${USER.adminA}', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', '${PROBE_EMAILS[1]}', now(), '{"provider":"email","providers":["email"]}', '{}', now(), now()),
  ('${USER.accountantA}', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', '${PROBE_EMAILS[2]}', now(), '{"provider":"email","providers":["email"]}', '{}', now(), now()),
  ('${USER.encoderA}', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', '${PROBE_EMAILS[3]}', now(), '{"provider":"email","providers":["email"]}', '{}', now(), now()),
  ('${USER.viewerA}', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', '${PROBE_EMAILS[4]}', now(), '{"provider":"email","providers":["email"]}', '{}', now(), now()),
  ('${USER.ownerB}', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', '${PROBE_EMAILS[5]}', now(), '{"provider":"email","providers":["email"]}', '{}', now(), now());

insert into public.workspaces (id, name, slug, created_by)
values
  ('${WORKSPACE_A}', 'RBAC Check A', 'rbac-check-a', '${USER.ownerA}'),
  ('${WORKSPACE_B}', 'RBAC Check B', 'rbac-check-b', '${USER.ownerB}');

insert into public.workspace_members (workspace_id, user_id, role)
values
  ('${WORKSPACE_A}', '${USER.ownerA}', 'owner'),
  ('${WORKSPACE_A}', '${USER.adminA}', 'admin'),
  ('${WORKSPACE_A}', '${USER.accountantA}', 'accountant'),
  ('${WORKSPACE_A}', '${USER.encoderA}', 'encoder'),
  ('${WORKSPACE_A}', '${USER.viewerA}', 'viewer'),
  ('${WORKSPACE_B}', '${USER.ownerB}', 'owner');

insert into public.accounts (id, workspace_id, code, name, account_type, created_by)
values
  ('${ACCOUNT_A}', '${WORKSPACE_A}', '1000', 'Cash on hand A', 'asset', '${USER.ownerA}'),
  ('${ACCOUNT_B}', '${WORKSPACE_B}', '1000', 'Cash on hand B', 'asset', '${USER.ownerB}');

insert into public.journals (id, workspace_id, code, name, journal_type)
values
  ('${JOURNAL_A}', '${WORKSPACE_A}', 'GEN', 'General A', 'general'),
  ('${JOURNAL_B}', '${WORKSPACE_B}', 'GEN', 'General B', 'general');

insert into public.accounting_periods (id, workspace_id, name, start_date, end_date)
values
  ('${PERIOD_A}', '${WORKSPACE_A}', 'FY 2026 A', '2026-01-01', '2026-12-31'),
  ('${PERIOD_B}', '${WORKSPACE_B}', 'FY 2026 B', '2026-01-01', '2026-12-31');

insert into public.journal_entries (id, workspace_id, journal_id, period_id, entry_date, description, created_by)
values ('${ENTRY_A}', '${WORKSPACE_A}', '${JOURNAL_A}', '${PERIOD_A}', '2026-01-15', 'RBAC seed entry', '${USER.ownerA}');

insert into public.invoices (id, workspace_id, invoice_number, invoice_type, status, invoice_date, subtotal, tax_total, total_amount, balance_due, created_by)
values
  ('${INVOICE_A}', '${WORKSPACE_A}', 'INV-RBAC-1', 'sales', 'issued', '2026-01-10', 100, 12, 112, 112, '${USER.ownerA}'),
  ('${INVOICE_B}', '${WORKSPACE_B}', 'INV-RBAC-1', 'sales', 'issued', '2026-01-10', 100, 12, 112, 112, '${USER.ownerB}');
`;

const cleanupSql = `
delete from public.workspaces where slug in ('rbac-check-a', 'rbac-check-b');
delete from public.demo_requests where email = 'probe@tcsi-rbac-check.test';
delete from auth.users where email like '%@tcsi-rbac-check.test';
`;

function isDeniedError(message) {
  return DENIED_MATCHERS.some((matcher) => matcher.test(message));
}

const results = [];
let failed = 0;

console.log(`TCSI RBAC verification against project ${PROJECT_REF}`);

try {
  await runSql(setupSql);
  console.log("Probe organizations, users, and seed rows created.");
} catch (error) {
  console.error("Setup failed:", error.message);
  process.exit(1);
}

try {
  for (const check of checks) {
    let outcome = "fail";
    let detail = "";
    let rows = null;
    let lastError = null;
    // Retry once on transient transport failures.
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        rows = await runSql(check.sql);
        lastError = null;
        break;
      } catch (error) {
        lastError = error;
        if (error.status === undefined && attempt === 0) continue;
        break;
      }
    }
    if (lastError) {
      if (check.expect === "denied" && isDeniedError(lastError.message)) {
        outcome = "pass";
        detail = "operation denied";
      } else if (check.expect === "denied") {
        detail = `denied but not by policy: ${lastError.message.slice(0, 160)}`;
      } else {
        detail = lastError.message.slice(0, 160);
      }
    } else if (check.expect === "denied") {
      detail = "operation unexpectedly allowed";
    } else {
      const assertVerdict = check.expect === "noop"
        ? (rows[0]?.affected === 0 || `affected=${rows[0]?.affected}`)
        : check.assert
          ? check.assert(rows)
          : true;
      if (assertVerdict !== true) {
        detail = `assertion failed: ${assertVerdict}`;
      } else {
        outcome = "pass";
        detail = check.expect === "noop" ? "operation affected no rows" : "operation allowed";
      }
    }
    if (outcome !== "pass") failed += 1;
    results.push({ id: check.id, description: check.description, expect: check.expect, outcome, detail });
    const marker = outcome === "pass" ? "PASS" : "FAIL";
    console.log(`  [${marker}] ${check.id} - ${check.description}${outcome === "pass" ? "" : ` (${detail})`}`);
  }
} finally {
  try {
    await runSql(cleanupSql);
    console.log("Probe data removed.");
  } catch (error) {
    console.error("Cleanup failed - remove rbac-check-a / rbac-check-b manually:", error.message);
    failed += 1;
  }
}

const summary = {
  projectRef: PROJECT_REF,
  checkedAt: new Date().toISOString(),
  passed: results.filter((result) => result.outcome === "pass").length,
  failed,
  results,
};

console.log(`\n${summary.passed}/${results.length} checks passed.`);
if (jsonPath) {
  await writeFile(jsonPath, `${JSON.stringify(summary, null, 2)}\n`);
  console.log(`Report written to ${jsonPath}`);
}
process.exit(failed === 0 ? 0 : 1);
