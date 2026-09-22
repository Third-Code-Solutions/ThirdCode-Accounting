/** Cloud deployments fail closed until the standalone ledger is released. */
export function isPilotPortal(): boolean {
  return process.env.TCSI_PORTAL_ONLY === "true" || process.env.VERCEL === "1";
}
