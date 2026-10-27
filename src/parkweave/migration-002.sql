-- Additive migration: preserve all existing Runs/Cases/Receipts. No external connector.
ALTER TABLE runs DROP CONSTRAINT runs_state_check;
ALTER TABLE runs ADD CONSTRAINT runs_state_check CHECK(state IN
 ('QUEUED','RUNNING','PAUSED','CANCELLED','SUCCEEDED','FAILED','RECONCILING'));
ALTER TABLE runs ADD COLUMN control_intent text NOT NULL DEFAULT 'CONTINUE'
 CHECK(control_intent IN ('CONTINUE','PAUSE','CANCEL'));
ALTER TABLE runs ADD COLUMN next_attempt_at timestamptz DEFAULT clock_timestamp();
ALTER TABLE operations DROP CONSTRAINT operations_action_check;
ALTER TABLE operations ADD CONSTRAINT operations_action_check CHECK(action IN ('case.create','fault.record'));
ALTER TABLE operations DROP CONSTRAINT operations_state_check;
ALTER TABLE operations ADD CONSTRAINT operations_state_check CHECK(state IN
 ('PREPARED','DISPATCHED','VERIFIED','FAILED_SAFE','OUTCOME_UNKNOWN','EFFECT_KNOWN_INVALID'));
ALTER TABLE operations ADD COLUMN reconcile_attempts integer NOT NULL DEFAULT 0;
CREATE TABLE fixture_effects (
 operation_id uuid PRIMARY KEY REFERENCES operations, park_id text NOT NULL, org_id text NOT NULL,
 fingerprint text NOT NULL, receipt jsonb NOT NULL, dispatch_count integer NOT NULL
);
INSERT INTO schema_version VALUES(2);
