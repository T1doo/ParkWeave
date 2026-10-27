-- Migration 001: local-only synthetic foundation. No external write adapter.
CREATE TABLE IF NOT EXISTS schema_version(version integer PRIMARY KEY);
INSERT INTO schema_version VALUES(1) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS principals (
 id text PRIMARY KEY, token_hash text UNIQUE NOT NULL,
 park_id text NOT NULL, org_id text NOT NULL,
 role text NOT NULL CHECK (role='enterprise_operator'),
 active boolean NOT NULL DEFAULT true
);
CREATE TABLE IF NOT EXISTS runs (
 id uuid PRIMARY KEY, principal_id text NOT NULL REFERENCES principals,
 park_id text NOT NULL, org_id text NOT NULL,
 namespace text NOT NULL CHECK(namespace='SYNTHETIC'),
 request_key text NOT NULL, fingerprint text NOT NULL, input jsonb NOT NULL,
 state text NOT NULL CHECK(state IN ('QUEUED','RUNNING','PAUSED','CANCELLED','SUCCEEDED','FAILED')),
 fence bigint NOT NULL DEFAULT 0, worker_id text, lease_until timestamptz,
 success_scope text, revision integer NOT NULL DEFAULT 1,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(principal_id,request_key)
);
CREATE TABLE IF NOT EXISTS operations (
 id uuid PRIMARY KEY, run_id uuid UNIQUE NOT NULL REFERENCES runs,
 action text NOT NULL CHECK(action='case.create'),
 state text NOT NULL CHECK(state IN ('PREPARED','VERIFIED','FAILED_SAFE')),
 receipt jsonb
);
CREATE TABLE IF NOT EXISTS cases (
 id uuid PRIMARY KEY, run_id uuid UNIQUE NOT NULL REFERENCES runs,
 park_id text NOT NULL, org_id text NOT NULL,
 goal text NOT NULL, state text NOT NULL CHECK(state='NEEDS_INPUT'),
 source text NOT NULL CHECK(source='SYNTHETIC'),
 external_acceptance text NOT NULL CHECK(external_acceptance='NOT_SUBMITTED'),
 offline_fulfillment text NOT NULL CHECK(offline_fulfillment='NO_EVIDENCE')
);
CREATE TABLE IF NOT EXISTS outbox (
 id uuid PRIMARY KEY, run_id uuid NOT NULL REFERENCES runs,
 revision integer NOT NULL, payload jsonb NOT NULL,
 consumed_at timestamptz, UNIQUE(run_id,revision)
);
CREATE TABLE IF NOT EXISTS run_projection (
 run_id uuid PRIMARY KEY REFERENCES runs, revision integer NOT NULL, payload jsonb NOT NULL
);
