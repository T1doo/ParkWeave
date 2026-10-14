"""Version four compact selections, rebuilt from authorized frozen capabilities.

This profile is deliberately separate from original candidate versions 1–3.
A model returns references only; neither saved claims nor IDs confer authority.
"""
from copy import deepcopy
from datetime import timedelta, timezone
import hashlib
import json
from itertools import combinations
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field
from psycopg.types.json import Jsonb
from . import bounded_planning as bp, controlled_plans as cp, preparation as prep
from . import service_plan_candidates as old, service_selection as ss
from .store import Conflict, Denied
from .intern_adapter import ModelBoundaryError, MODEL, strict_json, safe_id, validated_usage
from .service_plan_planner import SAFE_OUTCOMES as LEGACY_SAFE_OUTCOMES, UNKNOWN_OUTCOMES, valid_attempt_outcome as legacy_attempt_outcome

SAFE_OUTCOMES=LEGACY_SAFE_OUTCOMES|{'INVALID_SERVICE_SELECTION'}


def valid_attempt_outcome(state,outcome):
    return legacy_attempt_outcome(state,outcome) or state=='FAILED_SAFE' and outcome=='INVALID_SERVICE_SELECTION'

SCOPE='SYNTHETIC_SERVICE_SELECTION_CANDIDATE'
PROFILE='TRUSTED_SERVICE_SELECTION_V4'
ORIGIN=old.ORIGIN
clock=old.clock
KEYS=('preparation_id','case_id','run_id','preparation_revision','request_revision','source_sha256','catalog_sha256','registry_sha256','capability_catalog_sha256')

