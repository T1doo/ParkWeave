"""Explicit owned-fixture template adoption; original business effects never roll back."""
from copy import deepcopy
from contextlib import ExitStack, contextmanager
import sqlite3
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import preparation as prep, service_case_steps as plans
from .template_candidate import TemplateDraft, Scope, Command, sha
from .template_consumer import canonical, normal
from .store import Conflict, Denied

SCOPE = 'OWNED_SYNTHETIC_TEMPLATE_MIGRATION_V1'
ACTION = 'TEMPLATE_UPGRADE'
FLAGS = dict(scope=SCOPE, migration_performed=True, automatic_execution=False,
             automatically_replayed=False, new_grants=False, business_publication=False,
             formal_review=False, case_goal_completed=False)


class Apply(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)
    expected_instance_id: UUID = Field(strict=False)
    target_release_id: UUID = Field(strict=False)
    expected_target_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    expected_check_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    expected_choice_revision: int = Field(ge=1, le=64)
    expected_choice_event_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    expected_plan_id: UUID = Field(strict=False)
    expected_plan_revision: int = Field(ge=1, le=63)
    expected_preparation_revision: int = Field(ge=1, le=64)
    expected_source_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    reason: str = Field(min_length=1, max_length=1000)


class NoteCarryApply(Apply):
    expected_note_carry_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    confirm_note_carry: Literal[True]

    @field_validator('confirm_note_carry', mode='before')
    @classmethod
    def explicit_note_confirmation(cls, value):
        if type(value) is not bool or value is not True:
            raise ValueError('explicit true manual note carry confirmation required')
        return value


class StructureApply(Apply):
    expected_structure_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    confirm_structure_change: Literal[True]

    @field_validator('confirm_structure_change', mode='before')
    @classmethod
    def explicit_confirmation(cls, value):
        if type(value) is not bool or value is not True:
            raise ValueError('explicit true structure confirmation required')
        return value


def parse_apply_request(patch):
    """Historical nine-key requests and explicitly confirmed structure requests differ."""
    model = NoteCarryApply if 'note_carry' in patch else StructureApply if 'structure_change' in patch else Apply
    return model.model_validate(patch['request'])


@contextmanager
def source_connection(engine):
    """A query-only snapshot: hold its source read lease through the PG commit."""
    c=sqlite3.connect(engine.repository.path,timeout=3);c.row_factory=sqlite3.Row
    try:
        c.execute('PRAGMA query_only=ON');c.execute('BEGIN')
        yield c
        c.commit()
    except sqlite3.OperationalError as error:
        c.rollback();raise Conflict('template source lease unavailable; recover original key') from error
    except BaseException:
        c.rollback();raise
    finally:c.close()


def fingerprint(instance_id, data):
    return sha(dict(instance_id=str(instance_id), action=ACTION, **data.model_dump(mode='json')))


