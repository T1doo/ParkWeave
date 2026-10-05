-- Exactly-two local synthetic combinations, never external reservations.
CREATE TABLE IF NOT EXISTS synthetic_resource_combinations (
 id uuid PRIMARY KEY, principal_id text NOT NULL REFERENCES principals,
 park_id text NOT NULL, org_id text NOT NULL,
 state text NOT NULL CHECK(state IN ('CONFIRMED','CANCELLED')),
 created_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS synthetic_resource_combination_members (
 combination_id uuid NOT NULL REFERENCES synthetic_resource_combinations,
 hold_id uuid NOT NULL UNIQUE REFERENCES synthetic_resource_holds,
 PRIMARY KEY(combination_id,hold_id)
);
CREATE TABLE IF NOT EXISTS synthetic_resource_combination_receipts (
 id uuid PRIMARY KEY, combination_id uuid NOT NULL REFERENCES synthetic_resource_combinations,
 actor_id text NOT NULL REFERENCES principals, request_key text NOT NULL, fingerprint text NOT NULL,
 action text NOT NULL CHECK(action IN ('CONFIRM','CANCEL')), payload jsonb NOT NULL,
 UNIQUE(actor_id,request_key)
);
INSERT INTO schema_version VALUES(12) ON CONFLICT DO NOTHING;
