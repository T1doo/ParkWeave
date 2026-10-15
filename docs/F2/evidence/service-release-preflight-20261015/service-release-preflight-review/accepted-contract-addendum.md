# Subsequent contract decisions (implementation still WIP)

Parent/backend confirmed strict same-family `service_id + owner_org_id + source template_scope` and an explicit latest-template-head target. Same-release configuration inspection is `NO_RELEASE_CHANGE`, not a cross-version compatibility demonstration.

For the normal **target newly registered after the old V4 adoption** title-only upgrade, independently expected answers are two-layered:

- `contract_classification = COMPATIBLE`, `contract_affected = []` and contract-preserved = original P1–P5.
- The exact V4 `capability_catalog` binding has actually changed. Preserve the original `CURRENT_SERVICE_CAPABILITY_SOURCE_REQUIRED` / original binding diagnostics; overall classification is `NEEDS_RECHECK`, scope `THIS_CASE`, `current_case_affected = P1–P5` and final affected union = all five. Do not suppress the existing binding issue or imply title compatibility grants an actionable current plan.
- All existing UUIDs, content, manual locks, six goals and business/history stay unchanged. Any current affected locked step can make overall `LOCK_CONFLICT`; contract-preserved does not mean current checks are valid.

The original S01 in `contract-review.md` is explicitly a proposed special clean control with both revisions already in the saved catalog before adoption and identical source/registry/mappings. It is not the expected answer for a newly introduced head and is not required to expand this slice. S02–S04 similarly describe that control's current-resource-only change, not a promise to ignore a real changed catalog binding in normal upgrades.

This addendum freezes the normal title-only expected partition independently of any new production comparator. No product tests have run yet in this review; implementation and complete related modules must be evaluated at the later exact frozen SHA. Historical pass counts are not transferred.