def release_proof(engine, t, release_id, expected_sha, *, current=False):
    """Check original independent event columns/fingerprints, not a rehashed row alone."""
    row=t.execute('SELECT * FROM template_releases WHERE id=?',(str(release_id),)).fetchone()
    if not row: raise Conflict('original template release missing')
    import json
    payload=json.loads(row['payload'])
    try:
        definition=TemplateDraft.model_validate(payload['definition'])
        scope=Scope.model_validate(payload['scope'])
        if (sha(payload)!=row['payload_sha'] or row['payload_sha']!=expected_sha or
            payload['release_id']!=str(release_id) or payload['definition_sha256']!=sha(payload['definition']) or
            row['scope']!=canonical(scope.model_dump()) or payload['business_publication'] is not False): raise ValueError()
        rows=t.execute('SELECT * FROM template_events WHERE scope=? ORDER BY revision',(row['scope'],)).fetchall()
        events=[]
        for revision,eventrow in enumerate(rows,1):
            event=json.loads(eventrow['payload'])
            if (eventrow['revision']!=revision or event['revision']!=revision or eventrow['actor']!=event['actor_id'] or
                eventrow['action']!=event['action'] or event['scope']!=scope.model_dump()): raise ValueError()
            events.append((eventrow,event))
        published=[(r,e) for r,e in events if e['action']=='CANDIDATE_PUBLISH' and e['release_id']==str(release_id)]
        if len(published)!=1: raise ValueError()
        publishrow,publish=published[0]
        review=payload['review']
        reviewrow,reviewevent=events[review['revision']-1]
        if (reviewevent['action']!='REVIEW' or reviewrow['actor']!=review['reviewer_id'] or
            reviewevent['definition_sha256']!=payload['definition_sha256'] or
            reviewevent['reason']!=review['reason'] or reviewevent['content_version']!=payload['content_version'] or
            review['definition_sha256']!=payload['definition_sha256'] or review['registry_sha256']!=payload['registry_sha256'] or
            review['contract_sha256']!=payload['contract_sha256'] or review['action']!='REVIEW' or
            publish['revision']!=review['revision']+1 or publish['actor_id']!=payload['publisher_id'] or
            publish['definition_sha256']!=payload['definition_sha256'] or publish['content_version']!=payload['content_version'] or
            len({payload['author_id'],review['reviewer_id'],payload['publisher_id']})!=3): raise ValueError()
        drafts=[(r,e) for r,e in events[:review['revision']] if e['action']=='SAVE_DRAFT' and e['content_version']==payload['content_version']]
        if len(drafts)!=1: raise ValueError()
        draftrow,draft=drafts[0]
        if draft['actor_id']!=payload['author_id'] or draft['definition_sha256']!=payload['definition_sha256']: raise ValueError()
        previous=events[draft['revision']-2][1]['definition_sha256'] if draft['revision']>1 else None
        requests=[(draftrow,Command(action='SAVE_DRAFT',expected_revision=draft['revision']-1,expected_definition_sha256=previous,reason=draft['reason'],draft=definition)),
            (reviewrow,Command(action='REVIEW',expected_revision=review['revision']-1,expected_definition_sha256=payload['definition_sha256'],reason=reviewevent['reason'])),
            (publishrow,Command(action='CANDIDATE_PUBLISH',expected_revision=publish['revision']-1,expected_definition_sha256=payload['definition_sha256'],reason=publish['reason'],validity=payload['validity']))]
        for r,request in requests:
            if r['fp']!=sha(dict(scope=scope.model_dump(),**request.model_dump(mode='json'))): raise ValueError()
        source=definition.source.model_dump(mode='json')
        recorded=t.execute('SELECT payload,payload_sha FROM template_sources WHERE park_id=? AND source_id=? AND source_revision=?',(scope.park_id,source['id'],source['revision'])).fetchone()
        if not recorded or json.loads(recorded['payload'])!=source or recorded['payload_sha']!=sha(source): raise ValueError()
    except (ValueError,TypeError,KeyError,IndexError): raise Conflict('original template release event proof invalid')
    if current:
        view=engine._available(t,row)
        head=engine._row(t,scope)
        if not view['candidate_available']: raise Denied('current effective template unavailable: '+view['availability_reason'])
        if (not head or head['current_release']!=str(release_id) or head['state']!='PUBLISHED' or
            head['definition_sha']!=payload['definition_sha256'] or json.loads(head['definition'])!=payload['definition'] or
            json.loads(head['review'])!=payload['review']): raise Conflict('current effective template head changed')
    return dict(release_id=str(release_id),release_sha256=expected_sha,snapshot=payload)


def _effective(instance,plan):
    migrated=plan.get('template_migration') if plan else None
    if migrated:return deepcopy(migrated['release'])
    binding=instance['binding']
    return dict(release_id=binding['release_id'],release_sha256=binding['release_sha256'],snapshot=deepcopy(binding['release_snapshot']))


def _compatible(old,new):
    return (new['content_version']>old['content_version'] and old['scope']==new['scope'] and
        all(old['definition'][k]==new['definition'][k] for k in ('service_id','service_version','parameter_schema','required_goals','steps')) and
        all(old[k]==new[k] for k in ('registry_sha256','contract_sha256')))


