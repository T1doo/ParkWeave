"""Independent literal note carry answers; actual HTTP/ASGI and owned PostgreSQL."""
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
import test_new_enterprise_local_chain as chain
from psycopg.types.json import Jsonb
from parkweave.template_isolated_app import create_isolated_template_app
from parkweave.template_upgrade import TemplateUpgradeChecker, UpgradeRepository
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture, headers, command as prep_command, add as material_add, read as prep_read
from test_new_enterprise_local_chain import fresh_chain, actual_http, publish, new_case, enable_approval, finish_chain, ALL_GOALS, call
from test_template_upgrade import publication, check, choose, snapshot
from test_template_migration_independent import facts
from test_service_case_steps import read as plan_read, command as plan_command, verified
from test_service_plan_manual_lock import stored, lock

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'pyproject.toml').is_file())
OUT=ROOT/'.runtime/note-template-carry-independent/work'
RUN_ID=uuid4().hex
ALL=('P1','P2','P3','P4','P5')
MANUAL='人工说明：兼容模板升级后仍保留本提醒与两处空格  。\n本说明不充当事实、许可或办理完成。'


def record(kind,value):
    OUT.mkdir(parents=True,exist_ok=True)
    row=dict(value,run_id=RUN_ID,source_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),utc=datetime.now(timezone.utc).isoformat(),test=os.environ.get('PYTEST_CURRENT_TEST'))
    with (OUT/(kind+'-'+RUN_ID+'.jsonl')).open('a') as f:f.write(json.dumps(row,sort_keys=True,default=str)+'\n')
    return row


def private(tokens):
    OUT.mkdir(parents=True,exist_ok=True);p=OUT/('redaction-'+RUN_ID+'.private.json')
    previous=set(json.loads(p.read_text())) if p.exists() else set()
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as f:f.write(json.dumps(sorted(previous|set(tokens.values())))+'\n')
    p.chmod(0o600)


def note_get(t):
    r=t['f'][3].get('/api/preparations/'+t['row']['preparation_id']+'/plan-source-conflicts',headers=headers(t['f'][2]));assert r.status_code==200,r.text
    return r.json()


def note_write(t,text):
    v=note_get(t);d={**v['action_requests']['EDIT_NOTE'],'text':text,'reason':'SYNTHETIC explicit original manual edit'}
    r=t['f'][3].post('/api/preparations/'+t['row']['preparation_id']+'/plan-source-conflicts/commands',headers=headers(t['f'][2],key=uuid4().hex),json=d)
    assert r.status_code==200,r.text
    return r.json()


@pytest.fixture
def carry(fresh_chain,tmp_path,request):
    u=fresh_chain;private(u['f'][2])
    checker=TemplateUpgradeChecker(u['consumer'],UpgradeRepository(tmp_path/'note-carry.upgrade.candidate.sqlite3'),enabled_for_isolated_tests=True)
    with actual_http(create_isolated_template_app(u['f'][0],u['engine'],u['consumer'],checker)) as (client,traffic):
        u={**u,'f':(*u['f'][:3],client),'client':client,'checker':checker,'repository':checker.repository,'traffic':traffic}
        structural=getattr(request,'param',None)=='structure_initial'
        release=publish(u,ALL_GOALS[:-1] if structural else ALL_GOALS)
        original_input=chain.input_body
        def explicit_six_goals(*args,**kwargs):
            data=original_input(*args,**kwargs);data['required_goals']=list(ALL_GOALS);return data
        try:
            if structural:chain.input_body=explicit_six_goals
            row=new_case(u,release,number=627)
        finally:chain.input_body=original_input
        enable_approval(u,[row]);done=finish_chain(u,row)
        t=dict(u=u,f=u['f'],row=row,old=release,completed=done)
        note_write(t,MANUAL)
        ensure_current(t)
        view=plan_read(t['f'],row);assert view.status_code==200,view.text
        assert [s['adapter_id'] for s in view.json()['steps']]==list(ALL)
        assert all(s['state']=='VERIFIED' for s in view.json()['steps'])
        t['initial']=deepcopy(stored(t['f'],row));t['note']=deepcopy(next(iter(t['initial']['owner_amendments'].values())))
        assert t['note']['text']==MANUAL and t['note']['origin']=='MANUAL'
        goals=call(u,'/api/preparations/'+row['preparation_id']+'/goal-results')
        assert goals['state']=='LOCAL_OUTPUTS_VERIFIED' and len(goals['results'])==6 and not goals['case_goal_completed']
        t['outputs']={r['goal']:r['actual_output'] for r in goals['results']}
        record('baseline',dict(scope='ACTUAL_SIX_GOAL_CURRENT_MANUAL_NOTE',case_id=row['case_id'],instance_id=row['instance_id'],plan_id=t['initial']['id'],required_goals=t['initial']['required_goals'],step_ids={s['adapter_id']:s['id'] for s in t['initial']['steps']},note=t['note']))
        yield t


