"""Explicit same-owner material-outline copies; never inherited review or authority."""
from copy import deepcopy
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from . import preparation as prep, material_corrections as corrections
from .executor_receipts import bounded
from .store import Conflict, Denied, digest

SCOPE='SYNTHETIC_SAME_OWNER_MATERIAL_OUTLINE_REUSE'
PURPOSE='SAME_SERVICE_MATERIAL_OUTLINE'
LIMIT=100


class MaterialReuse(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    expected_target_revision:int=Field(ge=1,le=63)
    source_preparation_id:UUID=Field(strict=False)
    expected_source_preparation_revision:int=Field(ge=1,le=64)
    source_evidence_id:UUID=Field(strict=False)
    expected_source_evidence_version:int=Field(ge=1)
    expected_source_evidence_sha256:str=Field(pattern='^[a-f0-9]{64}$')
    expected_source_snapshot_sha256:str=Field(pattern='^[a-f0-9]{64}$')
    purpose:Literal['SAME_SERVICE_MATERIAL_OUTLINE']
    reason:str=Field(min_length=1,max_length=1000)


def _auth(store,c,token):
    c.execute("SET LOCAL lock_timeout='3s'")
    p=store.auth(c,token,lock=True)
    prep.grant(store,c,p,'PREPARE');store.check_capability(c,p,'EXECUTE')
    if not c.execute("SELECT 1 FROM action_grants WHERE principal_id=%s AND action='case.create' AND park_id=%s AND org_id=%s AND active",(p['id'],p['park_id'],p['org_id'])).fetchone():
        raise Denied('current case action grant required')
    return p


def _scope(store,c,p,id,write=False):
    row=prep.scoped(store,c,p,id,write=write)
    run=store.scoped_run(c,p,row['run_id'])
    case=c.execute('SELECT * FROM cases WHERE id=%s AND run_id=%s AND park_id=%s AND org_id=%s',
                   (row['case_id'],row['run_id'],p['park_id'],p['org_id'])).fetchone()
    if row['namespace']!='SYNTHETIC' or run['principal_id']!=p['id'] or run['input'].get('action','case.create')!='case.create' or run['state']!='SUCCEEDED' or not case or case['source']!='SYNTHETIC':
        raise Denied('own synthetic Case and Run binding required')
    return row


def _target_issues(c,target):
    issues=[]
    if target['state']!='IN_PREPARATION' or target['review_sha256'] is not None:issues.append('FRESH_TARGET_PREPARATION_REQUIRED')
    if target['revision']>=64:issues.append('TARGET_HISTORY_LIMIT_REACHED')
    if c.execute('SELECT 1 FROM preparation_evidence WHERE preparation_id=%s',(target['id'],)).fetchone():issues.append('EMPTY_TARGET_EVIDENCE_REQUIRED')
    for table in ('service_dispatches','service_receipt_steps','case_resource_links','case_local_lifecycles'):
        if c.execute('SELECT 1 FROM '+table+' WHERE preparation_id=%s',(target['id'],)).fetchone():issues.append('TARGET_BUSINESS_RECORDS_EXIST')
    if c.execute('SELECT 1 FROM resource_case_claims WHERE case_id=%s',(target['case_id'],)).fetchone():issues.append('TARGET_BUSINESS_RECORDS_EXIST')
    if corrections.active(target.get('material_corrections')):issues.append('TARGET_ACTIVE_CORRECTION')
    return sorted(set(issues))


def _source(c,source,target,evidence_id=None):
    if (source['id']==target['id'] or source['case_id']==target['case_id'] or source['run_id']==target['run_id'] or
        (source['owner_id'],source['park_id'],source['org_id'],source['namespace'],source['service_id'],source['service_version'])!=
        (target['owner_id'],target['park_id'],target['org_id'],'SYNTHETIC',target['service_id'],target['service_version'])):
        raise Conflict('distinct same-owner same-service material source required')
    latest=prep.latest(c,source['id'])
    if source['state']!='LOCAL_CONFIRMED' or corrections.active(source.get('material_corrections')) or {i['slot'] for i in latest}!=set(prep.SLOTS) or any(digest(i['text'])!=i['source_sha256'] for i in latest) or prep.snapshot(source,latest)!=source['review_sha256']:
        raise Conflict('current confirmed source materials required')
    outline=next(i for i in latest if i['slot']=='material_outline')
    if evidence_id is not None and outline['id']!=evidence_id:raise Conflict('current material outline source required')
    item=c.execute('SELECT * FROM preparation_evidence WHERE id=%s AND preparation_id=%s',(outline['id'],source['id'])).fetchone()
    if not item or item['actor_id']!=source['owner_id'] or item['authenticity']!='UNVERIFIED':raise Conflict('original owner-authored material source required')
    if c.execute("SELECT 1 FROM preparation_events WHERE preparation_id=%s AND payload->'material_reuse'->>'target_evidence_id'=%s",(source['id'],str(item['id']))).fetchone():
        raise Conflict('reused material cannot be a reuse source')
    return item


def _metadata(source,item):
    return dict(source_preparation_id=str(source['id']),source_case_id=str(source['case_id']),source_run_id=str(source['run_id']),
                source_goal=source['goal'],
                source_preparation_revision=source['revision'],source_snapshot_sha256=source['review_sha256'],
                source_evidence_id=str(item['id']),source_evidence_version=item['version'],source_evidence_sha256=item['source_sha256'],
                source_kind=item['source_kind'],source_label=item['source_label'])


def _history(store,c,p,target):
    rows=c.execute("SELECT id,revision,payload FROM preparation_events WHERE preparation_id=%s AND payload ? 'material_reuse' ORDER BY revision",(target['id'],)).fetchall()
    result=[]
    for row in rows:
        proof=deepcopy(row['payload']['material_reuse']);status='HISTORICAL_SOURCE_CHANGED'
        try:
            source=_scope(store,c,p,UUID(proof['source_preparation_id']))
        except Denied:
            proof={k:proof[k] for k in ('target_evidence_id','target_version','target_sha256','purpose','requires_independent_review','snapshot_mode')}
            status='SOURCE_UNAVAILABLE'
        else:
            try:
                item=_source(c,source,target,UUID(proof['source_evidence_id']))
                if all(proof.get(k)==v for k,v in _metadata(source,item).items()):status='CURRENT_SOURCE_SNAPSHOT'
            except Conflict:pass
        result.append(dict(event_id=str(row['id']),revision=row['revision'],material_reuse=proof,source_status=status))
    return result


@bounded
def candidates(store,token,id,source_evidence_id=None):
    with store.connect() as c:
        p=_auth(store,c,token);target=_scope(store,c,p,id)
        issues=_target_issues(c,target);items=[];preview=None
        if source_evidence_id is not None:
            source_id=c.execute('SELECT preparation_id FROM preparation_evidence WHERE id=%s',(source_evidence_id,)).fetchone()
            if not source_id:raise Denied('material source unavailable')
            source=_scope(store,c,p,source_id['preparation_id'])
            item=_source(c,source,target,source_evidence_id)
            preview=dict(**_metadata(source,item),text=item['text'],purpose=PURPOSE)
        rows=c.execute("SELECT id FROM preparations WHERE owner_id=%s AND park_id=%s AND org_id=%s AND namespace='SYNTHETIC' AND service_id=%s AND service_version=%s AND state='LOCAL_CONFIRMED' AND id<>%s ORDER BY created_at DESC,id LIMIT %s",
                       (p['id'],p['park_id'],p['org_id'],target['service_id'],target['service_version'],id,LIMIT+1)).fetchall() if not issues else []
        for row in rows[:LIMIT]:
            try:
                source=_scope(store,c,p,row['id']);item=_source(c,source,target)
            except (Denied,Conflict):continue
            items.append(_metadata(source,item))
        return dict(scope=SCOPE,role=p['role'],target=dict(preparation_id=str(target['id']),case_id=str(target['case_id']),run_id=str(target['run_id']),
                    revision=target['revision'],state=target['state'],service_id=target['service_id'],service_version=target['service_version']),
                    can_reuse=not issues and bool(items or preview),target_issues=issues,items=items,has_older_sources=len(rows)>LIMIT,
                    source_preview=preview,history=_history(store,c,p,target),purpose=PURPOSE,requires_independent_review=True,
                    qualification='NOT_EVALUATED',external_acceptance='NOT_SUBMITTED',offline_fulfillment='NO_EVIDENCE',case_goal_completed=False)


def _save(c,p,target,key,fp,item,proof):
    added=prep._insert_evidence(c,p,target,'material_outline',item['text'],item['source_kind'],item['source_label'])
    proof=dict(proof,target_evidence_id=str(added['id']),target_version=added['version'],target_sha256=added['source_sha256'],
               requires_independent_review=True,snapshot_mode='INDEPENDENT_COPY')
    updated=c.execute("UPDATE preparations SET state='IN_PREPARATION',revision=revision+1,review_sha256=NULL WHERE id=%s RETURNING *",(target['id'],)).fetchone()
    from .controlled_plans import invalidate
    invalidate(c,target['id'],1)
    return prep.event(c,p,updated,key,fp,'ADD_EVIDENCE',snapshot_sha256=prep.snapshot(updated,prep.latest(c,target['id'])),reason=proof['reason'],material_reuse=proof)


@bounded
def reuse(store,token,id,key,data):
    fp=digest(prep.canonical(dict(action='MATERIAL_OUTLINE_REUSE',target_preparation_id=str(id),**data.model_dump(mode='json'))))
    with store.connect() as c:
        p=_auth(store,c,token);prep.key_lock(c,p,key)
        rows={ref:_scope(store,c,p,ref,write=True) for ref in sorted({id,data.source_preparation_id},key=str)}
        target=rows[id];source=rows[data.source_preparation_id]
        old=prep.replay(c,p,key,fp,id)
        if old:return old
        if target['revision']!=data.expected_target_revision:raise Conflict('target preparation revision changed')
        issues=_target_issues(c,target)
        if issues:raise Conflict('fresh target required: '+','.join(issues))
        item=_source(c,source,target,data.source_evidence_id)
        if (source['revision']!=data.expected_source_preparation_revision or source['review_sha256']!=data.expected_source_snapshot_sha256 or
            item['version']!=data.expected_source_evidence_version or item['source_sha256']!=data.expected_source_evidence_sha256):
            raise Conflict('source material version or snapshot changed')
        proof=dict(**_metadata(source,item),source_actor_id=item['actor_id'],purpose=data.purpose,reason=data.reason)
        return _save(c,p,target,key,fp,item,proof)


read=candidates
