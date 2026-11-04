alter table public.job_runs
  drop constraint job_runs_job_name_run_key_key;

alter table public.job_runs
  add constraint job_runs_workspace_job_run_key_key
  unique nulls not distinct (workspace_id, job_name, run_key);
