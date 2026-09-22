-- Public demo intake and the single TCSI platform-owner control plane.
-- Customer organization owners remain members of their own workspace. The
-- platform owner is deliberately a separate singleton account.

create table public.demo_requests (
  id uuid primary key default gen_random_uuid(),
  company_name text not null check (char_length(btrim(company_name)) between 2 and 160),
  contact_name text not null check (char_length(btrim(contact_name)) between 2 and 120),
  email text not null check (email ~* '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'),
  phone text,
  team_size text not null check (team_size in ('1-5', '6-20', '21-50', '51-200', '201+')),
  accounting_stack text,
  message text not null check (char_length(btrim(message)) between 10 and 2000),
  source text not null default 'website' check (source = 'website'),
  status text not null default 'new' check (status in ('new', 'contacted', 'qualified', 'closed')),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index demo_requests_status_created_idx on public.demo_requests(status, created_at desc);
create index demo_requests_email_idx on public.demo_requests(lower(email));

create trigger demo_requests_set_updated_at
before update on public.demo_requests
for each row execute function public.set_updated_at();

alter table public.demo_requests enable row level security;
alter table public.demo_requests force row level security;

revoke all on public.demo_requests from anon, authenticated;
grant insert on public.demo_requests to anon, authenticated;

create policy demo_requests_insert_public on public.demo_requests
for insert to anon, authenticated
with check (status = 'new' and source = 'website');

create table public.platform_owner_access (
  singleton boolean primary key default true check (singleton = true),
  user_id uuid not null unique references auth.users(id) on delete restrict,
  created_at timestamptz not null default timezone('utc', now())
);

comment on table public.platform_owner_access is
  'Exactly one row may exist. Seed the approved TCSI owner auth user through a protected administrative migration.';

alter table public.platform_owner_access enable row level security;
alter table public.platform_owner_access force row level security;
revoke all on public.platform_owner_access from anon, authenticated;

create or replace function public.is_platform_owner()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.platform_owner_access
    where singleton = true
      and user_id = (select auth.uid())
  );
$$;

revoke all on function public.is_platform_owner() from public;
grant execute on function public.is_platform_owner() to authenticated;

create or replace function public.get_platform_analytics()
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  analytics jsonb;
begin
  if not public.is_platform_owner() then
    raise exception using errcode = '42501', message = 'Platform owner access required';
  end if;

  select jsonb_build_object(
    'workspace_count', (select count(*)::int from public.workspaces),
    'membership_count', (select count(*)::int from public.workspace_members),
    'invoice_count', (select count(*)::int from public.invoices),
    'journal_entry_count', (select count(*)::int from public.journal_entries),
    'receivables_due', coalesce((select sum(balance_due) from public.invoices where status <> 'void'), 0),
    'demo_request_count', (select count(*)::int from public.demo_requests),
    'open_demo_request_count', (select count(*)::int from public.demo_requests where status <> 'closed'),
    'workspaces', coalesce((
      select jsonb_agg(to_jsonb(workspace_rows) order by workspace_rows.created_at desc)
      from (
        select
          workspace.id,
          workspace.name,
          workspace.slug,
          workspace.created_at,
          count(distinct member.user_id)::int as member_count,
          count(distinct invoice.id)::int as invoice_count,
          count(distinct entry.id) filter (where entry.status = 'posted')::int as posted_entry_count
        from public.workspaces as workspace
        left join public.workspace_members as member on member.workspace_id = workspace.id
        left join public.invoices as invoice on invoice.workspace_id = workspace.id
        left join public.journal_entries as entry on entry.workspace_id = workspace.id
        group by workspace.id, workspace.name, workspace.slug, workspace.created_at
      ) as workspace_rows
    ), '[]'::jsonb),
    'recent_demo_requests', coalesce((
      select jsonb_agg(to_jsonb(request_rows) order by request_rows.created_at desc)
      from (
        select id, company_name, contact_name, email, team_size, status, created_at
        from public.demo_requests
        order by created_at desc
        limit 8
      ) as request_rows
    ), '[]'::jsonb)
  ) into analytics;

  return analytics;
end;
$$;

revoke all on function public.get_platform_analytics() from public;
grant execute on function public.get_platform_analytics() to authenticated;
