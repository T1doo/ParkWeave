-- Local record closure is not Case fulfillment. No FULFILLED or real evidence states.
ALTER TABLE cases DROP CONSTRAINT IF EXISTS cases_state_check;
ALTER TABLE cases ADD CONSTRAINT cases_state_check CHECK(state IN ('NEEDS_INPUT','WAITING_CONFIRMATION','REOPENED'));
CREATE TABLE IF NOT EXISTS case_local_lifecycles (
 preparation_id uuid PRIMARY KEY REFERENCES preparations, case_id uuid UNIQUE NOT NULL REFERENCES cases,
 revision integer NOT NULL CHECK(revision BETWEEN 1 AND 64), cycle integer NOT NULL CHECK(cycle BETWEEN 1 AND 64),
 state text NOT NULL CHECK(state IN ('READY','LOCAL_RECORD_CLOSED','REOPENED')),
 verified_snapshot jsonb, verified_sha256 text,
 CHECK((state IN ('READY','LOCAL_RECORD_CLOSED') AND verified_snapshot IS NOT NULL AND verified_sha256 IS NOT NULL AND verified_sha256 ~ '^[a-f0-9]{64}$') OR (state='REOPENED' AND verified_snapshot IS NULL AND verified_sha256 IS NULL))
);
CREATE TABLE IF NOT EXISTS case_local_events (
 id uuid PRIMARY KEY, preparation_id uuid NOT NULL REFERENCES case_local_lifecycles,
 actor_id text NOT NULL REFERENCES principals, request_key text NOT NULL, fingerprint text NOT NULL,
 revision integer NOT NULL, cycle integer NOT NULL,
 action text NOT NULL CHECK(action IN ('REVALIDATE','CLOSE_LOCAL_RECORD','REOPEN')),
 payload jsonb NOT NULL, snapshot jsonb,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(actor_id,request_key), UNIQUE(preparation_id,revision)
);
INSERT INTO schema_version VALUES(16) ON CONFLICT DO NOTHING;
