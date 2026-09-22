/** Cloud deployments fail closed until the standalone ledger is released. */
export function isPilotPortal(): boolean {
  return process.env.TCSI_PORTAL_ONLY === "true" || process.env.VERCEL === "1";
}

const publicPortalPages = new Set(["/", "/platform", "/controls", "/pilot", "/contact", "/owner", "/login"]);
const publicPortalApis = new Set(["/api/demo-requests", "/api/platform/analytics"]);

export function isPublicPortalPage(pathname: string): boolean {
  return publicPortalPages.has(pathname);
}

export function isPublicPortalApi(pathname: string): boolean {
  return publicPortalApis.has(pathname);
}
