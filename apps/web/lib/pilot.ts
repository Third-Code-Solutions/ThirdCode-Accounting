/** Cloud deployments fail closed until the standalone ledger is released. */
export function isPilotPortal(): boolean {
  return process.env.TCSI_PORTAL_ONLY === "true" || process.env.VERCEL === "1";
}

const publicPortalPages = new Set([
  "/",
  "/platform",
  "/controls",
  "/pilot",
  "/contact",
  "/owner",
  "/login",
  "/auth/confirm",
  "/icon.svg",
  "/robots.txt",
  "/sitemap.xml",
  "/apple-touch-icon.png",
]);
const publicPortalApis = new Set(["/api/demo-requests", "/api/platform/analytics"]);

/**
 * Screens that exist in the router but are withheld from the hosted pilot.
 * These keep redirecting home; anything else must be allowed to 404 so that
 * monitoring and crawlers can tell a real page from a typo.
 */
const withheldPortalPages = [
  "/dashboard",
  "/customers",
  "/invoices",
  "/reports",
  "/settings",
  "/transactions",
];

export function isPublicPortalPage(pathname: string): boolean {
  return publicPortalPages.has(pathname);
}

export function isPublicPortalApi(pathname: string): boolean {
  return publicPortalApis.has(pathname);
}

export function isWithheldPortalPage(pathname: string): boolean {
  return withheldPortalPages.some(
    (page) => pathname === page || pathname.startsWith(`${page}/`),
  );
}
