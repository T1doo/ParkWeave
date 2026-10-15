# Independent frozen-source review

**LIMITED_PASS** for `6b8da028182d9b4ce35996eaaef2e6a78cff0666`, within Linux owned synthetic Case scope. No remaining confirmed product blocker in this review. This does not sign off complete F3, formal AT24–27, Windows, a real browser, a real model, production migration, or fulfillment.

## Exact execution and source identity

The 10 complete modules collected **351** nodes and JUnit executed the identical 351 unique nodes: **351 PASS, 0 FAIL, 0 ERROR, 0 SKIP**, pytest **837.62 s**, JUnit **837.612 s**. Modules: source_change_adoption, service_case_steps, service_plan_recovery, service_plan_manual_lock, registered_local_revision, case_goal_results, case_opportunities, template_migration_legacy, template_migration_independent, template_structure_independent.

The separate reviewer probes yielded **8 PASS, 0 FAIL, 0 ERROR, 0 SKIP**, pytest **53.28 s**, JUnit **53.272 s**. Six use actual HTTP → original ASGI → owned PostgreSQL; two use isolated in-process ASGI with owned PostgreSQL to compose source adoption and template structural upgrade in both orders. No browser was used. Probes cover hint-only source generations, repeated explicit source revisions, withdrawal after historical success, a real source rewrite between the two adoption builds, revoked EXECUTE, both template ordering cases, and the exact original recovery key collision.

Before/after manifests cover **592 paths**, comprising **587 Git-tracked source/test/script/pyproject paths** and five existing editable-install `src/parkweave.egg-info` metadata files. Zero before/after byte drift; every tracked path also exactly matches the frozen commit bytes. `git status --short` and `git diff --check` were empty on completion. The reviewer changed no product files or Git state. Collection/JUnit set comparison found zero missing, extra, or duplicate nodes.

## Findings and retained failures

A real blocker was independently reproduced on the preceding `957fb8df` freeze: actual IMPORT using legal key `plan-revision` succeeded, then the original `/opportunities/recovery/plan-revision` GET returned UUID422 because the new dynamic route matched `card_id=recovery` first. The original failure is retained in `route-957fb8df.log` and `.xml`. Root placed the original recovery route before the new dynamic route and froze `6b8da028`; both the full module and independent probe now pass. No other serious static finding remained.

The old reviewer windows remain historical: 9 PASS/45.13 s then interruption on `1d7f4c8`; 39 PASS/139.92 s then interruption on `957fb8df`. An initial reviewer-only probe oracle wrongly required an externally modified resource table to stay byte-identical; it produced 4 PASS/1 FAIL. Its original stdout/JUnit remain. Correcting the expected external write while still requiring every other table unchanged passed, and the final eight-probe window also passed. None of these windows is counted toward final 351 or 8.

## Root HOLD test failures

The two root failures are **test output directory prerequisites**, not a confirmed source-adoption regression. Static inspection of `tests/test_template_hold.py:67` and `:107` places the failing `Path.write_text` after the PostgreSQL/Node business assertions. The independent two-test reproduction records only `FileNotFoundError` for the absent `.runtime/template-hold-20261014` directory. Root created only this bounded runtime output directory, with frozen source still unchanged; the complete seven-test module then passed in 9.34 s (JUnit 9.344 s).

The successful probe artifacts show actual PostgreSQL authority-lock waiting, no revocation commit before journal CAS, and 34 original HTML NodeVM storage guard checks. This treatment introduces no remaining product blocker. Preserve the original root FAIL statistics and two-test reproduction; report the seven-test recheck separately. Do not relabel the root first window as uninterrupted all-PASS.

## Static invariants and evidence limits

Imported opportunity prose is not read as fact or authority. Proofs bind the latest pending card, current plan/version, actual sources, immutable ledger prefix, and mutable row epochs. The original ADOPT route is used with explicit local_revision, original actor/key replay semantics, current authorization, post-lock source rebuilding, and original event capacity constraints. Affected locks require original UNLOCK; stable IDs, goals, prior events, old verification snapshots, and unaffected lock evidence remain. Original VERIFY is still required for affected outputs. Current-card suppression remains separate from successful historical receipts.

Old optional-request fingerprints remain compatible through exclude_none, and source-change history composes with template structure history in both tested orders. UI source adoption calls the original tracked servicePlanWrite/entryFetch flow, checks original pending writes, keeps the existing opaque recovery handle, and separates stale identity/Case/draft responses from current views. Original HTML end-to-end coverage is reported by the separate independent-test owner, not added to these reviewer counts.

Two inherited complete test modules append private synthetic-session redaction sets at `.runtime/template-migration-tests-20261014/redaction-values.private.json` and `.runtime/template-structure-tests-20261015/redaction-values.private.json`. These shared metadata files are not reviewer-exclusive evidence and may combine concurrent runs. Reviewer logs, JUnit, collection, manifests, and `/tmp` database basetemps are independent. No synthetic sessions should be published; failure exports must preserve XML/JSON structure while masking only private fixture-repr/session content, with raw/export hashes and transformation counts.

The SELECT-only administrator final-read-to-COMMIT race remains the documented existing trust boundary. No new linearization protocol, credential, grant, security setting, deployment, real model, or production action was introduced or tested by this reviewer. Archive integrity review is pending root's completed export.
