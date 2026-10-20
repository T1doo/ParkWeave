"""Exact registered employees assertion history; never a truth or authority grant.

The optional protocol keeps the aggregate source graph frozen. Historical nodes
are rebuilt from their original confirmation prefix, never from current facts.
"""
from copy import deepcopy
import re
from uuid import UUID
from pydantic import ValidationError
from .domain import FactInput
from . import case_fact_clarifications as facts, fact_history_read_source as history
from . import controlled_plans as cp, preparation as prep, executor_receipts as er
from .store import Conflict, Denied

SCOPE = 'EMPLOYEES_USER_ASSERTION_V1'
PUBLIC_SCOPE = 'EMPLOYEES_FACT_PROVENANCE_PREVIEW'
MANUAL_SCOPE = 'EMPLOYEES_USER_ASSERTION_MANUAL_V1'
MANUAL_PUBLIC_SCOPE = 'EMPLOYEES_MANUAL_PROVENANCE_PREVIEW'
ERRORS = (Conflict, Denied, ValidationError, ValueError, KeyError, TypeError, AttributeError, IndexError, OverflowError, RecursionError)
EVENT_KEYS = {'id','action','revision','preparation_revision','actor_id','reason','decided_at','source_sha256','source_snapshot','applicable','choices','selection','authenticity','decision_sha256'}
ROW_KEYS = {'id','evidence_id','field_name','value','unit','source_ref','source_kind','source_excerpt','valid_from','valid_until','revision','fingerprint','confirmed_by'}


def _sha(value):
    if type(value) is not str or re.fullmatch('[a-f0-9]{64}', value) is None:
        raise ValueError('exact SHA256 required')


def _uuid(value):
    if type(value) is not str or str(UUID(value)) != value:
        raise ValueError('canonical UUID required')


def _receipts(parent, ledger):
    """Reconstruct only deterministic receipt bindings, without keys or IDs."""
    output=[]
    for index,event in enumerate(ledger['events'],1):
        if index==1:
            command=facts.Declare(expected_preparation_revision=event['preparation_revision']-1,
                profile=facts.PROFILE,purpose=facts.PURPOSE,reason=event['reason'])
        else:
            command=facts.Confirm(expected_preparation_revision=event['preparation_revision']-1,
                expected_clarification_revision=index-1,expected_source_sha256=event['source_sha256'],
                choices=event['choices'],reason=event['reason'])
        prefix=dict(ledger,revision=index,events=ledger['events'][:index])
        payload=dict(preparation_id=str(parent['id']),case_id=str(parent['case_id']),run_id=str(parent['run_id']),
            revision=event['preparation_revision'],action=event['action'],actor_id=parent['owner_id'],
            decision_ref=event['id'],decision_sha256=event['decision_sha256'],required_fields=list(facts.FIELDS),
            state='IN_PREPARATION',scope='SYNTHETIC_LOCAL_PREPARATION_ONLY',qualification='NOT_EVALUATED',
            external_acceptance='NOT_SUBMITTED',offline_fulfillment='NO_EVIDENCE',reason=event['reason'],
            public_status=facts.public_status(facts._result(prefix,'CURRENT' if index>1 else 'UNKNOWN',
                () if index>1 else ('FACT_PURPOSE_SELECTION_REQUIRED',),event['source_sha256'])))
        output.append(dict(preparation_id=str(parent['id']),actor_id=parent['owner_id'],revision=event['preparation_revision'],
            action=event['action'],fingerprint=facts._hash(dict(preparation_id=str(parent['id']),action=event['action'],**command.model_dump(mode='json'))),
            payload=payload))
    return output


