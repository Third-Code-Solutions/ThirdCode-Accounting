-- Public credentials may call the narrow intake RPC, never insert directly.
-- Operators configure only a SHA-256 digest here; the random 32-byte secret
-- belongs in TCSI_DEMO_INTAKE_SECRET on the web server, not in client assets.
revoke insert on public.demo_requests from anon, authenticated;
drop policy demo_requests_insert_public on public.demo_requests;

create table private.demo_intake_config (
  singleton boolean primary key default true check (singleton),
  secret_sha256 text not null check (secret_sha256 ~ '^[0-9a-f]{64}$')
);
alter table private.demo_intake_config enable row level security;
alter table private.demo_intake_config force row level security;
revoke all on private.demo_intake_config from public, anon, authenticated;

alter table public.demo_requests add column intake_client_hash text
  check (intake_client_hash is null or intake_client_hash ~ '^[0-9a-f]{64}$');
create index demo_requests_intake_created_idx on public.demo_requests(created_at desc)
  include (intake_client_hash);

create function private.submit_demo_request(ingestion_secret text, client_hash text, details jsonb)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  global_count bigint;
  client_count bigint;
begin
  if ingestion_secret is null or ingestion_secret !~ '^[0-9a-f]{64}$'
     or not exists (
       select 1 from private.demo_intake_config
       where singleton and secret_sha256 = encode(sha256(convert_to(ingestion_secret, 'UTF8')), 'hex')
     ) then
    raise exception using errcode = '42501', message = 'Intake authentication required';
  end if;
  if client_hash is null or client_hash !~ '^[0-9a-f]{64}$'
     or details is null or jsonb_typeof(details) <> 'object'
     or octet_length(details::text) > 24000 then
    raise exception using errcode = '22023', message = 'Invalid intake request';
  end if;

  -- One lock covers both counts and the insert, including concurrent web hosts.
  perform pg_advisory_xact_lock(18273, 1);
  select count(*), count(*) filter (where intake_client_hash = client_hash)
    into global_count, client_count
    from public.demo_requests
    where created_at >= now() - interval '1 hour';
  if global_count >= 100 or client_count >= 5 then
    raise exception using errcode = 'PT429', message = 'Demo request rate limit exceeded';
  end if;

  -- Explicit columns exclude status, timestamps and any caller-supplied identity.
  insert into public.demo_requests
    (company_name, contact_name, email, phone, team_size, accounting_stack, message, intake_client_hash)
  values
    (details->>'company_name', details->>'contact_name', details->>'email', details->>'phone',
     details->>'team_size', details->>'accounting_stack', details->>'message', client_hash);
end;
$$;
revoke all on function private.submit_demo_request(text, text, jsonb) from public, anon, authenticated;
grant usage on schema private to anon;
grant execute on function private.submit_demo_request(text, text, jsonb) to anon, authenticated;

create function public.submit_demo_request(ingestion_secret text, client_hash text, details jsonb)
returns void
language sql
security invoker
set search_path = ''
as $$ select private.submit_demo_request(ingestion_secret, client_hash, details); $$;
revoke all on function public.submit_demo_request(text, text, jsonb) from public, anon, authenticated;
grant execute on function public.submit_demo_request(text, text, jsonb) to anon, authenticated;
