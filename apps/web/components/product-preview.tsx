"use client";

import { ArrowDownLeft, ArrowUpRight, BarChart3, BookOpen, Check, ChevronDown, CircleHelp, FileText, LayoutDashboard, Search, ShieldCheck, Wallet } from "lucide-react";
import { useState, type KeyboardEvent } from "react";
import { TCSIMark } from "./tcsi-mark";

const views = ["Overview", "Invoicing", "Reporting"] as const;
type View = typeof views[number];

function CashChart() {
  return (
    <div className="showcase-chart" role="img" aria-label="Illustrative cash movement chart from April to September. Income and expenses are sample values.">
      <div className="showcase-chart-labels"><span>₱300k</span><span>₱200k</span><span>₱100k</span><span>₱0</span></div>
      <div className="showcase-plot">
        <svg viewBox="0 0 640 180" fill="none" preserveAspectRatio="none" aria-hidden="true">
          <path className="showcase-grid-line" d="M0 10H640M0 60H640M0 110H640M0 160H640" />
          <path className="showcase-chart-fill" d="M0 130C45 130 55 94 100 104S166 114 210 76S264 98 316 59S364 83 418 39S475 71 526 32S580 42 640 10V170H0Z" />
          <path className="showcase-chart-income" d="M0 130C45 130 55 94 100 104S166 114 210 76S264 98 316 59S364 83 418 39S475 71 526 32S580 42 640 10" />
          <path className="showcase-chart-expense" d="M0 152C50 148 56 130 100 139S160 113 210 125S268 91 316 109S365 83 418 95S478 68 526 82S590 65 640 63" />
        </svg>
        <div className="showcase-months">{["Apr", "May", "Jun", "Jul", "Aug", "Sep"].map(month => <span key={month}>{month}</span>)}</div>
      </div>
    </div>
  );
}

function OverviewPreview() {
  return (
    <>
      <div className="showcase-metrics">
        <div><span>Cash & bank <Wallet size={15} /></span><strong>₱842,500<span>.00</span></strong><small>Across your cash accounts</small></div>
        <div><span>Receivables <ArrowDownLeft size={15} /></span><strong>₱186,200<span>.00</span></strong><small><b className="showcase-status-dot" />12 open invoices</small></div>
        <div><span>Payables <ArrowUpRight size={15} /></span><strong>₱94,800<span>.00</span></strong><small>8 bills to follow up</small></div>
      </div>
      <div className="showcase-panels">
        <section className="showcase-cash" aria-label="Sample cash movement">
          <div className="showcase-panel-title"><strong>Cash movement</strong><span><i /> Income <i /> Expenses</span></div>
          <CashChart />
        </section>
        <section className="showcase-attention" aria-label="Sample work to review">
          <div className="showcase-panel-title"><strong>Needs your attention</strong><span>03</span></div>
          <div><span className="showcase-task-icon"><FileText size={16} /></span><p><strong>Invoice review</strong><small>3 drafts ready to review</small></p><ArrowUpRight size={14} /></div>
          <div><span className="showcase-task-icon"><Wallet size={16} /></span><p><strong>Bank reconciliation</strong><small>2 statements to match</small></p><ArrowUpRight size={14} /></div>
          <div><span className="showcase-task-icon"><BookOpen size={16} /></span><p><strong>Recurring journals</strong><small>Review upcoming entries</small></p><ArrowUpRight size={14} /></div>
          <span className="showcase-review-note"><ShieldCheck size={13} /> Your role. Your company. Your work.</span>
        </section>
      </div>
    </>
  );
}

function InvoicingPreview() {
  return (
    <section className="showcase-invoices" aria-label="Sample invoice register">
      <div className="showcase-panel-title"><strong>Customer invoices</strong><span>Illustrative records</span></div>
      <div className="showcase-table-wrap"><table><caption className="sr-only">Fictional invoice examples showing document, customer, status and balance due</caption>
        <thead><tr><th>Invoice</th><th>Customer</th><th>Status</th><th>Balance due</th></tr></thead>
        <tbody>{[
          ["INV / 0048", "Example Trading Co.", "Posted", "₱48,000.00"],
          ["INV / 0047", "Sample Services Ltd.", "Partially paid", "₱32,500.00"],
          ["INV / 0046", "Demo Supply Co.", "Draft", "₱24,800.00"],
          ["INV / 0045", "Example Trading Co.", "Paid", "₱0.00"],
        ].map(([invoice, customer, status, amount]) => <tr key={invoice}><td>{invoice}</td><td>{customer}</td><td><span className={`showcase-invoice-status${status === "Paid" ? " is-paid" : ""}`}>{status}</span></td><td>{amount}</td></tr>)}</tbody>
      </table></div>
      <p className="showcase-explainer"><Check size={16} /> Follow each invoice from draft through posting and settlement.</p>
    </section>
  );
}

