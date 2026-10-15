"""Explicit opt-in confirmation of two actual material slots for a MANUAL note.

The frozen v1 package compiler acknowledges summary context; it does not turn
that context into note prose, business facts, authority or a verified result.
"""
from copy import deepcopy
from typing import Literal
from uuid import UUID, uuid4
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from psycopg.types.json import Jsonb
from . import plan_source_conflicts as notes, case_opportunities as op
from . import service_case_steps as service, preparation as prep, source_change_adoption as adoption
from . import executor_receipts as er
from .store import Conflict, Denied, digest

SCOPE='OWNER_NOTE_MATERIAL_PACKAGE'
CONFIRMATION_SCOPE='OWNER_NOTE_MATERIAL_PACKAGE_CONFIRMATION'
POLICY_V1=dict(need_summary='CONTEXT_ACK_ONLY',material_outline='EXACT_LINE_CARRIAGE_WHEN_REQUIRED_V1')
ACTIONS=('KEEP_AND_CONTINUE','MERGE_NOTE')
PROOF_KEYS={'version','request','preview_basis','preview_sha256','op_event_id','op_revision','op_previous_sha256','before_note','after_note','sha256'}
BASIS_KEYS={'schema','binding','actor_ref','plan_ref','note','ledger_revision','ledger_sha256','card_id','card','source','materials','source_epochs_sha256','case_versions_sha256','source_change','package_confirmation'}
SOURCE_CHANGE_KEYS_V1={'version','binding','plan_id','plan_revision','ledger_revision','ledger_sha256','card_id','card_version','basis_sha256','basis','proposal_sha256',
    'source_epochs_sha256','before_sources','current_sources','dependencies_sha256','directly_changed','affected','preserved','sha256','source_impact'}
GRAPH_KEYS_V1={'schema','scope','binding','plan_id','nodes','edges','step_endpoints','changed_node_ids','affected','preserved','unknown_scope','unknown_reasons','sha256'}


