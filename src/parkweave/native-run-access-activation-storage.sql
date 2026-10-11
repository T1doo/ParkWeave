-- UNENABLED owned-fixture activation storage; never part of Store.migrate().
-- No SQL privilege/Grant changes. Production installation is NOT authorized.
ALTER TABLE runs ADD COLUMN native_run_access_activation jsonb;

CREATE FUNCTION guard_native_run_access_activation() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE old_events jsonb; events jsonb; event jsonb; n integer; binding jsonb;
BEGIN
  IF TG_OP='INSERT' THEN
    IF NEW.native_run_access_activation IS NOT NULL THEN RAISE EXCEPTION 'native activation must begin with an explicit command'; END IF;
    RETURN NEW;
  END IF;
  IF NEW.native_run_access_activation IS NOT DISTINCT FROM OLD.native_run_access_activation THEN RETURN NEW; END IF;
  IF NEW.native_run_access_activation IS NULL THEN RAISE EXCEPTION 'immutable native activation cannot be removed'; END IF;
  old_events:=coalesce(OLD.native_run_access_activation->'events','[]'::jsonb);
  events:=NEW.native_run_access_activation->'events';
  IF jsonb_typeof(events) IS DISTINCT FROM 'array' OR
     NEW.native_run_access_activation->>'namespace' IS DISTINCT FROM 'ORDINARY_PG_RUN_ACCESS_ACTIVATION_V1' THEN
    RAISE EXCEPTION 'invalid native activation ledger';
  END IF;
  n:=jsonb_array_length(events);
  IF n<>jsonb_array_length(old_events)+1 OR n>64 OR
     jsonb_typeof(NEW.native_run_access_activation->'revision') IS DISTINCT FROM 'number' OR
     (NEW.native_run_access_activation->>'revision')::integer IS DISTINCT FROM n OR
     NEW.id IS DISTINCT FROM OLD.id OR NEW.revision IS DISTINCT FROM OLD.revision OR
     NEW.park_id IS DISTINCT FROM OLD.park_id OR NEW.org_id IS DISTINCT FROM OLD.org_id OR
     NEW.principal_id IS DISTINCT FROM OLD.principal_id OR
     EXISTS(SELECT 1 FROM jsonb_array_elements(old_events) WITH ORDINALITY e(value,pos)
            WHERE events->((pos-1)::integer) IS DISTINCT FROM value) THEN
    RAISE EXCEPTION 'native activation requires one immutable bound event';
  END IF;
  event:=events->(n-1);binding:=event->'binding';
  IF event->>'namespace' IS DISTINCT FROM NEW.native_run_access_activation->>'namespace' OR
     event->>'run_id' IS DISTINCT FROM NEW.id::text OR event->>'actor_id' IS DISTINCT FROM NEW.principal_id OR
     event->>'action' IS DISTINCT FROM 'ACTIVATE' OR event->>'state' IS DISTINCT FROM 'ACTIVATED' OR
     jsonb_typeof(event->'revision') IS DISTINCT FROM 'number' OR
     (event->>'revision')::integer IS DISTINCT FROM n OR
     event->>'activation_id' IS NULL OR
     event->>'activation_id' IS DISTINCT FROM NEW.native_run_access_activation->>'activation_id' OR
     event->>'policy_sha256' IS NULL OR event->>'policy_sha256' !~ '^[a-f0-9]{64}$' OR
     event->>'fingerprint' IS NULL OR event->>'fingerprint' !~ '^[a-f0-9]{64}$' OR
     event->>'request_key' IS NULL OR event->>'request_key' !~ '^[A-Za-z0-9_-]{1,100}$' OR
     jsonb_typeof(event->'reason') IS DISTINCT FROM 'string' OR length(btrim(event->>'reason')) NOT BETWEEN 1 AND 1000 OR
     event->'actual_run_access' IS DISTINCT FROM 'true'::jsonb OR
     event->'actual_assignment_written' IS DISTINCT FROM 'true'::jsonb OR
     event->>'projection_state' IS DISTINCT FROM 'ACTIVE_SYNTHETIC_FIXTURE' OR
     event->'production_policy_adopted' IS DISTINCT FROM 'false'::jsonb OR
     EXISTS(SELECT 1 FROM jsonb_array_elements(old_events) e
            WHERE (e->>'actor_id'=event->>'actor_id' AND e->>'request_key'=event->>'request_key') OR
                  e->>'activation_id'=event->>'activation_id' OR e->>'lease_id'=event->>'lease_id') THEN
    RAISE EXCEPTION 'invalid immutable native activation receipt';
  END IF;
  IF NEW.native_run_access_protocol->>'state' IS DISTINCT FROM 'APPROVED' OR
     event->>'lease_id' IS DISTINCT FROM NEW.native_run_access_protocol->>'lease_id' OR
     jsonb_typeof(binding) IS DISTINCT FROM 'object' OR
     binding->>'namespace' IS DISTINCT FROM event->>'namespace' OR
     binding->>'run_id' IS DISTINCT FROM NEW.id::text OR binding->>'owner_id' IS DISTINCT FROM NEW.principal_id OR
     binding->>'lease_id' IS DISTINCT FROM event->>'lease_id' OR binding->>'capability' IS DISTINCT FROM 'READ' OR
     binding->'protocol_revision' IS DISTINCT FROM NEW.native_run_access_protocol->'revision' OR
     binding->>'request_id' IS DISTINCT FROM NEW.native_run_access_protocol->'request'->>'request_id' OR
     binding->>'executor_id' IS DISTINCT FROM NEW.native_run_access_protocol->'request'->>'target_id' OR
     binding->>'approver_id' IS DISTINCT FROM NEW.native_run_access_protocol->'request'->>'approver_id' OR
     binding->'validity' IS DISTINCT FROM NEW.native_run_access_protocol->'request'->'approved_validity' OR
     binding->'source' IS DISTINCT FROM NEW.native_run_access_protocol->'request'->'source' OR
     binding->'authority' IS DISTINCT FROM NEW.native_run_access_protocol->'request'->'authority' OR
     binding->'approver_authority' IS DISTINCT FROM NEW.native_run_access_protocol->'request'->'approver_authority' OR
     jsonb_typeof(binding->'authority_generations') IS DISTINCT FROM 'object' OR
     jsonb_typeof(binding->'approver_authority') IS DISTINCT FROM 'object' THEN
    RAISE EXCEPTION 'activation requires exact independently approved lease binding';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER native_activation_append_only BEFORE INSERT OR UPDATE ON runs