def _prefix(parent,descriptor,registered_preparation_revision):
    if type(registered_preparation_revision) is not int or not 1<=registered_preparation_revision<=parent['revision']:
        raise ValueError("registered preparation revision unavailable")
    if type(descriptor) is not dict:
        raise ValueError('registered fact descriptor required')
    required={'enabled','state','satisfied','issues','revision','decision_ref','decision_sha256','source_sha256','profile','purpose','required_fields','qualification','authenticity','descriptor_sha256'}
    if set(descriptor)!=required or descriptor['enabled'] is not True or descriptor['state']!='CURRENT' or descriptor['satisfied'] is not True or descriptor['issues']!=[]:
        raise ValueError('known original fact descriptor required')
    if (type(descriptor['revision']) is not int or descriptor['revision']<2 or descriptor['profile']!=facts.PROFILE or
        descriptor['purpose']!=facts.PURPOSE or descriptor['required_fields']!=list(facts.FIELDS) or
        descriptor['qualification']!='NOT_EVALUATED' or descriptor['authenticity']!='USER_ASSERTED_UNVERIFIED'):
        raise ValueError('unsupported fact descriptor')
    for key in ('decision_sha256','source_sha256','descriptor_sha256'):_sha(descriptor[key])
    _uuid(descriptor['decision_ref'])
    if descriptor['descriptor_sha256']!=facts._hash({k:v for k,v in descriptor.items() if k!='descriptor_sha256'}):
        raise ValueError('descriptor digest changed')
    ledger=facts._ledger(parent)
    if ledger is None or type(ledger['version']) is not int or set(ledger)!={'version','profile','purpose','required_fields','revision','events'}:
        raise ValueError('original ledger required')
    matches=[event for event in ledger['events'] if event.get('id')==descriptor['decision_ref']]
    if len(matches)!=1:raise ValueError('unique original decision required')
    event=matches[0];index=descriptor['revision']
    if event['revision']!=index or ledger['events'][index-1]!=event or event['decision_sha256']!=descriptor['decision_sha256'] or event['source_sha256']!=descriptor['source_sha256']:
        raise ValueError('registered decision binding changed')
    if event['preparation_revision']>registered_preparation_revision or any(type(later.get('preparation_revision')) is not int or later['preparation_revision']<=registered_preparation_revision for later in ledger['events'][index:]):
        raise ValueError('registered decision was not latest at original source revision')
    prefix=deepcopy(dict(ledger,revision=index,events=ledger['events'][:index]))
    previous=0;seen=set()
    for n,e in enumerate(prefix['events'],1):
        if type(e) is not dict or set(e)!=EVENT_KEYS:raise ValueError('closed original event required')
        _uuid(e['id']);_sha(e['decision_sha256']);_sha(e['source_sha256']);history._utc(e['decided_at'])
        if e['id'] in seen or type(e['revision']) is not int or e['revision']!=n or type(e['preparation_revision']) is not int or not previous<e['preparation_revision']<=parent['revision']:
            raise ValueError('event sequence changed')
        seen.add(e['id']);previous=e['preparation_revision']
        snap=e['source_snapshot']
        if type(snap) is not dict or set(snap)!={'binding','sources'} or type(snap['binding']) is not dict or type(snap['sources']) is not list or len(snap['sources'])>60 or e['source_sha256']!=facts._hash(snap):
            raise ValueError('original snapshot unavailable')
        ids=set()
        for row in snap['sources']:
            if type(row) is not dict or set(row)!=ROW_KEYS:raise ValueError('unsupported original source row')
            _uuid(row['id']);_uuid(row['evidence_id']);_sha(row['fingerprint'])
            if row['id'] in ids or row['field_name'] not in facts.FIELDS or type(row['revision']) is not int or row['revision']<1 or type(row['unit']) is not str or type(row['source_excerpt']) is not str or row['confirmed_by']!=parent['owner_id']:
                raise ValueError('source row identity changed')
            ids.add(row['id'])
            ref=row['source_ref']
            if type(ref) is not dict or set(ref)!={'kind','id','revision'} or ref['kind']!='SYNTHETIC' or any(type(ref[k]) is not str or not ref[k] for k in ('id','revision')):
                raise ValueError('source reference unavailable')
            if history._utc(row['valid_until'])<=history._utc(row['valid_from']):raise ValueError('source interval changed')
            if row['source_kind']=='USER_ASSERTED_SYNTHETIC':
                FactInput.model_validate(dict(schema_version='parkweave-domain/1.0-draft',field=row['field_name'],value=row['value'],unit=row['unit'],
                    source_ref=row['source_ref'],source_excerpt=row['source_excerpt'],validity=dict(valid_from=row['valid_from'],valid_until=row['valid_until'],timezone='UTC')))
        if type(e['applicable']) is not dict or set(e['applicable'])!=ids or any(type(v) is not bool for v in e['applicable'].values()):raise ValueError('original applicability unavailable')
        if e['decision_sha256']!=facts._hash({k:v for k,v in e.items() if k!='decision_sha256'}):raise ValueError('event digest changed')
    # Existing strict owner/tenant/Case/Run, original request fingerprints,
    # choices, field identities and source-row checks, evaluated at THIS prefix.
    bindings=_receipts(parent,prefix)
    receipts=[dict(row,request_key='prefix-'+str(i)) for i,row in enumerate(bindings)]
    local=deepcopy(parent);local['fact_clarifications']=prefix
    local['goal']=event['source_snapshot']['binding']['goal']
    local['request_intent']=event['source_snapshot']['binding']['request_intent']
    principal=dict(id=parent['owner_id'],park_id=parent['park_id'],org_id=parent['org_id'],role='enterprise_operator',active=True)
    history.project(local,principal,receipts,event['source_snapshot']['sources'],event['applicable'],event['decided_at'])
    choices=[facts.Choice.model_validate(x) for x in event['choices']]
    choice=[x for x in choices if x.field=='employees']
    if len(choice)!=1:raise ValueError('unique employees choice required')
    selected=[row for row in event['source_snapshot']['sources'] if row['id']==str(choice[0].assertion_id)]
    if len(selected)!=1 or selected[0]['source_kind']!='USER_ASSERTED_SYNTHETIC':raise ValueError('supported employees assertion required')
    row=selected[0]
    node=dict(field='employees',assertion_ref=row['id'],assertion_revision=row['revision'],assertion_fingerprint=row['fingerprint'],
        assertion_sha256=facts._hash(row),source_kind=row['source_kind'],source_ref_sha256=facts._hash(row['source_ref']),
        valid_from=row['valid_from'],valid_until=row['valid_until'],decision_ref=event['id'],decision_revision=index,
        decision_sha256=event['decision_sha256'],source_sha256=event['source_sha256'],descriptor_sha256=descriptor['descriptor_sha256'],
        ledger_prefix_sha256=facts._hash(prefix),receipt_bindings_sha256=facts._hash(bindings),authenticity='USER_ASSERTED_UNVERIFIED')
    node['sha256']=facts._hash(node)
    return node,bindings


