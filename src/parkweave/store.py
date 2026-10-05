"""PostgreSQL transactions are the authority; no process-memory business state."""
import hashlib
import json
import uuid
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from .domain import Intake, FactInput
from .permissions import ROLE_CAPABILITIES, TRUSTED_ACTIONS


class Denied(Exception):
    pass


class Conflict(Exception):
    pass


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class Store:
    def __init__(self, dsn: str, mode="LOCAL", file_root=None):
        if mode not in ("LOCAL", "FAULT_INJECTION"):
            raise ValueError("unsupported execution mode")
        self.dsn, self.mode = dsn, mode
        self.file_root = file_root

    def connect(self):
        return psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=2)

    def migrate(self):
        with self.connect() as c:
            c.execute("SELECT pg_advisory_xact_lock(hashtextextended('parkweave:migrate',0))")
            c.execute(Path(__file__).with_name("schema.sql").read_text())
            version = c.execute("SELECT max(version) version FROM schema_version").fetchone()["version"]
            if version > 8:
                raise Conflict("database version newer than this code")
            if version < 2:
                c.execute(Path(__file__).with_name("migration-002.sql").read_text())
            if version < 3:
                c.execute(Path(__file__).with_name("migration-003.sql").read_text())
            if version < 4:
                c.execute(Path(__file__).with_name("migration-004.sql").read_text())
            if version < 5:
                c.execute(Path(__file__).with_name("migration-005.sql").read_text())

            if version < 6:
                c.execute(Path(__file__).with_name("migration-006.sql").read_text())

            if version < 7:
                c.execute(Path(__file__).with_name("migration-007.sql").read_text())
            if version < 8:
                c.execute(Path(__file__).with_name("migration-008.sql").read_text())

    def seed(self, identities: dict[str, str]):
        """Explicit synthetic setup only. Never reactivates a revoked identity."""
        scopes = {"fixture-a": ("park-a", "org-a"), "fixture-b": ("park-a", "org-b"),
                  "fixture-c": ("park-b", "org-c")}
        with self.connect() as c:
            for user, token in identities.items():
                park, org = scopes[user]
                c.execute("INSERT INTO principals VALUES(%s,%s,%s,%s,'enterprise_operator',true) "
                          "ON CONFLICT(id) DO NOTHING", (user, digest(token), park, org))
                if c.execute("SELECT to_regclass('field_grants') t").fetchone()['t'] is not None:
                    self.seed_field_grants(c,user,park,org)
                if c.execute("SELECT to_regclass('capability_grants') t").fetchone()['t'] is not None:
                    for cap in ROLE_CAPABILITIES['enterprise_operator']:
                        c.execute("INSERT INTO capability_grants(principal_id,capability,park_id,org_id) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",(user,cap,park,org))
                    for action in TRUSTED_ACTIONS:
                        c.execute("INSERT INTO action_grants(principal_id,action,park_id,org_id) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",(user,action,park,org))

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

    def check_capability(self, c, p, capability):
        if not p['active'] or capability not in ROLE_CAPABILITIES.get(p['role'],()):
            raise Denied('role capability denied')
        grant=c.execute('SELECT 1 FROM capability_grants WHERE principal_id=%s AND capability=%s AND park_id=%s AND org_id=%s AND active',
                        (p['id'],capability,p['park_id'],p['org_id'])).fetchone()
        if not grant:raise Denied('current capability grant required')

    def scoped_run(self, c, p, run_id, lock=False, capability='READ'):
        self.check_capability(c,p,capability)
        sql = 'SELECT * FROM runs WHERE id=%s AND park_id=%s AND org_id=%s'
        if lock:sql += ' FOR UPDATE'
        r=c.execute(sql,(run_id,p['park_id'],p['org_id'])).fetchone()
        if r is None:raise Denied('record unavailable')
        if p['role'] != 'enterprise_operator':
            assignment=c.execute('SELECT 1 FROM run_assignments WHERE principal_id=%s AND run_id=%s '
                                 'AND park_id=%s AND org_id=%s AND active',
                                 (p['id'],run_id,p['park_id'],p['org_id'])).fetchone()
            if capability!='READ' or not assignment:
                raise Denied('assigned scope required')
        elif r['principal_id'] != p['id']:
            raise Denied('owner scope required')
        return r

    def check_execution(self,c,p,r):
        self.check_capability(c,p,'EXECUTE')
        if p['id']!=r['principal_id'] or p['park_id']!=r['park_id'] or p['org_id']!=r['org_id']:
            raise Denied('execution scope changed')
        action=r['input'].get('action','case.create')
        if action not in TRUSTED_ACTIONS or (action=='fault.record' and self.mode!='FAULT_INJECTION'):
            raise Denied('trusted action required')
        if not c.execute('SELECT 1 FROM action_grants WHERE principal_id=%s AND action=%s AND park_id=%s AND org_id=%s AND active',(p['id'],action,p['park_id'],p['org_id'])).fetchone():
            raise Denied('current action capability required')
        if action=='facts.assess':
            self.check_fields(c,p,r['input']['fact_fields'],'READ')
            if r['input'].get('candidate_review'):self.check_fields(c,p,r['input']['fact_fields'],'WRITE')

    def revoke_capability(self,principal_id,capability):
        if capability not in ROLE_CAPABILITIES['enterprise_operator']:raise ValueError('unknown capability')
        with self.connect() as c:
            self.lock_principal(c,principal_id,exclusive=True)
            c.execute('UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id=%s AND capability=%s',
                      (principal_id,capability))

    def assign_status(self,principal_id,run_id,active=True):
        """Owner-only synthetic setup; cannot assign cross-org or mutate role grants."""
        with self.connect() as c:
            self.lock_principal(c,principal_id,exclusive=True)
            p=c.execute('SELECT * FROM principals WHERE id=%s',(principal_id,)).fetchone()
            r=c.execute('SELECT * FROM runs WHERE id=%s',(run_id,)).fetchone()
            if not p or not r or p['role']=='enterprise_operator' or (p['park_id'],p['org_id'])!=(r['park_id'],r['org_id']):
                raise Denied('invalid assignment scope')
            c.execute('INSERT INTO run_assignments VALUES(%s,%s,%s,%s,%s) ON CONFLICT(principal_id,run_id) '
                      'DO UPDATE SET active=excluded.active',(principal_id,run_id,p['park_id'],p['org_id'],active))

    def event(self, c, run_id):
        r = c.execute("SELECT state,revision,success_scope FROM runs WHERE id=%s", (run_id,)).fetchone()
        c.execute("INSERT INTO outbox VALUES(%s,%s,%s,%s,NULL)",
                  (uuid.uuid4(), run_id, r["revision"], Jsonb(r)))

    def submit(self, token: str, key: str, data: Intake):
        if data.action == "fault.record" and self.mode != "FAULT_INJECTION":
            raise Denied("fixture adapter disabled")
        fingerprint = digest(json.dumps(data.snapshot(), sort_keys=True, ensure_ascii=False))
        with self.connect() as c:
            p = self.auth(c, token, lock=True)
            self.check_capability(c,p,'EXECUTE')
            if not c.execute('SELECT 1 FROM action_grants WHERE principal_id=%s AND action=%s AND park_id=%s AND org_id=%s AND active',(p['id'],data.action,p['park_id'],p['org_id'])).fetchone():raise Denied('current action grant required')
            if data.action=='facts.assess':
                self.check_fields(c,p,data.fact_fields,'READ')
                if data.candidate_review:self.check_fields(c,p,data.fact_fields,'WRITE')
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
                      (run_id, p["id"], p["park_id"], p["org_id"], key, fingerprint, Jsonb(data.snapshot())))
            c.execute("INSERT INTO operations(id,run_id,action,state) VALUES(%s,%s,%s,'PREPARED')",
                      (uuid.uuid4(), run_id, data.action))
            self.event(c, run_id)
            return str(run_id)

    def read(self, token, run_id):
        with self.connect() as c:
            p = self.auth(c, token, lock=True)
            r = self.scoped_run(c, p, run_id)
            if p['role']!='enterprise_operator':
                return {'run_id':str(r['id']),'state':r['state'],'revision':r['revision'],'visibility':'ASSIGNED_STATUS_ONLY'}
            if r['input'].get('action')=='facts.assess':self.check_fields(c,p,r['input']['fact_fields'],'READ')
            case = c.execute("SELECT id,state,goal,source,external_acceptance,offline_fulfillment "
                             "FROM cases WHERE run_id=%s", (run_id,)).fetchone()
            op = c.execute("SELECT id,state,receipt FROM operations WHERE run_id=%s", (run_id,)).fetchone()
            model_step=c.execute("SELECT result FROM model_steps WHERE run_id=%s ORDER BY phase DESC LIMIT 1",(r['id'],)).fetchone()
            model_mode='MODEL_MOCK' if not model_step else (model_step['result'] or {}).get('mode','MODEL_CHAIN_ATTEMPTED')
            return {"run_id": str(r["id"]), "state": r["state"], "success_scope": r["success_scope"],
                    "namespace": r["namespace"], "case": case, "operation": op, "model_mode": model_mode,
                    "control_intent": r["control_intent"], "execution_mode": self.mode}

    def control(self, token, run_id, intent):
        with self.connect() as c:
            p = self.auth(c, token, lock=True)
            r = self.scoped_run(c, p, run_id, lock=True,capability='CONTROL')
            if r['input'].get('action')=='facts.assess':self.check_fields(c,p,r['input']['fact_fields'],'READ')
            op = c.execute("SELECT * FROM operations WHERE run_id=%s", (run_id,)).fetchone()
            pending = op["state"] in ("DISPATCHED", "OUTCOME_UNKNOWN")
            if op["state"] not in ("PREPARED", "DISPATCHED", "OUTCOME_UNKNOWN"):
                raise Conflict("known operation outcome cannot be resumed or reversed")
            if r["state"] not in ("QUEUED", "RUNNING", "PAUSED", "RECONCILING"):
                raise Conflict("terminal run cannot be controlled; effects are not reversed")
            if intent == "reconcile":
                if not pending:
                    raise Conflict("no unknown dispatched outcome")
                state, control = "RECONCILING", r["control_intent"]
                c.execute("UPDATE operations SET reconcile_attempts=0 WHERE run_id=%s", (run_id,))
            else:
                if intent == "resume" and (r["state"] != "PAUSED" or pending):
                    raise Conflict("only undispatched paused runs can resume")
                state = "RECONCILING" if pending else {"pause": "PAUSED", "cancel": "CANCELLED", "resume": "QUEUED"}[intent]
                control = {"pause": "PAUSE", "cancel": "CANCEL", "resume": "CONTINUE"}[intent]
            c.execute("UPDATE runs SET state=%s,control_intent=%s,fence=fence+1,lease_until=NULL,"
                      "next_attempt_at=clock_timestamp(),revision=revision+1 WHERE id=%s", (state,control,run_id))
            self.event(c, run_id)

    def revoke(self, principal_id):
        """Administrative test/CLI operation; not an API client role claim."""
        with self.connect() as c:
            self.lock_principal(c, principal_id, exclusive=True)
            c.execute("UPDATE principals SET active=false WHERE id=%s", (principal_id,))

    def claim(self, worker_id, lease_seconds=30):
        if not 1 <= lease_seconds <= 300:
            raise ValueError("lease must be 1..300 seconds")
        with self.connect() as c:
            r = c.execute("SELECT r.* FROM runs r JOIN operations o ON o.run_id=r.id WHERE "
                          "(o.action IN ('case.create','facts.assess') OR %s='FAULT_INJECTION') AND "
                          "(r.state='QUEUED' OR (r.state IN ('RUNNING','RECONCILING') AND "
                          "(r.lease_until IS NULL OR r.lease_until < clock_timestamp()))) "
                          "AND r.next_attempt_at <= clock_timestamp() "
                          "ORDER BY r.created_at,r.id FOR UPDATE OF r SKIP LOCKED LIMIT 1", (self.mode,)).fetchone()
            if not r:
                return None
            return c.execute("UPDATE runs SET state=CASE WHEN state='RECONCILING' THEN state ELSE 'RUNNING' END,"
                             "worker_id=%s,fence=fence+1,lease_until=clock_timestamp()+%s*interval '1 second' "
                             "WHERE id=%s RETURNING id,fence", (worker_id,lease_seconds,r["id"])).fetchone()

    def locked_execution(self, c, claim):
        initial = c.execute("SELECT principal_id FROM runs WHERE id=%s", (claim["id"],)).fetchone()
        if not initial:
            raise Conflict("run missing")
        self.lock_principal(c, initial["principal_id"])
        p = c.execute("SELECT * FROM principals WHERE id=%s", (initial["principal_id"],)).fetchone()
        r = c.execute("SELECT *,lease_until>clock_timestamp() AS lease_valid FROM runs WHERE id=%s FOR UPDATE",
                      (claim["id"],)).fetchone()
        if r["state"] not in ("RUNNING", "RECONCILING") or r["fence"] != claim["fence"] or not r["lease_valid"]:
            raise Conflict("stale worker or expired lease")
        op = c.execute("SELECT * FROM operations WHERE run_id=%s", (r["id"],)).fetchone()
        return p, r, op

    def finish(self, claim, fail_after_effect=False, defer_completion=False):
        with self.connect() as c:
            p, r, op = self.locked_execution(c, claim)
            if op["action"] != "case.create" or op["state"] != "PREPARED":
                raise Conflict("local finish only accepts a prepared local action")
            try:self.check_execution(c,p,r)
            except Denied:
                self.safe_failure(c,r,op,'AUTHORIZATION_REVOKED');return
            # Revalidate persisted input, even if an unsafe tool attempted to change it.
            data = Intake.model_validate(r["input"])
            if data.action != op["action"] or digest(json.dumps(r["input"], sort_keys=True, ensure_ascii=False)) != r["fingerprint"]:
                raise Conflict("persisted intent changed")
            case_id = uuid.uuid4()
            c.execute("INSERT INTO cases VALUES(%s,%s,%s,%s,%s,'NEEDS_INPUT','SYNTHETIC',"
                      "'NOT_SUBMITTED','NO_EVIDENCE')", (case_id,r["id"],r["park_id"],r["org_id"],data.goal))
            if fail_after_effect:
                raise RuntimeError("FAULT_INJECTION: transaction interruption")
            receipt = {"case_id": str(case_id), "source": "LOCAL_DATABASE", "verified": True,
                       "success_scope": "LOCAL_CASE_CREATED"}
            c.execute("UPDATE operations SET state='VERIFIED',receipt=%s WHERE run_id=%s",
                      (Jsonb(receipt),r["id"]))
            c.execute("UPDATE runs SET state=%s,success_scope='LOCAL_CASE_CREATED',"
                      "lease_until=CASE WHEN %s THEN lease_until ELSE NULL END,revision=revision+1 WHERE id=%s",
                      ('RUNNING' if defer_completion else 'SUCCEEDED',defer_completion,r['id']))
            self.event(c,r["id"])

    def seed_field_grants(self, c, user, park, org):
        # Owner-only setup, never reactivates an existing withdrawn grant.
        for field in ('region','employees','service_need'):
            for capability in ('READ','WRITE'):
                c.execute("INSERT INTO field_grants(principal_id,park_id,org_id,field_name,purpose,capability,source) "
                          "VALUES(%s,%s,%s,%s,'SERVICE_PREPARATION',%s,'SYNTHETIC_SETUP') ON CONFLICT DO NOTHING",
                          (user,park,org,field,capability))

    def check_fields(self, c, p, fields, capability):
        if not p['active'] or p['role']!='enterprise_operator':raise Denied('current enterprise field authorization required')
        self.check_capability(c,p,'READ' if capability=='READ' else 'EXECUTE')
        rows=c.execute("SELECT field_name FROM field_grants WHERE principal_id=%s AND park_id=%s AND org_id=%s "
                       "AND purpose='SERVICE_PREPARATION' AND capability=%s AND active "
                       "AND (valid_until IS NULL OR valid_until>clock_timestamp()) AND field_name=ANY(%s)",
                       (p['id'],p['park_id'],p['org_id'],capability,fields)).fetchall()
        if set(fields)!={row['field_name'] for row in rows}:raise Denied('current field grant required')

    def revoke_field(self, principal_id, field, capability):
        if field not in ('region','employees','service_need') or capability not in ('READ','WRITE'):
            raise ValueError('unknown field/capability')
        with self.connect() as c:
            self.lock_principal(c,principal_id,exclusive=True)
            c.execute("UPDATE field_grants SET active=false,revision=revision+1 WHERE principal_id=%s AND field_name=%s AND capability=%s",
                      (principal_id,field,capability))

    def save_fact(self, token, key, data: FactInput):
        fingerprint=digest(json.dumps(data.model_dump(),sort_keys=True,ensure_ascii=False))
        with self.connect() as c:
            p=self.auth(c,token,lock=True);self.check_fields(c,p,[data.field],'WRITE')
            c.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",('fact:'+p['id']+':'+key,))
            old=c.execute('SELECT id,fingerprint FROM fact_assertions WHERE principal_id=%s AND request_key=%s',(p['id'],key)).fetchone()
            if old:
                if old['fingerprint']!=fingerprint:raise Conflict('fact key fingerprint mismatch')
                return str(old['id'])
            c.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",('field:'+p['id']+':'+data.field,))
            count=c.execute('SELECT count(*) n FROM fact_assertions WHERE principal_id=%s AND field_name=%s',(p['id'],data.field)).fetchone()['n']
            if count>=16:raise Conflict('field evidence limit 16 reached')
            fact_id,evidence_id=uuid.uuid4(),uuid.uuid4()
            c.execute("INSERT INTO fact_assertions(id,evidence_id,principal_id,park_id,org_id,field_name,value,unit,source_ref,source_kind,"
                      "source_excerpt,valid_from,valid_until,request_key,fingerprint,confirmed_by) "
                      "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'USER_ASSERTED_SYNTHETIC',%s,%s,%s,%s,%s,%s)",
                      (fact_id,evidence_id,p['id'],p['park_id'],p['org_id'],data.field,Jsonb(data.value),data.unit,
                       Jsonb(data.source_ref.model_dump()),data.source_excerpt,data.validity.valid_from,data.validity.valid_until,key,fingerprint,p['id']))
            return str(fact_id)

    def facts_query(self, c, p, fields):
        return c.execute('SELECT id,evidence_id,field_name,value,unit,source_ref,source_kind,source_excerpt,valid_from,valid_until,'
                         'revision,fingerprint,confirmed_by FROM fact_assertions WHERE principal_id=%s AND park_id=%s AND org_id=%s '
                         'AND field_name=ANY(%s) ORDER BY id',(p['id'],p['park_id'],p['org_id'],fields)).fetchall()

    def read_facts(self, token, fields, fact_id=None):
        with self.connect() as c:
            p=self.auth(c,token,lock=True)
            if fact_id:
                row=c.execute('SELECT field_name FROM fact_assertions WHERE id=%s AND principal_id=%s AND park_id=%s AND org_id=%s',
                              (fact_id,p['id'],p['park_id'],p['org_id'])).fetchone()
                if not row:raise Denied('fact unavailable')
                fields=[row['field_name']]
            self.check_fields(c,p,fields,'READ')
            rows=self.facts_query(c,p,fields)
            return [r for r in rows if fact_id is None or str(r['id'])==str(fact_id)]

    def safe_failure(self,c,r,op,reason):
        if reason=='AUTHORIZATION_REVOKED':self.audit(c,r['principal_id'],'WORKER_AUTHORIZATION','DENIED')
        c.execute("UPDATE operations SET state='FAILED_SAFE',receipt=%s WHERE id=%s",
                  (Jsonb({'source':'LOCAL_GATEWAY','reason':reason}),op['id']))
        c.execute("UPDATE runs SET state='FAILED',lease_until=NULL,fence=fence+1,revision=revision+1 WHERE id=%s",(r['id'],))
        self.event(c,r['id'])

    def assess_facts(self, claim):
        with self.connect() as c:
            p,r,op=self.locked_execution(c,claim)
            if op['action']!='facts.assess' or op['state']!='PREPARED':raise Conflict('not a prepared assessment')
            data=Intake.model_validate(r['input'])
            if digest(json.dumps(r['input'],sort_keys=True,ensure_ascii=False))!=r['fingerprint'] or data.action!=op['action']:
                self.safe_failure(c,r,op,'INVALID_INTENT');return
            try:self.check_execution(c,p,r)
            except Denied:self.safe_failure(c,r,op,'AUTHORIZATION_REVOKED');return
            rows=self.facts_query(c,p,data.fact_fields)
            now=c.execute('SELECT clock_timestamp() now').fetchone()['now']
            results=[]
            for field in data.fact_fields:
                all_rows=[row for row in rows if row['field_name']==field]
                valid=[row for row in all_rows if row['valid_from']<=now<row['valid_until']]
                values={json.dumps([row['value'],row['unit']],ensure_ascii=False) for row in valid}
                reason='MISSING_EVIDENCE' if not all_rows else 'EXPIRED_OR_NOT_YET_VALID' if not valid else 'CONFLICTING_EVIDENCE' if len(values)>1 else 'CONSISTENT_EVIDENCE'
                results.append({'field':field,'state':'KNOWN' if reason=='CONSISTENT_EVIDENCE' else 'UNKNOWN','reason':reason,
                                'evidence':[{'id':str(row['evidence_id']),'fact_id':str(row['id']),'source_ref':row['source_ref'],
                                             'value':row['value'],'unit':row['unit'],'valid_from':row['valid_from'].isoformat(),
                                             'valid_until':row['valid_until'].isoformat(),'applicable_at_assessment':row in valid,
                                             'revision':row['revision'],'fingerprint':row['fingerprint'],
                                             'source_kind':row['source_kind']} for row in all_rows]})
            receipt={'source':'LOCAL_FACT_ASSESSMENT','assessed_at':now.isoformat(),'purpose':'SERVICE_PREPARATION',
                     'results':results,'qualification_decision':'NOT_EVALUATED'}
            c.execute("UPDATE operations SET state='VERIFIED',receipt=%s WHERE id=%s",(Jsonb(receipt),op['id']))
            c.execute("UPDATE runs SET state='SUCCEEDED',success_scope='FACT_EVIDENCE_ASSESSED',lease_until=NULL,revision=revision+1 WHERE id=%s",(r['id'],))
            self.event(c,r['id'])

    def heartbeat(self, claim, lease_seconds):
        if not 1<=lease_seconds<=300:raise ValueError('lease must be 1..300 seconds')
        with self.connect() as c:
            c.execute("SET LOCAL lock_timeout='500ms'")
            c.execute("SET LOCAL statement_timeout='1000ms'")
            p,r,op=self.locked_execution(c,claim)
            try:
                self.check_execution(c,p,r)
            except Denied:
                if op['state']=='PREPARED':self.safe_failure(c,r,op,'AUTHORIZATION_REVOKED')
                return False
            c.execute("UPDATE runs SET lease_until=clock_timestamp()+%s*interval '1 second',heartbeat_count=heartbeat_count+1,"
                      'last_heartbeat_at=clock_timestamp() WHERE id=%s',(lease_seconds,r['id']))
            return True

    def current_delivery_authority(self,c,p,r):
        if p['role']!='enterprise_operator':raise Denied('inbox recipient role changed')
        self.scoped_run(c,p,r['id'])
        if r['input'].get('action')=='facts.assess':self.check_fields(c,p,r['input']['fact_fields'],'READ')

    def consume(self, fail_before_ack=False):
        with self.connect() as c:
            initial=c.execute('SELECT o.id,r.principal_id FROM outbox o JOIN runs r ON r.id=o.run_id '
                              'WHERE o.consumed_at IS NULL ORDER BY o.revision DESC,o.id LIMIT 1').fetchone()
            if not initial:return self.retract_delivery(c)
            self.lock_principal(c,initial['principal_id'])
            e=c.execute('SELECT * FROM outbox WHERE id=%s AND consumed_at IS NULL FOR UPDATE SKIP LOCKED',
                        (initial['id'],)).fetchone()
            if not e:return False
            p=c.execute('SELECT * FROM principals WHERE id=%s',(initial['principal_id'],)).fetchone()
            r=c.execute('SELECT * FROM runs WHERE id=%s',(e['run_id'],)).fetchone()
            try:self.current_delivery_authority(c,p,r);allowed=True
            except Denied:allowed=False
            # Kernel projection is non-user status, not an authorization cache.
            c.execute('INSERT INTO run_projection VALUES(%s,%s,%s) ON CONFLICT(run_id) DO UPDATE '
                      'SET revision=excluded.revision,payload=excluded.payload '
                      'WHERE run_projection.revision < excluded.revision',(e['run_id'],e['revision'],Jsonb(e['payload'])))
            c.execute('INSERT INTO deliveries VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(event_id) DO NOTHING',
                      (e['id'],e['run_id'],p['id'],e['revision'],'READY' if allowed else 'SUPPRESSED',
                       Jsonb(e['payload'] if allowed else {})))
            self.audit(c,p['id'],'OUTBOX_LOCAL_DELIVERY','ALLOWED' if allowed else 'SUPPRESSED')
            if fail_before_ack:raise RuntimeError('FAULT_INJECTION: consumer interruption')
            c.execute('UPDATE outbox SET consumed_at=clock_timestamp() WHERE id=%s',(e['id'],))
            return True

    def retract_delivery(self,c):
        # Lock order matches owner revocation: principal -> delivery. One bounded
        # pass per drain; current reads independently recheck even before this pass.
        rows=c.execute("SELECT d.event_id,d.principal_id,d.run_id FROM deliveries d JOIN runs r ON r.id=d.run_id "
                       "JOIN principals p ON p.id=d.principal_id WHERE d.state='READY' AND "
                       "(NOT p.active OR p.role<>'enterprise_operator' OR p.org_id<>r.org_id OR p.park_id<>r.park_id OR "
                       "NOT EXISTS(SELECT 1 FROM capability_grants g WHERE g.principal_id=p.id AND g.capability='READ' AND g.park_id=p.park_id AND g.org_id=p.org_id AND g.active) OR "
                       "(r.input->>'action'='facts.assess' AND EXISTS(SELECT 1 FROM jsonb_array_elements_text(r.input->'fact_fields') f "
                       "WHERE NOT EXISTS(SELECT 1 FROM field_grants g WHERE g.principal_id=p.id AND g.park_id=p.park_id AND g.org_id=p.org_id "
                       "AND g.field_name=f AND g.purpose='SERVICE_PREPARATION' AND g.capability='READ' AND g.active "
                       "AND (g.valid_until IS NULL OR g.valid_until>clock_timestamp()))))) ORDER BY d.event_id LIMIT 1").fetchall()
        for row in rows:
            self.lock_principal(c,row['principal_id'])
            p=c.execute('SELECT * FROM principals WHERE id=%s',(row['principal_id'],)).fetchone()
            r=c.execute('SELECT * FROM runs WHERE id=%s',(row['run_id'],)).fetchone()
            try:self.current_delivery_authority(c,p,r)
            except Denied:
                c.execute("UPDATE deliveries SET state='RETRACTED',payload='{}' WHERE event_id=%s AND state='READY'",(row['event_id'],))
                self.audit(c,p['id'],'OUTBOX_LOCAL_DELIVERY','RETRACTED')
                return True
        return False

    def read_delivery(self,token,event_id):
        with self.connect() as c:
            p=self.auth(c,token,lock=True)
            row=c.execute('SELECT * FROM deliveries WHERE event_id=%s AND principal_id=%s',(event_id,p['id'])).fetchone()
            if not row:raise Denied('delivery unavailable')
            r=self.scoped_run(c,p,row['run_id']);self.current_delivery_authority(c,p,r)
            if row['state']!='READY':raise Denied('delivery withdrawn')
            return {'event_id':str(row['event_id']),'run_id':str(row['run_id']),'revision':row['revision'],'payload':row['payload'],
                    'channel':'LOCAL_INBOX','external_send':False}

    def register_synthetic_file(self,principal_id,run_id,content:bytes):
        """Owner/test setup only, not an upload API. Immutable synthetic plain text."""
        if self.file_root is None or len(content)>16384:raise ValueError('configured root and <=16KiB required')
        content.decode('utf-8',errors='strict')
        from .files import read_text_resource
        with self.connect() as c:
            self.lock_principal(c,principal_id)
            p=c.execute('SELECT * FROM principals WHERE id=%s',(principal_id,)).fetchone()
            r=self.scoped_run(c,p,run_id,capability='FILE_READ')
            if r['principal_id']!=p['id']:raise Denied('owner file only')
            from .files import resource_directory
            file_id=uuid.uuid4()
            resource={'id':file_id,'size':len(content),'sha256':hashlib.sha256(content).hexdigest()}
            import os
            with resource_directory(self.file_root,create=True) as directory:
                name=str(file_id)+'.txt'
                fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory)
                try:
                    with os.fdopen(fd,'wb') as f:f.write(content);f.flush();os.fsync(f.fileno())
                    read_text_resource(self.file_root,resource)
                    c.execute("INSERT INTO file_resources VALUES(%s,%s,%s,%s,%s,'text/plain',%s,%s,'SYNTHETIC_FIXTURE')",
                              (file_id,principal_id,run_id,p['park_id'],p['org_id'],len(content),resource['sha256']))
                except Exception:
                    os.unlink(name,dir_fd=directory);raise
            return str(file_id)

    def read_file(self,token,file_id):
        from .files import read_text_resource
        with self.connect() as c:
            p=self.auth(c,token,lock=True)
            self.check_capability(c,p,'FILE_READ')
            row=c.execute('SELECT * FROM file_resources WHERE id=%s AND principal_id=%s AND park_id=%s AND org_id=%s',
                          (file_id,p['id'],p['park_id'],p['org_id'])).fetchone()
            if not row:raise Denied('file unavailable')
            r=self.scoped_run(c,p,row['run_id'])
            self.current_delivery_authority(c,p,r)
            return read_text_resource(self.file_root,row)

    def audit(self,c,principal_id,category,outcome):
        c.execute('INSERT INTO authorization_audit(id,principal_id,category,outcome) VALUES(%s,%s,%s,%s)',
                  (uuid.uuid4(),principal_id,category,outcome))

    def audit_denial(self,token):
        # Called after API transaction rollback; no body, token or source text logged.
        with self.connect() as c:
            p=c.execute('SELECT id FROM principals WHERE token_hash=%s',(digest(token),)).fetchone()
            if p:self.audit(c,p['id'],'API_AUTHORIZATION','DENIED')

    def read_plan_revisions(self,token,run_id):
        with self.connect() as c:
            p=self.auth(c,token,lock=True)
            r=self.scoped_run(c,p,run_id)
            self.current_delivery_authority(c,p,r)
            return c.execute("SELECT revision,document,sha256,provider_call_id,tool_call_id,created_at "
                             "FROM model_plans WHERE run_id=%s ORDER BY revision",(run_id,)).fetchall()
