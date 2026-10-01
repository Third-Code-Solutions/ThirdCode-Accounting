#!/usr/bin/env node
/**
 * Bootstrap the singleton TCSI platform-owner account.
 *
 * Creates (or reuses) the Supabase Auth user for the approved owner through
 * the supported GoTrue admin API, assigns it to public.platform_owner_access
 * (exactly one row may exist), and, when the password is available, verifies
 * that password sign-in actually works before finishing.
 *
 * Requirements:
 *   SUPABASE_ACCESS_TOKEN  a Supabase personal access token (sbp_...)
 *   SUPABASE_PROJECT_REF   optional, defaults to the hosted pilot project
 *
 * Password input, in order of precedence:
 *   --password-stdin          read one line from stdin (for scripted runs)
 *   SUPABASE_OWNER_PASSWORD   environment variable
 *   hidden interactive prompt (recommended when run by a person)
 *
 * Usage:
 *   SUPABASE_ACCESS_TOKEN=sbp_... node scripts/bootstrap-platform-owner.mjs --email owner@thirdcodesolutions.com
 */
import { createInterface } from "node:readline";

const PROJECT_REF = process.env.SUPABASE_PROJECT_REF ?? "zcalwevgunkevwzficvm";
const ACCESS_TOKEN = process.env.SUPABASE_ACCESS_TOKEN;
const emailIndex = process.argv.indexOf("--email");
const email = emailIndex >= 0 ? process.argv[emailIndex + 1] : null;
const passwordStdin = process.argv.includes("--password-stdin");

if (!ACCESS_TOKEN) {
  console.error("SUPABASE_ACCESS_TOKEN is required (Supabase personal access token).");
  process.exit(2);
}
if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
  console.error("Provide the owner's sign-in address: --email owner@example.com");
  process.exit(2);
}

const supabaseUrl = `https://${PROJECT_REF}.supabase.co`;

