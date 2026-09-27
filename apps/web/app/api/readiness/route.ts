import { NextResponse } from "next/server";

import { getPublicEnv } from "../../../lib/env";
import { isPilotPortal } from "../../../lib/pilot";
import { accountingOrigin } from "../../../lib/accounting-routes";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const env = getPublicEnv();
  const pilotPortal = isPilotPortal();
  const supabaseAuth = env.supabaseConfigured ? await (async () => {
    try {
      const response = await fetch(`${env.NEXT_PUBLIC_SUPABASE_URL}/auth/v1/settings`, {
        headers: { apikey: env.NEXT_PUBLIC_SUPABASE_ANON_KEY! },
        cache: "no-store", signal: AbortSignal.timeout(5000),
      });
      return response.ok;
    } catch {
      return false;
    }
  })() : false;
  const accountingEngine = pilotPortal ? await (async () => {
    try {
      const response = await fetch(`${accountingOrigin}/web/login`, {
        cache: "no-store", redirect: "manual", signal: AbortSignal.timeout(5000),
      });
      return response.ok;
    } catch {
      return false;
    }
  })() : null;
  const ready = supabaseAuth && (!pilotPortal || accountingEngine === true);
  const body = {
    status: ready ? "ready" : "dependency_unavailable",
    service: "tcsi-web",
    mode: pilotPortal ? "pilot_portal" : "standalone_preview",
    checks: { supabaseAuth, accountingEngine },
  };

  return NextResponse.json(body, {
    status: ready ? 200 : 503,
    headers: { "Cache-Control": "no-store" },
  });
}
