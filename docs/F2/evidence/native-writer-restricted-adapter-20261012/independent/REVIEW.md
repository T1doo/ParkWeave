# Independent restricted adapter review

LIMITED_PASS for implemented code and pure synthetic dependency injection, bound to source `cae80fe81285b5eb658efb61f2441e6f691f38d6`. The independent 427-file source/contract manifest SHA256 is `d2caf123e1820dc71fadb4a89d44cb52ac9a1302e84a470db75b30f4dee43de8`; before/after bytes and Git source objects match, with no source or probe drift. Root's final 427-file map matches exactly. This does not qualify physical isolation or installation.

| Independent window | Source | PASS | FAIL | ERROR | SKIP | Exit |
|---|---|---:|---:|---:|---:|---:|
| initial-frozen | dfd2579556ff7d4da5757458d55eb6e4581eaeb8 | 212 | 4 | 0 | 0 | 1 |
| initial-default-authority | dfd2579556ff7d4da5757458d55eb6e4581eaeb8 | 0 | 1 | 0 | 0 | 1 |
| fixed-frozen | 5a01addf441829679015c416303a6160ec878405 | 238 | 0 | 0 | 0 | 0 |
| fixed-import-acl-probes | 5a01addf441829679015c416303a6160ec878405 | 0 | 5 | 0 | 0 | 1 |
| final-frozen | cae80fe81285b5eb658efb61f2441e6f691f38d6 | 259 | 1 | 0 | 0 | 1 |

Final independent window actually returned exit 1: 259 PASS and one unchanged old SQL Oracle FAIL, not an all-PASS window. All 242 shared production-module cases passed. The independent 18 additional cases produced 17 PASS and that one Oracle FAIL. Root separately ran 243 PASS; its sole extra case is the existing preflight pure CLI subprocess case, which the independent no-Popen guard deselected. These overlapping counts are not added. Every original XML, stdout/stderr, run record, source/probe manifest and failed source snapshot remains unchanged.

The original four source/cursor/identity counterexamples and the additional default-backend authority counterexample now pass under the same IDs. Valid protected-directory positive controls followed by cache/extension rejection also pass, avoiding the original fake-root metadata's early refusal. Four of the five later import/SQL counterexamples now pass under the same IDs. The remaining `system_schema_create` probe searches a namespace-exclusion phrase across the whole SQL statement and therefore catches the correct trusted-system routine exception. Its original and final FAIL remain recorded. A separate scoped control passes after checking the ownership/CREATE, table and routine subclauses independently. These three SQL probes and the corrected control observe query predicates through a synthetic Reader; no PostgreSQL privilege was exercised. Four valid-import positive controls followed by path/file/package/origin rejection also pass.

Static review confirms a complete protected source-node check, exact issued default-backend authorization, cursor SQL guards, existing-account/group predicates, isolated no-site launch with approved import paths, runtime module-origin checks, and expanded ACL predicates. API default remains closed. Dependency injection cannot issue a live host capability or enter the serving boundary. Actual protected files, identities, memfd issuance, processes, restricted SQL session/DML, sockets and peers, installation/activation, browser, Windows, LIVE/models and formal AT35 were NOT_RUN. No real permission, credential or authority change occurred. Separate explicit installation approval and a trusted physical host remain required.

No remaining development blocker was found within this code/DI scope. The remaining old Oracle failure is documented, preserved and not converted to PASS. `REVIEW.json` holds exact same-ID mappings; `SOURCE_BINDING.json` holds source/contract binding; `STATIC_EXPORT_REVIEW.json` permits only explicitly named, SHA-bound static files.
