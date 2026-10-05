-- Local synthetic resource holds only; not formal or external reservations.
CREATE TABLE IF NOT EXISTS synthetic_resources (
 id uuid PRIMARY KEY, park_id text NOT NULL, name text NOT NULL,
 revision integer NOT NULL CHECK(revision>0), capacity integer NOT NULL CHECK(capacity BETWEEN 1 AND 20),
 buffer_seconds integer NOT NULL CHECK(buffer_seconds BETWEEN 0 AND 1800),
 open_from timestamptz NOT NULL, open_until timestamptz NOT NULL CHECK(open_until>open_from),
 enabled boolean NOT NULL DEFAULT true, timezone text NOT NULL CHECK(timezone='UTC'),
 namespace text NOT NULL CHECK(namespace='SYNTHETIC'),
 authority text NOT NULL CHECK(authority='LOCAL_AUTHORITY'), source jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS synthetic_resource_grants (
 principal_id text NOT NULL REFERENCES principals, resource_id uuid NOT NULL REFERENCES synthetic_resources,
 park_id text NOT NULL, org_id text NOT NULL,
 capability text NOT NULL CHECK(capability IN ('READ','HOLD')), active boolean NOT NULL DEFAULT true,
 PRIMARY KEY(principal_id,resource_id,capability)
);
CREATE TABLE IF NOT EXISTS synthetic_resource_holds (
 id uuid PRIMARY KEY, resource_id uuid NOT NULL REFERENCES synthetic_resources,
 principal_id text NOT NULL REFERENCES principals, park_id text NOT NULL, org_id text NOT NULL,
 resource_revision integer NOT NULL CHECK(resource_revision>0),
 starts_at timestamptz NOT NULL, ends_at timestamptz NOT NULL CHECK(ends_at>starts_at),
 quantity integer NOT NULL CHECK(quantity BETWEEN 1 AND 20),
 buffer_seconds integer NOT NULL CHECK(buffer_seconds BETWEEN 0 AND 1800),
 purpose text NOT NULL CHECK(length(purpose) BETWEEN 1 AND 200),
 state text NOT NULL CHECK(state IN ('HELD','RELEASED')),
 created_at timestamptz NOT NULL, expires_at timestamptz NOT NULL CHECK(expires_at>created_at),
 namespace text NOT NULL CHECK(namespace='SYNTHETIC')
);
CREATE INDEX IF NOT EXISTS synthetic_hold_window ON synthetic_resource_holds(resource_id,state,expires_at);
CREATE TABLE IF NOT EXISTS synthetic_resource_receipts (
 id uuid PRIMARY KEY, hold_id uuid NOT NULL REFERENCES synthetic_resource_holds,
 actor_id text NOT NULL REFERENCES principals, request_key text NOT NULL, fingerprint text NOT NULL,
 action text NOT NULL CHECK(action IN ('HOLD','RELEASE')), payload jsonb NOT NULL,
 UNIQUE(actor_id,request_key)
);
INSERT INTO schema_version VALUES(10) ON CONFLICT DO NOTHING;
