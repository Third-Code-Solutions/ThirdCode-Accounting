import { describe, expect, it } from "vitest";
import { resolvePortalTheme } from "./portal-theme";

describe("portal theme preference", () => {
  it("defaults to light without an explicit choice", () => {
    expect(resolvePortalTheme()).toBe("light");
    expect(resolvePortalTheme("system")).toBe("light");
    expect(resolvePortalTheme("invalid")).toBe("light");
  });
  it("restores only supported preferences", () => {
    expect(resolvePortalTheme("dark")).toBe("dark");
    expect(resolvePortalTheme("light")).toBe("light");
  });
});
