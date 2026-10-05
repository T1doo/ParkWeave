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
CREATE OR REPLACE FUNCTION shared_model_quota.reserve(p text,a text,w text,n bigint,k text) RETURNS jsonb
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE b shared_model_quota.products; q shared_model_quota.accounts; r shared_model_quota.reservations;
BEGIN
 SELECT * INTO b FROM shared_model_quota.products WHERE product=p AND db_role=session_user;
 IF NOT FOUND OR b.account<>a THEN RAISE EXCEPTION 'QUOTA_BINDING_DENIED'; END IF;
 SELECT * INTO q FROM shared_model_quota.accounts WHERE account=a FOR UPDATE;
 SELECT * INTO b FROM shared_model_quota.products WHERE product=p FOR UPDATE;
 SELECT * INTO r FROM shared_model_quota.reservations WHERE product=p AND work=w;
 IF FOUND THEN RETURN to_jsonb(r); END IF;
 IF n<>8192 OR length(w)>160 OR k NOT IN ('SYNTHETIC','LIVE') OR NOT q.approved OR q.kind<>k
 OR clock_timestamp()<q.starts OR clock_timestamp()>=q.ends OR q.calls+1>q.call_limit
 OR q.tokens+n>q.token_limit OR b.calls+1>b.call_limit OR b.tokens+n>b.token_limit
 THEN RAISE EXCEPTION 'QUOTA_UNAUTHORIZED_OR_EXHAUSTED'; END IF;
 UPDATE shared_model_quota.accounts SET calls=calls+1,tokens=tokens+n WHERE account=a;
 UPDATE shared_model_quota.products SET calls=calls+1,tokens=tokens+n WHERE product=p;
 INSERT INTO shared_model_quota.reservations VALUES(gen_random_uuid(),p,w,n,'RESERVED',NULL,NULL,clock_timestamp()) RETURNING * INTO r;
 RETURN to_jsonb(r);
END $$;
CREATE OR REPLACE FUNCTION shared_model_quota.transition(i uuid,s text,o text,u jsonb) RETURNS jsonb
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE b shared_model_quota.products; r shared_model_quota.reservations; delta bigint;
BEGIN
 SELECT p.* INTO b FROM shared_model_quota.products p JOIN shared_model_quota.reservations x ON x.product=p.product
 WHERE x.id=i AND p.db_role=session_user;
 IF NOT FOUND THEN RAISE EXCEPTION 'QUOTA_BINDING_DENIED'; END IF;
 PERFORM 1 FROM shared_model_quota.accounts WHERE account=b.account FOR UPDATE;
 SELECT * INTO r FROM shared_model_quota.reservations WHERE id=i FOR UPDATE;
 IF s<>'DISPATCHED' AND r.state=s AND r.outcome IS NOT DISTINCT FROM o AND r.usage IS NOT DISTINCT FROM u THEN RETURN to_jsonb(r); END IF;
 IF s='DISPATCHED' AND r.state='RESERVED' THEN
   IF NOT EXISTS(SELECT 1 FROM shared_model_quota.accounts WHERE account=b.account AND approved
                 AND starts<=clock_timestamp() AND ends>clock_timestamp()) THEN RAISE EXCEPTION 'QUOTA_EXPIRED'; END IF;
 ELSIF s='RELEASED' AND r.state='RESERVED' AND u IS NULL THEN
   UPDATE shared_model_quota.accounts SET calls=calls-1,tokens=tokens-r.reserved WHERE account=b.account;
   UPDATE shared_model_quota.products SET calls=calls-1,tokens=tokens-r.reserved WHERE product=b.product;
 ELSIF s IN ('SETTLED','OUTCOME_UNKNOWN') AND r.state='DISPATCHED' THEN
   IF u IS NOT NULL THEN
     IF s<>'SETTLED' OR jsonb_typeof(u)<>'object' OR NOT(u ?& ARRAY['prompt_tokens','completion_tokens','total_tokens'])
       OR (SELECT count(*) FROM jsonb_object_keys(u))<>3
       OR (u->>'prompt_tokens')!~'^[0-9]+$' OR (u->>'completion_tokens')!~'^[0-9]+$' OR (u->>'total_tokens')!~'^[0-9]+$'
       OR (u->>'prompt_tokens')::bigint+(u->>'completion_tokens')::bigint<>(u->>'total_tokens')::bigint
       THEN RAISE EXCEPTION 'INVALID_USAGE'; END IF;
     delta=(u->>'total_tokens')::bigint-r.reserved;
     UPDATE shared_model_quota.accounts SET tokens=tokens+delta WHERE account=b.account;
     UPDATE shared_model_quota.products SET tokens=tokens+delta WHERE product=b.product;
   ELSIF s<>'OUTCOME_UNKNOWN' THEN RAISE EXCEPTION 'UNKNOWN_USAGE_RETAINS_RESERVATION'; END IF;
 ELSE RAISE EXCEPTION 'QUOTA_REPLAY_DENIED'; END IF;
 IF o IS NOT NULL AND o!~'^[A-Z_]{1,80}$' THEN RAISE EXCEPTION 'INVALID_OUTCOME'; END IF;
 UPDATE shared_model_quota.reservations SET state=s,outcome=o,usage=u WHERE id=i RETURNING * INTO r;
 RETURN to_jsonb(r);
END $$;
REVOKE ALL ON ALL TABLES IN SCHEMA shared_model_quota FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA shared_model_quota FROM PUBLIC;