def structure_change(parent, plan, before, target):
    """Only strengthen template duties already declared and adopted by this Case.

    No Case goal, preview, step contract or original adoption is rewritten. The
    proof is rebuilt from those immutable inputs on every read and recovery.
    """
    old=before['snapshot'];new=target['snapshot']
    a=old['definition'];b=new['definition']
    if a['required_goals']==b['required_goals'] and a['steps']==b['steps']:
        return None
    from . import bounded_planning as planning, registered_dependencies as dependencies
    try:
        TemplateDraft.model_validate(a);TemplateDraft.model_validate(b)
        goals=a['required_goals'];declared=plan['required_goals']
        if (new['content_version']<=old['content_version'] or old['scope']!=new['scope'] or
            any(a[k]!=b[k] for k in ('service_id','service_version','parameter_schema')) or
            any(old[k]!=new[k] for k in ('registry_sha256','contract_sha256')) or
            b['required_goals'][:len(goals)]!=goals or len(b['required_goals'])<=len(goals) or
            plan.get('partial_adoption') is True or
            declared!=plan['binding']['request_intent']['required_goals'] or
            declared!=plan['adoption_preview']['required_goals'] or
            plan['goal_coverage']!=plan['adoption_preview']['goal_coverage'] or
            not set(b['required_goals'])<=set(declared) or
            any(step not in b['steps'] for step in a['steps'])):
            raise ValueError()
        steps={step['adapter_id']:step for step in plan['steps']}
        for template_step in b['steps']:
            case_step=steps[template_step['id']]
            if (type(case_step['adapter_revision']) is not int or type(case_step['contract']['revision']) is not int or
                case_step['adapter_revision']!=template_step['adapter_revision'] or
                case_step['depends_on']!=template_step['depends_on'] or
                case_step['contract']['id']!=template_step['id'] or
                case_step['contract']['revision']!=template_step['adapter_revision'] or
                case_step['contract']['depends_on']!=template_step['depends_on']):
                raise ValueError()
        added_goals=b['required_goals'][len(goals):]
        coverage={item['goal']:item for item in plan['goal_coverage']}
        for goal in b['required_goals']:
            compiled,_=planning.compile([goal])
            if coverage[goal]!=compiled[0] or compiled[0]['status']!='SUPPORTED_PREVIEW':raise ValueError()
        old_ids={step['id'] for step in a['steps']}
        added_steps=[step['id'] for step in b['steps'] if step['id'] not in old_ids]
        seeds=sorted(set(added_steps)|{planning.GOALS[goal] for goal in added_goals})
        affected=dependencies.closure(plan['steps'],seeds)
        if a['source']!=b['source']:affected=set(steps)
        binding=dict(preparation_id=str(parent['id']),case_id=str(parent['case_id']),run_id=str(parent['run_id']),
            plan_id=plan['id'],required_goals=declared,initial_request=plan['binding']['request_intent'],
            initial_adopt_fingerprint=plan['events'][0]['fingerprint'],adoption_preview=plan['adoption_preview'],
            goal_coverage=plan['goal_coverage'],steps=[dict(id=s['id'],adapter_id=s['adapter_id'],adapter=s['adapter'],
                adapter_revision=s['adapter_revision'],depends_on=s['depends_on'],contract=s['contract']) for s in plan['steps']])
        return dict(version=1,kind='REGISTERED_GOAL_STRENGTHENING',before_release_id=before['release_id'],
            before_release_sha256=before['release_sha256'],target_release_id=target['release_id'],target_release_sha256=target['release_sha256'],
            before_definition_sha256=old['definition_sha256'],target_definition_sha256=new['definition_sha256'],
            added_goals=added_goals,added_template_steps=added_steps,seed_adapters=seeds,
            affected_step_ids=[s['id'] for s in plan['steps'] if s['adapter_id'] in affected],
            preserved_step_ids=[s['id'] for s in plan['steps'] if s['adapter_id'] not in affected],
            case_binding_sha256=sha(normal(binding)))
    except (ValueError,TypeError,KeyError,IndexError,AttributeError):
        raise Conflict('UPGRADE_SCOPE_UNSUPPORTED: original Case goal and registered closure proof required')


