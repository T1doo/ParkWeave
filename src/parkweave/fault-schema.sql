-- OPT-IN TEST DATABASE ONLY. Not run by Store.migrate or production roles.sql.
-- Simulated remote effects intentionally commit in a separate transaction.
CREATE TABLE fault_operations (
 id uuid PRIMARY KEY, principal_id text NOT NULL REFERENCES principals,
 park_id text NOT NULL, org_id text NOT NULL,
 request_key text NOT NULL, fingerprint text NOT NULL, payload jsonb NOT NULL,
 state text NOT NULL CHECK(state IN ('PREPARED','DISPATCHED','OUTCOME_UNKNOWN','VERIFIED','FAILED_SAFE','EFFECT_KNOWN_INVALID')),
 intent text NOT NULL DEFAULT 'CONTINUE' CHECK(intent IN ('CONTINUE','PAUSE','CANCEL')),
 fence bigint NOT NULL DEFAULT 0, lease_until timestamptz, receipt jsonb,
 UNIQUE(principal_id,request_key)
);
CREATE TABLE fault_effects (
 operation_id uuid PRIMARY KEY, park_id text NOT NULL, org_id text NOT NULL,
 fingerprint text NOT NULL, receipt jsonb NOT NULL, dispatch_count integer NOT NULL
);
