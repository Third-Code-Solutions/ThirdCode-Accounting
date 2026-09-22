-- Tighten default Supabase function ACLs and keep cross-tenant reads behind a
-- non-exposed schema. Explicit role revokes are required because project
-- defaults may grant EXECUTE directly to anon/authenticated.

revoke execute on function public.create_workspace(text, text) from anon, authenticated;
grant execute on function public.create_workspace(text, text) to authenticated;

create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create or replace function private.is_platform_owner()
returns boolean
language sql
stable
security definer
set search_path = public, private
as $$
  select exists (
    select 1
    from public.platform_owner_access
    where singleton = true
      and user_id = (select auth.uid())
  );
$$;

revoke all on function private.is_platform_owner() from public, anon, authenticated;
grant execute on function private.is_platform_owner() to authenticated;

create or replace function private.get_platform_analytics()
returns jsonb
language plpgsql
stable
security definer
set search_path = public, private
as $$
declare
  analytics jsonb;
begin
  if not private.is_platform_owner() then
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

revoke all on function private.get_platform_analytics() from public, anon, authenticated;
grant execute on function private.get_platform_analytics() to authenticated;

-- The public RPC name stays stable for the application, but the wrapper is
-- invoker-only and cannot bypass tenant RLS by itself.
create or replace function public.get_platform_analytics()
returns jsonb
language sql
stable
security invoker
set search_path = public, private
as $$
  select private.get_platform_analytics();
$$;

revoke all on function public.get_platform_analytics() from public, anon, authenticated;
grant execute on function public.get_platform_analytics() to authenticated;

create or replace function public.is_platform_owner()
returns boolean
language sql
stable
security invoker
set search_path = public, private
as $$
  select private.is_platform_owner();
$$;

revoke all on function public.is_platform_owner() from public, anon, authenticated;
grant execute on function public.is_platform_owner() to authenticated;

create policy platform_owner_access_deny on public.platform_owner_access
for all to anon, authenticated
using (false)
with check (false);
