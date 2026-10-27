-- Additive Case intent metadata in existing authorised preparation tables.
-- No new identity, grant, table privilege, Run access or legacy backfill.
ALTER TABLE preparations ADD COLUMN IF NOT EXISTS request_intent jsonb
 CHECK(request_intent IS NULL OR jsonb_typeof(request_intent)='object');
ALTER TABLE preparation_events DROP CONSTRAINT IF EXISTS preparation_events_action_check;
ALTER TABLE preparation_events ADD CONSTRAINT preparation_events_action_check
 CHECK(action IN ('CREATE','ADD_EVIDENCE','REQUEST_CHANGES','REVIEW','CONFIRM','REOPEN','UPDATE_REQUEST'));
INSERT INTO schema_version VALUES(19) ON CONFLICT DO NOTHING;
