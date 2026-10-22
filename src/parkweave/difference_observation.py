"""Original LOCAL ADOPT difference observations, never verified outputs.

Pure historical verification uses saved candidate/ADOPT bytes only. Live
capture/adoption separately checks the original application's empty history.
"""
from copy import deepcopy
import re
from . import controlled_plans as cp
from .store import Conflict

SCOPE='LOCAL_DIFFERENCE_OBSERVATION_BASELINE'
FIELD='difference_observation_baseline'
VERSION='difference_observation_version'
SEAL='difference_observation'
TAIL={'P3','P4','P5'}


class Started(Conflict):pass


def unstarted(c,parent):
    """No issued qualification or claim against owner deletion of history."""
    from . import service_case_steps as steps
    from .business_frontier import TABLES
    steps._recovery_proofs(parent)
    plan=parent.get('service_case_plan')
    for prior in [*plan.get('history',[]),plan] if plan else []:
        tail={s['id'] for s in prior['steps'] if s['adapter_id'] in TAIL}
        if any(e['step_id'] in tail and e['action'] in ('BEGIN','VERIFY','REPORT_FAILURE','RETRY') for e in prior['events']):
            raise Started('local source continuation refuses started business coordination')
    for table in TABLES:
        if table in ('service_dispatches','service_receipt_steps','case_local_lifecycles','case_local_events'):
            query='SELECT 1 FROM '+table+' WHERE preparation_id=%s LIMIT 1'
        elif table in ('service_dispatch_offers','service_dispatch_events'):
            query='SELECT 1 FROM '+table+' x JOIN service_dispatches d ON d.id=x.dispatch_id WHERE d.preparation_id=%s LIMIT 1'
        else:query='SELECT 1 FROM '+table+' x JOIN service_receipt_steps s ON s.id=x.step_id WHERE s.preparation_id=%s LIMIT 1'
        # SQL/permission/schema failures propagate; they never mean empty.
        if c.execute(query,(parent['id'],)).fetchone():
            raise Started('local source continuation refuses existing business history')


def binding(value):
    return {k:deepcopy(value[k]) for k in ('preparation_id','case_id','run_id','preparation_revision','request_revision',
        'legacy_source_sha256','catalog_sha256','registry_sha256','capability_catalog_sha256')}


def capture(store,c,p,parent,value):
    from . import service_case_steps as steps,registered_dependencies as deps
    from .source_change_adoption import epochs,unavailable_sources
    from .business_frontier import TABLES
    try:unstarted(c,parent)
    except Started:return None
    provisional=dict(binding={'service_selection':{}},adoption_preview=value,events=[],
        steps=[dict(id=s['id'],adapter_id=s['id'],depends_on=s['depends_on'],contract=s) for s in value['steps']])
    provisional['dependency_manifest']=deps.manifest(provisional['steps'],value['dependency_collections'])
    issues,sources,_=steps.current_sources(store,c,parent,provisional)
    selected=[s['id'] for s in value['steps']]
    if any(unavailable_sources().intersection(issues[a]) for a in selected):
        raise Conflict('known original difference observation sources required')
    result=dict(scope=SCOPE,schema=1,binding=binding(value),contracts_sha256=cp._hash(value['steps']),
        adapters=selected,sources={a:deepcopy(sources[a]) for a in selected},
        empty_history_tables=list(TABLES),source_epochs_sha256=epochs(c,parent))
    return {**result,'sha256':cp._hash(result)}


def version(value):
    present=VERSION in value or FIELD in value
    if present and (set((VERSION,FIELD))-set(value) or type(value[VERSION]) is not int or value[VERSION]!=1):
        raise Conflict('difference observation version or field missing')
    return 2 if present else 1


def source_hash(value):
    data=dict(legacy_source_sha256=value['legacy_source_sha256'],capability_catalog_sha256=value['capability_catalog_sha256'])
    if version(value)==2:
        base=value[FIELD]
        data.update(difference_observation_version=1,difference_observation_sha256=base['sha256'] if base is not None else None)
    return cp._hash(data)


def validate(value,steps):
    from .business_frontier import TABLES
    if version(value)==1:return
    base=value[FIELD]
    if base is None:return
    try:
        selected=[s['id'] for s in steps]
        if (set(base)!={'scope','schema','binding','contracts_sha256','adapters','sources','empty_history_tables','source_epochs_sha256','sha256'}
            or base['scope']!=SCOPE or type(base['schema']) is not int or base['schema']!=1
            or base['binding']!=binding(value) or base['contracts_sha256']!=cp._hash(steps)
            or not 1<=len(selected)<=5 or len(set(selected))!=len(selected)
            or base['adapters']!=selected or set(base['sources'])!=set(selected)
            or any(not isinstance(base['sources'][a],dict) for a in selected)
            or base['empty_history_tables']!=list(TABLES)
            or not isinstance(base['source_epochs_sha256'],str) or not re.fullmatch('[a-f0-9]{64}',base['source_epochs_sha256'])
            or base['sha256']!=cp._hash({k:v for k,v in base.items() if k!='sha256'})):
            raise ValueError()
    except (KeyError,TypeError,ValueError):raise Conflict('original difference observation baseline invalid') from None


def seal(parent,plan,proof):
    value=plan['adoption_preview'];validate(value,value['steps'])
    if value[FIELD] is None:return None
    event=plan['events'][0]
    result=dict(scope=SCOPE,schema=1,preparation_id=str(parent['id']),case_id=str(parent['case_id']),run_id=str(parent['run_id']),
        owner_id=parent['owner_id'],plan_id=plan['id'],initial_event_id=event['id'],
        initial_dependencies_sha256=event['dependencies']['sha256'],source_sha256=value['source_sha256'],
        candidate_id=proof['candidate_id'],candidate_sha256=proof['candidate_sha256'],verification_sha256=proof['verification_sha256'],
        candidate_consumption_sha256=cp._hash(proof),baseline_sha256=value[FIELD]['sha256'],
        steps=[dict(adapter_id=s['adapter_id'],step_id=s['id'],contract_sha256=cp._hash(s['contract'])) for s in plan['steps']])
    return {**result,'sha256':cp._hash(result)}


def tail_sources(parent,plan):
    """No current reads, live bridge, or recursive whole-plan proof."""
    from . import local_demo_selections as candidates
    from .service_case_steps import Adopt,_adopt_request
    value=plan.get('adoption_preview',{})
    if value.get('profile')!=candidates.PROFILE:return {}
    if version(value)==1:return {}
    request=Adopt.model_validate(plan['adoption_request'])
    candidates.consumption_proof(parent,plan,request)
    event=plan['events'][0]
    if (event['action']!='ADOPT' or event['revision']!=1 or event['plan_id']!=plan['id'] or event['actor_id']!=parent['owner_id']
        or event['fingerprint']!=cp._hash(dict(preparation_id=str(parent['id']),action='ADOPT',**_adopt_request(request)))):
        raise Conflict('original difference observation ADOPT binding invalid')
    base=value[FIELD]
    return {} if base is None else {a:deepcopy(v) for a,v in base['sources'].items() if a in TAIL}


def pending_adapters(parent,plan,events=None):
    # ADOPT refreshes observation values, but never washes their provenance.
    selected=set(tail_sources(parent,plan))
    by_id={s['id']:s['adapter_id'] for s in plan['steps']}
    verified={by_id[e['step_id']] for e in (plan['events'] if events is None else events) if e['action']=='VERIFY'}
    return selected-verified
