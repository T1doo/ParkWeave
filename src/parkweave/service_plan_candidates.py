"""Untrusted synthetic planner records; exact IDs are locators, never authority.

The provider is closed. A bounded local producer emits a proposal that must pass
independent deterministic checks before the original Case plan can consume it.
"""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import hashlib
from uuid import UUID,uuid4
from psycopg.types.json import Jsonb
from . import bounded_planning as bp,controlled_plans as cp
from . import preparation as prep
from .store import Conflict
from .intern_adapter import ModelBoundaryError
from .service_plan_planner import UNKNOWN_OUTCOMES,SAFE_OUTCOMES,valid_attempt_outcome

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


def _records(parent):return [h for h in parent.get('planning_previews') or [] if 'candidate' in h and h.get('profile') not in ('TRUSTED_SERVICE_SELECTION_V4','LOCAL_SYNTHETIC_DEMO')]


def _producer(record):
    producer=record.get('producer')
    if producer is None:
        if 'candidate_producer' in record['document'] or any(k in record for k in ('planner_attempt','proposal_raw','response_raw','budget_record')):raise ValueError('planner provenance missing')
        return None
    from .service_plan_planner import ORIGIN as planner_origin
    from .intern_adapter import MODEL,safe_id,validated_usage,strict_json
    attempt=record['planner_attempt'];budget=record['budget_record']
    attempt_sha=cp._hash(dict(id=record['id'],actor_id=record['actor_id'],request_key=record['request_key'],fingerprint=record['fingerprint'],validity=record['validity']))
    if (set(producer)!={'version','origin','model','returned_model','call_id','usage','mode','provider_enabled','executed','proposal_sha256','response_sha256','attempt_sha256','budget_sha256'} or
        type(producer['version']) is not int or producer['version']!=3 or producer['origin']!=planner_origin or producer['model']!=MODEL or
        type(producer['returned_model']) is not str or not producer['returned_model'].isascii() or producer['returned_model'].casefold()!=MODEL or
        producer['provider_enabled'] is not False or producer['executed'] is not False or producer['mode']!='OFFLINE_HTTP_FIXTURE' or
        type(attempt) is not dict or set(attempt)!={'version','state','outcome','producer_sha256'} or
        attempt['state']!='COMMITTED' or not valid_attempt_outcome(attempt['state'],attempt['outcome']) or type(attempt['version']) is not int or attempt['version']!=3 or producer['attempt_sha256']!=attempt_sha or
        cp._hash(producer)!=cp._hash(record['document'].get('candidate_producer')) or
        attempt['producer_sha256']!=cp._hash(producer) or producer['proposal_sha256']!=record['candidate_sha256'] or producer['budget_sha256']!=cp._hash(budget) or
        type(producer['response_sha256']) is not str or len(producer['response_sha256'])!=64 or any(v not in '0123456789abcdef' for v in producer['response_sha256']) or
        set(budget)!={'attempt','kind','outcome','usage','reserved_tokens'} or type(budget['attempt']) is not int or not 1<=budget['attempt']<=3 or
        type(budget['reserved_tokens']) is not int or not 1<=budget['reserved_tokens']<=8192 or
        budget['kind']!='OFFLINE_HTTP_FIXTURE' or budget['outcome']!='VALIDATED' or cp._hash(budget['usage'])!=cp._hash(producer['usage'])):raise ValueError('planner provenance invalid')
    from .planner_proposal import validate_proposal
    if cp._hash(validate_proposal(record['proposal_raw'],document(record['document'])))!=record['candidate_sha256']:raise ValueError('planner raw proposal proof invalid')
    response=record['response_raw']
    if type(response) is not str or len(response.encode())>65536 or hashlib.sha256(response.encode()).hexdigest()!=producer['response_sha256']:raise ValueError('planner raw response proof invalid')
    wire=strict_json(response);choices=wire['choices']
    if (type(wire) is not dict or set(wire)-{'id','model','choices','usage'} or wire['id']!=producer['call_id'] or wire['model']!=producer['returned_model'] or
        type(choices) is not list or len(choices)!=1 or type(choices[0]) is not dict or set(choices[0])!={'index','message','finish_reason'} or
        type(choices[0]['index']) is not int or choices[0]['index']!=0 or choices[0]['finish_reason']!='stop' or
        choices[0]['message']!={'role':'assistant','content':record['proposal_raw']} or cp._hash(wire.get('usage') if wire.get('usage') is not None else 'UNKNOWN')!=cp._hash(producer['usage'])):raise ValueError('planner raw response contract invalid')
    safe_id(producer['call_id'])
    if producer['usage']!='UNKNOWN':
        if type(producer['usage']) is not dict or set(producer['usage'])!={'prompt_tokens','completion_tokens','total_tokens'}:raise ValueError('planner usage invalid')
        validated_usage(producer['usage'])
        if producer['usage']['total_tokens']>budget['reserved_tokens']:raise ValueError('planner usage exceeds reservation')
    return producer


