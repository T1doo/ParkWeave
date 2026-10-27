-- Retain every accepted snapshot and receipt. Existing INSERT permissions support
-- a new preparation generation; no actor, grant, assignment or history changes.
DO $$DECLARE item record; preparation_column smallint;
BEGIN
 SELECT attnum INTO preparation_column FROM pg_attribute
 WHERE attrelid='service_receipt_steps'::regclass AND attname='preparation_id' AND NOT attisdropped;
 FOR item IN SELECT conname FROM pg_constraint
   WHERE conrelid='service_receipt_steps'::regclass AND contype='u'
     AND conkey=ARRAY[preparation_column]::smallint[]
 LOOP
   EXECUTE format('ALTER TABLE service_receipt_steps DROP CONSTRAINT %I',item.conname);
 END LOOP;
 IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conrelid='service_receipt_steps'::regclass
   AND conname='service_receipt_preparation_generation_key') THEN
   ALTER TABLE service_receipt_steps ADD CONSTRAINT service_receipt_preparation_generation_key
     UNIQUE(preparation_id,preparation_revision);
 END IF;
END$$;
INSERT INTO schema_version VALUES(24) ON CONFLICT DO NOTHING;
