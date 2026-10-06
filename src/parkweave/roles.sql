-- Run as owner, after migrate. Role creation/authentication belongs to local DB setup.
-- Role parkweave_app must exist; this grants no administrator/DDL or DELETE rights.
GRANT CONNECT ON DATABASE parkweave TO parkweave_app;
GRANT USAGE ON SCHEMA public TO parkweave_app;
GRANT SELECT ON schema_version,principals TO parkweave_app;
GRANT SELECT,INSERT,UPDATE ON runs,operations,cases,outbox,run_projection TO parkweave_app;
GRANT SELECT ON field_grants TO parkweave_app;
GRANT SELECT,INSERT ON fact_assertions TO parkweave_app;
GRANT SELECT ON capability_grants,run_assignments,file_resources TO parkweave_app;
GRANT SELECT,INSERT,UPDATE ON deliveries TO parkweave_app;
GRANT SELECT ON action_grants TO parkweave_app;
GRANT INSERT ON authorization_audit TO parkweave_app;

GRANT SELECT,INSERT,UPDATE ON model_steps TO parkweave_app;

GRANT SELECT,INSERT ON model_plans TO parkweave_app;
GRANT SELECT,INSERT ON fact_reviews,fact_followups TO parkweave_app;

GRANT SELECT ON preparation_catalog,preparation_grants TO parkweave_app;
GRANT SELECT,INSERT,UPDATE ON preparations TO parkweave_app;
GRANT SELECT,INSERT ON preparation_evidence,preparation_events TO parkweave_app;

-- ENG018: new business tables only; registry/grants/history remain immutable to app.
GRANT SELECT ON synthetic_resources,synthetic_resource_grants TO parkweave_app;
GRANT SELECT,INSERT ON synthetic_resource_holds,synthetic_resource_receipts TO parkweave_app;
GRANT UPDATE(state) ON synthetic_resource_holds TO parkweave_app;

-- ENG021: only new combination tables; immutable membership and history.
GRANT SELECT,INSERT ON synthetic_resource_combinations,synthetic_resource_combination_members,synthetic_resource_combination_receipts TO parkweave_app;
GRANT UPDATE(state) ON synthetic_resource_combinations TO parkweave_app;

-- ENG023: new assigned-receipt tables only, parent binding/history immutable.
GRANT SELECT,INSERT ON service_receipt_steps,service_step_receipts,service_receipt_events TO parkweave_app;
GRANT UPDATE(state,revision,current_receipt_id) ON service_receipt_steps TO parkweave_app;

-- ENG025 immutable association/ownership tables only; core capabilities unchanged.
GRANT SELECT,INSERT ON resource_case_claims,case_resource_links TO parkweave_app;

-- ENG032 new internal dispatch tables only; no identity/capability grants.
GRANT SELECT,INSERT ON service_dispatches,service_dispatch_offers,service_dispatch_events TO parkweave_app;
GRANT UPDATE(revision,current_offer_id) ON service_dispatches TO parkweave_app;
GRANT UPDATE(state,receipt_step_id) ON service_dispatch_offers TO parkweave_app;

-- ENG033 new local lifecycle ledger and immutable events only.
GRANT SELECT,INSERT ON case_local_lifecycles,case_local_events TO parkweave_app;
GRANT UPDATE(revision,cycle,state,verified_snapshot,verified_sha256) ON case_local_lifecycles TO parkweave_app;

GRANT SELECT,INSERT ON dispatch_notice_outbox,dispatch_notices TO parkweave_app;
GRANT UPDATE(state,consumed_at) ON dispatch_notice_outbox TO parkweave_app;
GRANT UPDATE(seen_at,read_at) ON dispatch_notices TO parkweave_app;

-- ENG037 only local plan metadata and immutable audit, no grants to identities.
GRANT SELECT,INSERT ON controlled_plans,controlled_plan_events TO parkweave_app;
GRANT UPDATE(revision,checked,invalidated_from,invalidated_at) ON controlled_plans TO parkweave_app;