function ReportingPreview() {
  return (
    <section className="showcase-reports" aria-label="Sample reporting workspace">
      <div className="showcase-statement"><div className="showcase-panel-title"><strong>Profit & loss</strong><span>Sample period</span></div><p>September · Example company</p>
        <dl><div><dt>Revenue</dt><dd>₱428,000.00</dd></div><div><dt>Cost of revenue</dt><dd>₱196,000.00</dd></div><div><dt>Gross profit</dt><dd>₱232,000.00</dd></div><div><dt>Operating expenses</dt><dd>₱84,000.00</dd></div><div className="showcase-total"><dt>Net result</dt><dd>₱148,000.00</dd></div></dl>
      </div>
      <div className="showcase-report-list"><strong>From overview to detail</strong>{["Balance sheet", "Cash flow statement", "Trial balance", "General ledger", "Customer & supplier ageing"].map(label => <div key={label}><FileText size={16} /><span>{label}</span><ArrowUpRight size={14} /></div>)}<small>Review by company and period. Export for your next conversation.</small></div>
    </section>
  );
}

export function ProductPreview() {
  const [view, setView] = useState<View>("Overview");

  function moveTab(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next: number;
    if (event.key === "ArrowRight") next = (index + 1) % views.length;
    else if (event.key === "ArrowLeft") next = (index + views.length - 1) % views.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = views.length - 1;
    else return;
    event.preventDefault();
    setView(views[next]);
    document.getElementById(`preview-tab-${views[next]}`)?.focus();
  }

  return (
    <div className="product-showcase" id="product-preview">
      <div className="showcase-selector"><span>TAKE A CLOSER LOOK</span><div role="tablist" aria-label="Product preview">{views.map((label, index) => <button type="button" role="tab" key={label} id={`preview-tab-${label}`} aria-selected={view === label} aria-controls="preview-panel" tabIndex={view === label ? 0 : -1} onClick={() => setView(label)} onKeyDown={event => moveTab(event, index)}>{label}</button>)}</div><span className="showcase-sample-label">Illustrative workspace · Sample data</span></div>
      <div className="showcase-window" role="tabpanel" id="preview-panel" aria-labelledby={`preview-tab-${view}`} tabIndex={0}>
        <aside className="showcase-sidebar" aria-label="Illustrative workspace sidebar">
          <div className="showcase-logo"><TCSIMark compact /><strong>TCSI <small>ACCOUNTING</small></strong></div>
          <div className="showcase-company"><span>EX</span><div>Example company<small>Finance workspace</small></div><ChevronDown size={12} /></div>
          <span className="showcase-sidebar-label">WORKSPACE</span>
          {[{ label: "Overview", icon: LayoutDashboard }, { label: "Revenue", icon: FileText }, { label: "Purchases", icon: Wallet }, { label: "Banking", icon: BookOpen }, { label: "Reporting", icon: BarChart3 }, { label: "Controls", icon: ShieldCheck }].map(({ label, icon: Icon }) => <span className={`showcase-nav-item${label === (view === "Invoicing" ? "Revenue" : view) ? " is-active" : ""}`} key={label}><Icon size={16} />{label}</span>)}
          <div className="showcase-sidebar-bottom"><CircleHelp size={15} /><span>A connected financial day.</span></div>
        </aside>
        <div className="showcase-workspace"><div className="showcase-toolbar"><span>Workspace <span>/</span> {view}</span><span><Search size={15} /><span className="showcase-avatar">JD</span></span></div>
          <div className="showcase-content"><div className="showcase-heading"><div><span>YOUR FINANCES, IN FOCUS</span><h2>{view === "Overview" ? "Finance overview" : view === "Invoicing" ? "Revenue, without the loose ends." : "The story behind your numbers."}</h2></div><span className="showcase-period">September <ChevronDown size={12} /></span></div>
            {view === "Overview" ? <OverviewPreview /> : view === "Invoicing" ? <InvoicingPreview /> : <ReportingPreview />}
          </div>
        </div>
      </div>
      <div className="showcase-caption"><span><ShieldCheck size={14} /> Connected records. Clear responsibilities.</span><span>Explore the real workflows in your demo <ArrowUpRight size={13} /></span></div>
    </div>
  );
}
