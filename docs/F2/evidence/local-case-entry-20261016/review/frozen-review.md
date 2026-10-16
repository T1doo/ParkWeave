# Frozen independent review

Source: `2bfb955dc74fad7eb7e512c3b93396cef3f1332c`.

Static review scope: new `scripts/local_case_entry.py`, `scripts/local_case_entry_app.py`, `tests/test_local_case_entry.py`; original configured API, worker, Store seed/auth/capability/submit/read, role SQL and original fixture launcher contracts inspected for composition compatibility. Only three added files; no original product source changes.

The explicit setup creates a private owned Linux /tmp PostgreSQL fixture through the original live creation-receipt API, original migrate, original roles SQL and original fixed synthetic seeding CLI. Serve checks retained cluster identity/schema/restricted role read-only, never re-seeds/migrates, never reconstructs issued evidence, never writes assignments/approvals and launches only the original configured product API plus original worker with minimal child environment. New scope endpoint is read-only and checks current identity, READ, EXECUTE and exact scoped case.create grant. Original submit independently rechecks grants. Original APIs preserve tenant/owner access controls.

Initial review found immediate same-port restart TIME_WAIT rejection, nonexistent second confirmation-button instructions, and malformed-marker/psycopg exceptions escaping bounded CLI diagnostics. All three are fixed in frozen source; initial and after-fix evidence is retained. Unconfirmed child shutdown additionally leaves a durable blocked marker with no automatic clearing.

The delivered operable path is a single explicit original intake creation action producing only a local NEEDS_INPUT Case. The startup page honestly blocks full assignment/catalog/approval P1–P5, and does not claim external acceptance, fulfillment, real models or formal AT-35. No test import or manual DB business mutation substitutes for runtime actions. Negative tests use explicit original owner revocation outside user flow; that is not an ordinary runtime administration path.

Limits: only isolated Linux synthetic local Case creation/restart/read is in scope. Full browser P1–P5, Windows, formal AT-35, real models and production remain unexecuted. The stop-unconfirmed test verifies an existing blocked marker, not an actually unkillable child. Seven independent test results and source after-hash will be recorded separately after completion. Independent tests overlap integrator tests and must not be added as new unique coverage.
