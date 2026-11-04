import { describe, expect, it } from "vitest";

import { makeRunKey } from "./jobs.js";

describe("worker idempotency keys", () => {
  it("is deterministic for the same scheduled run", () => {
    expect(makeRunKey("recurring-invoices", "2026-09-22T00:00:00Z")).toBe(
      "recurring-invoices:2026-09-22T00:00:00Z",
    );
  });

  it("isolates the same scheduled job across workspaces and global runs", () => {
    const at = "2026-10-10T00:00:00Z";
    const first = makeRunKey("daily", at, "workspace-a");
    const second = makeRunKey("daily", at, "workspace-b");
    expect(first).not.toBe(second);
    expect(first).not.toBe(makeRunKey("daily", at));
    expect(first).toBe(makeRunKey("daily", at, "workspace-a"));
  });
});
