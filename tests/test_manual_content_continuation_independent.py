"""Independent literal manual preservation through real HTTP/ASGI/owned PG."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import selectors
import subprocess
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

import test_at24_27_change_batch_independent as previous
import test_new_enterprise_local_chain as chain
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture, headers, command as prepare, add as material_add, read as preparation_read
from test_new_enterprise_local_chain import fresh_chain, ALL_GOALS, call, report_and_ack
from test_service_case_steps import read as plan_read, command as plan_command, verified
from test_service_plan_manual_lock import stored, lock
from test_case_opportunities import get as opportunities, post as opportunity_post, body as opportunity_body, entry
from test_source_change_adoption import preview, adopt
from test_registered_local_revision import patch, patch_body
from test_case_resources import get as resource_link_read, post as resource_link_write
from test_service_dispatches import offer as dispatch_offer, command as dispatch_command
from test_case_lifecycle import read as local_read, act as local_command

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'pyproject.toml').is_file())
OUT = ROOT / '.runtime/manual-continuation-independent'
RUN_ID = uuid4().hex
ORACLE = json.loads((ROOT/'docs/F2/ManualContentContinuationOracles-20261015.json').read_text())
BASE_SOURCE = ORACLE['three_versions']['B']['text']
MANUAL = ORACLE['three_versions']['M']['text']
INCOMING = ORACLE['three_versions']['S']['text']
THIRD = ORACLE['three_versions']['S3']['text']
NEW = ('KEEP_AND_CONTINUE', 'MERGE_NOTE')


def record(kind, value):
    OUT.mkdir(parents=True, exist_ok=True)
    row = dict(value, run_id=RUN_ID, source_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
               utc=datetime.now(timezone.utc).isoformat(), test=os.environ.get('PYTEST_CURRENT_TEST'))
    with (OUT / (kind+'-'+RUN_ID+'.jsonl')).open('a') as stream:
        stream.write(json.dumps(row, sort_keys=True, default=str)+'\n')
    return row


@pytest.fixture
def cases(fresh_chain, tmp_path):
    # Only a runtime artifact destination is changed. The original fixture,
    # original commands and all six actual goals are used without modification.
    saved = previous.OUT
    previous.OUT = OUT / 'baseline'
    saved_input = chain.input_body
    def literal_input(*args, **kwargs):
        data=saved_input(*args,**kwargs)
        for material in data['materials']:
            if material['slot']=='material_outline':material['text']=BASE_SOURCE
        return data
    # Feed the literal B through the original new-Case HTTP input. Never rewrite
    # an already verified historical row to make a different baseline appear.
    chain.input_body=literal_input
    generator = previous.two_cases.__wrapped__(fresh_chain, tmp_path)
    try:
        t = next(generator)
        chain.input_body=saved_input
        t['baseline_source'] = deepcopy(note_read(t)['source'])
        assert t['baseline_source']['text']==BASE_SOURCE and t['baseline_source']['version']==1
        record('baseline', dict(cases={label: dict(case_id=row['case_id'], preparation_id=row['preparation_id'],
            plan_id=t['initial'][label]['id'], step_ids={s['adapter_id']:s['id'] for s in t['initial'][label]['steps']},
            required_goals=t['initial'][label]['required_goals']) for label,row in t['rows'].items()},
            original_source=t['baseline_source'], original_module_output_redirect=str(previous.OUT)))
        yield t
    finally:
        generator.close()
        previous.OUT = saved
        chain.input_body=saved_input


def note_path(t, label='A'):
    return '/api/preparations/'+t['rows'][label]['preparation_id']+'/plan-source-conflicts'


def note_response(t, card=None, label='A', actor='fixture-a'):
    return t['f'][3].get(note_path(t,label), headers=headers(t['f'][2],actor), params={'card_id':card['id']} if card else {})


def note_read(t, card=None):
    r=note_response(t,card);assert r.status_code==200,r.text
    return r.json()


def body(view, action, text=None):
    value = dict(schema=1, action=action, expected_plan_id=view['plan_id'], expected_plan_revision=view['plan_revision'],
        expected_note_revision=view['note']['revision'] if view['note'] else 0,
        expected_ledger_revision=view['opportunity_revision'], card_id=view['card_id'], text=text,
        reason='SYNTHETIC independent explicit '+action)
    value['expected_preview_sha256'] = (view['continuation']['preview_sha256'] if action in NEW else view['preview_sha256']) or '0'*64
    return value


def write(t, data, key=None, actor='fixture-a', label='A'):
    return t['f'][3].post(note_path(t,label)+'/commands', headers=headers(t['f'][2],actor,key or uuid4().hex), json=data)


def change_material(t, text):
    p=preparation_read(t['f'],t['rows']['A']).json()['preparation']
    p=dict(p,preparation_id=t['rows']['A']['preparation_id'])
    if p['state'] in ('REVIEWED','LOCAL_CONFIRMED'):
        response=prepare(t['f'],p,'REOPEN',reason='SYNTHETIC new actual source revision')
        assert response.status_code==200,response.text
        p=response.json()
    response=material_add(t['f'],p,slot='material_outline',text=text)
    assert response.status_code==200,response.text


def import_refresh(t):
    f=t['f'];p=t['rows']['A']
    value=opportunities(f,p).json()
    if not value['cards']:
        r=opportunity_post(f,p,opportunity_body(value,item=entry()));assert r.status_code==200,r.text
        value=r.json()['current']
    r=opportunity_post(f,p,opportunity_body(value,'REFRESH'));assert r.status_code==200,r.text
    return next(c for c in r.json()['current']['cards'] if c['is_latest_generation'])


def conflict(t, text=MANUAL, source=INCOMING, locked=False):
    initial=note_read(t);r=write(t,body(initial,'EDIT_NOTE',text));assert r.status_code==200,r.text
    if locked:assert lock(t['f'],t['rows']['A'],'P1').status_code==200
    change_material(t,source);card=import_refresh(t);view=note_read(t,card)
    assert view['note']['text']==text and view['source']['text']==source
    assert view['continuation']['baseline']==t['baseline_source']
    assert view['continuation']['manual']['text']==text and view['continuation']['incoming']==view['source']
    assert view['continuation']['semantic_evaluated'] is False
    return card,view


def refuse(t, data, *, actor='fixture-a', label='A', expected=409):
    before=previous.full_business(t)
    response=write(t,data,actor=actor,label=label)
    assert response.status_code==expected,response.text
    assert previous.full_business(t)==before
    record('refusals',dict(action=data['action'],status=response.status_code,no_business_write=True,actor=actor))
    return response


def partition(t, view, scenario, unknown=False):
    for label,wanted in [('A',{'P1','P2','P3','P4','P5'}),('B',set())]:
        graph=previous.source_graph(t['f'],t['rows'][label])['source_impact']
        ids={s['adapter_id']:s['id'] for s in t['initial'][label]['steps']}
        want={ids[s] for s in wanted};keep=set(ids.values())-want
        got=set(graph['affected']);preserved=set(graph['preserved'])
        row=record('oracle',dict(scenario=scenario,case=label,expected_affected=sorted(want),actual_affected=sorted(got),
            expected_preserved=sorted(keep),actual_preserved=sorted(preserved),intentional_unknown=unknown,
            missed_count=len(want-got),wrong_count=len(got-want),wrong_preserved_count=len(keep^preserved)))
        assert want==got and keep==preserved,row


def adopt_rejection(t, card):
    f=t['f'];p=t['rows']['A'];v=preview(f,p,card);assert v.status_code==200,v.text
    before=previous.full_business(t);r=adopt(f,p,v.json()['adoption']);assert r.status_code==409,r.text
    assert previous.full_business(t)==before
    data=patch_body(f,p);before=previous.full_business(t);r=patch(f,p,body=data)
    assert r.status_code==409 and previous.full_business(t)==before
    record('refusals',dict(scenario='BOTH_ORIGINAL_LOCAL_ADOPT_ENTRIES',status=409,no_business_write=True))


def test_three_actual_versions_keep_edit_continue_does_not_grant_future_source(cases):
    t=cases;card,v=conflict(t);partition(t,v,'THREE_WAY_MATERIAL')
    assert not v['continuation']['coverage_satisfied'];refuse(t,body(v,'KEEP_AND_CONTINUE'))
    v=note_read(t,card);r=write(t,body(v,'EDIT_NOTE',MANUAL+'\n'+INCOMING));assert r.status_code==200,r.text
    v=note_read(t,card);assert v['continuation']['coverage_satisfied'] and v['continuation']['can_keep_and_continue']
    r=write(t,body(v,'KEEP_AND_CONTINUE'));assert r.status_code==200,r.text
    after=r.json()['current'];assert after['state']=='CONTINUED_AWAITING_RECHECK'
    assert after['note']['origin']=='MANUAL' and after['note']['text']==MANUAL+'\n'+INCOMING
    assert after['note']['source_ref']['id']==v['source']['id']
    assert after['note']['verified_package_sha256'] is None
    old_request=body(note_read(t,card),'KEEP_AND_CONTINUE')
    change_material(t,THIRD);card=import_refresh(t);v=note_read(t,card)
    assert v['source']['text']==THIRD and v['continuation']['baseline']['text']==INCOMING
    assert not v['continuation']['coverage_satisfied'];refuse(t,old_request);adopt_rejection(t,card)
    assert stored(t['f'],t['rows']['B'])==t['initial']['B']


@pytest.mark.parametrize('kind',['delete_manual','normalize_manual'])
def test_merge_must_preserve_complete_contiguous_manual_bytes(cases,kind):
    t=cases;card,v=conflict(t)
    candidate=INCOMING if kind=='delete_manual' else MANUAL.replace('  ',' ')+'\n'+INCOMING
    assert MANUAL not in candidate
    refuse(t,body(v,'MERGE_NOTE',candidate))


@pytest.mark.parametrize('source,manual,expected',[
    ('DUP\nDUP','manual\nDUP',{'DUP':(2,1,1)}),
    ('HEADER\n  EXACT  \nSECOND','manual\nHEADER\nEXACT\nSECOND',{'HEADER':(1,1,0),'  EXACT  ':(1,0,1),'SECOND':(1,1,0)}),
    ('CaseSensitive','manual\ncasesensitive',{'CaseSensitive':(1,0,1)}),
])
def test_literal_source_lines_require_counts_original_whitespace_and_case(cases,source,manual,expected):
    t=cases;card,v=conflict(t,text=manual,source=source);c=v['continuation']
    actual={x['line']:(x['required_count'],x['present_count'],x['missing_count']) for x in c['conditions']}
    assert actual==expected and c['coverage_known'] and not c['coverage_satisfied']
    refuse(t,body(v,'KEEP_AND_CONTINUE'))


@pytest.mark.parametrize('count',[128,129])
def test_actual_source_condition_bound_is_not_vacuous_or_extended(cases,count):
    source='\n'.join('condition-'+str(i) for i in range(count));t=cases
    card,v=conflict(t,text=MANUAL+'\n'+source,source=source);c=v['continuation']
    assert c['coverage_known'] is (count==128)
    assert c['can_keep_and_continue'] is (count==128)
    if count==129:refuse(t,body(v,'KEEP_AND_CONTINUE'))
    else:
        r=write(t,body(v,'KEEP_AND_CONTINUE'));assert r.status_code==200,r.text


@pytest.mark.parametrize('drop_conditions',[False,True])
def test_edit_after_continue_always_requires_new_explicit_decision(cases,drop_conditions):
    t=cases;card,v=conflict(t,text=MANUAL+'\n'+INCOMING)
    r=write(t,body(v,'KEEP_AND_CONTINUE'));assert r.status_code==200,r.text
    v=note_read(t,card);draft=MANUAL+'\nnew human comment'+('' if drop_conditions else '\n'+INCOMING)
    r=write(t,body(v,'EDIT_NOTE',draft));assert r.status_code==200,r.text
    adopt_rejection(t,card);v=note_read(t,card)
    if drop_conditions:
        refuse(t,body(v,'KEEP_AND_CONTINUE'));v=note_read(t,card)
        r=write(t,body(v,'EDIT_NOTE',draft+'\n'+INCOMING));assert r.status_code==200,r.text
    v=note_read(t,card);r=write(t,body(v,'KEEP_AND_CONTINUE'));assert r.status_code==200,r.text
    v=preview(t['f'],t['rows']['A'],card);assert v.status_code==200 and v.json()['can_adopt']


@pytest.mark.parametrize('action',['KEEP_MANUAL','DEFER'])
def test_old_keep_and_defer_never_become_continuation(cases,action):
    t=cases;card,v=conflict(t,text=MANUAL+'\n'+INCOMING)
    r=write(t,body(v,action));assert r.status_code==200,r.text
    assert r.json()['current']['note']['text']==MANUAL+'\n'+INCOMING
    adopt_rejection(t,card)


@pytest.mark.parametrize('action',NEW)
def test_original_p1_unlock_is_required_for_new_continuation(cases,action):
    t=cases;card,v=conflict(t,text=MANUAL+'\n'+INCOMING,locked=True);old=deepcopy(stored(t['f'],t['rows']['A'])['steps'][0]['manual_lock'])
    refuse(t,body(v,action,MANUAL+'\n'+INCOMING if action=='MERGE_NOTE' else None))
    assert stored(t['f'],t['rows']['A'])['steps'][0]['manual_lock']==old
    assert plan_command(t['f'],t['rows']['A'],'P1','UNLOCK').status_code==200
    v=note_read(t,card);r=write(t,body(v,action,MANUAL+'\n'+INCOMING if action=='MERGE_NOTE' else None));assert r.status_code==200,r.text


@pytest.mark.parametrize('mutation',['source','manual','card','plan'])
def test_new_continuation_proof_rejects_source_note_card_and_plan_aba(cases,mutation):
    t=cases;card,v=conflict(t,text=MANUAL+'\n'+INCOMING);data=body(v,'KEEP_AND_CONTINUE')
    if mutation=='source':
        # Owned-PG fault injection: the temporary row need not form a coherent
        # material package. Verify actual storage rather than claiming an
        # old-card UNKNOWN projection must expose an authoritative source.
        with t['f'][1].connect() as c:
            before=c.execute('SELECT *,xmin::text AS fixture_epoch FROM preparation_evidence WHERE id=%s',(v['source']['id'],)).fetchone()
        for text in (THIRD,INCOMING):
            digest=hashlib.sha256(text.encode()).hexdigest()
            with t['f'][1].connect() as c:
                c.execute('UPDATE preparation_evidence SET text=%s,source_sha256=%s WHERE id=%s',(text,digest,v['source']['id']))
                current=c.execute('SELECT text,source_sha256 FROM preparation_evidence WHERE id=%s',(v['source']['id'],)).fetchone()
                assert current['text']==text and current['source_sha256']==digest
        with t['f'][1].connect() as c:
            after=c.execute('SELECT *,xmin::text AS fixture_epoch FROM preparation_evidence WHERE id=%s',(v['source']['id'],)).fetchone()
        assert {k:value for k,value in before.items() if k!='fixture_epoch'}=={k:value for k,value in after.items() if k!='fixture_epoch'}
        assert before['fixture_epoch']!=after['fixture_epoch']
        record('aba-fault-injections',dict(kind='OWNED_PG_SOURCE_ROW_ABA',business_command=False,entire_row_restored=True,epoch_changed=True))
    elif mutation=='manual':
        r=write(t,body(v,'EDIT_NOTE',MANUAL+'\n'+INCOMING+'\nextra'));assert r.status_code==200,r.text
        v=note_read(t,card);r=write(t,body(v,'EDIT_NOTE',MANUAL+'\n'+INCOMING));assert r.status_code==200,r.text
    elif mutation=='card':
        value=opportunities(t['f'],t['rows']['A']).json();r=opportunity_post(t['f'],t['rows']['A'],opportunity_body(value,item=entry(family_id=card['entry']['family_id'],generation=card['entry']['generation']+1)));assert r.status_code==200,r.text
    else:
        # Fault injection, not a legal LOCK on an already invalidated P1.
        # Two committed transactions restore the entire original plan, with no
        # business read or command between them; only the row epoch advances.
        preparation_id=t['rows']['A']['preparation_id']
        with t['f'][1].connect() as c:
            before=c.execute('SELECT service_case_plan,service_case_plan::text AS plan_bytes,xmin::text AS fixture_epoch FROM preparations WHERE id=%s',(preparation_id,)).fetchone()
        temporary=deepcopy(before['service_case_plan']);temporary['revision']+=1
        with t['f'][1].connect() as c:
            c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(temporary),preparation_id))
        with t['f'][1].connect() as c:
            c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(before['service_case_plan']),preparation_id))
        with t['f'][1].connect() as c:
            after=c.execute('SELECT service_case_plan,service_case_plan::text AS plan_bytes,xmin::text AS fixture_epoch FROM preparations WHERE id=%s',(preparation_id,)).fetchone()
        assert after['service_case_plan']==before['service_case_plan'] and after['plan_bytes']==before['plan_bytes']
        assert after['fixture_epoch']!=before['fixture_epoch']
        record('aba-fault-injections',dict(kind='OWNED_PG_PLAN_ROW_ABA',business_command=False,entire_plan_restored=True,epoch_changed=True))
    refuse(t,data)


@pytest.mark.parametrize('capability',['READ','EXECUTE'])
def test_current_authority_precedes_continuation_receipt(cases,capability):
    t=cases;card,v=conflict(t,text=MANUAL+'\n'+INCOMING);data=body(v,'KEEP_AND_CONTINUE');key=uuid4().hex
    r=write(t,data,key=key);assert r.status_code==200,r.text
    with t['f'][1].connect() as c:
        t['f'][1].lock_principal(c,'fixture-a',exclusive=True)
        c.execute('UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id=%s AND capability=%s',('fixture-a',capability))
    before=previous.full_business(t);r=write(t,data,key=key);assert r.status_code==403,r.text
    assert previous.full_business(t)==before


@pytest.mark.parametrize('actor',['fixture-b','fixture-c'])
def test_new_continuation_does_not_authorize_other_owner_or_tenant(cases,actor):
    t=cases;card,v=conflict(t,text=MANUAL+'\n'+INCOMING)
    refuse(t,body(v,'KEEP_AND_CONTINUE'),actor=actor,expected=403)


@pytest.mark.parametrize('kind',['missing_baseline','source_unknown'])
def test_unknown_actual_baseline_or_current_source_cannot_continue(cases,kind):
    t=cases;card,v=conflict(t,text=MANUAL+'\n'+INCOMING)
    # Capture complete, originally valid requests before the actual source is
    # made unavailable. UNKNOWN must not manufacture a new writable template.
    original=preview(t['f'],t['rows']['A'],card);assert original.status_code==200,original.text
    original_adoption=deepcopy(original.json()['adoption'])
    original_patch=patch_body(t['f'],t['rows']['A'])
    v=note_read(t,card);assert v['continuation']['can_keep_and_continue']
    original_continue=body(v,'KEEP_AND_CONTINUE')
    with t['f'][1].connect() as c:
        if kind=='missing_baseline':c.execute('DELETE FROM preparation_evidence WHERE id=%s',(t['baseline_source']['id'],))
        else:c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{kind}','\"UNKNOWN\"') WHERE park_id='park-a' AND service_id='synthetic-material-preparation' AND version=1")
    v=note_read(t,card);continuation=v.get('continuation')
    assert not (continuation or {}).get('can_keep_and_continue',False)
    assert not (continuation or {}).get('can_merge',False)
    assert not set(NEW).intersection(v['action_requests'])
    if kind=='source_unknown':assert v['state']=='UNKNOWN'
    refuse(t,original_continue)
    current=preview(t['f'],t['rows']['A'],card)
    assert current.status_code in (200,409),current.text
    if current.status_code==200:assert not current.json()['can_adopt']
    for entry_name,request in [('ORIGINAL_OPPORTUNITY_ADOPT',original_adoption),('ORIGINAL_PROOFLESS_LOCAL_ADOPT',original_patch)]:
        before=previous.full_business(t)
        response=adopt(t['f'],t['rows']['A'],request) if entry_name=='ORIGINAL_OPPORTUNITY_ADOPT' else patch(t['f'],t['rows']['A'],body=request)
        assert response.status_code==409,response.text
        assert previous.full_business(t)==before
        record('refusals',dict(scenario=entry_name,status=response.status_code,no_business_write=True,request_captured_before_unknown=True))


def test_continuation_idempotency_parameter_conflict_and_cold_get(cases):
    t=cases;card,v=conflict(t,text=MANUAL+'\n'+INCOMING);key=uuid4().hex;data=body(v,'KEEP_AND_CONTINUE')
    r=write(t,data,key=key);assert r.status_code==200,r.text;receipt=r.json()['receipt'];before=previous.full_business(t)
    r=write(t,data,key=key);assert r.status_code==200 and r.json()['receipt']==receipt
    r=write(t,{**data,'reason':'SYNTHETIC different parameters'},key=key);assert r.status_code==409
    recovered=t['f'][3].get(note_path(t)+'/recovery/'+key,headers=headers(t['f'][2]))
    assert recovered.status_code==200 and recovered.json()['receipt']==receipt and recovered.json()['historical_only']
    assert previous.full_business(t)==before


def html_controls(t):
    f=t['f'];u=t['u'];p=t['rows']['A'];state={}
    def changed():
        change_material(t,INCOMING);partition(t,{},'HTML_ACTUAL_MATERIAL')
    def remember():
        card=next(c for c in opportunities(f,p).json()['cards'] if c['is_latest_generation'])
        current=note_read(t,card);state['note']=deepcopy(current['note'])
    def before_adopt():
        state['plan']=deepcopy(stored(f,p));state['business']=previous.full_business(t)
    def after_adopt():
        old=state['plan'];current=stored(f,p)
        assert current['id']==old['id'] and current['required_goals']==ALL_GOALS
        assert [s['id'] for s in current['steps']]==[s['id'] for s in old['steps']]
        assert [s['contract'] for s in current['steps']]==[s['contract'] for s in old['steps']]
        assert current['owner_amendments']==old['owner_amendments']
        assert current['events'][:-1]==old['events'] and current['history']==old['history']
        assert set(current['events'][-1]['local_revision']['affected'])=={s['id'] for s in old['steps']}
        before=deepcopy(state['business']);after=previous.full_business(t)
        for value in (before,after):
            for parent in value['pg']['preparations']:parent.pop('service_case_plan')
        assert before==after
    def review_material():
        current=dict(preparation_read(f,p).json()['preparation'],preparation_id=p['preparation_id'])
        response=prepare(f,current,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC original changed source review')
        assert response.status_code==200,response.text
        response=prepare(f,response.json(),'CONFIRM',reason='SYNTHETIC original owner material confirmation')
        assert response.status_code==200,response.text
    def relink():
        value=resource_link_read(f,p).json();old=value['current']['record']
        current=dict(preparation_read(f,p).json()['preparation'],preparation_id=p['preparation_id'])
        response=resource_link_write(f,current,dict(id=old['combination_id']),revision=value['link_revision'])
        assert response.status_code==201,response.text
    def reoffer():
        current=dict(preparation_read(f,p).json()['preparation'],preparation_id=p['preparation_id'])
        dispatch_id=t['completed']['A']['dispatch']['dispatch_id']
        value=f[3].get('/api/service-dispatches/'+dispatch_id,headers=headers(f[2],'prep-specialist-fixture-a')).json()
        assert value['can_reoffer']
        response=dispatch_offer(f,current,revision=value['revision'],recovery_receipt_step_id=value['recovery_receipt_step_id'])[0]
        assert response.status_code==201,response.text
        response=dispatch_command(f,response.json(),'ACCEPT');assert response.status_code==200,response.text
        state['dispatch']=response.json()
    def report():report_and_ack(u,p,state['dispatch'])
    def revalidate():
        response=local_command(f,p,local_read(f,p).json(),'REVALIDATE');assert response.status_code==200,response.text
    def final():
        for label,row in t['rows'].items():
            plan=stored(f,row);initial=t['initial'][label]
            assert plan['id']==initial['id'] and plan['required_goals']==ALL_GOALS
            assert [s['id'] for s in plan['steps']]==[s['id'] for s in initial['steps']]
            assert plan['events'][:len(initial['events'])]==initial['events'] and plan['history']==initial['history']
            value=call(u,'/api/preparations/'+row['preparation_id']+'/goal-results')
            assert value['state']=='LOCAL_OUTPUTS_VERIFIED' and len(value['results'])==6 and not value['case_goal_completed']
        assert stored(f,t['rows']['B'])==t['initial']['B']
        assert next(iter(stored(f,p)['owner_amendments'].values()))==state['note']
        record('closures',dict(six_goals_current=True,original_ids_contract_history=True,unaffected_B_exact=True,manual_or_explicit_source=state['note']['origin']))
    def unresolved():
        card=next(c for c in opportunities(f,p).json()['cards'] if c['is_latest_generation'])
        response=preview(f,p,card);assert response.status_code in (200,409),response.text
        if 'before_unknown_adoption' in state:
            if response.status_code==200:assert not response.json()['can_adopt']
            requests=[('ORIGINAL_OPPORTUNITY_ADOPT_AFTER_UNKNOWN',state['before_unknown_adoption']),('ORIGINAL_PROOFLESS_LOCAL_ADOPT_AFTER_UNKNOWN',state['before_unknown_patch'])]
        else:
            assert response.status_code==200,response.text
            requests=[('ORIGINAL_OPPORTUNITY_ADOPT_UNRESOLVED_NOTE',response.json()['adoption']),('ORIGINAL_PROOFLESS_LOCAL_ADOPT_UNRESOLVED_NOTE',patch_body(f,p))]
        for entry_name,data in requests:
            before=previous.full_business(t)
            r=adopt(f,p,data) if 'OPPORTUNITY' in entry_name else patch(f,p,body=data)
            assert r.status_code==409,r.text
            assert previous.full_business(t)==before
            record('refusals',dict(scenario=entry_name,status=r.status_code,no_business_write=True,request_captured_before_unknown='before_unknown_adoption' in state))
    def unknown():
        card=next(c for c in opportunities(f,p).json()['cards'] if c['is_latest_generation'])
        response=preview(f,p,card);assert response.status_code==200,response.text
        state['before_unknown_adoption']=deepcopy(response.json()['adoption'])
        state['before_unknown_patch']=patch_body(f,p)
        with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{kind}','\"UNKNOWN\"') WHERE park_id='park-a' AND service_id='synthetic-material-preparation' AND version=1")
    def authority(active):
        with f[1].connect() as c:
            f[1].lock_principal(c,'fixture-a',exclusive=True)
            c.execute("UPDATE capability_grants SET active=%s,revision=revision+1 WHERE principal_id='fixture-a' AND capability='READ'",(active,))
        if not active:state['denial']=previous.full_business(t)
    def denied():
        assert previous.full_business(t)==state['denial']
        record('refusals',dict(scenario='ACTUAL_NOTE_GET_403_DIRECT_BEFORE_AFTER',status=403,no_business_write=True))
    return dict(change_material=changed,remember_decision=remember,before_adopt=before_adopt,after_adopt=after_adopt,
        review_material=review_material,relink_resources=relink,reoffer_accept=reoffer,new_report_ack=report,revalidate_local=revalidate,
        final_evidence=final,assert_unresolved=unresolved,make_unknown=unknown,revoke=lambda:authority(False),restore=lambda:authority(True),assert_denied_read_no_write=denied)


def run_html(t,mode):
    attempt=mode+'-'+uuid4().hex[:8];controls=html_controls(t)
    driver=Path(__file__).with_name('manual_content_continuation_real_html.js')
    if not driver.exists():driver=ROOT/'tests/manual_content_continuation_real_html.js'
    process=subprocess.Popen(['node',str(driver)],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    selector=selectors.DefaultSelector();selector.register(process.stdout,selectors.EVENT_READ);lines=[];error='';result=None
    try:
        process.stdin.write(json.dumps(dict(base=str(t['f'][3].base_url).rstrip('/'),token=t['f'][2]['fixture-a'],mode=mode,A=t['rows']['A'],B=t['rows']['B'],
            baseline=BASE_SOURCE,manual=MANUAL,incoming=INCOMING))+'\n');process.stdin.flush()
        while True:
            assert selector.select(timeout=45),'Original HTML made no progress for 45 seconds'
            line=process.stdout.readline()
            if not line:break
            lines.append(line);message=json.loads(line)
            if 'control' in message:
                controls[message['control']]();process.stdin.write('{}\n');process.stdin.flush()
            else:result=message;break
        code=process.wait(timeout=10);error=process.stderr.read();assert code==0,error
        assert result and result['scope']=='FULL_ORIGINAL_HTML_MANUAL_CONTINUATION_REAL_HTTP_ASGI_OWNED_PG'
        record('html-results',dict(mode=mode,result='PASS',checks=result['checks'],requests=len(result['calls']),trace=attempt+'.stdout.jsonl',actual_http=True,real_browser='NOT_RUN'))
        return result
    finally:
        selector.close()
        if process.poll() is None:process.terminate();process.wait(timeout=5)
        (OUT/(attempt+'.stdout.jsonl')).write_text(''.join(lines));(OUT/(attempt+'.stderr.log')).write_text(error+process.stderr.read())


@pytest.mark.parametrize('mode',['keep_edit','accept','merge','defer_unknown','lost_choice','lost_adopt','current_403','late_403'])
def test_complete_original_html_manual_continuation_to_actual_six_goal_evidence(cases,mode):
    run_html(cases,mode)
