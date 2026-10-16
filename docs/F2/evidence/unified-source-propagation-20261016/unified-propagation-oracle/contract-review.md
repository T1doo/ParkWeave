# Independent bounded propagation design review

Baseline: `e0ffc81f2d29dbfd498c1a9a93206e689bd0b310`. This is read-only source analysis, not executed validation.

The proposed explicit `dependency_scope` on the original opportunity preview/ADOPT is appropriate. Store a separate v4 source-change envelope and dependency-propagation schema2 proof. Keep default request serialization, typed schema1/build_v1, original v1/v2 source-change history, and employees v3 history unchanged. Reject mixed opt-in scopes unless their exact composition is specified and independently tested.

Use a fixed facet/type registry and bounded graph. A shared Case/plan-bound source node identifies a registered source group, not a guessed concrete historical material/field ID. Edges retain each consumer's original before/current observation hashes, known flag, and change flag. P1 and P2 may have different last verified baselines of the same material package. Trigger only changed observation edges, then follow the actual registered PRECEDES DAG. A shared node's aggregate changed flag must never trigger every consumer edge.

The graph remains explanatory proof constrained to exactly the original source_impact plus registered dependency manifest partition. It must neither narrow preparation-wide invalidation nor expand known sets merely because nodes are deduplicated. Compare both affected and preserved ordered UUID lists against independently rebuilt original results. Deterministic IDs must include Case/plan binding and fixed facet identity, not mutable versions or current values.

A SERVICE_RULE node for P1 service_catalog and a SERVICE_RULE node for P2 resource_catalog_decision are distinct facets. RESOURCE_ASSOCIATION in P2 and P5 contains different projections. Preserve those exact observation projections; do not equate hashes or union their fields into invented historical facts. Dates remain original recorded resource intervals or explicit unavailable date evidence; absent dates alone do not automatically make impact UNKNOWN.

Missing bases, current unknown/invalid facts, unmapped fields, inconsistent graph/reference shape, incomplete/overflow collection, declaration uncertainty and unsupported graph schema must be bounded UNKNOWN or refusal. UNKNOWN is full selected Case affected, preserved empty, no actionable adoption. Do not project unmapped private field names or values into the UI.

Manual conflicts use original MANUAL v1/v2 or dual-slot package v3 guards and commands. KEEP_MANUAL and DEFER remain pending, while original KEEP_AND_CONTINUE/MERGE_NOTE preserve complete manual bytes and required line carriage. Any affected lock requires explicit original UNLOCK; complete unaffected lock step objects must remain byte-identical. Discovery or a hint is never fact, permission, owner confirmation, or automatic ADOPT.

v4 validation must reconstruct the exact historical original ledger prefix, per-step sources, dependencies and schema2 graph. Rehashing a forged edge/node, changing a version/type/UUID binding, replacing a saved original baseline with today's row, or removing the dependency scope to downgrade must fail. Current compiler evolution must not reinterpret historical v4; save a frozen build_v2 or explicit version dispatch.

Reuse original actor/tenant/owner/Case/Run/plan revision, ledger/card generation, source epochs including xmin ABA, capabilities, bounded transaction/adoption budget, original idempotent parameter conflicts and cold-GET recovery. A graph's per-edge observation IDs should also be unique and references total: every observation has exactly one registered consumer and node; every expected source facet appears once; duplicate observations cannot silently remove a source.

The 36-row literal oracle is intentionally separate from implementation closure. UP13-UP16 are the central anti-overinvalidation cases. UP05 and UP12 show union/dedup, UP09 tests mixed source types, UP18-UP24 cover uncertainty. Full HTML/ASGI/owned PostgreSQL, lost receipt, current/late 403 and identity ABA, original six-goal/worklist and preserved manual/lock objects require actual execution elsewhere; this review runs no tests and claims none.
