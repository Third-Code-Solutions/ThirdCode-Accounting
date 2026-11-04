import { describe, expect, it } from "vitest";

import { safeNextUrl } from "../../../lib/auth-redirect";

describe("safeNextUrl", () => {
  it("keeps relative destinations on the portal origin", () => {
    expect(safeNextUrl("/owner?tab=leads", "https://portal.example").href)
      .toBe("https://portal.example/owner?tab=leads");
  });

  it.each(["//attacker.example/path", "/\\attacker.example/path", "/%5c%5cattacker.example/path", "/\\%", "https://attacker.example/path", "owner"])(
    "rejects external or non-relative destination %s",
    (next) => {
      expect(safeNextUrl(next, "https://portal.example").href).toBe("https://portal.example/");
    },
  );
});
