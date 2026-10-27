"""Independent two-slot literal tests; actual original HTTP/ASGI/owned PG only."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import selectors
import subprocess
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb
from parkweave import resource_holds as rh, resource_combinations as rc
from test_resource_holds import body as hold_body

import test_at24_27_change_batch_independent as batch
import test_manual_content_continuation_independent as legacy
import test_new_enterprise_local_chain as chain
from test_new_enterprise_local_chain import fresh_chain, ALL_GOALS, call
from test_case_resources import link_fixture, get as link_read, post as link_write
from test_executor_receipts import receipt_fixture, act as receipt_act
from test_preparation import preparation_fixture, headers, command as prepare, add as add_material, read as prep_read
from test_service_plan_manual_lock import stored, lock
from test_service_case_steps import read as plan_read, command as plan_command, verified
from test_source_change_adoption import preview, adopt
from test_registered_local_revision import patch, patch_body, add_resource
from test_case_opportunities import get as opp_read, post as opp_post, body as opp_body, entry
from test_case_lifecycle import read as local_read, act as local_act
from test_service_dispatches import offer as offer, command as dispatch_act

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'pyproject.toml').is_file())
OUT = ROOT/'.runtime/multifield-source-independent/artifacts'
RUN_ID = uuid4().hex
ORACLE = json.loads((ROOT/'docs/F2/MultifieldSourceConflictOracle-20261015.json').read_text())
LITERAL = ORACLE['fixed_fixture']
M, NB, NS, OB, OS = (LITERAL[k] for k in ('manual_M0','summary_B0','summary_S1','outline_B0','outline_S1'))
MERGED = LITERAL['merge_M1']
ALL = ('P1','P2','P3','P4','P5')
NEW = ('KEEP_AND_CONTINUE','MERGE_NOTE')


def record(artifact_kind, **value):
    OUT.mkdir(parents=True, exist_ok=True)
    row = dict(value, run_id=RUN_ID, test=os.environ.get('PYTEST_CURRENT_TEST'),
        utc=datetime.now(timezone.utc).isoformat(),
        source_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
    with (OUT/(artifact_kind+'-'+RUN_ID+'.jsonl')).open('a') as stream:
        stream.write(json.dumps(row,sort_keys=True,default=str)+'\n')
    return row


@pytest.fixture
def cases(fresh_chain, tmp_path):
    old_out, old_legacy, original_input = batch.OUT, legacy.OUT, chain.input_body
    batch.OUT, legacy.OUT = OUT/'baseline', OUT/'legacy-helper'
    def literal_input(*args, **kwargs):
        value = original_input(*args, **kwargs)
        for material in value['materials']:
            material['text'] = NB if material['slot']=='need_summary' else OB
        return value
    chain.input_body = literal_input
    generator = batch.two_cases.__wrapped__(fresh_chain,tmp_path)
    try:
        t = next(generator)
        chain.input_body = original_input
        record('baseline', cases={k:dict(preparation_id=v['preparation_id'],case_id=v['case_id'],
            plan_id=t['initial'][k]['id'],required_goals=t['initial'][k]['required_goals'],
            step_ids={s['adapter_id']:s['id'] for s in t['initial'][k]['steps']}) for k,v in t['rows'].items()},
            need_summary=NB, material_outline=OB)
        yield t
    finally:
        generator.close()
        batch.OUT, legacy.OUT, chain.input_body = old_out, old_legacy, original_input


def path(t, label='A'):
    return '/api/preparations/'+t['rows'][label]['preparation_id']+'/plan-material-package'


def card(t, label='A'):
    f,p=t['f'],t['rows'][label]
    value=opp_read(f,p).json()
    if not value['cards']:
        r=opp_post(f,p,opp_body(value,item=entry()));assert r.status_code==200,r.text
        value=r.json()['current']
    r=opp_post(f,p,opp_body(value,'REFRESH'));assert r.status_code==200,r.text
    return next(c for c in r.json()['current']['cards'] if c['is_latest_generation'])


def read_package(t, c=None, label='A', actor='fixture-a'):
    r=t['f'][3].get(path(t,label),headers=headers(t['f'][2],actor),params={'card_id':c['id']} if c else {})
    assert r.status_code==200,r.text
    value=r.json();assert value['scope']=='OWNER_NOTE_MATERIAL_PACKAGE' and value['schema']==1
    assert value['continuation'] is None and value['can_edit'] is False and value['allowed_choices']==[]
    q=value['package_confirmation']
    assert q['scope']=='OWNER_NOTE_MATERIAL_PACKAGE_CONFIRMATION' and q['schema']==1
    assert q['policy']==dict(need_summary='CONTEXT_ACK_ONLY',material_outline='EXACT_LINE_CARRIAGE_WHEN_REQUIRED_V1')
    assert q['semantic_evaluated'] is False and q['manual_preserved'] is True
    assert q['preview_sha256']==value['preview_sha256']
    record('package-previews',label=label,view=value)
    return value


def request(value, action='KEEP_AND_CONTINUE', text=None):
    assert value['preview_sha256'] is not None, 'Unknown views cannot manufacture a writable preview'
    return dict(schema=2,action=action,expected_plan_id=value['plan_id'],expected_plan_revision=value['plan_revision'],
        expected_note_revision=value['note']['revision'],expected_ledger_revision=value['opportunity_revision'],
        expected_preview_sha256=value['preview_sha256'],card_id=value['card_id'],text=text,
        reason='SYNTHETIC independent explicit two-slot package decision',confirm_package=True)


def write_package(t, data, *, key=None, label='A', actor='fixture-a'):
    return t['f'][3].post(path(t,label)+'/commands',headers=headers(t['f'][2],actor,key or uuid4().hex),json=data)


def deny(t, data, *, expected=409, **kwargs):
    before=batch.full_business(t);r=write_package(t,data,**kwargs)
    assert r.status_code==expected,r.text
    assert batch.full_business(t)==before
    record('refusals',action=data['action'],status=r.status_code,no_business_write=True)
    return r


def manual(t, text=M, label='A'):
    v=legacy.note_response(t,label=label).json()
    r=legacy.write(t,legacy.body(v,'EDIT_NOTE',text),label=label);assert r.status_code==200,r.text
    assert r.json()['current']['note']['text']==text
    return r.json()['current']['note']


def change_slots(t, *, summary=None, outline=None, label='A', refresh=True):
    f,p=t['f'],t['rows'][label]
    current=dict(prep_read(f,p).json()['preparation'],preparation_id=p['preparation_id'])
    if current['state'] in ('REVIEWED','LOCAL_CONFIRMED'):
        r=prepare(f,current,'REOPEN',reason='SYNTHETIC actual two-slot update');assert r.status_code==200,r.text
        current=r.json()
    for slot,text in [('need_summary',summary),('material_outline',outline)]:
        if text is not None:
            r=add_material(f,current,slot=slot,text=text);assert r.status_code==200,r.text
            current=r.json()
    return card(t,label) if refresh else None


def partition(t, scenario, a=ALL, b=(), unknown=False, original_plan=False):
    for label,want in [('A',set(a)),('B',set(b))]:
        if original_plan:
            response=plan_read(t['f'],t['rows'][label]);assert response.status_code==200,response.text
            graph=response.json()['change_impact']
        else:
            value=batch.source_graph(t['f'],t['rows'][label]);graph=value['source_impact']
        ids={s['adapter_id']:s['id'] for s in t['initial'][label]['steps']}
        expected={ids[x] for x in want};keep=set(ids.values())-expected
        actual=set(graph['affected']);preserved=set(graph['preserved'])
        row=record('oracle',scenario=scenario,case=label,intentional_unknown=unknown,
            projection_surface='ORIGINAL_SERVICE_CASE_PLAN_CHANGE_IMPACT' if original_plan else 'REGISTERED_TYPED_SOURCE_IMPACT',
            expected_affected=sorted(expected),actual_affected=sorted(actual),expected_preserved=sorted(keep),actual_preserved=sorted(preserved),
            missed_count=len(expected-actual),wrong_count=len(actual-expected),wrong_preserved_count=len(keep^preserved))
        assert actual==expected and preserved==keep,row
        assert bool(graph['unknown_scope'])==unknown


def enable(t, label='A'):
    manual(t,label=label);c=card(t,label);v=read_package(t,c,label)
    r=write_package(t,request(v),label=label);assert r.status_code==200,r.text
    assert r.json()['receipt']['plan_note']['version']==3
    assert r.json()['current']['package_confirmation']['active'] is True
    return c,r.json()


def refuse_original_adopts(t,c,label='A'):
    f,p=t['f'],t['rows'][label];v=preview(f,p,c);assert v.status_code==200,v.text
    data=v.json()['adoption'];before=batch.full_business(t);r=adopt(f,p,data)
    assert r.status_code==409,r.text;assert batch.full_business(t)==before
    data=patch_body(f,p);before=batch.full_business(t);r=patch(f,p,body=data)
    assert r.status_code==409,r.text;assert batch.full_business(t)==before
    record('refusals',scenario='BOTH_ORIGINAL_LOCAL_ADOPT_ROUTES',status=409,no_business_write=True)


def original_adopt(t,c,label='A'):
    f,p=t['f'],t['rows'][label];v=preview(f,p,c);assert v.status_code==200,v.text
    assert v.json()['can_adopt'],v.json()['blocking_reasons']
    old=deepcopy(stored(f,p));r=adopt(f,p,v.json()['adoption']);assert r.status_code==201,r.text
    after=stored(f,p)
    assert after['id']==old['id'] and after['required_goals']==ALL_GOALS
    assert [s['id'] for s in after['steps']]==[s['id'] for s in old['steps']]
    assert [s['contract'] for s in after['steps']]==[s['contract'] for s in old['steps']]
    assert [s['verified_sources'] for s in after['steps']]==[s['verified_sources'] for s in old['steps']]
    assert after['events'][:-1]==old['events'] and after['history']==old['history']
    return r.json()


def close_material(t):
    f,u,p=t['f'],t['u'],t['rows']['A']
    chain.material_decision(u,p,'REVIEW');chain.material_decision(u,p,'CONFIRM');verified(f,p,'P1')
    current=link_read(f,p).json();record=current['current']['record']
    prep=dict(prep_read(f,p).json()['preparation'],preparation_id=p['preparation_id'])
    r=link_write(f,prep,dict(id=record['combination_id']),revision=current['link_revision']);assert r.status_code==201,r.text
    verified(f,p,'P2')
    prep=dict(prep_read(f,p).json()['preparation'],preparation_id=p['preparation_id'])
    dispatch_id=t['completed']['A']['dispatch']['dispatch_id']
    current=f[3].get('/api/service-dispatches/'+dispatch_id,headers=headers(f[2],'prep-specialist-fixture-a')).json()
    r=offer(f,prep,revision=current['revision'],recovery_receipt_step_id=current['recovery_receipt_step_id'])[0];assert r.status_code==201,r.text
    r=dispatch_act(f,r.json(),'ACCEPT');assert r.status_code==200,r.text
    verified(f,p,'P3');chain.report_and_ack(u,p,r.json());verified(f,p,'P4')
    r=local_act(f,p,local_read(f,p).json(),'REVALIDATE');assert r.status_code==200,r.text
    verified(f,p,'P5');final(t,unaffected_B=True)


def final(t,unaffected_B=False):
    goal_refs={}
    for label,p in t['rows'].items():
        view=plan_read(t['f'],p).json();initial=t['initial'][label]
        assert view['required_goals']==ALL_GOALS and all(s['state']=='VERIFIED' for s in view['steps'])
        assert view['plan_id']==initial['id'] and [s['id'] for s in view['steps']]==[s['id'] for s in initial['steps']]
        current=stored(t['f'],p)
        assert [s['contract'] for s in current['steps']]==[s['contract'] for s in initial['steps']]
        assert current['events'][:len(initial['events'])]==initial['events'] and current['history']==initial['history']
        value=call(t['u'],'/api/preparations/'+p['preparation_id']+'/goal-results')
        assert value['state']=='LOCAL_OUTPUTS_VERIFIED' and len(value['results'])==6 and not value['case_goal_completed']
        assert all(r['state']=='LOCAL_OUTPUT_VERIFIED' for r in value['results'])
        source=next(s for s in stored(t['f'],p)['steps'] if s['adapter_id']=='P4')['verified_sources']
        goal_refs[p['case_id']]=dict(label=label,run_id=p['run_id'],preparation_id=p['preparation_id'],
            receipt_step_id=source['receipt_step_id'],goal_state=value['state'],goals=[r['goal'] for r in value['results']])
    before=batch.full_business(t);seen=[];after=None
    for _ in range(4):
        r=t['f'][3].get('/api/cases/worklist',headers=headers(t['f'][2]),params=dict(limit=1,**({'after':after} if after else {})))
        assert r.status_code==200,r.text
        value=r.json();assert value['read_only'] and value['recorded_states_only'] and not value['automatically_replayed']
        seen.extend(value['items']);after=value['next_after']
        if after is None:break
    assert after is None and len(seen)==2 and {r['case_id'] for r in seen}==set(goal_refs)
    for row in seen:
        refs=goal_refs[row['case_id']]
        for key in ('run_id','preparation_id','receipt_step_id'):assert row[key]==refs[key]
        assert row['attention']=='LOCAL_ACKNOWLEDGED' and row['evidence_verified'] is False and row['case_goal_completed'] is False
    assert batch.full_business(t)==before
    if unaffected_B:assert stored(t['f'],t['rows']['B'])==t['initial']['B']
    record('closures',six_goals_current=True,stable_ids_contract_history=True,worklist_complete=True,
        worklist_items=seen,goal_evidence_refs=goal_refs,worklist_is_recorded_state_not_fact_verification=True,unaffected_B_exact=unaffected_B)


def test_get_never_enables_and_legacy_summary_path_stays_compatible(cases):
    t=cases;manual(t);c=card(t);before=batch.full_business(t);v=read_package(t,c)
    assert not v['package_confirmation']['active'] and batch.full_business(t)==before
    c=change_slots(t,summary=NS);v=read_package(t,c);assert not v['package_confirmation']['active']
    original_adopt(t,c);assert next(iter(stored(t['f'],t['rows']['A'])['owner_amendments'].values()))['text']==M


def test_explicit_unchanged_package_enables_without_outline_carriage(cases):
    t=cases;c,r=enable(t);q=read_package(t,c)['package_confirmation']
    assert q['active'] and not q['outline_carriage_required']
    assert q['manual']['text']==M and q['coverage']['conditions']==[]


def test_no_manual_note_does_not_offer_new_package_mode(cases):
    t=cases;c=card(t);before=batch.full_business(t);v=read_package(t,c)
    assert v['note'] is None and not v['package_confirmation']['active'] and not v['action_requests']
    assert batch.full_business(t)==before


@pytest.mark.parametrize('both',[False,True])
def test_actual_summary_or_both_slots_explicit_decision_to_six_goals(cases,both):
    t=cases;manual(t);c=change_slots(t,summary=NS,outline=OS if both else None)
    partition(t,'MF06_BOTH_SLOTS' if both else 'MF04_SUMMARY_ONLY')
    v=read_package(t,c);q=v['package_confirmation'];assert q['outline_carriage_required']==both
    assert {x['slot'] for x in q['baseline_package']}=={'need_summary','material_outline'}
    assert q['manual']['text']==M and q['policy']['need_summary']=='CONTEXT_ACK_ONLY'
    if both:
        assert not q['can_keep_and_continue'];deny(t,request(v))
    action='MERGE_NOTE' if both else 'KEEP_AND_CONTINUE';text=MERGED if both else None
    v=read_package(t,c);key=uuid4().hex;r=write_package(t,request(v,action,text),key=key);assert r.status_code==200,r.text
    original=r.json()['receipt'];assert original['plan_note']['version']==3
    assert r.json()['current']['note']['text']==(MERGED if both else M)
    original_adopt(t,c);close_material(t)
    before=batch.full_business(t);recovered=t['f'][3].get(path(t)+'/recovery/'+key,headers=headers(t['f'][2]))
    assert recovered.status_code==200,recovered.text
    assert recovered.json()['receipt']==original and batch.full_business(t)==before


def test_required_outline_counts_only_outline_and_preserves_full_manual(cases):
    t=cases;manual(t);c=change_slots(t,summary=NS,outline=OS);v=read_package(t,c)
    conditions=v['package_confirmation']['coverage']['conditions'];dup=next(x for x in conditions if x['line']=='共同条件')
    assert dup['required_count']==2
    for bad in [M+'\nO1：资料核验\n共同条件',MERGED.replace('  保留本人空格  ','保留本人空格'),MERGED.replace('O1：资料核验','O1：资料核驗')]:
        deny(t,request(read_package(t,c),'MERGE_NOTE',bad))
    r=write_package(t,request(read_package(t,c),'MERGE_NOTE',MERGED));assert r.status_code==200,r.text


@pytest.mark.parametrize('legacy_v2',[False,True])
def test_outline_requirement_is_sticky_after_summary_only(cases,legacy_v2):
    t=cases;manual(t);c=change_slots(t,outline=OS)
    v=read_package(t,c);assert v['package_confirmation']['outline_carriage_required']
    assert not v['package_confirmation']['can_keep_and_continue'];deny(t,request(v))
    if legacy_v2:
        v=legacy.note_read(t,c);r=legacy.write(t,legacy.body(v,'MERGE_NOTE',MERGED));assert r.status_code==200,r.text
    else:
        r=write_package(t,request(read_package(t,c),'MERGE_NOTE',MERGED));assert r.status_code==200,r.text
    c=change_slots(t,summary=NS);v=read_package(t,c);assert v['package_confirmation']['outline_carriage_required']
    r=write_package(t,request(v));assert r.status_code==200,r.text
    assert read_package(t,c)['package_confirmation']['outline_carriage_required']


def test_every_legal_edit_and_each_new_slot_version_requires_fresh_confirmation(cases):
    t=cases;c,_=enable(t)
    c=change_slots(t,summary=NS)
    r=write_package(t,request(read_package(t,c)));assert r.status_code==200,r.text
    for text in [M,M+'\n新增本人提醒',M]:
        v=legacy.note_read(t,c);r=legacy.write(t,legacy.body(v,'EDIT_NOTE',text));assert r.status_code==200,r.text
        refuse_original_adopts(t,c)
        r=write_package(t,request(read_package(t,c)));assert r.status_code==200,r.text
        assert preview(t['f'],t['rows']['A'],c).json()['can_adopt']
    for slot,text in [('need_summary',NS),('material_outline',OS)]:
        old=request(read_package(t,c));c=change_slots(t,**{'summary' if slot=='need_summary' else 'outline':text})
        deny(t,old);refuse_original_adopts(t,c)
        v=read_package(t,c);action='MERGE_NOTE' if slot=='material_outline' else 'KEEP_AND_CONTINUE'
        r=write_package(t,request(v,action,(M+'\n'+OS) if action=='MERGE_NOTE' else None));assert r.status_code==200,r.text


def test_old_actions_and_preferences_never_bypass_new_package_guard(cases):
    t=cases;c,_=enable(t);c=change_slots(t,summary=NS)
    for action in ['ACCEPT_SOURCE','KEEP_AND_CONTINUE','MERGE_NOTE']:
        v=legacy.note_read(t,c);data=legacy.body(v,action,M+'\n'+OS if action=='MERGE_NOTE' else None)
        before=batch.full_business(t);r=legacy.write(t,data);assert r.status_code==409,r.text
        assert batch.full_business(t)==before
    for action in ['KEEP_MANUAL','DEFER']:
        v=legacy.note_read(t,c);r=legacy.write(t,legacy.body(v,action));assert r.status_code==200,r.text
        refuse_original_adopts(t,c)


def test_p1_and_other_affected_locks_require_only_explicit_original_unlock(cases):
    t=cases;manual(t);c=change_slots(t,summary=NS)
    # Lock before the actual change, because stale P1 cannot legally be LOCKed.
    # A separate fresh fixture baseline is available in t['initial']; no forged locks.
    # This test confirms the current original lock guard using the unchanged package first.
    v=read_package(t,c);r=write_package(t,request(v));assert r.status_code==200,r.text
    original_adopt(t,c);close_material(t)
    assert lock(t['f'],t['rows']['A'],'P1').status_code==200
    assert lock(t['f'],t['rows']['A'],'P3').status_code==200
    c=change_slots(t,summary=NS+'\n第三版摘要');deny(t,request(read_package(t,c)))
    assert plan_command(t['f'],t['rows']['A'],'P1','UNLOCK').status_code==200
    r=write_package(t,request(read_package(t,c)));assert r.status_code==200,r.text
    refuse_original_adopts(t,c)
    assert plan_command(t['f'],t['rows']['A'],'P3','UNLOCK').status_code==200
    assert preview(t['f'],t['rows']['A'],c).json()['can_adopt']


def test_strict_confirmation_foreign_scope_and_same_key_conflict(cases):
    t=cases;manual(t);c=card(t);data=request(read_package(t,c))
    for bad in [{**data,'confirm_package':False},{**data,'confirm_package':1},{k:v for k,v in data.items() if k!='confirm_package'}]:deny(t,bad,expected=422)
    for actor in ['fixture-b','fixture-c']:deny(t,data,actor=actor,expected=403)
    key=uuid4().hex;r=write_package(t,data,key=key);assert r.status_code==200,r.text;original=r.json()['receipt']
    before=batch.full_business(t);same=write_package(t,data,key=key);assert same.status_code==200 and same.json()['receipt']==original
    assert batch.full_business(t)==before;deny(t,{**data,'reason':'SYNTHETIC different key parameters'},key=key)
    recovery=t['f'][3].get(path(t)+'/recovery/'+key,headers=headers(t['f'][2]));assert recovery.status_code==200
    assert recovery.json()['receipt']==original and recovery.json()['historical_only'] is True


def test_current_authority_and_history_use_original_note_permission_contract(cases):
    t=cases;manual(t);c=card(t);data=request(read_package(t,c));key=uuid4().hex
    r=write_package(t,data,key=key);assert r.status_code==200,r.text;event=r.json()['receipt']
    for capability in ['READ','PREPARE','EXECUTE']:
        table='preparation_grants' if capability=='PREPARE' else 'capability_grants'
        revision='' if capability=='PREPARE' else ',revision=revision+1'
        with t['f'][1].connect() as db:
            t['f'][1].lock_principal(db,'fixture-a',exclusive=True)
            db.execute('UPDATE '+table+' SET active=false'+revision+' WHERE principal_id=%s AND capability=%s',('fixture-a',capability))
        deny(t,data,key=key,expected=403)
        r=t['f'][3].get(path(t)+'/recovery/'+key,headers=headers(t['f'][2]))
        assert r.status_code==(200 if capability=='EXECUTE' else 403),r.text
        if capability=='EXECUTE':assert r.json()['receipt']==event and not r.json()['current']['action_requests']
        with t['f'][1].connect() as db:
            t['f'][1].lock_principal(db,'fixture-a',exclusive=True)
            db.execute('UPDATE '+table+' SET active=true'+revision+' WHERE principal_id=%s AND capability=%s',('fixture-a',capability))


def test_current_and_captured_summary_aba_reject_old_preview(cases):
    t=cases;manual(t);c=change_slots(t,summary=NS)
    for which in ['current_package','baseline_package']:
        v=read_package(t,c);data=request(v);row=next(x for x in v['package_confirmation'][which] if x['slot']=='need_summary')
        with t['f'][1].connect() as db:
            old=db.execute('SELECT *,xmin::text row_epoch FROM preparation_evidence WHERE id=%s',(row['id'],)).fetchone()
            db.execute("UPDATE preparation_evidence SET source_label=source_label||' ABA' WHERE id=%s",(row['id'],))
        with t['f'][1].connect() as db:db.execute('UPDATE preparation_evidence SET source_label=%s WHERE id=%s',(old['source_label'],row['id']))
        with t['f'][1].connect() as db:after=db.execute('SELECT *,xmin::text row_epoch FROM preparation_evidence WHERE id=%s',(row['id'],)).fetchone()
        assert {k:v for k,v in old.items() if k!='row_epoch'}=={k:v for k,v in after.items() if k!='row_epoch'} and old['row_epoch']!=after['row_epoch']
        deny(t,data);record('aba',kind=which,fixture_fault_injection=True,visible_original_restored=True)


@pytest.mark.parametrize('kind',['missing_baseline','current_blank'])
def test_captured_or_current_summary_unknown_has_no_new_authority(cases,kind):
    t=cases;c,_=enable(t);c=change_slots(t,summary=NS)
    proofless=patch_body(t['f'],t['rows']['A']);bound=preview(t['f'],t['rows']['A'],c).json()['adoption']
    v=read_package(t,c);old=request(v)
    which='baseline_package' if kind=='missing_baseline' else 'current_package'
    row=next(x for x in v['package_confirmation'][which] if x['slot']=='need_summary')
    with t['f'][1].connect() as db:
        if kind=='missing_baseline':db.execute('DELETE FROM preparation_evidence WHERE id=%s',(row['id'],))
        else:db.execute('UPDATE preparation_evidence SET text=%s,source_sha256=%s WHERE id=%s',(' ',hashlib.sha256(b' ').hexdigest(),row['id']))
    current=read_package(t,c)
    assert current['unknown_scope']=='THIS_CASE' and set(current['affected'])=={s['id'] for s in t['initial']['A']['steps']} and not current['preserved']
    assert not current['package_confirmation']['can_keep_and_continue'] and not current['action_requests']
    deny(t,old)
    for data,method in [(bound,adopt),(proofless,patch)]:
        before=batch.full_business(t)
        r=method(t['f'],t['rows']['A'],data) if method is adopt else method(t['f'],t['rows']['A'],body=data)
        assert r.status_code==409,r.text;assert batch.full_business(t)==before


def test_summary_129_lines_is_context_but_outline_129_is_unknown(cases):
    t=cases;manual(t);c=change_slots(t,summary='\n'.join('N'+str(i) for i in range(129)))
    v=read_package(t,c);assert not v['package_confirmation']['outline_carriage_required']
    r=write_package(t,request(v));assert r.status_code==200,r.text
    old=request(read_package(t,c));c=change_slots(t,outline='\n'.join('O'+str(i) for i in range(129)))
    v=read_package(t,c);assert v['package_confirmation']['outline_carriage_required']
    assert not v['package_confirmation']['coverage']['coverage_known'] and not v['action_requests']
    deny(t,old);refuse_original_adopts(t,c)


def advance_receipt(t):
    row=t['rows']['A'];f=t['f'];id=t['completed']['A']['dispatch']['receipt_step_id']
    old=f[3].get('/api/executor-receipts/'+id,headers=headers(f[2])).json()
    r=receipt_act(f,old,'REOPEN');assert r.status_code==200,r.text
    new=chain.report_and_ack(t['u'],row,dict(receipt_step_id=id))
    assert new['current_receipt']['version']==old['current_receipt']['version']+1
    assert new['current_receipt']['adapter_execution']['report']['execution_id']!=old['current_receipt']['adapter_execution']['report']['execution_id']
    record('receipt-progress',actual_original_execute_local=True,old_report_preserved=True,new_version=new['current_receipt']['version'])
    return new


def repair_local_tail(t,label,adapters):
    f,p=t['f'],t['rows'][label]
    for adapter in adapters:
        if adapter!='P5':verified(f,p,adapter)
    r=local_act(f,p,local_read(f,p).json(),'REVALIDATE');assert r.status_code==200,r.text
    verified(f,p,'P5')


def test_real_six_goal_receipt_only_keeps_all_unaffected_locks(cases):
    t=cases;enable(t)
    for adapter in ('P1','P2','P3'):assert lock(t['f'],t['rows']['A'],adapter).status_code==200
    before=deepcopy(stored(t['f'],t['rows']['A']))
    advance_receipt(t);partition(t,'MF17_RECEIPT_ONLY',('P4','P5'))
    c=card(t);original_adopt(t,c);repair_local_tail(t,'A',('P4','P5'));final(t,unaffected_B=True)
    assert stored(t['f'],t['rows']['A'])['steps'][:3]==before['steps'][:3]


def current_resource_rebind(t,label,number):
    f,u,p=t['f'],t['u'],t['rows'][label]
    resources=call(u,'/api/synthetic-resources')['items'];revisions={r['id']:r['revision'] for r in resources}
    base=hold_body(f,ttl=300);start=datetime.fromisoformat(base['starts_at'])+timedelta(hours=48+number*24)
    holds=[]
    for index,id in enumerate((rh.RESOURCE_ID,rc.SECOND_RESOURCE_ID,rh.RESOURCE_ID)):
        data=dict(base,starts_at=(start+timedelta(hours=index*3)).isoformat(),ends_at=(start+timedelta(hours=index*3+1)).isoformat(),
            expected_revision=revisions[str(id)],purpose='SYNTHETIC explicit union current replacement '+label)
        holds.append(call(u,'/api/synthetic-resources/'+str(id)+'/holds',data=data,expected=201)['hold'])
    bundle=call(u,'/api/resource-bundles',data=dict(members=[dict(hold_id=h['id'],expected_revision=h['resource_revision']) for h in holds]),expected=201)
    path='/api/preparations/'+p['preparation_id']
    q=call(u,path+'/resource-plan-binding?candidate_combination_id='+bundle['combination']['id'])
    assert q['comparison']['can_confirm'],q['comparison']['blockers']
    current=prep_read(f,p).json()['preparation']
    data=dict(combination_id=bundle['combination']['id'],expected_preparation_revision=current['revision'],
        expected_link_revision=q['comparison']['link_revision'],expected_comparison_sha256=q['comparison']['sha256'],
        reason='SYNTHETIC explicit current selected resource and receipt union rebind')
    r=call(u,path+'/resource-link',data=data,expected=201);assert r['current']['status']=='CURRENT'


def test_selected_capacity_and_actual_adapter_receipt_union_cannot_hide_missed_source(cases):
    t=cases;f=t['f'];enable(t);enable(t,'B')
    for p in t['rows'].values():assert lock(f,p,'P1').status_code==200
    locked={label:deepcopy(stored(f,p)['steps'][0]) for label,p in t['rows'].items()}
    with f[1].connect() as db:
        tables=('synthetic_resource_holds','synthetic_resource_combinations','synthetic_resource_combination_members',
            'synthetic_resource_combination_receipts','resource_case_claims','case_resource_links','service_step_receipts','service_receipt_events')
        old_rows={table:db.execute('SELECT * FROM '+table).fetchall() for table in tables}
    # Generate the original current adapter report while P1-P3 are still valid.
    # A capacity-first SUBMIT would correctly hit the original checkpoint gate.
    advance_receipt(t);partition(t,'MF17_UNION_RECEIPT_CONTROL',('P4','P5'))
    with f[1].connect() as db:
        db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('synthetic-resource:'+str(rh.RESOURCE_ID),))
        db.execute('UPDATE synthetic_resources SET capacity=capacity+1,revision=revision+1 WHERE id=%s',(rh.RESOURCE_ID,))
    partition(t,'MF16_RESOURCE_RECEIPT_UNION',('P2','P3','P4','P5'),('P2','P3','P4','P5'))
    for label,p in t['rows'].items():
        graph=batch.source_graph(f,p)['source_impact']
        receipt=[n for n in graph['nodes'] if n['facet'] in ('RECEIPT_SOURCE','RECEIPT_EVENTS')]
        assert any(n['changed'] for n in receipt)==(label=='A')
        assert any(n['changed'] and n['facet'] in ('RESOURCE_RULES','RESOURCE_QUERY_SET','DEPENDENCY_RESOURCE_QUERY_SET') for n in graph['nodes'])
        c=card(t,label);original_adopt(t,c,label)
    for number,label in enumerate(('A','B')):
        current_resource_rebind(t,label,number);repair_local_tail(t,label,('P2','P3','P4','P5'))
    # Read both at the end; a previous success before changing B is insufficient.
    for _ in range(2):
        changed=False
        for label,p in t['rows'].items():
            v=plan_read(f,p).json()
            if v['local_revision_required']:
                changed=True;original_adopt(t,card(t,label),label);repair_local_tail(t,label,('P2','P3','P4','P5'))
        if not changed:break
    final(t)
    for label,p in t['rows'].items():assert stored(f,p)['steps'][0]==locked[label]
    with f[1].connect() as db:
        for table,original in old_rows.items():assert all(row in db.execute('SELECT * FROM '+table).fetchall() for row in original),table
    record('union-results',literal_affected_A=['P2','P3','P4','P5'],literal_affected_B=['P2','P3','P4','P5'],
        p1_locks_exact=True,receipt_source_changed_only_A=True,old_reservations_and_reports_preserved=True)


def test_bounded_resource_unknown_does_not_allow_partial_known_receipt_adoption(cases):
    t=cases;enable(t);advance_receipt(t);c=card(t)
    proofless=patch_body(t['f'],t['rows']['A'])
    good=preview(t['f'],t['rows']['A'],c);assert good.status_code==200,good.text
    adoption=deepcopy(good.json()['adoption']);old=request(read_package(t,c))
    for _ in range(130):add_resource(t['f'])
    # The original typed reader refuses an unbounded row-epoch proof.  Keep
    # that refusal; the original plan exposes the conservative UNKNOWN impact.
    before=batch.full_business(t)
    denied=t['f'][3].get('/api/preparations/'+t['rows']['A']['preparation_id']+'/source-impact',headers=headers(t['f'][2]))
    assert denied.status_code==409 and denied.json()['detail']=='bounded current source row-version proof unavailable',denied.text
    assert batch.full_business(t)==before
    record('refusals',scenario='ORIGINAL_TYPED_READER_EPOCH_BOUND',status=409,no_business_write=True,original_bound_preserved=True)
    partition(t,'MF25_UNKNOWN_RESOURCE_WITH_RECEIPT',ALL,ALL,unknown=True,original_plan=True)
    v=read_package(t,c)
    assert v['unknown_scope']=='THIS_CASE' and set(v['affected'])=={s['id'] for s in t['initial']['A']['steps']} and not v['preserved'] and not v['action_requests']
    deny(t,old)
    before=batch.full_business(t);r=adopt(t['f'],t['rows']['A'],adoption)
    assert r.status_code==409,r.text;assert batch.full_business(t)==before
    before=batch.full_business(t);r=patch(t['f'],t['rows']['A'],body=proofless)
    assert r.status_code==409,r.text;assert batch.full_business(t)==before
    record('refusals',scenario='UNKNOWN_MIXED_REAL_SOURCE_UNION',status=409,no_business_write=True,known_precision=False,
        package_command_status=409,opportunity_bound_adopt_status=409,original_proofless_local_adopt_status=409)


def html_controls(t,mode):
    controls=legacy.html_controls(t);state={}
    def changed():
        state['before_change']=deepcopy(stored(t['f'],t['rows']['A']))
        change_slots(t,summary=NS,outline=OS if mode=='dual_merge_lost_ack' else None,refresh=False)
        partition(t,'HTML_'+mode)
    def decision_only():
        current=stored(t['f'],t['rows']['A']);old=state['before_change']
        assert all(e['action']!='ADOPT' for e in current['events'][len(old['events']):])
        assert [s['verified_sources'] for s in current['steps']]==[s['verified_sources'] for s in old['steps']]
        partition(t,'COMMITTED_V3_IS_NOT_ADOPT_'+mode)
        record('decision-state',mode=mode,committed_not_adopted=True,old_verify_evidence_retained=True)
    original_final=controls['final_evidence']
    def finish():
        original_final();final(t,unaffected_B=True)
    controls.update(change_material=changed,assert_decision_not_adopted=decision_only,final_evidence=finish)
    return controls


def run_html(t,mode):
    OUT.mkdir(parents=True,exist_ok=True);attempt=mode+'-'+uuid4().hex[:8];controls=html_controls(t,mode)
    driver=Path(__file__).with_name('multifield_source_package_real_html.js')
    if not driver.exists():driver=ROOT/'tests/multifield_source_package_real_html.js'
    process=subprocess.Popen(['node',str(driver)],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    selector=selectors.DefaultSelector();selector.register(process.stdout,selectors.EVENT_READ);lines=[];error='';result=None
    try:
        config=dict(base=str(t['f'][3].base_url).rstrip('/'),token=t['f'][2]['fixture-a'],mode=mode,A=t['rows']['A'],B=t['rows']['B'],
            manual=M,merged=MERGED,summaryBaseline=NB,outlineBaseline=OB,summaryIncoming=NS,
            outlineIncoming=OS if mode=='dual_merge_lost_ack' else OB)
        process.stdin.write(json.dumps(config)+'\n');process.stdin.flush()
        while True:
            assert selector.select(timeout=45),'Full original package HTML made no progress for45 seconds'
            line=process.stdout.readline()
            if not line:break
            lines.append(line);message=json.loads(line)
            if 'control' in message:
                controls[message['control']]();process.stdin.write('{}\n');process.stdin.flush()
            else:result=message;break
        code=process.wait(timeout=10);error=process.stderr.read();assert code==0,error
        assert result and result['scope']=='FULL_ORIGINAL_HTML_MULTIFIELD_PACKAGE_ACTUAL_HTTP_ASGI_OWNED_PG'
        record('html-results',mode=mode,result='PASS',checks=result['checks'],requests=len(result['calls']),
            trace=attempt+'.stdout.jsonl',actual_http=True,real_browser='NOT_RUN')
        return result
    finally:
        selector.close()
        if process.poll() is None:process.terminate();process.wait(timeout=5)
        (OUT/(attempt+'.stdout.jsonl')).write_text(''.join(lines));(OUT/(attempt+'.stderr.log')).write_text(error+process.stderr.read())


@pytest.mark.parametrize('mode',['summary_keep','dual_merge_lost_ack','current_403','late_403'])
def test_full_original_html_package_confirmation_and_authority(cases,mode):
    if mode in ('current_403','late_403'):
        enable(cases);enable(cases,'B')
    run_html(cases,mode)
