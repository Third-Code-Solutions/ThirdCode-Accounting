import { createServerClient } from "@supabase/ssr";
import { type EmailOtpType } from "@supabase/supabase-js";
import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";

import { getPublicEnv } from "../../../lib/env";

/**
 * Consumes `{{ .TokenHash }}` email links (recovery, invite) server-side.
 * This is the flow that works from any device: the one-time token hash is
 * verified here, the session cookies are set on the redirect response, and
 * the user finishes on /login in the set-a-new-password screen.
 */
export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const tokenHash = searchParams.get("token_hash");
  const type = searchParams.get("type") as EmailOtpType | null;
  const next = searchParams.get("next") ?? "";
  const invalid = new URL("/login", origin);
  invalid.searchParams.set("state", "link_invalid");

  if (!tokenHash || !type) {
    return NextResponse.redirect(invalid);
  }

  const env = getPublicEnv();
  if (!env.supabaseConfigured) {
    return NextResponse.redirect(invalid);
  }

  const cookieStore = await cookies();
  const pendingCookies: { name: string; value: string; options?: Record<string, unknown> }[] = [];
  const supabase = createServerClient(
    env.NEXT_PUBLIC_SUPABASE_URL!,
    env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach((cookie) => pendingCookies.push(cookie));
        },
      },
    },
  );

  const { error } = await supabase.auth.verifyOtp({ type, token_hash: tokenHash });
  const target =
    error ? invalid
      : type === "recovery" || type === "invite" ? new URL("/login?mode=update", origin)
        : next.startsWith("/") ? new URL(next, origin) : new URL("/", origin);

  const response = NextResponse.redirect(target);
  pendingCookies.forEach(({ name, value, options }) => {
    response.cookies.set(name, value, options as Parameters<typeof response.cookies.set>[2]);
  });
  return response;
}
