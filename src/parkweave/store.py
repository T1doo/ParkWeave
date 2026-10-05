"""PostgreSQL transactions are the authority; no process-memory business state."""
import hashlib
import json
import uuid
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from .domain import Intake


class Denied(Exception):
    pass


class Conflict(Exception):
    pass


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class Store:
    def __init__(self, dsn: str):
        self.dsn = dsn

    def connect(self):
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def migrate(self):
        with self.connect() as c:
            c.execute(Path(__file__).with_name("schema.sql").read_text())

    def seed(self, identities: dict[str, str]):
        """Explicit synthetic setup only. Never reactivates a revoked identity."""
        scopes = {"fixture-a": ("park-a", "org-a"), "fixture-b": ("park-a", "org-b"),
                  "fixture-c": ("park-b", "org-c")}
        with self.connect() as c:
            for user, token in identities.items():
                park, org = scopes[user]
                c.execute("INSERT INTO principals VALUES(%s,%s,%s,%s,'enterprise_operator',true) "
                          "ON CONFLICT(id) DO NOTHING", (user, digest(token), park, org))

    def auth(self, c, token: str, lock=False):
        sql = "SELECT * FROM principals WHERE token_hash=%s AND active"
        p = c.execute(sql, (digest(token),)).fetchone()
        if p is None:
            raise Denied("current authorization required")
        if lock:
            self.lock_principal(c, p["id"])
            p = c.execute(sql, (digest(token),)).fetchone()
            if p is None:
                raise Denied("current authorization required")
        return p

    def lock_principal(self, c, principal_id, exclusive=False):
        # Row-level FOR SHARE requires UPDATE privilege. Advisory authorization locks
        # let the application remain read-only on identity rows; admin revocation
        # uses the same exclusive lock. No other identity writer is supported.
        function = "pg_advisory_xact_lock" if exclusive else "pg_advisory_xact_lock_shared"
        c.execute(f"SELECT {function}(hashtextextended(%s,0))", ("principal:"+principal_id,))

    def scoped_run(self, c, p, run_id, lock=False):
        sql = "SELECT * FROM runs WHERE id=%s AND park_id=%s AND org_id=%s AND principal_id=%s"
        if lock:
            sql += " FOR UPDATE"
        r = c.execute(sql, (run_id, p["park_id"], p["org_id"], p["id"])).fetchone()
        if r is None:
            raise Denied("record unavailable")
        return r

    def event(self, c, run_id):
        r = c.execute("SELECT state,revision,success_scope FROM runs WHERE id=%s", (run_id,)).fetchone()
        c.execute("INSERT INTO outbox VALUES(%s,%s,%s,%s,NULL)",
                  (uuid.uuid4(), run_id, r["revision"], Jsonb(r)))

    def submit(self, token: str, key: str, data: Intake):
        fingerprint = digest(json.dumps(data.model_dump(), sort_keys=True, ensure_ascii=False))
        with self.connect() as c:
            p = self.auth(c, token, lock=True)
            # Serializes request-key lookup/create. Scope derives exclusively from DB identity.
            c.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (p["id"] + ':' + key,))
            old = c.execute("SELECT id,fingerprint FROM runs WHERE principal_id=%s AND request_key=%s",
                            (p["id"], key)).fetchone()
            if old:
                if old["fingerprint"] != fingerprint:
                    raise Conflict("idempotency key fingerprint mismatch")
                return str(old["id"])
            run_id = uuid.uuid4()
            c.execute("INSERT INTO runs(id,principal_id,park_id,org_id,namespace,request_key,"
                      "fingerprint,input,state) VALUES(%s,%s,%s,%s,'SYNTHETIC',%s,%s,%s,'QUEUED')",
                      (run_id, p["id"], p["park_id"], p["org_id"], key, fingerprint, Jsonb(data.model_dump())))
            c.execute("INSERT INTO operations VALUES(%s,%s,'case.create','PREPARED',NULL)",
                      (uuid.uuid4(), run_id))
            self.event(c, run_id)
            return str(run_id)

    def read(self, token, run_id):
        with self.connect() as c:
            p = self.auth(c, token, lock=True)
            r = self.scoped_run(c, p, run_id)
            case = c.execute("SELECT id,state,goal,source,external_acceptance,offline_fulfillment "
                             "FROM cases WHERE run_id=%s", (run_id,)).fetchone()
            op = c.execute("SELECT id,state,receipt FROM operations WHERE run_id=%s", (run_id,)).fetchone()
            return {"run_id": str(r["id"]), "state": r["state"], "success_scope": r["success_scope"],
                    "namespace": r["namespace"], "case": case, "operation": op, "model_mode": "MODEL_MOCK"}

    def control(self, token, run_id, intent):
        with self.connect() as c:
            p = self.auth(c, token, lock=True)
            r = self.scoped_run(c, p, run_id, lock=True)
            if r["state"] not in ("QUEUED", "RUNNING", "PAUSED"):
                raise Conflict("terminal run cannot be controlled; effects are not reversed")
            if intent == "resume" and r["state"] != "PAUSED":
                raise Conflict("only paused runs can resume")
            state = {"pause": "PAUSED", "cancel": "CANCELLED", "resume": "QUEUED"}[intent]
            # This increment has only a single short atomic local action; no remote in-flight effect.
            c.execute("UPDATE runs SET state=%s,fence=fence+1,lease_until=NULL,revision=revision+1 "
                      "WHERE id=%s", (state, run_id))
            self.event(c, run_id)

    def revoke(self, principal_id):
        """Administrative test/CLI operation; not an API client role claim."""
        with self.connect() as c:
            self.lock_principal(c, principal_id, exclusive=True)
            c.execute("UPDATE principals SET active=false WHERE id=%s", (principal_id,))

    def claim(self, worker_id, lease_seconds=30):
        with self.connect() as c:
            r = c.execute("SELECT * FROM runs WHERE state='QUEUED' OR "
                          "(state='RUNNING' AND lease_until < clock_timestamp()) "
                          "ORDER BY created_at,id FOR UPDATE SKIP LOCKED LIMIT 1").fetchone()
            if not r:
                return None
            return c.execute("UPDATE runs SET state='RUNNING',worker_id=%s,fence=fence+1,"
                             "lease_until=clock_timestamp()+%s*interval '1 second' "
                             "WHERE id=%s RETURNING id,fence", (worker_id, lease_seconds, r["id"])).fetchone()

    def finish(self, claim, fail_after_effect=False):
        with self.connect() as c:
            # Lock identity first, matching API lock order and serializing authorization withdrawal.
            initial = c.execute("SELECT principal_id FROM runs WHERE id=%s", (claim["id"],)).fetchone()
            if not initial:
                raise Conflict("run missing")
            self.lock_principal(c, initial["principal_id"])
            p = c.execute("SELECT * FROM principals WHERE id=%s",
                          (initial["principal_id"],)).fetchone()
            r = c.execute("SELECT *,lease_until>clock_timestamp() AS lease_valid FROM runs "
                          "WHERE id=%s FOR UPDATE", (claim["id"],)).fetchone()
            if r["state"] != "RUNNING" or r["fence"] != claim["fence"] or not r["lease_valid"]:
                raise Conflict("stale worker or expired lease")
            if not p["active"]:
                c.execute("UPDATE runs SET state='FAILED',revision=revision+1 WHERE id=%s", (r["id"],))
                c.execute("UPDATE operations SET state='FAILED_SAFE' WHERE run_id=%s", (r["id"],))
                self.event(c, r["id"])
                return
            # Revalidate persisted input, even if an unsafe tool attempted to change it.
            data = Intake.model_validate(r["input"])
            case_id = uuid.uuid4()
            c.execute("INSERT INTO cases VALUES(%s,%s,%s,%s,%s,'NEEDS_INPUT','SYNTHETIC',"
                      "'NOT_SUBMITTED','NO_EVIDENCE')", (case_id,r["id"],r["park_id"],r["org_id"],data.goal))
            if fail_after_effect:
                raise RuntimeError("FAULT_INJECTION: transaction interruption")
            receipt = {"case_id": str(case_id), "source": "LOCAL_DATABASE", "verified": True,
                       "success_scope": "LOCAL_CASE_CREATED"}
            c.execute("UPDATE operations SET state='VERIFIED',receipt=%s WHERE run_id=%s",
                      (Jsonb(receipt),r["id"]))
            c.execute("UPDATE runs SET state='SUCCEEDED',success_scope='LOCAL_CASE_CREATED',"
                      "lease_until=NULL,revision=revision+1 WHERE id=%s", (r["id"],))
            self.event(c,r["id"])

    def consume(self, fail_before_ack=False):
        with self.connect() as c:
            e = c.execute("SELECT * FROM outbox WHERE consumed_at IS NULL ORDER BY revision DESC "
                          "FOR UPDATE SKIP LOCKED LIMIT 1").fetchone()
            if not e:
                return False
            c.execute("INSERT INTO run_projection VALUES(%s,%s,%s) ON CONFLICT(run_id) DO UPDATE "
                      "SET revision=excluded.revision,payload=excluded.payload "
                      "WHERE run_projection.revision < excluded.revision", (e["run_id"],e["revision"],Jsonb(e["payload"])))
            if fail_before_ack:
                raise RuntimeError("FAULT_INJECTION: consumer interruption")
            c.execute("UPDATE outbox SET consumed_at=clock_timestamp() WHERE id=%s", (e["id"],))
            return True
