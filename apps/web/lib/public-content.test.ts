import { afterEach, describe, expect, it, vi } from "vitest";
import { loadPublicContent, parsePublicContent } from "./public-content";

const entry = { id: 1, kind: "seo", title: "Title", description: "Description", version: "", category: "improvement", published_at: "2026-10-06 10:00:00" };
afterEach(() => vi.unstubAllGlobals());
describe("published website boundary", () => {
  it("accepts only published field shapes and release types", () => {
    expect(parsePublicContent({ seo: entry, releases: [] }).seo?.title).toBe("Title");
    expect(() => parsePublicContent({ seo: entry, releases: [entry] })).toThrow();
    expect(() => parsePublicContent({ seo: { ...entry, title: "x".repeat(121) }, releases: [] })).toThrow();
    expect(() => parsePublicContent({ seo: null, releases: [{ ...entry, kind: "release", category: "<script>" }] })).toThrow();
  });
  it("uses a fixed first-party endpoint and retains explicit unavailable state", async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: false });
    vi.stubGlobal("fetch", fetcher);
    const warning = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    expect(await loadPublicContent()).toEqual({ seo: null, releases: [], available: false });
    expect(fetcher).toHaveBeenCalledWith("https://tcsi-accounting-production.up.railway.app/thirdcode_accounting/public/website", expect.objectContaining({ cache: "no-store", redirect: "error" }));
    warning.mockRestore();
  });
  it("preserves text for escaped rendering, never evaluates markup", () => {
    expect(parsePublicContent({ seo: { ...entry, title: "<script>alert(1)</script>" }, releases: [] }).seo?.title).toContain("<script>");
  });
});
