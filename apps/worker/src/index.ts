import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { createServer } from "node:http";

import { loadWorkerEnv } from "./env.js";

const env = loadWorkerEnv();
const port = env.PORT ?? env.WORKER_PORT;
const supabase: SupabaseClient | null = env.configured
  ? createClient(env.SUPABASE_URL!, env.SUPABASE_SERVICE_ROLE_KEY!, {
      auth: { autoRefreshToken: false, persistSession: false },
    })
  : null;

function log(event: string, details: Record<string, unknown> = {}) {
  console.info(JSON.stringify({ service: "tcsi-worker", event, timestamp: new Date().toISOString(), ...details }));
}

function respond(response: import("node:http").ServerResponse, status: number, body: Record<string, unknown>) {
  response.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  });
  response.end(JSON.stringify(body));
}

const server = createServer((request, response) => {
  if (request.method !== "GET") {
    respond(response, 405, { error: "method_not_allowed" });
    return;
  }

  if (request.url === "/health") {
    respond(response, 200, { status: "ok", service: "tcsi-worker" });
    return;
  }

  if (request.url === "/ready") {
    respond(response, env.configured ? 200 : 503, {
      status: env.configured ? "ready" : "configuration_required",
      service: "tcsi-worker",
      checks: { supabase: env.configured },
    });
    return;
  }

  respond(response, 404, { error: "not_found" });
});

server.listen(port, () => {
  log("worker_started", { port, configured: env.configured, environment: env.WORKER_ENV });
});

const scheduler = setInterval(() => {
  if (!supabase) {
    log("scheduler_waiting_for_configuration");
    return;
  }

  // Accounting jobs are added as vertical slices. The idempotent claim/finish
  // helpers are the only path scheduled jobs may use to write job state.
  log("scheduler_ready", { pollIntervalMs: env.WORKER_POLL_INTERVAL_MS });
}, env.WORKER_POLL_INTERVAL_MS);

function shutdown(signal: string) {
  clearInterval(scheduler);
  log("worker_stopping", { signal });
  server.close(() => process.exit(0));
}

process.once("SIGTERM", () => shutdown("SIGTERM"));
process.once("SIGINT", () => shutdown("SIGINT"));
