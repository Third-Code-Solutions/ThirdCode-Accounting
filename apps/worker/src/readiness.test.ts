import { createClient } from "@supabase/supabase-js";
import { describe, expect, it, vi } from "vitest";

import { workerReadiness } from "./readiness.js";

describe("worker readiness", () => {
  it("requires configuration", async () => {
    expect((await workerReadiness(null)).status).toBe("configuration_required");
  });

  it("probes the database but does not claim scheduling support", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response("[]", { status: 200 }));
    const client = createClient("https://database.example", "test-key", { global: { fetch } });
    expect(await workerReadiness(client)).toEqual({
      status: "scheduler_disabled", checks: { supabase: true, scheduler: false },
    });
    expect(String(fetch.mock.calls[0][0])).toContain("/rest/v1/job_runs?select=id&limit=1");
    expect(fetch.mock.calls[0][1].signal).toBeInstanceOf(AbortSignal);
  });

  it("rejects revoked credentials instead of treating strings as readiness", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('{"message":"Invalid API key"}', { status: 401 }));
    const client = createClient("https://database.example", "revoked-key", { global: { fetch } });
    expect((await workerReadiness(client)).status).toBe("dependency_unavailable");
  });

  it("bounds a stalled dependency request", async () => {
    const fetch: typeof globalThis.fetch = async (_input, init) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => reject(init.signal?.reason), { once: true });
    });
    const client = createClient("https://database.example", "test-key", { global: { fetch } });
    const started = Date.now();
    expect((await workerReadiness(client)).status).toBe("dependency_unavailable");
    expect(Date.now() - started).toBeLessThan(4500);
  });
});
