import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { config, proxy } from "./proxy";
import { unstable_doesMiddlewareMatch, unstable_getResponseFromNextConfig, getRewrittenUrl } from "next/experimental/testing/server";
import nextConfig from "./next.config";
import { accountingRoutePrefixes } from "./lib/accounting-routes";

afterEach(() => vi.unstubAllEnvs());

describe("hosted pilot boundary", () => {
  it.each(["/odoo", "/odoo/action-408", "/odoo/account.move/42"])("canonicalizes legacy bookmark %s before proxying", async (path) => {
    vi.stubEnv("VERCEL", "1");
    const response = await unstable_getResponseFromNextConfig({ url: `https://portal.example${path}?debug=1`, nextConfig });
    expect(response.status).toBe(308);
    expect(response.headers.get("location")).toBe(`https://portal.example${path.replace("/odoo", "/workspace")}?debug=1`);
  });
  it.each(accountingRoutePrefixes.filter((prefix) => prefix !== "odoo"))("rewrites /%s without middleware buffering or shared caching", async (prefix) => {
    vi.stubEnv("VERCEL", "1");
    const url = `https://portal.example/${prefix}/test?lang=en_US`;
    expect(unstable_doesMiddlewareMatch({ config, url, nextConfig })).toBe(false);
    const response = await unstable_getResponseFromNextConfig({ url, nextConfig });
    expect(getRewrittenUrl(response)).toBe(`https://tcsi-accounting-production.up.railway.app/${prefix}/test?lang=en_US`);
    expect(response.headers.get("x-vercel-enable-rewrite-caching")).toBe("0");
  });
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

  it.each(["/platform", "/controls", "/pilot", "/contact", "/owner", "/login", "/api/demo-requests", "/api/platform/analytics"])("allows public portal route %s", async (path) => {
    vi.stubEnv("TCSI_PORTAL_ONLY", "true");
    const response = await proxy(new NextRequest(`https://portal.example${path}`));
    expect(response.headers.get("x-middleware-next")).toBe("1");
    expect(response.headers.get("location")).toBeNull();
  });

  it.each(["/api/workspaces", "/api/dashboard"])("blocks unreleased endpoint %s", async (path) => {
    vi.stubEnv("TCSI_PORTAL_ONLY", "true");
    const response = await proxy(new NextRequest(`https://portal.example${path}`, { method: "POST" }));
    expect(response.status).toBe(404);
  });

  it.each(["/dashboard", "/invoices", "/settings"])("redirects unreleased page %s", async (path) => {
    vi.stubEnv("TCSI_PORTAL_ONLY", "true");
    const response = await proxy(new NextRequest(`https://portal.example${path}`));
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("https://portal.example/");
  });
});
