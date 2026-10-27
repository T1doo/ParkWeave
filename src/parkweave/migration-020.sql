-- Metadata in an existing authorised table only; no new grant or identity.
ALTER TABLE preparations ADD COLUMN IF NOT EXISTS readiness_assessments jsonb
 CHECK(readiness_assessments IS NULL OR (jsonb_typeof(readiness_assessments)='array' AND jsonb_array_length(readiness_assessments)<=32));
INSERT INTO schema_version VALUES(20) ON CONFLICT DO NOTHING;
