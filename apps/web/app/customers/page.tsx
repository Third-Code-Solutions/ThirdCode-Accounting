import { AppShell } from "../../components/app-shell";
import { SectionPage } from "../../components/section-page";

export default function CustomersPage() {
  return <AppShell><SectionPage eyebrow="Directory" title="Customers" description="Keep customer details, tax identifiers, and account history together in one place." actionLabel="Add customer" actionHref="/customers" /></AppShell>;
}
