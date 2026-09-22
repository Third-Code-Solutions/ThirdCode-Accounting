import Link from "next/link";

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

export function MarketingHeader({ active }: { active?: string }) {
  const links = [
    ["Platform", "/platform"],
    ["Controls", "/controls"],
    ["Pilot", "/pilot"],
    ["Contact", "/contact"],
  ] as const;

  return (
    <header className="landing-header">
      <Link className="landing-brand" href="/" aria-label="TCSI Accounting home">
        <TCSIMark />
        <span><strong>Third Code Solutions Inc.</strong><small>TCSI Accounting</small></span>
      </Link>
      <nav className="landing-nav" aria-label="Primary navigation">
        {links.map(([label, href]) => (
          <Link className={active === href ? "marketing-nav-link--active" : undefined} href={href} key={href} aria-current={active === href ? "page" : undefined}>
            {label}
          </Link>
        ))}
      </nav>
      <div className="landing-header-actions">
        <a className="landing-text-link landing-header-company" href="https://www.thirdcodesolutions.com" target="_blank" rel="noreferrer">Company site <ArrowIcon /></a>
        <Link className="landing-header-cta" href="/web/login">Open workspace <ArrowIcon /></Link>
      </div>
    </header>
  );
}

export function MarketingFooter() {
  return (
    <footer className="landing-footer">
      <div className="landing-footer-brand"><TCSIMark compact /><span><strong>Third Code Solutions Inc.</strong><small>Accounting systems, made clearer.</small></span></div>
      <div className="landing-footer-links">
        <span>© {new Date().getFullYear()} TCSI</span>
        <Link href="/contact">Request a demo <ArrowIcon /></Link>
        <a href="https://www.thirdcodesolutions.com" target="_blank" rel="noreferrer">thirdcodesolutions.com <ArrowIcon /></a>
      </div>
    </footer>
  );
}

export function MarketingShell({ children, active }: Readonly<{ children: React.ReactNode; active?: string }>) {
  return (
    <main className="landing marketing-page">
      <div className="landing-frame">
        <MarketingHeader active={active} />
        {children}
        <MarketingFooter />
      </div>
    </main>
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
