-- Explicit coordinator-owner installation. Never application bootstrap/auto budget.
CREATE SCHEMA IF NOT EXISTS shared_model_quota;
REVOKE ALL ON SCHEMA shared_model_quota FROM PUBLIC;
CREATE TABLE IF NOT EXISTS shared_model_quota.accounts(
 account text PRIMARY KEY, kind text NOT NULL CHECK(kind IN ('SYNTHETIC','LIVE')),
 approved boolean NOT NULL DEFAULT false, starts timestamptz NOT NULL, ends timestamptz NOT NULL,
 call_limit bigint NOT NULL CHECK(call_limit>=0), token_limit bigint NOT NULL CHECK(token_limit>=0),
 calls bigint NOT NULL DEFAULT 0, tokens bigint NOT NULL DEFAULT 0,
 authorization_evidence text, approved_by text,
 CHECK(ends>starts), CHECK(kind<>'LIVE' OR NOT approved OR
 (length(authorization_evidence) BETWEEN 1 AND 160 AND length(approved_by) BETWEEN 1 AND 120
  AND authorization_evidence IS NOT NULL AND approved_by IS NOT NULL)));
CREATE TABLE IF NOT EXISTS shared_model_quota.products(
 product text PRIMARY KEY, db_role name NOT NULL UNIQUE, account text NOT NULL REFERENCES shared_model_quota.accounts,
 call_limit bigint NOT NULL CHECK(call_limit>=0), token_limit bigint NOT NULL CHECK(token_limit>=0),
 calls bigint NOT NULL DEFAULT 0, tokens bigint NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS shared_model_quota.reservations(
 id uuid PRIMARY KEY, product text NOT NULL REFERENCES shared_model_quota.products, work text NOT NULL,
 reserved bigint NOT NULL, state text NOT NULL CHECK(state IN ('RESERVED','DISPATCHED','SETTLED','OUTCOME_UNKNOWN','RELEASED')),
 outcome text, usage jsonb, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(product,work));
-- Additive coordinator upgrade preserves old budget/attempt records.
ALTER TABLE shared_model_quota.accounts ADD COLUMN IF NOT EXISTS rate_limit integer NOT NULL DEFAULT 30 CHECK(rate_limit BETWEEN 0 AND 30);
ALTER TABLE shared_model_quota.accounts ADD COLUMN IF NOT EXISTS rate_verified boolean NOT NULL DEFAULT false;
ALTER TABLE shared_model_quota.accounts ADD COLUMN IF NOT EXISTS rate_evidence text;
ALTER TABLE shared_model_quota.accounts ADD COLUMN IF NOT EXISTS last_clock timestamptz NOT NULL DEFAULT '-infinity';
ALTER TABLE shared_model_quota.reservations ADD COLUMN IF NOT EXISTS account text REFERENCES shared_model_quota.accounts;
UPDATE shared_model_quota.reservations r SET account=p.account FROM shared_model_quota.products p WHERE r.product=p.product AND r.account IS NULL;
ALTER TABLE shared_model_quota.reservations ALTER COLUMN account SET NOT NULL;
ALTER TABLE shared_model_quota.reservations ADD COLUMN IF NOT EXISTS rate_state text CHECK(rate_state IN ('HELD','IN_FLIGHT','COOLDOWN','RELEASED'));
ALTER TABLE shared_model_quota.reservations ADD COLUMN IF NOT EXISTS rate_denials integer NOT NULL DEFAULT 0;
ALTER TABLE shared_model_quota.reservations ADD COLUMN IF NOT EXISTS generation integer NOT NULL DEFAULT 1;
ALTER TABLE shared_model_quota.reservations ADD COLUMN IF NOT EXISTS held_at timestamptz;
ALTER TABLE shared_model_quota.reservations ADD COLUMN IF NOT EXISTS dispatched_at timestamptz;
ALTER TABLE shared_model_quota.reservations ADD COLUMN IF NOT EXISTS finished_at timestamptz;
-- Old sent records are conservatively unresolved; no automatic unmeasured expiry.
UPDATE shared_model_quota.reservations SET rate_state='IN_FLIGHT' WHERE rate_state IS NULL AND state IN ('DISPATCHED','SETTLED','OUTCOME_UNKNOWN');
CREATE INDEX IF NOT EXISTS quota_rate_account ON shared_model_quota.reservations(account,rate_state,finished_at);
CREATE TABLE IF NOT EXISTS shared_model_quota.synthetic_clock(account text PRIMARY KEY REFERENCES shared_model_quota.accounts, at timestamptz NOT NULL);
CREATE TABLE IF NOT EXISTS shared_model_quota.events(id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 reservation_id uuid NOT NULL REFERENCES shared_model_quota.reservations,event text NOT NULL, at timestamptz NOT NULL);
-- Owner-provisioned live worker facts. No application installer inserts or
-- approves these rows; absent/expired facts keep the normal worker offline.
CREATE TABLE IF NOT EXISTS shared_model_quota.live_worker_approvals(
 product text PRIMARY KEY REFERENCES shared_model_quota.products,
 account text NOT NULL REFERENCES shared_model_quota.accounts,
 coordinator_id uuid NOT NULL,
 approved boolean NOT NULL DEFAULT false,
 starts timestamptz NOT NULL, ends timestamptz NOT NULL CHECK(ends>starts),
 approved_by text NOT NULL CHECK(length(approved_by) BETWEEN 1 AND 120),
 injection_evidence text NOT NULL CHECK(length(injection_evidence) BETWEEN 1 AND 160));
ALTER TABLE shared_model_quota.events ADD COLUMN IF NOT EXISTS generation integer NOT NULL DEFAULT 1;
-- Remove old callable signatures: stale unsent handles must not operate a reopened attempt.
DROP FUNCTION IF EXISTS shared_model_quota.hold_rate(uuid);
DROP FUNCTION IF EXISTS shared_model_quota.transition(uuid,text,text,jsonb);
CREATE OR REPLACE FUNCTION shared_model_quota.time_for(a text) RETURNS timestamptz
 LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog AS $$
 SELECT CASE WHEN q.kind='SYNTHETIC' THEN coalesce(c.at,clock_timestamp()) ELSE clock_timestamp() END
 FROM shared_model_quota.accounts q LEFT JOIN shared_model_quota.synthetic_clock c ON c.account=q.account WHERE q.account=a
$$;
CREATE OR REPLACE FUNCTION shared_model_quota._reserve(p text,a text,w text,n bigint,k text) RETURNS jsonb
 LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE b shared_model_quota.products; q shared_model_quota.accounts; r shared_model_quota.reservations; t timestamptz;
BEGIN
 IF current_user<>(SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='shared_model_quota')
 THEN RAISE EXCEPTION 'COORDINATOR_OWNER_FUNCTION_REQUIRED'; END IF;
 SELECT * INTO b FROM shared_model_quota.products WHERE product=p AND db_role=session_user;
 IF NOT FOUND OR b.account<>a THEN RAISE EXCEPTION 'QUOTA_BINDING_DENIED'; END IF;
 SELECT * INTO q FROM shared_model_quota.accounts WHERE account=a FOR UPDATE;
 SELECT * INTO b FROM shared_model_quota.products WHERE product=p FOR UPDATE;
 SELECT * INTO r FROM shared_model_quota.reservations WHERE product=p AND work=w;
 IF FOUND AND r.account<>a THEN RAISE EXCEPTION 'QUOTA_BINDING_DENIED'; END IF;
 IF FOUND AND r.state<>'RELEASED' THEN RETURN to_jsonb(r); END IF;
 t=shared_model_quota.time_for(a);
 IF n<>8192 OR length(w)>160 OR k IS NULL OR k NOT IN ('SYNTHETIC','LIVE') OR NOT q.approved OR q.kind<>k
 OR t<q.starts OR t>=q.ends OR q.calls+1>q.call_limit OR q.tokens+n>q.token_limit
 OR b.calls+1>b.call_limit OR b.tokens+n>b.token_limit OR t<q.last_clock
 OR (q.kind='LIVE' AND (NOT q.rate_verified OR coalesce(length(q.rate_evidence),0)=0))
 THEN RAISE EXCEPTION 'QUOTA_UNAUTHORIZED_OR_EXHAUSTED'; END IF;
 UPDATE shared_model_quota.accounts SET calls=calls+1,tokens=tokens+n,last_clock=t WHERE account=a;
 UPDATE shared_model_quota.products SET calls=calls+1,tokens=tokens+n WHERE product=p;
 IF r.id IS NULL THEN
   INSERT INTO shared_model_quota.reservations(id,product,work,reserved,state,account,created_at)
    VALUES(gen_random_uuid(),p,w,n,'RESERVED',a,t) RETURNING * INTO r;
 ELSE
   UPDATE shared_model_quota.reservations SET state='RESERVED',outcome=NULL,usage=NULL,rate_state=NULL,
      held_at=NULL,dispatched_at=NULL,finished_at=NULL,generation=generation+1 WHERE id=r.id RETURNING * INTO r;
 END IF;
 INSERT INTO shared_model_quota.events(reservation_id,event,at,generation) VALUES(r.id,'BUDGET_RESERVED',t,r.generation);
 RETURN to_jsonb(r);
END $$;
CREATE OR REPLACE FUNCTION shared_model_quota._hold_rate(i uuid,g integer) RETURNS jsonb
 LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE r shared_model_quota.reservations; q shared_model_quota.accounts; t timestamptz; used bigint; pending boolean; retry timestamptz;
BEGIN
 IF current_user<>(SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='shared_model_quota')
 THEN RAISE EXCEPTION 'COORDINATOR_OWNER_FUNCTION_REQUIRED'; END IF;
 SELECT x.* INTO r FROM shared_model_quota.reservations x JOIN shared_model_quota.products p ON p.product=x.product
 WHERE x.id=i AND p.db_role=session_user;
 IF NOT FOUND THEN RAISE EXCEPTION 'QUOTA_BINDING_DENIED'; END IF;
 SELECT * INTO q FROM shared_model_quota.accounts WHERE account=r.account FOR UPDATE;
 SELECT * INTO r FROM shared_model_quota.reservations WHERE id=i FOR UPDATE;
 IF g IS NULL OR g<>r.generation THEN RAISE EXCEPTION 'STALE_QUOTA_GENERATION'; END IF;
 t=shared_model_quota.time_for(r.account);
 IF t<q.last_clock OR NOT q.approved OR t<q.starts OR t>=q.ends OR r.state<>'RESERVED'
 OR (q.kind='LIVE' AND (NOT q.rate_verified OR coalesce(length(q.rate_evidence),0)=0))
 THEN RAISE EXCEPTION 'RATE_AUTHORIZATION_DENIED'; END IF;
 UPDATE shared_model_quota.accounts SET last_clock=t WHERE account=r.account;
 IF r.rate_state='HELD' THEN RETURN jsonb_build_object('admitted',true); END IF;
 SELECT count(*),coalesce(bool_or(rate_state IN ('HELD','IN_FLIGHT')),false),min(finished_at+interval '60 seconds')
 INTO used,pending,retry FROM shared_model_quota.reservations WHERE account=r.account
 AND (rate_state IN ('HELD','IN_FLIGHT') OR (rate_state='COOLDOWN' AND finished_at>t-interval '60 seconds'));
 IF used>=q.rate_limit THEN
   UPDATE shared_model_quota.reservations SET rate_denials=rate_denials+1 WHERE id=i RETURNING * INTO r;
   INSERT INTO shared_model_quota.events(reservation_id,event,at,generation) VALUES(i,'RATE_DENIED_NOT_SENT',t,r.generation);
   RETURN jsonb_build_object('admitted',false,'retry_at',CASE WHEN pending THEN NULL ELSE retry END,
                            'retry_after_seconds',CASE WHEN pending OR retry IS NULL THEN NULL ELSE greatest(0,extract(epoch FROM retry-t)) END,'denials',r.rate_denials);
 END IF;
 UPDATE shared_model_quota.reservations SET rate_state='HELD',held_at=t WHERE id=i;
 INSERT INTO shared_model_quota.events(reservation_id,event,at,generation) VALUES(i,'RATE_HELD_NOT_SENT',t,r.generation);
 RETURN jsonb_build_object('admitted',true);
END $$;
CREATE OR REPLACE FUNCTION shared_model_quota._transition(i uuid,g integer,s text,o text,u jsonb) RETURNS jsonb
 LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE b shared_model_quota.products; r shared_model_quota.reservations; q shared_model_quota.accounts; delta bigint; t timestamptz;
BEGIN
 IF current_user<>(SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='shared_model_quota')
 THEN RAISE EXCEPTION 'COORDINATOR_OWNER_FUNCTION_REQUIRED'; END IF;
 SELECT p.* INTO b FROM shared_model_quota.products p JOIN shared_model_quota.reservations x ON x.product=p.product
 WHERE x.id=i AND p.db_role=session_user;
 IF NOT FOUND THEN RAISE EXCEPTION 'QUOTA_BINDING_DENIED'; END IF;
 SELECT * INTO r FROM shared_model_quota.reservations WHERE id=i;
 SELECT * INTO q FROM shared_model_quota.accounts WHERE account=r.account FOR UPDATE;
 SELECT * INTO r FROM shared_model_quota.reservations WHERE id=i FOR UPDATE;
 IF g IS NULL OR g<>r.generation THEN RAISE EXCEPTION 'STALE_QUOTA_GENERATION'; END IF;
 t=shared_model_quota.time_for(r.account);
 IF s<>'DISPATCHED' AND r.state=s AND r.outcome IS NOT DISTINCT FROM o AND r.usage IS NOT DISTINCT FROM u THEN RETURN to_jsonb(r); END IF;
 IF s='DISPATCHED' AND r.state='RESERVED' AND r.rate_state='HELD' THEN
   IF t<q.last_clock OR NOT q.approved OR t<q.starts OR t>=q.ends OR b.account<>r.account
    OR (SELECT count(*) FROM shared_model_quota.reservations WHERE account=r.account AND
        (rate_state IN ('HELD','IN_FLIGHT') OR (rate_state='COOLDOWN' AND finished_at>t-interval '60 seconds')))>q.rate_limit
    OR (q.kind='LIVE' AND (NOT q.rate_verified OR coalesce(length(q.rate_evidence),0)=0))
    THEN RAISE EXCEPTION 'RATE_AUTHORIZATION_DENIED'; END IF;
   UPDATE shared_model_quota.accounts SET last_clock=t WHERE account=r.account;
   UPDATE shared_model_quota.reservations SET rate_state='IN_FLIGHT',dispatched_at=t WHERE id=i;
 ELSIF s='RELEASED' AND r.state='RESERVED' AND u IS NULL THEN
   UPDATE shared_model_quota.accounts SET calls=calls-1,tokens=tokens-r.reserved WHERE account=r.account;
   UPDATE shared_model_quota.products SET calls=calls-1,tokens=tokens-r.reserved WHERE product=b.product;
   UPDATE shared_model_quota.reservations SET rate_state='RELEASED' WHERE id=i;
 ELSIF s IN ('SETTLED','OUTCOME_UNKNOWN') AND r.state='DISPATCHED' THEN
   IF u IS NOT NULL THEN
     IF s<>'SETTLED' OR jsonb_typeof(u)<>'object' OR NOT(u ?& ARRAY['prompt_tokens','completion_tokens','total_tokens'])
       OR (SELECT count(*) FROM jsonb_object_keys(u))<>3
       OR (u->>'prompt_tokens')!~'^[0-9]+$' OR (u->>'completion_tokens')!~'^[0-9]+$' OR (u->>'total_tokens')!~'^[0-9]+$'
       OR (u->>'prompt_tokens')::bigint+(u->>'completion_tokens')::bigint<>(u->>'total_tokens')::bigint
       THEN RAISE EXCEPTION 'INVALID_USAGE'; END IF;
     delta=(u->>'total_tokens')::bigint-r.reserved;
     UPDATE shared_model_quota.accounts SET tokens=tokens+delta WHERE account=r.account;
     UPDATE shared_model_quota.products SET tokens=tokens+delta WHERE product=b.product;
   ELSIF s<>'OUTCOME_UNKNOWN' THEN RAISE EXCEPTION 'UNKNOWN_USAGE_RETAINS_RESERVATION'; END IF;
   -- Never age an in-flight attempt out. Completion-time cooldown is conservative.
   t=greatest(t,q.last_clock);
   UPDATE shared_model_quota.reservations SET rate_state='COOLDOWN',finished_at=t WHERE id=i;
   UPDATE shared_model_quota.accounts SET last_clock=t WHERE account=r.account;
 ELSE RAISE EXCEPTION 'QUOTA_REPLAY_DENIED'; END IF;
 IF o IS NOT NULL AND o!~'^[A-Z_]{1,80}$' THEN RAISE EXCEPTION 'INVALID_OUTCOME'; END IF;
 UPDATE shared_model_quota.reservations SET state=s,outcome=o,usage=u WHERE id=i RETURNING * INTO r;
 INSERT INTO shared_model_quota.events(reservation_id,event,at,generation) VALUES(i,s,t,r.generation);
 RETURN to_jsonb(r);
END $$;
-- Preserve the public synthetic API and all existing settlement/release paths.
-- LIVE reserve/send requires the source-bound worker wrappers below. Private
-- implementations are invoker functions and additionally check current_user;
-- even an old broad EXECUTE grant does not turn them into an application bypass.
CREATE OR REPLACE FUNCTION shared_model_quota.reserve(p text,a text,w text,n bigint,k text) RETURNS jsonb
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
 IF k IS DISTINCT FROM 'SYNTHETIC' THEN RAISE EXCEPTION 'LIVE_WORKER_BINDING_REQUIRED'; END IF;
 RETURN shared_model_quota._reserve(p,a,w,n,k);
END $$;
CREATE OR REPLACE FUNCTION shared_model_quota.hold_rate(i uuid,g integer) RETURNS jsonb
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM shared_model_quota.reservations r JOIN shared_model_quota.accounts a ON a.account=r.account
   WHERE r.id=i AND a.kind='LIVE') THEN RAISE EXCEPTION 'LIVE_WORKER_BINDING_REQUIRED'; END IF;
 RETURN shared_model_quota._hold_rate(i,g);
