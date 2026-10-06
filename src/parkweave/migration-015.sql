-- Internal synthetic dispatch; identity, grants and Run assignments remain read-only.
CREATE TABLE IF NOT EXISTS service_dispatches (
 id uuid PRIMARY KEY, preparation_id uuid UNIQUE NOT NULL REFERENCES preparations,
 revision integer NOT NULL CHECK(revision BETWEEN 1 AND 64), current_offer_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS service_dispatch_offers (
 id uuid PRIMARY KEY, dispatch_id uuid NOT NULL REFERENCES service_dispatches,
 executor_id text NOT NULL REFERENCES principals, preparation_revision integer NOT NULL,
 preparation_sha256 text NOT NULL, reason text NOT NULL CHECK(length(reason) BETWEEN 1 AND 1000),
 state text NOT NULL CHECK(state IN ('OFFERED','ACCEPTED','DECLINED','WITHDRAWN')),
 receipt_step_id uuid REFERENCES service_receipt_steps,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), UNIQUE(dispatch_id,id),
 CHECK((state='ACCEPTED') = (receipt_step_id IS NOT NULL))
);
DO $$BEGIN IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='service_dispatch_current_offer_fk' AND conrelid='service_dispatches'::regclass) THEN
 ALTER TABLE service_dispatches ADD CONSTRAINT service_dispatch_current_offer_fk FOREIGN KEY(id,current_offer_id)
 REFERENCES service_dispatch_offers(dispatch_id,id) DEFERRABLE INITIALLY DEFERRED;
 END IF; END$$;
CREATE TABLE IF NOT EXISTS service_dispatch_events (
 id uuid PRIMARY KEY, dispatch_id uuid NOT NULL REFERENCES service_dispatches,
 offer_id uuid NOT NULL, actor_id text NOT NULL REFERENCES principals,
 request_key text NOT NULL, fingerprint text NOT NULL, revision integer NOT NULL,
 action text NOT NULL CHECK(action IN ('OFFER','REOFFER','ACCEPT','DECLINE','WITHDRAW')),
 payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 FOREIGN KEY(dispatch_id,offer_id) REFERENCES service_dispatch_offers(dispatch_id,id),
 UNIQUE(actor_id,request_key), UNIQUE(dispatch_id,revision)
);
INSERT INTO schema_version VALUES(15) ON CONFLICT DO NOTHING;
