"""Opt-in FAULT_INJECTION ledger, no network or production API registration.

Tests alone install fault-schema.sql and grant its tables. The fake remote stores
its effects in separate transactions, so a lost response does not mean no effect.
"""
import json
import uuid
from psycopg.types.json import Jsonb
from .domain import Intake
from .store import Store, Conflict, Denied, digest


class FaultAdapter:
    """Self-authored synthetic remote, using owner connection only in tests."""
    def __init__(self, owner: Store):
        self.owner = owner

    def send(self, envelope, lose_response=False):
        with self.owner.connect() as c:
            receipt = {'source': 'FAULT_INJECTION', 'operation_id': str(envelope['id']),
                       'park_id': envelope['park_id'], 'org_id': envelope['org_id'],
                       'fingerprint': envelope['fingerprint'], 'effect': 'SIMULATED_RECORD'}
            c.execute('INSERT INTO fault_effects VALUES(%s,%s,%s,%s,%s,1) '
                      'ON CONFLICT(operation_id) DO UPDATE SET dispatch_count=fault_effects.dispatch_count+1',
                      (envelope['id'],envelope['park_id'],envelope['org_id'],envelope['fingerprint'],Jsonb(receipt)))
        return None if lose_response else receipt

    def query(self, envelope):
        with self.owner.connect() as c:
            row = c.execute('SELECT receipt FROM fault_effects WHERE operation_id=%s AND park_id=%s AND org_id=%s',
                            (envelope['id'],envelope['park_id'],envelope['org_id'])).fetchone()
        # Absence is NOT authoritative proof that a previously sent action failed.
        return row['receipt'] if row else None


class FaultLedger:
    def __init__(self, store: Store, adapter: FaultAdapter):
        self.store, self.adapter = store, adapter

    def prepare(self, token, key, data: Intake):
        fingerprint = digest(json.dumps(data.model_dump(),sort_keys=True,ensure_ascii=False))
        with self.store.connect() as c:
            p = self.store.auth(c,token,lock=True)
            c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('fault:'+p['id']+':'+key,))
            old = c.execute('SELECT * FROM fault_operations WHERE principal_id=%s AND request_key=%s',
                            (p['id'],key)).fetchone()
            if old:
                if old['fingerprint'] != fingerprint:raise Conflict('fault key fingerprint mismatch')
                return old['id']
            op_id=uuid.uuid4()
            c.execute('INSERT INTO fault_operations(id,principal_id,park_id,org_id,request_key,fingerprint,payload,state) '
                      "VALUES(%s,%s,%s,%s,%s,%s,%s,'PREPARED')",
                      (op_id,p['id'],p['park_id'],p['org_id'],key,fingerprint,Jsonb(data.model_dump())))
            return op_id

    def read(self, token, op_id):
        with self.store.connect() as c:
            p=self.store.auth(c,token,lock=True)
            row=c.execute('SELECT * FROM fault_operations WHERE id=%s AND principal_id=%s AND park_id=%s AND org_id=%s',
                          (op_id,p['id'],p['park_id'],p['org_id'])).fetchone()
            if not row:raise Denied('fault record unavailable')
            return row

    def claim(self):
        with self.store.connect() as c:
            row=c.execute("SELECT * FROM fault_operations WHERE "
                          "((state='PREPARED' AND intent='CONTINUE') OR state IN ('DISPATCHED','OUTCOME_UNKNOWN')) "
                          'AND (lease_until IS NULL OR lease_until<clock_timestamp()) '
                          'ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1').fetchone()
            if not row:return None
            return c.execute("UPDATE fault_operations SET fence=fence+1,lease_until=clock_timestamp()+interval '30 seconds' "
                             'WHERE id=%s RETURNING id,fence',(row['id'],)).fetchone()

    def locked(self,c,claim):
        row=c.execute('SELECT *,lease_until>clock_timestamp() lease_valid FROM fault_operations WHERE id=%s FOR UPDATE',
                      (claim['id'],)).fetchone()
        if not row or row['fence']!=claim['fence'] or not row['lease_valid']:
            raise Conflict('stale fault worker')
        return row

    def dispatch(self,claim):
        with self.store.connect() as c:
            initial=c.execute('SELECT principal_id FROM fault_operations WHERE id=%s',(claim['id'],)).fetchone()
            if not initial:raise Conflict('fault operation missing')
            self.store.lock_principal(c,initial['principal_id'])
            row=self.locked(c,claim)
            if row['state']!='PREPARED' or row['intent']!='CONTINUE':
                raise Conflict('already dispatched or controlled; reconciliation only')
            p=c.execute('SELECT active FROM principals WHERE id=%s',(row['principal_id'],)).fetchone()
            if not p['active']:
                c.execute("UPDATE fault_operations SET state='FAILED_SAFE',lease_until=NULL WHERE id=%s",(row['id'],))
                return None
            Intake.model_validate(row['payload'])
            c.execute("UPDATE fault_operations SET state='DISPATCHED' WHERE id=%s",(row['id'],))
            return row  # durable dispatch intent committed before any simulated remote send

    def record(self,claim,receipt):
        # Recording the outcome of an already dispatched action is permitted after
        # withdrawal; it authorizes no new effect and remains unreadable to revoked users.
        with self.store.connect() as c:
            row=self.locked(c,claim)
            if row['state'] not in ('DISPATCHED','OUTCOME_UNKNOWN'):
                raise Conflict('not awaiting a dispatched outcome')
            state='OUTCOME_UNKNOWN'
            if receipt is not None:
                expected={'source':'FAULT_INJECTION','operation_id':str(row['id']),
                          'park_id':row['park_id'],'org_id':row['org_id'],
                          'fingerprint':row['fingerprint'],'effect':'SIMULATED_RECORD'}
                state='VERIFIED' if receipt==expected else 'EFFECT_KNOWN_INVALID'
            c.execute('UPDATE fault_operations SET state=%s,receipt=%s,lease_until=NULL WHERE id=%s',
                      (state,Jsonb(receipt) if receipt is not None else None,row['id']))

    def reconcile(self,claim):
        with self.store.connect() as c:
            row=self.locked(c,claim)
            if row['state'] not in ('DISPATCHED','OUTCOME_UNKNOWN'):
                raise Conflict('reconciliation cannot dispatch a new action')
        self.record(claim,self.adapter.query(row))

    def control(self,token,op_id,intent):
        if intent not in ('PAUSE','CANCEL','CONTINUE'):raise ValueError('unknown control intent')
        with self.store.connect() as c:
            p=self.store.auth(c,token,lock=True)
            row=c.execute('SELECT * FROM fault_operations WHERE id=%s AND principal_id=%s AND park_id=%s AND org_id=%s FOR UPDATE',
                          (op_id,p['id'],p['park_id'],p['org_id'])).fetchone()
            if not row:raise Denied('fault record unavailable')
            if row['state'] not in ('PREPARED','DISPATCHED','OUTCOME_UNKNOWN'):
                raise Conflict('known effect is not reversed by a control request')
            state='FAILED_SAFE' if intent=='CANCEL' and row['state']=='PREPARED' else row['state']
            c.execute('UPDATE fault_operations SET intent=%s,state=%s,fence=fence+1,lease_until=NULL WHERE id=%s',
                      (intent,state,op_id))
