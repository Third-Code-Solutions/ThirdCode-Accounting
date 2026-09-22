"use client";

import { createBrowserClient } from "@supabase/ssr";

import { getPublicEnv } from "../env";

export function getSupabaseBrowserClient() {
  const env = getPublicEnv();
  if (!env.supabaseConfigured) {
    return null;
  }

  return createBrowserClient(
    env.NEXT_PUBLIC_SUPABASE_URL!,
    env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}
