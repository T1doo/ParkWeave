-- F2 parallel SYNTHETIC material-preparation slice; not phase admission.
CREATE TABLE IF NOT EXISTS preparation_catalog (
 park_id text NOT NULL, service_id text NOT NULL, version integer NOT NULL CHECK(version>0),
 name text NOT NULL, source jsonb NOT NULL,
 namespace text NOT NULL CHECK(namespace='SYNTHETIC'),
 qualification text NOT NULL CHECK(qualification='NOT_EVALUATED'),
 PRIMARY KEY(park_id,service_id,version)
);
CREATE TABLE IF NOT EXISTS preparation_grants (
 principal_id text NOT NULL REFERENCES principals, park_id text NOT NULL, org_id text NOT NULL,
 capability text NOT NULL CHECK(capability IN ('PREPARE','REVIEW_ASSIGNED')), active boolean NOT NULL DEFAULT true,
 PRIMARY KEY(principal_id,capability)
);
CREATE TABLE IF NOT EXISTS preparations (
 id uuid PRIMARY KEY, run_id uuid UNIQUE NOT NULL REFERENCES runs, case_id uuid UNIQUE NOT NULL REFERENCES cases,
 owner_id text NOT NULL REFERENCES principals, reviewer_id text NOT NULL REFERENCES principals,
 park_id text NOT NULL, org_id text NOT NULL, service_id text NOT NULL, service_version integer NOT NULL,
 namespace text NOT NULL CHECK(namespace='SYNTHETIC'), goal text NOT NULL,
 state text NOT NULL CHECK(state IN ('IN_PREPARATION','CHANGES_REQUESTED','REVIEWED','LOCAL_CONFIRMED')),
 revision integer NOT NULL DEFAULT 1 CHECK(revision>0), review_sha256 text,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 FOREIGN KEY(park_id,service_id,service_version) REFERENCES preparation_catalog(park_id,service_id,version),
 CHECK((state IN ('REVIEWED','LOCAL_CONFIRMED')) = (review_sha256 IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS preparation_evidence (
 id uuid PRIMARY KEY, preparation_id uuid NOT NULL REFERENCES preparations,
 slot text NOT NULL CHECK(slot IN ('need_summary','material_outline')), version integer NOT NULL CHECK(version>0),
 text text NOT NULL CHECK(length(text) BETWEEN 1 AND 4000),
 source_kind text NOT NULL CHECK(source_kind IN ('USER_STATEMENT','DOCUMENT_EXCERPT')),
 source_label text NOT NULL CHECK(length(source_label) BETWEEN 1 AND 200),
 source_sha256 text NOT NULL, actor_id text NOT NULL REFERENCES principals,
 authenticity text NOT NULL CHECK(authenticity='UNVERIFIED'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), UNIQUE(preparation_id,slot,version)
);
CREATE TABLE IF NOT EXISTS preparation_events (
 id uuid PRIMARY KEY, preparation_id uuid NOT NULL REFERENCES preparations, actor_id text NOT NULL REFERENCES principals,
 request_key text NOT NULL, fingerprint text NOT NULL, revision integer NOT NULL,
 action text NOT NULL CHECK(action IN ('CREATE','ADD_EVIDENCE','REQUEST_CHANGES','REVIEW','CONFIRM','REOPEN')),
 payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(actor_id,request_key), UNIQUE(preparation_id,revision)
);
INSERT INTO schema_version VALUES(9) ON CONFLICT DO NOTHING;
