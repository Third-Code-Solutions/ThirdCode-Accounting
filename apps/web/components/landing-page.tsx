import Link from "next/link";
import { ArrowRight, ArrowUpRight, BookOpen, Building2, CalendarClock, Check, ChevronDown, CircleCheck, FileChartColumn, FileText, Fingerprint, FolderInput, Landmark, Layers3, Receipt, ShieldCheck, SlidersHorizontal, Terminal, Users, Wallet } from "lucide-react";

import { MarketingFooter, MarketingHeader } from "./marketing-layout";
import { ProductPreview } from "./product-preview";

const capabilities = [
  { icon: BookOpen, title: "General ledger", copy: "Your chart of accounts, journals, balanced entries, and source records. Connected from the start.", detail: "Accounts · Journals · Multi-currency" },
  { icon: FileText, title: "Invoicing & receivables", copy: "Prepare invoices and credit notes. Follow customer balances, collections, and statements of account.", detail: "Invoices · Credits · Customer statements" },
  { icon: Wallet, title: "Bills & payments", copy: "Keep supplier bills, payment batches, and receipt records together, with a clear settlement history.", detail: "Payables · Payment batches · Receipts" },
  { icon: Landmark, title: "Bank reconciliation", copy: "Match statement lines to accounting entries, review differences, and trace adjustments to their source.", detail: "Statements · Matching · Adjustments" },
  { icon: Receipt, title: "Expense management", copy: "Keep employee expenses, supporting documents, and review steps connected to your accounting work.", detail: "Expenses · Evidence · Review" },
  { icon: FileChartColumn, title: "Financial reporting", copy: "See profit and loss, balance sheet, cash flow, trial balance, general ledger, and ageing in context.", detail: "Financial statements · PDF & XLSX exports" },
  { icon: CalendarClock, title: "Recurring workflows", copy: "Set up recurring journals, invoices, and bills. Keep repeatable work on a defined schedule.", detail: "Schedules · Templates · Draft review" },
  { icon: SlidersHorizontal, title: "Tax & period controls", copy: "Configure tax profiles, review VAT and withholding summaries, and manage period and year-end close.", detail: "Tax profiles · Period locks · Year-end" },
  { icon: Users, title: "Company directory", copy: "Give customer, supplier, and product information a shared home, close to the documents that use it.", detail: "Customers · Suppliers · Products" },
  { icon: Building2, title: "Multi-company work", copy: "Move between your authorized companies while keeping records and access tied to the right business.", detail: "Company scope · Workspace switching" },
  { icon: Fingerprint, title: "Roles & audit history", copy: "Separate data entry, accounting, and oversight. Follow who changed a record and when.", detail: "Role permissions · Audit trail · Posting rules" },
  { icon: FolderInput, title: "Guided migration", copy: "Stage your source records in migration batches, validate mappings, and reconcile balances before cutover.", detail: "Import validation · Mapping · Reconciliation" },
];

const questions = [
  { question: "Who is TCSI Accounting built for?", answer: "Company finance teams that need a connected place for daily bookkeeping, customer and supplier activity, bank reconciliation, and financial reporting. The demo helps your finance lead and decision-makers evaluate the workflows against your own requirements." },
  { question: "Can we manage more than one company?", answer: "Yes. Authorized users can switch between their assigned companies. Records and actions remain subject to company scope and role permissions, so access can match each person’s responsibilities." },
  { question: "Can we bring our existing accounting data?", answer: "TCSI includes migration batches, mapping checks, and validation tools. Your rollout needs an agreed source export, opening balances, cutover date, and reconciliation with your finance team. We review those requirements with you before moving data." },
  { question: "Which reports can our team review?", answer: "The workspace includes profit and loss, balance sheet, cash flow, trial balance, general ledger, journal listing, customer and supplier ageing, statements of account, and tax summaries. Available exports include PDF and XLSX, depending on the report. Company-specific formats and tax classifications are reviewed during setup." },
  { question: "How do demos, pricing, and access work?", answer: "Request a demo with your company details and the workflows you want to see. We’ll discuss your team, companies, data, and rollout needs, then confirm scope and pricing with you. Workspace access is provided by invitation; requesting a demo does not create an accounting account." },
];

