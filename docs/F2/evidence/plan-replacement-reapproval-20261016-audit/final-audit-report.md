# Final independent archive audit

PASS at source 2dd98b67d52746dcdc3f358d2d60042cbea93909. The actual successful execution is final-v2 (exit 0), after a fully preserved final-v1 failure (exit 1) caused only by the auditor expecting the older writer-cessation status literal. The helper was changed to the exact declared V4 literal; no state set was broadened and no producer/public evidence was changed.

Independently checked 2,200 raw/export pairs, 607,300,358 exported bytes, exact public inventory (2,202 files including index and attributes), independent structured redaction reconstruction/counts, JSON/JSONL/XML parsing, known private residual absence, unchanged originals and 549 private registries/45,622 unique values. No values are exposed. Redactions were 8 exact known-value substitutions and 36 fixture representation lines.

Verified the primary seal (2,199 entries, self excluded but separately exported), all four review seals, 647 frozen source and 37 helper paths; independently reconstructed actual JUnit/collection union: 140 complete modules/3,690 unique PASS, no FAIL/ERROR/SKIP. Separate final CI: 433 PASS/14 original platform SKIP. Original recovery: 30 PASS, independently checked after all other final-source windows, CI and review. All 10,885 prior raw files and 3,642 prior actual test IDs remain; only the exact original import-time UUIDv4 parameter was normalized.

Verified all 12 V2/V3/V4 Chrome original-path/mtime/window/hash/byte mappings to exact copies, 16 private original/copy mappings with mode 0600/count/collector inclusion, support hashes and final writer cessation. These checks validate preserved evidence, not additional browser or product tests. No tests, producer-root writes or public-archive writes were performed by the auditor.

This audit does not close product gaps: dedicated PG27, general unfinished/UNKNOWN in-flight replacement, actual historical template-upgrade probe, Windows/native browser, broad browser acceptance, formal AT, real product model, production and real fulfillment remain limited/NOT_RUN as declared. The tested product remains LIMITED_PASS_WITH_PROFILE_GAP; archive integrity PASS is not full product acceptance.

The successful result is final-v2/final-archive-audit.json; all first-attempt outputs and the pre-fix helper remain. The PASS applies to the exact audited index hash and archive inventory; adding or changing files inside that archive requires a new audit.