FOR EACH ROW EXECUTE FUNCTION guard_native_run_access_activation();

CREATE FUNCTION guard_native_assignment() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE ledger jsonb; event jsonb; marker jsonb;
BEGIN
  IF TG_OP='DELETE' THEN
    IF OLD.native_access IS NOT NULL OR EXISTS(SELECT 1 FROM runs r CROSS JOIN LATERAL
         jsonb_array_elements(coalesce(r.native_run_access_activation->'events','[]'::jsonb)) e
         WHERE r.id=OLD.run_id AND e->'binding'->>'executor_id'=OLD.principal_id) THEN
      RAISE EXCEPTION 'native assignment provenance cannot be deleted';
    END IF;
    RETURN OLD;
  END IF;
  IF NEW.native_access IS NULL THEN
    IF TG_OP='UPDATE' AND OLD.native_access IS NOT NULL THEN RAISE EXCEPTION 'native assignment cannot become legacy'; END IF;
    IF EXISTS(SELECT 1 FROM runs r CROSS JOIN LATERAL
         jsonb_array_elements(coalesce(r.native_run_access_activation->'events','[]'::jsonb)) e
         WHERE r.id=NEW.run_id AND e->'binding'->>'executor_id'=NEW.principal_id) THEN
      RAISE EXCEPTION 'historical native assignment cannot become legacy';
    END IF;
    RETURN NEW;
  END IF;
  SELECT native_run_access_activation INTO ledger FROM runs WHERE id=NEW.run_id
    AND park_id=NEW.park_id AND org_id=NEW.org_id;
  event:=ledger->'events'->(jsonb_array_length(ledger->'events')-1);
  marker:=jsonb_build_object('namespace','ORDINARY_PG_RUN_ACCESS_ACTIVATION_V1',
    'activation_id',event->'activation_id','lease_id',event->'lease_id',
    'policy_sha256',event->'policy_sha256','binding',event->'binding');
  IF event IS NULL OR jsonb_typeof(NEW.native_access) IS DISTINCT FROM 'object' OR
     NEW.native_access IS DISTINCT FROM marker OR event->'binding'->>'executor_id' IS DISTINCT FROM NEW.principal_id OR
     event->'binding'->'source'->>'park_id' IS DISTINCT FROM NEW.park_id OR
     event->'binding'->'source'->>'org_id' IS DISTINCT FROM NEW.org_id OR
     coalesce(to_jsonb(NEW)->'managed_access','null'::jsonb) IS DISTINCT FROM 'null'::jsonb THEN
    RAISE EXCEPTION 'native assignment requires exact atomic activation receipt';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER native_assignment_bound BEFORE INSERT OR UPDATE OR DELETE ON run_assignments
FOR EACH ROW EXECUTE FUNCTION guard_native_assignment();
