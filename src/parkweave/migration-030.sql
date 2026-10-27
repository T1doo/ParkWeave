-- Owned Linux synthetic fixture only; ordinary Case cancellation, no new grants.
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
       SELECT 1 FROM pg_class WHERE oid IN ('public.cases'::regclass,
         'public.case_local_lifecycles'::regclass,'public.case_local_events'::regclass,'public.schema_version'::regclass)
         AND relowner<>(SELECT oid FROM pg_roles WHERE rolname=current_user)) THEN
   RAISE EXCEPTION 'actual dispatch schema/table owner required' USING ERRCODE='42501';
 END IF;
 IF COALESCE((SELECT max(version) FROM public.schema_version),0) NOT IN (29,30)
    OR NOT EXISTS(SELECT 1 FROM public.schema_version WHERE version=29) THEN
   RAISE EXCEPTION 'schema 29 prerequisite or retained schema 30 required';
 END IF;
END $$;
ALTER TABLE public.cases DROP CONSTRAINT cases_state_check;
ALTER TABLE public.cases ADD CONSTRAINT cases_state_check CHECK(state IN ('NEEDS_INPUT','WAITING_CONFIRMATION','REOPENED','CANCELLED'));
ALTER TABLE public.case_local_lifecycles DROP CONSTRAINT case_local_lifecycles_state_check;
ALTER TABLE public.case_local_lifecycles ADD CONSTRAINT case_local_lifecycles_state_check CHECK(state IN ('READY','LOCAL_RECORD_CLOSED','REOPENED','CANCELLED'));
ALTER TABLE public.case_local_lifecycles DROP CONSTRAINT case_local_lifecycles_check;
ALTER TABLE public.case_local_lifecycles ADD CONSTRAINT case_local_lifecycles_check CHECK(
 (state IN ('READY','LOCAL_RECORD_CLOSED') AND verified_snapshot IS NOT NULL AND verified_sha256 IS NOT NULL AND verified_sha256 ~ '^[a-f0-9]{64}$') OR
 (state IN ('REOPENED','CANCELLED') AND verified_snapshot IS NULL AND verified_sha256 IS NULL));
ALTER TABLE public.case_local_events DROP CONSTRAINT case_local_events_action_check;
ALTER TABLE public.case_local_events ADD CONSTRAINT case_local_events_action_check CHECK(action IN ('REVALIDATE','CLOSE_LOCAL_RECORD','REOPEN','CANCEL_BEFORE_ACCEPT'));
INSERT INTO public.schema_version VALUES(30) ON CONFLICT DO NOTHING;
