# Independent archive audit

**LIMITED_PASS.** No remaining blocking evidence defect. This is a new read-only stage; earlier `REVIEW.md`/`review.json` retain their original signatures and the fact that the parent's full window was pending when they were signed.

Source `3fc6fa712f14820d88fcf8cd94fa70fcf6120e0c` and the401-path freeze SHA256 `cb236fe42b8acf4c6cf2748d781106844bffd1b1201094d63827d3f6350309c7` match every committed byte through read-only Git archive and every current working byte. No source/test/script/packaging drift.

## Frozen archive

Directory: `docs/F2/evidence/case-cancel-before-receipt-20261011/`. Archive manifest SHA256 `b042b947c119656bd2ee40c4196f78a861070a80ecb7580ced73d144c9b10526`; failure-map SHA256 `6ce95f3e86df53b4a5367813fbf8818570c76f85a956b1b8186f2f96f9da632d`.

All64 original/exported/decompressed payload hashes and sizes match. All64 documented policy outputs and redaction counters were independently reproduced in memory. No builder main routine or export rewrite occurred. The12 JUnit documents preserve every testcase attribute, identity, outcome, time and suite metadata except explicitly scrubbed hostname. JSON preserves literal hashes/IDs; static helper/probe/pre-fix code retains original bytes. Credential/PG URI/Bearer and runtime execution-path scans found no unredacted runtime values. Explicit static code path literals remain under the documented byte-preservation policy.

All14 actual failed occurrences/unique IDs map exactly once, retain original failed status and sanitized failure body, and have a separate same-ID PASS in the referenced final root or corrected independent window. The independent HIGH counterexample remains9PASS/2FAIL in its old window, and11PASS in the corrected window. No failure was converted to PASS and no multi-window total is claimed as one run.

## Actual final full window

The root single37-module window completed **1390PASS/0FAIL/0ERROR/1WindowsSKIP**,1391 unique IDs, exit0. All1271 old IDs remain, with120 new IDs (107 backend plus13 accepted-scope offline page tests). Recorded process elapsed1593.573seconds; raw/exported JUnit suite **1591.251seconds**; pytest stdout **1591.28seconds**. UTC record delta1593.576097seconds differs from process elapsed by3.097ms because the recorded timer points are separate; original records remain unchanged. Two original warnings remain; no atexit cleanup exception appears.

Raw final XML SHA256 `a00223f043bede1c402624de11a8810450b6e4b9003c5e96c852efd12e6bcf1e`; raw log SHA256 `e76451e584b3f808f55972d8ddec3aa6ab9060662de7e76e8f53d1a50cc71d6f`. Genuine native skip: `tests.test_authorization_files::test_native_windows_file_backend_gate`.

## Unchanged earlier evidence and limits

Previous61-artifact archive and all73 directory paths/bytes exactly match baseline `396602aa4e4889cb32d6af89a2b32cc3e45b5029`, including manifest SHA256 `92a3e17ea953c55f73ba22ac5908ac6c03f130dd535213964329a51c88c4c147`. An initial strict-set audit assertion found only an extra ignored generated policy pyc; no baseline byte changed. Parent removed its cache and the final set matches. A second audit assertion used an overly strict1ms clock equality bound; the3.097ms recorded difference is now represented explicitly. Both audit diagnostics are preserved as diagnostics, not testcase failures.

Historical cross-scope fixture-b root cause remains **UNCONFIRMED**; final same-ID PASS cannot restore original missing worker output/persistent state or confirm the short-lease hypothesis. Previous39 missing API stderr files and prior cleanup exception remain disclosed in the unchanged earlier archive. Windows execution is SKIP; browser attempts0 and prior administrator refusal was not retried. This bounded37-module run does not claim entire repository/AT, restore, post-receipt cancellation or complete Case lifecycle.

This audit ran no tests/PG/browser, and changed no product/test/doc/Git or archive input/export. It writes only its own runtime reports. Normal final documentation commit/push and remote verification remain parent work. Publish these new audit documents outside the frozen64-entry manifest; do not recursively rebuild it to include later audit outputs.

Machine details, each checked artifact hash,14 ID associations and original timing/limits: `ARCHIVE_AUDIT.json`.
