-- TCSI Accounting foundation schema.
-- Every product table is tenant-scoped and protected by RLS. The service role
-- used by the Railway worker is never sent to the browser.

create extension if not exists pgcrypto;

create table public.workspaces (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(btrim(name)) between 2 and 160),
  slug text not null unique check (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
  base_currency char(3) not null default 'PHP' check (base_currency ~ '^[A-Z]{3}$'),
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table public.workspace_members (
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('owner', 'admin', 'accountant', 'encoder', 'viewer')),
  created_at timestamptz not null default timezone('utc', now()),
  primary key (workspace_id, user_id)
);

create table public.accounts (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  code text not null check (char_length(btrim(code)) between 1 and 40),
  name text not null check (char_length(btrim(name)) between 1 and 180),
  account_type text not null check (account_type in ('asset', 'liability', 'equity', 'revenue', 'expense')),
  is_active boolean not null default true,
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (workspace_id, code),
  unique (id, workspace_id)
);

create table public.journals (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  code text not null check (char_length(btrim(code)) between 1 and 20),
  name text not null check (char_length(btrim(name)) between 1 and 120),
  journal_type text not null check (journal_type in ('general', 'sales', 'purchases', 'cash', 'bank')),
  is_active boolean not null default true,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (workspace_id, code),
  unique (id, workspace_id)
);

create table public.accounting_periods (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  name text not null check (char_length(btrim(name)) between 1 and 120),
  start_date date not null,
  end_date date not null,
  status text not null default 'open' check (status in ('open', 'closed')),
  closed_by uuid references auth.users(id) on delete restrict,
  closed_at timestamptz,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  check (end_date >= start_date),
  unique (workspace_id, start_date, end_date),
  unique (id, workspace_id)
);

create table public.journal_entries (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  journal_id uuid not null,
  period_id uuid not null,
  entry_date date not null,
  reference text,
  description text not null check (char_length(btrim(description)) between 1 and 500),
  status text not null default 'draft' check (status in ('draft', 'posted', 'void')),
  source_key text,
  created_by uuid not null references auth.users(id) on delete restrict,
  posted_by uuid references auth.users(id) on delete restrict,
  posted_at timestamptz,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (id, workspace_id),
  unique (workspace_id, source_key),
  foreign key (journal_id, workspace_id) references public.journals(id, workspace_id) on delete restrict,
  foreign key (period_id, workspace_id) references public.accounting_periods(id, workspace_id) on delete restrict
);

create table public.journal_entry_lines (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  entry_id uuid not null,
  account_id uuid not null,
  description text,
  debit numeric(20, 2) not null default 0 check (debit >= 0),
  credit numeric(20, 2) not null default 0 check (credit >= 0),
  created_at timestamptz not null default timezone('utc', now()),
  check ((debit = 0 or credit = 0) and (debit + credit) > 0),
  foreign key (entry_id, workspace_id) references public.journal_entries(id, workspace_id) on delete cascade,
  foreign key (account_id, workspace_id) references public.accounts(id, workspace_id) on delete restrict
);

create table public.counterparties (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  kind text not null check (kind in ('customer', 'supplier', 'other')),
  legal_name text not null check (char_length(btrim(legal_name)) between 1 and 180),
  tax_identifier text,
  email text,
  is_active boolean not null default true,
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (id, workspace_id)
);

create table public.invoices (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  counterparty_id uuid,
  invoice_number text not null check (char_length(btrim(invoice_number)) between 1 and 80),
  invoice_type text not null check (invoice_type in ('sales', 'purchase', 'credit', 'debit')),
  status text not null default 'draft' check (status in ('draft', 'issued', 'partially_paid', 'paid', 'void')),
  invoice_date date not null,
  due_date date,
  currency char(3) not null default 'PHP' check (currency ~ '^[A-Z]{3}$'),
  subtotal numeric(20, 2) not null default 0 check (subtotal >= 0),
  tax_total numeric(20, 2) not null default 0 check (tax_total >= 0),
  total_amount numeric(20, 2) not null default 0 check (total_amount >= 0),
  balance_due numeric(20, 2) not null default 0 check (balance_due >= 0 and balance_due <= total_amount),
  source_key text,
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  check (due_date is null or due_date >= invoice_date),
  unique (workspace_id, invoice_number),
  unique (workspace_id, source_key),
  unique (id, workspace_id),
  foreign key (counterparty_id, workspace_id) references public.counterparties(id, workspace_id) on delete restrict
);

create table public.invoice_lines (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  invoice_id uuid not null,
  description text not null check (char_length(btrim(description)) between 1 and 500),
  quantity numeric(20, 4) not null check (quantity > 0),
  unit_price numeric(20, 2) not null check (unit_price >= 0),
  tax_amount numeric(20, 2) not null default 0 check (tax_amount >= 0),
  line_total numeric(20, 2) not null check (line_total >= 0),
  created_at timestamptz not null default timezone('utc', now()),
  foreign key (invoice_id, workspace_id) references public.invoices(id, workspace_id) on delete cascade
);

