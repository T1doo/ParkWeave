"""Frozen v1 manual-note carriage for same-structure template revisions.

This preserves an owner annotation. It does not evaluate its semantic duties or
change any source fact. Database epochs are command-time CAS evidence, not an
administrator signature or a promise about a later external transaction.
"""
from copy import deepcopy
import re
from . import case_opportunities as op, plan_source_conflicts as notes
from . import source_change_adoption as adoption
from .template_candidate import sha
from .template_consumer import normal
from .store import Conflict

VERSION=1
SCOPE='OWNER_MANUAL_NOTE_TEMPLATE_CARRY'
KEYS_V1={'version','scope','binding','plan_ref','notes','ledger','materials','case_versions',
         'previous_release','target_release','check_sha256','choice_revision','choice_event_sha256',
         'source_changed','affected','preserved','semantic_evaluated','sha256'}


def _same(a,b):return sha(normal(a))==sha(normal(b))
def _hash(value):return isinstance(value,str) and re.fullmatch('[a-f0-9]{64}',value) is not None
def _epoch(value):return isinstance(value,str) and re.fullmatch('[0-9]{1,20}',value) is not None


def release_ref_v1(release):
    snapshot=release['snapshot']
    return dict(release_id=release['release_id'],release_sha256=release['release_sha256'],
        definition_sha256=snapshot['definition_sha256'],source_sha256=sha(snapshot['definition']['source']))


def plan_ref_v1(plan,revision):
    return dict(plan_id=plan['id'],plan_revision=revision,initial_adopt_fingerprint=plan['events'][0]['fingerprint'],
        steps_sha256=sha([{k:s[k] for k in ('id','adapter_id','adapter','adapter_revision','depends_on','contract')} for s in plan['steps']]),
        required_goals_sha256=sha(plan['required_goals']),binding_sha256=sha(plan['binding']))


def notes_before_v1(plan,revision):
    current=None
    for event in plan['events']:
        if event['revision']>=revision:break
        if event['action'] in notes.ACTIONS:current={event['step_id']:deepcopy(event['plan_note']['after_note'])}
    return current


def _manual(value,plan):
    if not isinstance(value,dict) or len(value)!=1:raise ValueError('one manual annotation required')
    step=next(s for s in plan['steps'] if s['adapter_id']=='P1')
    if set(value)!={step['id']}:raise ValueError('original P1 note required')
    note=notes._note(value[step['id']],plan['id'],step['id'])
    if note['origin']!='MANUAL':raise ValueError('manual origin required')
    return note


def _epochs_for(c,parent,materials):
    result=[]
    for material in sorted(materials,key=lambda m:m['slot']):
        row=c.execute('SELECT id,slot,version,text,source_kind,source_label,source_sha256,authenticity,xmin::text AS row_epoch FROM preparation_evidence WHERE preparation_id=%s AND id=%s AND slot=%s AND version=%s AND source_sha256=%s',
            (parent['id'],material['id'],material['slot'],material['version'],material['source_sha256'])).fetchone()
        if not row or not _same({k:v for k,v in row.items() if k!='row_epoch'},material):raise Conflict('actual captured material proof unavailable')
        result.append(dict(notes.source_ref(material),row_epoch=row['row_epoch']))
    return result


def case_versions(c,parent,p):
    values={}
    for label,table,id in (('preparation_epoch','preparations',parent['id']),('case_epoch','cases',parent['case_id']),('run_epoch','runs',parent['run_id'])):
        row=c.execute('SELECT xmin::text AS row_epoch FROM '+table+' WHERE id=%s AND park_id=%s AND org_id=%s',(id,parent['park_id'],parent['org_id'])).fetchone()
        if not row:raise Conflict('original Case row-version proof unavailable')
        values[label]=row['row_epoch']
    rows=c.execute("SELECT action,active,xmin::text AS row_epoch FROM action_grants WHERE principal_id=%s AND park_id=%s AND org_id=%s AND action='case.create' ORDER BY action LIMIT 2",(p['id'],p['park_id'],p['org_id'])).fetchall()
    if len(rows)!=1 or rows[0]['active'] is not True:raise Conflict('current original Case grant required')
    values['action_grant_epochs']=normal(rows)
    values['source_epochs_sha256']=adoption.epochs(c,parent)
    return values


