import { describe, expect, it } from "vitest";

import { POST } from "./route";

describe("demo requests", () => {
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
  });
});
