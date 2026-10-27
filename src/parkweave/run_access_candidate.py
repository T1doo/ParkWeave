"""Exact single-Run READ candidate, isolated SYNTHETIC fixtures only.

No deployment Store, principal, Grant or assignment writes. Mock headers are not
authentication and this engine is deliberately absent from the production API.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json, sqlite3, threading
from typing import Literal
from uuid import uuid4
from pydantic import Field, model_validator
from .domain import Contract, PlanID, SourceRef, Validity
from .permissions import ROLE_CAPABILITIES
from .rule_publication_candidate import canonical, sha, active, Denied, Conflict

NAMESPACE='ISOLATED_SYNTHETIC_RUN_ACCESS'
CEILINGS={'enterprise_operator':{'STATUS','REQUEST','CANCEL','REVOKE'},'park_specialist':{'STATUS','APPROVE','REJECT','REVOKE'},'resource_admin':{'STATUS'},'service_executor':{'STATUS','ACCESS'}}

class RunScope(Contract):
    park_id: PlanID
    org_id: PlanID
    run_id: PlanID

class RunPersona(Contract):
    id: PlanID
    park_id: PlanID
    org_id: PlanID
    role: Literal['enterprise_operator','park_specialist','resource_admin','service_executor']
    active: bool=True

class MockReadFact(Contract):
    principal_id: PlanID
    park_id: PlanID
    org_id: PlanID
    capability: Literal['READ']='READ'
    validity: Validity
    active: bool=True

class RunPermit(Contract):
    id: PlanID
    principal_id: PlanID
    scope: RunScope
    actions: list[Literal['STATUS','REQUEST','APPROVE','REJECT','CANCEL','REVOKE','ACCESS']]=Field(min_length=1,max_length=7)
    validity: Validity
    active: bool=True

class MockRun(Contract):
    scope: RunScope
    owner_id: PlanID
    revision: int=Field(ge=1)
    source_ref: SourceRef
    snapshot: str=Field(min_length=1,max_length=2000)
    @model_validator(mode='after')
    def synthetic(self):
        if self.source_ref.kind!='SYNTHETIC':raise ValueError('synthetic Run fixture required')
        return self

class RunAccessConfig(Contract):
    enabled_for_isolated_tests: bool=False
    namespace: Literal['ISOLATED_SYNTHETIC_RUN_ACCESS']=NAMESPACE
    revision: int=Field(default=1,ge=1)
    max_access_seconds: int=Field(default=28800,ge=60,le=28800)
    personas: list[RunPersona]=Field(default_factory=list,max_length=16)
    read_facts: list[MockReadFact]=Field(default_factory=list,max_length=16)
    permits: list[RunPermit]=Field(default_factory=list,max_length=64)
    runs: list[MockRun]=Field(default_factory=list,max_length=16)
    @model_validator(mode='after')
    def explicit(self):
        ids={p.id for p in self.personas}
        if len(ids)!=len(self.personas) or len({p.id for p in self.permits})!=len(self.permits) or len({canonical(r.scope.model_dump()) for r in self.runs})!=len(self.runs):raise ValueError('duplicate candidate fixtures')
        if any(p.principal_id not in ids for p in [*self.permits,*self.read_facts]) or any(r.owner_id not in ids for r in self.runs):raise ValueError('missing fixture persona')
        if self.enabled_for_isolated_tests and not all([self.personas,self.read_facts,self.permits,self.runs]):raise ValueError('explicit isolated Run contract required')
        return self

class RunCommand(Contract):
    action: Literal['REQUEST','APPROVE','REJECT','CANCEL','REVOKE']
    expected_revision: int=Field(ge=0,le=64)
    expected_run_revision: int=Field(ge=1)
    expected_authority_sha256: str=Field(pattern=r'^[0-9a-f]{64}$')
    target_id: PlanID|None=None
    target_role: Literal['service_executor']|None=None
    capability: Literal['READ']|None=None
    requested_validity: Validity|None=None
    approved_validity: Validity|None=None
    reason: str=Field(min_length=1,max_length=1000)
    @model_validator(mode='after')
    def shape(self):
        request_fields=[self.target_id,self.target_role,self.capability,self.requested_validity]
        if not self.reason.strip() or (self.action=='REQUEST' and any(x is None for x in request_fields)) or (self.action!='REQUEST' and any(x is not None for x in request_fields)) or (self.action=='APPROVE')!=(self.approved_validity is not None):raise ValueError('explicit narrow candidate command required')
        return self

class AccessProbe(Contract):
    expected_revision: int=Field(ge=1,le=64)
    expected_run_revision: int=Field(ge=1)
    expected_authority_sha256: str=Field(pattern=r'^[0-9a-f]{64}$')
    lease_id: PlanID

class RunAccessRepository:
    def __init__(self,path):
        self.path=Path(path)
        if not self.path.name.endswith('.run-access.candidate.sqlite3') or self.path.is_symlink():raise ValueError('dedicated Run candidate file required')
        with sqlite3.connect(self.path) as c:
            tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            cols={'access_meta':['namespace','version'],'access_tickets':['scope','revision','state','payload','lease_id'],'access_leases':['id','scope','state','payload'],'access_events':['actor','key','fp','scope','revision','payload']}
            if tables and tables!=set(cols):raise Conflict('foreign or partial candidate database refused')
            if tables and (any([r[1] for r in c.execute('PRAGMA table_info('+t+')')]!=names for t,names in cols.items()) or c.execute('SELECT namespace,version FROM access_meta').fetchall()!=[(NAMESPACE,1)]):raise Conflict('candidate schema mismatch')
            c.executescript('''CREATE TABLE IF NOT EXISTS access_meta(namespace TEXT PRIMARY KEY,version INTEGER);
            CREATE TABLE IF NOT EXISTS access_tickets(scope TEXT PRIMARY KEY,revision INTEGER,state TEXT,payload TEXT,lease_id TEXT);
            CREATE TABLE IF NOT EXISTS access_leases(id TEXT PRIMARY KEY,scope TEXT,state TEXT,payload TEXT);
            CREATE TABLE IF NOT EXISTS access_events(actor TEXT,key TEXT,fp TEXT,scope TEXT,revision INTEGER,payload TEXT,PRIMARY KEY(actor,key));
            CREATE TRIGGER IF NOT EXISTS immutable_access_events_update BEFORE UPDATE ON access_events BEGIN SELECT RAISE(ABORT,'immutable candidate audit'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_access_events_delete BEFORE DELETE ON access_events BEGIN SELECT RAISE(ABORT,'immutable candidate audit'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_access_lease_payload BEFORE UPDATE OF payload ON access_leases BEGIN SELECT RAISE(ABORT,'immutable candidate lease'); END;''')
            c.execute('INSERT OR IGNORE INTO access_meta VALUES(?,1)',(NAMESPACE,))
    @contextmanager
    def connect(self,write=False):
        c=sqlite3.connect(self.path,timeout=3);c.row_factory=sqlite3.Row
        try:
            c.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            yield c;c.commit()
        except sqlite3.OperationalError as e:c.rollback();raise Conflict('candidate database busy; retry same key') from e
        except BaseException:c.rollback();raise
        finally:c.close()

class RunAccessEngine:
    def __init__(self,config=None,repository=None,clock=None):
        self.config=RunAccessConfig.model_validate((config or RunAccessConfig()).model_dump());self.repository=repository;self.clock=clock or (lambda:datetime.now(timezone.utc));self.mutex=threading.RLock()
        if self.config.enabled_for_isolated_tests and repository is None:raise ValueError('isolated repository required')
    def replace_test_contract(self,config):
        # Fixture-only revocation/version changes, never exposed through HTTP.
        with self.mutex:
            cfg=RunAccessConfig.model_validate(config.model_dump())
            if cfg.revision<=self.config.revision:raise Conflict('monotonic fixture contract revision required')
            self.config=cfg
    def status(self):return {'namespace':NAMESPACE,'candidate_demo':self.config.enabled_for_isolated_tests,'actual_assignment_written':False,'deployment_enabled':False,'mock_personas':[p.model_dump() for p in self.config.personas]}
    def _persona(self,actor,scope,now):
        if not self.config.enabled_for_isolated_tests or self.repository is None:raise Denied('candidate disabled')
        p=next((p for p in self.config.personas if p.id==actor and p.active and (p.park_id,p.org_id)==(scope.park_id,scope.org_id)),None)
        if p is None or 'READ' not in ROLE_CAPABILITIES[p.role]:raise Denied('current tenant/role required')
        if not any(f.principal_id==actor and f.active and (f.park_id,f.org_id)==(scope.park_id,scope.org_id) and active(f.validity.model_dump(),now) for f in self.config.read_facts):raise Denied('current existing READ fact required')
        return p
    def _authorize(self,actor,action,scope,now):
        p=self._persona(actor,scope,now)
        if action not in CEILINGS[p.role]:raise Denied('candidate role denied')
        permit=next((f for f in self.config.permits if f.principal_id==actor and f.scope==scope and f.active and action in f.actions and active(f.validity.model_dump(),now)),None)
        if permit is None:raise Denied('explicit single Run candidate permit required')
        return permit
    def _run(self,scope):
        r=next((r for r in self.config.runs if r.scope==scope),None)
        if r is None:raise Denied('mock Run unavailable')
        return r
    def _row(self,c,scope):return c.execute('SELECT * FROM access_tickets WHERE scope=?',(canonical(scope.model_dump()),)).fetchone()
    def _participants(self,actor,scope,row,now):
        p=self._authorize(actor,'STATUS',scope,now);person=self._persona(actor,scope,now);run=self._run(scope)
        if person.role=='enterprise_operator' and run.owner_id!=actor:raise Denied('current Run owner required')
        if person.role=='service_executor' and (row is None or json.loads(row['payload'])['target_id']!=actor):raise Denied('only requested beneficiary metadata available')
        if person.role=='resource_admin':raise Denied('generic reader cannot read private access decisions')
        if person.role=='park_specialist' and not any(f.principal_id==actor and f.scope==scope and f.active and set(f.actions)&{'APPROVE','REVOKE'} and active(f.validity.model_dump(),now) for f in self.config.permits):raise Denied('explicit current access decision authority required for metadata')
        return p
    def _request_current(self,payload,scope,now,check_deadline=True):
        run=self._run(scope)
        if run.revision!=payload['run_revision'] or run.owner_id!=payload['requester_id']:raise Conflict('Run version or owner changed')
        self._authorize(payload['requester_id'],'REQUEST',scope,now)
        if self._persona(payload['requester_id'],scope,now).role!='enterprise_operator' or self._persona(payload['target_id'],scope,now).role!='service_executor':raise Denied('current requester/beneficiary role required')
        self._authorize(payload['target_id'],'ACCESS',scope,now)
        if self.config.revision!=payload['contract_revision'] or sha(self.config.model_dump())!=payload['contract_sha256']:raise Conflict('candidate authority version changed')
        if check_deadline and datetime.fromisoformat(payload['requested_validity']['valid_until'])<=now:raise Conflict('request expired')
    def _available(self,row,scope,now):
        if row is None:return False,'NOT_REQUESTED',None
        if row['state']!='APPROVED':
            reason='EXPIRED_REQUEST' if row['state']=='REQUESTED' and datetime.fromisoformat(json.loads(row['payload'])['requested_validity']['valid_until'])<=now else row['state']
            return False,reason,None
        payload=json.loads(row['payload'])
        try:
            self._request_current(payload,scope,now,check_deadline=False)
            self._authorize(payload['approver_id'],'APPROVE',scope,now)
            if now>=datetime.fromisoformat(payload['approved_validity']['valid_until']):return False,'EXPIRED_APPROVAL',payload
            if not active(payload['approved_validity'],now):return False,'NOT_STARTED',payload
        except (Denied,Conflict):return False,'CURRENT_AUTHORITY_OR_RUN_CHANGED',payload
        return True,'ACTIVE_ISOLATED_READ',payload
    def _view(self,c,scope,row,now):
        available,reason,payload=self._available(row,scope,now);run=self._run(scope)
        revision=row['revision'] if row else 0;state=row['state'] if row else 'NOT_REQUESTED'
        authority_sha=sha({'contract':self.config.model_dump(),'scope':scope.model_dump(),'run_revision':run.revision,'revision':revision,'reason':reason})
        return {'namespace':NAMESPACE,'scope':scope.model_dump(),'revision':revision,'run_revision':run.revision,'authority_sha256':authority_sha,'state':state,'availability_reason':reason,'candidate_access_available':available,'request':json.loads(row['payload']) if row else None,'lease_id':row['lease_id'] if row else None,'history':[json.loads(e[0]) for e in c.execute('SELECT payload FROM access_events WHERE scope=? ORDER BY revision',(canonical(scope.model_dump()),))],'leases':[{'state':e['state'],**json.loads(e['payload'])} for e in c.execute('SELECT * FROM access_leases WHERE scope=? ORDER BY rowid',(canonical(scope.model_dump()),))],'actual_assignment_written':False,'actual_run_access':False,'deployment_enabled':False,'case_goal_completed':False,'qualification_truth':'UNKNOWN'}
    def read(self,actor,scope):
        with self.mutex:
            now=self.clock()
            with self.repository.connect() if self.repository else _disabled_context() as c:
                self._authorize(actor,'STATUS',scope,now);row=self._row(c,scope);now=self.clock();self._participants(actor,scope,row,now);return self._view(c,scope,row,now)
    def _valid_interval(self,v,scope,actors,now,allow_past=False):
        start,end=datetime.fromisoformat(v['valid_from']),datetime.fromisoformat(v['valid_until'])
        if end<=now or (end-start).total_seconds()>self.config.max_access_seconds or (not allow_past and (start-now).total_seconds() < -60):raise Conflict('bounded current/future access interval required')
        for actor,action in actors:
            permit=self._authorize(actor,action,scope,now)
            facts=[f for f in self.config.read_facts if f.principal_id==actor and f.active and (f.park_id,f.org_id)==(scope.park_id,scope.org_id) and active(f.validity.model_dump(),now)]
            if start<datetime.fromisoformat(permit.validity.valid_from) or end>datetime.fromisoformat(permit.validity.valid_until) or not any(start>=datetime.fromisoformat(f.validity.valid_from) and end<=datetime.fromisoformat(f.validity.valid_until) for f in facts):raise Conflict('interval exceeds current parent authority')
    def command(self,actor,scope,key,data):
        if not 1<=len(key)<=100:raise ValueError('bounded idempotency key required')
        fp=sha({'scope':scope.model_dump(),**data.model_dump(mode='json')})
        with self.mutex:
            now=self.clock();permit=self._authorize(actor,data.action,scope,now);run=self._run(scope)
            with self.repository.connect(write=True) as c:
                # BEGIN IMMEDIATE can wait; authority/time checks must use lock time.
                now=self.clock();permit=self._authorize(actor,data.action,scope,now);run=self._run(scope)
                row=self._row(c,scope);self._participants(actor,scope,row,now);view=self._view(c,scope,row,now)
                old=c.execute('SELECT * FROM access_events WHERE actor=? AND key=?',(actor,key)).fetchone()
                if old:
                    receipt=json.loads(old['payload'])
                    if old['fp']!=fp or old['revision']!=view['revision'] or receipt['contract_sha256']!=sha(self.config.model_dump()) or receipt['run_revision']!=run.revision:raise Conflict('old candidate receipt cannot be replayed as current authority')
                    if data.action in ('REQUEST','APPROVE'):
                        self._request_current(json.loads(row['payload']),scope,now)
                        if data.action=='APPROVE' and not view['candidate_access_available']:raise Denied('expired/revoked approval cannot be replayed')
                    return receipt
                if (data.expected_revision,data.expected_run_revision,data.expected_authority_sha256)!=(view['revision'],view['run_revision'],view['authority_sha256']):raise Conflict('candidate request/Run/authority changed')
                if view['revision']>=64:raise Conflict('bounded audit limit')
                if (data.action=='REQUEST' and view['revision']>=62) or (data.action=='APPROVE' and view['revision']>=63):raise Conflict('reserve audit capacity for cancellation or revocation')
                payload=json.loads(row['payload']) if row else None;lease_id=row['lease_id'] if row else None;state=row['state'] if row else None
                if data.action=='REQUEST':
                    if run.owner_id!=actor or self._persona(actor,scope,now).role!='enterprise_operator':raise Denied('owned Run only')
                    if state=='REQUESTED' or view['candidate_access_available']:raise Conflict('cancel/revoke existing candidate request first')
                    target=self._persona(data.target_id,scope,now)
                    if target.role!='service_executor' or target.id==actor:raise Denied('existing same tenant service executor required')
                    interval=data.requested_validity.model_dump();self._valid_interval(interval,scope,[(actor,'REQUEST'),(target.id,'ACCESS')],now)
                    if lease_id:c.execute("UPDATE access_leases SET state='SUPERSEDED' WHERE id=?",(lease_id,))
                    lease_id=None;state='REQUESTED';payload={'request_id':str(uuid4()),'requester_id':actor,'target_id':target.id,'target_role':'service_executor','capability':'READ','requested_validity':interval,'run_revision':run.revision,'contract_revision':self.config.revision,'contract_sha256':sha(self.config.model_dump())}
                elif data.action=='APPROVE':
                    if state!='REQUESTED':raise Conflict('current explicit request required')
                    if actor in (payload['requester_id'],payload['target_id']):raise Denied('independent approver required')
                    self._request_current(payload,scope,now);interval=data.approved_validity.model_dump();requested=payload['requested_validity']
                    if datetime.fromisoformat(interval['valid_from'])<datetime.fromisoformat(requested['valid_from']) or datetime.fromisoformat(interval['valid_until'])>datetime.fromisoformat(requested['valid_until']):raise Conflict('approval cannot broaden requested interval')
                    self._valid_interval(interval,scope,[(payload['requester_id'],'REQUEST'),(payload['target_id'],'ACCESS'),(actor,'APPROVE')],now,allow_past=True)
                    payload.update(approver_id=actor,approved_validity=interval);lease_id=str(uuid4());state='APPROVED'
                    lease={'id':lease_id,'scope':scope.model_dump(),**payload,'approved_at':now.isoformat(),'actual_assignment_written':False,'deployment_enabled':False}
                    c.execute('INSERT INTO access_leases VALUES(?,?,?,?)',(lease_id,canonical(scope.model_dump()),state,canonical(lease)))
                else:
                    if payload is None:raise Conflict('candidate request required')
                    if data.action=='CANCEL' and (state!='REQUESTED' or actor!=payload['requester_id']):raise Denied('requester may cancel pending request only')
                    if data.action=='REJECT' and state!='REQUESTED':raise Conflict('pending request required')
                    if data.action=='REVOKE' and state!='APPROVED':raise Conflict('approved candidate required')
                    if self._persona(actor,scope,now).role=='enterprise_operator' and actor!=payload['requester_id']:raise Denied('own request only')
                    state={'CANCEL':'CANCELLED','REJECT':'REJECTED','REVOKE':'REVOKED'}[data.action]
                    if lease_id:c.execute('UPDATE access_leases SET state=? WHERE id=?',(state,lease_id))
                    lease_id=None
                receipt={'namespace':NAMESPACE,'scope':scope.model_dump(),'revision':view['revision']+1,'run_revision':run.revision,'action':data.action,'state':state,'actor_id':actor,'permit_id':permit.id,'contract_revision':self.config.revision,'contract_sha256':sha(self.config.model_dump()),'reason':data.reason,'created_at':now.isoformat(),'request':payload,'lease_id':lease_id,'actual_assignment_written':False,'deployment_enabled':False}
                c.execute('INSERT INTO access_tickets VALUES(?,?,?,?,?) ON CONFLICT(scope) DO UPDATE SET revision=excluded.revision,state=excluded.state,payload=excluded.payload,lease_id=excluded.lease_id',(canonical(scope.model_dump()),receipt['revision'],state,canonical(payload),lease_id))
                c.execute('INSERT INTO access_events VALUES(?,?,?,?,?,?)',(actor,key,fp,canonical(scope.model_dump()),receipt['revision'],canonical(receipt)))
                return receipt
    def access(self,actor,scope,probe):
        with self.mutex:
            now=self.clock();self._authorize(actor,'ACCESS',scope,now);run=self._run(scope)
            with self.repository.connect() as c:
                row=self._row(c,scope);now=self.clock();self._authorize(actor,'ACCESS',scope,now);view=self._view(c,scope,row,now)
                if not view['candidate_access_available'] or not row or view['request']['target_id']!=actor:raise Denied('no current beneficiary approval')
                if (probe.expected_revision,probe.expected_run_revision,probe.expected_authority_sha256,probe.lease_id)!=(view['revision'],run.revision,view['authority_sha256'],row['lease_id']):raise Conflict('cached candidate access context is stale')
                if not self._available(row,scope,self.clock())[0]:raise Denied('candidate access expired during read')
                return {'namespace':NAMESPACE,'candidate_read_allowed':True,'mock_run_snapshot':run.snapshot,'run_revision':run.revision,'actual_run_access':False,'actual_assignment_written':False,'deployment_enabled':False,'capability':'READ','lease_id':row['lease_id']}

@contextmanager
def _disabled_context():yield None