END $$;
CREATE OR REPLACE FUNCTION shared_model_quota.transition(i uuid,g integer,s text,o text,u jsonb) RETURNS jsonb
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
 IF s='DISPATCHED' AND EXISTS(SELECT 1 FROM shared_model_quota.reservations r JOIN shared_model_quota.accounts a ON a.account=r.account
   WHERE r.id=i AND a.kind='LIVE') THEN RAISE EXCEPTION 'LIVE_WORKER_BINDING_REQUIRED'; END IF;
 RETURN shared_model_quota._transition(i,g,s,o,u);
END $$;
CREATE OR REPLACE FUNCTION shared_model_quota.live_worker_status(p text,a text,i uuid) RETURNS jsonb
 LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog AS $$
 SELECT jsonb_build_object(
 'budget_authorized',coalesce(q.kind='LIVE' AND q.approved AND clock_timestamp()>=q.starts AND clock_timestamp()<q.ends
   AND coalesce(length(q.authorization_evidence),0)>0 AND coalesce(length(q.approved_by),0)>0
   AND q.call_limit>0 AND q.token_limit>=8192 AND b.call_limit>0 AND b.token_limit>=8192
   AND q.calls<=q.call_limit AND q.tokens<=q.token_limit AND b.calls<=b.call_limit AND b.tokens<=b.token_limit,false),
 'injection_authorized',coalesce(x.approved AND clock_timestamp()>=x.starts AND clock_timestamp()<x.ends
   AND length(x.approved_by)>0 AND length(x.injection_evidence)>0,false),
 'rate_verified',coalesce(q.rate_verified AND length(q.rate_evidence)>0 AND q.rate_limit BETWEEN 1 AND 30,false),
 'shared_binding_verified',coalesce(b.account=a AND x.account=a AND x.coordinator_id=i,false))
 FROM (SELECT 1) anchor
 LEFT JOIN shared_model_quota.products b ON b.product=p AND b.db_role=session_user
 LEFT JOIN shared_model_quota.accounts q ON q.account=b.account AND q.account=a
 LEFT JOIN shared_model_quota.live_worker_approvals x ON x.product=b.product