def ensure_current(t):
    # Original VERIFY is only legal for a step requiring verification. EDIT of
    # an already-current coordination note may preserve all five checks.
    commands=0
    for adapter in ALL:
        view=plan_read(t['f'],t['row']);assert view.status_code==200,view.text
        step=next(s for s in view.json()['steps'] if s['adapter_id']==adapter)
        if step['state']!='VERIFIED':verified(t['f'],t['row'],adapter);commands+=1
    view=plan_read(t['f'],t['row']).json();assert all(s['state']=='VERIFIED' for s in view['steps'])
    record('fixture-current',dict(all_five_verified=True,required_original_verify_commands=commands,already_current_steps_preserved=5-commands))


def target(t,source='1',goals=None):return publication(t['u'],ALL_GOALS if goals is None else goals,source,'SYNTHETIC independent forward compatible title')


def inspect(t,to):
    r=check(t['u'],t['row'],to);assert r.status_code==200,r.text
    return r.json()


def request(t,to,choice='REQUEST_RECHECK',require_eligible=True):
    v=inspect(t,to);r=choose(t['u'],t['row'],v,choice);assert r.status_code==200,r.text
    v=inspect(t,to);a=v['application'];n=a['note_carry']
    assert a['eligible'] is False
    if require_eligible:assert n['eligible'] is True,n
    data=dict(expected_instance_id=t['row']['instance_id'],target_release_id=to['release_id'],expected_target_sha256=to['release_sha256'],expected_check_sha256=v['check_sha256'],expected_choice_revision=r.json()['event']['revision'],expected_choice_event_sha256=r.json()['event']['event_sha256'],expected_plan_id=a['plan_id'],expected_plan_revision=a['plan_revision'],expected_preparation_revision=a['preparation_revision'],expected_source_sha256=a['source_sha256'],reason='SYNTHETIC explicit current MANUAL carry',expected_note_carry_sha256=n.get('preview_sha256') or '0'*64,confirm_note_carry=True)
    return v,data


def apply(t,data,key=None,actor='fixture-a',route='apply-note-carry',client=None):
    return (client or t['f'][3]).post('/api/template-upgrade/'+t['row']['instance_id']+'/'+route,headers=headers(t['f'][2],actor,key or uuid4().hex),json=data)


def recovery(t,key,actor='fixture-a'):
    return t['f'][3].get('/api/template-upgrade/'+t['row']['instance_id']+'/apply-requests/'+key,headers=headers(t['f'][2],actor))


def full_snapshot(t):
    with t['u']['repository'].connect() as c:
        journal={name:[tuple(r) for r in c.execute('SELECT * FROM '+name+' ORDER BY rowid')] for name in t['u']['repository'].COLUMNS}
    return snapshot(t['u']),journal


def refused(t,data,status=409,**kwargs):
    before=full_snapshot(t);r=apply(t,data,**kwargs);assert r.status_code in (status if isinstance(status,tuple) else (status,)),r.text
    assert full_snapshot(t)==before
    record('refusals',dict(status=r.status_code,no_business_write=True,route=kwargs.get('route','apply-note-carry'),actor=kwargs.get('actor','fixture-a')))
    return r


def partition(t,v,affected,scenario):
    ids={s['adapter_id']:s['id'] for s in t['initial']['steps']};wanted={ids[x] for x in affected};preserved=set(ids.values())-wanted
    n=v['application']['note_carry'];got=set(n['affected']);kept=set(n['preserved'])
    row=record('oracle',dict(scenario=scenario,expected_affected=sorted(wanted),actual_affected=sorted(got),expected_preserved=sorted(preserved),actual_preserved=sorted(kept),intentional_unknown=False,missed_count=len(wanted-got),wrong_count=len(got-wanted),wrong_preserved_count=len(preserved^kept)))
    assert wanted==got and preserved==kept,row


