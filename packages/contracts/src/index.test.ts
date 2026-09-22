import { describe, expect, it } from "vitest";

import { dashboardSummarySchema, workerJobSchema } from "./index.js";

describe("shared TCSI contracts", () => {
  it("accepts a live dashboard envelope", () => {
    const summary = dashboardSummarySchema.parse({
      state: "ready",
      workspaceName: "Third Code Solutions",
      workspaceSlug: "third-code-solutions",
      metrics: [],
      activity: [],
      message: "Live data",
    });

    expect(summary.state).toBe("ready");
  });

  it("rejects malformed worker keys", () => {
    expect(() => workerJobSchema.parse({ jobName: "", runKey: "x" })).toThrow();
  });
});
