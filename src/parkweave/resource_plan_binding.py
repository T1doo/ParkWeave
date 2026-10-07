"""Read-only version impact of engineering checkpoints and Case resource links.

This projection is never an Approval or an execution authorization. Historical
records stay intact, including the occupancy of a replaced combination.
Catalogue reads observe committed versions at statement start under the current
Read Committed connection default; their hashes are comparison evidence, not a
lock or a promise that an uncoordinated administrator cannot update the catalogue
between the last read and association commit. Repeatable Read/Serializable would
freeze this observation snapshot, not block the catalogue writer.
"""
from datetime import timedelta
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field
from . import controlled_plans as cp, preparation as prep, request_intents as intents
from . import resource_combinations as rc, resource_holds as rh
from .executor_receipts import bounded
from .store import Denied

SCOPE='SYNTHETIC_RESOURCE_PLAN_BINDING_ONLY'


class Confirm(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    combination_id: UUID=Field(strict=False)
    expected_preparation_revision: int=Field(ge=1)
    expected_link_revision: int=Field(ge=0)
    expected_comparison_sha256: str=Field(pattern='^[a-f0-9]{64}$')
    reason: str=Field(min_length=1,max_length=1000)


def association_snapshot(snapshot):
    """Impact evidence is metadata, never a resource member/version difference."""
    return {key:value for key,value in snapshot.items() if key!='binding_impact'}


def changes(before,after,path=''):
    """Return concrete changes, retaining unavailable historical fields as null."""
    before=cp._normal(before);after=cp._normal(after)
    if isinstance(before,dict) and isinstance(after,dict):
        return [item for key in sorted(set(before)|set(after)) for item in changes(before.get(key),after.get(key),path+'.'+key if path else key)]
    if before==after:return []
    labels={'goal':'原诉求','required_goals':'显式目标','request_intent':'诉求版本','service_catalog':'服务目录版本','template_sha256':'模板指纹','preparation_revision':'材料版本','preparation_sha256':'材料指纹','resource_link_revision':'资源关联版本','combination_state':'资源组合状态','members':'资源组合成员与时段','resource_rules':'资源规则版本','hold_sources':'占位来源与有效期','resource_grants':'当前资源授权','owner_grants':'当前经办人授权','catalog':'目录版本绑定','resource_catalog_decision':'目录决定有效性'}
    return [dict(path=path,field=labels.get(path.split('.')[0],path),before=before,after=after)]


def _combination(c,p,id):
    group=rc._group(c,p,id);holds=rc._members(c,p,id)
    rules=rc._scope_lock(c,p,holds)
    group=rc._group(c,p,id);holds=rc._members(c,p,id)
    if any(h['namespace']!='SYNTHETIC' for h in holds) or any(r['namespace']!='SYNTHETIC' or r['authority']!='LOCAL_AUTHORITY' for r in rules.values()):
        raise Denied('synthetic local resource required')
    return group,holds,rules


def _hold_authority(c,p,holds):
    """Observe current association permissions without making HOLD a read gate."""
    allowed=True
    for resource_id in sorted({h['resource_id'] for h in holds},key=str):
        try:rh._scope(c,p,resource_id,write=True)
        except Denied:allowed=False
    return allowed


def _issues(c,parent,group,holds,rules,now):
    issues=[]
    if group['state']!='CONFIRMED' or any(h['state']!='CONFIRMED' for h in holds):issues.append('RESOURCE_CANCELLED')
    if any(h['ends_at']<=now for h in holds):issues.append('RESOURCE_WINDOW_ENDED')
    for h in holds:
        r=rules[h['resource_id']]
        lo=h['starts_at']-timedelta(seconds=h['buffer_seconds']);hi=h['ends_at']+timedelta(seconds=h['buffer_seconds'])
        if not r['enabled'] or r['revision']!=h['resource_revision']:issues.append('RESOURCE_RULE_CHANGED')
        elif lo<r['open_from'] or hi>r['open_until'] or rh._peak(c,h['resource_id'],lo,hi,now)>r['capacity']:issues.append('RESOURCE_CONSTRAINT_CHANGED')
        # Confirmed occupancy survives its source hold TTL; expiry stays visible.
        if h['state']=='HELD' and h['expires_at']<=now:issues.append('RESOURCE_HOLD_EXPIRED')
    claim=c.execute('SELECT case_id,owner_id,park_id,org_id FROM resource_case_claims WHERE combination_id=%s',(group['id'],)).fetchone()
    if claim and tuple(claim[k] for k in ('case_id','owner_id','park_id','org_id'))!=(parent['case_id'],parent['owner_id'],parent['park_id'],parent['org_id']):issues.append('COMBINATION_BELONGS_TO_OTHER_CASE')
    return sorted(set(issues))


def _link_issues(parent,link):
    expected=(parent['id'],parent['run_id'],parent['case_id'],parent['owner_id'],parent['park_id'],parent['org_id'],parent['service_id'],parent['service_version'],parent['revision'],parent['review_sha256'])
    actual=tuple(link[k] for k in ('preparation_id','run_id','case_id','owner_id','park_id','org_id','service_id','service_version','preparation_revision','preparation_sha256'))
    return ['RESOURCE_PREPARATION_CHANGED'] if actual!=expected or parent['state']!='LOCAL_CONFIRMED' else []


def _catalog_copy(catalog):
    document=cp._normal(catalog)
    source=document.get('source') if isinstance(document,dict) else None
    return dict(document=document,source_revision=source.get('revision') if isinstance(source,dict) else None,sha256=cp._hash(document))


def _decision_ref(document,link_id,catalog_sha256):
    value=dict(link_id=str(link_id),comparison_sha256=document.get('comparison_sha256'),
      catalog_sha256=catalog_sha256,preparation_id=document.get('preparation_id'),
      case_id=document.get('case_id'),run_id=document.get('run_id'),
      preparation_revision=document.get('preparation_revision'),
      combination_id=document.get('after',{}).get('combination_id'))
    return dict(link_id=str(link_id),comparison_sha256=document.get('comparison_sha256'),sha256=cp._hash(cp._normal(value)))


def catalog_decision(c,parent,link):
    """Validate an immutable local directory copy; never claim a published Release.

    Historical impact rows already contain the complete P1 directory descriptor.
    Derive a reference for those rows without altering them. Rows from the legacy
    direct association route have no version-bound decision; retain that contract.
    """
    current=c.execute('SELECT service_id,version,source,namespace,qualification FROM preparation_catalog WHERE park_id=%s AND service_id=%s AND version=%s',(parent['park_id'],parent['service_id'],parent['service_version'])).fetchone()
    now_copy=_catalog_copy(current)
    document=link['snapshot'].get('binding_impact') if link else None
    result=dict(status='NOT_VERSION_BOUND',decision_ref=None,saved_catalog_sha256=None,
      current_catalog_sha256=now_copy['sha256'],source_revision=None,current_source_revision=now_copy['source_revision'],
      catalog_snapshot=None,issues=[],formal_release=False,approval='NOT_IMPLEMENTED',execution_enabled=False)
    if not document:return result
    expected=tuple(parent[k] for k in ('id','case_id','run_id','owner_id','park_id','org_id'))
    actual=tuple(link[k] for k in ('preparation_id','case_id','run_id','owner_id','park_id','org_id'))
    if actual!=expected:
        result.update(status='STALE',issues=['RESOURCE_CATALOG_DECISION_SCOPE_CHANGED'])
        return result
    saved=document.get('immutable_catalog')
    if saved is None:
        legacy=document.get('before',{}).get('source_snapshots',{}).get('P1',{}).get('service_catalog')
        saved=_catalog_copy(legacy)
    catalog=saved.get('document') if isinstance(saved,dict) else None
    computed=_catalog_copy(catalog)
    reference=_decision_ref(document,link['id'],computed['sha256'])
    stored_ref=document.get('decision_ref')
    valid_copy=bool(catalog and isinstance(catalog,dict) and catalog.get('namespace')=='SYNTHETIC' and isinstance(catalog.get('source'),dict) and catalog['source'].get('kind')=='SYNTHETIC' and catalog['source'].get('id') and catalog['source'].get('revision'))
    valid_evidence=bool(valid_copy and saved.get('sha256')==computed['sha256'] and saved.get('source_revision')==computed['source_revision'] and (stored_ref is None or cp._normal(stored_ref)==reference))
    # The local reference is scoped to the immutable association and its Case/Run.
    valid_evidence=valid_evidence and all(str(document.get(key))==str(link[key]) for key in ('preparation_id','case_id','run_id','preparation_revision')) and str(document.get('after',{}).get('link_id'))==str(link['id']) and str(document.get('after',{}).get('combination_id'))==str(link['combination_id'])
    current_match=valid_evidence and computed['sha256']==now_copy['sha256']
    result.update(status='CURRENT' if current_match else 'STALE',decision_ref=reference,
      saved_catalog_sha256=computed['sha256'],source_revision=computed['source_revision'],catalog_snapshot=computed)
    if not valid_evidence:result['issues'].append('RESOURCE_CATALOG_DECISION_EVIDENCE_REQUIRED')
    if not current_match:result['issues'].append('RESOURCE_CATALOG_DECISION_STALE')
    return result


def current_catalog_decision(c,parent):
    link=c.execute('SELECT * FROM case_resource_links WHERE case_id=%s AND owner_id=%s AND park_id=%s AND org_id=%s ORDER BY revision DESC LIMIT 1',(parent['case_id'],parent['owner_id'],parent['park_id'],parent['org_id'])).fetchone()
    return catalog_decision(c,parent,link)


def impact_issues(c,parent,document,group,holds,rules,now):
    """Saved confirmation is evidence; compare its sources without rewriting it."""
    if not document:return []
    issues=[]
    p1=cp.binding_p1(c,parent,_snapshot(parent,None,None,[]))
    if cp._normal(document['before']['source_snapshots']['P1'])!=p1:issues.append('RESOURCE_BINDING_SOURCE_CHANGED')
    p2=cp.binding_p2(c,parent,{},holds,rules)
    if cp._normal(document['after']['resource_rules'])!=p2['resource_rules']:issues.append('RESOURCE_RULE_CHANGED')
    if cp._normal(document['after']['resource_grants'])!=p2['resource_grants']:issues.append('CURRENT_RESOURCE_AUTHORITY_REQUIRED')
    if cp._normal(document['after']['combination'])!=cp._normal(rc._view(group,holds,now)):issues.append('RESOURCE_COMBINATION_SOURCE_CHANGED')
    if issues and 'RESOURCE_BINDING_SOURCE_CHANGED' not in issues:issues.append('RESOURCE_BINDING_SOURCE_CHANGED')
    return issues


def _snapshot(parent,link,group,holds):
    snap=dict(preparation_id=str(parent['id']),case_id=str(parent['case_id']),run_id=str(parent['run_id']),service_id=parent['service_id'],service_version=parent['service_version'],preparation_revision=parent['revision'],preparation_sha256=parent['review_sha256'])
    if link:snap.update(resource_link_id=str(link['id']),resource_link_revision=link['revision'],combination_id=str(link['combination_id']))
    if group:snap.update(combination_state=group['state'],members=[{k:str(h[k]) for k in ('id','resource_id','resource_revision','starts_at','ends_at','buffer_seconds','quantity','state')} for h in holds])
    return snap


@bounded
def read(store,token,id,candidate_combination_id=None):
    with store.connect() as c:
        c.execute('SET TRANSACTION READ ONLY')
        c.execute("SET LOCAL lock_timeout='3s'")
        p=store.auth(c,token,lock=True)
        if p['role']!='enterprise_operator':raise Denied('own resource plan binding required')
        prep.grant(store,c,p,'PREPARE')
        parent=c.execute('SELECT * FROM preparations WHERE id=%s AND owner_id=%s AND park_id=%s AND org_id=%s',(id,p['id'],p['park_id'],p['org_id'])).fetchone()
        if not parent or parent['namespace']!='SYNTHETIC':raise Denied('own synthetic preparation required')
        run=store.scoped_run(c,p,parent['run_id'])
        if not c.execute('SELECT 1 FROM cases WHERE id=%s AND run_id=%s',(parent['case_id'],run['id'])).fetchone():raise Denied('Case Run binding unavailable')
        return proposal(store,c,p,parent,candidate_combination_id)


def proposal(store,c,p,parent,candidate_combination_id=None,comparison_plan=None):
    """One connection's current comparison; no mutation or hidden revalidation."""
    id=parent['id']
    plan=c.execute('SELECT * FROM controlled_plans WHERE preparation_id=%s',(id,)).fetchone()
    links=c.execute('SELECT * FROM case_resource_links WHERE case_id=%s AND owner_id=%s AND park_id=%s AND org_id=%s ORDER BY revision',(parent['case_id'],p['id'],p['park_id'],p['org_id'])).fetchall()
    groups={gid:_combination(c,p,gid) for gid in sorted({link['combination_id'] for link in links}|({candidate_combination_id} if candidate_combination_id else set()),key=str)}
    hold_authority={gid:_hold_authority(c,p,hs) for gid,(_,hs,_) in groups.items()}
    owner_execute=True
    try:store.check_capability(c,p,'EXECUTE')
    except Denied:owner_execute=False
    now=rh._now(c);link=links[-1] if links else None
    group,holds,rules=groups[link['combination_id']] if link else (None,[],{})
    snap=_snapshot(parent,link,group,holds)
    snap['resource_catalog_decision']=catalog_decision(c,parent,link) if link else None
    snapshots={'P1':cp.binding_p1(c,parent,snap),'P2':cp.binding_p2(c,parent,snap,holds,rules)}
    issues={'P1':[],'P2':[]}
    items=prep.latest(c,id)
    if parent['state']!='LOCAL_CONFIRMED' or {i['slot'] for i in items}!=set(prep.SLOTS) or prep.snapshot(parent,items)!=parent['review_sha256']:issues['P1'].append('CURRENT_MATERIAL_CONFIRMATION_REQUIRED')
    store.lock_principal(c,parent['reviewer_id'])
    reviewer=c.execute("SELECT p.* FROM principals p WHERE id=%s AND park_id=%s AND org_id=%s AND role='park_specialist' AND active",(parent['reviewer_id'],p['park_id'],p['org_id'])).fetchone()
    if reviewer:
        try:prep.grant(store,c,reviewer,'REVIEW_ASSIGNED')
        except Denied:reviewer=None
    if not reviewer:issues['P1'].append('CURRENT_REVIEWER_AUTHORITY_REQUIRED')
    if parent.get('request_intent') and intents.state(parent)!='SUPPORTED_LOCAL':issues['P1'].append('REQUEST_GOAL_COVERAGE_REQUIRED')
    if not cp.binding_catalog_known(snapshots['P1']['service_catalog']):issues['P1'].append('CURRENT_SERVICE_CATALOG_REQUIRED')
    if not link:issues['P2'].append('CURRENT_CASE_RESOURCE_LINK_REQUIRED')
    else:
        issues['P2']+=_link_issues(parent,link)+_issues(c,parent,group,holds,rules,now)+snap['resource_catalog_decision']['issues']
        if not hold_authority[group['id']]:issues['P2'].append('CURRENT_RESOURCE_AUTHORITY_REQUIRED')
        claim=c.execute('SELECT 1 FROM resource_case_claims WHERE combination_id=%s AND case_id=%s AND owner_id=%s AND park_id=%s AND org_id=%s',(group['id'],parent['case_id'],p['id'],p['park_id'],p['org_id'])).fetchone()
        if not claim:issues['P2'].append('CURRENT_CASE_RESOURCE_CLAIM_REQUIRED')
    checkpoints={};prior=True
    for index,step in enumerate(('P1','P2'),1):
        checked=plan['checked'].get(step) if plan else None
        delta=changes(checked['snapshot'] if checked else {},snapshots[step])
        current=bool(checked and checked['sha256']==cp._hash(snapshots[step]) and not issues[step] and prior and (plan['invalidated_from'] is None or index<plan['invalidated_from']) and plan['template_sha256']==cp.TEMPLATE_SHA)
        checkpoints[step]=dict(state='CURRENT' if current else 'NEEDS_RECHECK' if checked else 'PENDING',checked_source_sha256=checked['sha256'] if checked else None,current_source_sha256=cp._hash(snapshots[step]),changes=delta,issues=sorted(set(issues[step])),checked_snapshot=checked['snapshot'] if checked else None,current_snapshot=snapshots[step],execution_enabled=False)
        prior=current
    history=[]
    for old in links:
        g,hs,rs=groups[old['combination_id']];live=rc._view(g,hs,now)
        decision=catalog_decision(c,parent,old)
        why=_link_issues(parent,old)+_issues(c,parent,g,hs,rs,now)+impact_issues(c,parent,old['snapshot'].get('binding_impact'),g,hs,rs,now)+decision['issues']
        if not hold_authority[g['id']]:why.append('CURRENT_RESOURCE_AUTHORITY_REQUIRED')
        is_latest=old['id']==link['id']
        history.append(dict(revision=old['revision'],record=old,catalog_decision=decision,state='CURRENT_BINDING_RECORD' if is_latest and not why else 'NEEDS_RECHECK' if is_latest else 'HISTORICAL',issues=sorted(set(why)),binding_impact=old['snapshot'].get('binding_impact'),changes=changes(association_snapshot(old['snapshot']),live)+changes({k:old[k] for k in ('preparation_revision','preparation_sha256','service_id','service_version')},{'preparation_revision':parent['revision'],'preparation_sha256':parent['review_sha256'],'service_id':parent['service_id'],'service_version':parent['service_version']}),combination=live,execution_enabled=False))
        if old['snapshot'].get('binding_impact'):history[-1]['source_status']='NEEDS_RECHECK' if why else 'CURRENT'
    candidate=None
    if candidate_combination_id:
        g,hs,rs=groups[candidate_combination_id];live=rc._view(g,hs,now)
        proposed=cp.binding_p2(c,parent,_snapshot(parent,link,g,hs),hs,rs)
        prior_catalog=snap['resource_catalog_decision']['catalog_snapshot']['document'] if link and snap['resource_catalog_decision']['catalog_snapshot'] else None
        candidate_issues=_issues(c,parent,g,hs,rs,now)
        if not hold_authority[g['id']]:candidate_issues.append('RESOURCE_HOLD_PERMISSION_REQUIRED')
        if not owner_execute:candidate_issues.append('OWNER_EXECUTE_REQUIRED')
        candidate=dict(combination=live,resource_rules=proposed['resource_rules'],resource_grants=proposed['resource_grants'],changes=changes({'combination':rc._view(group,holds,now) if group else None,'resource_rules':snapshots['P2']['resource_rules'],'resource_grants':snapshots['P2']['resource_grants'],'catalog':prior_catalog},{'combination':live,'resource_rules':proposed['resource_rules'],'resource_grants':proposed['resource_grants'],'catalog':snapshots['P1']['service_catalog']}),issues=sorted(set(candidate_issues)),explicit_association_required=not link or link['combination_id']!=g['id'] or bool(_link_issues(parent,link)) or snap['resource_catalog_decision']['status']=='STALE',original_plan_recheck_required=True,old_occupancy_released=False,execution_enabled=False)
    grants=dict(READ=True,PREPARE=True,EXECUTE=owner_execute,resources=snapshots['P2']['resource_grants'])
    result=dict(scope=SCOPE,preparation_id=id,case_id=parent['case_id'],run_id=parent['run_id'],preparation_revision=parent['revision'],approval='NOT_IMPLEMENTED',engineering_check_only=True,execution_enabled=False,business_writes=False,authorization_writes=False,new_grants=False,automatic_execution=False,current=dict(catalog_decision=snap['resource_catalog_decision'],snapshot_sha256=cp._hash(snapshots),resource_rules=snapshots['P2']['resource_rules'],goal=parent['goal'],required_goals=intents.view(parent)['required_goals'],request_intent=intents.view(parent),service=snapshots['P1']['service_catalog'],template=dict(sha256=cp.TEMPLATE_SHA,version=cp.TEMPLATE['version']),plan=dict(id=plan['id'],revision=plan['revision'],template_sha256=plan['template_sha256'],invalidated_from=plan['invalidated_from']) if plan else None,preparation=dict(revision=parent['revision'],state=parent['state'],sha256=parent['review_sha256']),resource_link=history[-1] if history else None,grants=grants),checkpoints=checkpoints,history=history,candidate=candidate,association_blockers=(['OWNER_EXECUTE_REQUIRED'] if not owner_execute else [])+(['RESOURCE_HOLD_PERMISSION_REQUIRED'] if link and not hold_authority[link['combination_id']] else []),required_rechecks=list(dict.fromkeys(([s for s in ('P1','P2') if checkpoints[s]['state']!='CURRENT'])+(['P3','P4'] if any(checkpoints[s]['state']!='CURRENT' for s in ('P1','P2')) else [])+(['EXPLICIT_RESOURCE_ASSOCIATION','P2','P3','P4'] if candidate and candidate['explicit_association_required'] else []))),server_time=now,external_acceptance='NOT_SUBMITTED',offline_fulfillment='NO_EVIDENCE',case_goal_completed=False)

    result['comparison']=None
    result['impact_history']=[dict(link_id=item['record']['id'],revision=item['revision'],state=item['state'],source_status=item['source_status'],document=item['binding_impact']) for item in history if item['binding_impact']]
    if candidate:
        document=_comparison_document(c,p,parent,comparison_plan if comparison_plan is not None else plan,link,groups,snapshots,checkpoints,candidate,now)
        blockers=list(candidate['issues'])+list(checkpoints['P1']['issues'])
        if plan and checkpoints['P1']['state']!='CURRENT':blockers.append('CURRENT_P1_CHECK_REQUIRED')
        if parent['state']!='LOCAL_CONFIRMED':blockers.append('CURRENT_MATERIAL_CONFIRMATION_REQUIRED')
        if link and link['combination_id']==candidate_combination_id and link['preparation_revision']==parent['revision'] and snap['resource_catalog_decision']['status']!='STALE':blockers.append('CURRENT_CASE_ASSOCIATION_ALREADY_RECORDED')
        if len(links)>=64:blockers.append('CASE_RESOURCE_LINK_HISTORY_LIMIT_REACHED')
        comparison=dict(sha256=cp._hash(document),preparation_revision=parent['revision'],link_revision=link['revision'] if link else 0,can_confirm=not blockers,blockers=sorted(set(blockers)))
        candidate['comparison']=comparison
        result['comparison']=comparison
    return result


def _comparison_document(c,p,parent,plan,link,groups,snapshots,checkpoints,candidate,now):
    """Hash stable version facts and time-derived states, never observation time."""
    def resource_version(group_id):
        if group_id is None:return None
        group,holds,rules=groups[group_id]
        claim=c.execute('SELECT case_id,owner_id,park_id,org_id FROM resource_case_claims WHERE combination_id=%s',(group_id,)).fetchone()
        current_claim=bool(claim and tuple(claim[k] for k in ('case_id','owner_id','park_id','org_id'))==(parent['case_id'],parent['owner_id'],parent['park_id'],parent['org_id']))
        return dict(group=group,holds=holds,rules=[rules[key] for key in sorted(rules,key=str)],
          grants=cp.binding_p2(c,parent,{},holds,rules)['resource_grants'],
          claim=dict(recorded=bool(claim),belongs_to_current_case=current_claim),
          occupied_peaks=[dict(resource_id=h['resource_id'],peak=rh._peak(c,h['resource_id'],h['starts_at']-timedelta(seconds=h['buffer_seconds']),h['ends_at']+timedelta(seconds=h['buffer_seconds']),now)) for h in holds])
    original=dict(link) if link else None
    if original:original['snapshot']=association_snapshot(original['snapshot'])
    plan_version={key:plan[key] for key in ('id','revision','template_sha256','checked','invalidated_from')} if plan else None
    return cp._normal(dict(scope=SCOPE,preparation={key:parent[key] for key in ('id','case_id','run_id','owner_id','park_id','org_id','reviewer_id','namespace','goal','request_intent','state','revision','review_sha256','service_id','service_version')},
      material_snapshot_sha256=prep.snapshot(parent,prep.latest(c,parent['id'])),
      sources=snapshots,plan=plan_version,original_link=original,
      original_resources=resource_version(link['combination_id']) if link else None,
      candidate_resources=resource_version(candidate['combination']['id']),
      checkpoint_states={key:dict(state=value['state'],issues=value['issues'],source_sha256=value['current_source_sha256']) for key,value in checkpoints.items()},
      candidate_issues=candidate['issues']))


def impact(projection,new_link,comparison_sha256,reason):
    """Immutable explicitly confirmed comparison evidence stored with the link."""
    candidate=projection['candidate'];current=projection['current']
    document=dict(scope=SCOPE,comparison_sha256=comparison_sha256,
      preparation_id=projection['preparation_id'],case_id=projection['case_id'],run_id=projection['run_id'],
      preparation_revision=projection['preparation_revision'],reason=reason,
      before=dict(link_id=current['resource_link']['record']['id'] if current['resource_link'] else None,
        link_revision=projection['comparison']['link_revision'],combination_id=current['resource_link']['combination']['id'] if current['resource_link'] else None,
        source_snapshots={step:value['current_snapshot'] for step,value in projection['checkpoints'].items()},catalog_decision=current['catalog_decision'],plan=current['plan']),
      after=dict(link_id=new_link['id'],link_revision=new_link['revision'],combination_id=candidate['combination']['id'],
        combination=candidate['combination'],resource_rules=candidate['resource_rules'],resource_grants=candidate['resource_grants']),
      changes=candidate['changes'],required_rechecks=['P2','P3','P4'],
      approval='NOT_IMPLEMENTED',formal_approval='NOT_IMPLEMENTED',engineering_check_only=True,execution_enabled=False,
      old_occupancy_released=False,new_grants=False)
    document['immutable_catalog']=_catalog_copy(projection['checkpoints']['P1']['current_snapshot']['service_catalog'])
    document['decision_ref']=_decision_ref(document,new_link['id'],document['immutable_catalog']['sha256'])
    return cp._normal(document)
