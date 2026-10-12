-- Enforce the public intake contract at the database boundary. The web route
-- and direct Data API inserts are intentionally subject to the same limits.
alter table public.demo_requests
  add constraint demo_requests_email_length check (char_length(email) <= 254) not valid,
  add constraint demo_requests_phone_length check (phone is null or char_length(phone) <= 40) not valid,
  add constraint demo_requests_accounting_stack_length check (accounting_stack is null or char_length(accounting_stack) <= 160) not valid;

create or replace function private.enforce_demo_request_intake()
returns trigger
language plpgsql
security definer
set search_path = public, private, pg_temp
as $$
begin
  new.company_name := btrim(new.company_name);
  new.contact_name := btrim(new.contact_name);
  new.email := lower(btrim(new.email));
  new.phone := nullif(btrim(new.phone), '');
  new.accounting_stack := nullif(btrim(new.accounting_stack), '');
  new.message := btrim(new.message);
  new.created_at := timezone('utc', now());
  new.updated_at := new.created_at;

  -- Serialize each normalized email so concurrent requests cannot outrun the cap.
  perform pg_advisory_xact_lock(hashtextextended(new.email, 0));
  if (select count(*) from public.demo_requests
      where lower(email) = new.email
        and created_at >= timezone('utc', now()) - interval '1 hour') >= 3 then
    raise exception using errcode = 'P0001', message = 'Demo request rate limit exceeded';
  end if;
  return new;
end;
$$;

revoke all on function private.enforce_demo_request_intake() from public, anon, authenticated;

create trigger demo_requests_enforce_intake
before insert on public.demo_requests
for each row execute function private.enforce_demo_request_intake();
