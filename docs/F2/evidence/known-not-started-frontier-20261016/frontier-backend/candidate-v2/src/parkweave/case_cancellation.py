from .business_frontier_types import BusinessFrontierFence,request as frontier_request
from .business_frontier import view as frontier_view,check_fence
"""Owner cancellation of an ordinary synthetic Case before any actual acceptance.

The parent lock serializes absence of a dispatch/receipt against their creation.
Lock order is parent -> dispatch -> Case -> local ledger. Resources are retained.
"""
import json
from typing import Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator
from psycopg.types.json import Jsonb
from . import preparation as prep, service_dispatches as sd, executor_receipts as er
from .store import Conflict, Denied, digest

SCOPE='SYNTHETIC_CASE_CANCEL_BEFORE_FIRST_ACCEPT'
ACTION='CANCEL_BEFORE_ACCEPT'

class Cancel(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    case_id: UUID=Field(strict=False)
    expected_preparation_revision: int=Field(ge=1,le=64)
    expected_lifecycle_revision: int=Field(ge=0,le=63)
    expected_source_sha256: str=Field(pattern='^[a-f0-9]{64}$')
    confirm_cancel: Literal[True]
    reason: str=Field(min_length=1,max_length=1000)
    expected_business_frontier: BusinessFrontierFence | None = None

    @field_validator('confirm_cancel',mode='before')
    @classmethod
    def explicit_confirmation(cls,value):
        if value is not True:raise ValueError('explicit boolean cancellation confirmation required')
        return value


def _context(store,c,token,id,write=False):
    c.execute("SET LOCAL lock_timeout='3s'")
    p=store.auth(c,token,lock=True)
    if p['role']!='enterprise_operator':raise Denied('enterprise Case owner required')
    # Intentionally no business guard: original cancel keys remain replayable.
    parent=prep.scoped(store,c,p,id,write=write)
    if write:store.check_capability(c,p,'EXECUTE')
    return p,parent


def _locks(c,parent,write=False):
    root=sd._root(c,parent,write=write)
    case=c.execute('SELECT * FROM cases WHERE id=%s '+('FOR UPDATE' if write else 'FOR SHARE'),(parent['case_id'],)).fetchone()
    local=c.execute('SELECT * FROM case_local_lifecycles WHERE preparation_id=%s '+('FOR UPDATE' if write else 'FOR SHARE'),(parent['id'],)).fetchone()
    return root,case,local


def _source(c,parent,root,case,local,*,check_before_accept=True):
    run=c.execute('SELECT * FROM runs WHERE id=%s',(parent['run_id'],)).fetchone()
    op=c.execute('SELECT * FROM operations WHERE run_id=%s',(parent['run_id'],)).fetchone()
    issues=[]
    if not c.execute('SELECT 1 FROM schema_version WHERE version=30').fetchone():issues.append('CANCELLATION_INCREMENT_NOT_INSTALLED')
    if (not case or not run or not op or parent['namespace']!='SYNTHETIC' or case['source']!='SYNTHETIC'
        or run['namespace']!='SYNTHETIC'
        or (case['run_id'],case['park_id'],case['org_id'])!=(parent['run_id'],parent['park_id'],parent['org_id'])
        or (run['principal_id'],run['park_id'],run['org_id'])!=(parent['owner_id'],parent['park_id'],parent['org_id'])):
        issues.append('ORDINARY_SYNTHETIC_CASE_REQUIRED')
    receipt=(op or {}).get('receipt') or {}
    from .domain import Intake
    try:
        original=Intake.model_validate(run['input'])
        if original.action!='case.create' or digest(json.dumps(run['input'],sort_keys=True,ensure_ascii=False))!=run['fingerprint']:
            raise ValueError()
    except (TypeError,KeyError,ValueError):issues.append('ORDINARY_SYNTHETIC_CASE_REQUIRED')
    if (not run or run['state']!='SUCCEEDED' or run['success_scope']!='LOCAL_CASE_CREATED'
        or not isinstance(run['input'],dict) or run['input'].get('action','case.create')!='case.create' or not op or op['action']!='case.create'
        or op['state']!='VERIFIED' or not isinstance(receipt,dict) or receipt.get('verified') is not True or receipt!={'case_id':str(parent['case_id']), 'source':'LOCAL_DATABASE',
            'verified':True,'success_scope':'LOCAL_CASE_CREATED'}):
        issues.append('VERIFIED_SUCCESSFUL_CASE_CREATION_REQUIRED')
    if case and case['state']=='CANCELLED':issues.append('CASE_ALREADY_CANCELLED')
    if case and case['state'] not in ('NEEDS_INPUT','WAITING_CONFIRMATION','REOPENED','CANCELLED'):
        issues.append('CASE_STATE_NOT_SUPPORTED')
    if case and (case['external_acceptance']!='NOT_SUBMITTED' or case['offline_fulfillment']!='NO_EVIDENCE'):
        issues.append('CASE_FULFILLMENT_NOT_SUPPORTED')
    # Check the entire lineage, never only the currently selected offer.
    if check_before_accept and (c.execute("SELECT 1 FROM service_dispatch_events e JOIN service_dispatches d ON d.id=e.dispatch_id WHERE d.preparation_id=%s AND e.action='ACCEPT' LIMIT 1",(parent['id'],)).fetchone() or c.execute("SELECT 1 FROM service_dispatch_offers o JOIN service_dispatches d ON d.id=o.dispatch_id WHERE d.preparation_id=%s AND (o.state='ACCEPTED' OR o.receipt_step_id IS NOT NULL) LIMIT 1",(parent['id'],)).fetchone()):
        issues.append('HISTORICAL_ACCEPTANCE_NOT_SUPPORTED')
    if check_before_accept and c.execute('SELECT 1 FROM service_receipt_steps WHERE preparation_id=%s OR case_id=%s LIMIT 1',(parent['id'],parent['case_id'])).fetchone():
        issues.append('RECEIPT_STEP_NOT_SUPPORTED')
    if (local and local['state']=='LOCAL_RECORD_CLOSED') or c.execute("SELECT 1 FROM case_local_events WHERE preparation_id=%s AND action='CLOSE_LOCAL_RECORD' LIMIT 1",(parent['id'],)).fetchone():
        issues.append('LOCAL_CLOSURE_NOT_SUPPORTED')
    if local and local['revision']>=64:issues.append('LOCAL_HISTORY_LIMIT_REACHED')
    items=prep.latest(c,parent['id'])
    if any(digest(i['text'])!=i['source_sha256'] for i in items):issues.append('MATERIAL_SOURCE_PROOF_REQUIRED')
    snapshot=dict(preparation_id=str(parent['id']),case_id=str(parent['case_id']),run_id=str(parent['run_id']),
        preparation_revision=parent['revision'],material_sha256=prep.snapshot(parent,items),
        case_state=case['state'] if case else None,lifecycle_revision=local['revision'] if local else 0,
        lifecycle_cycle=local['cycle'] if local else 1,dispatch_revision=root['revision'] if root else 0,
        run_revision=run['revision'] if run else None,operation_id=str(op['id']) if op else None,
        run_state=run['state'] if run else None,
        operation_state=op['state'] if op else None,creation_receipt=receipt,
        service_id=parent['service_id'],service_version=parent['service_version'])
    return snapshot,sorted(set(issues))


def _view(store,c,p,parent,root,case,local):
    source,issues=_source(c,parent,root,case,local)
    allowed=True
    try:store.check_capability(c,p,'EXECUTE')
    except Denied:allowed=False
    return dict(**frontier_view(c,parent),scope=SCOPE,actor_id=p['id'],preparation_id=str(parent['id']),case_id=str(parent['case_id']),
        case_state=case['state'],preparation_revision=parent['revision'],lifecycle_revision=local['revision'] if local else 0,
        source_sha256=digest(prep.canonical(source)),source=source,blockers=issues,
        can_cancel=allowed and not issues,resource_release_automatic=False,restore_supported=False,
        run_state=source['run_state'],
        case_goal_completed=False)


def _original(c,p,parent,key,*,scope=SCOPE,action=ACTION):
    old=c.execute('SELECT * FROM case_local_events WHERE actor_id=%s AND request_key=%s',(p['id'],key)).fetchone()
    if not old:return None
    if old['preparation_id']!=parent['id'] or old['action']!=action:raise Conflict('original cancellation request scope mismatch')
    try:
        event=old['payload'];data=Cancel.model_validate(event['request']);snapshot=old['snapshot']
        if (event['scope']!=scope or event['actor_id']!=p['id'] or event['request_key']!=key or
            event['preparation_id']!=str(parent['id']) or event['case_id']!=str(parent['case_id']) or
            event['revision']!=old['revision'] or event['cycle']!=old['cycle'] or
            event['case_state']!='CANCELLED' or event['action']!=action or event['resource_release_automatic'] is not False or
            data.case_id!=parent['case_id'] or data.expected_lifecycle_revision+1!=old['revision'] or
            snapshot['lifecycle_cycle']!=old['cycle'] or snapshot['case_id']!=str(parent['case_id']) or
            snapshot['preparation_id']!=str(parent['id']) or snapshot['preparation_revision']!=data.expected_preparation_revision or
            digest(prep.canonical(snapshot))!=data.expected_source_sha256 or
            digest(prep.canonical(dict(preparation_id=str(parent['id']),**frontier_request(data))))!=old['fingerprint']):
            raise ValueError()
    except (KeyError,TypeError,ValueError):raise Conflict('original cancellation proof mismatch') from None
    return old


def _result(old):return dict(scope=old['payload']['scope'],status='COMMITTED',event_id=str(old['id']),event=old['payload'],
    historical_only=True,automatically_replayed=False,resource_release_automatic=False)


def _committed_state(case,local,old):
    if not case or case['state']!='CANCELLED' or not local or local['state']!='CANCELLED' or local['revision']!=old['revision']:
        raise Conflict('committed cancellation state proof mismatch')


@er.bounded
def read(store,token,id):
    with store.connect() as c:
        p,parent=_context(store,c,token,id)
        return _view(store,c,p,parent,*_locks(c,parent))


@er.bounded
def recover(store,token,id,key):
    with store.connect() as c:
        p,parent=_context(store,c,token,id)
        c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('case-local-key:'+p['id']+':'+key,))
        root,case,local=_locks(c,parent)
        old=_original(c,p,parent,key)
        result=_result(old) if old else dict(scope=SCOPE,status='NOT_OBSERVED',event=None,event_id=None,historical_only=True,automatically_replayed=False)
        if old:_committed_state(case,local,old)
        return dict(**result,current=_view(store,c,p,parent,root,case,local))


