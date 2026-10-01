-- Invoker wrappers need schema visibility to call the protected functions.
-- Function EXECUTE remains revoked on the private implementations.

grant usage on schema private to authenticated;
