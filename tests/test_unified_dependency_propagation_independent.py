"""Independent literal employees provenance; real owner HTTP/ASGI/owned PG.

Expected partitions come from frozen literal oracle, never product closure.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import queue
import threading
import subprocess
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb
import test_new_enterprise_local_chain as chain
from test_new_enterprise_local_chain import fresh_chain, ALL_GOALS, call
from test_case_resources import link_fixture, get as link_read, post as link_write
from test_executor_receipts import receipt_fixture, act as receipt_act
from test_preparation import preparation_fixture, headers, read as prep_read
from test_case_fact_clarifications_integration import (post_fact, seed_facts_through_original_api,
    fact_read, declare, confirm_body, confirm, current_parent)
from test_service_plan_manual_lock import stored, lock
from test_service_case_steps import read as plan_read, command as plan_command, verified
from test_case_opportunities import get as opp_read, post as opp_post, body as opp_body, entry
from test_source_change_adoption import adopt
from test_service_plan_recovery import recover
from test_registered_local_revision import add_resource
from test_service_dispatches import offer, command as dispatch_act
from test_case_lifecycle import read as local_read, act as local_act
import test_at24_27_change_batch_independent as batch

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'pyproject.toml').is_file())
OUT=ROOT/'.runtime/unified-propagation-independent/artifacts'
SCOPE='BOUNDED_MULTI_SOURCE_V1'
ALL=('P1','P2','P3','P4','P5')
RUN_ID=uuid4().hex
ORACLE=json.loads((ROOT/'docs/F2/UnifiedSourcePropagationOracle-20261016.json').read_text())
ANSWERS={r['id']:r for r in ORACLE['rows']}


def record(kind,**value):
    OUT.mkdir(parents=True,exist_ok=True)
    row=dict(value,run_id=RUN_ID,test=os.environ.get('PYTEST_CURRENT_TEST'),utc=datetime.now(timezone.utc).isoformat())
    with (OUT/(kind+'-'+RUN_ID+'.jsonl')).open('a') as f:f.write(json.dumps(row,sort_keys=True,default=str)+'\n')


def private_tokens(tokens):
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/('redaction-'+RUN_ID+'.private.json')
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600),'w') as f:json.dump(sorted(set(tokens.values())),f)
    path.chmod(0o600)


def create_declared_case(u,release,selected,number=350):
    # Stop original template flow before ADOPT, then use real original fact APIs.
    row=call(u,'/api/template-consumer/instances',data=chain.input_body(release,number=number),expected=201)
    work=u['f'][0].claim('employees-original-worker');assert work and str(work['id'])==row['run_id'];u['f'][0].finish(work)
    base='/api/template-consumer/instances/'+row['instance_id']
    row=call(u,base+'/resume',data={});assert row['state']=='PLAN_CONFIRMATION_REQUIRED'
    p=current_parent(u['f'],row)
    r=declare(u['f'],p);assert r.status_code==200,r.text
    r=confirm(u['f'],p,confirm_body(u['f'],p,selected));assert r.status_code==200,r.text
    v=call(u,base+'/planning')
    row=call(u,base+'/adopt',data=dict(expected_preparation_revision=v['current']['preparation_revision'],
        expected_request_revision=v['request_intent']['revision'],expected_source_sha256=v['current']['source_sha256'],
        expected_plan_revision=0,required_goals=v['request_intent']['required_goals'],reason='SYNTHETIC explicit original factual Case planning'))
    assert row['state']=='PLAN_ADOPTED'
    return row


@pytest.fixture
def facts_case(fresh_chain):
    u=fresh_chain;f=u['f'];private_tokens(f[2]);selected=seed_facts_through_original_api(f)
    release=chain.publish(u);row=create_declared_case(u,release,selected)
    chain.enable_approval(u,[row]);done=chain.finish_chain(u,row)
    t=dict(u=u,f=f,p=row,rows={'A':row},selected=selected,completed={'A':done},release=release)
    t['initial']={'A':deepcopy(stored(f,row))}
    assert len(t['initial']['A']['required_goals'])==6
    record('baseline',case_id=row['case_id'],run_id=row['run_id'],preparation_id=row['preparation_id'],
        plan_id=t['initial']['A']['id'],step_ids={s['adapter_id']:s['id'] for s in t['initial']['A']['steps']},six_goals_current=True)
    yield t


def full(t):return batch.full_business(t)

def endpoint(t,card):return '/api/preparations/'+t['p']['preparation_id']+'/opportunities/'+card['id']+'/plan-revision'

def impact(t,card=None,user='fixture-a'):
    return t['f'][3].get(endpoint(t,card),headers=headers(t['f'][2],user),params={'dependency_scope':SCOPE})

def view(t,card=None):
    r=impact(t,card);assert r.status_code==200,r.text
    v=r.json();assert v['scope']=='BOUNDED_MULTI_SOURCE_REVISION_PREVIEW'
    assert v['new_grants'] is False
    return v


def partition(t,v,oracle_id):
    a=ANSWERS[oracle_id];ids={s['adapter_id']:s['id'] for s in t['initial']['A']['steps']}
    assert v['affected']==[ids[x] for x in a['affected']]
    assert v['preserved']==[ids[x] for x in a['preserved']]
    assert v['unknown_scope']==a['unknown_scope']
    record('oracle',oracle_id=oracle_id,expected_affected=a['affected'],expected_preserved=a['preserved'],
        actual_affected=v['affected'],actual_preserved=v['preserved'],unknown_scope=v['unknown_scope'],
        missed_count=0,wrong_count=0)


def card(t):
    f,p=t['f'],t['p'];v=opp_read(f,p).json()
    if not v['cards']:
        r=opp_post(f,p,opp_body(v,item=entry()));assert r.status_code==200,r.text;v=r.json()['current']
    r=opp_post(f,p,opp_body(v,'REFRESH'));assert r.status_code==200,r.text
    return next(c for c in r.json()['current']['cards'] if c['is_latest_generation'])


def change_fact(t,kind='employees',value=None,refresh=True):
    f,p=t['f'],t['p']
    if kind in ('employees','same_value','region'):
        field='region' if kind=='region' else 'employees'
        value=value if value is not None else ('PRIVATE_REGION_NEW' if field=='region' else 17 if kind=='same_value' else 29)
        t['selected'][field]=post_fact(f,field,value,'new-'+kind+'-'+uuid4().hex[:6])
    elif kind=='unselected':post_fact(f,'employees',71,'new-unselected-'+uuid4().hex[:6])
    else:raise AssertionError('Unregistered independent source scenario')
    r=confirm(f,p,confirm_body(f,p,t['selected']));assert r.status_code==200,r.text
    return card(t) if refresh else None


def send(t,data,key=None,user='fixture-a'):
    return adopt(t['f'],t['p'],data,key or uuid4().hex,user)


def accepted(t,c):
    v=view(t,c);assert v['can_adopt'],v['blocking_reasons']
    b=deepcopy(v['adoption']);assert b['dependency_scope']==SCOPE and b['local_revision'] and b['opportunity_proof']
    old=deepcopy(stored(t['f'],t['p']));key=uuid4().hex;r=send(t,b,key);assert r.status_code==201,r.text
    now=stored(t['f'],t['p']);proof=now['events'][-1]['local_revision']['source_change']
    assert proof['version']==4 and proof['dependency_propagation']['schema']==2
    assert now['id']==old['id'] and now['required_goals']==ALL_GOALS
    assert now['events'][:-1]==old['events'] and now['history']==old['history']
    assert [s['id'] for s in now['steps']]==[s['id'] for s in old['steps']]
    assert [s['verified_sources'] for s in now['steps']]==[s['verified_sources'] for s in old['steps']]
    record('adoptions',key=key,proof_version=4,plan_id=now['id'],original_verify_evidence_retained=True)
    return b,key,r


def repair_material(t):
    f,u,p=t['f'],t['u'],t['p'];chain.material_decision(u,p,'REVIEW');chain.material_decision(u,p,'CONFIRM');verified(f,p,'P1')
    q=link_read(f,p).json();item=q['current']['record'];current=dict(prep_read(f,p).json()['preparation'],preparation_id=p['preparation_id'])
    r=link_write(f,current,dict(id=item['combination_id']),revision=q['link_revision']);assert r.status_code==201,r.text;verified(f,p,'P2')
    id=t['completed']['A']['dispatch']['dispatch_id'];current=dict(prep_read(f,p).json()['preparation'],preparation_id=p['preparation_id'])
    q=f[3].get('/api/service-dispatches/'+id,headers=headers(f[2],'prep-specialist-fixture-a')).json()
    r=offer(f,current,revision=q['revision'],recovery_receipt_step_id=q['recovery_receipt_step_id'])[0];assert r.status_code==201,r.text
    r=dispatch_act(f,r.json(),'ACCEPT');assert r.status_code==200,r.text;verified(f,p,'P3')
    chain.report_and_ack(u,p,r.json());verified(f,p,'P4');repair_tail(t,('P5',));final(t)


def repair_tail(t,adapters):
    for a in adapters:
        if a!='P5':verified(t['f'],t['p'],a)
    current=local_read(t['f'],t['p']).json()
    if current['verification_current'] is not True:
        r=local_act(t['f'],t['p'],current,'REVALIDATE');assert r.status_code==200,r.text
    else:assert current['local_record_state']=='READY'
    verified(t['f'],t['p'],'P5')


def final(t):
    f,p=t['f'],t['p'];before=full(t);current=stored(f,p);old=t['initial']['A']
    q=call(t['u'],'/api/preparations/'+p['preparation_id']+'/goal-results')
    assert q['state']=='LOCAL_OUTPUTS_VERIFIED' and len(q['results'])==6 and not q['case_goal_completed']
    assert all(r['state']=='LOCAL_OUTPUT_VERIFIED' for r in q['results'])
    assert current['events'][:len(old['events'])]==old['events'] and current['history']==old['history']
    assert [s['id'] for s in current['steps']]==[s['id'] for s in old['steps']]
    rows=[];after=None
    for _ in range(4):
        r=f[3].get('/api/cases/worklist',headers=headers(f[2]),params={'limit':1,**({'after':after} if after else {})});assert r.status_code==200,r.text
        v=r.json();assert v['read_only'] and v['recorded_states_only'];rows.extend(v['items']);after=v['next_after']
        if after is None:break
    hit=next(r for r in rows if r['case_id']==p['case_id'])
    assert hit['run_id']==p['run_id'] and hit['preparation_id']==p['preparation_id']
    assert hit['receipt_step_id']==current['steps'][3]['verified_sources']['receipt_step_id']
    assert not hit['evidence_verified'] and not hit['case_goal_completed']
    assert full(t)==before
    record('closures',six_goals_current=True,worklist_complete=after is None,stable_ids_history=True,worklist_recorded_only=True)


def literal_sha(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def html_controls(t,mode,state):
    f,u,p=t['f'],t['u'],t['p']
    def before_adopt():state['before']=deepcopy(stored(f,p))
    def after_adopt():
        now=stored(f,p);old=state['before'];change=now['events'][-1]['local_revision']['source_change']
        assert change['version']==4 and change['dependency_propagation']['scope']==SCOPE
        assert now['events'][:-1]==old['events'] and now['history']==old['history']
        assert [s['verified_sources'] for s in now['steps']]==[s['verified_sources'] for s in old['steps']]
    def material():chain.material_decision(u,p,'REVIEW');chain.material_decision(u,p,'CONFIRM')
    def resources():
        q=link_read(f,p).json();item=q['current']['record'];current=dict(prep_read(f,p).json()['preparation'],preparation_id=p['preparation_id'])
        r=link_write(f,current,dict(id=item['combination_id']),revision=q['link_revision']);assert r.status_code==201,r.text
    def dispatch():
        id=t['completed']['A']['dispatch']['dispatch_id'];current=dict(prep_read(f,p).json()['preparation'],preparation_id=p['preparation_id'])
        q=f[3].get('/api/service-dispatches/'+id,headers=headers(f[2],'prep-specialist-fixture-a')).json()
        r=offer(f,current,revision=q['revision'],recovery_receipt_step_id=q['recovery_receipt_step_id'])[0];assert r.status_code==201,r.text
        r=dispatch_act(f,r.json(),'ACCEPT');assert r.status_code==200,r.text;state['dispatch']=r.json()
    def report():chain.report_and_ack(u,p,state['dispatch'])
    def local():
        r=local_act(f,p,local_read(f,p).json(),'REVALIDATE');assert r.status_code==200,r.text
    def revoke():
        with f[1].connect() as db:db.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='READ'")
        state['denied_snapshot']=full(t)
    def restore():
        assert full(t)==state['denied_snapshot']
        with f[1].connect() as db:db.execute("UPDATE capability_grants SET active=true,revision=revision+1 WHERE principal_id='fixture-a' AND capability='READ'")
    def denied():assert full(t)==state['denied_snapshot']
    return dict(change_fact=lambda:mixed_change(t,refresh=False),before_adopt=before_adopt,after_adopt=after_adopt,
        review_material=material,relink_resources=resources,reoffer_accept=dispatch,new_report_ack=report,revalidate_local=local,
        final_evidence=lambda:final(t),revoke=revoke,restore=restore,assert_denied_read_no_write=denied)


def run_html(t,mode):
    OUT.mkdir(parents=True,exist_ok=True);state={};controls=html_controls(t,mode,state)
    config=dict(base=str(t['f'][3].base_url).rstrip('/'),token=t['f'][2]['fixture-a'],mode=mode,A=t['p'])
    if mode in ('current_403','late_403'):
        config['card']=card(t)['id']
        if mode=='late_403':
            B=create_declared_case(t['u'],t['release'],t['selected'],number=351)
            # B has original actual fact choices and plan but no fabricated VERIFY.
            q=opp_read(t['f'],B).json();r=opp_post(t['f'],B,opp_body(q,item=entry()));assert r.status_code==200,r.text
            config.update(B=B,cardB=r.json()['current']['cards'][0]['id'])
    script=Path(__file__).with_name('unified_dependency_propagation_real_html.js')
    process=subprocess.Popen(['node',str(script)],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    incoming=queue.Queue();lines=[];err='';result=None
    def consume_stdout():
        for line in process.stdout:incoming.put(line)
        incoming.put(None)
    reader=threading.Thread(target=consume_stdout,daemon=True);reader.start()
    attempt=mode+'-'+uuid4().hex[:8]
    try:
        process.stdin.write(json.dumps(config)+'\n');process.stdin.flush()
        while True:
            try:line=incoming.get(timeout=45)
            except queue.Empty:raise AssertionError('Original employees HTML flow made no progress for45 seconds')
            if line is None:break
            lines.append(line);msg=json.loads(line)
            if 'trace' in msg:continue
            if 'control' in msg:
                controls[msg['control']]();process.stdin.write('{}\n');process.stdin.flush()
            else:result=msg;break
        code=process.wait(timeout=10);err=process.stderr.read();assert code==0,err
        assert result and result['scope']=='FULL_ORIGINAL_HTML_UNIFIED_PROPAGATION_ACTUAL_HTTP_ASGI_OWNED_PG'
        assert result['fake_dto'] is False and result['real_browser']=='NOT_RUN'
        record('html-results',mode=mode,checks=result['checks'],requests=len(result['calls']),trace=attempt+'.stdout.jsonl',actual_http=True,real_browser='NOT_RUN')
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=5)
        reader.join(timeout=5)
        while not incoming.empty():
            line=incoming.get_nowait()
            if line is not None:lines.append(line)
        (OUT/(attempt+'.stdout.jsonl')).write_text(''.join(lines));(OUT/(attempt+'.stderr.log')).write_text(err+process.stderr.read())



@pytest.mark.parametrize('mode',['positive','lost_ack','current_403','late_403'])
def test_full_original_html_unified_adoption_and_authority(facts_case,mode):run_html(facts_case,mode)


def change_receipt(t):
    id=t['completed']['A']['dispatch']['receipt_step_id']
    q=t['f'][3].get('/api/executor-receipts/'+id,headers=headers(t['f'][2])).json()
    r=receipt_act(t['f'],q,'REOPEN');assert r.status_code==200,r.text
    chain.report_and_ack(t['u'],t['p'],dict(receipt_step_id=id))


def mixed_change(t,refresh=True):
    # Receipt bound to current preparation: change through its original API first.
    change_receipt(t)
    change_fact(t,refresh=False)
    from test_preparation import add,command
    p=dict(prep_read(t['f'],t['p']).json()['preparation'],preparation_id=t['p']['preparation_id'])
    # Original confirmation already leaves preparation requiring material review.
    if p['state'] in ('REVIEWED','LOCAL_CONFIRMED'):
        r=command(t['f'],p,'REOPEN',reason='SYNTHETIC mixed source reopening');assert r.status_code==200,r.text;p=r.json()
    r=add(t['f'],p,slot='need_summary',text='SYNTHETIC independently changed source context');assert r.status_code==200,r.text
    add_resource(t['f'])
    record('mixed-source-changes',material=True,fact=True,resource_collection=True,receipt=True,service_rule_source_revision=False)
    return card(t) if refresh else None


def test_actual_mixed_material_fact_resource_receipt_explicit_adopt_verify(facts_case):
    t=facts_case;c=mixed_change(t);v=view(t,c);partition(t,v,'UP09')
    q=v['dependency_propagation'];assert q['schema']==2 and q['scope']==SCOPE
    assert v['source_impact']['schema']==1
    assert {n['type'] for n in q['nodes']} >= {'MATERIAL','FACT','RESOURCE','RECEIPT'}
    accepted(t,c);repair_material(t)


def test_receipt_change_retains_three_original_locked_steps(facts_case):
    t=facts_case
    for a in ('P1','P2','P3'):assert lock(t['f'],t['p'],a).status_code==200
    old=deepcopy(stored(t['f'],t['p']));change_receipt(t);c=card(t)
    partition(t,view(t,c),'UP25');accepted(t,c);repair_tail(t,('P4','P5'));final(t)
    assert stored(t['f'],t['p'])['steps'][:3]==old['steps'][:3]


def test_resource_change_affected_manual_lock_needs_original_unlock(facts_case):
    t=facts_case;assert lock(t['f'],t['p'],'P1').status_code==200;assert lock(t['f'],t['p'],'P3').status_code==200
    old=deepcopy(stored(t['f'],t['p']));add_resource(t['f']);c=card(t);v=view(t,c)
    partition(t,v,'UP26');assert not v['can_adopt'] and 'AFFECTED_LOCK_REQUIRES_EXPLICIT_UNLOCK' in v['blocking_reasons']
    assert plan_command(t['f'],t['p'],'P3','UNLOCK').status_code==200
    accepted(t,c);repair_tail(t,('P2','P3','P4','P5'));final(t)
    assert stored(t['f'],t['p'])['steps'][0]==old['steps'][0]


def test_same_key_altered_scope_and_actual_original_cold_get(facts_case):
    t=facts_case;c=mixed_change(t);b,key,r=accepted(t,c);before=full(t)
    q=recover(t['f'],t['p'],key);assert q.status_code==200 and q.json()['status']=='COMMITTED' and full(t)==before
    assert send(t,b,key).status_code==201 and full(t)==before
    assert send(t,{k:v for k,v in b.items() if k!='dependency_scope'},key).status_code==409 and full(t)==before
    repair_material(t)


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a'])
def test_original_owner_tenant_role_scope_refuses_graph_and_adopt(facts_case,user):
    t=facts_case;c=mixed_change(t);b=view(t,c)['adoption'];before=full(t)
    r=impact(t,c,user);assert r.status_code==403 and 'dependency_propagation' not in r.text
    assert send(t,b,user=user).status_code==403 and full(t)==before


def test_resource_row_a_b_a_refuses_preview_after_values_restore(facts_case):
    t=facts_case;add_resource(t['f']);c=card(t);b=view(t,c)['adoption']
    with t['f'][1].connect() as db:r=db.execute('SELECT id,capacity FROM synthetic_resources ORDER BY id LIMIT 1').fetchone()
    with t['f'][1].connect() as db:db.execute('UPDATE synthetic_resources SET capacity=capacity+1 WHERE id=%s',(r['id'],))
    with t['f'][1].connect() as db:db.execute('UPDATE synthetic_resources SET capacity=%s WHERE id=%s',(r['capacity'],r['id']))
    before=full(t);assert send(t,b).status_code==409 and full(t)==before


def test_unconfirmed_fact_selection_unknown_never_authorizes(facts_case):
    t=facts_case;post_fact(t['f'],'employees',99,'SYNTHETIC competing unselected fact')
    c=card(t);v=view(t,c);partition(t,v,'UP24')
    assert not v['can_adopt'] and v['adoption'] is None


def test_new_v4_then_original_default_v2_is_nonsticky(facts_case):
    from test_source_change_adoption import preview as original_preview
    t=facts_case;c=mixed_change(t);accepted(t,c);repair_material(t)
    old=deepcopy(stored(t['f'],t['p']));add_resource(t['f']);c=card(t);v=original_preview(t['f'],t['p'],c).json()
    assert v['scope']=='SOURCE_CHANGE_LOCAL_REVISION_PREVIEW' and 'dependency_scope' not in v['adoption']
    key=uuid4().hex;r=send(t,v['adoption'],key);assert r.status_code==201,r.text
    now=stored(t['f'],t['p']);change=now['events'][-1]['local_revision']['source_change']
    assert change['version']==2 and 'dependency_propagation' not in change and now['events'][:len(old['events'])]==old['events']
    assert recover(t['f'],t['p'],key).json()['status']=='COMMITTED'
    repair_tail(t,('P2','P3','P4','P5'));final(t)

@pytest.mark.parametrize('decision',['KEEP_AND_CONTINUE','DEFER'])
def test_manual_source_conflict_reuses_original_explicit_package_decisions(facts_case,decision):
    from test_plan_source_conflicts import edit,read as note_read,send as note_send
    from test_preparation import add,command
    t=facts_case;f,p=t['f'],t['p'];manual=edit(f,p,'SYNTHETIC original manual note retained verbatim')['current']['note']
    current=dict(prep_read(f,p).json()['preparation'],preparation_id=p['preparation_id'])
    r=command(f,current,'REOPEN',reason='SYNTHETIC explicit actual material change');assert r.status_code==200,r.text
    r=add(f,r.json(),slot='material_outline',text=manual['text']);assert r.status_code==200,r.text
    c=card(t);v=view(t,c);partition(t,v,'UP27')
    assert not v['can_adopt'] and any('SOURCE' in s for s in v['blocking_reasons'])
    if decision=='DEFER':
        q=note_read(f,p,c).json();r=note_send(f,p,q,'DEFER');assert r.status_code==200,r.text
        v=view(t,c);partition(t,v,'UP29');assert not v['can_adopt'] and 'OWNER_NOTE_SOURCE_DEFERRED' in v['blocking_reasons']
    else:
        path='/api/preparations/'+p['preparation_id']+'/plan-material-package'
        q=f[3].get(path,headers=headers(f[2]),params={'card_id':c['id']}).json()
        b=dict(schema=2,action='KEEP_AND_CONTINUE',expected_plan_id=q['plan_id'],expected_plan_revision=q['plan_revision'],expected_note_revision=q['note']['revision'],expected_ledger_revision=q['opportunity_revision'],expected_preview_sha256=q['preview_sha256'],card_id=q['card_id'],text=None,reason='SYNTHETIC explicit original KEEP and continue',confirm_package=True)
        r=f[3].post(path+'/commands',headers=headers(f[2],key=uuid4().hex),json=b);assert r.status_code==200,r.text
        assert r.json()['current']['note']['text']==manual['text']
        v=view(t,c);partition(t,v,'UP28');assert v['can_adopt'],v['blocking_reasons']
        accepted(t,c);repair_material(t)


def test_original_execute_revocation_then_restore_cannot_revive_prior_preview(facts_case):
    t=facts_case;add_resource(t['f']);c=card(t);b=view(t,c)['adoption'];f=t['f']
    with f[1].connect() as db:db.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='EXECUTE'")
    before=full(t);assert send(t,b).status_code==403 and full(t)==before
    with f[1].connect() as db:db.execute("UPDATE capability_grants SET active=true,revision=revision+1 WHERE principal_id='fixture-a' AND capability='EXECUTE'")
    before=full(t);assert send(t,b).status_code==409 and full(t)==before

@pytest.mark.parametrize('damage',['observation','edge','path'])
def test_rehashed_forged_v4_graph_refuses_original_plan_goal_and_cold_reads(facts_case,damage):
    from parkweave import controlled_plans as cp
    from parkweave.service_case_steps import Adopt,_adopt_request
    t=facts_case;add_resource(t['f']);c=card(t);b,key,_=accepted(t,c)
    plan=deepcopy(stored(t['f'],t['p']));event=plan['events'][-1];change=event['local_revision']['source_change'];q=change['dependency_propagation']
    if damage=='observation':q['observations'][0]['changed']=not q['observations'][0]['changed']
    elif damage=='edge':q['edges'][0]['kind']='VERIFIED_BY' if q['edges'][0]['kind']!='VERIFIED_BY' else 'MATERIAL'
    else:q['propagation_paths'][0]['edge_ids']=[]
    q['sha256']=literal_sha({k:v for k,v in q.items() if k!='sha256'})
    change['sha256']=literal_sha({k:v for k,v in change.items() if k!='sha256'})
    request=event['local_revision']['request'];request['opportunity_proof']['expected_preview_sha256']=change['sha256']
    event['fingerprint']=cp._hash(dict(preparation_id=t['p']['preparation_id'],action='ADOPT',**_adopt_request(Adopt.model_validate(request))))
    with t['f'][1].connect() as db:db.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),t['p']['preparation_id']))
    before=full(t)
    assert plan_read(t['f'],t['p']).status_code==409
    assert recover(t['f'],t['p'],key).status_code==409
    r=t['f'][3].get('/api/preparations/'+t['p']['preparation_id']+'/goal-results',headers=headers(t['f'][2]));assert r.status_code==409
    assert full(t)==before



def test_catalog_rule_contract_mixed_change_preserves_original_explicit_replacement_refusal(facts_case):
    t=facts_case;f,p=t['f'],t['p']
    for a in ('P1','P3'):assert lock(f,p,a).status_code==200
    mixed_change(t,refresh=False)
    with f[1].connect() as db:
        db.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{revision}','\"UNIFIED-source-v2\"') WHERE park_id='park-a' AND service_id='synthetic-material-preparation' AND version=1")
    c=card(t);old=deepcopy(stored(f,p));before=full(t);v=view(t,c)
    partition(t,v,'UP09')  # Partition only: several actual direct sources changed.
    assert not v['can_adopt'] and 'CATALOG_CHANGED' in v['blocking_reasons']
    assert len(old['required_goals'])==6 and old['required_goals']==ALL_GOALS
    assert all(old['steps'][i]['manual_lock'] is not None for i in (0,2))
    assert send(t,v['adoption']).status_code==409
    assert stored(f,p)==old and full(t)==before
    record('catalog-rule-refusal',source_revision_changed=True,mixed_material_fact_receipt_resource=True,blocking_reasons=v['blocking_reasons'],six_goals_history_locks_retained=True,no_business_writes=True,original_explicit_replacement_required=True)
