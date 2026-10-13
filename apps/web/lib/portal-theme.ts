export const portalThemeCookie = "tcsi-portal-theme";
export type PortalTheme = "light" | "dark";

/** An explicit preference wins; a first visit always starts in light mode. */
export function resolvePortalTheme(value?: string): PortalTheme {
  return value === "dark" ? "dark" : "light";
}