def validate_plan(parent,plan):
    """Original-request anchored proof shared by reads, recovery and original gates."""
    prior=None;effective=None
    events=[e for e in plan['events'] if e['action']==ACTION]
    try:
        for event in events:
            patch=event['template_upgrade'];request=parse_apply_request(patch)
            before=patch['previous_release'];target=patch['target_release'];origin=patch['origin_binding']
            structural='structure_change' in patch
            carried='note_carry' in patch
            if structural and carried:raise ValueError()
            keys={'request','origin_binding','previous_release','target_release','check','choice','affected','preserved','source_changed'}
            if set(patch)!=(keys|{'note_carry'} if carried else keys|{'structure_change'} if structural else keys):raise ValueError()
            scope=patch['check']['scope'];choice=patch['choice'];choice_body={k:v for k,v in choice.items() if k!='event_sha256'}
            initial_key=plan['events'][0]['request_key']
            if initial_key.startswith('tc:') and initial_key!='tc:'+scope['instance_id']+':ADOPT_PLAN':raise ValueError()
            for release in (before,target):
                snapshot=release['snapshot'];TemplateDraft.model_validate(snapshot['definition'])
                if (snapshot['release_id']!=release['release_id'] or sha(snapshot)!=release['release_sha256'] or
                    snapshot['definition_sha256']!=sha(snapshot['definition'])): raise ValueError()
            if (origin['release_id']!=patch['check']['original_release_id'] or
                origin['release_sha256']!=patch['check']['original_release_sha256'] or
                origin['definition_sha256']!=patch['check']['original_definition_sha256'] or
                origin['release_snapshot']['definition_sha256']!=origin['definition_sha256'] or
                any(origin[k]!=scope[k] for k in ('actor_id','park_id','org_id','database_name'))):raise ValueError()
            if prior is None:
                if (before['release_id']!=origin['release_id'] or before['release_sha256']!=origin['release_sha256'] or
                    before['snapshot']!=origin['release_snapshot']): raise ValueError()
            elif before!=prior:raise ValueError()
            changed=before['snapshot']['definition']['source']!=target['snapshot']['definition']['source']
            ids=[s['id'] for s in plan['steps']]
            proof=structure_change(parent,plan,before,target)
            if structural:
                if (proof is None or sha(patch['structure_change'])!=sha(proof) or
                    request.expected_structure_sha256!=sha(patch['structure_change']) or request.confirm_structure_change is not True):raise ValueError()
            elif proof is not None or not _compatible(before['snapshot'],target['snapshot']):raise ValueError()
            affected=proof['affected_step_ids'] if proof else ids if changed else []
            preserved=[id for id in ids if id not in affected]
            if (patch['source_changed'] is not changed or
                patch['affected']!=affected or patch['preserved']!=preserved or
                event['actor_id']!=parent['owner_id'] or event['step_id'] is not None or event['sources'] is not None or
                event['source_sha256'] is not None or event['coordination_only'] is not True or
                event['reason']!=request.reason or event['revision']!=request.expected_plan_revision+1 or
                plan['id']!=str(request.expected_plan_id) or str(request.expected_instance_id)!=scope['instance_id'] or
                scope['actor_id']!=parent['owner_id'] or scope['case_id']!=str(parent['case_id']) or scope['preparation_id']!=str(parent['id']) or
                request.expected_source_sha256!=patch['check']['case_state_sha256'] or request.expected_check_sha256!=sha(patch['check']) or
                request.expected_target_sha256!=target['release_sha256'] or str(request.target_release_id)!=target['release_id'] or
                patch['check']['target_release_id']!=target['release_id'] or patch['check']['target_release_sha256']!=target['release_sha256'] or
                choice['choice'] not in patch['check']['allowed_choices'] or patch['check']['classification'] not in ('COMPATIBLE','NEEDS_RECHECK') or
                event['fingerprint']!=fingerprint(scope['instance_id'],request) or
                choice['event_sha256']!=sha(choice_body) or choice['event_sha256']!=request.expected_choice_event_sha256 or
                choice['revision']!=request.expected_choice_revision or choice['check_sha256']!=request.expected_check_sha256 or
                choice['check']!=patch['check'] or choice['scope']!=scope or choice['choice'] not in ('REQUEST_RECHECK','ACK_COMPATIBLE')): raise ValueError()
            from .template_upgrade import Selection
            selection=Selection(target_release_id=choice['check']['target_release_id'],expected_target_sha256=choice['check']['target_release_sha256'],expected_check_sha256=choice['check_sha256'],expected_revision=choice['revision']-1,choice=choice['choice'],reason=choice['reason'])
            if choice['request_sha256']!=sha(dict(instance_id=scope['instance_id'],**selection.model_dump(mode='json'))):raise ValueError()
            from . import note_template_carry
            prior_notes=note_template_carry.notes_before_v1(plan,event['revision'])
            if carried:
                if not isinstance(request,NoteCarryApply) or structural:raise ValueError()
                note_template_carry.validate(parent,plan,event,before,target,patch['check'],choice,affected,preserved)
            elif prior_notes:raise ValueError('historical annotation requires explicit carry proof')
            if effective and origin!=effective['origin_binding']:raise ValueError()
            effective=dict(instance_id=scope['instance_id'],origin_binding=origin,release=target,last_event_id=event['id'])
            prior=target
        if effective!=plan.get('template_migration'): raise ValueError()
    except (ValueError,TypeError,KeyError,AttributeError):raise Conflict('template migration plan proof invalid')
    return effective


