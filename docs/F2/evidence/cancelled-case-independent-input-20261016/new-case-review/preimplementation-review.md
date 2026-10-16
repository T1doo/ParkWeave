# New independent Case after explicit cancellation: read-only review

Actual input HEAD: 57c19eeeb059c36f6a066332752a545b27706222. No shared files/Git writes, no PostgreSQL execution. All old cancel33 primary and audit roots remain untouched. New outputs are confined to .runtime/new-case-review.

## Precise historical coverage correction

The immutable P3 delivery final gate lists 99 unexecuted prior modules / 2655 prior-baseline nodes. Intersecting that exact list with the later cancel33 six passing JUnit windows gives exactly two complete modules:

- tests/test_case_cancellation_before_receipt.py: 107 passing nodes.
- tests/test_case_cancellation_reconciliation.py: 141 passing nodes.

Those two source modules are unchanged from the P3 source c91bbea1 to current HEAD. Therefore the later batch adds 248 old-baseline nodes from the earlier excluded set, leaving 97 prior modules / 2407 nodes unexecuted under that historical baseline accounting. This is not 508 additional nodes against the earlier 99 set: the other later passing modules were outside that exact missing set or were previously executed. No full-repository or formal AT completion follows.

The original P3 report's 99-not-run statement was correct at its historical time and must remain intact. The subsequent cancel33 report's “原99个旧模块本轮未执行” was overbroad. Add a dated correction to new report/current top-level progress only; preserve old sealed report/index/JUnit/audit bytes.

Suggested correction: “前批旧99模块未跑集合中，本批已完整补跑before_receipt 107项及reconciliation 141项，共2模块248项；按原基线口径，累计剩97模块2407节点未重跑。原99的历史时点记录保留，不代表本批全仓回归或正式AT通过。”

Exact remaining paths are in remaining-module-correction.json.

## Product-plan support and hard boundary

Master design §7.4 explicitly says cancellation does not undo fulfilled facts and reservation release is a separately authorized operation. Stage plan AT-08 requires a new Case from new inputs without copying old materials/authority. This supports two independent workflows: explicitly cancel the original accepted Case under the existing before_receipt contract, then independently submit fresh inputs and adopt/approve/allocate/accept/perform for a distinct new Case. It does not establish migration, old-Case revival, rollback of acceptance or automatic release.

New instance/run/Case/preparation/plan/approval/hold/combination/dispatch/receipt identities and request keys must be independent; original six goals and P1–P5 history remain readable and unchanged. New goals and materials must be independently explicitly supplied, not silently copied as authority. Any sharing of existing authorized materials must still use its own original consent contract.

## Existing complete primitives; do not reimplement

1. Original ordinary create already exists: Store.submit authenticates EXECUTE/current case.create action and creates a new Run/operation under a new request key; preparation.create binds the actual successful Case, original current catalog/reviewer rights, and refuses duplicate preparation for the same Run. web prep-create says “创建新的Case和运行，不复制上一事项材料”.
2. The more complete cold new-input entrance already exists in service workspace: coldReadDirectory, coldPrepare, coldPrepareStage, coldSendStage and coldOpen. It preserves required goals plus the two explicit fresh material fields and prepares original commands only. Each original CREATE_RUN, CREATE_PREPARATION, SAVE_REQUEST and ADD_EVIDENCE stage requires its own explicit confirmation; unknown replies recover by original GET rather than automatic replay.
3. The original service-instance-consumer provider is explicitly optional/default disabled. API refusal when instance_consumer is absent must remain refusal. Catalog discovery itself currently rechecks PREPARE/EXECUTE and case.create authority, so READ-only old cancellation recovery cannot become permission to create the new Case.
4. Original plan generation/adoption, original resource approval/delivery, executor offer/accept and actual receipt/verification stay responsible for the new Case. Existing tests/test_new_enterprise_local_chain.py already checks separate new input IDs, materials, results and no reuse of another enterprise approval/acceptance/result. Its managed execution fixture is not interchangeable with an ordinary accepted/manual schema33 cancellation fixture; use the existing applicable ordinary primitives instead of relaxing the original gate to combine fixtures.
5. resource_case_claims refuses a combination already owned by another Case. CONFIRMED holds continue to occupy capacity independently of old Case state. Original resource_combinations.cancel separately reauthenticates current owner/resource write rights and changes old members to RELEASED in its own transaction. A new Case must create fresh holds and a fresh combination after release if it needs the same constrained capacity. The old cancelled combination must never be rebound or restored.

## Minimal remaining gap and useful verification

No generic clone/migration/revival/cancel-and-create backend is needed. The narrow product gap is a clear read-only route from a successfully reconciled old cancellation to the existing fresh-input entrance, with accurate explanation that old resource capacity remains occupied and new inputs/approval/acceptance are independent. Merely opening the entrance or reading current configuration must not create anything, release anything or import old form values.

The unproven integration edge is actual ordinary schema33 ACCEPT/no-receipt cancellation followed by independent new inputs and a new original plan/approval/resource/acceptance flow. Cover refusal to use old approval, old resource combination, old executor acceptance and old receipt IDs; old Case remains CANCELLED with all prior records stable. With one-slot resource, show old CONFIRMED occupancy blocks new hold; without current release permission release remains 403 and no new hold is granted; only a distinct explicit original authorized release allows a fresh new hold/combination. Keep old claim/link/receipt history intact after release.

Include current tenant/owner/revocation rejection, same-key changed-body conflict and lost-response cold GET with no automatic repeat. Unknown old cancellation must not be treated as known cancelled or as permission to start a supposedly linked replacement. Broader new independent Case creation is already a separately authorized original action, but UI must not claim the uncertain old workflow has safely ended.

Native Windows, formal AT, real models, production and cross-process issuance restart remain outside this read-only review; no execution credit is claimed.
