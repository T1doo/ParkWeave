# F3-T03 full replacement independent contract

Status: DESIGN_ONLY_NOT_EXECUTED. Baseline f1161454fd746806fccef7ec7ac848a7bf618d25.

The minimal legal case uses two original V4 adopted candidate snapshots, same Case/owner/service family, exact current selected releases and mappings, and a finite compatible forward release change. A title-only independently reviewed release is a legitimate first positive case. Original preflight reports contract COMPATIBLE but current Case NEEDS_RECHECK for the changed catalog. Its unknown_scope THIS_CASE is also populated for known binding blockers and cannot alone mean an unsupported source.

Original preflight observations are not Approval: save permits known BREAKING_REJECTED/LOCK_CONFLICT evidence too. Any execution gate must check classification, current target, exact original candidate and registry, all selected pairs and current epochs, then require separate full-plan ADOPT, fresh P1 and explicit new Approval. The old/new immutable candidate snapshots plus original recovery proofs provide verifiable finite compatibility data without inventing an approval authority. New plan id must be retained; silently removing same-plan guard from source reapproval is not sufficient.

Original full replacement already rejects owner amendments and active locks, and retains old plan/history. Do not expand that contract: unsupported manual content remains safely blocked. Preserve previous resources/capacity/claims/approvals, new fresh UUID steps and old history; original explicit UNLOCK and independent resource release remain mandatory. No automatic release or migration of outside Case data.

Product references: docs/平台产品设计.md §7.3, §7.4, §7.5, §8; docs/F2/Plan.md and Log.md. Code: ServiceReleasePreflight.compare_v1/_build/_originals; service_case_steps.adopt/_recovery_proofs; case_resource_delivery._source_reapproval; service_plan_approval._ledger.

Execution must be accounted separately from the design rows in oracle-v1.json. Existing test numbers may not be migrated. Ordinary owned PG only; dedicated PG27 role/profile is not available and must remain NOT_RUN.
