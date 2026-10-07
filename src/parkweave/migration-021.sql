-- Bounded planning metadata only, no business execution or new grants/tables.
ALTER TABLE preparations ADD COLUMN IF NOT EXISTS planning_previews jsonb
 CHECK(planning_previews IS NULL OR (jsonb_typeof(planning_previews)='array' AND jsonb_array_length(planning_previews)<=16));
INSERT INTO schema_version VALUES(21) ON CONFLICT DO NOTHING;
