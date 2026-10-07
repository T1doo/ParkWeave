"""Bounded closure of local synthetic records, never fulfillment of the Case goal."""
import json
from datetime import timedelta
from uuid import UUID, uuid4
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from psycopg.types.json import Jsonb
from . import preparation as prep, service_dispatches as sd, executor_receipts as er
from . import resource_combinations as rc, resource_holds as rh
from .store import Conflict, Denied, digest

SCOPE = 'SYNTHETIC_LOCAL_CASE_RECORD_ONLY'
RECHECKS = ('MATERIAL_REVIEW','ACCEPTANCE_RECHECK','RECEIPT_RECHECK','RESOURCE_RECHECK')


class Command(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)
    action: Literal['REVALIDATE','CLOSE_LOCAL_RECORD','REOPEN']
    expected_revision: int = Field(ge=0, le=64)
    expected_cycle: int = Field(ge=1, le=64)
    reason: str = Field(min_length=1, max_length=1000)
    expected_snapshot_sha256: str | None = Field(default=None, pattern='^[a-f0-9]{64}$')


def _auth(store, c, token, id, write=False):
    c.execute("SET LOCAL lock_timeout='3s'")
    p = store.auth(c, token, lock=True)
    if write and p['role'] != 'enterprise_operator': raise Denied('enterprise owner local lifecycle required')
    parent = sd._parent(store,c,p,id,write=write)
    if write: store.check_capability(c,p,'EXECUTE')
    p['_local_case_write']=False
    if p['role']=='enterprise_operator':
        try:store.check_capability(c,p,'EXECUTE');p['_local_case_write']=True
        except Denied:pass
    return p,parent


