-- Portal project hardening only; the standalone ledger foundation is not deployed.
-- Event-trigger execution by the database owner is unaffected.
REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM PUBLIC, anon, authenticated;