create table public.audit_events (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  actor_id uuid references auth.users(id) on delete set null,
  action text not null check (char_length(btrim(action)) between 1 and 120),
  entity_type text not null check (char_length(btrim(entity_type)) between 1 and 120),
  entity_id uuid,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now())
);

create table public.job_runs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid references public.workspaces(id) on delete cascade,
  job_name text not null check (char_length(btrim(job_name)) between 1 and 120),
  run_key text not null check (char_length(btrim(run_key)) between 1 and 240),
  status text not null default 'running' check (status in ('running', 'succeeded', 'failed')),
  started_at timestamptz not null default timezone('utc', now()),
  finished_at timestamptz,
  error_message text,
  unique (job_name, run_key)
);

create index workspace_members_user_idx on public.workspace_members(user_id);
create index accounts_workspace_type_idx on public.accounts(workspace_id, account_type);
create index journals_workspace_type_idx on public.journals(workspace_id, journal_type);
create index periods_workspace_status_idx on public.accounting_periods(workspace_id, status, start_date);
create index entries_workspace_status_date_idx on public.journal_entries(workspace_id, status, entry_date desc);
create index lines_workspace_entry_idx on public.journal_entry_lines(workspace_id, entry_id);
create index counterparties_workspace_kind_idx on public.counterparties(workspace_id, kind);
create index invoices_workspace_status_date_idx on public.invoices(workspace_id, status, invoice_date desc);
create index invoice_lines_workspace_invoice_idx on public.invoice_lines(workspace_id, invoice_id);
create index audit_events_workspace_created_idx on public.audit_events(workspace_id, created_at desc);
create index job_runs_workspace_status_idx on public.job_runs(workspace_id, status, started_at desc);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

create trigger workspaces_set_updated_at before update on public.workspaces for each row execute function public.set_updated_at();
create trigger accounts_set_updated_at before update on public.accounts for each row execute function public.set_updated_at();
create trigger journals_set_updated_at before update on public.journals for each row execute function public.set_updated_at();
create trigger periods_set_updated_at before update on public.accounting_periods for each row execute function public.set_updated_at();
create trigger entries_set_updated_at before update on public.journal_entries for each row execute function public.set_updated_at();
create trigger counterparties_set_updated_at before update on public.counterparties for each row execute function public.set_updated_at();
create trigger invoices_set_updated_at before update on public.invoices for each row execute function public.set_updated_at();

create or replace function public.is_workspace_member(target_workspace_id uuid)
returns boolean
language sql
stable
security invoker
set search_path = public
as $$
  select exists (
    select 1
    from public.workspace_members as member
    where member.workspace_id = target_workspace_id
      and member.user_id = (select auth.uid())
  );
$$;

create or replace function public.has_workspace_role(target_workspace_id uuid, allowed_roles text[])
returns boolean
language sql
stable
security invoker
set search_path = public
as $$
  select exists (
    select 1
    from public.workspace_members as member
    where member.workspace_id = target_workspace_id
      and member.user_id = (select auth.uid())
      and member.role = any(allowed_roles)
  );
$$;

create or replace function public.create_workspace(workspace_name text, workspace_slug text)
returns public.workspaces
language plpgsql
security definer
set search_path = public
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

alter table public.workspaces enable row level security;
alter table public.workspaces force row level security;
alter table public.workspace_members enable row level security;
alter table public.workspace_members force row level security;
alter table public.accounts enable row level security;
alter table public.accounts force row level security;
alter table public.journals enable row level security;
alter table public.journals force row level security;
alter table public.accounting_periods enable row level security;
alter table public.accounting_periods force row level security;
alter table public.journal_entries enable row level security;
alter table public.journal_entries force row level security;
alter table public.journal_entry_lines enable row level security;
alter table public.journal_entry_lines force row level security;
alter table public.counterparties enable row level security;
alter table public.counterparties force row level security;
alter table public.invoices enable row level security;
alter table public.invoices force row level security;
alter table public.invoice_lines enable row level security;
alter table public.invoice_lines force row level security;
alter table public.audit_events enable row level security;
alter table public.audit_events force row level security;
alter table public.job_runs enable row level security;
alter table public.job_runs force row level security;

create policy workspaces_select_member on public.workspaces for select to authenticated
  using (created_by = (select auth.uid()) or public.is_workspace_member(id));
create policy workspaces_update_admin on public.workspaces for update to authenticated
  using (public.has_workspace_role(id, array['owner', 'admin']))
  with check (public.has_workspace_role(id, array['owner', 'admin']));

create policy members_select_self on public.workspace_members for select to authenticated
  using (user_id = (select auth.uid()));

create policy accounts_select_member on public.accounts for select to authenticated using (public.is_workspace_member(workspace_id));
create policy accounts_insert_operator on public.accounts for insert to authenticated
  with check (public.has_workspace_role(workspace_id, array['owner', 'admin', 'accountant', 'encoder']) and created_by = (select auth.uid()));
create policy accounts_update_operator on public.accounts for update to authenticated
  using (public.has_workspace_role(workspace_id, array['owner', 'admin', 'accountant']))
  with check (public.has_workspace_role(workspace_id, array['owner', 'admin', 'accountant']));

