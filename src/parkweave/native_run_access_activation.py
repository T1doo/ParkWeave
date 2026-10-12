"""Default-closed native activation; the only issuer is an owned PG test fixture.

The fixture owner writes one exact assignment atomically with its receipt. No
production writer/policy is inferred from a database row or an environment flag.
"""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator
from psycopg.types.json import Jsonb

from . import preparation as prep
from .native_run_access import NativeRunAccess, _proof, _owner_connection, _hash, _now, _bounded
from .store import Conflict, Denied

NAMESPACE='ORDINARY_PG_RUN_ACCESS_ACTIVATION_V1'
STORAGE=Path(__file__).with_name('native-run-access-activation-storage.sql')
_issued_activation_permits={}


class Activate(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    action: Literal['ACTIVATE']
    lease_id: UUID=Field(strict=False)
    expected_revision: int=Field(ge=1)
    expected_run_revision: int=Field(ge=1)
    expected_activation_revision: int=Field(ge=0)
    expected_authority_sha256: str=Field(pattern='^[a-f0-9]{64}$')
    activation_policy_sha256: str=Field(pattern='^[a-f0-9]{64}$')
    confirm_activate: Literal[True]
    reason: str=Field(min_length=1,max_length=1000)

    @field_validator('confirm_activate',mode='before')
    @classmethod
    def explicit_confirmation(cls,value):
        if type(value) is not bool or value is not True:
            raise ValueError('explicit boolean true activation confirmation required')
        return value


@dataclass(frozen=True)
class ActivationTestPermit:
    owner: object
    decision_permit: object
    binding_json: str
    policy_sha256: str


def install_owned_test_activation_storage(owner,proof):
    _proof(owner,proof)
    with owner.connect() as c:
        _owner_connection(c,proof)
        if not NativeRunAccess(owner)._storage(c):
            raise Denied('existing native decision fixture storage required')
        c.execute(STORAGE.read_text())


def _approver_authority(bridge,c,run,actor):
    bridge._principal(c,actor,run,'park_specialist')
    return bridge._authority_snapshot(c,run,actor)


def _read_source(source):
    # State describes business progress. It must not turn historical READ into
    # a write guard after VERIFY, cancellation, reconciliation or local closure.
    return {k:v for k,v in source.items() if k!='case_state'}


def _generations(c,owner,target,approver):
    ids=sorted({owner,target,approver})
    return dict(principals=c.execute('SELECT id,xmin::text generation FROM principals WHERE id=ANY(%s) ORDER BY id',(ids,)).fetchall(),
        capabilities=c.execute("""SELECT principal_id,capability,xmin::text generation
            FROM capability_grants WHERE principal_id=ANY(%s) AND capability IN ('READ','EXECUTE')
            ORDER BY principal_id,capability""",(ids,)).fetchall(),
        preparation=c.execute("""SELECT principal_id,capability,xmin::text generation
            FROM preparation_grants WHERE principal_id=%s AND capability='PREPARE'""",(owner,)).fetchall())


def issue_activation_test_permit(owner,proof,decision_permit,*,run_id,lease_id,
                                 approver_id,executor_id,validity):
    """Explicit test capability for exactly the supplied approved scope/interval."""
    _proof(owner,proof)
    bridge=NativeRunAccess(owner,test_permit=decision_permit)
    with owner.connect() as c:
        _owner_connection(c,proof)
        permit=bridge._permit(c)
        if permit.proof is not proof:
            raise Denied('same issued owned decision fixture required')
        run=c.execute('SELECT * FROM runs WHERE id=%s',(run_id,)).fetchone()
        ledger=(run or {}).get('native_run_access_protocol') or {}
        request=ledger.get('request') or {}
        if (not run or ledger.get('state')!='APPROVED' or
                str(lease_id)!=ledger.get('lease_id') or
                approver_id not in permit.approver_ids or approver_id!=request.get('approver_id') or
                executor_id!=request.get('target_id') or validity!=request.get('approved_validity')):
            raise Denied('explicit exact approved fixture lease/actors/interval required')
        parent=bridge._parent(c,run,write=True)
        bridge._access_lock(c,run_id)
        run=c.execute('SELECT * FROM runs WHERE id=%s FOR SHARE',(run_id,)).fetchone()
        ledger=run.get('native_run_access_protocol') or {}
        request=ledger.get('request') or {}
        if ledger.get('state')!='APPROVED' or ledger.get('lease_id')!=str(lease_id):
            raise Conflict('approved decision changed while issuing fixture enablement')
        prep.case_write_guard(c,parent)
        source=bridge._source(c,run,parent)
        if _read_source(source)!=_read_source(request['source']):
            raise Conflict('approved activation source changed')
        bridge._participants_current(c,run,request)
        authority=bridge._authority_snapshot(c,run,executor_id)
        if authority!=request['authority']:
            raise Conflict('approved participant authority changed')
        if _approver_authority(bridge,c,run,approver_id)!=request.get('approver_authority'):
            raise Conflict('approved independent authority generation changed')
        binding=dict(namespace=NAMESPACE,run_id=str(run_id),lease_id=str(lease_id),
            request_id=request['request_id'],protocol_revision=ledger['revision'],
            owner_id=run['principal_id'],executor_id=executor_id,approver_id=approver_id,
            capability='READ',source=deepcopy(request['source']),authority=authority,
            approver_authority=_approver_authority(bridge,c,run,approver_id),validity=validity,
            authority_generations=_generations(c,run['principal_id'],executor_id,approver_id))
        encoded=prep.canonical(binding)
        policy_sha=_hash(dict(binding=binding,database_name=proof.database_name,
                             database_oid=proof.database_oid,
                             postmaster_start=proof.cluster.postmaster_start.isoformat()))
        result=ActivationTestPermit(owner,permit,encoded,policy_sha)
        _issued_activation_permits[id(result)]=result
        return result


def _permit(bridge,c,run_id):
    if bridge.writer is not None:
        from .native_run_access_writer import binding
        return binding(bridge,c,run_id)
    value=bridge.activation_permit
    if (type(bridge) is not NativeRunAccess or type(value) is not ActivationTestPermit or
            _issued_activation_permits.get(id(value)) is not value or
            bridge.test_permit is not value.decision_permit or bridge.store.mode!='LOCAL' or
            getattr(bridge.store,'_isolated_run_access',None) is not None):
        raise Denied('trusted production activation authority unavailable')
    bridge._permit(c)
    schemas=c.execute('SELECT current_schemas(true) value').fetchone()['value']
    if 'public' not in schemas or not set(schemas)<={'public','pg_catalog'}:
        raise Denied('native provider refuses temporary/shadow relation scope')
    binding=json.loads(value.binding_json)
    if binding['run_id']!=str(run_id) or _now(c)>=datetime.fromisoformat(binding['validity']['valid_until']):
        raise Denied('exact fixture activation scope expired or changed')
    return value,binding


def _current(bridge,c,run,binding):
    ledger=run.get('native_run_access_protocol') or {}
    request=ledger.get('request') or {}
    source=bridge._source(c,run,bridge._parent(c,run))
    bridge._participants_current(c,run,request)
    if (ledger.get('state')!='APPROVED' or ledger.get('revision')!=binding['protocol_revision'] or
            ledger.get('lease_id')!=binding['lease_id'] or
            request.get('request_id')!=binding['request_id'] or
            request.get('requester_id')!=binding['owner_id'] or
            request.get('target_id')!=binding['executor_id'] or
            request.get('approver_id')!=binding['approver_id'] or
            request.get('approved_validity')!=binding['validity'] or
            _read_source(source)!=_read_source(binding['source']) or
            _read_source(request.get('source',{}))!=_read_source(binding['source']) or
            request.get('authority')!=binding['authority'] or
            bridge._authority_snapshot(c,run,binding['executor_id'])!=binding['authority'] or
            _approver_authority(bridge,c,run,binding['approver_id'])!=binding['approver_authority'] or
            _generations(c,binding['owner_id'],binding['executor_id'],binding['approver_id'])!=binding['authority_generations'] or
            not any(x==dict(id=binding['lease_id'],state='NON_EFFECTIVE',
                           request_id=binding['request_id'],source=request['source'],
                           validity=binding['validity']) for x in ledger.get('leases',[]))):
        raise Denied('native lease current source/authority/decision binding changed')
    now=_now(c)
    if not datetime.fromisoformat(binding['validity']['valid_from'])<=now<datetime.fromisoformat(binding['validity']['valid_until']):
        raise Denied('native lease outside its exact approved UTC interval')


def _activation_allowed(c,parent):
    prep.case_write_guard(c,parent)
    lifecycle=c.execute('SELECT state FROM case_local_lifecycles WHERE preparation_id=%s',(parent['id'],)).fetchone()
    if lifecycle and lifecycle['state']=='LOCAL_RECORD_CLOSED':
        raise Conflict('locally closed Case cannot receive a new activation')


def _marker(event):
    return dict(namespace=NAMESPACE,activation_id=event['activation_id'],
                lease_id=event['lease_id'],policy_sha256=event['policy_sha256'],
                binding=deepcopy(event['binding']))


def effective(bridge,c,p,run_id,assignment):
    try:
        from .store import _AccessConnection
        if not isinstance(c,_AccessConnection):return False
        if (c.autocommit or not assignment or not assignment['active'] or
                p['role']!='service_executor' or not p['active'] or
                assignment.get('managed_access') is not None or
                not isinstance(assignment.get('native_access'),dict)):
            return False
        permit,binding=_permit(bridge,c,run_id)
        if (p['id']!=binding['executor_id'] or
                (assignment['principal_id'],str(assignment['run_id']),assignment['park_id'],assignment['org_id'])!=
                (p['id'],str(run_id),p['park_id'],p['org_id'])):
            return False
        readonly=c.execute("SELECT current_setting('transaction_read_only')='on' value").fetchone()['value']
        # Obtain the parent before Run scope locks on the first access check.
        # Commit checks repeat the same already-held locks; no late inversion.
        parent=c.execute('SELECT * FROM preparations WHERE run_id=%s'+('' if readonly else ' FOR SHARE'),(run_id,)).fetchone()
        if not parent:return False
        bridge._access_lock(c,run_id)
        run=c.execute('SELECT * FROM runs WHERE id=%s'+('' if readonly else ' FOR SHARE'),(run_id,)).fetchone()
        if not run:return False
        _current(bridge,c,run,binding)
        ledger=run.get('native_run_access_activation') or {}
        events=ledger.get('events',[])
        if not events:return False
        event=events[-1]
        actual=c.execute('SELECT * FROM run_assignments WHERE principal_id=%s AND run_id=%s',(p['id'],run_id)).fetchone()
        return bool(actual and actual['active'] and actual.get('managed_access') is None and
            actual.get('native_access')==assignment['native_access']==_marker(event) and
            event['binding']==binding and event['policy_sha256']==permit.policy_sha256 and
            event['state']=='ACTIVATED' and event['actor_id']==binding['owner_id'] and
            event['lease_id']==binding['lease_id'] and ledger['activation_id']==event['activation_id'])
    except (Denied,Conflict,KeyError,TypeError,ValueError):
        return False


def augment_view(bridge,c,p,run,result):
    ledger=run.get('native_run_access_activation') or {}
    result.update(activation_revision=ledger.get('revision',0),
                  activation_history=deepcopy(ledger.get('events',[])),
                  activation_policy_sha256=None,can_activate=False,activation_enabled=False,
                  production_policy_adopted=False,actual_assignment_written=bool(ledger.get('events')))
    try:
        permit,binding=_permit(bridge,c,run['id'])
        _current(bridge,c,run,binding)
        result.update(activation_policy_sha256=permit.policy_sha256,activation_enabled=True)
        target=bridge._principal(c,binding['executor_id'],run,'service_executor')
        # Metadata reports access; it does not consume beneficiary scope. Owner
        # revocation must be able to invalidate it in this same transaction.
        available=bridge.store.assignment_allowed(c,target,run['id'],track=False)
        result.update(actual_run_access=available,
                      actual_assignment_written=bool(ledger.get('events')),
                      decision_only=False,activation_pending=not available,
                      projection_state='ACTIVE_SYNTHETIC_FIXTURE' if available else 'NON_EFFECTIVE',
                      availability_reason='LIVE_OWNED_FIXTURE_LEASE' if available else 'ACTIVATION_PENDING')
        try:
            _activation_allowed(c,bridge._parent(c,run))
            result['can_activate']=p['id']==binding['owner_id'] and not available
        except Conflict:
            pass
    except (Denied,Conflict,KeyError,TypeError,ValueError):
        pass
    return result


@_bounded
def activate(bridge,token,run_id,key,data):
    bridge._key(key)
    data=Activate.model_validate(data.model_dump())
    if bridge.writer is not None:
        from .native_run_access_writer import WriterClient,invoke
        if type(bridge.writer) is WriterClient:
            return invoke(bridge,'ACTIVATE',token,run_id,key,data)
    permit=bridge.activation_permit
    if bridge.writer is None and (type(permit) is not ActivationTestPermit or _issued_activation_permits.get(id(permit)) is not permit):
        raise Denied('trusted production activation authority unavailable')
    # The restricted owner channel cannot lend its writer to a foreign business
    # Store. Verify the Store's actual endpoint/database before opening that
    # channel; the owner transaction separately verifies the same issued proof.
    with bridge.store._guarded_connect() as business:
        business.execute('SET TRANSACTION READ ONLY')
        _permit(bridge,business,run_id)
    fp=_hash(dict(run_id=str(run_id),command=data.model_dump(mode='json')))
    # This existing owned fixture connection is a narrowly issued test writer.
    # Authentication and all current checks occur in this SAME transaction.
    with bridge.store._guarded_connect(permit.owner.dsn if bridge.writer is None else None) as c:
        c.execute("SET LOCAL lock_timeout='5s'")
        if bridge.writer is None:
            _owner_connection(c,permit.decision_permit.proof)
        permit,binding=_permit(bridge,c,run_id)
        p=bridge.store.auth(c,token,lock=True)
        bridge.store.check_capability(c,p,'READ')
        run=bridge._run(c,p,run_id)
        bridge._authorize_read(c,p,run)
        if p['role']!='enterprise_operator' or p['id']!=binding['owner_id']:
            raise Denied('current exact owner activation required')
        prep.grant(bridge.store,c,p,'PREPARE')
        bridge.store.check_capability(c,p,'EXECUTE')
        c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('native-run-access-key:'+p['id']+':'+key,))
        parent=bridge._parent(c,run,write=True)
        bridge._access_lock(c,run_id,exclusive=True)
        run=c.execute('SELECT * FROM runs WHERE id=%s FOR UPDATE',(run_id,)).fetchone()
        old=bridge._key_receipt(c,p['id'],key)
        if old:
            return bridge._original_receipt(c,old,run_id,fp)
        if bridge.writer is not None:
            from .native_run_access_writer import before_action
            before_action(bridge,c,p,'ACTIVATE',run_id,data)
        _permit(bridge,c,run_id)
        view=bridge._view(c,p,run)
        if (data.expected_revision,data.expected_run_revision,data.expected_authority_sha256,
                data.expected_activation_revision,str(data.lease_id),data.activation_policy_sha256)!=(
                view['revision'],view['run_revision'],view['authority_sha256'],view['activation_revision'],
                binding['lease_id'],permit.policy_sha256):
            raise Conflict('exact activation decision/source/permit version changed')
        _current(bridge,c,run,binding)
        _activation_allowed(c,parent)
        old_assignment=c.execute('SELECT * FROM run_assignments WHERE principal_id=%s AND run_id=%s FOR UPDATE',
                                 (binding['executor_id'],run_id)).fetchone()
        ledger=deepcopy(run.get('native_run_access_activation') or dict(namespace=NAMESPACE,revision=0,events=[]))
        if old_assignment:
            prior=ledger['events'][-1] if ledger['events'] else None
            if (not prior or old_assignment.get('managed_access') is not None or
                    old_assignment.get('native_access')!=_marker(prior)):
                raise Denied('legacy/isolated/unknown assignment cannot be replaced')
            if prior['lease_id']==binding['lease_id']:
                raise Conflict('lease already activated; recover its original key')
        if ledger['revision']>=64:raise Conflict('bounded immutable activation history')
        receipt=dict(namespace=NAMESPACE,run_id=str(run_id),actor_id=p['id'],request_key=key,
            fingerprint=fp,action='ACTIVATE',reason=data.reason,state='ACTIVATED',
            revision=ledger['revision']+1,activation_id=str(uuid4()),lease_id=binding['lease_id'],
            policy_sha256=permit.policy_sha256,binding=deepcopy(binding),recorded_at=_now(c).isoformat(),
            actual_run_access=True,actual_assignment_written=True,
            projection_state='ACTIVE_SYNTHETIC_FIXTURE',production_policy_adopted=False)
        if bridge.writer is not None:
            from .native_run_access_writer import sign
            receipt=sign(bridge,receipt)
        ledger['events'].append(receipt);ledger.update(revision=receipt['revision'],activation_id=receipt['activation_id'])
        c.execute('UPDATE runs SET native_run_access_activation=%s WHERE id=%s',(Jsonb(ledger),run_id))
        c.execute("""INSERT INTO run_assignments(principal_id,run_id,park_id,org_id,active,native_access)
            VALUES(%s,%s,%s,%s,true,%s) ON CONFLICT(principal_id,run_id) DO UPDATE
            SET active=true,native_access=excluded.native_access""",
            (binding['executor_id'],run_id,run['park_id'],run['org_id'],Jsonb(_marker(receipt))))
        target=bridge._principal(c,binding['executor_id'],run,'service_executor')
        if not bridge.store.assignment_allowed(c,target,run_id):
            raise Denied('activated lease expired or changed before completion')
        # Guarded commit performs a final live recheck, including after any wait.
        return receipt