def _sources(store,c,p,parent):
    """Lock source records before resource mutexes and final Case/ledger locks."""
    issues={name:[] for name in RECHECKS};snapshot={'preparation_id':str(parent['id']),'case_id':str(parent['case_id']),
        'run_id':str(parent['run_id']),'service_id':parent['service_id'],'service_version':parent['service_version'],
        'preparation_revision':parent['revision'],'preparation_sha256':parent['review_sha256']}
    items=prep.latest(c,parent['id'])
    if parent['state']!='LOCAL_CONFIRMED' or {i['slot'] for i in items}!=set(prep.SLOTS) or prep.snapshot(parent,items)!=parent['review_sha256']:
        issues['MATERIAL_REVIEW'].append('CURRENT_MATERIAL_CONFIRMATION_REQUIRED')
    try:sd._party(store,c,parent,parent['reviewer_id'],'REVIEW_ASSIGNED')
    except Denied:issues['MATERIAL_REVIEW'].append('CURRENT_REVIEWER_AUTHORITY_REQUIRED')
    dispatch=sd._root(c,parent)
    offer=sd._own_offer(c,p,dispatch) if dispatch else None
    step=er.current_step(c,parent)
    receipt=er._current(c,step) if step else None
    if not offer:
        issues['ACCEPTANCE_RECHECK'].append('LEGACY_ACCEPTANCE_MISSING' if step else 'ACCEPTED_DISPATCH_REQUIRED')
    elif offer['state']!='ACCEPTED':issues['ACCEPTANCE_RECHECK'].append('ACCEPTED_DISPATCH_REQUIRED')
    else:
        try:er._executor(store,c,offer['executor_id'],parent['run_id'])
        except Denied:issues['ACCEPTANCE_RECHECK'].append('CURRENT_EXECUTOR_AUTHORITY_REQUIRED')
        if not sd._fresh(parent,offer):issues['ACCEPTANCE_RECHECK'].append('ACCEPTANCE_PREPARATION_CHANGED')
        snapshot.update(dispatch_id=str(dispatch['id']),dispatch_revision=dispatch['revision'],offer_id=str(offer['id']),executor_id=offer['executor_id'])
    if not step or not receipt or step['state']!='LOCAL_ACKNOWLEDGED':
        issues['RECEIPT_RECHECK'].append('CURRENT_ACKNOWLEDGED_RECEIPT_REQUIRED')
    elif not er._fresh(step,parent):issues['RECEIPT_RECHECK'].append('RECEIPT_PREPARATION_CHANGED_REPLAN_REQUIRED')
    if step:
        expected=(parent['id'],parent['run_id'],parent['case_id'],parent['owner_id'],parent['park_id'],parent['org_id'],parent['service_id'],parent['service_version'])
        actual=tuple(step[k] for k in ('preparation_id','run_id','case_id','owner_id','park_id','org_id','service_id','service_version'))
        if actual!=expected or not offer or offer['receipt_step_id']!=step['id'] or offer['executor_id']!=step['executor_id']:
            issues['RECEIPT_RECHECK'].append('RECEIPT_ACCEPTANCE_BINDING_CHANGED')
        snapshot.update(receipt_step_id=str(step['id']),receipt_step_revision=step['revision'],receipt_id=str(step['current_receipt_id']) if step['current_receipt_id'] else None,
                        receipt_sha256=receipt['source_sha256'] if receipt else None)
    if receipt and (digest(receipt['text'])!=receipt['source_sha256'] or not step or receipt['actor_id']!=step['executor_id'] or receipt['source_kind']!='SYNTHETIC'):
        issues['RECEIPT_RECHECK'].append('RECEIPT_PROVENANCE_CHANGED')
    link=c.execute('SELECT * FROM case_resource_links WHERE case_id=%s ORDER BY revision DESC LIMIT 1',(parent['case_id'],)).fetchone()
    group=None;holds=[];rules={}
    if not link:issues['RESOURCE_RECHECK'].append('CURRENT_CASE_RESOURCE_LINK_REQUIRED')
    else:
        expected=(parent['id'],parent['run_id'],parent['case_id'],parent['owner_id'],parent['park_id'],parent['org_id'],parent['service_id'],parent['service_version'])
        actual=tuple(link[k] for k in ('preparation_id','run_id','case_id','owner_id','park_id','org_id','service_id','service_version'))
        if actual!=expected or link['preparation_revision']!=parent['revision'] or link['preparation_sha256']!=parent['review_sha256']:
            issues['RESOURCE_RECHECK'].append('RESOURCE_PREPARATION_CHANGED')
        try:
            group=rc._group(c,p,link['combination_id']);holds=rc._members(c,p,group['id'])
            rules=rc._scope_lock(c,p,holds,write=True)
            group=rc._group(c,p,group['id'],lock=True);holds=rc._members(c,p,group['id'],lock=True)
        except Denied:issues['RESOURCE_RECHECK'].append('CURRENT_RESOURCE_AUTHORITY_REQUIRED')
        claim=c.execute('SELECT * FROM resource_case_claims WHERE combination_id=%s',(link['combination_id'],)).fetchone()
        if not claim or (claim['case_id'],claim['owner_id'],claim['park_id'],claim['org_id'])!=(parent['case_id'],parent['owner_id'],parent['park_id'],parent['org_id']):
            issues['RESOURCE_RECHECK'].append('CURRENT_CASE_RESOURCE_CLAIM_REQUIRED')
        from .resource_plan_binding import catalog_decision
        decision=catalog_decision(c,parent,link)
        issues['RESOURCE_RECHECK']+=decision['issues']
        snapshot['resource_catalog_decision']=decision
        snapshot.update(resource_link_id=str(link['id']),resource_link_revision=link['revision'],combination_id=str(link['combination_id']))
        if group and rules:
            snapshot.update(combination_state=group['state'],members=[{k:str(h[k]) for k in ('id','resource_id','resource_revision','starts_at','ends_at','buffer_seconds','quantity','state')} for h in holds])
    return issues,snapshot,group,holds,rules


