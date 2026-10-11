-- UNENABLED additive storage proposal; never called by Store.migrate().
-- No production installation, authority/Grant/assignment writes or SQL GRANT.
-- Tests install only with an issued fresh owned synthetic database proof.
ALTER TABLE runs ADD COLUMN native_run_access_protocol jsonb;
ALTER TABLE run_assignments ADD COLUMN native_access jsonb;

CREATE FUNCTION guard_native_run_access_protocol() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE old_events jsonb; new_events jsonb; last_event jsonb; n integer;
        old_leases jsonb; new_leases jsonb; action text; previous_state text;
        request jsonb; previous_request jsonb; lease jsonb;
BEGIN
  IF TG_OP='UPDATE' AND NEW.native_run_access_protocol IS NOT DISTINCT FROM OLD.native_run_access_protocol THEN
    RETURN NEW;
  END IF;
  IF NEW.native_run_access_protocol IS NULL THEN
    IF TG_OP='UPDATE' AND OLD.native_run_access_protocol IS NOT NULL THEN
      RAISE EXCEPTION 'immutable native protocol cannot be removed';
    END IF;
    RETURN NEW;
  END IF;
  IF TG_OP='INSERT' THEN RAISE EXCEPTION 'native protocol must begin with an explicit command'; END IF;
  old_events := coalesce(OLD.native_run_access_protocol->'events','[]'::jsonb);
  new_events := NEW.native_run_access_protocol->'events';
  IF jsonb_typeof(new_events) IS DISTINCT FROM 'array' OR
     NEW.native_run_access_protocol->>'namespace' IS DISTINCT FROM 'ORDINARY_PG_RUN_ACCESS_DECISION_V1' THEN
    RAISE EXCEPTION 'invalid native protocol storage';
  END IF;
  n := jsonb_array_length(new_events);
  IF n <> jsonb_array_length(old_events)+1 OR n > 64 OR
     jsonb_typeof(NEW.native_run_access_protocol->'revision') IS DISTINCT FROM 'number' OR
     (NEW.native_run_access_protocol->>'revision')::integer IS DISTINCT FROM n OR
     NEW.principal_id IS DISTINCT FROM OLD.principal_id OR NEW.park_id IS DISTINCT FROM OLD.park_id OR
     NEW.org_id IS DISTINCT FROM OLD.org_id OR NEW.revision IS DISTINCT FROM OLD.revision THEN
    RAISE EXCEPTION 'native protocol requires exactly one bound immutable event';
  END IF;
  IF EXISTS (SELECT 1 FROM jsonb_array_elements(old_events) WITH ORDINALITY AS e(value,pos)
             WHERE new_events->((pos-1)::integer) IS DISTINCT FROM value) THEN
    RAISE EXCEPTION 'immutable native protocol event prefix';
  END IF;
  last_event := new_events->(n-1);
  IF last_event->>'run_id' IS DISTINCT FROM NEW.id::text OR
     last_event->>'namespace' IS DISTINCT FROM NEW.native_run_access_protocol->>'namespace' OR
     last_event->>'state' IS DISTINCT FROM NEW.native_run_access_protocol->>'state' OR
     jsonb_typeof(last_event->'revision') IS DISTINCT FROM 'number' OR
     (last_event->>'revision')::integer IS DISTINCT FROM n OR
     last_event->'request' IS DISTINCT FROM NEW.native_run_access_protocol->'request' OR
     last_event->'lease_id' IS DISTINCT FROM NEW.native_run_access_protocol->'lease_id' OR
     last_event->'actual_run_access' IS DISTINCT FROM 'false'::jsonb OR
     last_event->'actual_assignment_written' IS DISTINCT FROM 'false'::jsonb OR
     last_event->>'projection_state' IS DISTINCT FROM 'NON_EFFECTIVE' THEN
    RAISE EXCEPTION 'native event and decision must agree and remain non-effective';
  END IF;
  action := last_event->>'action';
  previous_state := coalesce(OLD.native_run_access_protocol->>'state','NOT_REQUESTED');
  IF action IS NULL OR NOT coalesce((
    (action='REQUEST' AND previous_state IN ('NOT_REQUESTED','REJECTED','CANCELLED','REVOKED') AND last_event->>'state'='REQUESTED') OR
    (action='APPROVE' AND previous_state='REQUESTED' AND last_event->>'state'='APPROVED') OR
    (action='REJECT' AND previous_state='REQUESTED' AND last_event->>'state'='REJECTED') OR
    (action='CANCEL' AND previous_state='REQUESTED' AND last_event->>'state'='CANCELLED') OR
    (action='REVOKE' AND previous_state='APPROVED' AND last_event->>'state'='REVOKED')),false) OR
    last_event->>'actor_id' IS NULL OR last_event->>'request_key' IS NULL OR
    last_event->>'request_key' !~ '^[A-Za-z0-9_-]{1,100}$' OR
    last_event->>'fingerprint' IS NULL OR last_event->>'fingerprint' !~ '^[a-f0-9]{64}$' OR
    jsonb_typeof(last_event->'reason') IS DISTINCT FROM 'string' OR
    length(btrim(last_event->>'reason')) NOT BETWEEN 1 AND 1000 THEN
    RAISE EXCEPTION 'invalid native protocol transition or receipt';
  END IF;
  old_leases := coalesce(OLD.native_run_access_protocol->'leases','[]'::jsonb);
  new_leases := NEW.native_run_access_protocol->'leases';
  IF jsonb_typeof(new_leases) IS DISTINCT FROM 'array' OR
     jsonb_array_length(new_leases) IS DISTINCT FROM jsonb_array_length(old_leases)+(CASE WHEN action='APPROVE' THEN 1 ELSE 0 END) OR
     EXISTS (SELECT 1 FROM jsonb_array_elements(old_leases) WITH ORDINALITY AS e(value,pos)
             WHERE new_leases->((pos-1)::integer) IS DISTINCT FROM value) OR
     EXISTS (SELECT 1 FROM jsonb_array_elements(new_leases) e WHERE e->>'state' IS DISTINCT FROM 'NON_EFFECTIVE') THEN
    RAISE EXCEPTION 'immutable non-effective native lease history';
  END IF;
  IF EXISTS (SELECT 1 FROM jsonb_array_elements(old_events) e
             WHERE e->>'actor_id'=last_event->>'actor_id' AND e->>'request_key'=last_event->>'request_key') THEN
    RAISE EXCEPTION 'duplicate native actor request key';
  END IF;
  request := NEW.native_run_access_protocol->'request';
  previous_request := OLD.native_run_access_protocol->'request';
  IF jsonb_typeof(request) IS DISTINCT FROM 'object' OR
     request->>'requester_id' IS DISTINCT FROM NEW.principal_id OR
     request->>'capability' IS DISTINCT FROM 'READ' OR
     request->>'target_role' IS DISTINCT FROM 'service_executor' OR
     request->'source'->>'run_id' IS DISTINCT FROM NEW.id::text OR
     request->'source'->>'park_id' IS DISTINCT FROM NEW.park_id OR
     request->'source'->>'org_id' IS DISTINCT FROM NEW.org_id OR
     request->'source'->>'owner_id' IS DISTINCT FROM NEW.principal_id OR
     jsonb_typeof(request->'requested_validity') IS DISTINCT FROM 'object' OR
     request->'requested_validity'->>'timezone' IS DISTINCT FROM 'UTC' OR
     request->>'request_id' IS NULL OR request->>'target_id' IS NULL THEN
    RAISE EXCEPTION 'invalid exact-scope native request';
  END IF;
  IF action='REQUEST' THEN
    IF last_event->>'actor_id' IS DISTINCT FROM NEW.principal_id OR
       NEW.native_run_access_protocol->'lease_id' IS DISTINCT FROM 'null'::jsonb OR
       request ? 'approver_id' OR request ? 'approved_validity' OR request ? 'approver_authority' THEN
      RAISE EXCEPTION 'native request belongs to owner and begins without a lease';
    END IF;
  ELSIF action='APPROVE' THEN
    lease := new_leases->(jsonb_array_length(new_leases)-1);
    IF (request-'approver_id'-'approved_validity'-'approver_authority') IS DISTINCT FROM previous_request OR
       jsonb_typeof(request->'approver_authority') IS DISTINCT FROM 'object' OR
       request->>'approver_id' IS DISTINCT FROM last_event->>'actor_id' OR
       last_event->>'actor_id' IN (request->>'requester_id',request->>'target_id') OR
       lease->>'id' IS NULL OR lease->>'id' IS DISTINCT FROM NEW.native_run_access_protocol->>'lease_id' OR
       lease->>'request_id' IS DISTINCT FROM request->>'request_id' OR
       lease->'validity' IS DISTINCT FROM request->'approved_validity' OR
       jsonb_typeof(request->'approved_validity') IS DISTINCT FROM 'object' OR
       lease->'source' IS DISTINCT FROM request->'source' THEN
      RAISE EXCEPTION 'independent native decision and bound proposed lease required';
    END IF;
  ELSE
    IF request IS DISTINCT FROM previous_request OR
       NEW.native_run_access_protocol->'lease_id' IS DISTINCT FROM OLD.native_run_access_protocol->'lease_id' OR
       (action='CANCEL' AND last_event->>'actor_id' IS DISTINCT FROM request->>'requester_id') OR
       (action='REJECT' AND last_event->>'actor_id' IN (request->>'requester_id',request->>'target_id')) THEN
      RAISE EXCEPTION 'native cancellation/rejection/revocation preserves the original request';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER native_run_access_append_only BEFORE INSERT OR UPDATE ON runs
FOR EACH ROW EXECUTE FUNCTION guard_native_run_access_protocol();