def project(parent,before_sources,current_sources):
    """Pure bounded reconstruction; caller retains original aggregate partition."""
    before,bindings_before=_prefix(parent,before_sources['P1']['fact_clarification'],before_sources['P1']['preparation_revision'])
    current,bindings_current=_prefix(parent,current_sources['P1']['fact_clarification'],current_sources['P1']['preparation_revision'])
    selected_keys=('assertion_ref','assertion_revision','assertion_fingerprint','assertion_sha256','source_ref_sha256','valid_from','valid_until')
    selected_changed=any(before[k]!=current[k] for k in selected_keys)
    result=dict(version=1,scope=SCOPE,before=before,current=current,selected_changed=selected_changed,
        aggregate_changed=before_sources['P1']['fact_clarification']!=current_sources['P1']['fact_clarification'],
        authenticity='USER_ASSERTED_UNVERIFIED',new_grants=False)
    result['sha256']=facts._hash(result)
    return result,bindings_current


def _capture(c,parent,bindings):
    rows=c.execute("SELECT id,preparation_id,actor_id,revision,action,payload,request_key,fingerprint,xmin::text AS row_version FROM preparation_events WHERE preparation_id=%s AND action IN ('DECLARE_FACT_PURPOSE','CONFIRM_FACT_PURPOSE') ORDER BY revision,id LIMIT 65",(parent['id'],)).fetchall()
    if len(rows)>64 or len(rows)!=len(bindings):raise ValueError('complete unique receipt set required')
    seen=set()
    for expected in bindings:
        matches=[r for r in rows if r['revision']==expected['revision'] and r['action']==expected['action']]
        if len(matches)!=1:raise ValueError('original actual receipt unavailable')
        actual=matches[0]
        if any(not history._same(facts._normal(actual[k]),expected[k]) for k in ('preparation_id','actor_id','revision','action','fingerprint')) or not history._same(actual['payload'],expected['payload']):
            raise ValueError('actual receipt binding changed')
        if type(actual['request_key']) is not str or not actual['request_key'].strip() or len(actual['request_key'])>200 or actual['request_key'] in seen:raise ValueError('actual receipt key changed')
        seen.add(actual['request_key'])
    row=c.execute('SELECT fact_clarifications,xmin::text AS row_version FROM preparations WHERE id=%s',(parent['id'],)).fetchone()
    if not history._same(row['fact_clarifications'],parent['fact_clarifications']):raise ValueError('fact ledger changed during capture')
    return facts._hash(dict(ledger=row,receipts=rows))


