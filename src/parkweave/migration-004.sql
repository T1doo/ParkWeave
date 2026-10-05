-- Current authorization for existing single-action runs. No F2 step/workflow implementation.
ALTER TABLE principals DROP CONSTRAINT IF EXISTS principals_role_check;
ALTER TABLE principals ADD CONSTRAINT principals_role_check CHECK(role IN ('enterprise_operator','park_specialist','resource_admin','service_executor'));
CREATE TABLE IF NOT EXISTS capability_grants (
 principal_id text REFERENCES principals, capability text CHECK(capability IN ('READ','CONTROL','EXECUTE','FILE_READ')),
 active boolean NOT NULL DEFAULT true, revision integer NOT NULL DEFAULT 1,
 park_id text NOT NULL, org_id text NOT NULL,
 PRIMARY KEY(principal_id,capability)
);
INSERT INTO capability_grants(principal_id,capability,park_id,org_id)
 SELECT id,capability,park_id,org_id FROM principals CROSS JOIN (VALUES('READ'),('CONTROL'),('EXECUTE'),('FILE_READ')) v(capability)
 WHERE role='enterprise_operator' ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS run_assignments (
 principal_id text REFERENCES principals, run_id uuid REFERENCES runs,
 park_id text NOT NULL, org_id text NOT NULL, active boolean NOT NULL DEFAULT true,
 PRIMARY KEY(principal_id,run_id)
);
CREATE TABLE IF NOT EXISTS deliveries (
 event_id uuid PRIMARY KEY REFERENCES outbox, run_id uuid NOT NULL REFERENCES runs,
 principal_id text NOT NULL REFERENCES principals, revision integer NOT NULL,
 state text NOT NULL CHECK(state IN ('READY','SUPPRESSED','RETRACTED')), payload jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS file_resources (
 id uuid PRIMARY KEY, principal_id text NOT NULL REFERENCES principals, run_id uuid NOT NULL REFERENCES runs,
 park_id text NOT NULL, org_id text NOT NULL, media_type text NOT NULL CHECK(media_type='text/plain'),
 size integer NOT NULL CHECK(size BETWEEN 0 AND 16384), sha256 text NOT NULL,
 source text NOT NULL CHECK(source='SYNTHETIC_FIXTURE')
);
CREATE TABLE IF NOT EXISTS action_grants (
 principal_id text REFERENCES principals, action text CHECK(action IN ('case.create','facts.assess','fault.record')),
 active boolean NOT NULL DEFAULT true, park_id text NOT NULL, org_id text NOT NULL, PRIMARY KEY(principal_id,action)
);
INSERT INTO action_grants(principal_id,action,park_id,org_id)
 SELECT id,action,park_id,org_id FROM principals CROSS JOIN (VALUES('case.create'),('facts.assess'),('fault.record')) v(action)
 WHERE role='enterprise_operator' ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS authorization_audit (
 id uuid PRIMARY KEY, principal_id text REFERENCES principals,
 category text NOT NULL, outcome text NOT NULL CHECK(outcome IN ('ALLOWED','DENIED','SUPPRESSED','RETRACTED')),
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
INSERT INTO schema_version VALUES(4) ON CONFLICT DO NOTHING;
