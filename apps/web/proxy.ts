import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

import { getPublicEnv } from "./lib/env";
import {
  isPilotPortal,
  isPublicPortalApi,
  isPublicPortalPage,
  isWithheldPortalPage,
} from "./lib/pilot";
import { isAccountingRoute } from "./lib/accounting-routes";

/** Next.js stamps this nonce onto the script tags it renders. */
export const nonceHeader = "x-nonce";

function supabaseConnectSources(): string[] {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  if (!url) return [];
  try {
    const { origin, host } = new URL(url);
    return [origin, `wss://${host}`];
  } catch {
    return [];
  }
}

/**
 * Portal CSP. `strict-dynamic` keeps the policy meaningful for injected
 * scripts while letting the framework load the chunks it is trusted with.
 * The accounting engine is served through a rewrite and keeps its own
 * headers, so it is deliberately excluded from this policy.
 */
export function contentSecurityPolicy(nonce: string): string {
  const directives = [
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "form-action 'self'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    "style-src 'self' 'unsafe-inline'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`,
    "manifest-src 'self'",
    "worker-src 'self' blob:",
  ];
  const connect = supabaseConnectSources();
  directives.push(connect.length ? `connect-src 'self' ${connect.join(" ")}` : "connect-src 'self'");
  return directives.join("; ");
}

export async function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const policy = contentSecurityPolicy(nonce);
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set(nonceHeader, nonce);
  requestHeaders.set("Content-Security-Policy", policy);

  /** Portal response carrying the nonce the page needs to render its scripts. */
  const portalResponse = () => {
    const response = NextResponse.next({ request: { headers: requestHeaders } });
    response.headers.set("Content-Security-Policy", policy);
    return response;
  };

  // The hosted portal must not expose the unfinished standalone ledger.
  if (isPilotPortal()) {
    // Engine traffic keeps its own headers, including the engine CSP-less shell.
    if (isAccountingRoute(request.nextUrl.pathname)) return NextResponse.next();
    if (isPublicPortalPage(request.nextUrl.pathname)) return portalResponse();
    if (request.nextUrl.pathname.startsWith("/api/")) {
      if (isPublicPortalApi(request.nextUrl.pathname)) return portalResponse();
      return NextResponse.json({ error: "Standalone accounting is not released" }, { status: 404 });
    }
    if (isWithheldPortalPage(request.nextUrl.pathname)) {
      return NextResponse.redirect(new URL("/", request.url));
    }
    // Anything else is not a page: fall through so Next answers 404.
    return portalResponse();
  }
  const env = getPublicEnv();
  if (!env.supabaseConfigured) {
    return portalResponse();
  }

  let response = portalResponse();
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
          response = portalResponse();
          cookiesToSet.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
        },
      },
    },
  );

  await supabase.auth.getUser();
  return response;
}

export const config = {
  // Engine requests go directly through CDN rewrites, avoiding middleware body
  // buffering for accounting attachments and preserving upgrade requests.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api/health|api/readiness|(?:web|workspace|odoo|mail|bus|websocket|report|account|payment|portal|my|digest|auth_totp|thirdcode_accounting|discuss|hr_expense|spreadsheet|website|web_editor|html_editor|base_setup)(?:/|$)|[a-zA-Z0-9_]+/static/|logo\\.png$).*)"],
};
