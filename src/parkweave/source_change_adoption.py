"""Explicit source-change review bound to an existing opportunity and plan.

Imported prose never supplies facts or authority. Only the original sources and
registered edges determine the patch; this module performs no business action.
"""
from copy import deepcopy
import re
from pydantic import BaseModel, ConfigDict, Field
from . import controlled_plans as cp, preparation as prep, registered_dependencies as deps
from . import case_opportunities as op, executor_receipts as er
from .store import Conflict, Denied

SCOPE='SOURCE_CHANGE_LOCAL_REVISION_PREVIEW'


class OpportunityProof(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    card_id:str=Field(pattern='^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')
    expected_ledger_revision:int=Field(ge=1,le=128)
    expected_card_version:int=Field(ge=1,le=128)
    expected_basis_sha256:str=Field(pattern='^[a-f0-9]{64}$')
    expected_preview_sha256:str=Field(pattern='^[a-f0-9]{64}$')


def evidence_sources(parent,plan,events=None):
    """Reconstruct accepted source bases from original owner VERIFY/ADOPT events."""
    from .service_case_steps import Command
    values={};by_id={s['id']:s['adapter_id'] for s in plan['steps']}
    for event in plan['events'] if events is None else events:
        if event['action']=='VERIFY':
            command=Command(action='VERIFY',step_id=event['step_id'],expected_revision=event['revision']-1,
                            expected_source_sha256=event['source_sha256'],reason=event['reason'])
            if (event['actor_id']!=parent['owner_id'] or event['source_sha256']!=cp._hash(event['sources']) or
                event['fingerprint']!=cp._hash(dict(preparation_id=str(parent['id']),**command.model_dump(mode='json')))):
                raise Conflict('original source verification proof invalid')
            values[by_id[event['step_id']]]=deepcopy(event['sources'])
        elif event['action']=='ADOPT' and event.get('local_revision',{}).get('source_change') is not None:
            values=deepcopy(event['local_revision']['source_change']['current_sources'])
    return values


def source_impact(steps,before,current):
    selected={s['adapter_id'] for s in steps}
    if (not isinstance(before,dict) or not isinstance(current,dict) or set(before)!=selected or set(current)!=selected or
        any(not isinstance(x,dict) for x in list(before.values())+list(current.values()))):return set(),set(),True
    direct={a for a in selected if before[a]!=current[a]}
    return direct,deps.closure(steps,direct),False


def epochs(c,parent):
    """Row versions reject A->B->A between preview and explicit confirmation.

    Kept separate from old opportunity bases/fingerprints. The bounded scoped
    rows are read with existing privileges; only their digest leaves this stack.
    They detect committed rewrites, not an external administrator transaction
    committing after the final read (the existing trusted-admin boundary).
    """
    owner=parent['owner_id'];id=parent['id'];run=parent['run_id']
    queries={
      'materials':('SELECT DISTINCT ON(slot) id,slot,version,xmin::text AS row_version FROM preparation_evidence WHERE preparation_id=%s ORDER BY slot,version DESC',(id,)),
      'catalog':('SELECT service_id,version,xmin::text AS row_version FROM preparation_catalog WHERE park_id=%s AND service_id=%s ORDER BY version LIMIT 33',(parent['park_id'],parent['service_id'])),
      'resources':('SELECT r.id,r.xmin::text AS row_version FROM synthetic_resources r WHERE EXISTS(SELECT 1 FROM synthetic_resource_grants g WHERE g.resource_id=r.id AND g.principal_id=%s AND g.park_id=%s AND g.org_id=%s) ORDER BY r.id LIMIT 257',(owner,parent['park_id'],parent['org_id'])),
      'resource_grants':('SELECT resource_id,capability,xmin::text AS row_version FROM synthetic_resource_grants WHERE principal_id=%s AND park_id=%s AND org_id=%s ORDER BY resource_id,capability LIMIT 257',(owner,parent['park_id'],parent['org_id'])),
      'assignments':('SELECT principal_id,xmin::text AS row_version FROM run_assignments WHERE run_id=%s AND park_id=%s AND org_id=%s ORDER BY principal_id LIMIT 257',(run,parent['park_id'],parent['org_id'])),
      'actors':('SELECT id,xmin::text AS row_version FROM principals WHERE park_id=%s AND org_id=%s AND (id IN (%s,%s) OR id IN (SELECT principal_id FROM run_assignments WHERE run_id=%s)) ORDER BY id LIMIT 259',(parent['park_id'],parent['org_id'],owner,parent['reviewer_id'],run)),
      'capabilities':('SELECT principal_id,capability,xmin::text AS row_version FROM capability_grants WHERE park_id=%s AND org_id=%s AND (principal_id IN (%s,%s) OR principal_id IN (SELECT principal_id FROM run_assignments WHERE run_id=%s)) ORDER BY principal_id,capability LIMIT 1025',(parent['park_id'],parent['org_id'],owner,parent['reviewer_id'],run)),
      'preparation_grants':('SELECT principal_id,capability,xmin::text AS row_version FROM preparation_grants WHERE park_id=%s AND org_id=%s AND principal_id IN (%s,%s) ORDER BY principal_id,capability LIMIT 33',(parent['park_id'],parent['org_id'],owner,parent['reviewer_id'])),
      'links':('SELECT id,xmin::text AS row_version FROM case_resource_links WHERE preparation_id=%s ORDER BY id LIMIT 129',(id,)),
      'dispatches':('SELECT id,xmin::text AS row_version FROM service_dispatches WHERE preparation_id=%s ORDER BY id LIMIT 129',(id,)),
      'receipt_steps':('SELECT id,xmin::text AS row_version FROM service_receipt_steps WHERE preparation_id=%s ORDER BY id LIMIT 129',(id,)),
      'offers':('SELECT o.id,o.xmin::text AS row_version FROM service_dispatch_offers o JOIN service_dispatches d ON d.id=o.dispatch_id WHERE d.preparation_id=%s ORDER BY o.id LIMIT 129',(id,)),
      'dispatch_events':('SELECT e.id,e.xmin::text AS row_version FROM service_dispatch_events e JOIN service_dispatches d ON d.id=e.dispatch_id WHERE d.preparation_id=%s ORDER BY e.id LIMIT 129',(id,)),
      'receipts':('SELECT r.id,r.xmin::text AS row_version FROM service_step_receipts r JOIN service_receipt_steps s ON s.id=r.step_id WHERE s.preparation_id=%s ORDER BY r.id LIMIT 129',(id,)),
      'receipt_events':('SELECT e.id,e.xmin::text AS row_version FROM service_receipt_events e JOIN service_receipt_steps s ON s.id=e.step_id WHERE s.preparation_id=%s ORDER BY e.id LIMIT 129',(id,)),
      'holds':('SELECT h.id,h.xmin::text AS row_version FROM synthetic_resource_holds h JOIN synthetic_resource_combination_members m ON m.hold_id=h.id WHERE m.combination_id=(SELECT combination_id FROM case_resource_links WHERE preparation_id=%s ORDER BY revision DESC LIMIT 1) ORDER BY h.id LIMIT 129',(id,)),
      'combination':('SELECT id,xmin::text AS row_version FROM synthetic_resource_combinations WHERE id=(SELECT combination_id FROM case_resource_links WHERE preparation_id=%s ORDER BY revision DESC LIMIT 1) ORDER BY id LIMIT 2',(id,)),
      'lifecycle':('SELECT preparation_id,xmin::text AS row_version FROM case_local_lifecycles WHERE preparation_id=%s ORDER BY preparation_id LIMIT 129',(id,)),
    }
    bounds={'materials':2,'catalog':32,'resources':256,'resource_grants':256,'assignments':256,
            'actors':258,'capabilities':1024,'preparation_grants':32,'links':128,'dispatches':128,'receipt_steps':128,'lifecycle':128,
            'offers':128,'dispatch_events':128,'receipts':128,'receipt_events':128,'holds':128,'combination':1}
    if prep.fact_enabled(c,parent):
        queries['facts']=('SELECT id,xmin::text AS row_version FROM fact_assertions WHERE principal_id=%s AND park_id=%s AND org_id=%s ORDER BY id LIMIT 49',(owner,parent['park_id'],parent['org_id']))
        queries['field_grants']=('SELECT field_name,xmin::text AS row_version FROM field_grants WHERE principal_id=%s AND park_id=%s AND org_id=%s ORDER BY field_name LIMIT 17',(owner,parent['park_id'],parent['org_id']))
        bounds.update(facts=48,field_grants=16)
    values={}
    for name,(sql,args) in queries.items():
        rows=c.execute(sql,args).fetchall()
        if len(rows)>bounds[name]:raise Conflict('bounded current source row-version proof unavailable')
        values[name]=cp._normal(rows)
    return cp._hash(values)



def unavailable_sources():
    return {'CURRENT_OWNER_AUTHORITY_REQUIRED','CURRENT_REVIEWER_AUTHORITY_REQUIRED','CURRENT_EXECUTOR_AUTHORITY_REQUIRED',
        'CURRENT_RESOURCE_AUTHORITY_REQUIRED','CURRENT_SERVICE_CATALOG_REQUIRED','CURRENT_SERVICE_CATALOG_SOURCE_REQUIRED',
        'RECEIPT_PROVENANCE_CHANGED','ACCEPTANCE_EVENT_PROVENANCE_CHANGED','RECEIPT_EVENT_PROVENANCE_CHANGED',
        'RESOURCE_CANCELLED','RESOURCE_WINDOW_ENDED','RESOURCE_HOLD_EXPIRED','FACT_PURPOSE_LEDGER_INVALID',
        'FACT_PURPOSE_AUTHORITY_OR_SOURCE_UNAVAILABLE','SELECTED_FACT_NOT_CURRENT','FACT_SOURCE_VALIDITY_CHANGED',
        'SELECTED_INSTANCE_RESOURCE_BINDING_CHANGED','SELECTED_INSTANCE_ACTOR_BINDING_CHANGED','SELECTED_INSTANCE_EXECUTOR_BINDING_CHANGED'}


def current_card(parent,card_id,value=None):
    value=op.ledger(parent) if value is None else value
    cards,heads=op.project(value);card=cards.get(str(card_id))
    if (not card or card['state']!='PENDING_REVIEW' or heads[card['entry']['family_id']][1]!=card['id']):
        raise Conflict('current pending latest opportunity required')
    return value,card


def build(store,c,p,parent,card_id,*,current=None,fact_provenance_scope=None,dependency_scope=None):
    if dependency_scope is not None and (dependency_scope!='BOUNDED_MULTI_SOURCE_V1' or fact_provenance_scope is not None):
        raise Conflict('unique supported dependency scope required')
    from . import service_case_steps as service
    plan=deepcopy(parent.get('service_case_plan'))
    if not plan:raise Conflict('existing registered plan required')
    service._recovery_proofs(parent)
    value,card=current_card(parent,card_id)
    basis,basis_sha=op.sources(c,parent)
    if card['basis_sha256']!=basis_sha or not any(x['version']==card['entry']['catalog_version'] for x in basis['catalog']):
        raise Conflict('current opportunity source required; explicit refresh required')
    current=current or service.planning._proposal(store,c,p,parent)
    binding_issues=service._binding_issues(c,parent,plan,store=store)
    issues,sources,_=service.current_sources(store,c,parent,plan)
    sources={s['adapter_id']:sources[s['adapter_id']] for s in plan['steps']}
    before=evidence_sources(parent,plan)
    direct,affected,missing=source_impact(plan['steps'],before,sources)
    dependency_basis,dependency_affected,unknown=service.dependency_impact(store,c,parent,plan)
    affected|=dependency_affected
    from . import typed_source_impact
    typed_graph=typed_source_impact.build(parent,plan,before,sources,plan.get('dependency_manifest'),dependency_basis)
    expected_ids=[s['id'] for s in plan['steps'] if s['adapter_id'] in affected]
    expected_preserved=[s['id'] for s in plan['steps'] if s['adapter_id'] not in affected]
    if not typed_graph['unknown_scope'] and (typed_graph['affected']!=expected_ids or typed_graph['preserved']!=expected_preserved):
        raise Conflict('typed source graph impact inconsistent with original source proof')
    if typed_graph['unknown_scope']:affected={s['adapter_id'] for s in plan['steps']}
    else:affected={s['adapter_id'] for s in plan['steps'] if s['id'] in typed_graph['affected']}
    blockers=list(binding_issues)
    from .plan_source_conflicts import adoption_blockers
    blockers.extend(adoption_blockers(c,parent,plan))
    if typed_graph['unknown_scope']:blockers.append('KNOWN_CURRENT_SOURCE_GRAPH_REQUIRED')
    if missing:blockers.append('CURRENT_VERIFIED_SOURCE_BASE_REQUIRED')
    if unknown or any(not x['known'] for x in dependency_basis['collections'].values()):blockers.append('KNOWN_CURRENT_DEPENDENCIES_REQUIRED')
    if not affected:blockers.append('NO_ACTUAL_SOURCE_CHANGE')
    if plan.get('partial_adoption') is True:blockers.append('PARTIAL_PLAN_REQUIRES_ORIGINAL_REPLACEMENT')
    if current['state']!='COVERED_PREVIEW_ONLY' or current['source_unknowns']:blockers.append('CURRENT_SUPPORTED_PROPOSAL_REQUIRED')
    # These indicate absent authority, corrupt provenance, or expired/withdrawn
    # evidence. Ordinary current-business rechecks (e.g. a material reopen) do
    # not become evidence and still require their original adapter correction.
    unavailable=unavailable_sources()
    fact=sources.get('P1',{}).get('fact_clarification')
    if any(unavailable.intersection(reasons) for reasons in issues.values()) or (fact is not None and fact.get('satisfied') is not True):
        blockers.append('CURRENT_KNOWN_SOURCE_REQUIRED')
    locks=[s for s in plan['steps'] if service._manual_lock(plan,s)]
    if any(s['adapter_id'] in affected for s in locks):blockers.append('AFFECTED_LOCK_REQUIRES_EXPLICIT_UNLOCK')
    _,_,_,_,states,_=service._inspect(store,c,parent,deepcopy(plan),observe=False)
    remaining_verify=sum(s['adapter_id'] in affected or states[s['adapter_id']]!='VERIFIED' for s in plan['steps'])
    if plan['revision']+1+len(locks)+remaining_verify>service.LIMIT:blockers.append('EVENT_CAPACITY_RESERVED_FOR_UNLOCK_AND_VERIFY')
    if prep.case_write_blocked(c,parent):blockers.append('CASE_WRITE_BLOCKED')
    try:store.check_capability(c,p,'EXECUTE')
    except Denied:blockers.append('CURRENT_EXECUTE_REQUIRED')
    change=dict(version=2,source_impact=typed_graph,binding=op.binding(parent),plan_id=plan['id'],plan_revision=plan['revision'],
        ledger_revision=value['revision'],ledger_sha256=value['events'][-1]['sha256'],card_id=card['id'],card_version=card['version'],
        basis_sha256=card['basis_sha256'],basis=deepcopy(card['basis']),proposal_sha256=current['source_sha256'],
        source_epochs_sha256=epochs(c,parent),before_sources=before,current_sources=sources,dependencies_sha256=dependency_basis['sha256'],
        directly_changed=[s['id'] for s in plan['steps'] if s['adapter_id'] in direct],
        affected=[s['id'] for s in plan['steps'] if s['adapter_id'] in affected],preserved=[s['id'] for s in plan['steps'] if s['adapter_id'] not in affected])
    change['sha256']=cp._hash(change)
    proof=dict(card_id=card['id'],expected_ledger_revision=value['revision'],expected_card_version=card['version'],
        expected_basis_sha256=card['basis_sha256'],expected_preview_sha256=change['sha256'])
    adoption=dict(expected_preparation_revision=parent['revision'],expected_request_revision=parent['request_intent']['revision'],
        expected_source_sha256=current['source_sha256'],expected_plan_revision=plan['revision'],required_goals=deepcopy(plan['required_goals']),
        reason='明确采纳当前真实来源的局部修订；原提示不作为事实或授权',local_revision=True,opportunity_proof=proof)
    result=dict(scope=SCOPE,actor_ref=cp._hash(dict(actor_id=p['id'])),preparation_id=str(parent['id']),case_id=str(parent['case_id']),run_id=str(parent['run_id']),
        plan_id=plan['id'],plan_revision=plan['revision'],opportunity_revision=value['revision'],card_id=card['id'],card_version=card['version'],
        basis_sha256=card['basis_sha256'],preview_sha256=change['sha256'],current_preview_source_sha256=current['source_sha256'],current_sources_sha256=cp._hash(sources),
        directly_changed=change['directly_changed'],affected=change['affected'],preserved=change['preserved'],
        source_impact=typed_graph,remaining_verify_events=remaining_verify,unknown_scope='THIS_CASE' if missing or unknown or typed_graph['unknown_scope'] else None,blocking_reasons=sorted(set(blockers)),can_adopt=not blockers,adoption=adoption,
        new_grants=False,automatic_execution=False,case_goal_completed=False,qualification_decision='NOT_EVALUATED')
    if fact_provenance_scope is not None:
        from . import employees_fact_provenance as fact_provenance
        if fact_provenance_scope!=fact_provenance.SCOPE:raise Conflict("unsupported fact provenance scope")
        result,change,affected=fact_provenance.enhance(c,parent,result,change,affected)
    if dependency_scope is not None:
        from . import unified_dependency_propagation
        result,change,affected=unified_dependency_propagation.enhance(c,parent,result,change,affected)
    return result,change,dependency_basis,affected


def typed_dependency_preview(parent,result,change):
    """Read-only projection; never part of build(), an ADOPT body or history."""
    from . import dependency_graph as graph, service_case_steps as service
    try:
        converted=graph.from_unified_v1(result['dependency_propagation'])
    except graph.GraphError:
        raise Conflict('versioned dependency preview unavailable') from None
    plan=parent['service_case_plan'];locks=[]
    for step in plan['steps']:
        lock=service._manual_lock(plan,step)
        if lock:
            locks.append(dict(node_id=step['id'],event_id=lock['event_id'],
                              source_sha256=lock['source_sha256']))
    locks.sort(key=lambda item:item['node_id'])
    impact=converted['preview']
    binding={k:result[k] for k in ('actor_ref','preparation_id','case_id','run_id',
        'plan_id','plan_revision','card_id','card_version','opportunity_revision',
        'current_sources_sha256')}
    binding.update(legacy_preview_sha256=result['preview_sha256'],
                   source_epochs_sha256=change['source_epochs_sha256'])
    value=dict(scope='VERSIONED_TYPED_GRAPH_V1',binding=binding,
        legacy_graph_sha256=converted['legacy_sha256'],before=converted['before'],
        current=converted['current'],impact=impact,current_manual_locks=locks,
        lock_conflicts=[dict(**lock,reason='LOCK_CONFLICT') for lock in locks
                        if lock['node_id'] in impact['affected']],
        read_only=True,can_adopt=False,execution_authorized=False,
        authority_verified=False,new_grants=False,automatic_execution=False,
        history_rewritten=False,automatically_replayed=False,
        case_goal_completed=False,qualification_decision='NOT_EVALUATED')
    return {**value,'sha256':graph.digest(value)}


@er.bounded
def read(store,token,id,card_id,*,dependency_scope=None,graph_preview=None):
    if graph_preview is not None and (graph_preview!='VERSIONED_TYPED_GRAPH_V1' or
                                     dependency_scope!='BOUNDED_MULTI_SOURCE_V1'):
        raise Conflict('explicit original dependency scope required for graph preview')
    with store.connect() as c:
        # Obtain the original plan's parent UPDATE lock up front to avoid SHARE
        # upgrades when reading the original source adapters. No UPDATE follows.
        from .service_case_steps import _context
        p,parent=_context(store,c,token,id)
        if p['role']!='enterprise_operator':raise Denied('original Case owner required')
        if parent['service_id']!=prep.SERVICE or 'opportunities' not in parent:raise Denied('existing synthetic opportunity Case required')
        result,change,_,_=build(store,c,p,parent,card_id,**({'dependency_scope':dependency_scope} if dependency_scope is not None else {}))
        if graph_preview is not None:
            result={**result,'typed_dependency_preview':typed_dependency_preview(parent,result,change)}
            prep.grant(store,c,p,'PREPARE')
        return result


def validate_history(parent,plan,event,previous_dependencies,current_dependencies):
    """Prove the saved source patch against immutable original ledger prefixes."""
    if isinstance(event.get('local_revision',{}).get('source_change'),dict) and event['local_revision']['source_change'].get('version')==4:
        from .unified_dependency_propagation import validate_history as validate_unified_history
        return validate_unified_history(parent,plan,event,previous_dependencies,current_dependencies)
    if isinstance(event.get("local_revision",{}).get("source_change"),dict) and event["local_revision"]["source_change"].get("version")==3:
        from .employees_fact_provenance import validate_history as validate_fact_history
        return validate_fact_history(parent,plan,event,previous_dependencies,current_dependencies)
    from .service_case_steps import Adopt
    patch=event['local_revision'];request=Adopt.model_validate(patch['request']);proof=request.opportunity_proof
    if request.dependency_scope is not None:
        raise ValueError('unified dependency scope requires source-change version 4')
    if request.fact_provenance_scope is not None:
        raise ValueError('fact provenance scope requires source-change version 3')
    change=patch['source_change']
    keys={'version','binding','plan_id','plan_revision','ledger_revision','ledger_sha256','card_id','card_version','basis_sha256','basis','proposal_sha256',
          'source_epochs_sha256','before_sources','current_sources','dependencies_sha256','directly_changed','affected','preserved','sha256'}
    version=change.get('version') if isinstance(change,dict) else None
    if version==2:keys=keys|{'source_impact'}
    if (proof is None or not isinstance(change,dict) or set(change)!=keys or
        any(type(change[k]) is not int for k in ('version','plan_revision','ledger_revision','card_version')) or version not in (1,2) or
        any(not isinstance(change[k],str) or not re.fullmatch('[a-f0-9]{64}',change[k]) for k in
            ('ledger_sha256','basis_sha256','proposal_sha256','source_epochs_sha256','dependencies_sha256','sha256')) or
        not isinstance(change['before_sources'],dict) or not isinstance(change['current_sources'],dict) or
        change['binding']!=op.binding(parent) or change['plan_id']!=plan['id'] or change['plan_revision']!=event['revision']-1 or
        change['ledger_revision']!=proof.expected_ledger_revision or change['card_id']!=proof.card_id or
        change['card_version']!=proof.expected_card_version or change['basis_sha256']!=proof.expected_basis_sha256 or
        change['proposal_sha256']!=request.expected_source_sha256 or change['dependencies_sha256']!=current_dependencies['sha256'] or
        change['sha256']!=proof.expected_preview_sha256 or change['sha256']!=cp._hash({k:v for k,v in change.items() if k!='sha256'})):
        raise ValueError('source-change binding proof invalid')
    value=op.ledger(parent)
    if value['revision']<proof.expected_ledger_revision:raise ValueError('source-change ledger prefix missing')
    value['events']=value['events'][:proof.expected_ledger_revision];value['revision']=proof.expected_ledger_revision
    _,card=current_card(parent,proof.card_id,value)
    if (value['events'][-1]['sha256']!=change['ledger_sha256'] or card['version']!=change['card_version'] or
        card['basis_sha256']!=change['basis_sha256'] or card['basis']!=change['basis']):raise ValueError('source-change original opportunity proof invalid')
    earlier=[e for e in plan['events'] if e['revision']<event['revision']]
    before=evidence_sources(parent,plan,earlier)
    if before!=change['before_sources']:raise ValueError('source-change original verification base changed')
    direct,affected,unknown=source_impact(plan['steps'],before,change['current_sources'])
    dependency_affected,dependency_unknown=deps.impact_between(plan['steps'],previous_dependencies,current_dependencies)
    if unknown or dependency_unknown:raise ValueError('source-change unknown base cannot authorize adoption')
    affected|=dependency_affected
    if version==2:
        from . import typed_source_impact
        graph=change['source_impact']
        if not isinstance(graph,dict) or type(graph.get('schema')) is not int or graph['schema']!=1:
            raise ValueError('typed source graph schema unsupported')
        expected_graph=typed_source_impact.build_v1(parent,plan,before,change['current_sources'],previous_dependencies,current_dependencies)
        if change['source_impact']!=expected_graph or expected_graph['unknown_scope']:
            raise ValueError('typed source graph proof invalid')
        if set(expected_graph['affected'])!={s['id'] for s in plan['steps'] if s['adapter_id'] in affected}:
            raise ValueError('typed source graph impact changed')
    expected_direct=[s['id'] for s in plan['steps'] if s['adapter_id'] in direct]
    expected_affected=[s['id'] for s in plan['steps'] if s['adapter_id'] in affected]
    expected_preserved=[s['id'] for s in plan['steps'] if s['adapter_id'] not in affected]
    if (not affected or change['directly_changed']!=expected_direct or change['affected']!=expected_affected or
        change['preserved']!=expected_preserved or patch['affected']!=expected_affected or patch['preserved']!=expected_preserved):
        raise ValueError('source-change impact proof invalid')
    return affected
