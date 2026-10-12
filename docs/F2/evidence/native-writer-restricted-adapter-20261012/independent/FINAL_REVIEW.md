# Final independent restricted adapter review

LIMITED_PASS, bound to source `72f6b33ff3166f34dc12ae993cfcf50beefc811b` and independent 427-file manifest `68fc010b5f0b85569fda0547837b1e47484b096d3cbe28bfd6df2f288b5ea950`. Source/contract bytes match Git and remain identical before/after; root's final file map matches. Qualification is implemented code and pure synthetic dependency injection only.

| Independent window | Source | PASS | FAIL | ERROR | SKIP | Exit |
|---|---|---:|---:|---:|---:|---:|
| initial-frozen | dfd2579556ff7d4da5757458d55eb6e4581eaeb8 | 212 | 4 | 0 | 0 | 1 |
| initial-default-authority | dfd2579556ff7d4da5757458d55eb6e4581eaeb8 | 0 | 1 | 0 | 0 | 1 |
| fixed-frozen | 5a01addf441829679015c416303a6160ec878405 | 238 | 0 | 0 | 0 | 0 |
| fixed-import-acl-probes | 5a01addf441829679015c416303a6160ec878405 | 0 | 5 | 0 | 0 | 1 |
| final-frozen | cae80fe81285b5eb658efb61f2441e6f691f38d6 | 259 | 1 | 0 | 0 | 1 |
| final-default-store-authority | cae80fe81285b5eb658efb61f2441e6f691f38d6 | 0 | 1 | 0 | 0 | 1 |
| delivery-frozen | 72f6b33ff3166f34dc12ae993cfcf50beefc811b | 262 | 1 | 0 | 0 | 1 |

Final actual result is 262 PASS / 1 unchanged SQL Oracle FAIL, exit 1, not an all-PASS window. All 244 cases shared with root passed. Root separately ran 245 PASS; its only extra case is the existing preflight pure CLI subprocess test, deselected by our no-Popen boundary. The independent 19 additional cases yield 18 PASS and one Oracle FAIL. Do not add overlapping totals.

The late default-Store counterexample actually failed on `cae80fe...`: a ducktyped guard reached the default connector sentinel. No connection occurred. The frozen repair requires exact RuntimeGuard at construction and connect and calls the class's live-issuance method; the unchanged counterexample now passes, together with both new ducktype/instance-override regression cases. Earlier REVIEW and BLOCKED finding bytes remain unchanged; this later report supplies the final conclusion.

Across original failing windows, 10 of 11 same test IDs now PASS. The remaining old `system_schema_create` test searches an exclusion phrase across the entire statement and catches the correct routine system exception. Its actual old/current FAIL is preserved. Separate precise ownership/CREATE, table and routine control PASS proves the intended query predicate scopes. SQL observations are synthetic Reader/query-shape checks, not PostgreSQL execution. Valid-root source controls and valid-import positive/negative controls also pass, addressing possible early-refusal masking in older probes.

No remaining development blocker was found in this scope. Physical Linux process/UID/GID/IPC isolation, live protected-file/memfd issuance, actual restricted PostgreSQL metadata/ACL/DML and peers, production installation/activation, Windows/browser/LIVE/models and formal AT35 remain NOT_RUN. Seven actual preflight PG cases and the one CLI subprocess case were deliberately deselected here. No actual PG, service, private FD, credential or permission action occurred. Explicit installation approval and a trusted physical host are still required.

`FINAL_REVIEW.json` preserves exact windows, failure mappings and counts; `FINAL_SOURCE_BINDING.json` binds source and contracts. All seven original windows, failed code snapshots and earlier reports remain immutable. The new explicit export increment retains the late FAIL as well as its repair.
