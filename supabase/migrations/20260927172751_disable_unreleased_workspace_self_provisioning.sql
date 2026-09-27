-- The hosted accounting pilot uses Odoo for company onboarding. The
-- standalone Supabase ledger is unreleased, so authenticated users must not
-- create their own workspaces through the Data API.
revoke execute on function public.create_workspace(text, text) from authenticated;
revoke execute on function private.create_workspace(text, text) from authenticated;
