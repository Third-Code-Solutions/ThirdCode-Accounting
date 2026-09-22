-- Keep workspace creation available to authenticated users without exposing a
-- SECURITY DEFINER implementation through the public API schema.

create or replace function private.create_workspace(workspace_name text, workspace_slug text)
returns public.workspaces
language plpgsql
security definer
set search_path = public, private
as $$
declare
  created public.workspaces;
  current_user_id uuid := auth.uid();
begin
  if current_user_id is null then
    raise exception using errcode = '42501', message = 'Authentication is required';
  end if;

  insert into public.workspaces (name, slug, created_by)
  values (btrim(workspace_name), lower(btrim(workspace_slug)), current_user_id)
  returning * into created;

  insert into public.workspace_members (workspace_id, user_id, role)
  values (created.id, current_user_id, 'owner');

  return created;
end;
$$;

revoke all on function private.create_workspace(text, text) from public, anon, authenticated;
grant execute on function private.create_workspace(text, text) to authenticated;

create or replace function public.create_workspace(workspace_name text, workspace_slug text)
returns public.workspaces
language plpgsql
security invoker
set search_path = public, private
as $$
begin
  return private.create_workspace(workspace_name, workspace_slug);
end;
$$;

revoke all on function public.create_workspace(text, text) from public, anon, authenticated;
grant execute on function public.create_workspace(text, text) to authenticated;
