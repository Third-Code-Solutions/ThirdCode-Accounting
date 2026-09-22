import type { SupabaseClient } from "@supabase/supabase-js";

import { workerJobSchema, type WorkerJob } from "@tcsi/contracts";

type JobState = "running" | "succeeded" | "failed";

export function makeRunKey(jobName: string, scheduledFor: string): string {
  return `${jobName}:${scheduledFor}`;
}

export async function claimJob(
  supabase: SupabaseClient,
  input: WorkerJob,
): Promise<{ claimed: boolean; jobId: string | null }> {
  const job = workerJobSchema.parse(input);
  const { data, error } = await supabase
    .from("job_runs")
    .insert({
      job_name: job.jobName,
      run_key: job.runKey,
      workspace_id: job.workspaceId ?? null,
      status: "running",
    })
    .select("id")
    .maybeSingle<{ id: string }>();

  if (!error) {
    return { claimed: true, jobId: data?.id ?? null };
  }

  if (error.code === "23505") {
    return { claimed: false, jobId: null };
  }

  throw error;
}

export async function finishJob(
  supabase: SupabaseClient,
  jobId: string,
  status: Exclude<JobState, "running">,
  errorMessage?: string,
): Promise<void> {
  const { error } = await supabase
    .from("job_runs")
    .update({
      status,
      finished_at: new Date().toISOString(),
      error_message: errorMessage ?? null,
    })
    .eq("id", jobId);

  if (error) throw error;
}
