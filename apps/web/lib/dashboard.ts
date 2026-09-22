import type { DashboardSummary } from "@tcsi/contracts";

import { getPublicEnv } from "./env";
import { getSupabaseServerClient } from "./supabase/server";

type WorkspaceMembership = {
  workspace_id: string;
  role: string;
  workspace: { name: string; slug: string } | null;
};

type InvoiceRow = {
  id: string;
  invoice_number: string;
  status: string;
  balance_due: string | number;
  created_at: string;
};

function currency(value: number): string {
  return new Intl.NumberFormat("en-PH", {
    style: "currency",
    currency: "PHP",
    maximumFractionDigits: 2,
  }).format(value);
}

function setupSummary(message: string): DashboardSummary {
  return {
    state: "configuration_required",
    workspaceName: null,
    workspaceSlug: null,
    metrics: [],
    activity: [],
    message,
  };
}

export async function loadDashboardSummary(): Promise<DashboardSummary> {
  const env = getPublicEnv();
  if (!env.supabaseConfigured) {
    return setupSummary(
      "Connect Supabase Auth and the TCSI data workspace to activate live accounting data.",
    );
  }

  const supabase = await getSupabaseServerClient();
  if (!supabase) {
    return setupSummary("The data workspace is not configured for this environment.");
  }

  const {
    data: { user },
    error: userError,
  } = await supabase.auth.getUser();

  if (userError) {
    return {
      ...setupSummary("We could not verify the current session. Please sign in again."),
      state: "unavailable",
    };
  }

  if (!user) {
    return {
      ...setupSummary("Sign in to open your TCSI workspace."),
      state: "signed_out",
    };
  }

  const { data: membership, error: membershipError } = await supabase
    .from("workspace_members")
    .select("workspace_id, role, workspace:workspaces(name, slug)")
    .eq("user_id", user.id)
    .limit(1)
    .maybeSingle<WorkspaceMembership>();

  if (membershipError) {
    return {
      ...setupSummary("Your workspace could not be loaded. Check the data service logs."),
      state: "unavailable",
    };
  }

  if (!membership?.workspace) {
    return {
      ...setupSummary("Your account is ready, but it is not assigned to a workspace yet."),
      state: "no_access",
    };
  }

  const workspaceId = membership.workspace_id;
  const [accounts, invoices, periods, entries, activity] = await Promise.all([
    supabase
      .from("accounts")
      .select("id", { count: "exact", head: true })
      .eq("workspace_id", workspaceId),
    supabase
      .from("invoices")
      .select("id, invoice_number, status, balance_due, created_at")
      .eq("workspace_id", workspaceId)
      .neq("status", "void")
      .order("created_at", { ascending: false })
      .limit(50),
    supabase
      .from("accounting_periods")
      .select("id", { count: "exact", head: true })
      .eq("workspace_id", workspaceId)
      .eq("status", "open"),
    supabase
      .from("journal_entries")
      .select("id", { count: "exact", head: true })
      .eq("workspace_id", workspaceId)
      .eq("status", "draft"),
    supabase
      .from("invoices")
      .select("id, invoice_number, status, balance_due, created_at")
      .eq("workspace_id", workspaceId)
      .order("created_at", { ascending: false })
      .limit(4),
  ]);

  const queryError = [accounts.error, invoices.error, periods.error, entries.error, activity.error].find(
    Boolean,
  );
  if (queryError) {
    return {
      ...setupSummary("Live workspace data is temporarily unavailable."),
      state: "unavailable",
    };
  }

  const invoiceRows = (invoices.data ?? []) as InvoiceRow[];
  const outstanding = invoiceRows.reduce((sum, invoice) => {
    const balance = Number(invoice.balance_due);
    return Number.isFinite(balance) ? sum + balance : sum;
  }, 0);
  const draftCount = entries.count ?? 0;
  const activities = ((activity.data ?? []) as InvoiceRow[]).map((invoice) => ({
    id: invoice.id,
    title: `Invoice ${invoice.invoice_number}`,
    detail: `${invoice.status.replaceAll("_", " ")} · ${currency(Number(invoice.balance_due) || 0)} due`,
    timestamp: invoice.created_at,
    tone: invoice.status === "paid" ? ("positive" as const) : ("accent" as const),
  }));

  return {
    state: "ready",
    workspaceName: membership.workspace.name,
    workspaceSlug: membership.workspace.slug,
    message: `Live data for ${membership.workspace.name}`,
    metrics: [
      {
        label: "Active accounts",
        value: String(accounts.count ?? 0),
        helper: "Chart of accounts",
        tone: "neutral",
      },
      {
        label: "Open receivables",
        value: currency(outstanding),
        helper: "Outstanding invoice balances",
        tone: outstanding > 0 ? "attention" : "positive",
      },
      {
        label: "Draft entries",
        value: String(draftCount),
        helper: draftCount > 0 ? "Review before posting" : "Ledger is clear",
        tone: draftCount > 0 ? "attention" : "positive",
      },
      {
        label: "Open periods",
        value: String(periods.count ?? 0),
        helper: "Available for posting",
        tone: "accent",
      },
    ],
    activity: activities,
  };
}
