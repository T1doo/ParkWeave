"""Version-one owner coordination notes and explicit source-change choices.

This is a P1 coordination annotation, not a material edit, compiled contract,
verified business fact or publication. Notes and decisions have original plan
events and exact opportunity-ledger counterparts in the same PG row transaction.
"""
from copy import deepcopy
from typing import Literal
from uuid import UUID,uuid4
import re

from pydantic import BaseModel,ConfigDict,Field,model_validator
from psycopg.types.json import Jsonb
from . import preparation as prep, controlled_plans as cp, case_opportunities as op
from . import source_change_adoption as adoption, service_case_steps as service
from . import executor_receipts as er
from . import typed_source_impact as typed
from .store import Conflict,Denied,digest

SCOPE='OWNER_PLAN_SOURCE_CONFLICT'
VERSION=1
ACTIONS=('EDIT_NOTE','KEEP_MANUAL','ACCEPT_SOURCE','DEFER')
OP_ACTIONS=('EDIT_PLAN_NOTE','RESOLVE_PLAN_NOTE')
NOTE_LIMIT=4000


class DefinitiveConflict(Conflict):
    """A particular monotonic gate rejected an absent key, after rollback."""
    def __init__(self,parent,p,key,data):
        super().__init__('current exact owner note and source preview required')
        self.proof=dict(scope=SCOPE,schema=VERSION,status='DEFINITIVELY_REJECTED',preparation_id=str(parent['id']),
            case_id=str(parent['case_id']),run_id=str(parent['run_id']),actor_ref=sha(dict(actor_id=p['id'])),
            request_key=key,fingerprint=fingerprint(parent['id'],data),action=data.action,plan_id=str(data.expected_plan_id),
            definitively_rejected=True,business_writes=False,automatically_replayed=False)


