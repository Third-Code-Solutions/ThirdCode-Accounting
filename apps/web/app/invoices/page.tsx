import { AppShell } from "../../components/app-shell";
import { SectionPage } from "../../components/section-page";

export default function InvoicesPage() {
  return <AppShell><SectionPage eyebrow="Receivables" title="Invoices" description="Create customer invoices, follow payment status, and keep every decision reviewable." actionLabel="Create invoice" actionHref="/invoices" /></AppShell>;
}
