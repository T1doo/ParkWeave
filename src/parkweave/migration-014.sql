-- Immutable, explicitly confirmed synthetic Case/resource associations.
CREATE TABLE IF NOT EXISTS resource_case_claims (
 combination_id uuid PRIMARY KEY REFERENCES synthetic_resource_combinations,
 case_id uuid NOT NULL REFERENCES cases, owner_id text NOT NULL REFERENCES principals,
 park_id text NOT NULL, org_id text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS case_resource_links (
 id uuid PRIMARY KEY, preparation_id uuid NOT NULL REFERENCES preparations,
 case_id uuid NOT NULL REFERENCES cases, run_id uuid NOT NULL REFERENCES runs,
 owner_id text NOT NULL REFERENCES principals, park_id text NOT NULL, org_id text NOT NULL,
 combination_id uuid NOT NULL REFERENCES synthetic_resource_combinations,
 revision integer NOT NULL CHECK(revision BETWEEN 1 AND 64), preparation_revision integer NOT NULL,
 preparation_sha256 text NOT NULL, service_id text NOT NULL, service_version integer NOT NULL,
 reason text NOT NULL CHECK(length(reason) BETWEEN 1 AND 1000), snapshot jsonb NOT NULL,
 actor_id text NOT NULL REFERENCES principals, request_key text NOT NULL, fingerprint text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(case_id,revision), UNIQUE(actor_id,request_key)
);
INSERT INTO schema_version VALUES(14) ON CONFLICT DO NOTHING;