def unchanged_note(t,before,after):
    assert after['id']==before['id'] and after['required_goals']==before['required_goals']==ALL_GOALS
    assert [s['id'] for s in after['steps']]==[s['id'] for s in before['steps']]
    assert [s['contract'] for s in after['steps']]==[s['contract'] for s in before['steps']]
    assert after['owner_amendments']==before['owner_amendments']
    assert after['history']==before['history'] and after['events'][:len(before['events'])]==before['events']


def final_evidence(t):
    value=call(t['u'],'/api/preparations/'+t['row']['preparation_id']+'/goal-results')
    assert value['state']=='LOCAL_OUTPUTS_VERIFIED' and len(value['results'])==6 and not value['case_goal_completed']
    assert {r['goal']:r['actual_output'] for r in value['results']}==t['outputs']
    current=stored(t['f'],t['row']);assert current['owner_amendments']==t['initial']['owner_amendments']
    unchanged_note(t,t['initial'],current)
    record('closures',dict(six_goals_current=True,actual_outputs_preserved=True,manual_note_exact=True,stable_ids_contract_history=True))


@pytest.mark.parametrize('source',['1','2'])
def test_literal_title_or_template_source_carry_and_original_verification(carry,source):
    t=carry;to=target(t,source);v,data=request(t,to);partition(t,v,() if source=='1' else ALL,'NC00_TITLE_ONLY' if source=='1' else 'NC02_TEMPLATE_SOURCE')
    old=deepcopy(stored(t['f'],t['row']));business=facts(t['u']);ledger=note_get(t)['opportunity_revision']
    r=apply(t,data);assert r.status_code==200,r.text;after=stored(t['f'],t['row']);unchanged_note(t,old,after)
    assert facts(t['u'])==business and after['events'][-1]['template_upgrade']['note_carry']['notes']==old['owner_amendments']
    assert note_get(t)['opportunity_revision']==ledger
    if source=='1':assert after['steps']==old['steps']
    else:
        v=plan_read(t['f'],t['row']).json();assert all(s['state']!='VERIFIED' for s in v['steps'])
        for adapter in ALL:verified(t['f'],t['row'],adapter)
    final_evidence(t)


@pytest.mark.parametrize('route',['apply','apply-structure'])
def test_original_routes_never_silently_carry_manual_note(carry,route):
    t=carry;to=target(t);_,d=request(t,to)
    d={k:v for k,v in d.items() if k not in ('confirm_note_carry','expected_note_carry_sha256')}
    if route=='apply-structure':d.update(confirm_structure_change=True,expected_structure_sha256='0'*64)
    refused(t,d,route=route)


@pytest.mark.parametrize('confirmation',[False,1,None])
def test_new_confirmation_is_strict_and_required(carry,confirmation):
    t=carry;_,d=request(t,target(t))
    if confirmation is None:d.pop('confirm_note_carry')
    else:d['confirm_note_carry']=confirmation
    refused(t,d,status=422)


def test_affected_lock_requires_original_unlock_and_fresh_carry(carry):
    t=carry;assert lock(t['f'],t['row'],'P3').status_code==200;to=target(t,'2');v=inspect(t,to)
    assert v['check']['classification']=='LOCK_CONFLICT' and not v['application']['note_carry']['eligible']
    _,d=request(t,to,'KEEP_CURRENT',False);refused(t,d)
    assert plan_command(t['f'],t['row'],'P3','UNLOCK').status_code==200
    _,d=request(t,to);r=apply(t,d);assert r.status_code==200,r.text


@pytest.mark.parametrize('actor',['fixture-b','fixture-c'])
def test_carry_owner_and_tenant_boundaries(carry,actor):
    t=carry;_,d=request(t,target(t));refused(t,d,status=403,actor=actor)


@pytest.mark.parametrize('capability',['READ','PREPARE','EXECUTE'])
def test_current_authority_precedes_original_receipt(carry,capability):
    t=carry;_,d=request(t,target(t));key=uuid4().hex;r=apply(t,d,key=key);assert r.status_code==200,r.text
    with t['f'][1].connect() as c:
        t['f'][1].lock_principal(c,'fixture-a',exclusive=True)
        table='preparation_grants' if capability=='PREPARE' else 'capability_grants'
        c.execute('UPDATE '+table+" SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability=%s",(capability,))
    refused(t,d,status=403,key=key);before=full_snapshot(t);r=recovery(t,key)
    if capability=='EXECUTE':assert r.status_code==200 and r.json()['status']=='COMMITTED',r.text
    else:assert r.status_code==403,r.text
    assert full_snapshot(t)==before


