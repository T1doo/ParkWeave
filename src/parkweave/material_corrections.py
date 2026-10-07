"""Assigned reviewer's slot-specific correction requests and actual source review.

Request bases and past review sources remain historical evidence. New text or a
decision reason alone never resolves a correction or proves external fulfillment.
"""
from copy import deepcopy
from uuid import uuid4

from . import preparation as prep
from .executor_receipts import bounded
from .store import Conflict, Denied, digest

LIMIT=16
SCOPE='SYNTHETIC_SLOT_MATERIAL_CORRECTIONS'


def materials(c,id):
    return c.execute('SELECT DISTINCT ON(slot) id,slot,version,text,source_kind,source_label,source_sha256,actor_id,authenticity FROM preparation_evidence WHERE preparation_id=%s ORDER BY slot,version DESC',(id,)).fetchall()


def source(item):
    if not item:return None
    return dict(evidence_id=str(item['id']),version=item['version'],source_kind=item['source_kind'],
                source_label=item['source_label'],source_sha256=item['source_sha256'],actor_id=item['actor_id'])


def targets(ledger):
    return [target for request in ledger or [] for target in request['targets']]


def active(ledger):
    return [target for target in targets(ledger) if target['status']=='ACTIVE']


def submitted(target,item,owner_id):
    current=source(item)
    return bool(item and item['version']>target['base_version'] and item['actor_id']==owner_id
                and item['source_kind'] in ('USER_STATEMENT','DOCUMENT_EXCERPT')
                and digest(item['text'])==item['source_sha256']
                and any(all(entry.get(k)==v for k,v in current.items()) for entry in target['submissions']))


def request(row,p,slots,reason,items):
    ledger=deepcopy(row.get('material_corrections') or [])
    if len(ledger)>=LIMIT:raise Conflict('material correction request history limit reached')
    by_slot={item['slot']:item for item in items}
    entry=dict(id=str(uuid4()),preparation_revision=row['revision']+1,requested_by=p['id'],reason=reason,
               source='ASSIGNED_SPECIALIST_REQUEST',targets=[])
    for slot in slots:
        item=by_slot.get(slot);id=str(uuid4())
        for previous in active(ledger):
            if previous['slot']==slot:
                previous.update(status='SUPERSEDED',superseded_by=id,superseded_revision=row['revision']+1)
        entry['targets'].append(dict(id=id,slot=slot,base_version=item['version'] if item else 0,
                                    base_sha256=item['source_sha256'] if item else None,base_source=source(item),
                                    status='ACTIVE',submissions=[],resolved_source=None,resolution=None,superseded_by=None))
    ledger.append(entry)
    return ledger


def submit(row,p,item):
    ledger=deepcopy(row.get('material_corrections') or [])
    for target in active(ledger):
        if target['slot']==item['slot']:
            # Appended only by the authorized ADD_EVIDENCE transaction.
            target['submissions'].append(dict(**source(item),preparation_revision=row['revision']+1,
                                              action='ADD_EVIDENCE'))
    return ledger


def require_review(row,items):
    by_slot={item['slot']:item for item in items}
    if any(not submitted(target,by_slot.get(target['slot']),row['owner_id']) for target in active(row.get('material_corrections'))):
        raise Conflict('each requested material slot requires a new owner evidence version before review')


def resolve(row,p,items,current_hash,reason):
    require_review(row,items)
    ledger=deepcopy(row.get('material_corrections') or [])
    by_slot={item['slot']:item for item in items}
    for target in active(ledger):
        target.update(status='RESOLVED',resolved_source=source(by_slot[target['slot']]),
                      resolution=dict(reviewer_id=p['id'],preparation_revision=row['revision']+1,
                                      snapshot_sha256=current_hash,reason=reason,action='REVIEW'))
    return ledger


def _view(c,p,row):
    ledger=deepcopy(row.get('material_corrections') or [])
    current=materials(c,row['id']);by_slot={item['slot']:item for item in current}
    snapshot=prep.snapshot(row,prep.latest(c,row['id']))
    items=[];requests=[]
    for request in ledger:
        projected=[]
        for target in request['targets']:
            item=by_slot.get(target['slot']);actual=source(item)
            resolution=target.get('resolution')
            source_same=bool(resolution and actual==target['resolved_source'] and item and digest(item['text'])==item['source_sha256'])
            review_current=bool(source_same and row['state'] in ('REVIEWED','LOCAL_CONFIRMED') and
                                resolution['snapshot_sha256']==row['review_sha256']==snapshot)
            status=target['status']
            if status=='ACTIVE':status='SUBMITTED_FOR_REVIEW' if submitted(target,item,row['owner_id']) else 'REQUESTED'
            elif status=='RESOLVED' and not review_current:status='STALE_RESOLUTION'
            output=dict(target)
            output.update(request_id=request['id'],reason=request['reason'],requested_by=request['requested_by'],
                          preparation_revision=request['preparation_revision'],status=status,
                          current_version=item['version'] if item else 0,current_source_sha256=item['source_sha256'] if item else None,
                          current_review_valid=review_current,
                          source_status='CURRENT' if review_current else 'HISTORICAL_REVIEW_CHANGED' if source_same else 'HISTORICAL_SOURCE_CHANGED' if resolution else 'NOT_REVIEWED')
            projected.append(output);items.append(output)
        requests.append({**request,'targets':projected})
    pending=[item for item in items if item['status'] in ('REQUESTED','SUBMITTED_FOR_REVIEW')]
    state='NOT_REQUESTED' if not ledger else 'CHANGES_REQUESTED' if any(item['status']=='REQUESTED' for item in pending) else 'SUBMITTED_FOR_REVIEW' if pending else 'RESOLVED'
    review_valid=row['state'] in ('REVIEWED','LOCAL_CONFIRMED') and row['review_sha256']==snapshot
    if state=='RESOLVED' and not review_valid and any(item['resolution'] for item in items):state='STALE_RESOLUTION'
    reviewer=p['role']=='park_specialist';reviewable=row['state'] in ('IN_PREPARATION','CHANGES_REQUESTED') and {i['slot'] for i in current}==set(prep.SLOTS) and not any(i['status']=='REQUESTED' for i in pending)
    return dict(scope=SCOPE,role=p['role'],preparation_id=str(row['id']),case_id=str(row['case_id']),run_id=str(row['run_id']),
                preparation_revision=row['revision'],preparation_state=row['state'],review_sha256=row['review_sha256'],
                current_review_valid=review_valid,
                correction_state=state,items=items,active_targets=pending,requests=requests,history=requests,
                history_limit=LIMIT,can_review=reviewer and reviewable and row['revision']<64,
                can_request_changes=reviewer and row['state'] in ('IN_PREPARATION','CHANGES_REQUESTED') and len(ledger)<LIMIT and row['revision']<64,
                qualification='NOT_EVALUATED',external_acceptance='NOT_SUBMITTED',offline_fulfillment='NO_EVIDENCE',case_goal_completed=False)


@bounded
def read(store,token,id):
    with store.connect() as c:
        c.execute("SET LOCAL lock_timeout='3s'")
        p=store.auth(c,token,lock=True)
        if p['role'] not in ('enterprise_operator','park_specialist'):raise Denied('owner or assigned material reviewer required')
        row=prep.scoped(store,c,p,id)
        if row['namespace']!='SYNTHETIC':raise Denied('synthetic material correction required')
        return _view(c,p,row)