def add_sources(parent,plan,sources):
    effective=validate_plan(parent,plan)
    if not effective:return
    original=effective['origin_binding']['release_snapshot']['definition']['source']
    source=effective['release']['snapshot']['definition']['source']
    if source!=original:
        for step in plan['steps']:sources[step['adapter_id']]['adopted_template_source']=deepcopy(source)
    for step in plan['steps']:
        # Append-only structure proofs survive later description/source releases.
        # Only this original step's affected events enter its source identity.
        proofs=[sha(e['template_upgrade']['structure_change']) for e in plan['events']
            if e['action']==ACTION and 'structure_change' in e['template_upgrade'] and step['id'] in e['template_upgrade']['affected']]
        if proofs:sources[step['adapter_id']]['adopted_template_structures']=proofs



def availability(store,parent,plan):
    """Current source validity is a read projection, never an execution lease/write."""
    effective=validate_plan(parent,plan)
    if not effective:return None
    checker=getattr(store,'_isolated_template_migration_checker',None)
    result=dict(scope=SCOPE,effective_release_id=effective['release']['release_id'],
        effective_release_sha256=effective['release']['release_sha256'],current=False,reasons=[],
        historical_binding_preserved=True,read_only=True,execution_lease_registered=False)
    if checker is None or checker.consumer.store is not store:
        result['reasons']=['CURRENT_TEMPLATE_AUTHORITY_NOT_MOUNTED']
        return result
    try:
        with checker.engine.lock,source_connection(checker.engine) as t:
            release=effective['release']
            if release_proof(checker.engine,t,release['release_id'],release['release_sha256'],current=True)!=release:
                raise Conflict('effective template snapshot changed')
            result['current']=True
    except (Denied,Conflict):result['reasons']=['CURRENT_TEMPLATE_SOURCE_UNAVAILABLE']
    return result


class SourceLease:
    """One existing connection owns the source read lease until its actual commit."""
    def __init__(self,checker,release):
        self.checker=checker;self.release=deepcopy(release);self.stack=ExitStack()
        try:
            self.stack.enter_context(checker.engine.lock)
            self.t=self.stack.enter_context(source_connection(checker.engine))
            self.recheck()
        except BaseException:
            self.stack.close();raise

    def recheck(self):
        r=self.release
        if release_proof(self.checker.engine,self.t,r['release_id'],r['release_sha256'],current=True)!=r:
            raise Conflict('effective template snapshot changed')

    def close(self):
        self.stack.close()


