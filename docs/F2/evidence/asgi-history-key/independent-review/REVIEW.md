# Independent ASGI original request-key review

Frozen source reviewed and tested: `1928c811a31c48cc2a25c83cf184306b88f83add`.
Parent candidate: `8a8a0321d63abd05de36b71e0b51a56593bb2e8f`.
Candidate branch: `acceptance/asgi-history-key-20261011`.

## Conclusion

No blocking defect found within this optional original-key ASGI query slice. The new query preserves the memory-only fixed summary contract and current authorization/source guards. This is a limited candidate review, not approval or proof of dev/main integration, deployment, persistence, restored execution authority, push permission, old-container recovery, browser/Windows acceptance, or complete issuer/database restart recovery.

## Read-only source review

The application source diff against the parent candidate changes only the existing summary route: it accepts an optional plain string Query, rejects more than one decoded `request_key` query parameter, and passes the key unchanged as the existing `read_case` key argument with `stage=stage`. The reader, summary projector, current source adapter, existing execution routes, configured application factory and web are unchanged.

The original `_key` requires exact str or None and ASCII `[A-Za-z0-9._:-]{1,128}` with fullmatch. It does not strip, case-fold, normalize, enroll, or generate a key. Empty, overlength, non-ASCII and unsupported punctuation fail with Denied. The route does not use Query regex/max-length validation that could echo rejected input in a framework 422 response. The existing generic Denied handler returns HTTP 403 without key or private record contents. Ordinary URL decoding is query parsing, not semantic key normalization; a literal percent-bearing key passed through client params is rejected.

Exact known keys return the original projector's COMMITTED envelope and the exact fixed historical summary, including original historical FAILED state. Unknown keys return NOT_OBSERVED and null. The complete history is still validated before either keyed result, and omission leaves the original full-history envelope without top-level request_key/status/result. No retry, execution, inferred failure, proof issuance or authority registration is added.

Missing keys do not bypass current owner/tenant/Case READ or all-three-field fact-purpose READ, source validity/integrity/withdrawal, independent baseline validity, bounded original anchored document validation, or the before/after context/baseline/row/stage checks. The path stage remains explicitly pinned through read_case. The reader retains a read-only transaction and the fixed no-execution/no-grants/no-formal-writes flags. Authorization denials can append an existing authorization_audit record; business/permissions/outbox preservation is evaluated separately.

## Actual independent runtime result

**37 passed, 0 failed, 0 errors, 0 skipped, 15.92 seconds** on the frozen source above. No earlier slice's counts are included in this result.

Evidence: `review-1928c811.log`, `review-1928c811.xml`, and new independent probe source `test_key_independent.py`. Fixture adapter `conftest.py` explicitly loads the repository's owned isolated PostgreSQL fixtures and exports drop_owned_fixture_database for synthetic builder imports.

- 12 ASCII/length/punctuation cases: 1 and 128 characters accepted; 129, empty, whitespace, slash, plus, Unicode, newline and literal percent keys rejected. Valid keys preserve exact spelling and historical FAILED state. Invalid keys are rejected before instrumented history access; replies do not expose input.
- 3 duplicate cases: distinct values, identical values, and an encoded parameter name that decodes to request_key all reject before reader entry, without exposing either input.
- P4 and P5 existing, case-different missing, late and omitted queries: the precise summary and complete history agree; missing returns NOT_OBSERVED/null; GET leaves records unchanged; only explicit fixture enrollment makes a late key subsequently COMMITTED; no replay or new grant occurs.
- For both an existing and missing key, each of region/employees/service_need READ is independently revoked: all reject before instrumented private-source/history access.
- For both existing and missing keys, changes made after projection to READ capability, selected-source version, baseline expiry and server-owned anchored history all reject.
- For both existing and missing keys, wrong Case rejects before instrumented private source/history access.
- Both omitted and missing-key queries reject a server-owned P4-to-P5 stage replacement between route validation and reader entry.
- A missing key cannot bypass an extra unanchored duplicate row. A key query cannot register the default-None reader.
- Complete database snapshots for successful read, invalid/duplicate key, current READ denial, wrong Case, stage pin, unanchored row, and default-None probes show no read-caused business/permission/outbox mutation. Denied probes show exactly one existing audit append. Mutations performed deliberately after projection are fixture setup, not read-caused writes.

## Execution boundary and remaining limits

Reviewer used only repository/Git reads, private `/tmp/parkweave-key-independent-review` writes, the existing isolated synthetic PG fixture and in-process ASGI TestClient. No repository or Git mutation, credentials inspection, URL/proxy/network/security permission change, browser/listener/alternative navigation, real model or old receipt/restricted execution chain was performed. Repository HEAD still matched the frozen source at completion; the parent writer's untracked evidence directory is outside this reviewer's writes.

Original `data: ERR_BLOCKED_BY_ADMINISTRATOR` browser restriction remains untouched. Windows/full-page acceptance, persistent enrollment and full issuer exit/database restart recovery remain unverified. No dev/main integration or cross-environment state/credential sharing is inferred.
