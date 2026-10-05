-- Additive immutable R3 snapshots/followups; no mutation of fact_assertions/history.
CREATE TABLE IF NOT EXISTS fact_reviews(run_id uuid PRIMARY KEY REFERENCES runs,document jsonb NOT NULL,
 sha256 text NOT NULL CHECK(sha256~'^[0-9a-f]{64}$'),created_at timestamptz NOT NULL DEFAULT clock_timestamp());
CREATE TABLE IF NOT EXISTS fact_followups(parent_run_id uuid NOT NULL REFERENCES fact_reviews(run_id),
 request_key text NOT NULL,fingerprint text NOT NULL,decision text NOT NULL CHECK(decision IN ('ANSWER','CANCEL')),
 child_run_id uuid REFERENCES runs,created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 CHECK((decision='ANSWER' AND child_run_id IS NOT NULL) OR (decision='CANCEL' AND child_run_id IS NULL)),
 PRIMARY KEY(parent_run_id,request_key));
INSERT INTO schema_version VALUES(8) ON CONFLICT DO NOTHING;