def _proof(parent,record):
    try:
        UUID(record['id'])
        raw=record['candidate'];request=bp.Capture.model_validate(record['candidate_request'])
        _window(record)
        producer=_producer(record)
        if (record['document']['preparation_id']!=str(parent['id']) or
            record['actor_id']!=parent['owner_id'] or
            cp._hash(raw)!=cp._hash(document(record['document'])) or
            record['candidate_sha256']!=cp._hash(raw) or
            request.expected_preparation_revision!=raw['binding']['preparation_revision'] or
            request.expected_source_sha256!=raw['binding']['source_sha256'] or
            record['fingerprint']!=_fingerprint(parent['id'],request,model=producer is not None)):raise ValueError()
    except (KeyError,TypeError,ValueError,AttributeError,ModelBoundaryError):raise Conflict('candidate original provenance proof invalid')


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
    producer=_producer(record)
    if producer is not None:basis.update(validator_version=3,producer_sha256=cp._hash(producer))
    old_graph=[dict(id=s['id'],depends_on=s['depends_on']) for s in raw['steps']]
    new_graph=[dict(id=s['id'],depends_on=s['depends_on']) for s in expected['steps']]
    return dict(**basis,scope=SCOPE,origin=ORIGIN,verification_sha256=cp._hash(basis),can_adopt=bool(state=='VERIFIED_STRUCTURE_ONLY' and full),can_adopt_partial=bool(state=='VERIFIED_STRUCTURE_ONLY' and partial),
                graph_comparison='UNCHANGED' if cp._hash(old_graph)==cp._hash(new_graph) else 'CHANGED',
                **({'producer':deepcopy(producer)} if producer else {}),
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
        attempts=[h for h in parent.get('planning_previews') or [] if 'planner_attempt' in h and h.get('profile')!='TRUSTED_SERVICE_SELECTION_V4']
        if key is not None:attempts=[h for h in attempts if h['actor_id']==p['id'] and h['request_key']==key]
        statuses=[_attempt_view(parent,h) for h in attempts]
        status='COMMITTED' if key is not None and result else statuses[0]['status'] if key is not None and statuses else 'NOT_OBSERVED' if key is not None else 'LIST'
        return dict(scope=SCOPE,preparation_id=str(id),case_id=str(parent['case_id']),run_id=str(parent['run_id']),actor_ref=cp._hash(dict(actor_id=p['id'])),
                    status=status,request_key=key,items=result,**({'attempts':statuses} if statuses else {}),
                    provider_enabled=False,read_only=True,automatically_replayed=False,execution_enabled=False,new_grants=False,case_goal_completed=False)


def _attempt_view(parent,record):
    try:
        UUID(record['id']);request=bp.Capture.model_validate(record['candidate_request']);attempt=record['planner_attempt']
        if (type(attempt) is not dict or set(attempt)!=({'version','state','outcome','producer_sha256'} if attempt.get('state')=='COMMITTED' else {'version','state','outcome'}) or
            type(attempt['version']) is not int or attempt['version']!=3 or not valid_attempt_outcome(attempt['state'],attempt['outcome']) or
            record['actor_id']!=parent['owner_id'] or record['document']['preparation_id']!=str(parent['id']) or
            request.expected_preparation_revision!=record['document']['preparation_revision'] or request.expected_source_sha256!=record['document']['source_sha256'] or
            record['fingerprint']!=_fingerprint(parent['id'],request,model=True) or _window(record) is None or
            ('candidate' in record)!=(attempt['state']=='COMMITTED')):raise ValueError()
        if attempt['state']=='COMMITTED':_proof(parent,record)
    except (KeyError,TypeError,ValueError,AttributeError,ModelBoundaryError):raise Conflict('planner original attempt proof invalid')
    return dict(attempt_id=record['id'],status='PENDING' if attempt['state']=='STARTED' else attempt['state'],outcome=attempt.get('outcome'),validity=deepcopy(record['validity']),
                automatically_replayed=False,read_only=True,can_adopt=False,provider_enabled=False,execution_enabled=False,new_grants=False)


def _fingerprint(id,data,*,model=False):return cp._hash(dict(preparation_id=str(id),kind=SCOPE,**data.model_dump(),**({'producer_version':3} if model else {})))


def _prior(c,p,parent,key,fp):
    rows=c.execute('SELECT * FROM preparations WHERE planning_previews @> %s',(Jsonb([dict(actor_id=p['id'],request_key=key)]),)).fetchall()
    matches=[(row,h) for row in rows for h in row['planning_previews'] or [] if h['actor_id']==p['id'] and h['request_key']==key]
    if len(matches)>1:raise Conflict('planner original key ambiguous')
    if matches:
        row,h=matches[0]
        matches_fp=h['fingerprint']==fp
        if not matches_fp and 'candidate' in h and 'planner_attempt' not in h:
            try:saved=bp.Capture.model_validate(h['candidate_request'])
            except (KeyError,TypeError,ValueError):raise Conflict('candidate original key proof invalid')
            matches_fp=fp==_fingerprint(id=parent['id'],data=saved,model=True) and h['fingerprint']==_fingerprint(parent['id'],saved)
        if row['id']!=parent['id'] or not matches_fp or 'candidate' not in h and 'planner_attempt' not in h:raise Conflict('candidate request key scope changed')
        # The separately fetched JSON is not the locked parent's in-memory slot.
        # Mutations must update the exact list serialized by the final UPDATE.
        owned=[v for v in parent.get('planning_previews') or [] if v['id']==h['id'] and v['actor_id']==p['id'] and v['request_key']==key]
        if len(owned)!=1 or cp._hash(owned[0])!=cp._hash(h):raise Conflict('planner locked original key changed')
        return owned[0]


def _failure(store,token,id,key,fp,attempt_id,code):
    # Outcome bookkeeping is permitted only while original write authority and
    # Case guard still hold. Otherwise original STARTED stays unresolved, never
    # authorizes a resend, and a later authorized GET still finds the original key.
    from .store import Denied
    try:
        with store.connect() as c:
            p,parent=bp._context(store,c,token,id,True);prep.key_lock(c,p,'planning-preview:'+key)
            h=_prior(c,p,parent,key,fp)
            if h is None or h['id']!=attempt_id or h['planner_attempt']['state']!='STARTED':return
            _attempt_view(parent,h)
            # Unknown/new exception codes cannot certify a safe refusal.
            if code not in UNKNOWN_OUTCOMES and code not in SAFE_OUTCOMES:code='PLANNER_OUTCOME_UNKNOWN'
            unknown=code in UNKNOWN_OUTCOMES
            h['planner_attempt'].update(state='OUTCOME_UNKNOWN' if unknown else 'FAILED_SAFE',outcome=code)
            c.execute('UPDATE preparations SET planning_previews=%s WHERE id=%s',(Jsonb(parent['planning_previews']),id))
    except (Denied,Conflict):return


def _generate_proposal(store,token,id,key,data,planner):
    from .service_plan_planner import OfflineProposalPlanner
    if type(planner) is not OfflineProposalPlanner:raise Conflict('explicit offline-only proposal planner required')
    planner.require();fp=_fingerprint(id,data,model=True)
    with store.connect() as c:
        p,parent=bp._context(store,c,token,id,True);prep.key_lock(c,p,'planning-preview:'+key)
        prior=_prior(c,p,parent,key,fp)
        if prior is not None:
            if 'candidate' in prior:return verify(parent,prior,bp._proposal(store,c,p,parent),now=clock(c))
            return _attempt_view(parent,prior)
        current=bp._proposal(store,c,p,parent)
        if parent['revision']!=data.expected_preparation_revision or current['source_sha256']!=data.expected_source_sha256:raise Conflict('candidate source changed')
        history=deepcopy(parent.get('planning_previews') or [])
        if len(history)>=bp.LIMIT:raise Conflict('bounded planning metadata history full')
        if any(h.get('planner_attempt',{}).get('state')=='STARTED' for h in history):raise Conflict('original planner attempt requires GET recovery first')
        bp._context(store,c,token,id,True);now=clock(c).astimezone(timezone.utc)
        window=dict(version=2,created_at=now.isoformat(),expires_at=(now+timedelta(seconds=VALIDITY_SECONDS)).isoformat(),seconds=VALIDITY_SECONDS)
        saved=deepcopy(current);saved['candidate_validity']=deepcopy(window)
        record=dict(id=str(uuid4()),revision=len(history)+1,actor_id=p['id'],request_key=key,fingerprint=fp,document=saved,
                    candidate_request=data.model_dump(),validity=window,planner_attempt=dict(version=3,state='STARTED',outcome=None))
        history.append(record);c.execute('UPDATE preparations SET planning_previews=%s WHERE id=%s',(Jsonb(history),id))
    # No connection, business lock or advisory lock spans provider waiting.
    def authority():
        with store.connect() as c:
            p,parent=bp._context(store,c,token,id,True);prep.key_lock(c,p,'planning-preview:'+key)
            h=_prior(c,p,parent,key,fp)
            if h is None or h['id']!=record['id'] or h['planner_attempt']['state']!='STARTED':raise Conflict('planner original attempt changed before dispatch')
            _attempt_view(parent,h);actual=bp._proposal(store,c,p,parent)
            if actual['source_sha256']!=data.expected_source_sha256 or parent['revision']!=data.expected_preparation_revision:raise Conflict('planner source changed before dispatch')
            bp._context(store,c,token,id,True);now=clock(c)
            if not _time(h['validity']['created_at'])<=now<_time(h['validity']['expires_at']):raise Conflict('planner original attempt expired before dispatch')
    try:
        result=planner.propose(document(current),before_dispatch=authority)
        with store.connect() as c:
            p,parent=bp._context(store,c,token,id,True);prep.key_lock(c,p,'planning-preview:'+key)
            original=_prior(c,p,parent,key,fp)
            if original is None or original['id']!=record['id'] or original['planner_attempt']['state']!='STARTED' or cp._hash(original['validity'])!=cp._hash(record['validity']):raise Conflict('planner original attempt changed')
            _attempt_view(parent,original)
            latest=bp._proposal(store,c,p,parent)
            if parent['revision']!=data.expected_preparation_revision or latest['source_sha256']!=data.expected_source_sha256:raise Conflict('planner source changed while waiting')
            from .planner_proposal import validate_proposal
            candidate=validate_proposal(result['proposal_raw'],document(latest))
            if cp._hash(candidate)!=cp._hash(result['proposal']):raise Conflict('planner parsed proposal changed')
            original.update(candidate=candidate,candidate_sha256=cp._hash(candidate),producer=deepcopy(result['producer']),proposal_raw=result['proposal_raw'],response_raw=result['response_raw'],budget_record=deepcopy(result['budget_record']))
            original['producer']['attempt_sha256']=cp._hash(dict(id=original['id'],actor_id=original['actor_id'],request_key=original['request_key'],fingerprint=original['fingerprint'],validity=original['validity']))
            original['producer']['budget_sha256']=cp._hash(original['budget_record'])
            original['document']['candidate_producer']=deepcopy(original['producer'])
            original['planner_attempt'].update(state='COMMITTED',outcome='VALIDATED',producer_sha256=cp._hash(original['producer']))
            bp._context(store,c,token,id,True);now=clock(c)
            view=verify(parent,original,latest,now=now)
            if view['state'] in ('EXPIRED','CLOCK_UNCERTAIN','STALE','REJECTED'):raise Conflict('planner current source or validity changed')
            c.execute('UPDATE preparations SET planning_previews=%s WHERE id=%s',(Jsonb(parent['planning_previews']),id))
            return view
    except ModelBoundaryError as e:
        _failure(store,token,id,key,fp,record['id'],e.code)
        raise Conflict('offline planner '+e.code+'; GET original key only') from None
    except Exception as e:
        from .store import Denied
        code='AUTHORIZATION_CHANGED' if isinstance(e,Denied) else 'SOURCE_OR_ATTEMPT_CHANGED' if isinstance(e,Conflict) else 'PLANNER_OUTCOME_UNKNOWN'
        _failure(store,token,id,key,fp,record['id'],code)
        raise


def generate(store,token,id,key,data,*,planner=None):
    if planner is not None:return _generate_proposal(store,token,id,key,data,planner)
    with store.connect() as c:
        p,parent=bp._context(store,c,token,id,True)
        prep.key_lock(c,p,'planning-preview:'+key)
        fp=_fingerprint(id,data)
        rows=c.execute('SELECT * FROM preparations WHERE planning_previews @> %s',(Jsonb([dict(actor_id=p['id'],request_key=key)]),)).fetchall()
        for row in rows:
            for record in row['planning_previews'] or []:
                if record['actor_id']==p['id'] and record['request_key']==key:
                    expected=_fingerprint(id,data,model='planner_attempt' in record)
                    if row['id']!=parent['id'] or record['fingerprint']!=expected or 'candidate' not in record and 'planner_attempt' not in record:raise Conflict('candidate request key scope changed')
                    if 'candidate' not in record:return _attempt_view(parent,record)
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
    if v['validator_version'] in (2,3):proof.update(accepted_at=now.astimezone(timezone.utc).isoformat());proof['verification_basis']['validity']=deepcopy(v['validity'])
    if v['validator_version']==3:proof['verification_basis']['producer_sha256']=v['producer_sha256'];proof['producer']=deepcopy(v['producer'])
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
        if type(version) is not int or version not in (1,2,3):raise ValueError('unknown candidate proof version')
        accepted=_time(proof['accepted_at']) if version in (2,3) else None
        if version in (2,3) and plan['events'][0].get('candidate_consumption_sha256')!=cp._hash(proof):raise ValueError('candidate acceptance event changed')
        expected=consume(parent,plan['adoption_preview'],request,now=accepted,historical=True)
    except (KeyError,TypeError,ValueError):raise Conflict('candidate acceptance time proof invalid')
    if cp._hash(proof)!=cp._hash(expected):raise Conflict('candidate consumption proof invalid')
