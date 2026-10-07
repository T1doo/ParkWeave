-- Candidate only: apply inside an owner transaction to a new UUID fixture DB.
-- No GRANT, role, identity, existing fact, material or receipt changes.
-- Rollback before COMMIT is ordinary transaction rollback (DDL is transactional).
-- After COMMIT, retain schema-25-compatible readers and all column/events.
-- Baseline Store rejects version >24 even when no profile is declared; a direct
-- code rollback is therefore not an operational recovery strategy. Disable new
-- writes only through separately reviewed compatible code, without unlocking
-- declared Cases. Never drop a populated ledger or relabel its actions. Any
-- schema downgrade needs a separately reviewed compatibility/retention plan.
DO $$ BEGIN
 IF current_database() !~ '^fixture_[0-9a-f]{32}$' THEN
   RAISE EXCEPTION 'isolated UUID fixture database required';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM schema_version WHERE version=24) THEN
   RAISE EXCEPTION 'schema 24 prerequisite required';
 END IF;
END $$;
ALTER TABLE preparations ADD COLUMN IF NOT EXISTS fact_clarifications jsonb;
ALTER TABLE preparation_events DROP CONSTRAINT IF EXISTS preparation_events_action_check;
ALTER TABLE preparation_events ADD CONSTRAINT preparation_events_action_check
 CHECK(action IN ('CREATE','ADD_EVIDENCE','REQUEST_CHANGES','REVIEW','CONFIRM','REOPEN','UPDATE_REQUEST',
                  'DECLARE_FACT_PURPOSE','CONFIRM_FACT_PURPOSE'));
INSERT INTO schema_version VALUES(25) ON CONFLICT DO NOTHING;
