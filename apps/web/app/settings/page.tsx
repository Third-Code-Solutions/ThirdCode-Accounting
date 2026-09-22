import { AppShell } from "../../components/app-shell";
import { SectionPage } from "../../components/section-page";

export default function SettingsPage() {
  return <AppShell><SectionPage eyebrow="Control plane" title="Workspace settings" description="Configure identity, roles, accounting preferences, and integrations for your TCSI workspace." actionLabel="Start setup" actionHref="/settings" /></AppShell>;
}
