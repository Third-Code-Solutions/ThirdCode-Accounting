import { AppShell } from "../../components/app-shell";
import { SectionPage } from "../../components/section-page";

export default function ReportsPage() {
  return <AppShell><SectionPage eyebrow="Insight" title="Reports" description="Turn posted activity into focused financial views your team can trust." actionLabel="Explore reports" actionHref="/reports" /></AppShell>;
}
