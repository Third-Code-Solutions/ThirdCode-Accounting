import {
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  FilePlus2,
  Import,
  Plus,
  Sparkles,
  WalletCards,
} from "lucide-react";
import Link from "next/link";

import type { DashboardSummary } from "@tcsi/contracts";

function formatActivityTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "Recently";
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(date);
}

function StatePanel({ summary }: { summary: DashboardSummary }) {
  if (summary.state === "ready") return null;

  const signedOut = summary.state === "signed_out";
  const noAccess = summary.state === "no_access";
  const unavailable = summary.state === "unavailable";

  return (
    <section className="setup-panel" aria-live="polite">
      <div className="setup-icon">
        {unavailable || noAccess ? <CircleAlert size={22} /> : <Sparkles size={22} />}
      </div>
      <div className="setup-copy">
        <span className="eyebrow">{signedOut ? "Secure access" : noAccess ? "Workspace access" : "One step to go"}</span>
        <h2>
          {signedOut
            ? "Sign in to see your live numbers"
            : noAccess
              ? "Your workspace invitation is pending"
              : unavailable
                ? "The data service needs attention"
                : "Connect your data workspace"}
        </h2>
        <p>{summary.message}</p>
      </div>
      <div className="setup-actions">
        {signedOut ? (
          <Link className="button button--primary" href="/login">Sign in</Link>
        ) : noAccess ? (
          <Link className="button button--quiet" href="/settings">View settings</Link>
        ) : unavailable ? (
          <Link className="button button--quiet" href="/dashboard">Try again</Link>
        ) : (
          <Link className="button button--primary" href="/settings">Open setup</Link>
        )}
      </div>
    </section>
  );
}

export function DashboardView({ summary }: { summary: DashboardSummary }) {
  const hasLiveData = summary.state === "ready";
  const hasActivity = summary.activity.length > 0;

  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <span className="eyebrow">Overview</span>
          <h1>Command center</h1>
          <p>Keep your books clear, your cash visible, and your next action obvious.</p>
        </div>
        <div className="heading-actions">
          <Link className="button button--quiet" href="/transactions">
            <FilePlus2 aria-hidden="true" size={16} />
            New entry
          </Link>
          <Link className="button button--primary" href="/invoices">
            <Plus aria-hidden="true" size={17} />
            Create invoice
          </Link>
        </div>
      </div>

      <StatePanel summary={summary} />

      <section className="metric-grid" aria-label="Workspace summary">
        {(hasLiveData ? summary.metrics : [
          { label: "Cash position", value: "—", helper: "Connect a workspace", tone: "neutral" as const },
          { label: "Receivables", value: "—", helper: "Live data will appear here", tone: "accent" as const },
          { label: "Draft entries", value: "—", helper: "Nothing is simulated", tone: "neutral" as const },
          { label: "Open periods", value: "—", helper: "Awaiting connection", tone: "neutral" as const },
        ]).map((metric) => (
          <article className="metric-card" key={metric.label}>
            <div className="metric-card-topline">
              <span>{metric.label}</span>
              <span className={`metric-indicator metric-indicator--${metric.tone}`} aria-hidden="true" />
            </div>
            <strong>{metric.value}</strong>
            <span className="metric-helper">{metric.helper}</span>
          </article>
        ))}
      </section>

      <div className="dashboard-grid">
        <section className="panel chart-panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Cash movement</span>
              <h2>Financial pulse</h2>
            </div>
            <button className="select-control" type="button" disabled={!hasLiveData}>
              Last 30 days <ChevronRight aria-hidden="true" size={14} />
            </button>
          </div>
          <div className="chart-area" aria-label="Cash movement chart">
            <div className="chart-gridlines" aria-hidden="true">
              <span /><span /><span /><span />
            </div>
            {hasLiveData ? (
              <svg className="line-chart" viewBox="0 0 800 220" role="img" aria-label="Cash movement trend">
                <defs>
                  <linearGradient id="pulse-fill" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stopColor="#6b4eff" stopOpacity="0.22" />
                    <stop offset="100%" stopColor="#6b4eff" stopOpacity="0" />
                  </linearGradient>
                </defs>
                <path d="M0,168 C72,150 78,178 136,144 S228,120 276,142 S362,106 420,126 S500,78 566,112 S664,86 800,42 V220 H0 Z" fill="url(#pulse-fill)" />
                <path d="M0,168 C72,150 78,178 136,144 S228,120 276,142 S362,106 420,126 S500,78 566,112 S664,86 800,42" fill="none" stroke="#765cff" strokeWidth="3" vectorEffect="non-scaling-stroke" />
              </svg>
            ) : (
              <div className="chart-empty">
                <WalletCards aria-hidden="true" size={24} />
                <strong>Your first posting will appear here</strong>
                <span>Connect a live workspace to see cash movement over time.</span>
              </div>
            )}
            <div className="chart-axis" aria-hidden="true"><span>Start</span><span>Midpoint</span><span>Today</span></div>
          </div>
        </section>

        <section className="panel activity-panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Recent activity</span>
              <h2>Keep the momentum</h2>
            </div>
            <Link className="panel-link" href="/invoices">View all <ChevronRight aria-hidden="true" size={14} /></Link>
          </div>
          {hasActivity ? (
            <div className="activity-list">
              {summary.activity.map((item) => (
                <div className="activity-row" key={item.id}>
                  <span className={`activity-icon activity-icon--${item.tone}`} aria-hidden="true"><ReceiptIcon /></span>
                  <div className="activity-copy"><strong>{item.title}</strong><span>{item.detail}</span></div>
                  <time dateTime={item.timestamp}>{formatActivityTime(item.timestamp)}</time>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state empty-state--compact">
              <CheckCircle2 aria-hidden="true" size={22} />
              <strong>No activity yet</strong>
              <span>Once invoices and entries move through your workspace, the latest updates will show here.</span>
              <Link className="text-link" href="/invoices">Create your first invoice <ArrowUpRight aria-hidden="true" size={14} /></Link>
            </div>
          )}
        </section>
      </div>

      <section className="quick-start panel">
        <div className="quick-start-mark"><Import aria-hidden="true" size={21} /></div>
        <div>
          <span className="eyebrow">Recommended next step</span>
          <h2>Bring your workspace to life</h2>
          <p>Start with your chart of accounts, then add customers and your first invoice. TCSI keeps each step reviewable.</p>
        </div>
        <Link className="button button--quiet" href="/settings">Review setup <ChevronRight aria-hidden="true" size={15} /></Link>
      </section>
    </div>
  );
}

function ReceiptIcon() {
  return <FilePlus2 aria-hidden="true" size={17} />;
}
