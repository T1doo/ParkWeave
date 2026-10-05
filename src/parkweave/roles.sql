-- Run as owner, after migrate. Role creation/authentication belongs to local DB setup.
-- Role parkweave_app must exist; this grants no administrator/DDL or DELETE rights.
GRANT CONNECT ON DATABASE parkweave TO parkweave_app;
GRANT USAGE ON SCHEMA public TO parkweave_app;
GRANT SELECT ON schema_version,principals TO parkweave_app;
GRANT SELECT,INSERT,UPDATE ON runs,operations,cases,outbox,run_projection TO parkweave_app;
