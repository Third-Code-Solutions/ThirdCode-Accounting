import Link from "next/link";

import { MarketingFooter, MarketingHeader } from "./marketing-layout";

type FeatureKind = "ledger" | "review" | "evidence";

function TCSIMark({ compact = false }: { compact?: boolean }) {
  return <span className={`landing-mark${compact ? " landing-mark--compact" : ""}`} aria-hidden="true">TC</span>;
}

function ArrowIcon() {
  return (
    <svg aria-hidden="true" className="landing-arrow" viewBox="0 0 16 16" fill="none">
      <path d="M2.5 8h10.2M8.8 3.8 13 8l-4.2 4.2" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.4" />
    </svg>
  );
}

function PreviewGlyph({ kind }: { kind: "overview" | "ledger" | "review" }) {
  if (kind === "ledger") {
    return <span className="preview-glyph preview-glyph--ledger" aria-hidden="true"><i /><i /><i /></span>;
  }
  if (kind === "review") {
    return <span className="preview-glyph preview-glyph--review" aria-hidden="true"><i /><i /></span>;
  }
  return <span className="preview-glyph" aria-hidden="true"><i /><i /><i /></span>;
}

function FeatureIcon({ kind }: { kind: FeatureKind }) {
  if (kind === "review") {
    return (
      <svg aria-hidden="true" className="feature-icon" viewBox="0 0 24 24" fill="none">
        <path d="M6 4.5h9.2L18.5 7v12.5H6V4.5Z" stroke="currentColor" strokeWidth="1.5" />
        <path d="M15 4.5V8h3.5M9 11h6M9 14h4" stroke="currentColor" strokeLinecap="round" strokeWidth="1.5" />
      </svg>
    );
  }
  if (kind === "evidence") {
    return (
      <svg aria-hidden="true" className="feature-icon" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="8.5" stroke="currentColor" strokeWidth="1.5" />
        <path d="m8.5 12.2 2.2 2.2 4.8-5" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" />
      </svg>
    );
  }
  return (
    <svg aria-hidden="true" className="feature-icon" viewBox="0 0 24 24" fill="none">
      <path d="M4.5 7.5h15M4.5 12h15M4.5 16.5h9" stroke="currentColor" strokeLinecap="round" strokeWidth="1.5" />
      <path d="M4.5 4.5h15v15h-15v-15Z" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function ProductPreview() {
  return (
    <div className="landing-preview" aria-label="Preview of the TCSI Accounting workspace">
      <div className="preview-topbar">
        <div className="preview-brand"><TCSIMark compact /><span>Finance workspace</span></div>
        <span className="preview-status"><i /> Sample view</span>
      </div>
      <div className="preview-body">
        <aside className="preview-rail" aria-label="Preview navigation">
          <span className="preview-rail-label">Workspace</span>
          <span className="preview-rail-item preview-rail-item--active"><PreviewGlyph kind="overview" />Overview</span>
          <span className="preview-rail-item"><PreviewGlyph kind="ledger" />Ledger</span>
          <span className="preview-rail-item"><PreviewGlyph kind="review" />Review</span>
          <span className="preview-rail-item"><PreviewGlyph kind="ledger" />Controls</span>
        </aside>
        <div className="preview-main">
          <div className="preview-heading">
            <div><span>Today</span><strong>Command center</strong></div>
            <span className="preview-date">Sep 22, 2026</span>
          </div>
          <div className="preview-kpis">
            <div><span>Cash position</span><strong>$198,420</strong><small>Across posted accounts</small></div>
            <div><span>Open invoices</span><strong>24</strong><small>8 need review</small></div>
            <div><span>Month close</span><strong>72%</strong><small>On track</small></div>
          </div>
          <div className="preview-lower">
            <div className="preview-chart-panel">
              <div className="preview-panel-head"><span>Cash movement</span><small>Last 30 days</small></div>
              <svg className="preview-chart" viewBox="0 0 520 144" fill="none" preserveAspectRatio="none" aria-hidden="true">
                <path d="M0 32h520M0 72h520M0 112h520" stroke="#f0edf5" />
                <path d="M0 116C42 108 52 96 88 103c38 7 54-26 88-20 38 7 53 2 85-21 34-24 56 15 87-2 25-14 52-35 78-31 29 5 45-7 94-23v138H0V116Z" fill="#f1edff" />
                <path d="M0 116C42 108 52 96 88 103c38 7 54-26 88-20 38 7 53 2 85-21 34-24 56 15 87-2 25-14 52-35 78-31 29 5 45-7 94-23" stroke="#7152d6" strokeLinecap="round" strokeWidth="2" />
                <circle cx="426" cy="36" r="3.5" fill="#7152d6" />
              </svg>
              <div className="preview-axis"><span>Aug 24</span><span>Sep 08</span><span>Sep 22</span></div>
            </div>
            <div className="preview-activity">
              <div className="preview-panel-head"><span>Activity</span><small>View all</small></div>
              <div className="preview-activity-row"><span className="preview-activity-dot" /><div><strong>Reconciliation</strong><small>Ready for review</small></div><time>09:40</time></div>
              <div className="preview-activity-row"><span className="preview-activity-dot preview-activity-dot--soft" /><div><strong>Invoice review</strong><small>3 new documents</small></div><time>08:15</time></div>
              <div className="preview-activity-row"><span className="preview-activity-dot preview-activity-dot--muted" /><div><strong>Statement export</strong><small>Completed</small></div><time>Yesterday</time></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

const features: Array<{ kind: FeatureKind; label: string; title: string; copy: string }> = [
  {
    kind: "ledger",
    label: "01 / Ledger control",
    title: "See what moved, and why.",
    copy: "Bring journals, balances, and account activity into one readable operating view for the day.",
  },
  {
    kind: "review",
    label: "02 / Review flows",
    title: "Make the next action obvious.",
    copy: "Create and follow invoices, payments, and close work with focused queues instead of scattered handoffs.",
  },
  {
    kind: "evidence",
    label: "03 / Clear evidence",
    title: "Leave a trail people can trust.",
    copy: "Give every financial conversation a source, status, owner, and audit event before it reaches the close.",
  },
];

export function LandingPage() {
  return (
    <main className="landing">
      <div className="landing-frame">
        <MarketingHeader />

        <section className="landing-hero" id="top" aria-labelledby="landing-title">
          <div className="landing-hero-copy">
            <p className="landing-kicker"><span /> TCSI ACCOUNTING <b>/</b> CUSTOMER PILOT</p>
            <h1 id="landing-title">Clear books for the work <em>behind the numbers.</em></h1>
            <p className="landing-lede">TCSI Accounting connects the everyday financial work: prepare entries, follow invoices, reconcile activity, and understand what is ready for close.</p>
            <div className="landing-actions">
              <a className="landing-button landing-button--primary" href="/web/login">Open the accounting workspace <ArrowIcon /></a>
              <Link className="landing-button landing-button--quiet" href="/platform">See the platform <ArrowIcon /></Link>
            </div>
            <dl className="landing-hero-details">
              <div><dt>Access</dt><dd>Invitation-only pilot</dd></div>
              <div><dt>Designed for</dt><dd>Review · reconcile · close</dd></div>
            </dl>
          </div>
          <ProductPreview />
        </section>

        <section className="landing-intro" id="platform" aria-labelledby="platform-title">
          <div className="landing-intro-heading">
            <p className="landing-kicker">THE OPERATING VIEW</p>
            <h2 id="platform-title">One place for the financial day.</h2>
          </div>
          <div className="landing-intro-copy">
            <p>TCSI Accounting puts the state of your work in front of you without adding another layer of noise. Start with what needs attention, then follow the evidence through the ledger.</p>
            <Link className="landing-text-link" href="/controls">A clearer way to work <ArrowIcon /></Link>
          </div>
        </section>

        <section className="landing-feature-grid" id="controls" aria-label="Platform capabilities">
          {features.map((feature) => (
            <article className="landing-feature" key={feature.kind}>
              <div className="landing-feature-top"><FeatureIcon kind={feature.kind} /><span>{feature.label}</span></div>
              <h3>{feature.title}</h3>
              <p>{feature.copy}</p>
              <span className="landing-feature-rule" aria-hidden="true" />
            </article>
          ))}
        </section>

        <section className="landing-signal" aria-label="TCSI operating principles">
          <div><p className="landing-kicker">BUILT AROUND YOUR CLOSE</p><h2>Less searching. More certainty.</h2></div>
          <div className="landing-signal-items">
            <div><strong>01</strong><span>One operating view</span></div>
            <div><strong>02</strong><span>Reviewable handoffs</span></div>
            <div><strong>03</strong><span>Clear next steps</span></div>
          </div>
        </section>

        <section className="landing-cta" id="pilot" aria-labelledby="pilot-title">
          <div><p className="landing-kicker">READY WHEN YOU ARE</p><h2 id="pilot-title">Bring the month-end conversation into one workspace.</h2></div>
          <div className="landing-cta-action"><p>See how the product fits your close, review, and reporting workflow before you commit to a rollout.</p><Link className="landing-button landing-button--primary" href="/contact">Request a demo <ArrowIcon /></Link></div>
        </section>

        <MarketingFooter />
      </div>
    </main>
  );
}
