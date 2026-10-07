-- Adopted registered adapter plans use existing preparation metadata permissions.
ALTER TABLE preparations ADD COLUMN IF NOT EXISTS service_case_plan jsonb
 CHECK(service_case_plan IS NULL OR jsonb_typeof(service_case_plan)='object');
INSERT INTO schema_version VALUES(22) ON CONFLICT DO NOTHING;
