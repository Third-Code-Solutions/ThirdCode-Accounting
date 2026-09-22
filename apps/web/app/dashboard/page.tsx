import { loadDashboardSummary } from "../../lib/dashboard";
import { AppShell } from "../../components/app-shell";
import { DashboardView } from "../../components/dashboard-view";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const summary = await loadDashboardSummary();

  return (
    <AppShell>
      <DashboardView summary={summary} />
    </AppShell>
  );
}
