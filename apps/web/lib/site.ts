const fallbackPortalOrigin = "https://tcsi-accounting-portal.vercel.app";

/** Canonical origin for crawler-facing files (robots.txt, sitemap.xml). */
export function siteOrigin(): string {
  const configured = process.env.NEXT_PUBLIC_APP_URL;
  if (!configured) return fallbackPortalOrigin;
  try {
    return new URL(configured).origin;
  } catch {
    return fallbackPortalOrigin;
  }
}

/** Marketing routes that are actually served by the hosted pilot portal. */
export const publicPortalSitemapPaths = ["/", "/platform", "/controls", "/pilot", "/contact"];