$$;
CREATE OR REPLACE FUNCTION shared_model_quota.require_live_worker(p text,a text,i uuid) RETURNS void
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE facts jsonb;
BEGIN
 -- Keep owner revocation and the following reserve/dispatch in one ordered
 -- transaction. This does not authorize a request after it was dispatched.
 PERFORM 1 FROM shared_model_quota.live_worker_approvals WHERE product=p FOR SHARE;
 facts=shared_model_quota.live_worker_status(p,a,i);
 IF EXISTS(SELECT 1 FROM jsonb_each(facts) WHERE value<>'true'::jsonb)
 THEN RAISE EXCEPTION 'LIVE_WORKER_NOT_AUTHORIZED'; END IF;
END $$;
CREATE OR REPLACE FUNCTION shared_model_quota.reserve_for_worker(p text,a text,w text,n bigint,i uuid) RETURNS jsonb
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
 PERFORM shared_model_quota.require_live_worker(p,a,i);
 RETURN shared_model_quota._reserve(p,a,w,n,'LIVE');
END $$;
CREATE OR REPLACE FUNCTION shared_model_quota.dispatch_for_worker(i uuid,g integer,binding uuid) RETURNS jsonb
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE r shared_model_quota.reservations; held jsonb;
BEGIN
 SELECT x.* INTO r FROM shared_model_quota.reservations x
 JOIN shared_model_quota.products p ON p.product=x.product AND p.db_role=session_user WHERE x.id=i;
 IF NOT FOUND THEN RAISE EXCEPTION 'QUOTA_BINDING_DENIED'; END IF;
 PERFORM shared_model_quota.require_live_worker(r.product,r.account,binding);
 held=shared_model_quota._hold_rate(i,g);
 IF NOT (held->>'admitted')::boolean THEN
   PERFORM shared_model_quota._transition(i,g,'RELEASED','NOT_SENT',NULL);
   RETURN held;
 END IF;
 RETURN shared_model_quota._transition(i,g,'DISPATCHED',NULL,NULL);
END $$;
REVOKE ALL ON ALL TABLES IN SCHEMA shared_model_quota FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA shared_model_quota FROM PUBLIC;
