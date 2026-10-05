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