async function managementSql(query) {
  const response = await fetch(`https://api.supabase.com/v1/projects/${PROJECT_REF}/database/query`, {
    method: "POST",
    headers: { Authorization: `Bearer ${ACCESS_TOKEN}`, "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  const text = await response.text();
  if (!response.ok) throw new Error(`management query failed: ${text.slice(0, 240)}`);
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function readHiddenPassword(promptText) {
  const rl = createInterface({ input: process.stdin, output: process.stdout, terminal: true });
  const previousWrite = rl._writeToOutput?.bind(rl);
  rl._writeToOutput = (chunk) => {
    if (chunk.includes(promptText)) previousWrite?.(chunk);
    else previousWrite?.("*");
  };
  return await new Promise((resolve) => {
    rl.question(promptText, (answer) => {
      rl.close();
      process.stdout.write("\n");
      resolve(answer);
    });
  });
}

async function readPassword() {
  if (passwordStdin) {
    const chunks = [];
    for await (const chunk of process.stdin) chunks.push(chunk);
    return Buffer.concat(chunks).toString("utf8").split("\n")[0];
  }
  if (process.env.SUPABASE_OWNER_PASSWORD) {
    return process.env.SUPABASE_OWNER_PASSWORD;
  }
  const first = await readHiddenPassword(`Password for ${email} (input hidden): `);
  const second = await readHiddenPassword("Repeat password: ");
  if (first !== second) {
    console.error("Passwords did not match.");
    process.exit(2);
  }
  return first;
}

function assertStrongEnough(password) {
  if (typeof password !== "string" || password.length < 12) {
    console.error("Choose a password of at least 12 characters.");
    process.exit(2);
  }
}

async function fetchApiKeys() {
  const response = await fetch(`https://api.supabase.com/v1/projects/${PROJECT_REF}/api-keys`, {
    headers: { Authorization: `Bearer ${ACCESS_TOKEN}` },
  });
  if (!response.ok) throw new Error(`could not read project api keys (${response.status})`);
  const keys = await response.json();
  const serviceRole =
    keys.find((key) => key.name === "service_role" && key.api_key) ??
    keys.find((key) => typeof key.api_key === "string" && key.api_key.startsWith("sb_secret_"));
  const anon =
    keys.find((key) => key.name === "anon" && key.api_key) ??
    keys.find((key) => typeof key.api_key === "string" && key.api_key.startsWith("sb_publishable_"));
  if (!serviceRole?.api_key || !anon?.api_key) {
    throw new Error("service_role and anon keys were not both available");
  }
  return { serviceRoleKey: serviceRole.api_key, anonKey: anon.api_key };
}

async function findUserByEmail(serviceRoleKey, address) {
  // The admin list endpoint is paginated; the pilot has few users.
  for (let page = 1; page <= 20; page += 1) {
    const response = await fetch(`${supabaseUrl}/auth/v1/admin/users?page=${page}&per_page=200`, {
      headers: { Authorization: `Bearer ${serviceRoleKey}`, apikey: serviceRoleKey },
    });
    if (!response.ok) throw new Error(`admin user listing failed (${response.status})`);
    const body = await response.json();
    const users = body.users ?? [];
    const match = users.find((user) => user.email?.toLowerCase() === address.toLowerCase());
    if (match) return match;
    if (users.length < 200) return null;
  }
  return null;
}

async function createUser(serviceRoleKey, address, password) {
  const response = await fetch(`${supabaseUrl}/auth/v1/admin/users`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${serviceRoleKey}`,
      apikey: serviceRoleKey,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email: address, password, email_confirm: true }),
  });
  const text = await response.text();
  if (!response.ok) throw new Error(`user creation failed (${response.status}): ${text.slice(0, 240)}`);
  return JSON.parse(text);
}

async function verifyPasswordSignIn(anonKey, address, password) {
  const response = await fetch(`${supabaseUrl}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: { apikey: anonKey, "Content-Type": "application/json" },
    body: JSON.stringify({ email: address, password }),
  });
  return response.ok;
}

async function main() {
  console.log(`TCSI platform owner bootstrap against project ${PROJECT_REF}`);
  const { serviceRoleKey, anonKey } = await fetchApiKeys();

  let user = await findUserByEmail(serviceRoleKey, email);
  let createdNow = false;
  let password;
  let canVerify = false;

  if (!user) {
    password = await readPassword();
    assertStrongEnough(password);
    user = await createUser(serviceRoleKey, email, password);
    createdNow = true;
    canVerify = true;
    console.log(`Created the auth user ${email} (id ${user.id}).`);
  } else {
    console.log(`An auth user for ${email} already exists (id ${user.id}); password left unchanged.`);
    if (passwordStdin || process.env.SUPABASE_OWNER_PASSWORD) {
      password = await readPassword();
      canVerify = true;
    }
  }

  const assignment = await managementSql(
    `insert into public.platform_owner_access (user_id)
     values ('${user.id}')
     on conflict (singleton) do update set user_id = excluded.user_id
     returning user_id, created_at;`,
  );
  console.log(`platform_owner_access now points at user ${user.id}.`);

  if (canVerify) {
    const ok = await verifyPasswordSignIn(anonKey, email, password);
    if (!ok) {
      console.error("Sign-in verification failed: the account exists but the password did not authenticate.");
      process.exit(1);
    }
    console.log("Password sign-in verified against Supabase Auth.");
  } else {
    console.log("Existing account reused; password sign-in not re-verified. Reset the password in the dashboard if needed.");
  }

  const ownerCheck = await managementSql(
    `select count(*)::int as owner_rows from public.platform_owner_access;`,
  );
  console.log(`Owner rows: ${ownerCheck?.[0]?.owner_rows ?? "?"} (must be exactly 1).`);
  console.log(
    createdNow
      ? "Done. Sign in at https://tcsi-accounting-portal.vercel.app/login and open /owner."
      : "Done. The existing credentials keep working; open /owner after signing in.",
  );
  console.log("Reminder: never paste this password into a chat, ticket, or email. Store it in the team password manager.");
}

main().catch((error) => {
  console.error(`Bootstrap failed: ${error.message}`);
  process.exit(1);
});
