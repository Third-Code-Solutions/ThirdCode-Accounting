// These paths belong to the existing accounting engine, not the unreleased app.
export const accountingRoutePrefixes = [
  "web", "workspace", "odoo", "mail", "bus", "websocket", "report",
  "account", "payment", "portal", "my", "digest", "auth_totp",
  "thirdcode_accounting", "discuss", "hr_expense", "spreadsheet",
];

export function isAccountingRoute(pathname: string): boolean {
  return accountingRoutePrefixes.some((prefix) =>
    pathname === `/${prefix}` || pathname.startsWith(`/${prefix}/`),
  ) || /^\/[a-zA-Z0-9_]+\/static\//.test(pathname) || pathname === "/logo.png";
}

export const accountingOrigin = "https://tcsi-accounting-production.up.railway.app";
