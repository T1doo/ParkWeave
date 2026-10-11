"""PostgreSQL decision-only protocol. Approval never grants business access.

Production writes are closed. Owned-fixture permits authorize non-effective
protocol tests only; storage is not an automatic migration or a permission grant.
"""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
import json
from pathlib import Path
from uuid import uuid4
from pydantic import model_validator
from functools import wraps
from psycopg.errors import LockNotAvailable

from psycopg.types.json import Jsonb

from . import case_fact_clarifications as facts, preparation as prep
from .domain import Intake, Validity
from .run_access_candidate import RunCommand as CandidateCommand
from .store import Conflict, Denied, digest

NAMESPACE = 'ORDINARY_PG_RUN_ACCESS_DECISION_V1'
STORAGE = Path(__file__).with_name('native-run-access-storage.sql')
_issued_test_permits = {}


class RunCommand(CandidateCommand):
    @model_validator(mode='after')
    def utc(self):
        for value in (self.requested_validity,self.approved_validity):
            if value and any(datetime.fromisoformat(t).utcoffset()!=timedelta(0)
                             for t in (value.valid_from,value.valid_until)):
                raise ValueError('native protocol requires explicit UTC intervals')
        return self


def _hash(value):
    return digest(prep.canonical(value))


def _now(c):
    return c.execute('SELECT clock_timestamp() AS now').fetchone()['now']


def _bounded(fn):
    @wraps(fn)
    def call(*args,**kwargs):
        try:
            return fn(*args,**kwargs)
        except LockNotAvailable as exc:
            raise Conflict('native protocol lock timeout; recover original key without resubmitting') from exc
    return call


@dataclass(frozen=True)
class DecisionTestPermit:
    proof: facts.FixtureDatabaseEvidence
    endpoint: tuple
    approver_ids: frozenset
    valid_until: datetime
    max_access_seconds: int
    revision: int = 1


def _proof(owner, proof):
    if (type(proof) is not facts.FixtureDatabaseEvidence or
            facts._fixture_databases.get(proof.nonce) is not proof or
            facts._fixture_clusters.get(proof.cluster.nonce) is not proof.cluster or
            set(dict(proof.cluster.initial_databases)) != {'postgres', 'template0', 'template1'} or
            proof.database_name in dict(proof.cluster.initial_databases)):
        raise Denied('issued fresh owned temporary fixture proof required')
    with owner.connect() as c:
        _owner_connection(c,proof)
        if owner.mode != 'LOCAL':
            raise Denied('owned decision fixture binding refused')
        return c.info.host, c.info.port


def _owner_connection(c,proof):
    actual=facts._migration_identity(c)
    facts._same_cluster(proof.cluster,actual)
    if (facts._fixture_databases.get(proof.nonce) is not proof or
            actual['database_oid']!=proof.database_oid or actual['database_name']!=proof.database_name or
            actual['owner_name']!=proof.cluster.owner or actual['session_name']!=proof.cluster.owner):
        raise Denied('owned decision fixture connection changed')


def install_owned_test_storage(owner, proof):
    """Explicit test installation only; does not grant SQL privileges."""
    _proof(owner, proof)
    with owner.connect() as c:
        _owner_connection(c,proof)
        c.execute(STORAGE.read_text())


def issue_decision_test_permit(owner, proof, *, approver_ids, seconds=600):
    endpoint = _proof(owner, proof)
    if (type(seconds) is not int or not 60 <= seconds <= 3600 or
            not isinstance(approver_ids,(set,frozenset)) or not approver_ids or len(approver_ids) > 8 or
            any(not isinstance(actor,str) or not actor for actor in approver_ids)):
        raise Denied('explicit bounded decision-only test permit required')
    with owner.connect() as c:
        _owner_connection(c,proof)
        for actor in sorted(approver_ids):
            p = c.execute('SELECT * FROM principals WHERE id=%s', (actor,)).fetchone()
            if not p or p['role'] != 'park_specialist':
                raise Denied('existing independent decision test actor required')
            owner.check_capability(c, p, 'READ')
        permit = DecisionTestPermit(proof, endpoint, frozenset(approver_ids),
                                    _now(c) + timedelta(seconds=seconds), seconds)
        _issued_test_permits[id(permit)] = permit
        return permit


