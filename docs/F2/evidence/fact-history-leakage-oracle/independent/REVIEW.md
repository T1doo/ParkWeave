# Independent fact-history leakage test-oracle review

Final frozen source: `8e3e2f23d9380333f21e37b157d1d7d8c132e976`.
Parent: `b1beff467dbc54c77eea985ca2b7208f70b202ec`.
Candidate: `acceptance/fact-history-leakage-oracle-20261011`.

## Conclusion

Independent review passes within this tests-only correction scope. No remaining blocking defect found. The final oracle preserves and strengthens exact public-output and input-nonmutation checks while permitting legitimate digest metadata that happens to contain the short numeric fact text `17`. Source diff against the parent contains only `tests/test_fact_history_read_source.py`; production code, authority and trust anchors are unchanged. After the final independent PASS, the parent writer separately completed the original expanded three-file range; its preserved `/tmp/parkweave-oracle-expanded.log` shows 339 passed. That associated run is not included in the 48 independent probes, and its 87 oracle cases are a subset of 339, not an additional count.

## Issues found and fixed during independent review

On initial frozen source `c78c4922e2ebdb85fc43c89ee70dbb36678b8a69`, two independent negative probes failed to detect test-oracle bypasses:

1. A str subclass key with private underlying text and hash/equality impersonating `qualification` passed the key-set check; JSON serialization exposed its actual private string. The final oracle now requires all output keys to be exact str before whitelist comparison.
2. The independently separated input guard still used normal tuple/dict equality. A projector stub replacing integer employee value 17 with float 17.0 passed that equality. The final test-local guard recursively requires exact types and values, exact str dict keys, exact key sets, sequence types/lengths/items and scalar types/values. It runs in finally.

The first key fix was separately frozen at `2ec890fde2e707dfdb440e2be280c9f73ec49664`; both fixes are present in final `8e3e2f23...`. Original c78 source was read-only exported to `frozen_c78c4922_oracle.py`; the final historical probe evidence records **2 deliberately failed rejection assertions**, not passes. Evidence: `test_key_alias_defect.py`, `historical-c78c4922.log` and `.xml`. The historical source was not checked out or altered.

## Final source assessment

The result must be an exact dict, with exact str keys matching the closed public whitelist. Scalar values and the fields list must have exact expected types and complete values; each fields element must be exact str. Hash metadata must be lowercase 64 hex and equal a separately supplied fixture digest, not merely be hash-shaped. The actual projection test computes that digest from fixture binding/decision/sorted selected rows before projecting. A fixed UUID fixture also provides a hard-coded expected digest independent of the output. An unrelated valid 64-hex value cannot replace the digest slot.

The output schema no longer searches arbitrary numeric strings across JSON. Unknown keys, fragments appended to allowed scalar values, private list entries, proof/body/source identifiers, changed fixed flags and numeric bool substitutes all fail structurally. Public fields retain exact full-value assertions.

Input nonmutation is a separate test with a finally guard, so a failed output assertion no longer prevents the input check from running. If the projector raises without mutation, its original exception propagates. If it mutates first, the exact input guard fails even after the projector raises. The guard also detects same-value int/float/bool changes and custom input-key aliases. It is local test code; no production comparator or projection is changed.

## Actual independent final runtime evidence

**48 passed, 0 failed, 0 errors, 0 skipped, 0.19 seconds** on final frozen source. New private pure synthetic probes only; no PG, API/listener, browser, network or old restricted execution chain. No prior slice's tests are counted here.

Evidence: `test_oracle_independent.py`, `review-8e3e2f23.log`, `review-8e3e2f23.xml` and `manifest.json`.

Independent controls include:

- Two valid lowercase 64-hex digests containing `17` are accepted. The actual deterministic pure project fixture yields exactly `1ab214b54e972ae2231da520785615e66a899c101a448b4c8b963508627d5717`, matches an independently written full public-result dictionary and the hard-coded digest, and retains numeric employee input 17.
- Numeric private fact 17, private excerpt fragment and source UUID injected in an unknown field, appended to an allowed scalar, appended to fields or replacing digest are rejected (12 cases).
- Embedded excerpts in each permitted string scalar are rejected; four other hash-shaped/different digests are rejected.
- Every public boolean flag with int/float 0 or 1 is rejected even when normal equality would consider it equal (12 cases).
- Both str and int JSON-serializable key aliases are rejected; value/list-element and result subclasses are rejected.
- Six projector mutations including equal float/bool/revision values, extra source row, changed excerpt and custom input-key alias all cause the independent nonmutation test to fail as intended.
- Mutation followed by a projector exception still triggers the finally guard; a no-mutation exception remains the original error; deliberately invalid output fails the output test while the separately executed nonmutation test still runs and succeeds when its input is unchanged.

## Historical associated failures retained

Previous expanded registration slice's two **250 passed, 1 failed** runs remain preserved as `previous-associated-final.log` and `previous-associated-verified.log`, copied from the earlier private evidence. The failure was literal string `17` appearing within allowed random source_sha256 metadata. The preceding exact public-fields assertion passed; the old later input-nonmutation assertion was not reached. This report does not claim that assertion executed or relabel those two runs green. No repetition of the old flawed test was used to seek a green result.

## Scope and execution limits

All reviewer mutations were private `/tmp/parkweave-oracle-independent-review` probes/evidence. Repository/Git access was read-only. No fetch/checkout/commit/push, production write, credentials/network/security/proxy/URL operation, real PG/model, browser/listener or restricted execution chain. Production src tree is unchanged versus parent and the fact adapter file hash comparison is recorded in `scope.json`.

This is a test-oracle correction, not new production authorization, trust registration or reader enablement. Original browser data: ERR_BLOCKED_BY_ADMINISTRATOR, Windows/full-page, persistent registration and complete restart-recovery limitations remain unchanged.