def _timed(c,issues,group,holds,rules):
    # Called after the last Case/ledger lock, never before a possible blocking wait.
    now=rh._now(c)
    if group and rules:
        if group['state']!='CONFIRMED' or any(h['state']!='CONFIRMED' for h in holds):issues['RESOURCE_RECHECK'].append('RESOURCE_CANCELLED')
        if any(h['ends_at']<=now for h in holds):issues['RESOURCE_RECHECK'].append('RESOURCE_WINDOW_ENDED')
        for h in holds:
            r=rules[h['resource_id']];lo=h['starts_at']-timedelta(seconds=h['buffer_seconds']);hi=h['ends_at']+timedelta(seconds=h['buffer_seconds'])
            if not r['enabled'] or r['revision']!=h['resource_revision']:issues['RESOURCE_RECHECK'].append('RESOURCE_RULE_CHANGED')
            elif lo<r['open_from'] or hi>r['open_until'] or rh._peak(c,h['resource_id'],lo,hi,now)>r['capacity']:issues['RESOURCE_RECHECK'].append('RESOURCE_CONSTRAINT_CHANGED')
    for k in issues:issues[k]=sorted(set(issues[k]))
    return now


def _ledger(c,parent,write=False):
    return c.execute('SELECT * FROM case_local_lifecycles WHERE preparation_id=%s '+('FOR UPDATE' if write else 'FOR SHARE'),(parent['id'],)).fetchone()


def _sha(snapshot,cycle):return digest(prep.canonical({'cycle':cycle,'sources':snapshot}))


def _view(c,p,parent,case,row,issues=None,snapshot=None,event=None):
    owner=p['role']=='enterprise_operator';can_write=owner and p.get('_local_case_write',False);cycle=row['cycle'] if row else 1
    current_sha=_sha(snapshot,cycle) if snapshot is not None else None
    current=bool(row and row['verified_sha256'] and current_sha==row['verified_sha256'] and not any(issues.values())) if issues is not None else None
    history=c.execute('SELECT revision,cycle,action,payload,created_at FROM case_local_events WHERE preparation_id=%s ORDER BY revision',(parent['id'],)).fetchall()
    if not owner:
        history=[{k:v for k,v in e.items() if k!='payload'} for e in history];event=None
    state=row['state'] if row else 'NOT_STARTED'
    return dict(scope=SCOPE,role=p['role'],preparation_id=parent['id'],case_id=parent['case_id'],goal=parent['goal'],case_state=case['state'],
        local_record_state=state,revision=row['revision'] if row else 0,cycle=cycle,
        verification_current=current,current_snapshot_sha256=current_sha if owner else None,
        verified_snapshot_sha256=row['verified_sha256'] if owner and row else None,
        checks=issues if owner else None,required_rechecks=list(RECHECKS) if state=='REOPENED' or current is False else [],
        can_revalidate=can_write and state!='LOCAL_RECORD_CLOSED' and issues is not None and not any(issues.values()) and (not row or row['revision']<63),
        can_close_local_record=can_write and state=='READY' and current and row['revision']<64,
        can_reopen=can_write and state=='LOCAL_RECORD_CLOSED' and row['revision']<=61,
        history=history,event=event,qualification='NOT_EVALUATED',external_acceptance='NOT_SUBMITTED',offline_fulfillment='NO_EVIDENCE',case_goal_completed=False)


@er.bounded
def read(store,token,id):
    with store.connect() as c:
        p,parent=_auth(store,c,token,id)
        sources=_sources(store,c,p,parent) if p['role']=='enterprise_operator' else None
        case=c.execute('SELECT * FROM cases WHERE id=%s FOR SHARE',(parent['case_id'],)).fetchone();row=_ledger(c,parent)
        if sources:_timed(c,sources[0],*sources[2:])
        return _view(c,p,parent,case,row,*(sources[:2] if sources else (None,None)))