def live_guard(store,c,parent,plan):
    effective=validate_plan(parent,plan)
    if not effective:return
    checker=getattr(store,'_isolated_template_migration_checker',None)
    if checker is None or checker.consumer.store is not store:raise Denied('current isolated template migration authority is not mounted')
    from .store import _AccessConnection
    if not isinstance(c,_AccessConnection) or c.autocommit:raise Denied('template migration requires original guarded transaction')
    database=checker.consumer.validate_fixture()
    instance=checker.consumer._instance(dict(id=parent['owner_id'],park_id=parent['park_id'],org_id=parent['org_id']),database,effective['instance_id'])
    if instance['binding']!=effective['origin_binding']:raise Conflict('original immutable consumer binding changed')
    key=(effective['instance_id'],effective['release']['release_id'])
    leases=getattr(c,'_template_source_leases',{})
    if key not in leases:
        leases[key]=SourceLease(checker,effective['release'])
        c._template_source_leases=leases
    else:leases[key].recheck()


check_live=live_guard


def application(checker,context,check,events,t):
    c,_,parent,case,stages,instance,_=context
    plan=parent.get('service_case_plan');blockers=[]
    if case['state'] in ('CANCELLED','RECONCILING'):blockers.append('CASE_'+case['state'])
    local=c.execute('SELECT state FROM case_local_lifecycles WHERE preparation_id=%s',(parent['id'],)).fetchone()
    if local and local['state']=='LOCAL_RECORD_CLOSED':blockers.append('LOCAL_RECORD_CLOSED')
    run=c.execute('SELECT namespace,state,success_scope FROM runs WHERE id=%s',(parent['run_id'],)).fetchone()
    operation=c.execute('SELECT action,state,receipt FROM operations WHERE run_id=%s',(parent['run_id'],)).fetchone()
    if (parent['namespace']!='SYNTHETIC' or case['source']!='SYNTHETIC' or not run or run['namespace']!='SYNTHETIC'):
        blockers.append('ORDINARY_SYNTHETIC_CASE_REQUIRED')
    if (not run or run['state']!='SUCCEEDED' or run['success_scope']!='LOCAL_CASE_CREATED' or not operation or
        operation['action']!='case.create' or operation['state']!='VERIFIED' or operation['receipt']!={'case_id':str(parent['case_id']),'source':'LOCAL_DATABASE','verified':True,'success_scope':'LOCAL_CASE_CREATED'}):
        blockers.append('VERIFIED_ORIGINAL_CASE_CREATION_REQUIRED')
    if not plan: blockers.append('PLAN_REQUIRED')
    if plan:plans._recovery_proofs(parent)
    if plan and plan.get('owner_amendments'):blockers.append('OWNER_NOTE_CONTROLLED_CARRY_REQUIRED_FOR_APPLICATION')
    effective=_effective(instance,plan)
    target=release_proof(checker.engine,t,check['target_release_id'],check['target_release_sha256'],current=True)
    release_proof(checker.engine,t,effective['release_id'],effective['release_sha256'])
    proof=None
    try:
        proof=structure_change(parent,plan,effective,target) if plan else None
        if proof is None and not _compatible(effective['snapshot'],target['snapshot']):blockers.append('UPGRADE_SCOPE_UNSUPPORTED')
    except Conflict:blockers.append('UPGRADE_SCOPE_UNSUPPORTED')
    changed=effective['snapshot']['definition']['source']!=target['snapshot']['definition']['source']
    ids=[s['id'] for s in plan['steps']] if plan else []
    if any(s['state']!='CONFIRMED' for s in stages):blockers.append('UNRESOLVED_CONSUMER_STAGE')
    if plan and plans._binding_issues(context[0],parent,plan,store=checker.consumer.store):blockers.append('CURRENT_PLAN_BINDING_REQUIRED')
    affected=proof['affected_step_ids'] if proof else ids if changed else []
    if proof:
        binding_issues,issues,_,_,states,_=plans._inspect(checker.consumer.store,c,parent,deepcopy(plan),observe=False,fresh_clock=True)
        if binding_issues or any(states[s['adapter_id']]!='VERIFIED' for s in plan['steps']):blockers.append('CURRENT_VERIFIED_CASE_PLAN_REQUIRED')
    if plan and any(s['id'] in affected and plans._manual_lock(plan,s) for s in plan['steps']):blockers.append('LOCK_CONFLICT')
    # Adoption must leave room for every affected original VERIFY, as well as
    # the existing reservation for explicit unlocks of preserved decisions.
    verification_events=len(affected)
    if plan and plan['revision']+1+verification_events+sum(bool(s.get('manual_lock')) for s in plan['steps'])>plans.LIMIT:blockers.append('PLAN_EVENT_LIMIT')
    choice=events[-1] if events else None
    if not choice or choice['choice'] not in ('REQUEST_RECHECK','ACK_COMPATIBLE') or choice['check_sha256']!=sha(check):blockers.append('CURRENT_EXPLICIT_CHOICE_REQUIRED')
    result=dict(eligible=not blockers,blockers=blockers,effective_release_id=effective['release_id'],plan_id=plan['id'] if plan else None,
        plan_revision=plan['revision'] if plan else 0,preparation_revision=parent['revision'],source_sha256=check['case_state_sha256'],
        affected=affected,preserved=[id for id in ids if id not in affected],
        structure_change=proof,structure_sha256=sha(proof) if proof else None,requires_structure_confirmation=proof is not None,
        choice_revision=choice['revision'] if choice else 0,
        choice_event_sha256=choice['event_sha256'] if choice else None)
    if plan and plan.get('owner_amendments'):
        from .note_template_carry import projection
        carried=projection(checker,context,check,events,t,result,effective,target)
        result.update(note_carry=carried,note_carry_sha256=carried['preview_sha256'],requires_note_carry_confirmation=True)
    return result


