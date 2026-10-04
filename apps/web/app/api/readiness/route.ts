import { NextResponse } from "next/server";

import { getPublicEnv } from "../../../lib/env";
import { isPilotPortal } from "../../../lib/pilot";
import { accountingOrigin } from "../../../lib/accounting-routes";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Probes must not hold the endpoint open; both dependencies are checked together. */
const probeTimeoutMs = 2500;

async function reachable(url: string, init: RequestInit): Promise<boolean> {
  try {
    const response = await fetch(url, {
      ...init,
      cache: "no-store",
      signal: AbortSignal.timeout(probeTimeoutMs),
    });
    return response.ok;
  } catch {
    return false;
  }
}

export async function GET() {
  const env = getPublicEnv();
  const pilotPortal = isPilotPortal();
  const [supabaseAuth, accountingEngine] = await Promise.all([
    env.supabaseConfigured
      ? reachable(`${env.NEXT_PUBLIC_SUPABASE_URL}/auth/v1/settings`, {
          headers: { apikey: env.NEXT_PUBLIC_SUPABASE_ANON_KEY! },
        })
      : Promise.resolve(false),
    pilotPortal
      ? reachable(`${accountingOrigin}/web/login`, { redirect: "manual" })
      : Promise.resolve(null),
  ]);

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
