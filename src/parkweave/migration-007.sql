CREATE TABLE IF NOT EXISTS model_plans(
 run_id uuid NOT NULL REFERENCES runs(id), revision integer NOT NULL CHECK(revision IN (1,2)),
 document jsonb NOT NULL, sha256 text NOT NULL CHECK(sha256~'^[0-9a-f]{64}$'),
 provider_call_id text NOT NULL, tool_call_id text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), PRIMARY KEY(run_id,revision));
INSERT INTO schema_version VALUES(7);