def apply(checker,token,instance_id,key,data):
    checker.consumer._key(key)
    if str(data.expected_instance_id)!=str(instance_id):raise Conflict('expected original instance changed')
    fp=fingerprint(instance_id,data)
    # Canonical original PG parent -> dispatch -> Case, then source lease. No lock upgrade.
    with checker._context(token,instance_id,business_write=True) as context:
        c,p,parent,case,stages,instance,scope=context
        prep.key_lock(c,p,'service-case-plan:'+key)
        plan=deepcopy(parent.get('service_case_plan'))
        if not plan:raise Conflict('adopted original plan required')
        plans._recovery_proofs(parent)
        old=plans._replay(c,p,parent,key,fp)
        if old:
            if old['action']!=ACTION:raise Conflict('original request action changed')
            return dict(**FLAGS,event=old,historical_only=True,effective_release_id=old['template_upgrade']['target_release']['release_id'])
        from .plan_source_conflicts import adoption_guard
        adoption_guard(c,parent,plan)
        # Note history binds the original complete step contracts. A migration
        # must not silently reinterpret that history or discard the owner body.
        if plan.get('owner_amendments') and not isinstance(data,NoteCarryApply):
            raise Conflict('owner coordination note requires controlled carry before template application')
        if isinstance(data,NoteCarryApply) and not plan.get('owner_amendments'):raise Conflict('current manual owner note required for carry')
        local=c.execute('SELECT state FROM case_local_lifecycles WHERE preparation_id=%s',(parent['id'],)).fetchone()
        if local and local['state']=='LOCAL_RECORD_CLOSED':raise Conflict('closed local Case cannot adopt template revision')
        with checker.engine.lock,source_connection(checker.engine) as t,checker.repository.connect() as journal:
            check=checker._check(context,data.target_release_id,data.expected_target_sha256,t)
            events=checker._history(journal,scope)
            projection=application(checker,context,check,events,t)
            carry=projection.get('note_carry') if isinstance(data,NoteCarryApply) else None
            eligible=carry['eligible'] if carry is not None else projection['eligible']
            if (not eligible or sha(check)!=data.expected_check_sha256 or
                projection['choice_revision']!=data.expected_choice_revision or projection['choice_event_sha256']!=data.expected_choice_event_sha256 or
                plan['id']!=str(data.expected_plan_id) or plan['revision']!=data.expected_plan_revision or
                parent['revision']!=data.expected_preparation_revision or check['case_state_sha256']!=data.expected_source_sha256):
                raise Conflict('template application check, choice, plan or source changed: '+','.join(projection['blockers']))
            if isinstance(data,NoteCarryApply) and (carry is None or not carry['proof'] or data.expected_note_carry_sha256!=carry['preview_sha256']):raise Conflict('fresh explicit manual note carry proof required')
            before=_effective(instance,plan)
            target=release_proof(checker.engine,t,data.target_release_id,data.expected_target_sha256,current=True)
            release_proof(checker.engine,t,before['release_id'],before['release_sha256'])
            proof=projection['structure_change']
            if proof is not None:
                if not isinstance(data,StructureApply):raise Conflict('explicit structure confirmation required; use apply-structure')
                if data.expected_structure_sha256!=sha(proof) or data.confirm_structure_change is not True:raise Conflict('structure confirmation proof changed')
            elif isinstance(data,StructureApply):raise Conflict('current structural change required')
            if isinstance(data,NoteCarryApply):
                if proof is not None:raise Conflict('manual annotation structure migration unsupported')
                final_check=checker._check(context,data.target_release_id,data.expected_target_sha256,t)
                final_projection=application(checker,context,final_check,events,t)
                final_carry=final_projection.get('note_carry')
                if (not final_carry or not final_carry['eligible'] or final_carry['proof']!=carry['proof'] or
                    final_carry['preview_sha256']!=data.expected_note_carry_sha256):raise Conflict('manual note carry source or authority changed before application')
            origin=deepcopy(instance['binding'])
            plan['revision']+=1
            event=plans._event(plan,p,key,fp,ACTION,data.reason)
            event['template_upgrade']=dict(request=data.model_dump(mode='json'),origin_binding=origin,previous_release=before,target_release=target,
                check=check,choice=events[-1],affected=projection['affected'],preserved=projection['preserved'],
                source_changed=before['snapshot']['definition']['source']!=target['snapshot']['definition']['source'])
            if proof is not None:event['template_upgrade']['structure_change']=proof
            if isinstance(data,NoteCarryApply):event['template_upgrade']['note_carry']=deepcopy(carry['proof'])
            plan['template_migration']=dict(instance_id=scope['instance_id'],origin_binding=origin,release=target,last_event_id=event['id'])
            for step in plan['steps']:
                if step['id'] in projection['affected'] and step.get('verified_sha256'):step['invalidated']=True
            plans._recovery_proofs({**parent,'service_case_plan':plan})
            # Register the adopted target on the original guarded PG connection.
            # Its lease is rechecked by actual commit, including expiry after UPDATE.
            live_guard(checker.consumer.store,c,parent,plan)
            # Recheck after all PG/source waits, and keep SQLite source lease through PG commit.
            checker.engine._enabled(t)
            release_proof(checker.engine,t,data.target_release_id,data.expected_target_sha256,current=True)
            checker.consumer.store.auth(c,token,lock=True)
            checker.consumer.store.check_capability(c,p,'EXECUTE')
            prep.grant(checker.consumer.store,c,p,'PREPARE')
            plans._save(c,parent,plan)
            c.commit()
            return dict(**FLAGS,event=event,historical_only=False,effective_release_id=target['release_id'])


