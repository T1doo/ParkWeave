-- Slot-specific material correction history; existing preparation UPDATE only.
ALTER TABLE preparations ADD COLUMN IF NOT EXISTS material_corrections jsonb
 CHECK(material_corrections IS NULL OR
       (jsonb_typeof(material_corrections)='array' AND jsonb_array_length(material_corrections)<=16));
INSERT INTO schema_version VALUES(23) ON CONFLICT DO NOTHING;