def proof_v1(scope,plan,revision,annotations,ledger,materials,versions,before,target,check,choice,affected,preserved):
    value=dict(version=1,scope=SCOPE,binding=deepcopy(scope),plan_ref=plan_ref_v1(plan,revision),notes=deepcopy(annotations),
        ledger=deepcopy(ledger),materials=deepcopy(materials),case_versions=deepcopy(versions),
        previous_release=release_ref_v1(before),target_release=release_ref_v1(target),check_sha256=sha(check),
        choice_revision=choice['revision'],choice_event_sha256=choice['event_sha256'],
        source_changed=before['snapshot']['definition']['source']!=target['snapshot']['definition']['source'],
        affected=list(affected),preserved=list(preserved),semantic_evaluated=False)
    value['sha256']=sha(value)
    return value


def _epoch_list(value,materials):
    if not isinstance(value,list) or len(value)!=2:raise ValueError('complete source epochs required')
    wanted=[notes.source_ref(m) for m in sorted(materials,key=lambda m:m['slot'])]
    for item,expected in zip(value,wanted):
        if not isinstance(item,dict) or set(item)!=set(expected)|{'row_epoch'} or not _epoch(item['row_epoch']) or {k:v for k,v in item.items() if k!='row_epoch'}!=expected:raise ValueError('exact source epoch reference required')


def validate_v1(parent,plan,event,before,target,check,choice,affected,preserved):
    """Validate historical prefix inputs; never reinterpret with current notes."""
    try:
        value=event['template_upgrade']['note_carry']
        if (not isinstance(value,dict) or set(value)!=KEYS_V1 or type(value['version']) is not int or value['version']!=1 or
            value['scope']!=SCOPE or value['semantic_evaluated'] is not False or value['sha256']!=sha({k:v for k,v in value.items() if k!='sha256'})):raise ValueError()
        annotations=notes_before_v1(plan,event['revision']);note=_manual(annotations,plan)
        ledger=op.ledger(parent);prefix=value['ledger']
        if (not isinstance(prefix,dict) or set(prefix)!={'revision','sha256'} or type(prefix['revision']) is not int or not 1<=prefix['revision']<=ledger['revision'] or
            prefix['sha256']!=ledger['events'][prefix['revision']-1]['sha256']):raise ValueError('original ledger prefix required')
        # Every note represented at this plan revision must already exist in that
        # prefix. Later note edits/decisions must not rewrite the old carry.
        old_notes=[e for e in plan['events'] if e['revision']<event['revision'] and e['action'] in notes.ACTIONS]
        if any(e['plan_note']['op_revision']>prefix['revision'] for e in old_notes):raise ValueError()
        if any(e['plan_note']['op_revision']<=prefix['revision'] for e in plan['events'] if e['revision']>event['revision'] and e['action'] in notes.ACTIONS):raise ValueError()
        materials=value['materials'];versions=value['case_versions']
        if not isinstance(materials,dict) or set(materials)!={'current','current_epochs','captured_epochs'} or not isinstance(materials['current'],list) or len(materials['current'])!=2:raise ValueError()
        for material in materials['current']:notes._material(material)
        if [m['slot'] for m in materials['current']]!=sorted(notes.prep.SLOTS):raise ValueError()
        outline=next(m for m in materials['current'] if m['slot']=='material_outline')
        if notes.source_ref(outline)!=note['source_ref']:raise ValueError('resolved material anchor required')
        _epoch_list(materials['current_epochs'],materials['current']);_epoch_list(materials['captured_epochs'],note['source_package'])
        if (not isinstance(versions,dict) or set(versions)!={'preparation_epoch','case_epoch','run_epoch','source_epochs_sha256','action_grant_epochs'} or
            any(not _epoch(versions[k]) for k in ('preparation_epoch','case_epoch','run_epoch')) or not _hash(versions['source_epochs_sha256'])):raise ValueError()
        grants=versions['action_grant_epochs']
        if (not isinstance(grants,list) or len(grants)!=1 or set(grants[0])!={'action','active','row_epoch'} or
            grants[0]['action']!='case.create' or grants[0]['active'] is not True or not _epoch(grants[0]['row_epoch'])):raise ValueError()
        rebuilt=proof_v1(check['scope'],plan,event['revision']-1,annotations,prefix,materials,versions,before,target,check,choice,affected,preserved)
        if not _same(value,rebuilt):raise ValueError('immutable note carry binding changed')
        request=event['template_upgrade']['request']
        if request['expected_note_carry_sha256']!=value['sha256'] or request['confirm_note_carry'] is not True:raise ValueError()
    except (KeyError,TypeError,ValueError,AttributeError,StopIteration):raise Conflict('version-one manual note carry proof invalid') from None