class Command(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    schema:Literal[2]
    action:Literal['KEEP_AND_CONTINUE','MERGE_NOTE']
    expected_plan_id:UUID=Field(strict=False)
    expected_plan_revision:int=Field(ge=1,le=63)
    expected_note_revision:int=Field(ge=1,le=64)
    expected_ledger_revision:int=Field(ge=0,le=127)
    expected_preview_sha256:str=Field(pattern='^[a-f0-9]{64}$')
    card_id:UUID=Field(strict=False)
    text:str|None=Field(default=None,min_length=1,max_length=notes.NOTE_LIMIT)
    reason:str=Field(min_length=1,max_length=1000)
    confirm_package:Literal[True]

    @field_validator('schema',mode='before')
    @classmethod
    def exact_schema(cls,value):
        if type(value) is not int or value!=2:raise ValueError('exact package request schema required')
        return value

    @field_validator('confirm_package',mode='before')
    @classmethod
    def exact_confirmation(cls,value):
        if type(value) is not bool or value is not True:raise ValueError('explicit package confirmation required')
        return value

    @model_validator(mode='after')
    def content(self):
        if not self.reason.strip():raise ValueError('explicit nonblank reason required')
        try:self.reason.encode('utf-8')
        except UnicodeError:raise ValueError('valid exact UTF-8 reason required') from None
        if self.action=='KEEP_AND_CONTINUE':
            if self.text is not None:raise ValueError('keep preserves the original complete manual text')
        elif self.text is None or not self.text.strip():raise ValueError('explicit complete merge draft required')
        if self.text is not None:
            try:self.text.encode('utf-8')
            except UnicodeError:raise ValueError('valid exact UTF-8 text required') from None
        return self


class DefinitiveConflict(notes.DefinitiveConflict):
    def __init__(self,parent,p,key,data):
        super().__init__(parent,p,key,data)
        self.proof['scope']=SCOPE


def request(data):return data.model_dump(mode='json')
def fingerprint(id,data):return notes.sha(dict(preparation_id=str(id),**request(data)))
def _epoch(value):return isinstance(value,str) and re.fullmatch('[0-9]{1,20}',value) is not None
def _hash(value):return isinstance(value,str) and re.fullmatch('[a-f0-9]{64}',value) is not None


def latest_event(events):
    return next((e for e in reversed(events) if e['action'] in ACTIONS and
                 type((e.get('plan_note') or {}).get('version')) is int and e['plan_note']['version']==3),None)


def active(plan):return bool(plan and latest_event(plan.get('events',[])))


def _outline(package):return next(m for m in package if m['slot']=='material_outline')


def required_v1(events,note,current):
    previous=latest_event(events)
    inherited=bool(previous and previous['plan_note']['preview_basis']['package_confirmation']['outline_carriage_required'])
    old_v2=any(e['action'] in notes.CONTINUATION_ACTIONS and
        type((e.get('plan_note') or {}).get('version')) is int and e['plan_note']['version']==2 and
        notes.same(e['plan_note']['after_note']['source_ref'],note['source_ref']) for e in events)
    return bool(inherited or old_v2 or not notes.same(note['source_ref'],notes.source_ref(_outline(current))))


def coverage_v1(text,source,required):
    if required:return dict(required=True,**notes.line_coverage_v1(text,source['text']))
    return dict(required=False,coverage_known=True,coverage_satisfied=True,conditions=[])


def _package(value):
    if not isinstance(value,list) or len(value)!=2:raise ValueError('two actual material slots required')
    for row in value:notes._material(row)
    if [m['slot'] for m in value]!=sorted(prep.SLOTS):raise ValueError('exact ordered material package required')
    return value


def epochs_for(c,parent,materials):
    result=[]
    for material in materials:
        row=c.execute('SELECT id,slot,version,text,source_kind,source_label,source_sha256,authenticity,xmin::text AS row_epoch FROM preparation_evidence WHERE preparation_id=%s AND id=%s AND slot=%s AND version=%s AND source_sha256=%s',
            (parent['id'],material['id'],material['slot'],material['version'],material['source_sha256'])).fetchone()
        if not row or not notes.same(op.normal({k:v for k,v in row.items() if k!='row_epoch'}),material):raise Conflict('actual complete material package unavailable')
        result.append(dict(notes.source_ref(material),row_epoch=row['row_epoch']))
    return result


def _epoch_list(value,materials):
    if not isinstance(value,list) or len(value)!=2:raise ValueError('complete material epochs required')
    for row,material in zip(value,materials):
        if (not isinstance(row,dict) or set(row)!=set(notes.source_ref(material))|{'row_epoch'} or
            type(row.get('version')) is not int or not notes.same({k:v for k,v in row.items() if k!='row_epoch'},notes.source_ref(material)) or
            not _epoch(row['row_epoch'])):raise ValueError('exact material row epoch proof invalid')


def validate_source_change_v1(change,basis):
    """Frozen captured-context shape, not an ADOPT or material-review proof."""
    if (not isinstance(change,dict) or set(change)!=SOURCE_CHANGE_KEYS_V1 or
        any(type(change[k]) is not int for k in ('version','plan_revision','ledger_revision','card_version')) or change['version']!=2 or
        any(not _hash(change[k]) for k in ('ledger_sha256','basis_sha256','proposal_sha256','source_epochs_sha256','dependencies_sha256','sha256')) or
        change['sha256']!=notes.sha({k:v for k,v in change.items() if k!='sha256'})):raise ValueError('captured source context shape invalid')
    card=basis['card'];binding=basis['binding']
    if (not notes.same(change['binding'],binding) or change['plan_id']!=basis['plan_ref']['plan_id'] or
        change['plan_revision']!=basis['plan_ref']['plan_revision'] or change['ledger_revision']!=basis['ledger_revision'] or
        change['ledger_sha256']!=basis['ledger_sha256'] or change['source_epochs_sha256']!=basis['source_epochs_sha256'] or
        change['card_id']!=basis['card_id'] or change['card_id']!=card['id'] or type(card['version']) is not int or
        change['card_version']!=card['version'] or change['basis_sha256']!=card['basis_sha256'] or
        change['basis_sha256']!=notes.sha(card['basis']) or not notes.same(change['basis'],card['basis'])):
        raise ValueError('captured source context binding changed')
    for key in ('before_sources','current_sources'):
        if not isinstance(change[key],dict) or set(change[key])!=set(('P1','P2','P3','P4','P5')) or any(not isinstance(v,dict) for v in change[key].values()):
            raise ValueError('complete original source context required')
    graph=change['source_impact']
    if (not isinstance(graph,dict) or set(graph)!=GRAPH_KEYS_V1 or type(graph['schema']) is not int or graph['schema']!=1 or
        graph['scope']!='REGISTERED_CASE_TYPED_SOURCE_IMPACT' or not _hash(graph['sha256']) or
        graph['sha256']!=notes.sha({k:v for k,v in graph.items() if k!='sha256'}) or
        not notes.same(graph['binding'],binding) or graph['plan_id']!=change['plan_id'] or graph['unknown_scope'] is not None or graph['unknown_reasons']!=[] or
        not notes.same(graph['affected'],change['affected']) or not notes.same(graph['preserved'],change['preserved'])):
        raise ValueError('known schema-one source graph required')
    endpoints=graph['step_endpoints']
    if (not isinstance(endpoints,list) or len(endpoints)!=5 or any(not isinstance(e,dict) or set(e)!={'id','type','adapter_id'} or
        e['type']!='PLAN_STEP' for e in endpoints) or {e['adapter_id'] for e in endpoints}!=set(('P1','P2','P3','P4','P5'))):
        raise ValueError('complete original five step endpoints required')
    ids=[e['id'] for e in endpoints]
    for id in ids:UUID(id)
    if len(set(ids))!=5 or next(e['id'] for e in endpoints if e['adapter_id']=='P1')!=basis['plan_ref']['step_id']:raise ValueError()
    for key in ('directly_changed','affected','preserved'):
        items=change[key]
        if not isinstance(items,list) or len(items)!=len(set(items)) or any(id not in ids for id in items):raise ValueError('unique original source partition required')
    if (len(change['affected']+change['preserved'])!=5 or set(change['affected']+change['preserved'])!=set(ids) or
        not set(change['directly_changed'])<=set(change['affected'])):raise ValueError('complete source impact partition required')
    if (not isinstance(graph['nodes'],list) or len(graph['nodes'])>96 or not isinstance(graph['edges'],list) or len(graph['edges'])>128 or
        not isinstance(graph['changed_node_ids'],list) or len(graph['changed_node_ids'])!=len(set(graph['changed_node_ids']))):raise ValueError()
    node_ids=[]
    for node in graph['nodes']:
        if (not isinstance(node,dict) or not _hash(node.get('id')) or node.get('known') is not True or
            type(node.get('changed')) is not bool or node.get('step_id') not in ids):raise ValueError('known captured source node required')
        node_ids.append(node['id'])
    if len(set(node_ids))!=len(node_ids) or graph['changed_node_ids']!=[node['id'] for node in graph['nodes'] if node['changed']]:raise ValueError()
    for edge in graph['edges']:
        if (not isinstance(edge,dict) or set(edge)!={'upstream','downstream','kind','provenance'} or
            edge['upstream'] not in node_ids+ids or edge['downstream'] not in ids or
            edge['kind'] not in ('MATERIAL','CAPACITY','PRECEDES','VERIFIED_BY','PACKAGED_IN')):raise ValueError('captured source edge invalid')
    return change


def core_v1(events,note,current,baseline_epochs,current_epochs,versions):
    required=required_v1(events,note,current);is_active=latest_event(events) is not None
    return dict(schema=1,scope=CONFIRMATION_SCOPE,mode='PACKAGE_V3' if is_active else 'LEGACY_OUTLINE_ONLY',active=is_active,
        baseline_package=deepcopy(note['source_package']),current_package=deepcopy(current),
        epochs=dict(baseline=deepcopy(baseline_epochs),current=deepcopy(current_epochs),case_versions=deepcopy(versions)),
        policy=deepcopy(POLICY_V1),outline_carriage_required=required,
        manual={k:note[k] for k in ('text','text_sha256','revision','event_id')},
        coverage=coverage_v1(note['text'],_outline(current),required),semantic_evaluated=False,manual_preserved=True)


def command_basis(c,p,parent,plan,basis):
    if not isinstance(basis,dict):raise Conflict('current package source inspection unavailable')
    note=basis['note']
    if note is None or note['origin']!='MANUAL':raise Conflict('original MANUAL coordination note required')
    _package(note['source_package']);_package(basis['materials'])
    from .note_template_carry import case_versions
    value=core_v1(plan['events'],note,basis['materials'],epochs_for(c,parent,note['source_package']),
                  epochs_for(c,parent,basis['materials']),case_versions(c,parent,p))
    result=dict(basis,schema=3,package_confirmation=value)
    try:validate_source_change_v1(result['source_change'],result)
    except (ValueError,KeyError,TypeError):raise Conflict('known closed source context required') from None
    return result


def adoption_blockers(c,parent,plan):
    event=latest_event(plan['events'])
    if event is None:return []
    try:
        note=next(iter(plan['owner_amendments'].values()));notes._note(note,plan['id'],note['step_id'])
        current=notes._materials(c,parent);current_epochs=epochs_for(c,parent,current)
        confirmed=event['plan_note']['after_note'];saved=event['plan_note']['preview_basis']['package_confirmation']
        if note['origin']!='MANUAL':return ['OWNER_NOTE_SOURCE_PACKAGE_MANUAL_REQUIRED']
        reasons=[]
        if (not notes.same(current,confirmed['source_package']) or
            not notes.same(current_epochs,saved['epochs']['current'])):reasons.append('OWNER_NOTE_SOURCE_PACKAGE_CONFIRMATION_REQUIRED')
        if note['event_id']!=event['id']:reasons.append('OWNER_NOTE_CONTENT_EDIT_REQUIRES_RECONFIRMATION')
        check=coverage_v1(note['text'],_outline(current),saved['outline_carriage_required'])
        if not check['coverage_known']:reasons.append('OWNER_NOTE_SOURCE_LINES_UNKNOWN')
        elif not check['coverage_satisfied']:reasons.append('OWNER_NOTE_SOURCE_LINES_NOT_CARRIED')
        return reasons
    except (KeyError,TypeError,ValueError,StopIteration,Conflict):return ['OWNER_NOTE_SOURCE_UNKNOWN']


def _prefix_events(value,event,plan_id):
    return [e['payload']['plan_event'] for e in value['events'] if e['revision']<event['revision'] and
            e['action'] in notes.OP_ACTIONS and e['payload']['plan_event']['plan_id']==plan_id]


def validate_embedded_event_v3(value,event):
    """Frozen closed pure validator; no database reads or recursive ledger calls."""
    try:
        if set(event['payload'])!={'plan_event'}:raise ValueError()
        e=event['payload']['plan_event'];proof=e['plan_note'];data=Command.model_validate(proof['request'])
        if set(e)!={'id','plan_id','revision','actor_id','request_key','fingerprint','action','reason','step_id','source_sha256','sources','coordination_only','plan_note'}:raise ValueError()
        if (set(proof)!=PROOF_KEYS or type(proof['version']) is not int or proof['version']!=3 or
            proof['sha256']!=notes.sha({k:v for k,v in proof.items() if k!='sha256'}) or
            proof['preview_sha256']!=notes.sha(proof['preview_basis']) or proof['preview_sha256']!=data.expected_preview_sha256 or
            proof['op_event_id']!=event['id'] or type(proof['op_revision']) is not int or proof['op_revision']!=event['revision'] or
            proof['op_previous_sha256']!=event['previous_sha256'] or event['revision']!=data.expected_ledger_revision+1 or
            event['action']!='RESOLVE_PLAN_NOTE' or event['outcome']!=data.action or e['actor_id']!=event['actor_id'] or
            e['request_key']!=event['request_key'] or e['fingerprint']!=event['fingerprint'] or e['action']!=data.action or
            e['plan_id']!=str(data.expected_plan_id) or type(e['revision']) is not int or e['revision']!=data.expected_plan_revision+1 or
            e['reason']!=data.reason or e['fingerprint']!=fingerprint(value['binding']['id'],data) or
            e['coordination_only'] is not True or e['source_sha256'] is not None or e['sources'] is not None):raise ValueError()
        basis=proof['preview_basis']
        if (set(basis)!=BASIS_KEYS or type(basis['schema']) is not int or basis['schema']!=3 or
            not notes.same(basis['binding'],value['binding']) or basis['actor_ref']!=notes.sha(dict(actor_id=e['actor_id'])) or
            type(basis['ledger_revision']) is not int or basis['ledger_revision']!=data.expected_ledger_revision or
            basis['ledger_sha256']!=event['previous_sha256'] or basis['plan_ref']['plan_id']!=str(data.expected_plan_id) or
            type(basis['plan_ref']['plan_revision']) is not int or basis['plan_ref']['plan_revision']!=data.expected_plan_revision or
            basis['plan_ref']['step_id']!=e['step_id'] or basis['card_id']!=str(data.card_id) or
            not notes.same(basis['note'],proof['before_note'])):raise ValueError()
        before=notes._note(proof['before_note'],e['plan_id'],e['step_id']);after=notes._note(proof['after_note'],e['plan_id'],e['step_id'])
        if before is None or before['origin']!='MANUAL' or before['revision']!=data.expected_note_revision:raise ValueError()
        _package(basis['materials']);_package(before['source_package']);notes._material(basis['source'])
        if not notes.same(_outline(basis['materials']),basis['source']):raise ValueError()
        for key in ('source_epochs_sha256','case_versions_sha256'):
            if not _hash(basis[key]):raise ValueError()
        core=basis['package_confirmation'];epochs=core['epochs'];versions=epochs['case_versions']
        if set(epochs)!={'baseline','current','case_versions'}:raise ValueError()
        _epoch_list(epochs['baseline'],before['source_package']);_epoch_list(epochs['current'],basis['materials'])
        if (set(versions)!={'preparation_epoch','case_epoch','run_epoch','source_epochs_sha256','action_grant_epochs'} or
            any(not _epoch(versions[k]) for k in ('preparation_epoch','case_epoch','run_epoch')) or
            versions['source_epochs_sha256']!=basis['source_epochs_sha256'] or
            notes.sha({k:versions[k] for k in ('preparation_epoch','case_epoch','run_epoch')})!=basis['case_versions_sha256']):raise ValueError()
        grants=versions['action_grant_epochs']
        if (not isinstance(grants,list) or len(grants)!=1 or set(grants[0])!={'action','active','row_epoch'} or
            grants[0]['action']!='case.create' or grants[0]['active'] is not True or not _epoch(grants[0]['row_epoch'])):raise ValueError()
        prefix=_prefix_events(value,event,e['plan_id'])
        expected=core_v1(prefix,before,basis['materials'],epochs['baseline'],epochs['current'],versions)
        if not notes.same(core,expected) or not core['coverage']['coverage_known']:raise ValueError()
        change=validate_source_change_v1(basis['source_change'],basis);card=basis['card']
        p1=change['current_sources']['P1'];binding=value['binding'];version=card['basis']['preparation_service_version']
        # This is a raw observed package, often before the original REVIEW.
        # P1.preparation_sha256 is the existing review_sha256, not its raw SHA.
        if (type(version) is not int or version<1 or type(p1['service_version']) is not int or p1['service_version']!=version or
            any(p1[k]!=binding[b] for k,b in [('preparation_id','id'),('case_id','case_id'),('run_id','run_id'),('service_id','service_id')]) or
            p1['preparation_sha256'] is not None and not _hash(p1['preparation_sha256'])):raise ValueError('captured P1 context binding invalid')
        op.valid_basis(card['basis'],binding)
        if not notes.same(card['basis']['materials'],[notes.source_ref(m) for m in basis['materials']]):raise ValueError()
        text=before['text'] if data.action=='KEEP_AND_CONTINUE' else data.text
        if (after is None or after['origin']!='MANUAL' or after['revision']!=before['revision']+1 or after['event_id']!=e['id'] or
            after['text']!=text or after['verified_package_sha256'] is not None or
            not notes.same(after['source_package'],basis['materials']) or not notes.same(after['source_ref'],notes.source_ref(basis['source'])) or
            data.action=='MERGE_NOTE' and before['text'] not in text or
            not coverage_v1(text,basis['source'],core['outline_carriage_required'])['coverage_satisfied']):raise ValueError()
        return e
    except (KeyError,TypeError,ValueError,AttributeError,StopIteration):raise ValueError('material package confirmation proof invalid') from None


def validate_plan_context_v1(parent,plan,event):
    """Bind new v3 captured context to the actual original plan event prefix."""
    change=event['plan_note']['preview_basis']['source_change']
    expected=[dict(id=s['id'],type='PLAN_STEP',adapter_id=s['adapter_id']) for s in plan['steps']]
    if not notes.same(change['source_impact']['step_endpoints'],expected):raise ValueError('package graph endpoints differ from original plan')
    prefix=[e for e in plan['events'] if e['revision']<event['revision']]
    if not notes.same(change['before_sources'],adoption.evidence_sources(parent,plan,events=prefix)):
        raise ValueError('package source base differs from original event prefix')


def _view(store,c,p,parent,card_id=None):
    common,basis=notes._view(store,c,p,parent,card_id)
    plan=parent.get('service_case_plan');is_active=active(plan)
    previous=latest_event(plan['events']) if plan else None
    inherited_required=bool(previous and previous['plan_note']['preview_basis']['package_confirmation']['outline_carriage_required'])
    result=dict(common,scope=SCOPE,continuation=None,can_edit=False,can_resolve=False,allowed_choices=[],action_requests={},
                history=[deepcopy(e) for saved in (plan.get('history',[])+[plan] if plan else []) for e in saved['events'] if e['action'] in ACTIONS and (e.get('plan_note') or {}).get('version')==3])
    core=dict(schema=1,scope=CONFIRMATION_SCOPE,mode='PACKAGE_V3' if is_active else 'LEGACY_OUTLINE_ONLY',active=is_active,
        baseline_package=None,current_package=deepcopy(basis['materials']) if basis else None,epochs=dict(baseline=None,current=None,case_versions=None),policy=deepcopy(POLICY_V1),
        outline_carriage_required=inherited_required,manual={k:common['note'][k] for k in ('text','text_sha256','revision','event_id')} if common['note'] else None,
        coverage=dict(required=inherited_required,coverage_known=False,coverage_satisfied=False,conditions=[]),
        semantic_evaluated=False,manual_preserved=True)
    blocks=[r for r in common['blocking_reasons'] if r!='EVENT_CAPACITY_RESERVED_FOR_UNLOCK_ACCEPT_ADOPT_VERIFY'];new_basis=None
    if basis is None:blocks.append('CURRENT_KNOWN_SOURCE_AND_CARD_REQUIRED')
    else:
        try:
            new_basis=command_basis(c,p,parent,plan,basis);core=new_basis['package_confirmation']
        except (Conflict,ValueError,TypeError,KeyError):blocks.append('ACTUAL_HISTORICAL_MANUAL_PACKAGE_REQUIRED')
    if card_id is None:blocks.append('CURRENT_PENDING_CARD_REQUIRED')
    if new_basis and not core['coverage']['coverage_known']:blocks.append('BOUNDED_NONEMPTY_OUTLINE_LINES_REQUIRED')
    if plan:
        locks=[s for s in plan['steps'] if service._manual_lock(plan,s)]
        if plan['revision']+1+len(locks)+1+len(plan['steps'])>service.LIMIT:blocks.append('EVENT_CAPACITY_RESERVED_FOR_UNLOCK_CONFIRM_ADOPT_VERIFY')
    if basis and basis['ledger_revision']+2>op.MAX_EVENTS:blocks.append('PACKAGE_LEDGER_CAPACITY_RESERVED')
    eligible=bool(new_basis and common['state']!='UNKNOWN' and not blocks)
    core=deepcopy(core)
    core.update(preview_sha256=notes.sha(new_basis) if new_basis else None,can_keep_and_continue=bool(eligible and core['coverage']['coverage_satisfied']),
                can_merge=eligible,blocking_reasons=sorted(set(blocks)))
    if new_basis:
        template=dict(schema=2,expected_plan_id=plan['id'],expected_plan_revision=plan['revision'],expected_note_revision=basis['note']['revision'],
            expected_ledger_revision=basis['ledger_revision'],expected_preview_sha256=notes.sha(new_basis),card_id=basis['card_id'],reason='',confirm_package=True)
        if core['can_keep_and_continue']:result['action_requests']['KEEP_AND_CONTINUE']=dict(template,action='KEEP_AND_CONTINUE',text=None)
        if core['can_merge']:result['action_requests']['MERGE_NOTE']=dict(template,action='MERGE_NOTE',text='')
    result.update(package_confirmation=core,preview_sha256=core['preview_sha256'],can_resolve=bool(result['action_requests']),blocking_reasons=core['blocking_reasons'])
    if not new_basis or common['state']=='UNKNOWN' or not core['coverage']['coverage_known']:
        core.update(can_keep_and_continue=False,can_merge=False)
        result.update(state='UNKNOWN',can_resolve=False,action_requests={},
                      affected=[s['id'] for s in plan['steps']] if plan else [],preserved=[],unknown_scope='THIS_CASE')
    return result,new_basis


@er.bounded
def read(store,token,id,*,card_id=None):
    with store.connect() as c:
        p,parent=service._context(store,c,token,id)
        if p['role']!='enterprise_operator':raise Denied('original Case owner required')
        return _view(store,c,p,parent,card_id)[0]


def _response(store,c,p,parent,event,*,historical):
    card_id=event['plan_note']['request']['card_id'] if event else None
    current=_view(store,c,p,parent,card_id)[0]
    return dict(scope=SCOPE,schema=1,actor_ref=notes.sha(dict(actor_id=p['id'])),preparation_id=str(parent['id']),case_id=str(parent['case_id']),run_id=str(parent['run_id']),
        plan_id=event['plan_id'] if event else current['plan_id'],status='COMMITTED' if event else 'NOT_OBSERVED',historical_only=historical,
        automatically_replayed=False,receipt=deepcopy(event),current=current)


@er.bounded
def command(store,token,id,key,data):
    if not re.fullmatch('[A-Za-z0-9_-]{1,100}',key):raise Conflict('bounded original note key required')
    with store.connect() as c:
        p,parent=service._context(store,c,token,id,True)
        if p['role']!='enterprise_operator':raise Denied('original Case owner required')
        prep.key_lock(c,p,'service-case-plan:'+key);fp=fingerprint(id,data)
        old=service._replay(c,p,parent,key,fp)
        if old:
            if (old.get('plan_note') or {}).get('version')!=3:raise Conflict('original key belongs to another protocol')
            service._recovery_proofs(parent);return _response(store,c,p,parent,old,historical=True)
        view,basis=_view(store,c,p,parent,data.card_id)
        if basis is None or view['state']=='UNKNOWN':raise Conflict('known package source inspection required; preserve request key')
        if (data.action not in view['action_requests'] or str(data.expected_plan_id)!=view['plan_id'] or data.expected_plan_revision!=view['plan_revision'] or
            data.expected_note_revision!=view['note']['revision'] or data.expected_ledger_revision!=view['opportunity_revision'] or data.expected_preview_sha256!=notes.sha(basis)):
            raise DefinitiveConflict(parent,p,key,data)
        before=deepcopy(view['note']);text=before['text'] if data.action=='KEEP_AND_CONTINUE' else data.text
        if (not coverage_v1(text,basis['source'],basis['package_confirmation']['outline_carriage_required'])['coverage_satisfied'] or
            data.action=='MERGE_NOTE' and before['text'] not in text):raise DefinitiveConflict(parent,p,key,data)
        plan=deepcopy(parent['service_case_plan']);ledger=op.ledger(parent);plan['revision']+=1
        step=next(s for s in plan['steps'] if s['id']==view['step_id']);event=service._event(plan,p,key,fp,data.action,data.reason,step)
        after=dict(before,revision=before['revision']+1,text=text,text_sha256=digest(text),origin='MANUAL',source_ref=notes.source_ref(basis['source']),
                   source_package=deepcopy(basis['materials']),verified_package_sha256=None,event_id=event['id'])
        op_id=str(uuid4());proof=dict(version=3,request=request(data),preview_basis=basis,preview_sha256=notes.sha(basis),op_event_id=op_id,
            op_revision=ledger['revision']+1,op_previous_sha256=ledger['events'][-1]['sha256'] if ledger['events'] else None,before_note=before,after_note=after)
        proof['sha256']=notes.sha(proof);event['plan_note']=proof;plan['owner_amendments']={step['id']:after}
        op_event=dict(id=op_id,scope=op.SCOPE,revision=ledger['revision']+1,actor_id=p['id'],request_key=key,fingerprint=fp,action='RESOLVE_PLAN_NOTE',
            outcome=data.action,reason=data.reason,created_at=c.execute('SELECT clock_timestamp() now').fetchone()['now'].isoformat(),
            previous_sha256=proof['op_previous_sha256'],payload=dict(plan_event=deepcopy(event)))
        op_event['sha256']=op.sha(op_event)
        final,final_basis=_view(store,c,p,parent,data.card_id)
        capability='can_keep_and_continue' if data.action=='KEEP_AND_CONTINUE' else 'can_merge'
        if (final_basis is None or final['state']=='UNKNOWN' or data.action not in final['action_requests'] or
            final['package_confirmation'][capability] is not True or not notes.same(final_basis,basis)):
            raise Conflict('source changed before package confirmation')
        ledger['events'].append(op_event);ledger['revision']+=1
        c.execute('UPDATE preparations SET opportunities=%s,service_case_plan=%s WHERE id=%s',(Jsonb(ledger),Jsonb(plan),id))
        updated=c.execute('SELECT * FROM preparations WHERE id=%s',(id,)).fetchone()
        service._recovery_proofs(updated);service._context(store,c,token,id,True)
        return _response(store,c,p,updated,event,historical=False)


@er.bounded
def recover(store,token,id,key):
    if not re.fullmatch('[A-Za-z0-9_-]{1,100}',key):raise Conflict('bounded original package key required')
    with store.connect() as c:
        p,parent=service._context(store,c,token,id)
        if p['role']!='enterprise_operator':raise Denied('original Case owner required')
        service._recovery_proofs(parent);root=parent.get('service_case_plan') or {}
        matches=[e for plan in root.get('history',[])+([root] if root else []) for e in plan['events'] if e['actor_id']==p['id'] and e['request_key']==key]
        if len(matches)>1:raise Conflict('original package key ambiguous')
        event=matches[0] if matches else None
        if event and (event.get('plan_note') or {}).get('version')!=3:raise Conflict('original key belongs to another protocol')
        return _response(store,c,p,parent,event,historical=True)