def _manual_snapshot(parent,plan,revision):
    """Replay the note at THIS plan prefix, never the latest owner_amendments."""
    from . import plan_source_conflicts as notes, material_package_continuation as package
    if (type(revision) is not int or type(plan['revision']) is not int or not 1<=revision<=plan['revision']<=64
            or plan.get('template_migration') or plan.get('partial_adoption')):
        raise ValueError('bounded original non-template full plan required')
    prefix=deepcopy(plan)
    prefix['events']=[e for e in plan['events'] if e['revision']<=revision]
    if (len(prefix['events'])!=revision or any(type(e['revision']) is not int or e['revision']!=i
            for i,e in enumerate(prefix['events'],1)) or package.active(prefix)):
        raise ValueError('complete non-package manual prefix required')
    events=[e for e in prefix['events'] if e['action'] in notes.ACTIONS]
    if not events:raise ValueError('original manual note event required')
    latest=events[-1];note=deepcopy(latest['plan_note']['after_note'])
    p1=[step for step in plan['steps'] if step['adapter_id']=='P1']
    if len(p1)!=1 or not note or note['origin']!='MANUAL' or note['step_id']!=p1[0]['id']:
        raise ValueError('unique original P1 MANUAL note required')
    prefix['revision']=revision;prefix['owner_amendments']={p1[0]['id']:note}
    notes.validate_plan_history(parent,prefix)
    proof=dict(version=1,scope=MANUAL_SCOPE,plan_id=plan['id'],plan_revision=revision,
        step_id=p1[0]['id'],note=note,note_sha256=cp._hash(note),
        latest_decision=dict(id=latest['id'],revision=latest['revision'],action=latest['action'],
            fingerprint=latest['fingerprint'],proof_sha256=latest['plan_note']['sha256']),
        note_history_sha256=cp._hash(events))
    proof['sha256']=cp._hash(proof)
    return proof


def enhance(c,parent,result,change,affected,*,scope=SCOPE):
    result=deepcopy(result);change=deepcopy(change)
    result['scope']=MANUAL_PUBLIC_SCOPE if scope==MANUAL_SCOPE else PUBLIC_SCOPE
    plan=parent['service_case_plan']
    reasons=[]
    if scope!=MANUAL_SCOPE and (plan.get('owner_amendments') or plan.get('template_migration')):
        reasons.append('FACT_PROVENANCE_COMBINATION_UNSUPPORTED')
    try:
        if reasons:raise ValueError()
        manual=_manual_snapshot(parent,plan,plan['revision']) if scope==MANUAL_SCOPE else None
        if manual is not None and not history._same(plan.get('owner_amendments'),{manual['step_id']:manual['note']}):
            raise ValueError('current manual body differs from original note events')
        proof,bindings=project(parent,change['before_sources'],change['current_sources'])
        # Capture every retained prefix receipt, not merely the selected current
        # row. Before may be older but must resolve to the exact original event.
        ledger=facts._ledger(parent)
        capture=_capture(c,parent,_receipts(parent,ledger))
        change.update(version=5 if manual is not None else 3,fact_provenance=proof,fact_provenance_capture_sha256=capture)
        if manual is not None:
            change['manual_provenance']=manual
            result['manual_provenance']=deepcopy(manual)
        change['sha256']=cp._hash({k:v for k,v in change.items() if k!='sha256'})
        result.update(fact_provenance=proof,preview_sha256=change['sha256'])
        result['adoption']['fact_provenance_scope']=scope
        result['adoption']['opportunity_proof']['expected_preview_sha256']=change['sha256']
    except ERRORS:
        reasons.append('EXACT_REGISTERED_EMPLOYEES_PROVENANCE_REQUIRED')
        if scope==MANUAL_SCOPE:
            reasons.append('EXACT_ORIGINAL_MANUAL_PROVENANCE_REQUIRED')
            result['manual_provenance']=None
        ids=[s['id'] for s in plan['steps']]
        result.update(fact_provenance=None,unknown_scope='THIS_CASE',directly_changed=ids,affected=ids,preserved=[],adoption=None)
        affected={s['adapter_id'] for s in plan['steps']}
    result['blocking_reasons']=sorted(set(result['blocking_reasons']+reasons))
    result['can_adopt']=not result['blocking_reasons']
    return result,change,affected


