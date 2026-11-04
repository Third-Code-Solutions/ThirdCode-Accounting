import { createHmac } from "node:crypto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { client, rpc, abortSignal } = vi.hoisted(() => {
  const abortSignal = vi.fn();
  const rpc = vi.fn<(name: string, params: { client_hash: string }) => { abortSignal: typeof abortSignal }>(() => ({ abortSignal }));
  return { client: vi.fn(async () => ({ rpc })), rpc, abortSignal };
});
vi.mock("../../../lib/supabase/server", () => ({ getSupabaseServerClient: client }));

import { POST } from "./route";

const secret = "a".repeat(64);
const validInput = {
  companyName: "Pilot Company", contactName: "Pilot Accountant", email: "Accountant@Example.test",
  teamSize: "1-5", message: "Please show us the accounting system.", website: "",
};
const requestFor = (headers: HeadersInit = {}) => new Request("https://example.test/api/demo-requests", {
  method: "POST", headers, body: JSON.stringify(validInput),
});

describe("demo requests", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubEnv("TCSI_DEMO_INTAKE_SECRET", secret);
    vi.stubEnv("VERCEL", "");
    abortSignal.mockResolvedValue({ error: null });
  });
  afterEach(() => vi.unstubAllEnvs());

  it("rejects an oversized body even without a Content-Length header", async () => {
    const request = new Request("https://example.test/api/demo-requests", {
      method: "POST",
      body: "x".repeat(24_001),
    });
    expect(request.headers.get("content-length")).toBeNull();

    const response = await POST(request);

    expect(response.status).toBe(413);
    expect((await response.json()).error.code).toBe("payload_too_large");
  });

  it("parses a valid bounded request", async () => {
    const request = new Request("https://example.test/api/demo-requests", {
      method: "POST",
      body: JSON.stringify({
        companyName: "Pilot Company",
        contactName: "Pilot Accountant",
        email: "Accountant@Example.test",
        teamSize: "1-5",
        message: "Please show us the accounting system.",
        website: "automated-submission",
      }),
    });

    const response = await POST(request);

    expect(response.status).toBe(201);
    expect((await response.json()).data.accepted).toBe(true);
    expect(client).not.toHaveBeenCalled();
  });

  it.each(["", "short", "G".repeat(64)])("fails closed with invalid intake configuration %s", async (value) => {
    vi.stubEnv("TCSI_DEMO_INTAKE_SECRET", value);
    expect((await POST(requestFor())).status).toBe(503);
    expect(client).not.toHaveBeenCalled();
  });

  it("submits through the bounded intake RPC with a server-owned identity", async () => {
    vi.stubEnv("VERCEL", "1");
    const response = await POST(requestFor({ "x-vercel-forwarded-for": "203.0.113.7", "x-forwarded-for": "attacker" }));
    expect(response.status).toBe(201);
    expect(rpc).toHaveBeenCalledWith("submit_demo_request", {
      ingestion_secret: secret,
      client_hash: createHmac("sha256", secret).update("demo-intake:203.0.113.7").digest("hex"),
      details: {
        company_name: "Pilot Company", contact_name: "Pilot Accountant", email: "accountant@example.test",
        phone: null, team_size: "1-5", accounting_stack: null, message: validInput.message,
      },
    });
    expect(abortSignal).toHaveBeenCalledWith(expect.any(AbortSignal));
    expect(await response.text()).not.toContain(secret);
  });

  it("ignores forged forwarding headers outside Vercel", async () => {
    await POST(requestFor({ "x-vercel-forwarded-for": "203.0.113.1", "x-forwarded-for": "203.0.113.2" }));
    await POST(requestFor({ "x-vercel-forwarded-for": "203.0.113.3", "x-real-ip": "203.0.113.4" }));
    expect(rpc.mock.calls[0][1].client_hash).toBe(rpc.mock.calls[1][1].client_hash);
  });

  it("canonicalizes IPv6 and bounds malformed or missing ingress identities", async () => {
    vi.stubEnv("VERCEL", "1");
    await POST(requestFor({ "x-vercel-forwarded-for": "2001:db8:0:0:0:0:0:1" }));
    await POST(requestFor({ "x-vercel-forwarded-for": "2001:db8::1" }));
    expect(rpc.mock.calls[0][1].client_hash).toBe(rpc.mock.calls[1][1].client_hash);
    await POST(requestFor({ "x-vercel-forwarded-for": "fe80::1%eth0" }));
    await POST(requestFor());
    expect(rpc.mock.calls[2][1].client_hash).toBe(rpc.mock.calls[3][1].client_hash);
  });

  it.each(["PT429", "P0001"])("returns a retry response for %s limits", async (code) => {
    abortSignal.mockResolvedValue({ error: { code, message: "Demo request rate limit exceeded" } });
    const response = await POST(requestFor());
    expect(response.status).toBe(429);
    expect(response.headers.get("retry-after")).toBe("3600");
    expect((await response.json()).error.code).toBe("rate_limited");
  });

  it("does not report database rejection or transport failure as accepted", async () => {
    abortSignal.mockResolvedValueOnce({ error: { code: "42501", message: "Intake authentication required" } });
    expect((await POST(requestFor())).status).toBe(503);
    abortSignal.mockRejectedValueOnce(new Error("timeout"));
    expect((await POST(requestFor())).status).toBe(503);
  });
});
