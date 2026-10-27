-- Explicit owned Linux storage extension; no startup DDL, schema version or grant changes.
DO $$ DECLARE receipt record; actual_owner name; marker regclass;
BEGIN
 SELECT pg_get_userbyid(datdba) INTO actual_owner FROM pg_database WHERE datname=current_database();
 IF current_user<>actual_owner OR session_user<>actual_owner THEN
   RAISE EXCEPTION 'actual test database owner required' USING ERRCODE='42501';
 END IF;
 IF current_database() IN ('postgres','template0','template1') THEN
   RAISE EXCEPTION 'new owned test database creation evidence required';
 END IF;
 marker:=to_regclass('pg_temp.parkweave_fixture_migration_receipt');
 IF marker IS NULL OR NOT EXISTS(SELECT 1 FROM pg_class WHERE oid=marker
     AND relnamespace=pg_my_temp_schema() AND relowner=(SELECT oid FROM pg_roles WHERE rolname=current_user)) THEN
   RAISE EXCEPTION 'verified fixture creation ticket required in migration transaction';
 END IF;
 IF (SELECT count(*) FROM pg_temp.parkweave_fixture_migration_receipt)<>1 THEN
   RAISE EXCEPTION 'exact fixture creation ticket required';
 END IF;
 SELECT * INTO receipt FROM pg_temp.parkweave_fixture_migration_receipt;
 IF receipt.database_oid IS DISTINCT FROM (SELECT oid FROM pg_database WHERE datname=current_database())
    OR receipt.database_name IS DISTINCT FROM current_database() OR receipt.owner_name IS DISTINCT FROM actual_owner
    OR receipt.system_identifier IS DISTINCT FROM (SELECT system_identifier::text FROM pg_control_system())
    OR receipt.data_directory IS DISTINCT FROM current_setting('data_directory')
    OR receipt.postmaster_start IS DISTINCT FROM pg_postmaster_start_time()
    OR receipt.backend_pid IS DISTINCT FROM pg_backend_pid() OR receipt.transaction_id IS DISTINCT FROM txid_current()
    OR receipt.cluster_nonce IS NULL OR receipt.database_nonce IS NULL THEN
   RAISE EXCEPTION 'fixture creation ticket does not match current owner transaction';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM pg_namespace WHERE oid='public'::regnamespace
       AND pg_has_role(current_user,nspowner,'USAGE')) OR EXISTS(
       SELECT 1 FROM pg_class WHERE oid IN ('public.preparation_catalog'::regclass,'public.schema_version'::regclass)
         AND relowner<>(SELECT oid FROM pg_roles WHERE rolname=current_user)) THEN
   RAISE EXCEPTION 'actual dispatch schema/table owner required' USING ERRCODE='42501';
 END IF;
 IF COALESCE((SELECT max(version) FROM public.schema_version),0) <>32
    OR NOT EXISTS(SELECT 1 FROM public.schema_version WHERE version=32) THEN
   RAISE EXCEPTION 'existing schema32 required for local approval storage';
 END IF;
END $$;
ALTER TABLE public.preparations ADD COLUMN local_resource_approvals jsonb CHECK(local_resource_approvals IS NULL OR jsonb_typeof(local_resource_approvals)='object'), ADD COLUMN local_resource_approval_head jsonb CHECK(local_resource_approval_head IS NULL OR jsonb_typeof(local_resource_approval_head)='object');
CREATE FUNCTION public.local_resource_approval_prefix() RETURNS trigger LANGUAGE plpgsql AS $local_approval$
DECLARE previous jsonb; next_value jsonb; i integer; n integer;
BEGIN
 previous:=OLD.local_resource_approvals; next_value:=NEW.local_resource_approvals;
 IF next_value IS NOT DISTINCT FROM previous THEN
   IF NEW.local_resource_approval_head IS DISTINCT FROM OLD.local_resource_approval_head THEN
     RAISE EXCEPTION 'immutable candidate Approval head';
   END IF;
   RETURN NEW;
 END IF;
 IF next_value IS NULL OR next_value->>'namespace'<>'LOCAL_CASE_RESOURCE_APPROVAL_V1'
    OR next_value->>'version'<>'1' OR jsonb_typeof(next_value->'events')<>'array' THEN
   RAISE EXCEPTION 'candidate Approval history required';
 END IF;
 n:=jsonb_array_length(next_value->'events');
 IF n<1 OR n>64 OR (next_value->>'revision')::integer<>n THEN
   RAISE EXCEPTION 'bounded candidate Approval history required';
 END IF;
 IF previous IS NULL THEN
   IF n<>1 THEN RAISE EXCEPTION 'initial candidate Approval event required'; END IF;
 ELSE
   IF n<>jsonb_array_length(previous->'events')+1 THEN
     RAISE EXCEPTION 'candidate Approval append only';
   END IF;
   FOR i IN 0..n-2 LOOP
     IF next_value->'events'->i IS DISTINCT FROM previous->'events'->i THEN
       RAISE EXCEPTION 'immutable candidate Approval event';
     END IF;
   END LOOP;
 END IF;
 NEW.local_resource_approval_head:=jsonb_build_object('revision',n,'sha256',next_value->'events'->(n-1)->>'sha256');
 RETURN NEW;
END
$local_approval$;
CREATE TRIGGER local_resource_approval_prefix BEFORE UPDATE OF local_resource_approvals,local_resource_approval_head ON public.preparations FOR EACH ROW EXECUTE FUNCTION public.local_resource_approval_prefix();
