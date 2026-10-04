"use client";

import { createBrowserClient } from "@supabase/ssr";

import { getPublicEnv } from "../env";

let browserClient: ReturnType<typeof createBrowserClient> | null = null;

export function getSupabaseBrowserClient() {
  const env = getPublicEnv();
  if (!env.supabaseConfigured) {
    return null;
  }

  // A single client per page: multiple GoTrueClient instances would both try
  // to consume one-time URL tokens (recovery links) and race each other.
  if (!browserClient) {
    browserClient = createBrowserClient(
      env.NEXT_PUBLIC_SUPABASE_URL!,
      env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    );
  }

  return browserClient;
}
