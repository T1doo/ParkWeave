# Vertical candidate draft static review

No definite code blocker identified. This is **not a frozen-source or execution signoff**. No tests, PG, CI or network calls were made. The JSON binds draft hashes and checks.

All 27 function names exist: seven original PG IDs match exactly, followed by nineteen existing Case cases and one same-database bridge. The actual fixture/source helper methods used by the bridge exist with matching call shapes. Session supplier interception is compatible with pytest firstresult/tryfirst; the result wrapper applies each per-DB REVOKE after original fixture creation. Original tests and expected owner/system-role refusals remain intact.

Pure regression must exercise the real pytest hook chain with a fake PG supplier and a default fixture sentinel that cannot run, including generator teardown and failures. Direct hook calls alone do not prove precedence. Also test DSN/role/options rejection, issued receipt boundaries, exact42501 plus recovery control, collection/outcome aggregation, cleanup/log faults and FD restoration. The original pg fixture dependency tmp_path_factory may initialize before interception, so private basetemp matters.

Connection/cleanup design retains private socket, new empty passfile, disabled SSL/GSS, temporary SQL roles, own Popen and required normal exit0. Application/native output is private; public diagnostics use fixed IDs and hashes. These patches constrain selected reviewed paths, not arbitrary hostile code.

The bridge binds persisted synthetic Case source to the same database's catalog checks. Its final catalog PASS after cancellation proves directory/ACL state, not continued policy validity or activation. No host/OS separation, password authentication, external HTTP service, process restart recovery or physical fulfillment is established. PostgreSQL uses multiple processes and ASGI tests use threads.

One review-checker invocation failed because SQL-containing node IDs include ::jsonb; split was corrected to split once, and this read-only error is preserved separately. No candidate test was run and no source was changed.
