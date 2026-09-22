import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { proxy } from "./proxy";

afterEach(() => vi.unstubAllEnvs());

describe("hosted pilot boundary", () => {
  it.each(["/web/login", "/web/session/authenticate", "/workspace/action-408", "/report/pdf/test/1", "/mail/data", "/websocket", "/thirdcode_accounting/static/src/img/tcsi-mark.svg"])("passes accounting route %s to the origin rewrite", async (path) => {
    vi.stubEnv("TCSI_PORTAL_ONLY", "true");
    const response = await proxy(new NextRequest(`https://portal.example${path}`));
    expect(response.headers.get("x-middleware-next")).toBe("1");
    expect(response.headers.get("location")).toBeNull();
  });
  it("fails closed on Vercel when a preview has no portal flag", async () => {
    vi.stubEnv("VERCEL", "1");
    vi.stubEnv("TCSI_PORTAL_ONLY", undefined);
    const response = await proxy(new NextRequest("https://portal.example/api/workspaces", { method: "POST" }));
    expect(response.status).toBe(404);
  });
  it("allows the portal without requiring a ledger session", async () => {
    vi.stubEnv("TCSI_PORTAL_ONLY", "true");
    const response = await proxy(new NextRequest("https://portal.example/"));
    expect(response.headers.get("x-middleware-next")).toBe("1");
  });

  it.each(["/api/workspaces", "/api/dashboard"])("blocks unreleased endpoint %s", async (path) => {
    vi.stubEnv("TCSI_PORTAL_ONLY", "true");
    const response = await proxy(new NextRequest(`https://portal.example${path}`, { method: "POST" }));
    expect(response.status).toBe(404);
  });

  it.each(["/dashboard", "/login", "/invoices", "/settings"])("redirects unreleased page %s", async (path) => {
    vi.stubEnv("TCSI_PORTAL_ONLY", "true");
    const response = await proxy(new NextRequest(`https://portal.example${path}`));
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("https://portal.example/");
  });
});
