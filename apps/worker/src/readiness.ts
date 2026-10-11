import type { SupabaseClient } from "@supabase/supabase-js";

/** This service has no released job handlers; never advertise scheduling readiness. */
export async function workerReadiness(supabase: SupabaseClient | null) {
  if (!supabase) {
    return { status: "configuration_required", checks: { supabase: false, scheduler: false } };
  }
  try {
    const { error } = await supabase.from("job_runs").select("id").limit(1)
      .abortSignal(AbortSignal.timeout(2500)).retry(false);
    if (!error) {
      return { status: "scheduler_disabled", checks: { supabase: true, scheduler: false } };
    }
  } catch {
    // Transport failures and revoked credentials both make this instance unavailable.
  }
  return { status: "dependency_unavailable", checks: { supabase: false, scheduler: false } };
}