class NativeRunAccess:
    def __init__(self, store, *, test_permit=None, activation_permit=None):
        if getattr(store, '_isolated_run_access', None) is not None:
            raise Denied('ordinary and isolated access providers cannot be combined')
        self.store, self.test_permit = store, test_permit
        self.activation_permit=activation_permit

    def assignment_allowed(self,c,p,run_id,assignment):
        from .native_run_access_activation import effective
        return effective(self,c,p,run_id,assignment)

    def activate(self,token,run_id,key,data):
        from .native_run_access_activation import activate
        return activate(self,token,run_id,key,data)

    @staticmethod
    def _key_receipt(c,actor,key):
        return c.execute("""SELECT e FROM runs r CROSS JOIN LATERAL
            jsonb_array_elements(coalesce(r.native_run_access_protocol->'events','[]'::jsonb)
              ||coalesce(to_jsonb(r)->'native_run_access_activation'->'events','[]'::jsonb)) e
            WHERE e->>'actor_id'=%s AND e->>'request_key'=%s LIMIT 1""",(actor,key)).fetchone()

    @staticmethod
    def _access_lock(c,run_id,exclusive=False):
        fn='pg_advisory_xact_lock' if exclusive else 'pg_advisory_xact_lock_shared'
        c.execute('SELECT '+fn+'(hashtextextended(%s,0))',('native-effective-access:'+str(run_id),))

    def _permit(self, c):
        permit = self.test_permit
        if type(permit) is not DecisionTestPermit or _issued_test_permits.get(id(permit)) is not permit:
            raise Denied('production access decision writes disabled')
        proof = permit.proof
        row = c.execute("""SELECT d.oid,d.datname,pg_postmaster_start_time() started
            FROM pg_database d WHERE d.datname=current_database()""").fetchone()
        if (facts._fixture_databases.get(proof.nonce) is not proof or
                facts._fixture_clusters.get(proof.cluster.nonce) is not proof.cluster or
                (c.info.host, c.info.port) != permit.endpoint or not row or
                (row['oid'], row['datname'], row['started']) !=
                (proof.database_oid, proof.database_name, proof.cluster.postmaster_start) or
                _now(c) >= permit.valid_until):
            raise Denied('decision-only test permit expired or changed')
        return permit

    def _storage(self, c):
        return bool(c.execute("""SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='runs'
            AND column_name='native_run_access_protocol' AND data_type='jsonb'""").fetchone())

    def _live_permit(self,c):
        try:
            return self._permit(c)
        except Denied:
            return None

    @_bounded
    def status(self, token):
        with self.store.connect() as c:
            c.execute("SET LOCAL lock_timeout='5s'")
            p = self.store.auth(c, token, lock=True)
            self.store.check_capability(c, p, 'READ')
            enabled = self._live_permit(c) is not None
            return dict(namespace=NAMESPACE, enabled=enabled, read_available=True,
                        storage_available=self._storage(c), role=p['role'],
                        can_approve=enabled and p['id'] in self.test_permit.approver_ids,
                        can_revoke=enabled and (p['role']=='enterprise_operator' or
                                              p['id'] in self.test_permit.approver_ids),
                        decision_only=True, activation_pending=True,
                        production_policy_adopted=False, deployment_enabled=False,
                        max_validity_hours=(self.test_permit.max_access_seconds / 3600 if enabled else None),
                        authority_valid_until=(self.test_permit.valid_until.isoformat() if enabled else None))

    def _principal(self, c, actor, run, role=None):
        self.store.lock_principal(c, actor)
        p = c.execute('SELECT * FROM principals WHERE id=%s', (actor,)).fetchone()
        if (not p or not p['active'] or (p['park_id'],p['org_id']) !=
                (run['park_id'],run['org_id']) or (role and p['role'] != role)):
            raise Denied('current exact-tenant participant required')
        self.store.check_capability(c, p, 'READ')
        return p

    def _run(self, c, p, run_id):
        row = c.execute('SELECT * FROM runs WHERE id=%s AND park_id=%s AND org_id=%s',
                        (run_id,p['park_id'],p['org_id'])).fetchone()
        if not row:
            raise Denied('record unavailable')
        return row

    def _authorize_read(self, c, p, run):
        self.store.check_capability(c, p, 'READ')
        ledger = run.get('native_run_access_protocol') or {}
        request = ledger.get('request') or {}
        if p['role'] == 'enterprise_operator' and p['id'] == run['principal_id']:
            return
        if p['role'] == 'service_executor' and p['id'] == request.get('target_id'):
            return
        if self.test_permit is not None:
            self._permit(c)
            if p['role']=='park_specialist' and p['id'] in self.test_permit.approver_ids:
                return
        raise Denied('current access metadata participant required')

    def _source(self, c, run, parent):
        op = c.execute('SELECT action,state,receipt FROM operations WHERE run_id=%s', (run['id'],)).fetchone()
        case = c.execute('SELECT id,state,source,park_id,org_id FROM cases WHERE id=%s AND run_id=%s',
                         (parent['case_id'],run['id'])).fetchone()
        expected = dict(case_id=str(parent['case_id']),source='LOCAL_DATABASE',
                        verified=True,success_scope='LOCAL_CASE_CREATED')
        try:
            intake=Intake.model_validate(run['input'])
            if intake.action!='case.create' or digest(json.dumps(run['input'],sort_keys=True,ensure_ascii=False))!=run['fingerprint']:
                raise ValueError()
        except (TypeError,KeyError,ValueError) as exc:
            raise Conflict('ordinary verified synthetic Case Run input proof required') from exc
        if (run['namespace']!='SYNTHETIC' or parent['namespace']!='SYNTHETIC' or
                not isinstance(run['input'],dict) or run['input'].get('action','case.create')!='case.create' or
                run['state']!='SUCCEEDED' or run['success_scope']!='LOCAL_CASE_CREATED' or
                not op or op['action']!='case.create' or op['state']!='VERIFIED' or not isinstance(op['receipt'],dict) or
                op['receipt'].get('verified') is not True or op['receipt']!=expected or
                not case or case['source']!='SYNTHETIC' or (case['park_id'],case['org_id'])!=(run['park_id'],run['org_id']) or
                (parent['owner_id'],parent['park_id'],parent['org_id']) !=
                (run['principal_id'],run['park_id'],run['org_id'])):
            raise Conflict('ordinary verified synthetic Case Run required')
        return dict(run_id=str(run['id']),run_revision=run['revision'],
                    input_fingerprint=run['fingerprint'],
                    owner_id=run['principal_id'],park_id=run['park_id'],org_id=run['org_id'],
                    preparation_id=str(parent['id']),preparation_revision=parent['revision'],
                    preparation_state=parent['state'],review_sha256=parent['review_sha256'],
                    material_sha256=prep.snapshot(parent,prep.latest(c,parent['id'])),
                    case_id=str(case['id']),case_state=case['state'])

    def _parent(self, c, run, write=False):
        parent = c.execute('SELECT * FROM preparations WHERE run_id=%s'+
                           (' FOR UPDATE' if write else ''), (run['id'],)).fetchone()
        if not parent:
            raise Conflict('bound preparation required')
        return parent

    def _authority_snapshot(self,c,run,target_id=None):
        ids=sorted({run['principal_id'],*([target_id] if target_id else [])})
        principals=c.execute('SELECT id,role,active,park_id,org_id,xmin::text generation FROM principals WHERE id=ANY(%s) ORDER BY id',(ids,)).fetchall()
        grants=c.execute("""SELECT principal_id,capability,active,revision,park_id,org_id,xmin::text generation
            FROM capability_grants WHERE principal_id=ANY(%s) AND capability IN ('READ','EXECUTE')
            ORDER BY principal_id,capability""",(ids,)).fetchall()
        preparation=c.execute("SELECT principal_id,active,park_id,org_id,xmin::text generation FROM preparation_grants WHERE principal_id=%s AND capability='PREPARE'",(run['principal_id'],)).fetchall()
        return dict(principals=principals,grants=grants,preparation=preparation)

    def _view(self, c, p, run):
        ledger = run.get('native_run_access_protocol') or {}
        parent = self._parent(c, run)
        source = self._source(c, run, parent)
        permit = self._live_permit(c)
        enabled = permit is not None
        revision = ledger.get('revision',0)
        state = ledger.get('state','NOT_REQUESTED')
        request = ledger.get('request')
        authority = dict(source=source,revision=revision,actor=p['id'],
                         permit_revision=permit.revision if enabled else None,
                         approver_ids=sorted(permit.approver_ids) if enabled else [],
                         permit_until=permit.valid_until.isoformat() if enabled else None,
                         current=self._authority_snapshot(c,run,request.get('target_id') if request else None))
        can_request = enabled and p['id']==run['principal_id'] and state not in ('REQUESTED','APPROVED')
        try:
            prep.grant(self.store,c,p,'PREPARE')
            self.store.check_capability(c,p,'EXECUTE')
        except Denied:
            can_request=False
        can_request=can_request and parent['state']=='LOCAL_CONFIRMED' and parent['review_sha256']==source['material_sha256']
        current_request=bool(request and request['source']==source and request.get('authority')==self._authority_snapshot(c,run,request['target_id']) and
                             datetime.fromisoformat(request['requested_validity']['valid_until'])>_now(c))
        targets=[]
        if can_request:
            targets=c.execute("""SELECT p.id FROM principals p JOIN capability_grants g
                ON g.principal_id=p.id AND g.park_id=p.park_id AND g.org_id=p.org_id
                WHERE p.park_id=%s AND p.org_id=%s AND p.active AND p.role='service_executor'
                AND g.active AND g.capability='READ' ORDER BY p.id LIMIT 100""",
                (run['park_id'],run['org_id'])).fetchall()
        result=dict(namespace=NAMESPACE,scope={k:source[k] for k in ('park_id','org_id','run_id')},
                    revision=revision,run_revision=run['revision'],authority_sha256=_hash(authority),
                    state=state,request=deepcopy(request),history=deepcopy(ledger.get('events',[])),
                    leases=deepcopy(ledger.get('leases',[])),lease_id=ledger.get('lease_id'),
                    role=p['role'],enabled=enabled,read_available=True,
                    can_request=can_request and source['case_state'] not in ('CANCELLED','RECONCILING'),
                    can_approve=enabled and p['role']=='park_specialist' and p['id'] in permit.approver_ids and state=='REQUESTED'
                                and source['case_state'] not in ('CANCELLED','RECONCILING') and current_request,
                    can_reject=enabled and p['role']=='park_specialist' and p['id'] in permit.approver_ids and state=='REQUESTED',
                    can_cancel=enabled and p['id']==run['principal_id'] and state=='REQUESTED',
                    can_revoke=enabled and state=='APPROVED' and
                               (p['id']==run['principal_id'] or p['id'] in permit.approver_ids),
                    executors=[dict(**t,role='service_executor',capability='READ') for t in targets],
                    decision_only=True,projection_state='NON_EFFECTIVE',
                    availability_reason='ACTIVATION_PENDING',activation_pending=True,
                    authority_valid_until=permit.valid_until.isoformat() if enabled else None,
                    candidate_access_available=False,actual_run_access=False,
                    actual_assignment_written=False,deployment_enabled=False,
                    qualification_truth='UNKNOWN')
        from .native_run_access_activation import augment_view
        return augment_view(self,c,p,run,result)

    @_bounded
    def read(self, token, run_id):
        with self.store.connect() as c:
            c.execute('SET TRANSACTION READ ONLY')
            c.execute("SET LOCAL lock_timeout='5s'")
            p=self.store.auth(c,token,lock=True)
            run=self._run(c,p,run_id)
            self._authorize_read(c,p,run)
            return self._view(c,p,run)

    @_bounded
    def recover(self, token, run_id, key):
        self._key(key)
        with self.store.connect() as c:
            c.execute('SET TRANSACTION READ ONLY')
            c.execute("SET LOCAL lock_timeout='5s'")
            p=self.store.auth(c,token,lock=True)
            run=self._run(c,p,run_id)
            self._authorize_read(c,p,run)
            events=((run.get('native_run_access_protocol') or {}).get('events',[])+
                    (run.get('native_run_access_activation') or {}).get('events',[]))
            receipt=next((e for e in events if e['actor_id']==p['id'] and e['request_key']==key),None)
            current=self._view(c,p,run)
            return dict(found=receipt is not None,receipt=deepcopy(receipt),
                        namespace=NAMESPACE,actual_run_access=current['actual_run_access'],
                        actual_assignment_written=current['actual_assignment_written'])

    @staticmethod
    def _key(key):
        if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',key):
            raise ValueError('bounded original request key required')

    def _participants_current(self, c, run, request):
        requester=self._principal(c,request['requester_id'],run,'enterprise_operator')
        if requester['id']!=run['principal_id']:
            raise Denied('current owner required')
        prep.grant(self.store,c,requester,'PREPARE')
        self.store.check_capability(c,requester,'EXECUTE')
        self._principal(c,request['target_id'],run,'service_executor')

    def _interval(self, c, value):
        value=Validity.model_validate(value).model_dump()
        start,end=datetime.fromisoformat(value['valid_from']),datetime.fromisoformat(value['valid_until'])
        permit=self._permit(c)
        now=_now(c)
        if (end<=now or start<now-timedelta(seconds=60) or end>permit.valid_until or
                (end-start).total_seconds()>permit.max_access_seconds):
            raise Conflict('bounded current UTC decision interval required')
        return value

    @_bounded
    def command(self, token, run_id, key, data):
        self._key(key)
        data=RunCommand.model_validate(data.model_dump())
        fp=_hash(dict(run_id=str(run_id),command=data.model_dump(mode='json')))
        with self.store.connect() as c:
            c.execute("SET LOCAL lock_timeout='5s'")
            p=self.store.auth(c,token,lock=True)
            self.store.check_capability(c,p,'READ')
            permit=self._permit(c)
            run=self._run(c,p,run_id)
            self._authorize_read(c,p,run)
            c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                      ('native-run-access-key:'+p['id']+':'+key,))
            # Serializes with material, dispatch/ACCEPT, resource association and
            # cancellation before taking any Case lock; no Run→parent lock inversion.
            parent=self._parent(c,run,write=True)
            self._access_lock(c,run_id,exclusive=True)
            run=c.execute('SELECT * FROM runs WHERE id=%s FOR UPDATE',(run_id,)).fetchone()
            self._authorize_read(c,p,run)
            permit=self._permit(c)
            old=self._key_receipt(c,p['id'],key)
            if old:
                if old['e']['fingerprint']!=fp:
                    raise Conflict('original request key fingerprint mismatch')
                return old['e']
            view=self._view(c,p,run)
            if ((data.expected_revision,data.expected_run_revision,data.expected_authority_sha256)!=
                    (view['revision'],view['run_revision'],view['authority_sha256'])):
                raise Conflict('request, Run or current source version changed')
            if view['revision']>=64 or (data.action=='REQUEST' and view['revision']>=62) or (data.action=='APPROVE' and view['revision']>=63):
                raise Conflict('bounded history; reserve revocation capacity')
            source=self._source(c,run,parent)
            ledger=deepcopy(run.get('native_run_access_protocol') or
                            dict(namespace=NAMESPACE,revision=0,state='NOT_REQUESTED',events=[],leases=[]))
            request=ledger.get('request')
            state=ledger['state']
            if data.action=='REQUEST':
                if p['id']!=run['principal_id'] or p['role']!='enterprise_operator':
                    raise Denied('current owner request required')
                prep.grant(self.store,c,p,'PREPARE')
                self.store.check_capability(c,p,'EXECUTE')
                prep.case_write_guard(c,parent)
                if parent['state']!='LOCAL_CONFIRMED' or parent['review_sha256']!=source['material_sha256']:
                    raise Conflict('current owner-confirmed reviewed material required')
                if state in ('REQUESTED','APPROVED'):
                    raise Conflict('cancel or revoke existing protocol first')
                self._principal(c,data.target_id,run,'service_executor')
                request=dict(request_id=str(uuid4()),requester_id=p['id'],target_id=data.target_id,
                             target_role='service_executor',capability='READ',source=source,
                             authority=self._authority_snapshot(c,run,data.target_id),
                             requested_validity=self._interval(c,data.requested_validity.model_dump()))
                ledger.update(request=request,state='REQUESTED',lease_id=None)
            elif data.action in ('APPROVE','REJECT'):
                if (p['id'] not in permit.approver_ids or p['role']!='park_specialist' or
                        not request or p['id'] in (request['requester_id'],request['target_id'])):
                    raise Denied('explicit independent decision authority required')
                if state!='REQUESTED':
                    raise Conflict('current requested protocol required')
                if data.action=='APPROVE':
                    prep.case_write_guard(c,parent)
                    if request['source']!=source:
                        raise Conflict('request source changed')
                    self._participants_current(c,run,request)
                    if request['authority']!=self._authority_snapshot(c,run,request['target_id']):
                        raise Conflict('request participant authority version changed')
                    if datetime.fromisoformat(request['requested_validity']['valid_until'])<=_now(c):
                        raise Conflict('request expired')
                    approved=self._interval(c,data.approved_validity.model_dump())
                    requested=request['requested_validity']
                    if (datetime.fromisoformat(approved['valid_from'])<datetime.fromisoformat(requested['valid_from']) or
                            datetime.fromisoformat(approved['valid_until'])>datetime.fromisoformat(requested['valid_until'])):
                        raise Conflict('approval may only shrink requested interval')
                    lease_id=str(uuid4())
                    request.update(approver_id=p['id'],approved_validity=approved,
                                   approver_authority=self._authority_snapshot(c,run,p['id']))
                    ledger['leases'].append(dict(id=lease_id,state='NON_EFFECTIVE',
                        request_id=request['request_id'],source=source,validity=approved))
                    ledger['lease_id']=lease_id
                    ledger['state']='APPROVED'
                else:
                    ledger['state']='REJECTED'
            elif data.action=='CANCEL':
                if not request or p['id']!=request['requester_id'] or p['id']!=run['principal_id']:
                    raise Denied('current requesting owner required')
                if state!='REQUESTED':
                    raise Conflict('current request required')
                ledger['state']='CANCELLED'
            else:
                if not request or (p['id']!=run['principal_id'] and p['id'] not in permit.approver_ids):
                    raise Denied('current owner or explicit revoker required')
                if state!='APPROVED':
                    raise Conflict('approved protocol required')
                ledger['state']='REVOKED'
            ledger['revision']+=1
            receipt=dict(namespace=NAMESPACE,run_id=str(run_id),actor_id=p['id'],request_key=key,
                         fingerprint=fp,action=data.action,reason=data.reason,
                         revision=ledger['revision'],state=ledger['state'],
                         request=deepcopy(ledger['request']),lease_id=ledger.get('lease_id'),
                         recorded_at=_now(c).isoformat(),actual_run_access=False,
                         actual_assignment_written=False,projection_state='NON_EFFECTIVE')
            ledger['events'].append(receipt)
            c.execute('UPDATE runs SET native_run_access_protocol=%s WHERE id=%s',(Jsonb(ledger),run_id))
            # No external decision store: event, request, decision and lease roll
            # back together, including a failed final permission/time recheck.
            self._permit(c)
            if data.action in ('REQUEST','APPROVE'):
                self._participants_current(c,run,ledger['request'])
                interval=ledger['request'].get('approved_validity') if data.action=='APPROVE' else ledger['request']['requested_validity']
                if datetime.fromisoformat(interval['valid_until'])<=_now(c):
                    raise Conflict('decision interval expired before completion')
            return receipt
