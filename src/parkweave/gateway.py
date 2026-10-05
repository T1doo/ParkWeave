"""One worker gateway for trusted local actions and opt-in synthetic fault adapter."""
import json
from psycopg.types.json import Jsonb
from .domain import Intake
from .store import Conflict, digest


class InjectedCrash(Exception):
    pass


class FixtureAdapter:
    def __init__(self, store):
        if store.mode != 'FAULT_INJECTION':
            raise Conflict('fixture adapter disabled')
        self.store = store

    def expected(self, envelope):
        return {'source':'FAULT_INJECTION','operation_id':str(envelope['operation_id']),
                'park_id':envelope['park_id'],'org_id':envelope['org_id'],
                'fingerprint':envelope['fingerprint'],'effect':'SIMULATED_RECORD'}

    def send(self, envelope):
        # This second transaction models a remote effect that cannot be atomically
        # committed with the caller's local ledger. It is never an external API.
        with self.store.connect() as c:
            receipt=self.expected(envelope)
            c.execute('INSERT INTO fixture_effects VALUES(%s,%s,%s,%s,%s,1) '
                      'ON CONFLICT(operation_id) DO UPDATE SET dispatch_count=fixture_effects.dispatch_count+1',
                      (envelope['operation_id'],envelope['park_id'],envelope['org_id'],envelope['fingerprint'],Jsonb(receipt)))
        return None  # this fixture deliberately loses every dispatch response

    def query(self, envelope):
        with self.store.connect() as c:
            row=c.execute('SELECT receipt FROM fixture_effects WHERE operation_id=%s AND park_id=%s AND org_id=%s',
                          (envelope['operation_id'],envelope['park_id'],envelope['org_id'])).fetchone()
        return row['receipt'] if row else None  # absence does not prove no effect


class ExecutionGateway:
    def __init__(self, store):
        self.store=store

    def envelope(self, run, op):
        return {'operation_id':op['id'],'park_id':run['park_id'],'org_id':run['org_id'],
                'fingerprint':run['fingerprint']}

    def prepare_dispatch(self, claim):
        with self.store.connect() as c:
            p,r,op=self.store.locked_execution(c,claim)
            if op['action']=='case.create':
                return 'LOCAL', None
            if op['action']!='fault.record' or self.store.mode!='FAULT_INJECTION':
                raise Conflict('unregistered execution capability')
            envelope=self.envelope(r,op)
            if op['state'] in ('DISPATCHED','OUTCOME_UNKNOWN'):
                # Withdrawn authority blocks new sends, not recording historical outcomes.
                return 'RECONCILE', envelope
            if op['state']!='PREPARED':
                raise Conflict('operation is terminal')
            if not p['active'] or r['control_intent']!='CONTINUE':
                c.execute("UPDATE operations SET state='FAILED_SAFE' WHERE id=%s",(op['id'],))
                c.execute("UPDATE runs SET state='FAILED',lease_until=NULL,revision=revision+1 WHERE id=%s",(r['id'],))
                self.store.event(c,r['id'])
                return 'STOP', None
            data=Intake.model_validate(r['input'])
            if data.action!=op['action'] or digest(json.dumps(data.model_dump(),sort_keys=True,ensure_ascii=False))!=r['fingerprint']:
                raise Conflict('persisted intent changed')
            c.execute("UPDATE operations SET state='DISPATCHED' WHERE id=%s",(op['id'],))
            return 'SEND', envelope

    def record(self, claim, receipt):
        with self.store.connect() as c:
            p,r,op=self.store.locked_execution(c,claim)
            if op['action']!='fault.record' or self.store.mode!='FAULT_INJECTION' or op['state'] not in ('DISPATCHED','OUTCOME_UNKNOWN'):
                raise Conflict('not awaiting fixture outcome')
            if receipt is None:
                op_state,state,scope='OUTCOME_UNKNOWN','RECONCILING',None
            elif receipt==FixtureAdapter(self.store).expected(self.envelope(r,op)):
                op_state,scope='VERIFIED','FAULT_INJECTION_EFFECT_KNOWN'
                state={'CONTINUE':'SUCCEEDED','CANCEL':'CANCELLED','PAUSE':'PAUSED'}[r['control_intent']]
            else:
                op_state,state,scope='EFFECT_KNOWN_INVALID','FAILED',None
            attempts=op['reconcile_attempts']+1 if receipt is None else op['reconcile_attempts']
            c.execute('UPDATE operations SET state=%s,receipt=%s,reconcile_attempts=%s WHERE id=%s',
                      (op_state,Jsonb(receipt) if receipt is not None else None,attempts,op['id']))
            # Maximum three automatic unknown observations. Manual authorized reconcile
            # can re-enable queries but cannot authorize redispatch of an unknown effect.
            c.execute("UPDATE runs SET state=%s,success_scope=%s,lease_until=NULL,revision=revision+1,"
                      "next_attempt_at=CASE WHEN %s='RECONCILING' AND %s<3 THEN clock_timestamp()+interval '1 second' ELSE NULL END "
                      'WHERE id=%s',(state,scope,state,attempts,r['id']))
            self.store.event(c,r['id'])

    def execute(self, claim, crash_at=None):
        phase,envelope=self.prepare_dispatch(claim)
        if phase=='LOCAL':
            self.store.finish(claim)
        elif phase=='SEND':
            if crash_at=='after-dispatch':raise InjectedCrash('FAULT_INJECTION: after dispatch commit')
            receipt=FixtureAdapter(self.store).send(envelope)
            if crash_at=='after-effect':raise InjectedCrash('FAULT_INJECTION: after simulated effect commit')
            self.record(claim,receipt)
        elif phase=='RECONCILE':
            self.record(claim,FixtureAdapter(self.store).query(envelope))
