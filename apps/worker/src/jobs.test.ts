import { describe, expect, it } from "vitest";

import { makeRunKey } from "./jobs.js";

describe("worker idempotency keys", () => {
  it("is deterministic for the same scheduled run", () => {
    expect(makeRunKey("recurring-invoices", "2026-09-22T00:00:00Z")).toBe(
      "recurring-invoices:2026-09-22T00:00:00Z",
    );
  });
});
