import { NextResponse } from "next/server";

import { loadDashboardSummary } from "../../../lib/dashboard";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const summary = await loadDashboardSummary();
  const status = summary.state === "ready" || summary.state === "signed_out" ? 200 : 503;

  return NextResponse.json(
    { data: summary },
    { status, headers: { "Cache-Control": "no-store" } },
  );
}