@er.bounded
def cancel(store,token,id,key,data):
    fp=digest(prep.canonical(dict(preparation_id=str(id),**frontier_request(data))))
    with store.connect() as c:
        p,parent=_context(store,c,token,id,True)
        c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('case-local-key:'+p['id']+':'+key,))
        root,case,local=_locks(c,parent,True)
        old=_original(c,p,parent,key)
        if old:
            if old['fingerprint']!=fp:raise Conflict('cancellation key fingerprint mismatch')
            _committed_state(case,local,old)
            return _result(old)
        check_fence(c,parent,data)
        if not c.execute('SELECT 1 FROM schema_version WHERE version=30').fetchone():raise Conflict('owned synthetic cancellation increment not installed')
        source,issues=_source(c,parent,root,case,local)
        if issues:raise Conflict(';'.join(issues))
        if (data.case_id!=parent['case_id'] or data.expected_preparation_revision!=parent['revision'] or
            data.expected_lifecycle_revision!=(local['revision'] if local else 0) or data.expected_source_sha256!=digest(prep.canonical(source))):
            raise Conflict('exact Case and material source version required; refresh and explicitly confirm')
        return _commit(c,p,parent,local,key,data,fp,source)


def _commit(c,p,parent,local,key,data,fp,source,*,scope=SCOPE,action=ACTION):
    """Caller has proved its bounded policy and holds parent/dispatch/Case locks."""
    id=parent['id'];cycle=local['cycle'] if local else 1
    if local:
        local=c.execute("UPDATE case_local_lifecycles SET revision=revision+1,state='CANCELLED',verified_snapshot=NULL,verified_sha256=NULL WHERE preparation_id=%s RETURNING *",(id,)).fetchone()
    else:
        local=c.execute("INSERT INTO case_local_lifecycles(preparation_id,case_id,revision,cycle,state) VALUES(%s,%s,1,1,'CANCELLED') RETURNING *",(id,parent['case_id'])).fetchone()
    c.execute("UPDATE cases SET state='CANCELLED' WHERE id=%s",(parent['case_id'],))
    event=dict(scope=scope,action=action,actor_id=p['id'],request_key=key,preparation_id=str(id),case_id=str(parent['case_id']),
        revision=local['revision'],cycle=cycle,case_state='CANCELLED',resource_release_automatic=False,request=frontier_request(data))
    old=c.execute('INSERT INTO case_local_events(id,preparation_id,actor_id,request_key,fingerprint,revision,cycle,action,payload,snapshot) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *',
        (uuid4(),id,p['id'],key,fp,local['revision'],cycle,action,Jsonb(event),Jsonb(source))).fetchone()
    return _result(old)
