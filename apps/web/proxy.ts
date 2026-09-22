import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

import { getPublicEnv } from "./lib/env";
import { isPilotPortal } from "./lib/pilot";

export async function proxy(request: NextRequest) {
  // The hosted portal must not expose the unfinished standalone ledger.
  if (isPilotPortal()) {
    if (request.nextUrl.pathname === "/") return NextResponse.next();
    if (request.nextUrl.pathname.startsWith("/api/")) {
      return NextResponse.json({ error: "Standalone accounting is not released" }, { status: 404 });
    }
    return NextResponse.redirect(new URL("/", request.url));
  }
  const env = getPublicEnv();
  if (!env.supabaseConfigured) {
    return NextResponse.next();
  }

  let response = NextResponse.next({ request });
  const supabase = createServerClient(
    env.NEXT_PUBLIC_SUPABASE_URL!,
    env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
        },
      },
    },
  );

  await supabase.auth.getUser();
  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api/health|api/readiness).*)"],
};
