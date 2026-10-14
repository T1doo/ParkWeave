"""Untrusted synthetic planner records; exact IDs are locators, never authority.

The provider is closed. A bounded local producer emits a proposal that must pass
independent deterministic checks before the original Case plan can consume it.
"""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from uuid import UUID,uuid4
from psycopg.types.json import Jsonb
from . import bounded_planning as bp,controlled_plans as cp
from . import preparation as prep
from .store import Conflict

SCOPE='SYNTHETIC_SERVICE_PLAN_CANDIDATE'
ORIGIN='SYNTHETIC_UNTRUSTED_CANDIDATE'
PROVIDER_ENABLED=False
VALIDITY_SECONDS=900


def clock(c):return c.execute('SELECT clock_timestamp() AS now').fetchone()['now']


def _time(value):
    if not isinstance(value,str):raise ValueError('candidate clock format required')
    result=datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset()!=timedelta(0) or result.isoformat()!=value:raise ValueError('canonical UTC candidate clock required')
    return result


def _window(record):
    window=record.get('validity')
    if window is None:
        if 'candidate_validity' in record['document']:raise ValueError('candidate validity missing')
        return None
    if (set(window)!= {'version','created_at','expires_at','seconds'} or type(window['version']) is not int or window['version']!=2 or
        type(window['seconds']) is not int or window['seconds']!=VALIDITY_SECONDS or
        cp._hash(window)!=cp._hash(record['document'].get('candidate_validity'))):raise ValueError('candidate validity proof invalid')
    start=_time(window['created_at']);end=_time(window['expires_at'])
    if end-start!=timedelta(seconds=VALIDITY_SECONDS):raise ValueError('candidate validity interval invalid')
    return window


def document(current):
    return dict(schema_version=1,origin=ORIGIN,provider_enabled=False,
                binding={k:deepcopy(current[k]) for k in ('preparation_id','case_id','run_id','preparation_revision','request_revision','source_sha256','catalog_sha256','registry_sha256')},
                required_goals=deepcopy(current['required_goals']),goal_coverage=deepcopy(current['goal_coverage']),
                steps=deepcopy(current['steps']),constraints=deepcopy(current.get('constraint_evaluation')),
                global_requirements=deepcopy(current['global_requirements']))


def _records(parent):return [h for h in parent.get('planning_previews') or [] if 'candidate' in h]


def _proof(parent,record):
    try:
        UUID(record['id'])
        raw=record['candidate'];request=bp.Capture.model_validate(record['candidate_request'])
        _window(record)
        if (record['document']['preparation_id']!=str(parent['id']) or
            record['actor_id']!=parent['owner_id'] or
            cp._hash(raw)!=cp._hash(document(record['document'])) or
            record['candidate_sha256']!=cp._hash(raw) or
            request.expected_preparation_revision!=raw['binding']['preparation_revision'] or
            request.expected_source_sha256!=raw['binding']['source_sha256'] or
            record['fingerprint']!=cp._hash(dict(preparation_id=str(parent['id']),kind=SCOPE,**request.model_dump()))):raise ValueError()
    except (KeyError,TypeError,ValueError,AttributeError):raise Conflict('candidate original provenance proof invalid')


def find(parent,id):
    records=[h for h in _records(parent) if h['id']==str(id)]
    if len(records)!=1:raise Conflict('candidate unavailable in this Case')
    _proof(parent,records[0]);return records[0]


