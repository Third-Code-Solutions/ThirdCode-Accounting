import { afterEach, describe, expect, it, vi } from "vitest";

import { GET } from "./route";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("pilot readiness", () => {
  it("requires both Auth and the accounting engine", async () => {
    vi.stubEnv("TCSI_PORTAL_ONLY", "true");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://example.supabase.co");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "test-key");
    vi.stubGlobal("fetch", vi.fn(async (url: string) => ({ ok: !url.includes("railway.app") })));

    const response = await GET();
    expect(response.status).toBe(503);
    expect(await response.json()).toMatchObject({
      status: "dependency_unavailable",
      mode: "pilot_portal",
      checks: { supabaseAuth: true, accountingEngine: false },
    });
  });

  it("reports ready when both dependencies respond", async () => {
    vi.stubEnv("TCSI_PORTAL_ONLY", "true");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://example.supabase.co");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "test-key");
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true })));

    const response = await GET();
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ checks: { supabaseAuth: true, accountingEngine: true } });
  });
});
