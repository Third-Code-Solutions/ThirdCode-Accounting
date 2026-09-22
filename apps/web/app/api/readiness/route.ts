import { NextResponse } from "next/server";

import { getPublicEnv } from "../../../lib/env";
import { isPilotPortal } from "../../../lib/pilot";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const env = getPublicEnv();
  let reachable = false;
  if (env.supabaseConfigured) {
    try {
      const response = await fetch(`${env.NEXT_PUBLIC_SUPABASE_URL}/auth/v1/settings`, {
        headers: { apikey: env.NEXT_PUBLIC_SUPABASE_ANON_KEY! },
        cache: "no-store", signal: AbortSignal.timeout(5000),
      });
      reachable = response.ok;
    } catch {
      reachable = false;
    }
  }
  const body = {
    status: reachable ? "ready" : "dependency_unavailable",
    service: "tcsi-web",
    mode: isPilotPortal() ? "pilot_portal" : "standalone_preview",
    checks: { supabaseAuth: reachable },
  };

  return NextResponse.json(body, {
    status: reachable ? 200 : 503,
    headers: { "Cache-Control": "no-store" },
  });
}