def verify(parent,record,current,*,now=None,historical=False):
    _proof(parent,record)
    # The stored proposal (including claims) is not the compiler's authority.
    # Compare the full graph/action/goal/constraint contract and current binding.
    raw=record['candidate'];expected=document(current)
    stale=cp._hash(raw['binding'])!=cp._hash(expected['binding'])
    valid=set(raw)==set(expected) and all(cp._hash(raw[k])==cp._hash(expected[k]) for k in expected if k!='binding')
    unknown=current['state']=='UNKNOWN' or any(not v['known'] for v in current['dependency_collections'].values())
    full=current['state']=='COVERED_PREVIEW_ONLY' and not unknown
    partial=current['state']=='PARTIAL' and current['partial_offer']['can_adopt'] and not unknown
    state='STALE' if stale else 'REJECTED' if not valid else 'UNKNOWN' if unknown else 'VERIFIED_STRUCTURE_ONLY' if full or partial else 'BLOCKED'
    window=_window(record)
    if window is None:
        if not historical:state='LEGACY_REVALIDATION_REQUIRED'
    else:
        if now is None:raise Conflict('current server candidate clock required')
        if now<_time(window['created_at']):state='CLOCK_UNCERTAIN'
        elif now>=_time(window['expires_at']):state='EXPIRED'
    basis=dict(validator_version=1,validated_contract_sha256=cp._hash({k:expected[k] for k in expected if k!='binding'}),candidate_id=record['id'],candidate_sha256=record['candidate_sha256'],current_source_sha256=current['source_sha256'],state=state,
               preparation_id=str(parent['id']),case_id=str(parent['case_id']),run_id=str(parent['run_id']),
               preparation_revision=current['preparation_revision'],request_revision=current['request_revision'],
               catalog_sha256=current['catalog_sha256'],registry_sha256=current['registry_sha256'])
    if window is not None:basis.update(validator_version=2,validity=deepcopy(window))
    old_graph=[dict(id=s['id'],depends_on=s['depends_on']) for s in raw['steps']]
    new_graph=[dict(id=s['id'],depends_on=s['depends_on']) for s in expected['steps']]
    return dict(**basis,scope=SCOPE,origin=ORIGIN,verification_sha256=cp._hash(basis),can_adopt=bool(state=='VERIFIED_STRUCTURE_ONLY' and full),can_adopt_partial=bool(state=='VERIFIED_STRUCTURE_ONLY' and partial),
                graph_comparison='UNCHANGED' if cp._hash(old_graph)==cp._hash(new_graph) else 'CHANGED',
                required_goals=current['required_goals'],goal_coverage=current['goal_coverage'],steps=current['steps'],constraint_evaluation=current.get('constraint_evaluation'),
                source_unknowns=current['source_unknowns'],provider_enabled=False,read_only=True,execution_enabled=False,new_grants=False,case_goal_completed=False)


def read(store,token,id,candidate_id=None,key=None):
    with store.connect() as c:
        p,parent=bp._context(store,c,token,id)
        current=bp._proposal(store,c,p,parent)
        now=clock(c)
        if candidate_id is not None:return verify(parent,find(parent,candidate_id),current,now=now)
        records=_records(parent)
        if key is not None:records=[h for h in records if h['actor_id']==p['id'] and h['request_key']==key]
        result=[verify(parent,h,current,now=now) for h in records]
        return dict(scope=SCOPE,preparation_id=str(id),case_id=str(parent['case_id']),run_id=str(parent['run_id']),actor_ref=cp._hash(dict(actor_id=p['id'])),
                    status='COMMITTED' if key is not None and result else 'NOT_OBSERVED' if key is not None else 'LIST',request_key=key,items=result,
                    provider_enabled=False,read_only=True,automatically_replayed=False,execution_enabled=False,new_grants=False,case_goal_completed=False)


