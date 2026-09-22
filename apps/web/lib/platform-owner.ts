import { platformAnalyticsSchema, type PlatformAnalytics } from "@tcsi/contracts";

import { getPublicEnv } from "./env";
import { getSupabaseServerClient } from "./supabase/server";

export type PlatformOwnerState = "ready" | "configuration_required" | "signed_out" | "forbidden" | "unavailable";

export type PlatformOwnerSummary = {
  state: PlatformOwnerState;
  analytics: PlatformAnalytics | null;
  message: string;
};

export async function loadPlatformOwnerSummary(): Promise<PlatformOwnerSummary> {
  const env = getPublicEnv();
  if (!env.supabaseConfigured) {
    return { state: "configuration_required", analytics: null, message: "Connect the TCSI data workspace to activate the platform console." };
  }

  const supabase = await getSupabaseServerClient();
  if (!supabase) {
    return { state: "configuration_required", analytics: null, message: "The platform data workspace is not configured for this environment." };
  }

  const { data: userData, error: userError } = await supabase.auth.getUser();
  if (userError) {
    return { state: "unavailable", analytics: null, message: "We could not verify this session. Please sign in again." };
  }
  if (!userData.user) {
    return { state: "signed_out", analytics: null, message: "Sign in with the TCSI platform-owner account to continue." };
  }

  const { data, error } = await supabase.rpc("get_platform_analytics");
  if (error) {
    if (error.code === "42501" || /not authorized|platform owner/i.test(error.message)) {
      return { state: "forbidden", analytics: null, message: "This console is reserved for the TCSI platform owner." };
    }
    return { state: "unavailable", analytics: null, message: "Platform analytics are temporarily unavailable." };
  }

  const parsed = platformAnalyticsSchema.safeParse(data);
  if (!parsed.success) {
    return { state: "unavailable", analytics: null, message: "Platform analytics returned an invalid response." };
  }

  return { state: "ready", analytics: parsed.data, message: "Cross-tenant product view" };
}
