CREATE TABLE IF NOT EXISTS model_steps(
 run_id uuid NOT NULL REFERENCES runs(id), phase text NOT NULL CHECK(phase IN ('PLAN','FEEDBACK')),
 state text NOT NULL CHECK(state IN ('STARTED','VALIDATED','FAILED')), result jsonb, outcome text,
 PRIMARY KEY(run_id,phase));
INSERT INTO schema_version VALUES(6);
