-- Additive repair of unreleased ENG-005 schema4 prototype: bind every ability
-- grant to its setup scope. Never changes active flags or business history.
ALTER TABLE capability_grants ADD COLUMN IF NOT EXISTS park_id text;
ALTER TABLE capability_grants ADD COLUMN IF NOT EXISTS org_id text;
UPDATE capability_grants g SET park_id=p.park_id,org_id=p.org_id FROM principals p
 WHERE g.principal_id=p.id AND (g.park_id IS NULL OR g.org_id IS NULL);
ALTER TABLE capability_grants ALTER COLUMN park_id SET NOT NULL;
ALTER TABLE capability_grants ALTER COLUMN org_id SET NOT NULL;
ALTER TABLE action_grants ADD COLUMN IF NOT EXISTS park_id text;
ALTER TABLE action_grants ADD COLUMN IF NOT EXISTS org_id text;
UPDATE action_grants g SET park_id=p.park_id,org_id=p.org_id FROM principals p
 WHERE g.principal_id=p.id AND (g.park_id IS NULL OR g.org_id IS NULL);
ALTER TABLE action_grants ALTER COLUMN park_id SET NOT NULL;
ALTER TABLE action_grants ALTER COLUMN org_id SET NOT NULL;
INSERT INTO schema_version VALUES(5) ON CONFLICT DO NOTHING;
