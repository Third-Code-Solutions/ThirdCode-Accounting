import { ArrowLeft, BarChart3, Building2, Inbox, ReceiptText, Users } from "lucide-react";
import Link from "next/link";

import type { PlatformOwnerSummary } from "../lib/platform-owner";

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-PH", { style: "currency", currency: "PHP", maximumFractionDigits: 2 }).format(value);
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-PH", { dateStyle: "medium" }).format(new Date(value));
}

function OwnerBrand() {
  return <Link className="owner-brand" href="/" aria-label="Back to TCSI Accounting home"><span className="brand-mark">T</span><span><strong>TC<span>SI</span></strong><small>Platform console</small></span></Link>;
}

export function PlatformOwnerView({ summary }: Readonly<{ summary: PlatformOwnerSummary }>) {
  if (summary.state !== "ready" || !summary.analytics) {
    return (
      <main className="owner-page owner-page--state">
        <div className="owner-frame">
          <header className="owner-header"><OwnerBrand /><Link className="owner-back" href="/"><ArrowLeft aria-hidden="true" size={15} /> Back to TCSI home</Link></header>
          <section className="owner-state-card" aria-live="polite">
            <span className="owner-state-mark"><BarChart3 aria-hidden="true" size={24} /></span>
            <p className="landing-kicker">PLATFORM OWNER CONSOLE</p>
            <h1>{summary.state === "signed_out" ? "Sign in to the TCSI control plane." : "Restricted product analytics."}</h1>
            <p>{summary.message}</p>
            {summary.state === "signed_out" && <Link className="button button--primary" href="/login">Open secure sign in</Link>}
            {summary.state !== "signed_out" && <Link className="button button--quiet" href="/">Return to landing page</Link>}
          </section>
        </div>
      </main>
    );
  }

  const { analytics } = summary;
  return (
    <main className="owner-page">
      <div className="owner-frame">
        <header className="owner-header">
          <OwnerBrand />
          <div className="owner-header-actions"><span className="owner-mode"><i aria-hidden="true" /> Single platform owner</span><Link className="owner-back" href="/"><ArrowLeft aria-hidden="true" size={15} /> TCSI home</Link></div>
        </header>
        <section className="owner-intro" aria-labelledby="owner-title">
          <div><p className="landing-kicker">PRIVATE PRODUCT VIEW</p><h1 id="owner-title">Everything your product is carrying.</h1><p>Cross-tenant operating signals for the TCSI owner account. Customer organization owners remain scoped to their own workspaces.</p></div>
          <span className="owner-intro-note">{summary.message}</span>
        </section>
        <section className="owner-metrics" aria-label="Platform metrics">
          <article><span className="owner-metric-label"><Building2 aria-hidden="true" size={16} /> Organizations</span><strong>{analytics.workspace_count}</strong><small>Customer workspaces</small></article>
          <article><span className="owner-metric-label"><Users aria-hidden="true" size={16} /> Memberships</span><strong>{analytics.membership_count}</strong><small>Assigned user roles</small></article>
          <article><span className="owner-metric-label"><ReceiptText aria-hidden="true" size={16} /> Invoices</span><strong>{analytics.invoice_count}</strong><small>{formatCurrency(analytics.receivables_due)} receivables due</small></article>
          <article><span className="owner-metric-label"><Inbox aria-hidden="true" size={16} /> Demo requests</span><strong>{analytics.open_demo_request_count}</strong><small>{analytics.demo_request_count} total website requests</small></article>
        </section>
        <section className="owner-data-grid">
          <div className="owner-panel">
            <div className="owner-panel-heading"><div><p className="landing-kicker">TENANT VIEW</p><h2>Customer organizations</h2></div><span>{analytics.journal_entry_count} journal entries</span></div>
            {analytics.workspaces.length === 0 ? <p className="owner-empty">No customer workspaces have been created yet.</p> : <div className="owner-table-wrap"><table><thead><tr><th>Organization</th><th>Members</th><th>Invoices</th><th>Posted entries</th></tr></thead><tbody>{analytics.workspaces.map((workspace) => <tr key={workspace.id}><td><strong>{workspace.name}</strong><small>{workspace.slug} · since {formatDate(workspace.created_at)}</small></td><td>{workspace.member_count}</td><td>{workspace.invoice_count}</td><td>{workspace.posted_entry_count}</td></tr>)}</tbody></table></div>}
          </div>
          <div className="owner-panel">
            <div className="owner-panel-heading"><div><p className="landing-kicker">INTAKE</p><h2>Recent demo requests</h2></div><Link className="owner-panel-link" href="/contact">Open form <ArrowLeft aria-hidden="true" size={14} /></Link></div>
            {analytics.recent_demo_requests.length === 0 ? <p className="owner-empty">No demo requests yet. New requests will appear here.</p> : <ul className="owner-request-list">{analytics.recent_demo_requests.map((request) => <li key={request.id}><div><strong>{request.company_name}</strong><span>{request.contact_name} · {request.email}</span></div><time dateTime={request.created_at}>{formatDate(request.created_at)}</time></li>)}</ul>}
          </div>
        </section>
        <footer className="owner-footer"><span>Platform owner access is separate from customer organization ownership.</span><Link href="/controls">Review the access model <ArrowLeft aria-hidden="true" size={14} /></Link></footer>
      </div>
    </main>
  );
}
