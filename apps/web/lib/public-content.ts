import { accountingOrigin } from "./accounting-routes";

export type PublishedItem = {
  id: number;
  kind: "seo" | "release";
  title: string;
  description: string;
  version: string;
  category: "feature" | "improvement" | "fix" | "security";
  published_at: string;
};
export type PublicContent = { seo: PublishedItem | null; releases: PublishedItem[]; available: boolean };

function publishedItem(value: unknown): value is PublishedItem {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return Number.isSafeInteger(v.id) && (v.kind === "seo" || v.kind === "release")
    && typeof v.title === "string" && v.title.length > 0 && v.title.length <= 120
    && typeof v.description === "string" && v.description.length <= 12000
    && typeof v.version === "string" && v.version.length <= 40
    && ["feature", "improvement", "fix", "security"].includes(String(v.category))
    && typeof v.published_at === "string" && !Number.isNaN(Date.parse(v.published_at));
}

export function parsePublicContent(value: unknown): PublicContent {
  if (!value || typeof value !== "object") throw new Error("Invalid published content");
  const data = value as Record<string, unknown>;
  if (data.seo !== null && (!publishedItem(data.seo) || data.seo.kind !== "seo")) throw new Error("Invalid published SEO");
  if (!Array.isArray(data.releases) || data.releases.length > 100 || data.releases.some((r) => !publishedItem(r) || r.kind !== "release")) throw new Error("Invalid published releases");
  return { seo: data.seo as PublishedItem | null, releases: data.releases as PublishedItem[], available: true };
}

export async function loadPublicContent(): Promise<PublicContent> {
  try {
    // Fixed first-party destination. No user URL, credentials or session forwarding.
    const response = await fetch(`${accountingOrigin}/thirdcode_accounting/public/website`, {
      cache: "no-store", signal: AbortSignal.timeout(4000), redirect: "error",
    });
    if (!response.ok) throw new Error("Published content unavailable");
    const raw = await response.text();
    if (raw.length > 1_500_000) throw new Error("Published content too large");
    return parsePublicContent(JSON.parse(raw));
  } catch {
    // Keep the existing, reviewed landing metadata available during an engine outage.
    console.warn("TCSI published website content unavailable; retaining default metadata");
    return { seo: null, releases: [], available: false };
  }
}
