# ENG105 isolated Run access demo

This opt-in Linux launcher creates a new private temporary PostgreSQL fixture and retains its issued database-creation evidence in the API process. The API uses `create_app(store)` with the isolated bridge attached. Only the original `LOCAL` worker runs as a subprocess. This launcher does not enable a production factory or an installed Windows adapter.

From the repository root, using the project's Python environment:

```sh
PYTHONPATH=src:. python -m scripts.isolated_run_access_demo \
  --enable-isolated-run-access --fresh-fixture --port 8765 --max-seconds 3600
```

Both opt-in flags are required. The port must be 1024–65535; the duration must be 1–28800 seconds. Final single-invocation real Chromium verification is recorded in `docs/integration/ENG105-RunAccessEvidence.json`: fresh Case → REQUEST → independent APPROVE → original OFFER/ACCEPT/SUBMIT/owner ACK → REVOKE → original Run HTTP 403 and executor list removal. Static startup counts are supplemented by an authenticated live empty preparation-list check before browser writes; a reused populated fixture is rejected. This remains isolated local verification, not formal acceptance.

After readiness, stdout reports the loopback port and this invocation's temporary runtime directory. It never reports tokens or a DSN. Open `http://127.0.0.1:8765/`. The runtime directory contains private files:

- `synthetic-sessions.json`: original `fixture-a`, `fixture-b`, and `fixture-c` enterprise tokens.
- `preparation-sessions.json`: original `prep-specialist-fixture-a/b/c` tokens. These IDs are explicitly configured as independent access approvers for this isolated demonstration; material review alone does not confer approval authority.
- `receipt-sessions.json`: original `receipt-executor-fixture-a/b/c` tokens, initialized with current tenant `READ` only.
- `fixture-info.json`: token lookup and token-file paths for the owned browser harness.
- `smoke-environment.json`: startup identity and zero-business-record counts.
- `worker.log`: original worker output.

Preparation/catalog, resource, combination, and executor identity fixtures are initialized before interaction. No Run, Case, preparation, dispatch, receipt, or Run assignment is precreated. The user must create a real synthetic Run, request exact access, obtain an explicit independent decision, and use the original preparation/dispatch/receipt actions. The bridge supplies no new general capability or role. Revoke and expiry must be enforced by the actual product access checks; an approval display alone is not evidence of access.

Ctrl-C, SIGTERM, or the duration limit requests a bounded API shutdown and stops the exact owned worker. The original fresh-fixture context removes only this invocation's temporary directory after PostgreSQL stop is confirmed. Existing `.runtime` data is never reused or removed. If application termination cannot be confirmed, cleanup fails closed and retains the temporary fixture.
