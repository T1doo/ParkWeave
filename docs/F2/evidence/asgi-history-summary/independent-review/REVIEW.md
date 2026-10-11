# Independent ASGI history summary review

Reviewed frozen source: `c3da9cb33a2fc205834d21825d64e98ddfcb1cce`.
Baseline: `b58cf201de3d6ca4e249bec3e8544ea53163807a`.
Branch under review: `acceptance/asgi-history-summary-20261011`.

## Conclusion

No remaining blocking defect found within the authorized memory-only ASGI summary scope after the stage binding fix. This review does not authorize or prove integration, deployment, push permission, persistent enrollment, Windows/browser acceptance, or full issuer/database restart recovery.

## Defect found and resolved

On initial frozen source `12a1afc3ddeba923fa1dfbb65f735f61fee3461a`, the API validated `reader.stage` but did not pass the requested stage into `read_case`. If the server-owned mutable reader changed to a different stage and matching baseline/rows between the route check and reader entry, the reader captured the new stage and returned its summary. The independent controlled mutation probe observed a P4 URL return HTTP 200 with P5 response stage. This does not demonstrate request-controlled registration; it demonstrates missing continuity of the server-owned stage contract.

The final source explicitly passes `stage=stage` into `read_case`, fixes `expected_stage` for projection, rejects mismatch before opening the read transaction, and compares `self.stage` again before return. The exact same independent probe now receives HTTP 403.

Historical evidence: `historical-12a1afc-stage.log` and `.xml`: 1 deliberately failing rejection assertion, 11 deselected. Only `api.py` and `history_summary.py` were exported read-only with `git show` to `old_source/` and loaded by the private plugin for the historical proof; all other source dependencies were unchanged between these two source commits. There was no checkout, repository mutation, or restoration of the old container.

## Static checks

- `create_app(store, *, summary_reader=None)` requires explicit server injection; exact type `MemoryHistorySummaryReader` and path stage are checked. The configured application still calls the default-None factory. Request/env/Store attributes do not register a reader.
- `read_case` requires exact UUID Case. `current_context` authenticates current READ and scopes the preparation to the enterprise operator, owner, park and org, then rejects a path Case mismatch before facts source queries, baseline access, history row access or document decode. Run/Case consistency checks follow.
- Declared facts reuse the reviewed `fact_history_read_source` adapter. Current READ for all three fields is checked before private facts queries and after cooperative field locks; the original explicit purpose/selection, source body integrity, source version, validity and withdrawal checks remain in place. No execution gate or issuance path is introduced.
- The reader sets its transaction READ ONLY and uses before/after source context checks, baseline equality/validity, row comparison, and stage continuity. Current Case is checked again in the second context. This is cooperative protection and snapshot comparison, not an atomicity claim over all independent writers.
- The projection retains fixed summary flags (`execution_available=false`, `NOT_EVALUATED`, `formal_writes=0`, `new_grants=false`), adds Case and stage, and does not return source bodies, selected facts, proof, execution leases, or restore authority.
- The existing receipt/lifecycle GET/POST/recovery executor gates and their exact provider type checks are untouched in the source diff. No web, production loader, persistence registration, credentials, proxy or access authorization change is present.
- The existing API Denied handler can append authorization_audit for a recognized bearer. Successful summary reads do not write; denial business, permissions and outbox preservation must be evaluated separately from that audit append.

## Independent runtime checks

`review-c3da9cb.log` and `.xml`: **12 passed**, 0 failed, 0 skipped, in 6.23 seconds. Probe source: `test_independent_summary.py`; fixture adapter: `conftest.py`.

- P4 and P5 successful reads: exact top-level shape, Case/stage, no private body/proof, no-store and unchanged complete database snapshots.
- Each of region, employees and service_need READ revoked independently: HTTP 403 before instrumented private facts/history access; complete database snapshot unchanged apart from one existing denial audit row.
- Wrong Case: HTTP 403 before instrumented private sources, row access and decode; same audit distinction.
- Post-projection baseline expiry, READ capability removal and fact expiry: rejected.
- Default None with simultaneous request query, environment and Store attribute attempts: rejected; no registration.
- Stage transition after API check but before reader capture: rejected on final source.
- Ordinary undeclared synthetic Case with a lawful current source revision change: summary marked STALE and no restored authority; database unchanged during read.

The initial private probe collection failed because its conftest adapter did not export `drop_owned_fixture_database` needed by reused fixture builders. This was corrected only under `/tmp` before the actual historical and final runtime runs; the collection failure is not counted as a passing application test.

## Execution boundary

Only reads of repository files and Git status/show/diff/rev-parse, private `/tmp` evidence writes, the existing isolated synthetic PostgreSQL fixture, and in-process ASGI TestClient were used. No listener/browser/alternative URL, real business test, repository modification, credential read, fetch/push/checkout/commit, URL/proxy/security permission change, or new access authorization was performed by this reviewer.

Unresolved limits retained: original browser `data: ERR_BLOCKED_BY_ADMINISTRATOR`; Windows/full-page acceptance; persistent registration; complete issuer exit and PostgreSQL restart recovery. These results are new-instance measurements and do not reuse the old 76 results or establish old-container authentication recovery.