class Command(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    schema:int=Field(ge=1,le=1)
    action:Literal['EDIT_NOTE','KEEP_MANUAL','ACCEPT_SOURCE','DEFER']
    expected_plan_id:UUID=Field(strict=False)
    expected_plan_revision:int=Field(ge=1,le=63)
    expected_note_revision:int=Field(ge=0,le=64)
    expected_ledger_revision:int=Field(ge=0,le=127)
    expected_preview_sha256:str=Field(pattern='^[a-f0-9]{64}$')
    card_id:UUID|None=Field(default=None,strict=False)
    text:str|None=Field(default=None,min_length=1,max_length=NOTE_LIMIT)
    reason:str=Field(min_length=1,max_length=1000)

    @model_validator(mode='after')
    def shape(self):
        if not self.reason.strip():raise ValueError('explicit nonblank decision reason required')
        if self.action=='EDIT_NOTE':
            if self.text is None or not self.text.strip():raise ValueError('explicit owner coordination text required')
        elif self.text is not None or self.card_id is None:raise ValueError('decision uses actual server source and current card only')
        return self


def sha(value):return cp._hash(value)
def same(left,right):return sha(left)==sha(right)
def request(data):return data.model_dump(mode='json')
def fingerprint(id,data):return sha(dict(preparation_id=str(id),**request(data)))
def source_ref(source):return {k:source[k] for k in ('id','slot','version','source_sha256')}


def _material(value):
    keys={'id','slot','version','text','source_kind','source_label','source_sha256','authenticity'}
    if (not isinstance(value,dict) or set(value)!=keys or value['slot'] not in prep.SLOTS or
        type(value['version']) is not int or value['version']<1 or
        not isinstance(value['text'],str) or not 1<=len(value['text'])<=NOTE_LIMIT or not value['text'].strip() or
        value['source_kind'] not in ('USER_STATEMENT','DOCUMENT_EXCERPT') or
        not isinstance(value['source_label'],str) or not 1<=len(value['source_label'])<=200 or
        value['source_sha256']!=digest(value['text']) or value['authenticity']!='UNVERIFIED'):
        raise ValueError('actual bounded material evidence required')
    UUID(value['id']);return value


def _materials(c,parent):
    values=op.normal(prep.latest(c,parent['id']))
    if len(values)!=2 or {m['slot'] for m in values}!=set(prep.SLOTS):raise Conflict('known actual material package required')
    try:
        for m in values:_material(m)
    except (ValueError,TypeError,KeyError):raise Conflict('known actual material evidence required') from None
    return values


def _note(value,plan_id,step_id):
    if value is None:return None
    if (not isinstance(value,dict) or set(value)!={'version','revision','text','text_sha256','origin','source_ref','source_package','verified_package_sha256','event_id','plan_id','step_id'} or
        type(value['version']) is not int or value['version']!=VERSION or type(value['revision']) is not int or not 1<=value['revision']<=64 or
        value['plan_id']!=plan_id or value['step_id']!=step_id or value['origin'] not in ('MANUAL','SOURCE') or
        not isinstance(value['text'],str) or not 1<=len(value['text'])<=NOTE_LIMIT or not value['text'].strip() or value['text_sha256']!=digest(value['text']) or
        not isinstance(value['source_package'],list) or len(value['source_package'])!=2):raise ValueError('owner annotation proof invalid')
    UUID(value['event_id'])
    for material in value['source_package']:_material(material)
    if {m['slot'] for m in value['source_package']}!=set(prep.SLOTS):raise ValueError('complete original source package required')
    outline=next(m for m in value['source_package'] if m['slot']=='material_outline')
    if not same(value['source_ref'],source_ref(outline)):raise ValueError('owner annotation source anchor invalid')
    if value['verified_package_sha256'] is not None and not re.fullmatch('[a-f0-9]{64}',value['verified_package_sha256']):raise ValueError()
    return value


def _plan_ref(parent,plan,revision,step_id):
    return dict(binding=op.binding(parent),plan_id=plan['id'],plan_revision=revision,step_id=step_id,
        initial_adopt_fingerprint=plan['events'][0]['fingerprint'],
        steps_sha256=sha([{k:s[k] for k in ('id','adapter_id','adapter','adapter_revision','depends_on','contract')} for s in plan['steps']]))


def validate_embedded_event(value,event):
    """Pure ledger validation; deliberately never calls op.ledger/recovery."""
    try:
        if set(event['payload'])!={'plan_event'}:raise ValueError()
        plan_event=event['payload']['plan_event'];proof=plan_event['plan_note'];data=Command.model_validate(proof['request'])
        if set(plan_event)!={'id','plan_id','revision','actor_id','request_key','fingerprint','action','reason','step_id','source_sha256','sources','coordination_only','plan_note'}:raise ValueError()
        proof_keys={'version','request','preview_basis','preview_sha256','op_event_id','op_revision','op_previous_sha256','before_note','after_note','sha256'}
        if (set(proof)!=proof_keys or type(proof['version']) is not int or proof['version']!=VERSION or
            proof['sha256']!=sha({k:v for k,v in proof.items() if k!='sha256'}) or
            proof['preview_sha256']!=sha(proof['preview_basis']) or proof['preview_sha256']!=data.expected_preview_sha256 or
            proof['op_event_id']!=event['id'] or type(proof['op_revision']) is not int or proof['op_revision']!=event['revision'] or proof['op_previous_sha256']!=event['previous_sha256'] or
            event['revision']!=data.expected_ledger_revision+1 or event['outcome']!=data.action or
            event['action']!=('EDIT_PLAN_NOTE' if data.action=='EDIT_NOTE' else 'RESOLVE_PLAN_NOTE') or
            plan_event['actor_id']!=event['actor_id'] or plan_event['request_key']!=event['request_key'] or
            plan_event['fingerprint']!=event['fingerprint'] or plan_event['action']!=data.action or
            plan_event['plan_id']!=str(data.expected_plan_id) or plan_event['revision']!=data.expected_plan_revision+1 or
            plan_event['source_sha256'] is not None or plan_event['sources'] is not None or plan_event['coordination_only'] is not True or
            plan_event['reason']!=data.reason or plan_event['fingerprint']!=fingerprint(value['binding']['id'],data)):
            raise ValueError('note decision event proof invalid')
        basis=proof['preview_basis']
        if set(basis)!={'schema','binding','actor_ref','plan_ref','note','ledger_revision','ledger_sha256','card_id','card','source','materials','source_epochs_sha256','case_versions_sha256','source_change'}:raise ValueError()
        if (basis['schema']!=VERSION or type(basis['schema']) is not int or not same(basis['binding'],value['binding']) or
            basis['actor_ref']!=sha(dict(actor_id=event['actor_id'])) or type(basis['ledger_revision']) is not int or basis['ledger_revision']!=data.expected_ledger_revision or
            basis['ledger_sha256']!=event['previous_sha256'] or basis['plan_ref']['plan_id']!=str(data.expected_plan_id) or
            basis['plan_ref']['plan_revision']!=data.expected_plan_revision or basis['plan_ref']['step_id']!=plan_event['step_id'] or
            not same(basis['note'],proof['before_note']) or (proof['before_note']['revision'] if proof['before_note'] else 0)!=data.expected_note_revision or
            basis['card_id']!=(str(data.card_id) if data.card_id else None)):
            raise ValueError('note preview binding invalid')
        _material(basis['source'])
        if not isinstance(basis['materials'],list) or len(basis['materials'])!=2:raise ValueError()
        for material in basis['materials']:_material(material)
        if {m['slot'] for m in basis['materials']}!=set(prep.SLOTS) or basis['source']['slot']!='material_outline':raise ValueError('complete source preview required')
        if not same(next(m for m in basis['materials'] if m['slot']=='material_outline'),basis['source']):raise ValueError()
        for key in ('source_epochs_sha256','case_versions_sha256'):
            if not isinstance(basis[key],str) or not re.fullmatch('[a-f0-9]{64}',basis[key]):raise ValueError()
        before=_note(proof['before_note'],plan_event['plan_id'],plan_event['step_id'])
        after=_note(proof['after_note'],plan_event['plan_id'],plan_event['step_id'])
        if data.action in ('KEEP_MANUAL','DEFER'):
            if before is None or not same(after,before):raise ValueError('preserved note changed')
        else:
            if (after is None or after['revision']!=(before['revision'] if before else 0)+1 or after['event_id']!=plan_event['id']):raise ValueError()
            if data.action=='EDIT_NOTE':
                if after['origin']!='MANUAL' or after['text']!=data.text:raise ValueError()
                if before is None and (not same(after['source_ref'],source_ref(basis['source'])) or not same(after['source_package'],basis['materials'])):raise ValueError('initial manual source anchor changed')
                if before and any(not same(after[k],before[k]) for k in ('source_ref','source_package','verified_package_sha256')):raise ValueError('manual edit cannot rebase source')
            elif (before is None or after['origin']!='SOURCE' or after['text']!=basis['source']['text'] or
                  not same(after['source_ref'],source_ref(basis['source'])) or not same(after['source_package'],basis['materials'])):raise ValueError('accepted text is not actual source')
        return plan_event
    except (KeyError,TypeError,ValueError,AttributeError):raise ValueError('note opportunity event proof invalid') from None


def validate_ledger_links(parent,value):
    """Bidirectional exact links, without invoking any recursive plan reader."""
    plan=parent.get('service_case_plan')
    plans=plan.get('history',[])+[plan] if isinstance(plan,dict) else []
    note_events=[e for saved in plans for e in saved['events'] if e['action'] in ACTIONS]
    ledger_events=[e for e in value['events'] if e['action'] in OP_ACTIONS]
    if len(note_events)!=len(ledger_events):raise ValueError('note plan/ledger event count differs')
    for event in ledger_events:
        linked=validate_embedded_event(value,event)
        matches=[e for e in note_events if e['id']==linked['id']]
        if len(matches)!=1 or not same(matches[0],linked):raise ValueError('original note plan counterpart changed')
        proof=linked['plan_note'];basis=proof['preview_basis']
        prefix=dict(value,revision=event['revision']-1,events=value['events'][:event['revision']-1])
        if basis['card_id'] is None:
            if basis['card'] is not None:raise ValueError('unexpected annotation card')
        else:
            cards,heads=op.project(prefix);card=cards.get(basis['card_id'])
            if (not card or card['state']!='PENDING_REVIEW' or heads[card['entry']['family_id']][1]!=card['id'] or not same(card,basis['card'])):
                raise ValueError('annotation card differs from original ledger prefix')


def validate_plan_history(parent,plan):
    events=[e for e in plan['events'] if e['action'] in ACTIONS]
    notes=plan.get('owner_amendments')
    if not events:
        if notes is not None:raise ValueError('annotation has no original owner event')
        return
    # Validate ledger structure without calling this function back from project.
    ledger=op.ledger(parent);current=None
    for event in events:
        proof=event['plan_note'];expected_ref=_plan_ref(parent,plan,event['revision']-1,event['step_id'])
        if not same(proof['preview_basis']['plan_ref'],expected_ref) or not same(proof['before_note'],current):raise ValueError('note plan revision or original body changed')
        matching=[e for e in ledger['events'] if e['id']==proof['op_event_id']]
        if len(matching)!=1 or not same(validate_embedded_event(ledger,matching[0]),event):raise ValueError('note ledger counterpart missing or changed')
        if event['actor_id']!=parent['owner_id']:raise ValueError('note owner changed')
        step=next((s for s in plan['steps'] if s['id']==event['step_id']),None)
        if not step or step['adapter_id']!='P1':raise ValueError('only original P1 annotation supported')
        current=proof['after_note']
    if not same(notes,{events[-1]['step_id']:current}):raise ValueError('current owner annotation differs from original events')


def adoption_blockers(c,parent,plan):
    if not plan or not plan.get('owner_amendments'):return []
    try:
        note=next(iter(plan['owner_amendments'].values()));_note(note,plan['id'],note['step_id'])
        actual=next(m for m in _materials(c,parent) if m['slot']=='material_outline')
    except (ValueError,TypeError,KeyError,StopIteration,Conflict):return ['OWNER_NOTE_SOURCE_UNKNOWN']
    if same(note['source_ref'],source_ref(actual)):return []
    latest=next((e for e in reversed(plan['events']) if e['action'] in ACTIONS),None)
    choice=latest['action'] if latest else None
    return ['OWNER_NOTE_SOURCE_KEPT_PENDING' if choice=='KEEP_MANUAL' else 'OWNER_NOTE_SOURCE_DEFERRED' if choice=='DEFER' else 'OWNER_NOTE_SOURCE_CONFLICT_REQUIRES_DECISION']


def adoption_guard(c,parent,plan):
    if not plan or not plan.get('owner_amendments'):return
    service._recovery_proofs(parent)
    reasons=adoption_blockers(c,parent,plan)
    if reasons:raise Conflict('unresolved owner coordination note: '+','.join(reasons))


def _material_diffs(c,parent,note,materials):
    results=[]
    plan=parent.get('service_case_plan') or {}
    p1=next((s for s in plan.get('steps',[]) if s['adapter_id']=='P1'),None)
    verified=(p1.get('verified_sources') or {}) if p1 else {}
    packages=[note['source_package']] if note else []
    for event in plan.get('events',[]):
        if event['action'] in ACTIONS:
            packages.extend(n['source_package'] for n in (event['plan_note']['before_note'],event['plan_note']['after_note']) if n)
    exact=[]
    for package in packages:
        row=dict(parent,service_version=verified.get('service_version',parent['service_version']))
        if prep.snapshot(row,package)==verified.get('preparation_sha256') and package not in exact:exact.append(package)
    for slot in prep.SLOTS:
        current=next(m for m in materials if m['slot']==slot);before=None;kind='UNKNOWN_BASELINE'
        if len(exact)==1:
            captured=next(m for m in exact[0] if m['slot']==slot)
            row=c.execute('SELECT id,slot,version,text,source_kind,source_label,source_sha256,authenticity FROM preparation_evidence WHERE preparation_id=%s AND id=%s AND slot=%s AND version=%s AND source_sha256=%s',
                (parent['id'],captured['id'],slot,captured['version'],captured['source_sha256'])).fetchone()
            if row is not None and op.normal(row)==captured:before=captured;kind='OWNER_AMENDMENT_CAPTURED_VERIFIED_PACKAGE'
        results.append(dict(slot=slot,before=before,current=current,changed=source_ref(before)!=source_ref(current) if before else None,proof_kind=kind))
    return results


def _basis(store,c,p,parent,plan,note,card_id):
    ledger=op.ledger(parent);materials=_materials(c,parent);source=next(m for m in materials if m['slot']=='material_outline')
    source_change=None;source_view=None;card=None
    if card_id is not None:
        source_view,source_change,_,_=adoption.build(store,c,p,parent,str(card_id))
        _,card=adoption.current_card(parent,str(card_id),ledger)
    else:
        issues,sources,_=service.current_sources(store,c,parent,plan)
        sources={s['adapter_id']:sources[s['adapter_id']] for s in plan['steps']}
        dependencies,_,_=service.dependency_impact(store,c,parent,plan)
        graph=typed.build(parent,plan,adoption.evidence_sources(parent,plan),sources,plan.get('dependency_manifest'),dependencies)
        blocks=service._binding_issues(c,parent,plan,store=store)
        if any(adoption.unavailable_sources().intersection(v) for v in issues.values()):blocks.append('CURRENT_KNOWN_SOURCE_REQUIRED')
        source_view=dict(affected=graph['affected'],preserved=graph['preserved'],unknown_scope=graph['unknown_scope'],blocking_reasons=blocks)
    versions=c.execute('SELECT p.xmin::text preparation_epoch,c.xmin::text case_epoch,r.xmin::text run_epoch FROM preparations p JOIN cases c ON c.id=p.case_id JOIN runs r ON r.id=p.run_id WHERE p.id=%s',(parent['id'],)).fetchone()
    p1=next(s for s in plan['steps'] if s['adapter_id']=='P1')
    basis=dict(schema=VERSION,binding=op.binding(parent),actor_ref=sha(dict(actor_id=p['id'])),plan_ref=_plan_ref(parent,plan,plan['revision'],p1['id']),
        note=deepcopy(note),ledger_revision=ledger['revision'],ledger_sha256=ledger['events'][-1]['sha256'] if ledger['events'] else None,
        card_id=str(card_id) if card_id is not None else None,card=deepcopy(card),source=source,materials=materials,
        source_epochs_sha256=adoption.epochs(c,parent),case_versions_sha256=sha(op.normal(versions)),source_change=source_change)
    return basis,source_view


def _view(store,c,p,parent,card_id=None):
    plan=deepcopy(parent.get('service_case_plan'))
    result=dict(scope=SCOPE,schema=VERSION,actor_ref=sha(dict(actor_id=p['id'])),preparation_id=str(parent['id']),case_id=str(parent['case_id']),run_id=str(parent['run_id']),
        plan_id=None,plan_revision=0,step_id=None,card_id=str(card_id) if card_id else None,card_version=None,opportunity_revision=op.ledger(parent)['revision'],
        preview_sha256=None,note=None,source=None,material_diffs=[],state='UNKNOWN',can_edit=False,can_resolve=False,allowed_choices=[],blocking_reasons=[],affected=[],preserved=[],history=[],action_requests={},unknown_scope='THIS_CASE',
        read_only=True,automatically_replayed=False,new_grants=False,automatic_execution=False,case_goal_completed=False,qualification_decision='NOT_EVALUATED')
    if not plan:return dict(result,blocking_reasons=['ORIGINAL_ADOPTED_P1_REQUIRED']),None
    service._recovery_proofs(parent)
    p1=next((s for s in plan['steps'] if s['adapter_id']=='P1'),None)
    if not p1:return dict(result,blocking_reasons=['ORIGINAL_ADOPTED_P1_REQUIRED']),None
    note=deepcopy((plan.get('owner_amendments') or {}).get(p1['id']))
    history=[deepcopy(e) for old in plan.get('history',[])+[plan] for e in old['events'] if e['action'] in ACTIONS]
    result.update(plan_id=plan['id'],plan_revision=plan['revision'],step_id=p1['id'],note=note,history=history,affected=[s['id'] for s in plan['steps']])
    try:basis,source_view=_basis(store,c,p,parent,plan,note,card_id)
    except Conflict as error:return dict(result,blocking_reasons=['CURRENT_KNOWN_SOURCE_AND_CARD_REQUIRED']),None
    conflict=bool(note and note['source_ref']!=source_ref(basis['source']))
    locks=[s for s in plan['steps'] if service._manual_lock(plan,s)]
    locked=bool(p1.get('manual_lock'));source_blockers=[]
    if source_view:
        source_blockers=[r for r in source_view['blocking_reasons'] if r not in {'AFFECTED_LOCK_REQUIRES_EXPLICIT_UNLOCK','NO_ACTUAL_SOURCE_CHANGE'} and not r.startswith('OWNER_NOTE_SOURCE_')]
    if source_view and source_view['unknown_scope']:source_blockers.append('KNOWN_SOURCE_CHANGE_REQUIRED')
    can_write=not prep.case_write_blocked(c,parent)
    try:store.check_capability(c,p,'EXECUTE')
    except Denied:can_write=False
    # Reserve original unlocks plus a subsequent accept/adopt/VERIFY path even
    # for KEEP/DEFER, so a note cannot consume the only way out of conflict.
    # A preserve/edit choice needs a future ACCEPT plus ADOPT. ACCEPT already
    # is that event: reserve only its subsequent original ADOPT and VERIFYs.
    base=plan['revision']+1+len(locks)+len(plan['steps'])
    capacity=base+2<=service.LIMIT and basis['ledger_revision']+2<=op.MAX_EVENTS
    accept_capacity=base+1<=service.LIMIT and basis['ledger_revision']+1<=op.MAX_EVENTS
    can_edit=can_write and not locked and capacity and not source_view['unknown_scope'] and not source_blockers
    resolve_context=bool(can_write and conflict and card_id is not None and not source_blockers)
    choices=((['KEEP_MANUAL','DEFER'] if capacity else [])+(['ACCEPT_SOURCE'] if not locked and accept_capacity else [])) if resolve_context else []
    can_resolve=bool(choices)
    state='NO_NOTE' if note is None else 'CONFLICT' if conflict else 'NO_CHANGE'
    last=next((e for e in reversed(plan['events']) if e['action'] in ACTIONS),None)
    if conflict and last and last['action']=='KEEP_MANUAL':state='KEPT_MANUAL'
    if conflict and last and last['action']=='DEFER':state='DEFERRED'
    if note and not conflict and note['origin']=='SOURCE':
        _,_,_,_,states,_=service._inspect(store,c,parent,deepcopy(plan),observe=False)
        state='RESOLVED' if states['P1']=='VERIFIED' else 'ACCEPTED_AWAITING_RECHECK'
    if source_view['unknown_scope'] or source_blockers:state='UNKNOWN'
    blocks=list(source_blockers)
    if locked:blocks.append('P1_LOCK_REQUIRES_ORIGINAL_UNLOCK_FOR_EDIT_OR_ACCEPT')
    if not (capacity or conflict and not locked and accept_capacity):blocks.append('EVENT_CAPACITY_RESERVED_FOR_UNLOCK_ACCEPT_ADOPT_VERIFY')
    if not can_write:blocks.append('CURRENT_EXECUTE_REQUIRED')
    template=dict(schema=VERSION,expected_plan_id=plan['id'],expected_plan_revision=plan['revision'],expected_note_revision=note['revision'] if note else 0,
        expected_ledger_revision=basis['ledger_revision'],expected_preview_sha256=sha(basis),card_id=basis['card_id'],reason='')
    action_requests={a:dict(template,action=a,text='' if a=='EDIT_NOTE' else None) for a in (['EDIT_NOTE'] if can_edit else [])+choices}
    result.update(card_version=basis['card']['version'] if basis['card'] else None,opportunity_revision=basis['ledger_revision'],preview_sha256=sha(basis),source=basis['source'],
        material_diffs=_material_diffs(c,parent,note,basis['materials']),state=state,can_edit=can_edit,can_resolve=can_resolve,
        allowed_choices=choices,blocking_reasons=sorted(set(blocks)),affected=source_view['affected'],preserved=source_view['preserved'],action_requests=action_requests,unknown_scope=source_view['unknown_scope'])
    return result,basis


@er.bounded
def read(store,token,id,*,card_id=None):
    with store.connect() as c:
        p,parent=service._context(store,c,token,id)
        if p['role']!='enterprise_operator':raise Denied('original owner coordination note required')
        return _view(store,c,p,parent,card_id)[0]


def _response(store,c,p,parent,event,*,historical):
    card_id=event['plan_note']['request']['card_id'] if event else None
    current=_view(store,c,p,parent,card_id)[0]
    return dict(scope=SCOPE,schema=VERSION,actor_ref=sha(dict(actor_id=p['id'])),preparation_id=str(parent['id']),case_id=str(parent['case_id']),run_id=str(parent['run_id']),
        plan_id=event['plan_id'] if event else current['plan_id'],status='COMMITTED' if event else 'NOT_OBSERVED',historical_only=historical,automatically_replayed=False,receipt=deepcopy(event),current=current)


@er.bounded
def command(store,token,id,key,data):
    if not re.fullmatch('[A-Za-z0-9_-]{1,100}',key):raise Conflict('bounded original note request key required')
    with store.connect() as c:
        p,parent=service._context(store,c,token,id,True)
        if p['role']!='enterprise_operator':raise Denied('original owner coordination note required')
        prep.key_lock(c,p,'service-case-plan:'+key);fp=fingerprint(id,data)
        old=service._replay(c,p,parent,key,fp)
        if old:
            if old['action'] not in ACTIONS:raise Conflict('original note action changed')
            service._recovery_proofs(parent);return _response(store,c,p,parent,old,historical=True)
        view,basis=_view(store,c,p,parent,data.card_id)
        if basis is None:raise Conflict('current source inspection unavailable; preserve original request key')
        if view['state']=='UNKNOWN':raise Conflict('unknown source inspection; preserve original request key')
        if (data.action not in view['action_requests'] or data.expected_plan_id!=UUID(view['plan_id']) or
            data.expected_plan_revision!=view['plan_revision'] or data.expected_note_revision!=(view['note']['revision'] if view['note'] else 0) or
            data.expected_ledger_revision!=view['opportunity_revision'] or data.expected_preview_sha256!=view['preview_sha256']):
            raise DefinitiveConflict(parent,p,key,data)
        plan=deepcopy(parent['service_case_plan']);ledger=op.ledger(parent)
        if ledger['revision']>=op.MAX_EVENTS:raise Conflict('bounded opportunity history exhausted')
        before=deepcopy(view['note']);after=deepcopy(before);plan['revision']+=1
        step=next(s for s in plan['steps'] if s['id']==view['step_id'])
        event=service._event(plan,p,key,fp,data.action,data.reason,step)
        if data.action in ('EDIT_NOTE','ACCEPT_SOURCE'):
            material_package=basis['materials'] if before is None or data.action=='ACCEPT_SOURCE' else before['source_package']
            before_p1=adoption.evidence_sources(parent,parent['service_case_plan']).get('P1',{})
            package_sha=prep.snapshot(parent,material_package)
            verified=package_sha if before_p1.get('preparation_sha256')==package_sha else None
            after=dict(version=VERSION,revision=(before['revision'] if before else 0)+1,text=data.text if data.action=='EDIT_NOTE' else basis['source']['text'],
                text_sha256=digest(data.text if data.action=='EDIT_NOTE' else basis['source']['text']),origin='MANUAL' if data.action=='EDIT_NOTE' else 'SOURCE',
                source_ref=source_ref(next(m for m in material_package if m['slot']=='material_outline')),source_package=deepcopy(material_package),
                verified_package_sha256=before['verified_package_sha256'] if before and data.action=='EDIT_NOTE' else verified,event_id=event['id'],plan_id=plan['id'],step_id=step['id'])
        op_id=str(uuid4())
        proof=dict(version=VERSION,request=request(data),preview_basis=basis,preview_sha256=sha(basis),op_event_id=op_id,op_revision=ledger['revision']+1,
            op_previous_sha256=ledger['events'][-1]['sha256'] if ledger['events'] else None,before_note=before,after_note=after)
        proof['sha256']=sha(proof);event['plan_note']=proof
        plan['owner_amendments']={step['id']:after}
        op_event=dict(id=op_id,scope=op.SCOPE,revision=ledger['revision']+1,actor_id=p['id'],request_key=key,fingerprint=fp,
            action='EDIT_PLAN_NOTE' if data.action=='EDIT_NOTE' else 'RESOLVE_PLAN_NOTE',outcome=data.action,reason=data.reason,
            created_at=c.execute('SELECT clock_timestamp() now').fetchone()['now'].isoformat(),previous_sha256=proof['op_previous_sha256'],payload=dict(plan_event=deepcopy(event)))
        op_event['sha256']=op.sha(op_event)
        final,final_basis=_view(store,c,p,parent,data.card_id)
        if final_basis!=basis or final['preview_sha256']!=data.expected_preview_sha256:raise Conflict('source changed before owner note decision')
        ledger['events'].append(op_event);ledger['revision']+=1
        c.execute('UPDATE preparations SET opportunities=%s,service_case_plan=%s WHERE id=%s',(Jsonb(ledger),Jsonb(plan),id))
        updated=c.execute('SELECT * FROM preparations WHERE id=%s',(id,)).fetchone()
        service._recovery_proofs(updated)
        service._context(store,c,token,id,True)
        return _response(store,c,p,updated,event,historical=False)


@er.bounded
def recover(store,token,id,key):
    if not re.fullmatch('[A-Za-z0-9_-]{1,100}',key):raise Conflict('bounded original note request key required')
    with store.connect() as c:
        # READ/PREPARE scope is the original history contract; no EXECUTE or
        # business-write permission is inferred from an old successful receipt.
        p,parent=service._context(store,c,token,id)
        if p['role']!='enterprise_operator':raise Denied('original owner note history required')
        service._recovery_proofs(parent)
        matches=[e for plan in parent.get('service_case_plan',{}).get('history',[])+([parent['service_case_plan']] if parent.get('service_case_plan') else []) for e in plan['events'] if e['actor_id']==p['id'] and e['request_key']==key]
        if len(matches)>1:raise Conflict('original note key history ambiguous')
        event=matches[0] if matches else None
        if event and event['action'] not in ACTIONS:raise Conflict('original key is another plan action')
        return _response(store,c,p,parent,event,historical=True)
