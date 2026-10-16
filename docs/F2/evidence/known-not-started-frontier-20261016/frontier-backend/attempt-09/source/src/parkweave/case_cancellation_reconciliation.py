from .business_frontier_types import BusinessFrontierFence,request as frontier_request
from .business_frontier import view as frontier_view,check_fence
"""Explicit cancellation intent and owner reconciliation of existing manual facts.

No receipt is created or changed. The common parent lock freezes all business
writes while independent, currently authorized resource release stays available.
"""
from typing import Literal
from uuid import UUID,uuid4
from pydantic import BaseModel,ConfigDict,Field,model_validator
from psycopg.types.json import Jsonb
from . import case_cancellation as cc,case_cancellation_before_receipt as cb,case_lifecycle as lc,executor_receipts as er,preparation as prep
from .store import Conflict,digest,Denied

SCOPE='SYNTHETIC_MANUAL_RECEIPT_CASE_CANCELLATION_RECONCILIATION'
ACTIONS=('REQUEST_CANCEL','RECONCILE','CONFIRM_CANCEL')


class Outcome(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    step_id: UUID=Field(strict=False)
    receipt_id: UUID=Field(strict=False)
    version: int=Field(ge=1,le=64)
    receipt_sha256: str=Field(pattern='^[a-f0-9]{64}$')
    outcome: Literal['KNOWN_LOCAL_RESULT','UNRESOLVED']


class Command(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    expected_business_frontier: BusinessFrontierFence | None = None
    action: Literal['REQUEST_CANCEL','RECONCILE','CONFIRM_CANCEL']
    case_id: UUID=Field(strict=False)
    expected_preparation_revision: int=Field(ge=1,le=64)
    expected_lifecycle_revision: int=Field(ge=0,le=63)
    expected_source_sha256: str=Field(pattern='^[a-f0-9]{64}$')
    confirm: bool
    reason: str=Field(min_length=1,max_length=1000)
    request_event_id: UUID|None=Field(default=None,strict=False)
    reconciliation_event_id: UUID|None=Field(default=None,strict=False)
    receipts: list[Outcome]=Field(default_factory=list,max_length=64)

    @model_validator(mode='after')
    def explicit(self):
        if self.confirm is not True:raise ValueError('explicit boolean confirmation required')
        if self.action=='REQUEST_CANCEL':
            if self.request_event_id or self.reconciliation_event_id or self.receipts:raise ValueError('request cannot imply reconciliation')
        elif not self.request_event_id:raise ValueError('exact original request required')
        if self.action=='RECONCILE':
            if self.reconciliation_event_id or not self.receipts:raise ValueError('explicit complete receipt outcomes required')
        elif self.receipts:raise ValueError('receipt outcomes apply only to explicit reconciliation')
        if self.action=='CONFIRM_CANCEL' and not self.reconciliation_event_id:raise ValueError('exact latest reconciliation required')
        return self


def _ledger(c,parent,lineage):
    """Replay each immutable manual receipt generation, including old versions."""
    steps=c.execute('SELECT * FROM service_receipt_steps WHERE preparation_id=%s OR case_id=%s ORDER BY id LIMIT 65',(parent['id'],parent['case_id'])).fetchall()
    events=c.execute('''SELECT e.* FROM service_receipt_events e JOIN service_receipt_steps s ON s.id=e.step_id
        WHERE s.preparation_id=%s OR s.case_id=%s ORDER BY s.id,e.revision LIMIT 65''',(parent['id'],parent['case_id'])).fetchall()
    receipts=c.execute('''SELECT r.* FROM service_step_receipts r JOIN service_receipt_steps s ON s.id=r.step_id
        WHERE s.preparation_id=%s OR s.case_id=%s ORDER BY s.id,r.version LIMIT 65''',(parent['id'],parent['case_id'])).fetchall()
    issues=[];heads=[];bound=set()
    if not receipts:issues.append('HISTORICAL_MANUAL_SUBMISSION_REQUIRED')
    if any(len(rows)>64 for rows in (steps,events,receipts)):issues.append('MANUAL_LEDGER_LIMIT_REACHED')
    by_id={r['id']:r for r in receipts}
    for step in steps:
        sequence=[e for e in events if e['step_id']==step['id']]
        state='AWAITING_RECEIPT';revision=1;current=None;version=0
        try:
            if not sequence or sequence[0]['action']!='CREATE' or sequence[0]['revision']!=1:raise ValueError()
            for event in sequence[1:]:
                revision+=1;payload=event['payload'];action=event['action']
                if not isinstance(payload,dict) or event['revision']!=revision:raise ValueError()
                if action=='SUBMIT':
                    receipt=next((r for r in receipts if str(r['id'])==payload.get('receipt_id')),None)
                    version+=1
                    if (state not in ('AWAITING_RECEIPT','CHANGES_REQUESTED') or not receipt
                        or receipt['id'] in bound or receipt['step_id']!=step['id'] or receipt['version']!=version
                        or receipt['actor_id']!=step['executor_id'] or receipt['source_kind']!='SYNTHETIC'
                        or receipt.get('adapter_execution') is not None or digest(receipt['text'])!=receipt['source_sha256']):raise ValueError()
                    request=er.Command(action='SUBMIT',expected_revision=revision-1,text=receipt['text'],source_kind='SYNTHETIC',source_label=receipt['source_label'],
                        **({'expected_business_frontier':payload['expected_business_frontier']} if 'expected_business_frontier' in payload else {}))
                    current=receipt;state='RECEIPT_RECORDED';bound.add(receipt['id'])
                    heads.append(dict(step_id=str(step['id']),receipt_id=str(receipt['id']),version=version,receipt_sha256=receipt['source_sha256'],
                        submit_event_id=str(event['id']),submit_revision=revision,submit_fingerprint=event['fingerprint']))
                    actor=step['executor_id']
                else:
                    if not current or action not in ('ACKNOWLEDGE','REQUEST_CHANGES','REOPEN'):raise ValueError()
                    if action in ('ACKNOWLEDGE','REQUEST_CHANGES') and state!='RECEIPT_RECORDED':raise ValueError()
                    if action=='REOPEN' and state not in ('RECEIPT_RECORDED','LOCAL_ACKNOWLEDGED'):raise ValueError()
                    request=er.Command(action=action,expected_revision=revision-1,receipt_sha256=current['source_sha256'],reason=payload['reason'],
                        **({'expected_business_frontier':payload['expected_business_frontier']} if 'expected_business_frontier' in payload else {}))
                    state={'ACKNOWLEDGE':'LOCAL_ACKNOWLEDGED','REQUEST_CHANGES':'CHANGES_REQUESTED','REOPEN':'AWAITING_RECEIPT'}[action]
                    actor=parent['owner_id']
                expected=dict(step_id=str(step['id']),revision=revision,state=state,action=action,actor_id=actor,scope=er.SCOPE,
                    receipt_id=str(current['id']),receipt_sha256=current['source_sha256'],reason=request.reason)
                if 'expected_business_frontier' in payload:expected['expected_business_frontier']=frontier_request(request)['expected_business_frontier']
                if (event['actor_id']!=actor or set(payload)!=set(expected) or not cb.sd._typed_fields_equal(payload,expected)
                    or digest(prep.canonical(dict(step_id=str(step['id']),**frontier_request(request))))!=event['fingerprint']):raise ValueError()
            if (step['revision']!=revision or step['state']!=state or step['current_receipt_id']!=(current['id'] if current else None)
                or revision>64):raise ValueError()
        except (KeyError,TypeError,ValueError):issues.append('EXACT_MANUAL_SUBMISSION_AND_DECISION_PROOF_REQUIRED')
    if bound!=set(by_id):issues.append('ALL_HISTORICAL_RECEIPTS_MUST_HAVE_EXACT_SUBMISSION_PROOF')
    return dict(steps=cb._json(steps),events=cb._json(events),receipts=cb._json(receipts),heads=heads),issues


def _fingerprint(id,data):return digest(prep.canonical(dict(preparation_id=str(id),**frontier_request(data))))


def _record(event,parent):
    try:
        payload=event['payload'];snapshot=event['snapshot']
        if not isinstance(payload,dict) or not isinstance(snapshot,dict):raise ValueError()
        data=Command.model_validate(payload['request'])
        expected=dict(scope=SCOPE,action=data.action,actor_id=parent['owner_id'],request_key=event['request_key'],
            preparation_id=str(parent['id']),case_id=str(parent['case_id']),revision=event['revision'],cycle=event['cycle'],
            case_state='CANCELLED' if data.action=='CONFIRM_CANCEL' else 'RECONCILING',resource_release_automatic=False,
            request=frontier_request(data))
        if (event['preparation_id']!=parent['id'] or event['actor_id']!=parent['owner_id'] or event['action']!=data.action
            or set(payload)!=set(expected) or prep.canonical(payload)!=prep.canonical(expected)
            or data.case_id!=parent['case_id'] or data.expected_preparation_revision!=snapshot['preparation_revision']
            or data.expected_lifecycle_revision!=snapshot['lifecycle_revision'] or data.expected_lifecycle_revision+1!=event['revision']
            or event['cycle']!=snapshot['lifecycle_cycle'] or snapshot['preparation_id']!=str(parent['id'])
            or snapshot['case_id']!=str(parent['case_id']) or data.expected_source_sha256!=digest(prep.canonical(snapshot))
            or snapshot['cancellation_scope']!=SCOPE or digest(prep.canonical(snapshot['immutable_source']))!=snapshot['immutable_source_sha256']
            or event['fingerprint']!=_fingerprint(parent['id'],data)):raise ValueError()
        return data
    except (KeyError,TypeError,ValueError):raise Conflict('original cancellation reconciliation proof mismatch') from None


def _outcomes(data,heads):
    expected={(h['step_id'],h['receipt_id'],h['version'],h['receipt_sha256']) for h in heads}
    actual=[(str(r.step_id),str(r.receipt_id),r.version,r.receipt_sha256) for r in data.receipts]
    return len(actual)==len(expected)==len(heads) and set(actual)==expected


def _phase(c,parent,case,local,base,immutable,immutable_sha,heads):
    global_rows=c.execute('SELECT * FROM case_local_events WHERE preparation_id=%s ORDER BY revision LIMIT 65',(parent['id'],)).fetchall()
    rows=[row for row in global_rows if row['action'] in ACTIONS]
    issues=[];request=None;latest=None;previous=None;terminal=False
    try:
        if len(global_rows)>64 or any(row['revision']!=index+1 for index,row in enumerate(global_rows)):raise ValueError()
        if any(row['cycle']!=1 for row in global_rows) or (local and local['cycle']!=1):raise ValueError()
        if local:
            if len(global_rows)!=local['revision'] or (global_rows and global_rows[-1]['cycle']!=local['cycle']):raise ValueError()
        elif global_rows:raise ValueError()
        if any(row['action'] not in (*ACTIONS,'REVALIDATE') for row in global_rows):raise ValueError()
        if rows and any(row['action'] not in ACTIONS for row in global_rows if row['revision']>=rows[0]['revision']):raise ValueError()
        for old in global_rows:
            if old['action'] in ACTIONS:continue
            payload=old['payload'];snapshot=old['snapshot']
            if not isinstance(payload,dict) or not isinstance(snapshot,dict) or old['actor_id']!=parent['owner_id'] or old['cycle']!=1:raise ValueError()
            original=lc.Command(action='REVALIDATE',expected_revision=old['revision']-1,expected_cycle=1,
                reason=payload['reason'],expected_snapshot_sha256=lc._sha(snapshot,1),
                **({'expected_business_frontier':payload['expected_business_frontier']} if 'expected_business_frontier' in payload else {}))
            expected=dict(action='REVALIDATE',revision=old['revision'],cycle=1,local_record_state='READY',case_state='WAITING_CONFIRMATION',
                actor_id=parent['owner_id'],reason=original.reason,verified_snapshot_sha256=original.expected_snapshot_sha256,scope=lc.SCOPE)
            if 'expected_business_frontier' in payload:expected['expected_business_frontier']=frontier_request(original)['expected_business_frontier']
            if prep.canonical(payload)!=prep.canonical(expected) or old['fingerprint']!=digest(prep.canonical(dict(preparation_id=str(parent['id']),**frontier_request(original)))):raise ValueError()
            if any(snapshot.get(k)!=str(parent[v]) for k,v in (('preparation_id','id'),('case_id','case_id'),('run_id','run_id'))):raise ValueError()
        prefix=[row for row in global_rows if row['action']=='REVALIDATE']
        initial_case_state='WAITING_CONFIRMATION' if prefix else 'NEEDS_INPUT'
        if not rows:
            if case['state']!=initial_case_state:raise ValueError()
            if prefix and (not local or local['state']!='READY' or local['verified_sha256']!=prefix[-1]['payload']['verified_snapshot_sha256']
                or prep.canonical(local['verified_snapshot'])!=prep.canonical(prefix[-1]['snapshot'])):raise ValueError()
        for index,row in enumerate(rows):
            data=_record(row,parent)
            prior=[dict(id=str(e['id']),action=e['action'],revision=e['revision'],fingerprint=e['fingerprint'],
                payload_sha256=digest(prep.canonical(e['payload'])),snapshot_sha256=digest(prep.canonical(e['snapshot']))) for e in rows[:index]]
            expected=dict(**{k:v for k,v in base.items() if k not in ('case_state','lifecycle_revision','lifecycle_cycle')},
                case_state=initial_case_state if index==0 else 'RECONCILING',
                lifecycle_revision=row['revision']-1,lifecycle_cycle=row['cycle'],cancellation_scope=SCOPE,
                immutable_source_sha256=immutable_sha,immutable_source=immutable,cancellation_events=prior)
            if prep.canonical(row['snapshot'])!=prep.canonical(expected):raise ValueError()
            if terminal or (previous and (row['revision']!=previous['revision']+1 or row['cycle']!=previous['cycle'])):raise ValueError()
            if row['snapshot']['immutable_source_sha256']!=immutable_sha:raise ValueError()
            if data.action=='REQUEST_CANCEL':
                if request or previous or data.expected_lifecycle_revision>61 or row['snapshot']['case_state'] not in ('NEEDS_INPUT','WAITING_CONFIRMATION','REOPENED'):raise ValueError()
                request=row
            else:
                if not request or data.request_event_id!=request['id'] or row['snapshot']['case_state']!='RECONCILING':raise ValueError()
                if data.action=='RECONCILE':
                    if not _outcomes(data,heads) or data.expected_lifecycle_revision>=63:raise ValueError()
                    if data.expected_lifecycle_revision>=62 and any(r.outcome=='UNRESOLVED' for r in data.receipts):raise ValueError()
                    latest=row
                else:
                    if not latest or data.reconciliation_event_id!=latest['id']:raise ValueError()
                    reconciled=_record(latest,parent)
                    if not _outcomes(reconciled,heads) or any(r.outcome!='KNOWN_LOCAL_RESULT' for r in reconciled.receipts):raise ValueError()
                    terminal=True
            previous=row
        if rows:
            expected='CANCELLED' if terminal else 'RECONCILING'
            if not local or case['state']!=expected or local['state']!=expected or local['revision']!=rows[-1]['revision'] or local['cycle']!=rows[-1]['cycle']:raise ValueError()
        elif case['state']=='RECONCILING' or (local and local['state']=='RECONCILING'):raise ValueError()
    except (Conflict,KeyError,TypeError,ValueError):issues.append('EXACT_CANCELLATION_PHASE_PROOF_REQUIRED')
    return rows,request,latest,terminal,issues


def _source(store,c,parent,root,case,local):
    base,issues=cc._source(c,parent,root,case,local,check_before_accept=False)
    # RECONCILING/CANCELLED are accepted only with a fully validated new ledger.
    issues=[i for i in issues if i not in ('CASE_STATE_NOT_SUPPORTED','CASE_ALREADY_CANCELLED','LOCAL_HISTORY_LIMIT_REACHED')]
    if case['state'] not in ('NEEDS_INPUT','WAITING_CONFIRMATION','REOPENED','RECONCILING','CANCELLED'):issues.append('CASE_STATE_NOT_SUPPORTED')
    if not c.execute('SELECT 1 FROM schema_version WHERE version=32').fetchone():issues.append('CANCELLATION_RECONCILIATION_INCREMENT_NOT_INSTALLED')
    lineage,lineage_issues=cb._manual_lineage(store,c,parent,root,allow_manual_receipts=True)
    ledger,ledger_issues=_ledger(c,parent,lineage)
    immutable=dict(**{k:v for k,v in base.items() if k not in ('case_state','lifecycle_revision','lifecycle_cycle')},
        manual_lineage=lineage,manual_ledger=ledger,
        controlled_plan=cb._head(c.execute('SELECT * FROM controlled_plans WHERE preparation_id=%s',(parent['id'],)).fetchone()),
        registered_plan=cb._head(parent.get('service_case_plan')),
        prior_local_events=[dict(id=str(e['id']),action=e['action'],revision=e['revision'],cycle=e['cycle'],fingerprint=e['fingerprint'],
            payload_sha256=digest(prep.canonical(e['payload'])),snapshot_sha256=digest(prep.canonical(e['snapshot']))) for e in
            c.execute('SELECT * FROM case_local_events WHERE preparation_id=%s AND NOT(action=ANY(%s)) ORDER BY revision LIMIT 65',(parent['id'],list(ACTIONS))).fetchall()],
        resource_links=[cb._head(x) for x in c.execute('SELECT * FROM case_resource_links WHERE case_id=%s ORDER BY revision',(parent['case_id'],)).fetchall()])
    immutable_sha=digest(prep.canonical(immutable))
    rows,request,latest,terminal,phase_issues=_phase(c,parent,case,local,base,immutable,immutable_sha,ledger['heads'])
    if case['state']=='CANCELLED' and not terminal:issues.append('CASE_ALREADY_CANCELLED')
    source=dict(**base,cancellation_scope=SCOPE,immutable_source_sha256=immutable_sha,immutable_source=immutable,
        cancellation_events=[dict(id=str(e['id']),action=e['action'],revision=e['revision'],fingerprint=e['fingerprint'],
            payload_sha256=digest(prep.canonical(e['payload'])),snapshot_sha256=digest(prep.canonical(e['snapshot']))) for e in rows])
    return source,sorted(set(issues+lineage_issues+ledger_issues+phase_issues)),rows,request,latest,terminal


def _view(store,c,p,parent,root,case,local):
    source,issues,rows,request,latest,terminal=_source(store,c,parent,root,case,local)
    allowed=True
    try:store.check_capability(c,p,'EXECUTE')
    except Denied:allowed=False
    revision=local['revision'] if local else 0
    known=bool(latest and all(r.outcome=='KNOWN_LOCAL_RESULT' for r in _record(latest,parent).receipts)) if not issues else False
    # Corrupt/foreign-bound history must not export unproved receipt bodies.
    public_source=source if not issues else {**source,'immutable_source':{
        **source['immutable_source'],'manual_lineage':{'proof_unavailable':True},
        'manual_ledger':{'proof_unavailable':True,'heads':[],'receipts':[]}}}
    return dict(**frontier_view(c,parent),scope=SCOPE,actor_id=p['id'],preparation_id=str(parent['id']),case_id=str(parent['case_id']),case_state=case['state'],
        preparation_revision=parent['revision'],lifecycle_revision=revision,source_sha256=digest(prep.canonical(public_source)),source=public_source,
        blockers=issues,can_request=allowed and not issues and not request and revision<=61,
        can_reconcile=allowed and not issues and bool(request) and not terminal and revision<63,
        can_confirm=allowed and not issues and not terminal and known and revision<64,
        request_event_id=str(request['id']) if request else None,reconciliation_event_id=str(latest['id']) if latest else None,
        receipts=source['immutable_source']['manual_ledger']['heads'] if not issues else [],outcomes=latest['payload']['request']['receipts'] if latest and not issues else [],
        history=[dict(event_id=str(e['id']),event=e['payload']) for e in rows],unresolved_results=not known,
        resource_release_automatic=False,restore_supported=False,case_goal_completed=False,run_state=source['run_state'])


def _result(event):return dict(scope=SCOPE,status='COMMITTED',event_id=str(event['id']),event=event['payload'],
    historical_only=True,automatically_replayed=False,resource_release_automatic=False)


@er.bounded
def read(store,token,id):
    with store.connect() as c:
        p,parent=cc._context(store,c,token,id)
        return _view(store,c,p,parent,*cc._locks(c,parent))


@er.bounded
def recover(store,token,id,key):
    with store.connect() as c:
        p,parent=cc._context(store,c,token,id)
        c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('case-local-key:'+p['id']+':'+key,))
        root,case,local=cc._locks(c,parent)
        old=c.execute('SELECT * FROM case_local_events WHERE actor_id=%s AND request_key=%s',(p['id'],key)).fetchone()
        current=_view(store,c,p,parent,root,case,local)
        if old:
            _record(old,parent)
            if current['blockers'] or not any(e['event_id']==str(old['id']) for e in current['history']):raise Conflict('current cancellation phase proof mismatch')
            result=_result(old)
        else:result=dict(scope=SCOPE,status='NOT_OBSERVED',event_id=None,event=None,historical_only=True,automatically_replayed=False)
        return dict(**result,current=current)


@er.bounded
def command(store,token,id,key,data):
    fp=_fingerprint(id,data)
    with store.connect() as c:
        p,parent=cc._context(store,c,token,id,True)
        c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('case-local-key:'+p['id']+':'+key,))
        root,case,local=cc._locks(c,parent,True)
        source,issues,rows,request,latest,terminal=_source(store,c,parent,root,case,local)
        old=c.execute('SELECT * FROM case_local_events WHERE actor_id=%s AND request_key=%s',(p['id'],key)).fetchone()
        if old:
            _record(old,parent)
            if old['fingerprint']!=fp or old['action']!=data.action:raise Conflict('original reconciliation request key fingerprint mismatch')
            if issues or old['id'] not in {e['id'] for e in rows}:raise Conflict('current cancellation phase proof mismatch')
            return _result(old)
        check_fence(c,parent,data)
        if issues:raise Conflict(';'.join(issues))
        if (data.case_id!=parent['case_id'] or data.expected_preparation_revision!=parent['revision']
            or data.expected_lifecycle_revision!=(local['revision'] if local else 0) or data.expected_source_sha256!=digest(prep.canonical(source))):
            raise Conflict('exact Case, material, cancellation and complete manual source required; refresh and explicitly confirm')
        revision=local['revision'] if local else 0
        if terminal:raise Conflict('Case cancellation already terminal')
        if data.action=='REQUEST_CANCEL':
            if request or revision>61:raise Conflict('new explicit cancellation request with reconciliation capacity required')
        else:
            if not request or data.request_event_id!=request['id']:raise Conflict('exact original cancellation request required')
            if data.action=='RECONCILE':
                if revision>=63 or not _outcomes(data,source['immutable_source']['manual_ledger']['heads']):raise Conflict('all original receipt identities, versions and hashes required')
                if revision>=62 and any(r.outcome=='UNRESOLVED' for r in data.receipts):raise Conflict('reserve capacity for another explicit reconciliation and final confirmation')
            elif not latest or data.reconciliation_event_id!=latest['id'] or any(r.outcome!='KNOWN_LOCAL_RESULT' for r in _record(latest,parent).receipts):
                raise Conflict('all results must be explicitly known in the exact latest reconciliation; remain RECONCILING')
        target='CANCELLED' if data.action=='CONFIRM_CANCEL' else 'RECONCILING';cycle=local['cycle'] if local else 1
        if local:local=c.execute('UPDATE case_local_lifecycles SET revision=revision+1,state=%s,verified_snapshot=NULL,verified_sha256=NULL WHERE preparation_id=%s RETURNING *',(target,id)).fetchone()
        else:local=c.execute('INSERT INTO case_local_lifecycles(preparation_id,case_id,revision,cycle,state) VALUES(%s,%s,1,1,%s) RETURNING *',(id,parent['case_id'],target)).fetchone()
        c.execute('UPDATE cases SET state=%s WHERE id=%s',(target,parent['case_id']))
        payload=dict(scope=SCOPE,action=data.action,actor_id=p['id'],request_key=key,preparation_id=str(id),case_id=str(parent['case_id']),
            revision=local['revision'],cycle=cycle,case_state=target,resource_release_automatic=False,request=frontier_request(data))
        event=c.execute('''INSERT INTO case_local_events(id,preparation_id,actor_id,request_key,fingerprint,revision,cycle,action,payload,snapshot)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',(uuid4(),id,p['id'],key,fp,local['revision'],cycle,data.action,Jsonb(payload),Jsonb(source))).fetchone()
        return _result(event)
