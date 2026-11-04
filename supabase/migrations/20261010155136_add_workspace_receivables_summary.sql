create or replace function public.get_workspace_receivables_due(target_workspace_id uuid)
returns numeric
language sql
stable
security invoker
set search_path = public
as $$
  select coalesce(sum(invoice.balance_due), 0)
  from public.invoices as invoice
  where invoice.workspace_id = target_workspace_id
    and invoice.invoice_type = 'sales'
    and invoice.status in ('issued', 'partially_paid')
    and invoice.currency = 'PHP'
    and public.is_workspace_member(target_workspace_id);
$$;

revoke all on function public.get_workspace_receivables_due(uuid) from public, anon, authenticated;
grant execute on function public.get_workspace_receivables_due(uuid) to authenticated;