def validate_history(parent,plan,event,previous_dependencies,current_dependencies):
    """v3/v5 dispatch normalizes only proven extensions for frozen v2 validation."""
    from . import source_change_adoption as original
    change=event['local_revision']['source_change']
    request=event['local_revision']['request']
    manual=request.get('fact_provenance_scope')==MANUAL_SCOPE
    expected_version=5 if manual else 3
    if (request.get('fact_provenance_scope') not in (SCOPE,MANUAL_SCOPE) or
            change.get('version')!=expected_version or type(change['version']) is not int):
        raise ValueError('explicit fact provenance scope/version pair required')
    if manual:
        expected_manual=_manual_snapshot(parent,plan,event['revision']-1)
        if not history._same(expected_manual,change.get('manual_provenance')):
            raise ValueError('historical manual provenance changed')
    _sha(change.get('fact_provenance_capture_sha256'))
    if change.get('sha256')!=cp._hash({k:v for k,v in change.items() if k!='sha256'}) or request['opportunity_proof']['expected_preview_sha256']!=change['sha256']:
        raise ValueError('fact provenance preview binding invalid')
    if (type(request.get('expected_preparation_revision')) is not int or type(change['current_sources'].get('P1',{}).get('preparation_revision')) is not int or
        change['current_sources']['P1']['preparation_revision']>request['expected_preparation_revision']):
        raise ValueError('historical current fact is later than original ADOPT')
    expected,_=project(parent,change['before_sources'],change['current_sources'])
    if not history._same(expected,change.get('fact_provenance')):raise ValueError('historical fact provenance changed')
    canonical=deepcopy(event);patch=canonical['local_revision'];change=patch['source_change']
    change.pop('fact_provenance');change.pop('fact_provenance_capture_sha256')
    if manual:change.pop('manual_provenance')
    change['version']=2
    change['sha256']=cp._hash({k:v for k,v in change.items() if k!='sha256'})
    patch['request'].pop('fact_provenance_scope')
    patch['request']['opportunity_proof']['expected_preview_sha256']=change['sha256']
    return original.validate_history(parent,plan,canonical,previous_dependencies,current_dependencies)


@er.bounded
def read(store,token,id,card_id=None,*,scope=SCOPE):
    from . import source_change_adoption as original
    from .service_case_steps import _context
    with store.connect() as c:
        principal,parent=_context(store,c,token,id)
        if principal['role']!='enterprise_operator' or parent['service_id']!=prep.SERVICE or 'opportunities' not in parent:
            raise Denied('existing synthetic owner opportunity Case required')
        store.check_fields(c,principal,list(facts.FIELDS),'READ')
        if card_id is None:
            return dict(scope=MANUAL_PUBLIC_SCOPE if scope==MANUAL_SCOPE else PUBLIC_SCOPE,**({'manual_provenance':None} if scope==MANUAL_SCOPE else {}),preparation_id=str(parent['id']),card_id=None,can_adopt=False,
                fact_provenance=None,unknown_scope='THIS_CASE',blocking_reasons=['EXPLICIT_OPPORTUNITY_CARD_REQUIRED'],new_grants=False)
        return original.build(store,c,principal,parent,card_id,fact_provenance_scope=scope)[0]