def recover(checker,token,instance_id,key):
    checker.consumer._key(key)
    with checker._context(token,instance_id) as context:
        c,p,parent,_,_,instance,_=context
        prep.key_lock(c,p,'service-case-plan:'+key)
        plan=parent.get('service_case_plan')
        if plan:plans._recovery_proofs(parent)
        matches=[e for item in ([plan]+plan.get('history',[]) if plan else []) for e in item['events'] if e['actor_id']==p['id'] and e['request_key']==key]
        if matches and (len(matches)!=1 or matches[0]['action']!=ACTION or matches[0]['template_upgrade']['check']['scope']['instance_id']!=str(instance_id)):raise Conflict('original application key scope changed')
        if not matches:
            rows=c.execute("SELECT id FROM preparations WHERE jsonb_path_exists(service_case_plan,'$.** ? (@.actor_id == $actor && @.request_key == $key)',%s)",(plans.Jsonb(dict(actor=p['id'],key=key)),)).fetchall()
            if rows:raise Conflict('original application key Case changed')
        return dict(**{**FLAGS,'migration_performed':bool(matches)},status='COMMITTED' if matches else 'NOT_OBSERVED',event=matches[0] if matches else None,
            historical_only=True,not_committed_final=False,effective_release_id=matches[0]['template_upgrade']['target_release']['release_id'] if matches else _effective(instance,plan)['release_id'])