create policy journals_select_member on public.journals for select to authenticated using (public.is_workspace_member(workspace_id));
create policy journals_insert_operator on public.journals for insert to authenticated
  with check (public.has_workspace_role(workspace_id, array['owner', 'admin', 'accountant']));
create policy journals_update_operator on public.journals for update to authenticated
  using (public.has_workspace_role(workspace_id, array['owner', 'admin', 'accountant']))
  with check (public.has_workspace_role(workspace_id, array['owner', 'admin', 'accountant']));

create policy periods_select_member on public.accounting_periods for select to authenticated using (public.is_workspace_member(workspace_id));
create policy periods_insert_operator on public.accounting_periods for insert to authenticated
  with check (public.has_workspace_role(workspace_id, array['owner', 'admin', 'accountant']));
create policy periods_update_operator on public.accounting_periods for update to authenticated
  using (public.has_workspace_role(workspace_id, array['owner', 'admin', 'accountant']))
  with check (public.has_workspace_role(workspace_id, array['owner', 'admin', 'accountant']));

create policy entries_select_member on public.journal_entries for select to authenticated using (public.is_workspace_member(workspace_id));
create policy entries_insert_operator on public.journal_entries for insert to authenticated
  with check (public.has_workspace_role(workspace_id, array['owner', 'admin', 'accountant', 'encoder']) and created_by = (select auth.uid()));
create policy entries_update_operator on public.journal_entries for update to authenticated
  using (public.has_workspace_role(workspace_id, array['owner', 'admin', 'accountant', 'encoder']))
  with check (public.has_workspace_role(workspace_id, array['owner', 'admin', 'accountant', 'encoder']));

create policy entry_lines_select_member on public.journal_entry_lines for select to authenticated using (public.is_workspace_member(workspace_id));
create policy entry_lines_insert_operator on public.journal_entry_lines for insert to authenticated
  with check (public.has_workspace_role(workspace_id, array['owner', 'admin', 'accountant', 'encoder']));
create policy entry_lines_update_operator on public.journal_entry_lines for update to authenticated
  using (public.has_workspace_role(workspace_id, array['owner', 'admin', 'accountant', 'encoder']))
  with check (public.has_workspace_role(workspace_id, array['owner', 'admin', 'accountant', 'encoder']));

create policy counterparties_select_member on public.counterparties for select to authenticated using (public.is_workspace_member(workspace_id));
create policy counterparties_insert_operator on public.counterparties for insert to authenticated
  with check (public.has_workspace_role(workspace_id, array['owner', 'admin', 'accountant', 'encoder']) and created_by = (select auth.uid()));
create policy counterparties_update_operator on public.counterparties for update to authenticated
  using (public.has_workspace_role(workspace_id, array['owner', 'admin', 'accountant', 'encoder']))
  with check (public.has_workspace_role(workspace_id, array['owner', 'admin', 'accountant', 'encoder']));

create policy invoices_select_member on public.invoices for select to authenticated using (public.is_workspace_member(workspace_id));
create policy invoices_insert_operator on public.invoices for insert to authenticated
  with check (public.has_workspace_role(workspace_id, array['owner', 'admin', 'accountant', 'encoder']) and created_by = (select auth.uid()));
create policy invoices_update_operator on public.invoices for update to authenticated
  using (public.has_workspace_role(workspace_id, array['owner', 'admin', 'accountant', 'encoder']))
  with check (public.has_workspace_role(workspace_id, array['owner', 'admin', 'accountant', 'encoder']));

create policy invoice_lines_select_member on public.invoice_lines for select to authenticated using (public.is_workspace_member(workspace_id));
create policy invoice_lines_insert_operator on public.invoice_lines for insert to authenticated
  with check (public.has_workspace_role(workspace_id, array['owner', 'admin', 'accountant', 'encoder']));
create policy invoice_lines_update_operator on public.invoice_lines for update to authenticated
  using (public.has_workspace_role(workspace_id, array['owner', 'admin', 'accountant', 'encoder']))
  with check (public.has_workspace_role(workspace_id, array['owner', 'admin', 'accountant', 'encoder']));

create policy audit_events_select_member on public.audit_events for select to authenticated using (public.is_workspace_member(workspace_id));
create policy job_runs_select_member on public.job_runs for select to authenticated using (workspace_id is not null and public.is_workspace_member(workspace_id));

revoke all on public.workspaces, public.workspace_members, public.accounts, public.journals,
  public.accounting_periods, public.journal_entries, public.journal_entry_lines,
  public.counterparties, public.invoices, public.invoice_lines, public.audit_events,
  public.job_runs from anon;

grant select on public.workspaces, public.workspace_members, public.accounts, public.journals,
  public.accounting_periods, public.journal_entries, public.journal_entry_lines,
  public.counterparties, public.invoices, public.invoice_lines, public.audit_events,
  public.job_runs to authenticated;
grant insert, update on public.accounts, public.journals, public.accounting_periods,
  public.journal_entries, public.journal_entry_lines, public.counterparties,
  public.invoices, public.invoice_lines to authenticated;
revoke all on function public.create_workspace(text, text) from public;
grant execute on function public.create_workspace(text, text) to authenticated;