export function LandingPage() {
  return (
    <div className="landing marketing-home">
      <div className="landing-frame">
        <MarketingHeader />
        <main id="main-content">
          <section className="home-hero" aria-labelledby="landing-title">
            <p className="home-eyebrow"><span /> ACCOUNTING, WITH A CLEARER PERSPECTIVE</p>
            <h1 id="landing-title">Clarity for every<br /><span>financial decision.</span></h1>
            <p className="home-hero-lede">Bring your books, payments, and reporting into one connected workspace. Give your team the clarity to move business forward.</p>
            <div className="home-actions"><Link className="landing-button landing-button--primary" href="/contact">Request a demo <ArrowRight size={17} /></Link><a className="landing-button home-button-secondary" href="#platform">Explore the platform <ArrowRight size={17} /></a></div>
            <p className="home-hero-note"><Check size={14} /> A guided demo, built around your company.</p>
          </section>
          <ProductPreview />
          <div className="home-value-strip" aria-label="Platform foundations"><span>ONE WORKSPACE.<br /><strong>EVERY PART OF YOUR FINANCIAL DAY.</strong></span><p><Layers3 /> Connected accounting</p><p><ShieldCheck /> Clear controls</p><p><FileChartColumn /> Reporting with context</p></div>

          <section className="home-section home-platform" id="platform" aria-labelledby="capabilities-title">
            <div className="home-section-heading"><div><p className="home-eyebrow">THE CONNECTED PLATFORM</p><h2 id="capabilities-title">From the first entry.<br />To the bigger picture.</h2></div><p>The everyday essentials, connected with purpose. Follow the work from a source document to the financial conversation it informs.</p></div>
            <div className="home-capabilities">{capabilities.map(({ icon: Icon, title, copy, detail }) => <article key={title}><Icon size={24} strokeWidth={1.5} aria-hidden="true" /><h3>{title}</h3><p>{copy}</p><span>{detail}</span></article>)}</div>
          </section>

          <section className="home-control-section home-section" id="why-tcsi" aria-labelledby="control-title">
            <div className="home-control-copy"><p className="home-eyebrow">CONFIDENCE IS IN THE DETAILS</p><h2 id="control-title">Give your team freedom.<br /><span>Keep the right controls.</span></h2><p>Good accounting depends on clear responsibilities. TCSI keeps draft work, posting authority, and company access distinct, so every person knows their part.</p><ul><li><CircleCheck /> Role-based access for encoders, accountants, administrators, and viewers.</li><li><CircleCheck /> Protected posted records and period controls that support a disciplined close.</li><li><CircleCheck /> Audit history and source references that help explain the numbers.</li></ul><Link className="home-text-link" href="/controls">Explore accounting controls <ArrowRight size={16} /></Link></div>
            <div className="home-control-visual"><div className="control-visual-top"><span className="control-visual-icon"><ShieldCheck size={25} /></span><span>BUILT-IN ACCOUNTABILITY</span></div><h3>Clear at every step.</h3><p>From preparation to financial review.</p><ol>{[{ title: "Prepare", role: "Encoder", copy: "Capture records and save drafts." }, { title: "Review & post", role: "Accountant", copy: "Check entries and post authorized work." }, { title: "Oversee", role: "Administrator", copy: "Manage access and accounting controls." }].map((item, index) => <li key={item.title}><span>{String(index + 1).padStart(2, "0")}</span><div><h4>{item.title}<small>{item.role}</small></h4><p>{item.copy}</p></div></li>)}</ol><div className="control-visual-footer"><Fingerprint size={17} /><span>One record. A traceable history.</span></div></div>
          </section>

          <section className="home-orvexa" aria-labelledby="orvexa-title"><div className="home-orvexa-copy"><p className="home-eyebrow"><Terminal size={14} /> MEET ORVEXA</p><h2 id="orvexa-title">A direct line to<br />your accounting work.</h2><p>Read your finance summary, find invoices, surface overdue balances, or prepare an invoice draft with explicit commands. Orvexa works within your company access and permissions.</p><Link className="home-text-link" href="/contact">See Orvexa in your demo <ArrowUpRight size={16} /></Link></div><div className="orvexa-example"><div><span className="orvexa-monogram">O</span><strong>ORVEXA</strong><span>WORKSPACE ASSISTANT</span></div><code><span>&gt;</span> /overdue</code><p>Find posted customer invoices past their due date, within your authorized company.</p><div className="orvexa-boundaries"><Check size={14} /><span>Rule-based commands. Source-linked results.<br />Drafts require confirmation. Posting stays with your team.</span></div><small>Command example · No live accounting data</small></div></section>

          <section className="home-section home-rollout" id="rollout" aria-labelledby="rollout-title"><div className="home-section-heading"><div><p className="home-eyebrow">A THOUGHTFUL START</p><h2 id="rollout-title">Your business first.<br />Your rollout, with a plan.</h2></div><p>Start with a conversation about how your team works. Build the path to your workspace around the people, records, and reports that matter.</p></div><ol className="home-rollout-steps"><li><span>01</span><h3>See your workflow</h3><p>Walk through the product with your finance lead. Focus the demo on your daily work and month-end needs.</p></li><li><span>02</span><h3>Shape your setup</h3><p>Agree on companies, roles, accounts, tax settings, report formats, and any migration requirements.</p></li><li><span>03</span><h3>Validate, then begin</h3><p>Review opening balances and sample outputs with your team. Confirm access and readiness before rollout.</p></li></ol></section>

          <section className="home-faq home-section" aria-labelledby="faq-title"><div><p className="home-eyebrow">BEFORE WE TALK</p><h2 id="faq-title">Good questions.<br />Clear answers.</h2><p>Have a workflow in mind?<br /><Link className="home-text-link" href="/contact">Let’s talk it through <ArrowUpRight size={15} /></Link></p></div><div className="home-faq-list">{questions.map(({ question, answer }) => <details key={question}><summary>{question}<ChevronDown size={18} aria-hidden="true" /></summary><p>{answer}</p></details>)}</div></section>

          <section className="home-final-cta" aria-labelledby="demo-title"><span className="home-eyebrow">A CLEARER FINANCIAL DAY STARTS HERE</span><h2 id="demo-title">Let’s put your business<br />in perspective.</h2><p>See how TCSI Accounting fits your team, your processes, and your next stage of growth.</p><Link className="landing-button landing-button--primary" href="/contact">Request your company demo <ArrowRight size={17} /></Link><small>A focused conversation. A practical next step.</small></section>
        </main>
        <MarketingFooter />
      </div>
    </div>
  );
}