@pytest.mark.parametrize('kind',['material','note','parent','action_grant'])
def test_owned_pg_aba_rejects_same_visible_state(carry,kind):
    t=carry;_,d=request(t,target(t));owner=t['f'][1];id=t['row']['preparation_id']
    if kind=='material':
        with owner.connect() as c:row=c.execute('SELECT * FROM preparation_evidence WHERE preparation_id=%s ORDER BY slot,version DESC',(id,)).fetchone()
        for text in (row['text']+'\nSYNTHETIC TEMP',row['text']):
            with owner.connect() as c:c.execute('UPDATE preparation_evidence SET text=%s,source_sha256=%s WHERE id=%s',(text,hashlib.sha256(text.encode()).hexdigest(),row['id']))
        with owner.connect() as c:assert c.execute('SELECT * FROM preparation_evidence WHERE id=%s',(row['id'],)).fetchone()==row
    elif kind in ('note','parent'):
        before=deepcopy(stored(t['f'],t['row']));temporary=deepcopy(before)
        if kind=='note':next(iter(temporary['owner_amendments'].values()))['text']+='\nSYNTHETIC TEMP'
        else:temporary['revision']+=1
        for plan in (temporary,before):
            with owner.connect() as c:c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),id))
        assert stored(t['f'],t['row'])==before
    else:
        with owner.connect() as c:row=c.execute("SELECT * FROM action_grants WHERE principal_id='fixture-a' AND action='case.create'").fetchone()
        assert row is not None
        for active in (False,row['active']):
            with owner.connect() as c:c.execute('UPDATE action_grants SET active=%s WHERE principal_id=%s AND action=%s',(active,row['principal_id'],row['action']))
        with owner.connect() as c:assert c.execute('SELECT * FROM action_grants WHERE principal_id=%s AND action=%s',(row['principal_id'],row['action'])).fetchone()==row
    refused(t,d);record('aba',dict(kind=kind,fixture_fault_injection=True,visible_original_restored=True,scope='OWNED_PG_ONLY_NO_GENERAL_SQLITE_RESTORE_CLAIM'))


@pytest.mark.parametrize('kind',['withdraw','supersede'])
def test_current_target_head_cannot_reuse_old_carry(carry,kind):
    from parkweave.template_candidate import Command
    t=carry;_,d=request(t,target(t))
    if kind=='supersede':target(t,'3')
    else:
        v=t['u']['engine'].read('template-publisher',t['u']['scope'])
        t['u']['engine'].command('template-publisher',t['u']['scope'],uuid4().hex,Command.model_validate(dict(action='WITHDRAW',expected_revision=v['revision'],expected_definition_sha256=v['definition_sha256'],reason='SYNTHETIC actual source withdrawal')))
    refused(t,d,status=(403,409))


def test_actual_catalog_unknown_refuses_existing_complete_request(carry):
    t=carry;to=target(t);_,d=request(t,to)
    with t['f'][1].connect() as c:c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{kind}','\"UNKNOWN\"') WHERE park_id='park-a' AND service_id='synthetic-material-preparation' AND version=1")
    v=inspect(t,to);assert not v['application']['note_carry']['eligible'];refused(t,d)


def test_actual_new_material_cannot_reuse_prior_carry_or_manual_decision(carry):
    t=carry;_,d=request(t,target(t));p=prep_read(t['f'],t['row']).json()['preparation']
    p=prep_command(t['f'],{**p,'preparation_id':t['row']['preparation_id']},'REOPEN',reason='SYNTHETIC actual new material').json()
    r=material_add(t['f'],p,slot='material_outline',text='SYNTHETIC new current source is not authorized by old manual carry');assert r.status_code==200,r.text
    refused(t,d)


def test_idempotency_conflict_and_cold_original_get(carry):
    t=carry;_,d=request(t,target(t));key=uuid4().hex;r=apply(t,d,key);assert r.status_code==200,r.text;event=r.json()['event'];before=full_snapshot(t)
    r=apply(t,d,key);assert r.status_code==200 and r.json()['event']==event
    r=apply(t,{**d,'reason':'SYNTHETIC changed original input'},key);assert r.status_code==409
    r=recovery(t,key);assert r.status_code==200 and r.json()['status']=='COMMITTED' and r.json()['event']==event
    assert full_snapshot(t)==before


