import { AppShell } from "../../components/app-shell";
import { SectionPage } from "../../components/section-page";

export default function TransactionsPage() {
  return <AppShell><SectionPage eyebrow="Ledger" title="Transactions" description="Review, prepare, and post balanced entries with a clear audit trail." actionLabel="New entry" actionHref="/transactions" /></AppShell>;
}