@er.bounded
def command(store,token,id,key,data):
    fp=digest(prep.canonical({'preparation_id':str(id),**data.model_dump(mode='json')}))
    with store.connect() as c:
        p,parent=_auth(store,c,token,id,write=True)
        c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('case-local-key:'+p['id']+':'+key,))
        # Reopen and historical replay must not depend on obsolete resource grants.
        old=c.execute('SELECT * FROM case_local_events WHERE actor_id=%s AND request_key=%s',(p['id'],key)).fetchone()
        if old and (old['fingerprint']!=fp or old['preparation_id']!=id):raise Conflict('local Case request key fingerprint mismatch')
        if data.action!='REOPEN' and not old and parent.get('service_case_plan'):
            from .service_case_steps import gate as case_step_gate
            case_step_gate(store,c,parent,4)
        sources=_sources(store,c,p,parent) if data.action!='REOPEN' and not old else None
        case=c.execute('SELECT * FROM cases WHERE id=%s FOR UPDATE',(parent['case_id'],)).fetchone();row=_ledger(c,parent,write=True)
        if old:return _view(c,p,parent,case,row,event=old['payload'])
        if (row['revision'] if row else 0)!=data.expected_revision or (row['cycle'] if row else 1)!=data.expected_cycle:
            raise Conflict('stale local Case revision or cycle; refresh required')
        if row and row['revision']>=64:raise Conflict('local Case history limit reached')
        cycle=row['cycle'] if row else 1;sha=None;snapshot=None
        if data.action=='REOPEN':
            if not row or row['state']!='LOCAL_RECORD_CLOSED':raise Conflict('closed local record required for reopen')
            if row['revision']>61:raise Conflict('local Case history limit cannot accommodate another cycle')
            state='REOPENED';case_state='REOPENED';cycle+=1
        else:
            issues,snapshot,group,holds,rules=sources;_timed(c,issues,group,holds,rules)
            if any(issues.values()):raise Conflict('local Case prerequisites need recheck')
            sha=_sha(snapshot,cycle)
            if data.expected_snapshot_sha256!=sha:raise Conflict('local Case source snapshot changed; refresh required')
            if data.action=='REVALIDATE':
                if row and row['state']=='LOCAL_RECORD_CLOSED':raise Conflict('reopen closed local record before revalidation')
                if row and row['state']=='READY' and row['verified_sha256']==sha:raise Conflict('current cycle already validated')
                if row and row['revision']>=63:raise Conflict('local Case history limit cannot accommodate closure')
                state='READY'
            else:
                if not row or row['state']!='READY' or row['verified_sha256']!=sha:raise Conflict('current cycle explicit revalidation required')
                state='LOCAL_RECORD_CLOSED'
            case_state='WAITING_CONFIRMATION'
        if row:
            row=c.execute('UPDATE case_local_lifecycles SET revision=revision+1,cycle=%s,state=%s,verified_snapshot=%s,verified_sha256=%s WHERE preparation_id=%s RETURNING *',(cycle,state,Jsonb(snapshot) if snapshot else None,sha,id)).fetchone()
        else:
            row=c.execute('INSERT INTO case_local_lifecycles(preparation_id,case_id,revision,cycle,state,verified_snapshot,verified_sha256) VALUES(%s,%s,1,%s,%s,%s,%s) RETURNING *',(id,parent['case_id'],cycle,state,Jsonb(snapshot),sha)).fetchone()
        case=c.execute('UPDATE cases SET state=%s WHERE id=%s RETURNING *',(case_state,parent['case_id'])).fetchone()
        payload=dict(action=data.action,revision=row['revision'],cycle=cycle,local_record_state=state,case_state=case_state,
                     actor_id=p['id'],reason=data.reason,verified_snapshot_sha256=sha,scope=SCOPE)
        c.execute('INSERT INTO case_local_events(id,preparation_id,actor_id,request_key,fingerprint,revision,cycle,action,payload,snapshot) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',(uuid4(),id,p['id'],key,fp,row['revision'],cycle,data.action,Jsonb(payload),Jsonb(snapshot) if snapshot else None))
        # Return no new resource reads/locks after Case lock. Reopen explicitly invalidates checks.
        return _view(c,p,parent,case,row,sources[0] if sources else None,snapshot,event=payload)
