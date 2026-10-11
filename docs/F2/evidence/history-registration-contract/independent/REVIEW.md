# Independent pure registration consistency contract review

Frozen source: `55d1366373e949ffe3f621be98c8a5d13435750f`.
Parent candidate: `008ecdaf767eec4e5d1dc9e82074b2781c3502d8`.
Branch: `acceptance/history-registration-contract-20261011`.

## Conclusion and scope

No blocking defect found within the approved default-disabled pure synthetic declaration/classification scope. No actual registration, provenance verification, storage, loader, API registration, access permission, execution authority or trusted installation-generation source is provided or proven by this module. MATCH must remain a data classification, never an authority decision. Limited candidate release is not dev/main integration or production enablement.

## Source review

The source diff contains only the new pure module, its synthetic tests and contract documentation. No existing reader, API, fact adapter, migration, role, credentials or execution chain is changed. Repository source search finds no production caller/import of the new checker. The module imports only dataclasses, datetime, pathlib pure path classes, re and UUID; it performs no file/database/network/environment/clock/proof discovery.

The synthetic enable flag must be exact True; default or truthy non-bool values return fixed UNKNOWN/DEFAULT_DISABLED before inspecting inputs. Both observations must be exact model types, complete, generation-known, maintenance-isolated and structurally valid; missing or unrecognized provenance/observations return UNKNOWN. These markers remain caller-supplied fixture labels, not authenticated trust roots.

Declaration validation checks exact immutable models and exact scalar types, bounded positive installation/revision values, canonical positive OID/system-identifier strings within unsigned DB bounds, syntactically absolute non-parent paths, maintainer installation/DB-owner consistency and separation of DB-owner/application role, exact person/park/org/UUID preparation/Case/Run/stage/document compatibility and namespace, unique 1–16 original UUID/key/hash anchors, standard fixed zero-offset UTC validity and revocation fields. Paths are only lexical strings, not verified real installation roots or owner/ACL evidence.

With complete observations, known invalid declarations, independent binding mismatch, first/last changes, expired absolute validity, time/revision/floor regressions and terminal revocation yield MISMATCH. Both current READ and source-current observations must be true. All returned fields and reasons are fixed classifications and do not expose identities, paths, original keys, bodies or proof. bool(result) raises TypeError.

The contract is stateless. It can compare a supplied current revision floor, ever-revoked record and generation, but cannot preserve them or authenticate them. If the entire declaration and all allegedly current independent observations (including time, generation, revision and revocation history) are replayed or replaced consistently, MATCH remains possible. This unavoidable complete indistinguishable replay case is explicitly documented and covered by both the new implementation tests and this independent probe. Missing current generation must remain UNKNOWN; hashes, same-SID files and old proof labels cannot fill it.

## New independent runtime evidence

**80 passed, 0 failed, 0 errors, 0 skipped, 0.09 seconds** on the frozen source. All are new private pure synthetic probes, not previous API/PG slice results. No PostgreSQL, browser/listener, network, actual model or old restricted execution chain is used.

Evidence files:

- `test_registration_independent.py`: independently constructed declaration and separately constructed observations.
- `review-55d13663.log` and `review-55d13663.xml`: actual run result.
- `manifest.json`: evidence hashes and frozen/parent SHA.

Coverage:

- Default disabled flags with poison inputs prove the default does not inspect candidate data.
- P4/P5 and 1/16 anchors match only as fixed data classification, preserve inputs, expose no private fields and cannot be coerced to bool.
- All 14 required observation/completeness fields missing independently in before and after positions return UNKNOWN (28 cases).
- Bool/integer/string substitutions for trusted-current flags, revision floor and read/source booleans are rejected as UNKNOWN.
- Independent install generation/root, database SID/directory/OID and person/org/Case/Run/preparation differences reject both stable mismatch and mid-observation change.
- Previously known revocation, revocation rollback, revoked current registration, revision/floor rollback, exact-end expiry, before-start and clock regression reject.
- Declaration type/boundary errors: bool revision, app/DB-owner equality, noncanonical OID, SID overflow, parent-traversing/relative paths, 129-character anchor key, duplicate/17 anchors and naive time reject.
- 128-character original key accepted; valid wrong P5 binding rejected; caller tzinfo callback never invoked; dictionary/subclass models rejected.
- Equal hashes/same SID without independent current generation, old proof and self-report provenance labels remain UNKNOWN.
- Complete indistinguishable replay is explicitly shown to remain MATCH; separately supplied current expiry rejects.
- Module import graph is pure; instrumented file/socket/sqlite/env interfaces are forbidden during evaluation without affecting classification.

## Existing associated regression limitation

Independently inspected both parent's preserved broad run logs, `/tmp/parkweave-registration-final.log` and `/tmp/parkweave-registration-verified.log`. Each reports **250 passed, 1 failed**; neither is counted as fully green or as an independent passing run here. Failed test: `tests/test_fact_history_read_source.py::test_exact_projection_no_values_or_proof_and_no_input_mutation`.

The old test first asserts the exact fixed projection fields and then searches the entire serialized JSON for every original source value as a substring. The employee source value is numeric 17, converted to literal string `17`; both failures show that substring occurring only inside allowed `source_sha256` hexadecimal metadata. Random fixture UUIDs feed that hash, so the substring check can reject an unrelated hash collision. The logged exact-field equality assertion had already passed. This demonstrates a weakness of the existing leakage assertion, not new registration output or evidence of the private numeric field being returned as a source value. It does not independently verify the final no-input-mutation assertion after the failed line.

Both the old test file and fact_history_read_source implementation are byte-for-byte unchanged versus this slice's parent; the comparison and file hashes are recorded in `associated-limitation.json`. Copied original failure logs are preserved privately as `associated-final.log` and `associated-verified.log`. No old test was edited or retried to obtain green. A fix to that old structural leakage assertion requires separate authorized work.

## Reviewer execution boundary

Only repository/Git reads and private `/tmp/parkweave-registration-independent-review` evidence writes were performed. No repository/Git mutation, fetch/checkout/commit/push, network, credentials, security permission/proxy/URL change, browser/listener, real PG or restricted execution chain. Final HEAD still matches the frozen source; parent's untracked evidence is not a reviewer write.

Original data: ERR_BLOCKED_BY_ADMINISTRATOR remains unchanged. Persistent registration/trust root, actual maintenance isolation, independent installation-generation continuity, Windows/full-page acceptance, complete issuer/API/worker exit and PG restart recovery remain outside the approved and tested pure-contract scope.
