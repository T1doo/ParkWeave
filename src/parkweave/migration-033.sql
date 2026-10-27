-- Owned Linux synthetic fixture only; versioned service capability fixture metadata, no new grants.
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
 IF COALESCE((SELECT max(version) FROM public.schema_version),0) NOT IN (32,33)
    OR NOT EXISTS(SELECT 1 FROM public.schema_version WHERE version=32) THEN
   RAISE EXCEPTION 'schema 32 prerequisite or retained schema 33 required';
 END IF;
END $$;
ALTER TABLE public.preparation_catalog ADD COLUMN IF NOT EXISTS service_capability_catalog jsonb;
DO $capability_install$
DECLARE existing record;
BEGIN
 IF to_regprocedure('public.service_capability_prefix()') IS NOT NULL THEN
   SELECT p.prosrc,p.prosecdef,p.proconfig,p.proowner=r.relowner correct_owner,l.lanname
     INTO existing FROM pg_proc p JOIN pg_class r ON r.oid='public.preparation_catalog'::regclass
     JOIN pg_language l ON l.oid=p.prolang WHERE p.oid='public.service_capability_prefix()'::regprocedure;
   IF existing.prosrc IS DISTINCT FROM $capability_expected$
DECLARE before_value jsonb; after_value jsonb; n integer; i integer;
BEGIN
 IF TG_OP='DELETE' THEN
   IF OLD.service_capability_catalog IS NOT NULL THEN RAISE EXCEPTION 'immutable capability history'; END IF;
   RETURN OLD;
 END IF;
 before_value:=OLD.service_capability_catalog; after_value:=NEW.service_capability_catalog;
 IF before_value IS NOT NULL AND (NEW.park_id,NEW.service_id,NEW.version) IS DISTINCT FROM (OLD.park_id,OLD.service_id,OLD.version) THEN
   RAISE EXCEPTION 'immutable capability scope';
 END IF;
 IF after_value IS NOT DISTINCT FROM before_value THEN RETURN NEW; END IF;
 IF (NEW.park_id,NEW.service_id,NEW.version) IS DISTINCT FROM (OLD.park_id,OLD.service_id,OLD.version)
    OR jsonb_typeof(after_value) IS DISTINCT FROM 'object'
    OR after_value->>'scope' IS DISTINCT FROM 'ISOLATED_SERVICE_CAPABILITIES_V1'
    OR jsonb_typeof(after_value->'events') IS DISTINCT FROM 'array' THEN
   RAISE EXCEPTION 'immutable scoped capability journal required';
 END IF;
 n:=jsonb_array_length(after_value->'events');
 IF n<1 OR n>64 OR (after_value->>'revision')::integer IS DISTINCT FROM n THEN
   RAISE EXCEPTION 'bounded capability revision required';
 END IF;
 IF before_value IS NULL THEN
   IF n<>1 THEN RAISE EXCEPTION 'initial capability event required'; END IF;
 ELSE
   IF n<>jsonb_array_length(before_value->'events')+1 THEN RAISE EXCEPTION 'append-only capability journal required'; END IF;
   FOR i IN 0..n-2 LOOP
     IF after_value->'events'->i IS DISTINCT FROM before_value->'events'->i THEN
       RAISE EXCEPTION 'immutable capability history';
     END IF;
   END LOOP;
 END IF;
 RETURN NEW;
END;
$capability_expected$
      OR existing.prosecdef OR existing.proconfig IS NOT NULL OR NOT existing.correct_owner OR existing.lanname<>'plpgsql' THEN
     RAISE EXCEPTION 'retained immutable capability function mismatch';
   END IF;
 ELSE
   IF EXISTS(SELECT 1 FROM pg_trigger WHERE tgrelid='public.preparation_catalog'::regclass AND tgname='service_capability_prefix') THEN
     RAISE EXCEPTION 'partial capability trigger refused';
   END IF;
   EXECUTE $capability_function$CREATE FUNCTION public.service_capability_prefix() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE before_value jsonb; after_value jsonb; n integer; i integer;
