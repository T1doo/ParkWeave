"""Read-only evidence for the six existing adopted local goals, never fulfillment."""
from copy import deepcopy
from uuid import UUID
import re
from . import preparation as prep, controlled_plans as cp, bounded_planning as bp
from . import service_case_steps as steps, executor_receipts as er, material_objections as objections
from .store import Conflict, Denied, digest

SCOPE='SYNTHETIC_ADOPTED_LOCAL_GOAL_RESULTS_ONLY'
TITLES={
 'LOCAL_MATERIAL_PREPARATION':'当前材料的人工核对与企业确认',
 'LOCAL_CASE_RESOURCE_ASSOCIATION':'此事项当前资源组合关联',
 'LOCAL_INTERNAL_ACCEPTANCE':'当前获派执行者本人接单',
 'LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT':'当前合成回执的企业核对',
 'LOCAL_SYNTHETIC_COORDINATION_RECORDS':'当前合成本地协作记录',
 'LOCAL_CASE_RECORD_RECHECK':'当前本地事项记录重验',
}

def structure(plan):
    """Stored application proof, not a signature against an administrator rewrite."""
    try:
        UUID(plan['id'])
        if type(plan['revision']) is not int or not 1<=plan['revision']<=64 or len(plan['events'])!=plan['revision'] or len(plan.get('history',[]))>8:raise ValueError()
        coverage,expected=bp.compile(plan['required_goals'])
        if not 1<=len(plan['required_goals'])<=8 or any(x['status']!='SUPPORTED_PREVIEW' for x in coverage) or len(expected)!=len(plan['steps']):raise ValueError()
        ids=set()
        for saved,current in zip(plan['steps'],expected):
            UUID(saved['id'])
            if saved['id'] in ids or (saved['adapter_id'],saved['adapter'],saved['adapter_revision'],saved['depends_on'])!=(current['id'],current['adapter'],current['revision'],current['depends_on']):raise ValueError()
            ids.add(saved['id'])
        keys=set();event_ids=set()
        for i,event in enumerate(plan['events'],1):
            UUID(event['id'])
            if (type(event['revision']) is not int or event['revision']!=i or event['plan_id']!=plan['id'] or event['id'] in event_ids or
                event['request_key'] in keys or not re.fullmatch('[A-Za-z0-9_-]{1,100}',event['request_key']) or not re.fullmatch('[a-f0-9]{64}',event['fingerprint']) or
                event['action'] not in ('ADOPT','BEGIN','REPORT_FAILURE','RETRY','VERIFY') or
                (i==1)!=(event['action']=='ADOPT') or (event['step_id'] is None if i==1 else event['step_id'] in ids) is not True):raise ValueError()
            keys.add(event['request_key']);event_ids.add(event['id'])
    except (KeyError,TypeError,ValueError,AttributeError):raise Conflict('adopted goal result plan proof invalid')


def verification(parent,plan,step):
    matches=[]
    for event in plan['events']:
        if event['action']!='VERIFY' or event['step_id']!=step['id']:continue
        try:
            data=dict(action='VERIFY',step_id=step['id'],expected_revision=event['revision']-1,
                      expected_source_sha256=event['source_sha256'],reason=event['reason'])
            if (event['actor_id']==parent['owner_id'] and event['source_sha256']==step['verified_sha256']==cp._hash(step['verified_sources']) and
                event['sources']==step['verified_sources'] and event['fingerprint']==cp._hash(dict(preparation_id=str(parent['id']),**data))):matches.append(event)
        except (KeyError,TypeError,ValueError):pass
    return matches[-1] if matches else None


def material_proof(store,c,parent):
    bound,valid=objections.binding(store,c,parent)
    records=c.execute("SELECT * FROM preparation_events WHERE preparation_id=%s AND action IN ('REVIEW','CONFIRM') ORDER BY revision",(parent['id'],)).fetchall()
    review=next((e for e in reversed(records) if e['action']=='REVIEW'),None)
    confirm=next((e for e in reversed(records) if e['action']=='CONFIRM'),None)
    def matches(e,action,actor,state):
        if not e:return False
        want=dict(preparation_id=str(parent['id']),case_id=str(parent['case_id']),run_id=str(parent['run_id']),revision=e['revision'],actor_id=actor,action=action,state=state,snapshot_sha256=parent['review_sha256'])
        return e['actor_id']==actor and all(type(e['payload'].get(k)) is type(v) and e['payload'].get(k)==v for k,v in want.items())
    valid=bool(valid and parent['state']=='LOCAL_CONFIRMED' and matches(review,'REVIEW',parent['reviewer_id'],'REVIEWED') and
               matches(confirm,'CONFIRM',parent['owner_id'],'LOCAL_CONFIRMED') and review['revision']<confirm['revision']<=parent['revision'])
    issues=[] if valid else ['CURRENT_MATERIAL_EVENT_PROOF_REQUIRED']
    if objections.unresolved(store,c,parent):issues.append('MATERIAL_DELIVERY_OBJECTION_UNRESOLVED')
    output=dict(kind='REVIEWED_AND_OWNER_CONFIRMED_SYNTHETIC_MATERIALS',preparation_id=str(parent['id']),snapshot_sha256=parent['review_sha256'],
                materials=bound['materials'],review_event_id=str(review['id']) if review else None,confirm_event_id=str(confirm['id']) if confirm else None)
    return issues,output