def test_real_pg_save_fault_rolls_back_note_and_migration(carry,monkeypatch):
    from parkweave import service_case_steps as plans
    t=carry;_,d=request(t,target(t));before=full_snapshot(t);original=plans._save;reached=[]
    def fail(*args,**kwargs):
        original(*args,**kwargs);reached.append(True);raise RuntimeError('SYNTHETIC failure after actual plan UPDATE')
    monkeypatch.setattr(plans,'_save',fail)
    r=apply(t,d,key='independent-transaction-fault');assert reached and r.status_code in (500,503),r.text
    assert full_snapshot(t)==before
    assert recovery(t,'independent-transaction-fault').json()['status']=='NOT_OBSERVED'


@pytest.mark.parametrize('carry',['structure_initial'],indirect=True)
def test_registered_structural_strengthening_still_refuses_manual_carry(carry):
    t=carry;to=target(t);v=inspect(t,to)
    assert v['check']['classification']=='NEEDS_RECHECK' and not v['application']['note_carry']['eligible']
    _,d=request(t,to,require_eligible=False);refused(t,d)
    old={k:value for k,value in d.items() if k not in ('confirm_note_carry','expected_note_carry_sha256')}
    old.update(confirm_structure_change=True,expected_structure_sha256=v['application']['structure_sha256'])
    refused(t,old,route='apply-structure')


def test_breaking_target_never_discards_manual(carry):
    t=carry;to=target(t,goals=ALL_GOALS[:-1]);v=inspect(t,to)
    assert v['check']['classification']=='BREAKING_REJECTED' and not v['application']['note_carry']['eligible']
    _,d=request(t,to,'KEEP_CURRENT',False);refused(t,d)


def test_multi_hop_history_and_first_key_survives_later_manual_edit(carry):
    t=carry;_,d=request(t,target(t));key=uuid4().hex;r=apply(t,d,key);assert r.status_code==200,r.text;event=deepcopy(r.json()['event'])
    note_write(t,MANUAL+'\nSYNTHETIC subsequent genuine human reminder')
    ensure_current(t)
    _,second=request(t,target(t,'2'));r=apply(t,second);assert r.status_code==200,r.text
    before=full_snapshot(t);r=recovery(t,key);assert r.status_code==200 and r.json()['status']=='COMMITTED' and r.json()['event']==event
    assert full_snapshot(t)==before
    assert plan_read(t['f'],t['row']).status_code==200


def run_html(t,mode):
    attempt=mode+'-'+uuid4().hex[:8];driver=Path(__file__).with_name('note_template_carry_real_html.js')
    proc=subprocess.Popen(['node',str(driver)],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ);lines=[];error='';final=None;state={}
    def adopted():
        before=state['before'];after=stored(t['f'],t['row']);unchanged_note(t,before,after)
        assert facts(t['u'])==state['facts']
        assert after['owner_amendments']==t['initial']['owner_amendments']
    controls=dict(before_apply=lambda:state.update(before=deepcopy(stored(t['f'],t['row'])),facts=facts(t['u'])),after_apply=adopted,final=lambda:final_evidence(t))
    try:
        proc.stdin.write(json.dumps(dict(base=str(t['f'][3].base_url).rstrip('/'),token=t['f'][2]['fixture-a'],mode=mode,row=t['row'],target=t['target'],manual=MANUAL,plan_id=t['initial']['id']))+'\n');proc.stdin.flush()
        while True:
            assert selector.select(timeout=60),'Original full HTML stopped producing control/output'
            line=proc.stdout.readline()
            if not line:break
            lines.append(line);message=json.loads(line)
            if 'control' in message:controls[message['control']]();proc.stdin.write('{}\n');proc.stdin.flush()
            else:final=message;break
        code=proc.wait(timeout=10);error=proc.stderr.read();assert code==0,error
        assert final and final['scope']=='FULL_ORIGINAL_HTML_NOTE_TEMPLATE_CARRY_ACTUAL_HTTP_ASGI_OWNED_PG'
        record('html-results',dict(mode=mode,checks=final['checks'],requests=len(final['calls']),trace=attempt+'.stdout.jsonl',real_browser='NOT_RUN'))
    finally:
        selector.close()
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
        (OUT/(attempt+'.stdout.jsonl')).write_text(''.join(lines));(OUT/(attempt+'.stderr.log')).write_text(error+proc.stderr.read())


@pytest.mark.parametrize('mode',['title_locked','source_changed'])
def test_complete_original_html_carry_to_six_goals_and_worklist(carry,mode):
    t=carry
    if mode=='title_locked':
        for adapter in ('P1','P3'):assert lock(t['f'],t['row'],adapter).status_code==200
    t['target']=target(t,'1' if mode=='title_locked' else '2')
    run_html(t,mode)
