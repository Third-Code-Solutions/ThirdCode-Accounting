import type { Metadata } from "next";
import { MarketingShell } from "../../components/marketing-layout";
import { loadPublicContent } from "../../lib/public-content";
import { siteOrigin } from "../../lib/site";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Product updates", description: "Published releases, improvements and fixes for TCSI Accounting.",
  alternates: { canonical: `${siteOrigin()}/updates` },
};

export default async function UpdatesPage() {
  const content = await loadPublicContent();
  return <MarketingShell active="/updates">
    <section className="updates-heading"><p className="home-eyebrow">PRODUCT JOURNAL</p><h1>What’s new in TCSI.</h1><p>Improvements, new capabilities and fixes. Published by the team behind your workspace.</p></section>
    <section className="updates-list" aria-label="Published product updates">
      {!content.available ? <p role="status">Updates are temporarily unavailable. Please try again shortly.</p>
        : content.releases.length === 0 ? <p>No product updates published yet.</p>
          : content.releases.map((release) => <article key={release.id} className="updates-entry">
            <div className="updates-meta"><span>{release.category}</span>{release.version && <span>{release.version}</span>}<time dateTime={release.published_at.replace(" ", "T")+"Z"}>{release.published_at.slice(0,10)}</time></div>
            <h2>{release.title}</h2><p className="updates-body">{release.description}</p>
          </article>)}
    </section>
  </MarketingShell>;
}