def generate(store,token,id,key,data):
    with store.connect() as c:
        p,parent=bp._context(store,c,token,id,True)
        prep.key_lock(c,p,'planning-preview:'+key)
        fp=cp._hash(dict(preparation_id=str(id),kind=SCOPE,**data.model_dump()))
        rows=c.execute('SELECT * FROM preparations WHERE planning_previews @> %s',(Jsonb([dict(actor_id=p['id'],request_key=key)]),)).fetchall()
        for row in rows:
            for record in row['planning_previews'] or []:
                if record['actor_id']==p['id'] and record['request_key']==key:
                    if row['id']!=parent['id'] or record['fingerprint']!=fp or 'candidate' not in record:raise Conflict('candidate request key scope changed')
                    current=bp._proposal(store,c,p,parent)
                    return verify(parent,record,current,now=clock(c))
        current=bp._proposal(store,c,p,parent)
        if parent['revision']!=data.expected_preparation_revision or current['source_sha256']!=data.expected_source_sha256:raise Conflict('candidate source changed')
        history=deepcopy(parent.get('planning_previews') or [])
        if len(history)>=bp.LIMIT:raise Conflict('bounded planning metadata history full')
        raw=document(current)
        # Fixed server timestamps are provenance, never a client-provided TTL.
        bp._context(store,c,token,id,True)
        now=clock(c).astimezone(timezone.utc)
        window=dict(version=2,created_at=now.isoformat(),expires_at=(now+timedelta(seconds=VALIDITY_SECONDS)).isoformat(),seconds=VALIDITY_SECONDS)
        current=deepcopy(current);current['candidate_validity']=deepcopy(window)
        record=dict(id=str(uuid4()),revision=len(history)+1,actor_id=p['id'],request_key=key,fingerprint=fp,document=current,
                    candidate=raw,candidate_sha256=cp._hash(raw),candidate_request=data.model_dump(),validity=window)
        # Recheck original authority after source locks; no provider/action runs.
        bp._context(store,c,token,id,True)
        history.append(record);c.execute('UPDATE preparations SET planning_previews=%s WHERE id=%s',(Jsonb(history),id))
        return verify(parent,record,current,now=clock(c))


def consume(parent,current,data,*,now=None,historical=False):
    record=find(parent,data.candidate_id);v=verify(parent,record,current,now=now,historical=historical)
    if (v['state']!='VERIFIED_STRUCTURE_ONLY' or
        v['candidate_sha256']!=data.expected_candidate_sha256 or v['verification_sha256']!=data.expected_verification_sha256 or
        not (v['can_adopt_partial'] if data.partial_adoption else v['can_adopt'])):raise Conflict('current candidate deterministic verification required')
    proof=dict(candidate_id=v['candidate_id'],candidate_sha256=v['candidate_sha256'],verification_sha256=v['verification_sha256'],
                origin=ORIGIN,verification_basis={k:v[k] for k in ('validator_version','validated_contract_sha256','candidate_id','candidate_sha256','current_source_sha256','state','preparation_id','case_id','run_id','preparation_revision','request_revision','catalog_sha256','registry_sha256')})
    if v['validator_version']==2:proof.update(accepted_at=now.astimezone(timezone.utc).isoformat());proof['verification_basis']['validity']=deepcopy(v['validity'])
    return proof


def consumption_proof(parent,plan,request):
    proof=plan.get('candidate_consumption')
    if request.candidate_id is None:
        if proof is not None:raise Conflict('candidate consumption request missing')
        return
    if (request.expected_preparation_revision!=plan['adoption_preparation_revision'] or
        request.expected_request_revision!=plan['binding']['request_intent']['revision'] or
        request.expected_source_sha256!=plan['adoption_preview']['source_sha256'] or
        request.required_goals!=plan['required_goals']):raise Conflict('candidate original adoption request invalid')
    selected=[s for s in plan['adoption_preview']['steps'] if not request.partial_adoption or s['id'] in plan['adoption_preview']['partial_offer']['step_ids']]
    actual=[{k:s[k] for k in ('adapter_id','adapter','adapter_revision','depends_on','contract')} for s in plan['steps']]
    expected_steps=[dict(adapter_id=s['id'],adapter=s['adapter'],adapter_revision=s['revision'],depends_on=s['depends_on'],contract=s) for s in selected]
    if cp._hash(actual)!=cp._hash(expected_steps):raise Conflict('candidate adopted graph contract changed')
    try:
        version=proof['verification_basis']['validator_version']
        accepted=_time(proof['accepted_at']) if version==2 else None
        if version==2 and plan['events'][0].get('candidate_consumption_sha256')!=cp._hash(proof):raise ValueError('candidate acceptance event changed')
        expected=consume(parent,plan['adoption_preview'],request,now=accepted,historical=True)
    except (KeyError,TypeError,ValueError):raise Conflict('candidate acceptance time proof invalid')
    if cp._hash(proof)!=cp._hash(expected):raise Conflict('candidate consumption proof invalid')
