# Source opportunity adoption evidence

Final source: `4c163fe23d8a841ece7b796e40e35511d70a0797`. The 214 indexed exports include historical windows; this source reference does not claim every entry ran at the final SHA.

- `index.json`: original/export SHA-256, byte lengths, and exact redaction counts. Private originals remain in the selected environment.
- `audit.json`: root deterministic export, raw preservation, structure and required-evidence checks.
- `source-adoption/final-coverage.json`: separate execution windows and exact byte equivalence; 52-module initial run was 1661 PASS / 27 FAIL, with original failures retained. HOLD7 and final diagnostics resolve the failures without relabeling the initial run.
- `source-adoption/delta-4c163fe.json`: final 8-module run, 297 PASS / 8 SKIP; same-invocation collection and JUnit match 305 nodes.
- `source-adoption-independent/freeze-4c163fe-result.json`: final 20 PASS and five complete original HTML → actual HTTP/ASGI/owned PostgreSQL traces.
- `source-adoption-review/REVIEW-4c163fe2.md`: final independent review. Previous 351-case business review and 8 probes actually ran at 6b8da028; relevant product/test bytes remain identical.

Only synthetic session values and fixture representation lines are redacted. XML is parsed before text redaction; JSON is processed recursively. Failure assertions and stack details remain. 33 fixture lines were masked; private session sets, database files and caches are excluded. Two inherited template redaction lists were shared metadata, not exclusive execution evidence. The selected inherited compatibility/UI/HOLD artifacts use fixed names and are last snapshots, not all historical windows.

Index/audit/README and this directory's Git attributes are metadata outside the indexed raw-export pairs. The later independent archive audit is likewise separate to avoid recursive hashing. No Windows, actual browser, formal AT, real model or production acceptance is claimed.