def outputs(store,c,parent,plan,issues,sources):
    out={};extra,material=material_proof(store,c,parent);issues['P1']=sorted(set(issues['P1']+extra));out['P1']=material
    s=sources['P2'];out['P2']=dict(kind='CURRENT_SYNTHETIC_CASE_RESOURCE_ASSOCIATION',**{k:s.get(k) for k in ('resource_link_id','resource_link_revision','combination_id','combination_state','members')})
    s=sources['P3'];event=s.get('acceptance_event')
    out['P3']=dict(kind='CURRENT_EXECUTOR_ACCEPTANCE',**{k:s.get(k) for k in ('dispatch_id','offer_id','executor_id','receipt_step_id')},acceptance_event_id=event['id'] if event else None)
    s=sources['P4'];row=er.current_step(c,parent);receipt=er._current(c,row) if row else None
    kind='MANUAL_SYNTHETIC_TEXT_ACKNOWLEDGEMENT';execution_id=None
    if receipt and receipt.get('adapter_execution'):
        from .isolated_local_execution import current
        if not current(store,c,row,parent,receipt):issues['P4'].append('CURRENT_LOCAL_EXECUTION_PROOF_REQUIRED')
        else:kind='ISOLATED_SYNTHETIC_HANDOFF_REPORT_ACKNOWLEDGEMENT';execution_id=receipt['adapter_execution']['report']['execution_id']
    out['P4']=dict(kind=kind,execution_id=execution_id,**{k:s.get(k) for k in ('receipt_step_id','receipt_id','receipt_version','receipt_sha256')},
                  submit_event_ids=[e['id'] for e in s.get('receipt_events',[]) if e['action']=='SUBMIT'],ack_event_ids=[e['id'] for e in s.get('receipt_events',[]) if e['action']=='ACKNOWLEDGE'])
    if 'P5' in sources:
        from . import case_lifecycle as life
        s=sources['P5'];local=s.get('local_lifecycle');proof=None
        if local:
            events=c.execute("SELECT * FROM case_local_events WHERE preparation_id=%s AND cycle=%s AND action='REVALIDATE' ORDER BY revision DESC",(parent['id'],local['cycle'])).fetchall()
            for e in events:
                want=dict(scope=life.SCOPE,action='REVALIDATE',actor_id=parent['owner_id'],revision=e['revision'],cycle=local['cycle'],verified_snapshot_sha256=local['verified_sha256'],local_record_state='READY')
                if (e['actor_id']==parent['owner_id'] and e['revision']<=local['revision'] and e['snapshot']==local['verified_snapshot'] and
                    life._sha(e['snapshot'],local['cycle'])==local['verified_sha256'] and all(type(e['payload'].get(k)) is type(v) and e['payload'].get(k)==v for k,v in want.items())):
                    proof=e;break
        if not proof:issues['P5'].append('CURRENT_LOCAL_REVALIDATE_EVENT_PROOF_REQUIRED')
        out['P5']=dict(kind='LOCAL_CASE_RECORD_REVALIDATION',cycle=local['cycle'] if local else None,revision=local['revision'] if local else None,
                       local_record_state=local['state'] if local else None,revalidation_event_id=str(proof['id']) if proof else None,source_sha256=local['verified_sha256'] if local else None)
    return out


