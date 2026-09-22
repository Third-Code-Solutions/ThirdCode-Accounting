import { NextResponse } from "next/server";

import { loadPlatformOwnerSummary } from "../../../../lib/platform-owner";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const summary = await loadPlatformOwnerSummary();
  const status = summary.state === "ready" ? 200 : summary.state === "signed_out" ? 401 : summary.state === "forbidden" ? 403 : 503;

  return NextResponse.json(
    { data: summary.analytics, state: summary.state, message: summary.message },
    { status, headers: { "Cache-Control": "private, no-store" } },
  );
}