def validate(parent,plan,event,before,target,check,choice,affected,preserved):
    value=event['template_upgrade']['note_carry']
    if not isinstance(value,dict) or type(value.get('version')) is not int or value['version']!=1:raise Conflict('unsupported manual note carry version')
    return validate_v1(parent,plan,event,before,target,check,choice,affected,preserved)


def projection(checker,context,check,events,t,base,before,target):
    from . import service_case_steps as service
    from .template_migration import _compatible
    c,p,parent,_,_,_,scope=context;plan=parent['service_case_plan']
    annotations=plan['owner_amendments'];blockers=[b for b in base['blockers'] if b!='OWNER_NOTE_CONTROLLED_CARRY_REQUIRED_FOR_APPLICATION']
    result=dict(schema=1,eligible=False,blockers=[],proof=None,preview_sha256=None,notes=deepcopy(annotations),
        affected=base['affected'],preserved=base['preserved'],template_source_changed=before['snapshot']['definition']['source']!=target['snapshot']['definition']['source'],
        previous_template_source=deepcopy(before['snapshot']['definition']['source']),target_template_source=deepcopy(target['snapshot']['definition']['source']),
        previous_content_version=before['snapshot']['content_version'],target_content_version=target['snapshot']['content_version'],manual_preserved=True,requires_confirmation=True,semantic_evaluated=False)
    try:
        note=_manual(annotations,plan)
        if base['structure_change'] is not None or not _compatible(before['snapshot'],target['snapshot']):blockers.append('SAME_STRUCTURE_COMPATIBLE_TEMPLATE_REQUIRED')
        if [s['adapter_id'] for s in plan['steps']]!=['P1','P2','P3','P4','P5']:blockers.append('COMPLETE_REGISTERED_CASE_REQUIRED')
        reasons=notes.adoption_blockers(c,parent,plan)
        if reasons:blockers+=reasons
        binding,issues,_,_,states,_=service._inspect(checker.consumer.store,c,parent,deepcopy(plan),observe=False,fresh_clock=True)
        if binding or any(states[s['adapter_id']]!='VERIFIED' or issues[s['adapter_id']] for s in plan['steps']):blockers.append('CURRENT_VERIFIED_CASE_SOURCES_REQUIRED')
        current=sorted(notes._materials(c,parent),key=lambda m:m['slot'])
        material_proof=dict(current=current,current_epochs=_epochs_for(c,parent,current),captured_epochs=_epochs_for(c,parent,note['source_package']))
        versions=case_versions(c,parent,p);ledger=op.ledger(parent)
        choice=events[-1] if events else None
        if choice is not None:
            proof=proof_v1(scope,plan,plan['revision'],annotations,dict(revision=ledger['revision'],sha256=ledger['events'][-1]['sha256']),material_proof,versions,before,target,check,choice,base['affected'],base['preserved'])
            result.update(proof=proof,preview_sha256=proof['sha256'])
    except (Conflict,ValueError,TypeError,KeyError,StopIteration,AttributeError):blockers.append('CURRENT_KNOWN_MANUAL_NOTE_AND_SOURCE_PROOF_REQUIRED')
    result.update(eligible=not blockers,blockers=sorted(set(blockers)))
    return result
