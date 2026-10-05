import Link from "next/link";
import { cookies } from "next/headers";

import { portalThemeCookie, resolvePortalTheme } from "../lib/portal-theme";
import { ThemeToggle } from "./theme-toggle";

function ArrowIcon() {
  return (
    <svg aria-hidden="true" className="landing-arrow" viewBox="0 0 16 16" fill="none">
      <path d="M2.5 8h10.2M8.8 3.8 13 8l-4.2 4.2" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.4" />
    </svg>
  );
}

function TCSIMark({ compact = false }: { compact?: boolean }) {
  return <span className={`landing-mark${compact ? " landing-mark--compact" : ""}`} aria-hidden="true">TC</span>;
}

export async function MarketingHeader({ active }: { active?: string }) {
  const theme = resolvePortalTheme((await cookies()).get(portalThemeCookie)?.value);
  const links = [
    ["Platform", "/#platform"],
    ["Why TCSI", "/#why-tcsi"],
    ["Getting started", "/#rollout"],
  ] as const;

  return (
    <header className="landing-header">
      <a className="marketing-skip" href="#main-content">Skip to content</a>
      <Link className="landing-brand" href="/" aria-label="TCSI Accounting home">
        <TCSIMark />
        <span><strong>TCSI <span>Accounting</span></strong><small>BY THIRD CODE SOLUTIONS INC.</small></span>
      </Link>
      <nav className="landing-nav" aria-label="Primary navigation">
        {links.map(([label, href]) => (
          <Link href={href} key={href} aria-current={active === href ? "page" : undefined}>{label}</Link>
        ))}
        <a className="marketing-mobile-signin" href="/web/login">Sign in</a>
      </nav>
      <div className="landing-header-actions">
        <ThemeToggle initialTheme={theme} />
        <a className="marketing-signin" href="/web/login">Sign in</a>
        <Link className="landing-header-cta" href="/contact">Request a demo <ArrowIcon /></Link>
      </div>
    </header>
  );
}

export function MarketingFooter() {
  return (
    <footer className="landing-footer">
      <div className="marketing-footer-top">
        <div className="marketing-footer-about">
          <Link className="landing-brand" href="/" aria-label="TCSI Accounting home">
            <TCSIMark compact /><span><strong>TCSI Accounting</strong><small>BY THIRD CODE SOLUTIONS INC.</small></span>
          </Link>
          <p>A clearer view of your business.<br />A better way to work with your numbers.</p>
        </div>
        <nav aria-label="Product links"><strong>Product</strong><Link href="/#platform">Capabilities</Link><Link href="/controls">Accounting controls</Link><Link href="/web/login">Sign in to workspace</Link></nav>
        <nav aria-label="Company links"><strong>Let’s talk</strong><Link href="/contact">Request a demo</Link><Link href="/pilot">Rollout & access</Link><a href="https://www.thirdcodesolutions.com" target="_blank" rel="noreferrer">Third Code Solutions <ArrowIcon /></a></nav>
      </div>
      <div className="marketing-footer-bottom"><span>© {new Date().getFullYear()} Third Code Solutions Inc.</span><span>Built for the people behind the numbers.</span></div>
    </footer>
  );
}

export function MarketingShell({ children, active }: Readonly<{ children: React.ReactNode; active?: string }>) {
  return (
    <div className="landing marketing-page">
      <div className="landing-frame">
        <MarketingHeader active={active} />
        <main id="main-content">{children}</main>
        <MarketingFooter />
      </div>
    </div>
  );
}

type DetailSection = {
  eyebrow: string;
  title: string;
  copy: string;
  bullets: string[];
};

export function MarketingDetailPage({
  active,
  eyebrow,
  title,
  intro,
  sections,
  asideTitle,
  asideCopy,
  asideLink,
  asideHref,
}: Readonly<{
  active: string;
  eyebrow: string;
  title: string;
  intro: string;
  sections: DetailSection[];
  asideTitle: string;
  asideCopy: string;
  asideLink: string;
  asideHref: string;
}>) {
  return (
    <MarketingShell active={active}>
      <section className="marketing-hero" aria-labelledby="marketing-page-title">
        <div className="marketing-hero-copy">
          <p className="landing-kicker"><span /> {eyebrow}</p>
          <h1 id="marketing-page-title">{title}</h1>
          <p className="marketing-hero-intro">{intro}</p>
        </div>
        <aside className="marketing-hero-aside">
          <span className="marketing-aside-index">TCSI / {active.replace("/", "")}</span>
          <strong>{asideTitle}</strong>
          <p>{asideCopy}</p>
          <Link className="landing-text-link" href={asideHref}>{asideLink} <ArrowIcon /></Link>
        </aside>
      </section>

      <section className="marketing-detail-grid" aria-label={`${eyebrow} details`}>
        {sections.map((section, index) => (
          <article className="marketing-detail-card" key={section.title}>
            <span className="marketing-detail-number">0{index + 1}</span>
            <div>
              <p className="landing-kicker">{section.eyebrow}</p>
              <h2>{section.title}</h2>
              <p>{section.copy}</p>
              <ul>
                {section.bullets.map((bullet) => <li key={bullet}>{bullet}</li>)}
              </ul>
            </div>
          </article>
        ))}
      </section>
    </MarketingShell>
  );
}
