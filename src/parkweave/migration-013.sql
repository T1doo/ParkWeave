-- Bounded assigned-executor SYNTHETIC receipts; no external/physical fulfillment.
CREATE TABLE IF NOT EXISTS service_receipt_steps (
 id uuid PRIMARY KEY, preparation_id uuid UNIQUE NOT NULL REFERENCES preparations,
 run_id uuid NOT NULL REFERENCES runs, case_id uuid NOT NULL REFERENCES cases,
 owner_id text NOT NULL REFERENCES principals, executor_id text NOT NULL REFERENCES principals,
 park_id text NOT NULL, org_id text NOT NULL, service_id text NOT NULL, service_version integer NOT NULL,
 preparation_revision integer NOT NULL, preparation_sha256 text NOT NULL, goal text NOT NULL,
 state text NOT NULL CHECK(state IN ('AWAITING_RECEIPT','RECEIPT_RECORDED','CHANGES_REQUESTED','LOCAL_ACKNOWLEDGED')),
 revision integer NOT NULL CHECK(revision BETWEEN 1 AND 64), current_receipt_id uuid,
 namespace text NOT NULL CHECK(namespace='SYNTHETIC'), created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS service_step_receipts (
 id uuid PRIMARY KEY, step_id uuid NOT NULL REFERENCES service_receipt_steps,
 version integer NOT NULL CHECK(version>0), text text NOT NULL CHECK(length(text) BETWEEN 1 AND 4000),
 source_kind text NOT NULL CHECK(source_kind='SYNTHETIC'), source_label text NOT NULL CHECK(length(source_label) BETWEEN 1 AND 200),
 source_sha256 text NOT NULL, actor_id text NOT NULL REFERENCES principals,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), UNIQUE(step_id,version), UNIQUE(step_id,id)
);
-- Repeatable version-marker migrations retain existing constraints/history.
DO $$BEGIN IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='service_step_current_receipt_fk' AND conrelid='service_receipt_steps'::regclass) THEN
 ALTER TABLE service_receipt_steps ADD CONSTRAINT service_step_current_receipt_fk FOREIGN KEY(id,current_receipt_id) REFERENCES service_step_receipts(step_id,id);
 END IF; END$$;
CREATE TABLE IF NOT EXISTS service_receipt_events (
 id uuid PRIMARY KEY, step_id uuid NOT NULL REFERENCES service_receipt_steps, actor_id text NOT NULL REFERENCES principals,
 request_key text NOT NULL, fingerprint text NOT NULL, revision integer NOT NULL,
 action text NOT NULL CHECK(action IN ('CREATE','SUBMIT','ACKNOWLEDGE','REQUEST_CHANGES','REOPEN')), payload jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), UNIQUE(actor_id,request_key), UNIQUE(step_id,revision)
);
INSERT INTO schema_version VALUES(13) ON CONFLICT DO NOTHING;