BEGIN
 IF TG_OP='DELETE' THEN
   IF OLD.service_capability_catalog IS NOT NULL THEN RAISE EXCEPTION 'immutable capability history'; END IF;
   RETURN OLD;
 END IF;
 before_value:=OLD.service_capability_catalog; after_value:=NEW.service_capability_catalog;
 IF before_value IS NOT NULL AND (NEW.park_id,NEW.service_id,NEW.version) IS DISTINCT FROM (OLD.park_id,OLD.service_id,OLD.version) THEN
   RAISE EXCEPTION 'immutable capability scope';
 END IF;
 IF after_value IS NOT DISTINCT FROM before_value THEN RETURN NEW; END IF;
 IF (NEW.park_id,NEW.service_id,NEW.version) IS DISTINCT FROM (OLD.park_id,OLD.service_id,OLD.version)
    OR jsonb_typeof(after_value) IS DISTINCT FROM 'object'
    OR after_value->>'scope' IS DISTINCT FROM 'ISOLATED_SERVICE_CAPABILITIES_V1'
    OR jsonb_typeof(after_value->'events') IS DISTINCT FROM 'array' THEN
   RAISE EXCEPTION 'immutable scoped capability journal required';
 END IF;
 n:=jsonb_array_length(after_value->'events');
 IF n<1 OR n>64 OR (after_value->>'revision')::integer IS DISTINCT FROM n THEN
   RAISE EXCEPTION 'bounded capability revision required';
 END IF;
 IF before_value IS NULL THEN
   IF n<>1 THEN RAISE EXCEPTION 'initial capability event required'; END IF;
 ELSE
   IF n<>jsonb_array_length(before_value->'events')+1 THEN RAISE EXCEPTION 'append-only capability journal required'; END IF;
   FOR i IN 0..n-2 LOOP
     IF after_value->'events'->i IS DISTINCT FROM before_value->'events'->i THEN
       RAISE EXCEPTION 'immutable capability history';
     END IF;
   END LOOP;
 END IF;
 RETURN NEW;
END;
$$;$capability_function$;
 END IF;
 IF EXISTS(SELECT 1 FROM pg_trigger WHERE tgrelid='public.preparation_catalog'::regclass AND tgname='service_capability_prefix') THEN
   IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgrelid='public.preparation_catalog'::regclass
      AND tgname='service_capability_prefix' AND tgfoid='public.service_capability_prefix()'::regprocedure
      AND tgenabled='O' AND tgtype=27 AND tgattr::text='' AND NOT tgisinternal) THEN
     RAISE EXCEPTION 'retained immutable capability trigger mismatch';
   END IF;
 ELSE
   EXECUTE $capability_trigger$CREATE TRIGGER service_capability_prefix BEFORE UPDATE OR DELETE ON public.preparation_catalog
FOR EACH ROW EXECUTE FUNCTION public.service_capability_prefix();$capability_trigger$;
 END IF;
END
$capability_install$;
-- A statement-level guard also covers TRUNCATE, which never invokes row DELETE.
DO $truncate_install$
DECLARE existing record;
BEGIN
 IF to_regprocedure('public.service_capability_no_truncate()') IS NOT NULL THEN
   SELECT p.prosrc,p.prosecdef,p.proconfig,p.proowner=r.relowner correct_owner,l.lanname
     INTO existing FROM pg_proc p JOIN pg_class r ON r.oid='public.preparation_catalog'::regclass
     JOIN pg_language l ON l.oid=p.prolang WHERE p.oid='public.service_capability_no_truncate()'::regprocedure;
   IF existing.prosrc IS DISTINCT FROM $truncate_expected$
BEGIN
 IF EXISTS(SELECT 1 FROM public.preparation_catalog WHERE service_capability_catalog IS NOT NULL) THEN
   RAISE EXCEPTION 'immutable capability history';
 END IF;
 RETURN NULL;
END;
$truncate_expected$
      OR existing.prosecdef OR existing.proconfig IS NOT NULL OR NOT existing.correct_owner OR existing.lanname<>'plpgsql' THEN
     RAISE EXCEPTION 'retained capability truncate function mismatch';
   END IF;
 ELSE
   IF EXISTS(SELECT 1 FROM pg_trigger WHERE tgrelid='public.preparation_catalog'::regclass AND tgname='service_capability_no_truncate') THEN
     RAISE EXCEPTION 'partial capability truncate trigger refused';
   END IF;
   EXECUTE $truncate_function$CREATE FUNCTION public.service_capability_no_truncate() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM public.preparation_catalog WHERE service_capability_catalog IS NOT NULL) THEN
   RAISE EXCEPTION 'immutable capability history';
 END IF;
 RETURN NULL;
END;
$$;$truncate_function$;
 END IF;
 IF EXISTS(SELECT 1 FROM pg_trigger WHERE tgrelid='public.preparation_catalog'::regclass AND tgname='service_capability_no_truncate') THEN
   IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgrelid='public.preparation_catalog'::regclass
      AND tgname='service_capability_no_truncate' AND tgfoid='public.service_capability_no_truncate()'::regprocedure
      AND tgenabled='O' AND tgtype=34 AND tgattr::text='' AND NOT tgisinternal) THEN
     RAISE EXCEPTION 'retained capability truncate trigger mismatch';
   END IF;
 ELSE
   EXECUTE $truncate_trigger$CREATE TRIGGER service_capability_no_truncate BEFORE TRUNCATE ON public.preparation_catalog
FOR EACH STATEMENT EXECUTE FUNCTION public.service_capability_no_truncate();$truncate_trigger$;
 END IF;
END
$truncate_install$;
INSERT INTO public.schema_version VALUES(33) ON CONFLICT DO NOTHING;
