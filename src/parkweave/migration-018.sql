-- One built-in synthetic template; no grants, business backfill or execution code.
CREATE TABLE IF NOT EXISTS controlled_plans (
 preparation_id uuid PRIMARY KEY REFERENCES preparations,
 id uuid UNIQUE NOT NULL, template_sha256 text NOT NULL,
 revision integer NOT NULL CHECK(revision BETWEEN 1 AND 64),
 checked jsonb NOT NULL DEFAULT '{}'::jsonb,
 invalidated_from integer CHECK(invalidated_from BETWEEN 1 AND 4),
 invalidated_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS controlled_plan_events (
 id uuid PRIMARY KEY, preparation_id uuid NOT NULL REFERENCES controlled_plans,
 actor_id text NOT NULL REFERENCES principals, request_key text NOT NULL,
 fingerprint text NOT NULL, revision integer NOT NULL,
 action text NOT NULL CHECK(action IN ('CREATE','CHECK_STEP')),
 step text CHECK(step IN ('P1','P2','P3','P4')),
 payload jsonb NOT NULL, snapshot jsonb,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(actor_id,request_key), UNIQUE(preparation_id,revision)
);
INSERT INTO schema_version VALUES(18) ON CONFLICT DO NOTHING;