class Capture(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    expected_preparation_revision:int=Field(ge=1,le=64)
    expected_source_sha256:str=Field(pattern='^[0-9a-f]{64}$')
    expected_capability_catalog_sha256:str=Field(pattern='^[0-9a-f]{64}$')


def binding(value):return {k:deepcopy(value[k]) for k in KEYS}


def document(value):
    result=old.document(value);result['binding']=binding(value)
    result.update(profile=PROFILE,selection=deepcopy(value.get('selection')))
    return result


def _request(parent,snapshot,base):
    constraints=deepcopy((parent.get('request_intent') or {}).get('planning_constraints') or dict(excluded_roles=[],additional_requirements=[]))
    constraints['additional_requirements']=sorted(set(constraints['additional_requirements'])|set(base['global_requirements']))
    return dict(park_id=parent['park_id'],required_goals=deepcopy(base['required_goals']),planning_constraints=constraints,mapping_states=deepcopy(snapshot['mapping_states']))


def _apply(base,snapshot,request,selection,*,now):
    value=deepcopy(base)
    if selection is None:return value
    rebuilt=ss.rebuild_selection(selection,snapshot['releases'],snapshot['instances'],request,binding(base),now=now)
    # Preserve original dependency issues, lifecycle and correction facts for each
    # registered node. Trusted selected source/mapping metadata is added, never
    # used to erase business prerequisites.
    original={s['id']:s for s in base['steps']}
    steps=[]
    for step in rebuilt['steps']:
        merged=deepcopy(original.get(step['id'],{}));merged.update(deepcopy(step));steps.append(merged)
    value.update(selection=deepcopy(selection),steps=steps,selection_rebuild=rebuilt)
    return value


def current(store,c,p,parent,catalog,selection=None):
    base=bp._proposal(store,c,p,parent);snapshot=catalog.snapshot(c,parent)
    base['legacy_source_sha256']=base['source_sha256']
    base['capability_catalog_sha256']=cp._hash(cp._normal(snapshot))
    base['source_sha256']=cp._hash(dict(legacy_source_sha256=base['legacy_source_sha256'],capability_catalog_sha256=base['capability_catalog_sha256']))
    request=_request(parent,snapshot,base);now=clock(c)
    if request['required_goals'] and snapshot['releases']:
        oracle=ss.enumerate_solutions(snapshot['releases'],snapshot['instances'],request,now=now)
    else:oracle=dict(state='UNKNOWN',minimal_solutions=[],unknowns=['CURRENT_SERVICE_CAPABILITIES_REQUIRED'],unsupported_goals=deepcopy(request['required_goals']))
    if snapshot['unknowns']:
        oracle['state']='UNKNOWN';oracle['unknowns']=sorted(set(oracle['unknowns'])|set(snapshot['unknowns']))
    base.update(profile=PROFILE,catalog_snapshot=deepcopy(snapshot),selection_request=request,selection_oracle=oracle,selection=None)
    base['source_unknowns']=sorted(set(base['source_unknowns'])|set(oracle['unknowns']))
    if oracle['state'] not in ('UNIQUE','MULTIPLE'):base['state']='UNKNOWN' if oracle['state']=='UNKNOWN' else 'SELECTION_BLOCKED'
    if selection is not None:
        if oracle['state'] not in ('UNIQUE','MULTIPLE'):raise Conflict('current service selection is not satisfiable')
        base=_apply(base,snapshot,request,selection,now=now)
    base['selection_context']=dict(binding=binding(base),required_goals=deepcopy(base['required_goals']),planning_constraints=deepcopy(request['planning_constraints']),available_services=[dict(ref=ss.selection_ref(r,i),service_id=r['service_id'],supported_goals=deepcopy(r['supported_goals'])) for i in snapshot['instances'] for r in snapshot['releases'] if r['release_id']==i['release_id']])
    return base


def _fingerprint(id,data):return cp._hash(dict(preparation_id=str(id),kind=SCOPE,producer_version=4,**data.model_dump()))


def _records(parent):return [h for h in parent.get('planning_previews') or [] if h.get('profile')==PROFILE]


def _producer(record):
    from .service_selection_planner import ORIGIN as producer_origin
    p=record['producer'];budget=record['budget_record'];attempt=record['planner_attempt']
    expected={'version','origin','model','returned_model','call_id','usage','mode','provider_enabled','executed','selection_sha256','response_sha256','attempt_sha256','budget_sha256'}
    if (type(p) is not dict or set(p)!=expected or type(p['version']) is not int or p['version']!=4 or p['origin']!=producer_origin or p['model']!=MODEL or
        type(p['returned_model']) is not str or not p['returned_model'].isascii() or p['returned_model'].casefold()!=MODEL or p['mode']!='OFFLINE_HTTP_FIXTURE' or p['provider_enabled'] is not False or p['executed'] is not False or
        p['selection_sha256']!=cp._hash(record['selection']) or p['attempt_sha256']!=cp._hash({k:record[k] for k in ('id','actor_id','request_key','fingerprint','validity')}) or
        p['budget_sha256']!=cp._hash(budget) or set(attempt)!={'version','state','outcome','producer_sha256'} or attempt!={'version':4,'state':'COMMITTED','outcome':'VALIDATED','producer_sha256':cp._hash(p)} or
        cp._hash(p)!=cp._hash(record['document'].get('candidate_producer')) or
        type(budget) is not dict or set(budget)!={'attempt','kind','outcome','usage','reserved_tokens'} or type(budget['attempt']) is not int or not 1<=budget['attempt']<=3 or type(budget['reserved_tokens']) is not int or not 1<=budget['reserved_tokens']<=8192 or budget['kind']!='OFFLINE_HTTP_FIXTURE' or budget['outcome']!='VALIDATED' or cp._hash(budget['usage'])!=cp._hash(p['usage'])):raise ValueError('selection producer proof invalid')
    raw=record['response_raw'];parsed=ss.parse_selection(record['selection_raw'],binding(record['document']))
    if parsed!=record['selection'] or type(raw) is not str or len(raw.encode())>65536 or hashlib.sha256(raw.encode()).hexdigest()!=p['response_sha256']:raise ValueError('selection wire proof invalid')
    wire=strict_json(raw)
    if type(wire) is not dict or set(wire)-{'id','model','choices','usage'} or wire.get('id')!=p['call_id'] or wire.get('model')!=p['returned_model'] or wire.get('choices')!=[dict(index=0,message=dict(role='assistant',content=record['selection_raw']),finish_reason='stop')] or cp._hash(wire.get('usage') if wire.get('usage') is not None else 'UNKNOWN')!=cp._hash(p['usage']):raise ValueError('selection response proof invalid')
    safe_id(p['call_id'])
    if p['usage']!='UNKNOWN':
        if type(p['usage']) is not dict or set(p['usage'])!={'prompt_tokens','completion_tokens','total_tokens'}:raise ValueError('selection usage invalid')
        validated_usage(p['usage'])
        if p['usage']['total_tokens']>budget['reserved_tokens']:raise ValueError('selection reservation exceeded')
    return p


def _attempt(parent,record):
    try:
        UUID(record['id']);data=Capture.model_validate(record['candidate_request']);a=record['planner_attempt'];window=old._window(record)
        if (record.get('profile')!=PROFILE or record['document'].get('profile')!=PROFILE or record['actor_id']!=parent['owner_id'] or record['document']['preparation_id']!=str(parent['id']) or record['fingerprint']!=_fingerprint(parent['id'],data) or window is None or
            data.expected_preparation_revision!=record['document']['preparation_revision'] or data.expected_source_sha256!=record['document']['source_sha256'] or data.expected_capability_catalog_sha256!=record['document']['capability_catalog_sha256'] or
            type(a) is not dict or set(a)!=({'version','state','outcome','producer_sha256'} if a.get('state')=='COMMITTED' else {'version','state','outcome'}) or type(a['version']) is not int or a['version']!=4 or not valid_attempt_outcome(a['state'],a['outcome']) or ('candidate' in record)!=(a['state']=='COMMITTED')):raise ValueError()
        if a['state']=='COMMITTED':_proof(parent,record)
    except (KeyError,TypeError,ValueError,AttributeError,ModelBoundaryError):raise Conflict('selection original attempt proof invalid') from None
    return dict(attempt_id=record['id'],status='PENDING' if a['state']=='STARTED' else a['state'],outcome=a['outcome'],validity=deepcopy(window),automatically_replayed=False,read_only=True,can_adopt=False,provider_enabled=False,execution_enabled=False,new_grants=False)


def _frozen_oracle(snapshot,request):
    goals,constraints,states=ss._request(request)
    if not 1<=len(snapshot['releases'])<=ss.MAX_RELEASES or len(snapshot['instances'])>ss.MAX_RELEASES:raise ValueError()
    pairs=sorted([(r,i) for r in snapshot['releases'] for i in snapshot['instances'] if r['release_id']==i['release_id'] and i['park_id']==request['park_id']],key=lambda pair:ss._identity(ss.selection_ref(*pair)))
    supported=set().union(*(set(r['supported_goals']) for r in snapshot['releases']))
    unsupported=[g for g in goals if g not in supported];solutions=[];unknown_sets=[];unknowns=set();examined=0
    for size in range(1,len(pairs)+1):
        for indices in combinations(range(len(pairs)),size):
            examined+=1;group=[pairs[i] for i in indices]
            if not set(goals)<=set().union(*(set(r['supported_goals']) for r,i in group)):continue
            state,missing=ss._set_state(group,constraints,states)
            if state=='TRUE' and not any(set(prior)<=set(indices) for prior in solutions):solutions.append(indices)
            elif state=='UNKNOWN' and not any(set(prior)<=set(indices) for prior in solutions+unknown_sets):unknown_sets.append(indices);unknowns.update(missing)
    state='UNSUPPORTED' if unsupported else 'UNKNOWN' if unknown_sets else 'UNIQUE' if len(solutions)==1 else 'MULTIPLE' if solutions else 'UNSAT'
    graphs=set()
    for indices in solutions:
        nodes={};maps={'roles':{},'resources':{},'fields':{}}
        for index in indices:
            r,i=pairs[index];nodes.update({s['id']:s for s in r['steps']})
            for group in maps:maps[group].update(i[group])
        graphs.add(json.dumps(dict(nodes=nodes,mappings=maps),sort_keys=True,ensure_ascii=False,separators=(',',':')))
    return dict(state=state,selection_variant_count=len(solutions),distinct_execution_graphs=len(graphs),required_goals=deepcopy(goals),unsupported_goals=unsupported,minimal_solutions=[[ss.selection_ref(*pairs[i]) for i in ids] for ids in solutions],unknown_solutions=[[ss.selection_ref(*pairs[i]) for i in ids] for ids in unknown_sets],unknowns=sorted(unknowns),examined_subsets=examined,execution_enabled=False,new_grants=False)


def _proof(parent,record):
    from .service_capability_contract import validate_release_integrity,validate_instance_integrity
    try:
        UUID(record['id']);data=Capture.model_validate(record['candidate_request']);doc=record['document'];old._window(record)
        if (record.get('profile')!=PROFILE or doc.get('profile')!=PROFILE or record['actor_id']!=parent['owner_id'] or doc['preparation_id']!=str(parent['id']) or record['fingerprint']!=_fingerprint(parent['id'],data) or data.expected_preparation_revision!=doc['preparation_revision'] or data.expected_source_sha256!=doc['source_sha256'] or data.expected_capability_catalog_sha256!=doc['capability_catalog_sha256'] or record['candidate_sha256']!=cp._hash(record['candidate']) or record['candidate']!=document(doc) or doc['selection']!=record['selection']):raise ValueError()
        _producer(record)
        snapshot=doc['catalog_snapshot'];frozen=record['frozen_registry'];at=old._time(record['validity']['created_at'])
        if set(frozen)!={'steps','actions'} or cp._hash(frozen)!=doc['registry_sha256'] or cp._hash(cp._normal(snapshot))!=doc['capability_catalog_sha256']:raise ValueError()
        for release in snapshot['releases']:validate_release_integrity(release,frozen['steps'],frozen['actions'],accepted_at=at)
        releases={r['release_id']:r for r in snapshot['releases']}
        for instance in snapshot['instances']:validate_instance_integrity(instance,releases[instance['release_id']],frozen['steps'],frozen['actions'],accepted_at=at)
        # Frozen reconstruction uses the authenticated adapter/action snapshot,
        # never a current registry or current availability/validity clock.
        selected=sorted(ss.parse_selection(record['selection_raw'],binding(doc))['selections'],key=ss._identity);nodes={};maps={};selected_pairs=[]
        goals,constraints,states=ss._request(doc['selection_request'])
        if goals!=doc['required_goals'] or snapshot['unknowns'] or doc['source_sha256']!=cp._hash(dict(legacy_source_sha256=doc['legacy_source_sha256'],capability_catalog_sha256=doc['capability_catalog_sha256'])):raise ValueError()
        for ref in selected:
            pairs=[(r,i) for r in snapshot['releases'] for i in snapshot['instances'] if r['release_id']==i['release_id'] and ss.selection_ref(r,i)==ref]
            if len(pairs)!=1:raise ValueError()
            r,i=pairs[0];selected_pairs.append((r,i))
            for s in r['steps']:
                if s['id'] in nodes and nodes[s['id']]!=s:raise ValueError()
                nodes[s['id']]=s
                maps.setdefault(s['id'],[]).append((ref,dict(instance_id=i['instance_id'],roles=i['roles'],resources=i['resources'],fields=i['fields'])))
        if not set(goals)<=set().union(*(set(r['supported_goals']) for r,i in selected_pairs)) or ss._set_state(selected_pairs,constraints,states)[0]!='TRUE':raise ValueError()
        if _frozen_oracle(snapshot,doc['selection_request'])!=doc['selection_oracle']:raise ValueError()
        if selected not in doc['selection_oracle']['minimal_solutions']:raise ValueError()
        coverage=[];by_id={s['id']:s for s in frozen['steps']}
        for goal in goals:
            closure=set()
            def include(id):
                if id in closure:return
                closure.add(id)
                for dependency in by_id[id]['depends_on']:include(dependency)
            target=ss.ORACLE_GOAL_TARGETS.get(goal)
            if target:include(target)
            coverage.append(dict(goal=goal,status=('UNKNOWN' if 'CURRENT_SERVICE_CATALOG_SOURCE_REQUIRED' in doc['source_unknowns'] else 'SUPPORTED_PREVIEW') if target else 'UNSUPPORTED',steps=sorted(closure)))
        if coverage!=doc['goal_coverage']:raise ValueError()
        # A legal but redundant model set is not a minimal service selection.
        # Removing one element suffices to disprove inclusion minimality because
        # role/resource/field conflict and UNKNOWN cannot improve by adding refs.
        for index in range(len(selected_pairs)):
            subset=selected_pairs[:index]+selected_pairs[index+1:]
            if subset and set(goals)<=set().union(*(set(r['supported_goals']) for r,i in subset)) and ss._set_state(subset,constraints,states)[0]=='TRUE':raise ValueError()
        if set(nodes)!={s['id'] for s in doc['steps']} or any(not set(s['depends_on'])<=set(nodes) for s in nodes.values()):raise ValueError()
        for s in doc['steps']:
            if any(s[k]!=v for k,v in nodes[s['id']].items()) or s['actions']!=frozen['actions'][s['id']] or s['service_refs']!=[v[0] for v in maps[s['id']]] or s['instance_mappings']!=[v[1] for v in maps[s['id']]]:raise ValueError()
    except (KeyError,TypeError,ValueError,AttributeError,ModelBoundaryError):raise Conflict('selection original provenance proof invalid') from None


def find(parent,id):
    values=[h for h in _records(parent) if h['id']==str(id)]
    if len(values)!=1:raise Conflict('selection candidate unavailable in this Case')
    _attempt(parent,values[0]);_proof(parent,values[0]);return values[0]


def verify(parent,record,current,*,now=None,historical=False):
    _proof(parent,record);doc=record['document'];expected=document(current);raw=record['candidate']
    stale=raw['binding']!=expected['binding'];valid=raw==expected
    unknown=current['state']=='UNKNOWN' or any(not v['known'] for v in current['dependency_collections'].values())
    full=current['state']=='COVERED_PREVIEW_ONLY' and not unknown and current['selection_oracle']['state'] in ('UNIQUE','MULTIPLE')
    state='STALE' if stale else 'REJECTED' if not valid else 'UNKNOWN' if unknown else 'VERIFIED_STRUCTURE_ONLY' if full else 'BLOCKED'
    if now is None:raise Conflict('current server candidate clock required')
    window=record['validity']
    if now<old._time(window['created_at']):state='CLOCK_UNCERTAIN'
    elif now>=old._time(window['expires_at']):state='EXPIRED'
    basis=dict(validator_version=4,validated_contract_sha256=cp._hash({k:expected[k] for k in expected if k!='binding'}),candidate_id=record['id'],candidate_sha256=record['candidate_sha256'],current_source_sha256=current['source_sha256'],state=state,**{k:current[k] for k in KEYS if k not in ('source_sha256',)},validity=deepcopy(window),producer_sha256=cp._hash(record['producer']))
    return dict(**basis,scope=SCOPE,profile=PROFILE,origin=ORIGIN,verification_sha256=cp._hash(basis),can_adopt=state=='VERIFIED_STRUCTURE_ONLY' and full,can_adopt_partial=False,producer=deepcopy(record['producer']),required_goals=current['required_goals'],goal_coverage=current['goal_coverage'],steps=current['steps'],constraint_evaluation=current.get('constraint_evaluation'),source_unknowns=current['source_unknowns'],selection=deepcopy(doc['selection']),selection_oracle=deepcopy(current['selection_oracle']),provider_enabled=False,read_only=True,execution_enabled=False,new_grants=False,case_goal_completed=False)


def _prior(c,p,parent,key,fp):
    rows=c.execute('SELECT * FROM preparations WHERE planning_previews @> %s',(Jsonb([dict(actor_id=p['id'],request_key=key)]),)).fetchall()
    matches=[(r,h) for r in rows for h in r['planning_previews'] or [] if h['actor_id']==p['id'] and h['request_key']==key]
    if len(matches)>1:raise Conflict('selection original key ambiguous')
    if matches:
        row,h=matches[0]
        if row['id']!=parent['id'] or h.get('profile')!=PROFILE or h['fingerprint']!=fp:raise Conflict('selection request key scope changed')
        owned=[v for v in parent.get('planning_previews') or [] if v['id']==h['id']]
        if len(owned)!=1 or cp._hash(owned[0])!=cp._hash(h):raise Conflict('selection locked original key changed')
        _attempt(parent,owned[0]);return owned[0]


def _failure(store,token,id,key,fp,attempt_id,code,catalog):
    try:
        with catalog.connection() as c:
            p,parent=bp._context(store,c,token,id,True);prep.key_lock(c,p,'planning-preview:'+key);h=_prior(c,p,parent,key,fp)
            if h is None or h['id']!=attempt_id or h['planner_attempt']['state']!='STARTED':return
            if code not in SAFE_OUTCOMES and code not in UNKNOWN_OUTCOMES:code='PLANNER_OUTCOME_UNKNOWN'
            h['planner_attempt'].update(state='OUTCOME_UNKNOWN' if code in UNKNOWN_OUTCOMES else 'FAILED_SAFE',outcome=code)
            c.execute('UPDATE preparations SET planning_previews=%s WHERE id=%s',(Jsonb(parent['planning_previews']),id))
    except (Denied,Conflict):return


def _exact(data,parent,value):
    if parent['revision']!=data.expected_preparation_revision or value['source_sha256']!=data.expected_source_sha256 or value['capability_catalog_sha256']!=data.expected_capability_catalog_sha256:raise Conflict('selection current source changed')


def generate(store,token,id,key,data,*,catalog,planner):
    from .service_selection_planner import OfflineSelectionPlanner
    if type(planner) is not OfflineSelectionPlanner:raise Conflict('explicit offline-only selection planner required')
    planner.require();fp=_fingerprint(id,data)
    with catalog.connection() as c:
        p,parent=bp._context(store,c,token,id,True);prep.key_lock(c,p,'planning-preview:'+key);prior=_prior(c,p,parent,key,fp)
        if prior is not None:
            if 'candidate' not in prior:return _attempt(parent,prior)
            return _availability_view(store,c,p,parent,catalog,prior)
        value=current(store,c,p,parent,catalog);_exact(data,parent,value)
        if value['selection_oracle']['state'] not in ('UNIQUE','MULTIPLE'):raise Conflict('current service capabilities unresolved')
        history=deepcopy(parent.get('planning_previews') or [])
        if len(history)>=bp.LIMIT or any(h.get('planner_attempt',{}).get('state')=='STARTED' for h in history):raise Conflict('bounded original attempt requires GET recovery')
        now=clock(c).astimezone(timezone.utc);window=dict(version=2,created_at=now.isoformat(),expires_at=(now+timedelta(seconds=old.VALIDITY_SECONDS)).isoformat(),seconds=old.VALIDITY_SECONDS)
        saved=deepcopy(value);saved['candidate_validity']=deepcopy(window)
        record=dict(id=str(uuid4()),profile=PROFILE,revision=len(history)+1,actor_id=p['id'],request_key=key,fingerprint=fp,document=saved,candidate_request=data.model_dump(),validity=window,planner_attempt=dict(version=4,state='STARTED',outcome=None))
        history.append(record);c.execute('UPDATE preparations SET planning_previews=%s WHERE id=%s',(Jsonb(history),id))
    def authority():
        with catalog.connection() as c:
            p,parent=bp._context(store,c,token,id,True);prep.key_lock(c,p,'planning-preview:'+key);h=_prior(c,p,parent,key,fp)
            if h is None or h['id']!=record['id'] or h['planner_attempt']['state']!='STARTED':raise Conflict('selection original attempt changed before dispatch')
            _exact(data,parent,current(store,c,p,parent,catalog));now=clock(c)
            if not old._time(h['validity']['created_at'])<=now<old._time(h['validity']['expires_at']):raise Conflict('selection original attempt expired before dispatch')
    try:
        result=planner.propose(value['selection_context'],before_dispatch=authority)
        with catalog.connection() as c:
            p,parent=bp._context(store,c,token,id,True);prep.key_lock(c,p,'planning-preview:'+key);h=_prior(c,p,parent,key,fp)
            if h is None or h['id']!=record['id'] or h['planner_attempt']['state']!='STARTED' or h['validity']!=record['validity']:raise Conflict('selection original attempt changed')
            selection=ss.parse_selection(result['selection_raw'],binding(value))
            if selection!=result['selection']:raise Conflict('selection parsed response changed')
            # A completed response can still refer to an older immutable source.
            # Distinguish that known, uncommitted refusal from malformed DSL.
            fresh=current(store,c,p,parent,catalog);_exact(data,parent,fresh)
            latest=current(store,c,p,parent,catalog,selection);_exact(data,parent,latest)
            saved=deepcopy(latest);saved['candidate_validity']=deepcopy(h['validity'])
            h.update(document=saved,selection=selection,candidate=document(saved),selection_raw=result['selection_raw'],response_raw=result['response_raw'],producer=deepcopy(result['producer']),budget_record=deepcopy(result['budget_record']),frozen_registry=deepcopy(dict(steps=bp.REGISTRY,actions=bp.ACTIONS)))
            h['candidate_sha256']=cp._hash(h['candidate']);h['producer'].update(attempt_sha256=cp._hash({k:h[k] for k in ('id','actor_id','request_key','fingerprint','validity')}),budget_sha256=cp._hash(h['budget_record']))
            h['document']['candidate_producer']=deepcopy(h['producer']);h['planner_attempt'].update(state='COMMITTED',outcome='VALIDATED',producer_sha256=cp._hash(h['producer']))
            bp._context(store,c,token,id,True);view=verify(parent,h,latest,now=clock(c))
            if view['state'] in ('EXPIRED','CLOCK_UNCERTAIN','STALE','REJECTED'):raise Conflict('selection current source or validity changed')
            c.execute('UPDATE preparations SET planning_previews=%s WHERE id=%s',(Jsonb(parent['planning_previews']),id));return view
    except ModelBoundaryError as e:
        _failure(store,token,id,key,fp,record['id'],e.code,catalog);raise Conflict('offline selection '+e.code+'; GET original key only') from None
    except Exception as e:
        _failure(store,token,id,key,fp,record['id'],'AUTHORIZATION_CHANGED' if isinstance(e,Denied) else 'SOURCE_OR_ATTEMPT_CHANGED' if isinstance(e,Conflict) else 'PLANNER_OUTCOME_UNKNOWN',catalog);raise


def _availability_view(store,c,p,parent,catalog,record):
    try:return verify(parent,record,current(store,c,p,parent,catalog,record['selection']),now=clock(c))
    except (Conflict,Denied,ModelBoundaryError):
        # Integrity failure of the saved record still raises; only current
        # availability becomes a read-only refusal with the same locator.
        item=verify(parent,record,record['document'],now=clock(c),historical=True)
        item.update(state='CURRENT_SOURCE_UNAVAILABLE',can_adopt=False,can_adopt_partial=False)
        names=('validator_version','validated_contract_sha256','candidate_id','candidate_sha256','current_source_sha256','state','preparation_id','case_id','run_id','preparation_revision','request_revision','catalog_sha256','registry_sha256','capability_catalog_sha256','validity','producer_sha256')
        item['verification_sha256']=cp._hash({k:item[k] for k in names})
        return item


def read(store,token,id,candidate_id=None,key=None,*,catalog):
    # Historical integrity is always available to the original current READ
    # authority. Today unavailable sources affect availability only, never mutate
    # or reinterpret the saved candidate, and never authorize a resend.
    with catalog.read_connection() as c:
        p,parent=bp._context(store,c,token,id);records=_records(parent)
        if candidate_id is not None:records=[find(parent,candidate_id)]
        if key is not None:records=[h for h in records if h['actor_id']==p['id'] and h['request_key']==key]
        items=[];attempts=[]
        for h in records:
            attempts.append(_attempt(parent,h))
            if 'candidate' not in h:continue
            _proof(parent,h)
            item=_availability_view(store,c,p,parent,catalog,h)
            items.append(item)
        status='COMMITTED' if key is not None and items else attempts[0]['status'] if key is not None and attempts else 'NOT_OBSERVED' if key is not None else 'LIST'
        result=dict(scope=SCOPE,profile=PROFILE,preparation_id=str(id),case_id=str(parent['case_id']),run_id=str(parent['run_id']),actor_ref=cp._hash(dict(actor_id=p['id'])),status=status,request_key=key,items=items,attempts=attempts,provider_enabled=False,read_only=True,automatically_replayed=False,execution_enabled=False,new_grants=False,case_goal_completed=False)
        return dict(**items[0],actor_ref=result['actor_ref']) if candidate_id is not None else result


def consume(parent,current,data,*,now=None,historical=False):
    record=find(parent,data.candidate_id)
    if historical:
        from .service_capability_contract import validate_release_integrity,validate_instance_integrity
        frozen=record['frozen_registry'];snapshot=record['document']['catalog_snapshot']
        try:
            releases={r['release_id']:validate_release_integrity(r,frozen['steps'],frozen['actions'],accepted_at=now) for r in snapshot['releases']}
            for instance in snapshot['instances']:validate_instance_integrity(instance,releases[instance['release_id']],frozen['steps'],frozen['actions'],accepted_at=now)
        except (ValueError,KeyError,TypeError):raise Conflict('selection historical acceptance validity invalid') from None
    v=verify(parent,record,current,now=now,historical=historical)
    if data.partial_adoption or v['state']!='VERIFIED_STRUCTURE_ONLY' or not v['can_adopt'] or v['candidate_sha256']!=data.expected_candidate_sha256 or v['verification_sha256']!=data.expected_verification_sha256:raise Conflict('current trusted selection deterministic verification required')
    names=('validator_version','validated_contract_sha256','candidate_id','candidate_sha256','current_source_sha256','state','preparation_id','case_id','run_id','preparation_revision','request_revision','catalog_sha256','registry_sha256','capability_catalog_sha256','validity','producer_sha256')
    return dict(candidate_id=v['candidate_id'],candidate_sha256=v['candidate_sha256'],verification_sha256=v['verification_sha256'],origin=ORIGIN,verification_basis={k:deepcopy(v[k]) for k in names},accepted_at=now.astimezone(timezone.utc).isoformat(),producer=deepcopy(v['producer']),selection=deepcopy(record['selection']),capability_catalog_sha256=current['capability_catalog_sha256'])


def consumption_proof(parent,plan,request):
    proof=plan.get('candidate_consumption')
    try:
        if proof['verification_basis']['validator_version']!=4 or type(proof['verification_basis']['validator_version']) is not int or request.candidate_id is None:raise ValueError()
        if request.expected_preparation_revision!=plan['adoption_preparation_revision'] or request.expected_request_revision!=plan['binding']['request_intent']['revision'] or request.expected_source_sha256!=plan['adoption_preview']['source_sha256'] or request.required_goals!=plan['required_goals']:raise ValueError()
        actual=[{k:s[k] for k in ('adapter_id','adapter','adapter_revision','depends_on','contract')} for s in plan['steps']]
        expected=[dict(adapter_id=s['id'],adapter=s['adapter'],adapter_revision=s['revision'],depends_on=s['depends_on'],contract=s) for s in plan['adoption_preview']['steps']]
        if actual!=expected or plan['events'][0].get('candidate_consumption_sha256')!=cp._hash(proof):raise ValueError()
        record=find(parent,request.candidate_id)
        expected_binding=dict(profile=PROFILE,capability_catalog_sha256=record['document']['capability_catalog_sha256'],selection=record['selection'])
        if plan['binding'].get('service_selection')!=expected_binding:raise ValueError()
        accepted=old._time(proof['accepted_at']);expected=consume(parent,plan['adoption_preview'],request,now=accepted,historical=True)
        if expected!=proof:raise ValueError()
    except (KeyError,TypeError,ValueError):raise Conflict('selection consumption original proof invalid') from None