@er.bounded
def read(store,token,id):
    with store.connect() as c:
        c.execute("SET LOCAL lock_timeout='3s'")
        p,parent=cp._auth(store,c,token,id)
        if p['role']!='enterprise_operator' or p['id']!=parent['owner_id']:raise Denied('original owner goal result scope required')
        run=store.scoped_run(c,p,parent['run_id'])
        case=c.execute("SELECT * FROM cases WHERE id=%s AND run_id=%s AND park_id=%s AND org_id=%s AND source='SYNTHETIC'",(parent['case_id'],parent['run_id'],parent['park_id'],parent['org_id'])).fetchone()
        if not case or parent['service_id']!=prep.SERVICE or parent['service_version']!=1 or run['state']!='SUCCEEDED' or run['input'].get('action','case.create')!='case.create':raise Denied('bound existing synthetic Case required')
        intent=parent.get('request_intent') or {};goals=intent.get('required_goals',[]);plan=deepcopy(parent.get('service_case_plan'));rows=[];binding_issues=[];states={};proofs={};out={};sources={};issues={}
        if plan:
            structure(plan);binding_issues=steps._binding_issues(c,parent,plan)
            if plan['required_goals']!=goals:binding_issues.append('PLAN_REQUIRED_GOALS_CHANGED')
            # First acquire the original source/fixed-plan/lifecycle locks.
            # Then recapture timed validity after their last possible wait.
            steps.current_sources(store,c,parent,plan)
            issues,sources,actual=steps.current_sources(store,c,parent,plan);out=outputs(store,c,parent,plan,issues,sources)
            for step in plan['steps']:
                a=step['adapter_id'];proof=verification(parent,plan,step);proofs[a]=proof
                deps=all(states.get(x)=='LOCAL_OUTPUT_VERIFIED' for x in step['depends_on'])
                reasons=list(issues[a])+binding_issues
                if not deps:reasons.append('CURRENT_PREDECESSOR_OUTPUT_VERIFICATION_REQUIRED')
                if step['coordination_state']=='REPORTED_BLOCKED':reasons.append('REPORTED_OBSTACLE_REQUIRES_EXPLICIT_RETRY')
                if step.get('verified_sha256') and not proof:reasons.append('OWNER_VERIFY_EVENT_PROOF_INVALID')
                current=bool(proof and step['verified_sha256']==cp._hash(sources[a]) and not step.get('invalidated') and step['coordination_state']=='VERIFIED')
                state='LOCAL_OUTPUT_VERIFIED' if current and not reasons else 'NEEDS_RECHECK' if proof or step.get('verified_sha256') else 'WAITING_DEPENDENCY' if not deps else 'WAITING_OUTPUT' if issues[a] else 'AWAITING_OWNER_VERIFICATION'
                states[a]=state
                step['_result_reasons']=sorted(set(reasons));step['_output_readable']=not issues[a] and not binding_issues and deps
        by_adapter={s['adapter_id']:s for s in plan['steps']} if plan else {}
        for goal in goals:
            adapter=bp.GOALS.get(goal);step=by_adapter.get(adapter);proof=proofs.get(adapter)
            state='UNSUPPORTED' if not adapter else 'NOT_ADOPTED' if not plan else 'NEEDS_NEW_PLAN' if binding_issues or not step else states[adapter]
            rows.append(dict(goal=goal,title=TITLES.get(goal,goal),adapter_id=adapter,step_id=step['id'] if step else None,state=state,
                             issues=sorted(set(binding_issues+(step.get('_result_reasons',[]) if step else ['ADOPT_CURRENT_SUPPORTED_PLAN'] if adapter else ['NO_REGISTERED_LOCAL_CAPABILITY']))),
                             actual_output=out.get(adapter) if step and step['_output_readable'] else None,
                             historical_verification=dict(id=proof['id'],revision=proof['revision'],actor_id=proof['actor_id'],current=state=='LOCAL_OUTPUT_VERIFIED') if proof else None,
                             next_action='READ_ORIGINAL_STEP_AND_VERIFY' if state=='AWAITING_OWNER_VERIFICATION' else 'USE_ORIGINAL_ADAPTER_TO_RECHECK' if state not in ('LOCAL_OUTPUT_VERIFIED','UNSUPPORTED') else 'MANUAL_SERVICE_CONTRACT_REQUIRED' if state=='UNSUPPORTED' else None))
        return dict(scope=SCOPE,actor_id=p['id'],preparation_id=str(id),case_id=str(parent['case_id']),run_id=str(parent['run_id']),preparation_revision=parent['revision'],
                    request_revision=intent.get('revision',0),current_request=intent.get('request_text',parent['goal']),original_request=parent['goal'],plan_id=plan['id'] if plan else None,plan_revision=plan['revision'] if plan else 0,
                    state='UNKNOWN' if not rows else 'LOCAL_OUTPUTS_VERIFIED' if all(r['state']=='LOCAL_OUTPUT_VERIFIED' for r in rows) else 'UNVERIFIED',
                    results=rows,adopted_goals=list(plan['required_goals']) if plan else [],historical_plans=[dict(id=h['id'],revision=h['revision'],goals=h['required_goals']) for h in plan.get('history',[])] if plan else [],
                    binding_issues=sorted(set(binding_issues)),read_only=True,automatically_verified=False,case_goal_completed=False,qualification='NOT_EVALUATED',external_acceptance='NOT_SUBMITTED',offline_fulfillment='NO_EVIDENCE')
