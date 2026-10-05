-- F1: synthetic sourced facts, current field authorization, heartbeat evidence.
ALTER TABLE operations DROP CONSTRAINT operations_action_check;
ALTER TABLE operations ADD CONSTRAINT operations_action_check CHECK(action IN ('case.create','fault.record','facts.assess'));
ALTER TABLE runs ADD COLUMN heartbeat_count bigint NOT NULL DEFAULT 0;
ALTER TABLE runs ADD COLUMN last_heartbeat_at timestamptz;
CREATE TABLE field_grants (
 principal_id text NOT NULL REFERENCES principals, park_id text NOT NULL, org_id text NOT NULL,
 field_name text NOT NULL CHECK(field_name IN ('region','employees','service_need')),
 purpose text NOT NULL CHECK(purpose='SERVICE_PREPARATION'),
 capability text NOT NULL CHECK(capability IN ('READ','WRITE')),
 active boolean NOT NULL DEFAULT true, revision integer NOT NULL DEFAULT 1,
 valid_until timestamptz, source text NOT NULL CHECK(source='SYNTHETIC_SETUP'),
 PRIMARY KEY(principal_id,field_name,purpose,capability)
);
CREATE TABLE fact_assertions (
 id uuid PRIMARY KEY, evidence_id uuid UNIQUE NOT NULL,
 principal_id text NOT NULL REFERENCES principals, park_id text NOT NULL, org_id text NOT NULL,
 field_name text NOT NULL CHECK(field_name IN ('region','employees','service_need')),
 value jsonb NOT NULL, unit text NOT NULL, source_ref jsonb NOT NULL,
 source_kind text NOT NULL CHECK(source_kind='USER_ASSERTED_SYNTHETIC'),
 source_excerpt text NOT NULL, valid_from timestamptz NOT NULL, valid_until timestamptz NOT NULL,
 request_key text NOT NULL, fingerprint text NOT NULL, revision integer NOT NULL DEFAULT 1,
 confirmed_by text NOT NULL REFERENCES principals,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 CHECK(valid_until>valid_from), UNIQUE(principal_id,request_key)
);
INSERT INTO schema_version VALUES(3);
