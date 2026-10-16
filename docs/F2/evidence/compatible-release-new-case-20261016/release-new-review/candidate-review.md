# Unfrozen compatible-publication candidate review

Development snapshot review only. Current implementation uses a process-level opt-in, preserves original Command/config schema and default fingerprints, and recomputes the finite name/description-only compatibility proof under the original SQLite write transaction. This narrow scope is appropriate; it does not authorize semantic source/goal/step changes or migration. Prior history state SUPERSEDED is correctly supported and original Release rows stay immutable.

Blocking confirmation issues reported to root (root accepted correction):

1. Publication.confirmed Literal[True] with strict model still accepts numeric 1 and 1.0 and normalizes to True. Pure actual Pydantic probe in confirmation-type-probe.json reproduces it. Add a before validator requiring value is True.
2. Strict direct TemplateEngine.command currently requires only a publicly observable preflight hash, not explicit confirmation. Add an exact-True strict argument, include only strict confirmation in the new strict fingerprint and immutable event proof; keep the default command bytes unchanged. API envelope alone cannot establish direct-service confirmation enforcement.

Other robustness findings reported for integration:

- Late preflight GET can reinstate a cleared publicationCheck after editor input/render because clearPublicationCheck does not advance a dedicated generation. The pure NodeVM probe late-preflight-probe.json reproduces late_preflight_reinstated=true using actual candidate HTML functions. Bind preview to a dedicated read ticket plus original view identity and invalidate on editor/goal input, render and context clearing.
- Opaque localStorage pending records lack exact bounded shape/UUID/hash validation. setItem is not read-back verified before POST and removeItem is not verified before unlocking. Use exact metadata-only handle validation, persist/readback before write and require successful removal before unlock. Corruption or storage failure must retain safe blocked state.
- Recovery validates several original actor/scope/hash/revision fields but should also require action CANDIDATE_PUBLISH, valid new Release ID, compatible strict proof and confirmed=True before clearing the key. NOT_OBSERVED already retains the handle and performs GET only, which is correct. 403 keeps original key while clearing private views.
- The preflight UI should validate explicit returned scope/profile/hash form and bind its complete snapshot, not only matching saved definition/revision.
- inspect directly indexes raw parsed previous Release/review structures. Malformed/non-object/incomplete records can produce KeyError/TypeError 500 rather than bounded UNKNOWN/refusal. Validate the complete finite proof under limited ValueError/TypeError/KeyError handling; do not swallow arbitrary programmer exceptions.

The release_new_case_support fixture explicitly retires old active capability catalog entries via original owner withdraw methods, then registers/maps the newly published source. This is needed because old superseded sources cannot silently be treated as available current catalog authority. It must be described as authorized fixture catalog governance, not automatic end-user rollout. New worker/assignment/issued approval bridge remain explicit fixture setup. Existing old Case history and capacity are retained; new holds use only remaining capacity and do not release old holds.

No PostgreSQL or browser execution was started by this reviewer. The two probes are controlled pure evidence only, not API/browser acceptance. Candidate is not frozen; fixes and final verification remain root's integration responsibility. All shared files and older sealed roots remain read only from this agent.
