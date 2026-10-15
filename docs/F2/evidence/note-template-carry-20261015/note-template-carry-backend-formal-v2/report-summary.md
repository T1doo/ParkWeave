Frozen SHA `f686adafe3cec9b2820c10fada51ef2f57a559a6`: **235/235 named PASS**, seven complete modules.

Collection, JUnit and progress nodes match exactly; no unnamed placeholders. 613 source files and 14392 tracked files retain their hashes; HEAD and clean Git status are unchanged. Prior 2127-file inventory has no drift.

41 original-HTML traces (6+9+14+12); 957 page-driver test-body fetch records. Python fixture/setup HTTP is not counted. Node VM/DOM shim -> actual HTTP/ASGI -> owned PostgreSQL; real browser NOT_RUN.

| Response evidence | Traces | Page-driver fetch records |
|---|---:|---:|
| REAL_BACKEND_RESPONSE_SCENARIO | 29 | 460 |
| REAL_BACKEND_COMMIT_WITH_CONTROLLED_RECEIPT_LOSS | 7 | 361 |
| CONTROLLED_CLIENT_NEGATIVE | 5 | 136 |

| Oracle suite | Known records / affected pairs | Declared UNKNOWN records / pairs | Extra observed UNKNOWN records / pairs |
|---|---:|---:|---:|
| test_typed_source_impact_independent | 8 / 23 | 2 / 10 | 1 / 5 |
| test_shared_source_cases_independent | 8 / 14 | 4 / 10 | 0 / 0 |
| test_service_release_preflight_independent | 15 / 62 | 4 / 20 | 0 / 0 |
| test_at24_27_change_batch_independent | 27 / 100 | 8 / 40 | 0 / 0 |

All recorded affected/preserved comparisons match the literal oracle. UNKNOWN expansions are reported separately from definite impact precision. Absent lock fields do not imply a zero-lock-test result.

Raw hashes, modes, node IDs and limits are in report-summary.json, html-summary.json, oracle-statistics.json and artifacts-index.json. No Windows, real browser, formal AT, real model, production or real governance claim is made.

Response categories group entire traces. Their fetch subtotals include ordinary real HTTP within controlled-negative traces; they do not count injected responses alone.
