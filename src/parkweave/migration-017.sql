-- Only new synthetic dispatch events. No legacy backfill or identity/grant writes.
CREATE TABLE IF NOT EXISTS dispatch_notice_outbox (
 event_id uuid NOT NULL REFERENCES service_dispatch_events,
 recipient_id text NOT NULL REFERENCES principals,
 state text NOT NULL DEFAULT 'PENDING' CHECK(state IN ('PENDING','DELIVERED','SUPPRESSED')),
 consumed_at timestamptz,
 PRIMARY KEY(event_id,recipient_id),
 CHECK((state='PENDING')=(consumed_at IS NULL))
);
CREATE TABLE IF NOT EXISTS dispatch_notices (
 event_id uuid NOT NULL, recipient_id text NOT NULL,
 delivered_at timestamptz NOT NULL DEFAULT clock_timestamp(), seen_at timestamptz, read_at timestamptz,
 PRIMARY KEY(event_id,recipient_id),
 FOREIGN KEY(event_id,recipient_id) REFERENCES dispatch_notice_outbox,
 CHECK(read_at IS NULL OR (seen_at IS NOT NULL AND read_at>=seen_at))
);
INSERT INTO schema_version VALUES(17) ON CONFLICT DO NOTHING;
