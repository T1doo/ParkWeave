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
OUT=ROOT/'.runtime/plan-reapproval-independent/artifacts'
ALL=('P1','P2','P3','P4','P5')
RUN_ID=uuid4().hex
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


@pytest.fixture(autouse=True)
def route_artifacts_before_business_fixtures(monkeypatch):
    # Autouse precedes non-autouse fresh_chain dependency setup. Only artifact
    # destinations change; product functions, clocks, grants and assertions do not.
    import sys
    routes=[]
    for name,module in list(sys.modules.items()):
        if not name.startswith('test_') or module is sys.modules[__name__]:continue
        value=getattr(module,'OUT',None)
        if isinstance(value,Path) and (str(value).startswith('.runtime/') or '.runtime' in value.parts):
            destination=OUT/'helpers'/name
            monkeypatch.setattr(module,'OUT',destination)
            routes.append(dict(module=name,original=str(value),actual=str(destination)))
    record('artifact-routing',before_fresh_chain=True,product_logic_changed=False,routes=routes)


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
    from parkweave.service_plan_approval import IsolatedPlanApproval
    t['bridge']=IsolatedPlanApproval(f[1],f[1]._case_fact_fixture_receipt,preparation_ids=[row['preparation_id']],enabled_for_isolated_tests=True,enabled_for_source_reapproval_tests=True)
    t['bridge'].attach_store(f[0])
    yield t


def full(t):return batch.full_business(t)


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



from test_case_resource_delivery import preview as delivery_preview,submit as commit,recover as delivery_recover,effects
from test_service_plan_approval import read as approval_read,propose,decide,ledger
from test_resource_bundles import states
from test_preparation import command as prepare,add as add_material
from parkweave.resource_holds import RESOURCE_ID


def original_rows(t):
    with t['f'][1].connect() as db:
        return {table:db.execute('SELECT * FROM '+table+' ORDER BY to_jsonb('+table+')::text').fetchall() for table in ('case_resource_links','synthetic_resource_combinations','synthetic_resource_combination_members','synthetic_resource_combination_receipts','resource_case_claims')}


def assert_prefix_preserved(before,after):
    for table,rows in before.items():
        assert all(row in after[table] for row in rows),table


def source_adopt(t,kind='material_fact'):
    f,p=t['f'],t['p'];old=deepcopy(stored(f,p))
    if kind=='resource':add_resource(f)
    else:
        change_fact(t,refresh=False)
        current=dict(prep_read(f,p).json()['preparation'],preparation_id=p['preparation_id'])
        if current['state'] in ('REVIEWED','LOCAL_CONFIRMED'):
            r=prepare(f,current,'REOPEN',reason='SYNTHETIC explicit source reapproval input');assert r.status_code==200,r.text;current=r.json()
        r=add_material(f,current,slot='need_summary',text='SYNTHETIC actual source reapproval context v2');assert r.status_code==200,r.text
    c=card(t)
    from test_source_change_adoption import preview
    q=preview(f,p,c);assert q.status_code==200,q.text;v=q.json()
    ids={s['adapter_id']:s['id'] for s in old['steps']};wanted=ALL if kind!='resource' else ('P2','P3','P4','P5')
    assert v['affected']==[ids[a] for a in wanted]
    assert v['preserved']==([] if kind!='resource' else [ids['P1']]) and v['unknown_scope'] is None
    r=adopt(f,p,v['adoption']);assert r.status_code==201,r.text
    if kind!='resource':
        chain.material_decision(t['u'],p,'REVIEW');chain.material_decision(t['u'],p,'CONFIRM');verified(f,p,'P1')
    now=stored(f,p);assert now['id']==old['id'] and now['events'][:len(old['events'])]==old['events']
    record('source-adopt',kind=kind,affected=list(wanted),preserved=[] if kind!='resource' else ['P1'],original_source_change=True,original_p1_verify=True)
    return now


def fresh_holds(t):
    hs,data=chain.holds(t['u'],offset=12)
    assert states(t['f'],hs)==['HELD']*3
    return hs,data


def quote(t,data,revision=None,user='fixture-a'):
    if revision is None:revision=link_read(t['f'],t['p']).json()['link_revision']
    q=delivery_preview(t['f'],t['p'],{**data,'expected_link_revision':revision},user)
    assert q.status_code==200,q.text;q=q.json();assert q['expected_link_revision']==revision
    return {**data,'expected_link_revision':revision,'expected_preparation_revision':q['expected_preparation_revision'],'expected_plan_revision':q['expected_plan_revision'],'expected_source_sha256':q['source_sha256'],'valid_until':q['valid_until'],'reason':'SYNTHETIC explicit new source same-Case reapproval delivery'},q


def approved(t,data):
    f,p=t['f'],t['p'];q=approval_read(f,p);assert q.status_code==200,q.text
    r=propose(f,p,data,revision=q.json()['revision']);assert r.status_code==201,r.text
    q=r.json();item=q['items'][-1];r=decide(f,p,item,q['revision']);assert r.status_code==200,r.text
    item=r.json()['items'][-1];assert item['state']=='APPROVED' and item['current_available']
    return item


def finish_new_link(t):
    f,p=t['f'],t['p'];verified(f,p,'P2')
    id=t['completed']['A']['dispatch']['dispatch_id'];current=dict(prep_read(f,p).json()['preparation'],preparation_id=p['preparation_id'])
    q=f[3].get('/api/service-dispatches/'+id,headers=headers(f[2],'prep-specialist-fixture-a')).json()
    r=offer(f,current,revision=q['revision'],recovery_receipt_step_id=q['recovery_receipt_step_id'])[0];assert r.status_code==201,r.text
    r=dispatch_act(f,r.json(),'ACCEPT');assert r.status_code==200,r.text;verified(f,p,'P3')
    chain.report_and_ack(t['u'],p,r.json());verified(f,p,'P4');repair_tail(t,('P5',));final(t)


def prepared_reapproval(t,kind='material_fact'):
    source_adopt(t,kind);hs,data=fresh_holds(t);data,q=quote(t,data);item=approved(t,data)
    return hs,{**data,'approval_id':item['id']},q,item


def no_effect(t,data,expected=409,key=None,user='fixture-a'):
    before=full(t);r=commit(t['f'],t['p'],data,key,user);assert r.status_code==expected,r.text
    assert full(t)==before
    record('refusals',status=r.status_code,no_business_writes=True)
    return r


@pytest.mark.parametrize('kind',['material_fact','resource'])
def test_actual_explicit_original_reapproval_and_partial_verify_to_six_goals(facts_case,kind):
    t=facts_case;f,p=t['f'],t['p']
    if kind=='resource':assert lock(f,p,'P1').status_code==200
    oldplan=deepcopy(stored(f,p));old=original_rows(t);oldledger=deepcopy(ledger(f,p));oldlink=link_read(f,p).json()['link_revision']
    hs,data,q,item=prepared_reapproval(t,kind)
    key=uuid4().hex;r=commit(f,p,data,key);assert r.status_code==201,r.text;x=r.json()
    assert x['independent_check']['status']=='CURRENT' and x['independent_check']['plan_p2_automatically_verified'] is False
    assert x['link']['revision']==oldlink+1 and states(f,hs)==['CONFIRMED']*3
    assert effects(f)==[2,6,2,2,2]
    assert_prefix_preserved(old,original_rows(t));assert ledger(f,p)['events'][:len(oldledger['events'])]==oldledger['events']
    assert ledger(f,p)['revision']==oldledger['revision']+3
    before=full(t);assert commit(f,p,data,key).json()['receipt']==x['receipt'];assert full(t)==before
    recovered=delivery_recover(f,p,key);assert recovered.status_code==200 and recovered.json()['receipt']==x['receipt'] and full(t)==before
    if kind=='resource':assert stored(f,p)['steps'][0]==oldplan['steps'][0]
    finish_new_link(t);assert_prefix_preserved(old,original_rows(t))
    r=delivery_recover(f,p,t['completed']['A']['delivery_key']);assert r.status_code==200 and r.json()['independent_check']['status']=='NEEDS_RECHECK'
    record('closure',kind=kind,six_goals=True,new_link_revision=oldlink+1,old_occupancy_preserved=True,old_receipt_cold_get=True)


def test_original_default_first_delivery_and_unapproved_reapproval_refuse(facts_case):
    t=facts_case;source_adopt(t);hs,data=fresh_holds(t)
    before=full(t);r=delivery_preview(t['f'],t['p'],data);assert r.status_code==409 and full(t)==before
    b,_=quote(t,data);before=full(t);r=propose(t['f'],t['p'],b,revision=approval_read(t['f'],t['p']).json()['revision']);assert r.status_code==201,r.text
    item=r.json()['items'][-1];no_effect(t,{**b,'approval_id':item['id']});assert states(t['f'],hs)==['HELD']*3


def test_consumed_old_approval_cannot_authorize_new_source_delivery(facts_case):
    t=facts_case;old=ledger(t['f'],t['p']);oldid=approval_read(t['f'],t['p']).json()['items'][-1]['id']
    source_adopt(t);hs,data=fresh_holds(t);b,_=quote(t,data)
    no_effect(t,{**b,'approval_id':oldid});assert ledger(t['f'],t['p'])==old and states(t['f'],hs)==['HELD']*3


@pytest.mark.parametrize('actor',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a'])
def test_original_tenant_owner_and_role_cannot_read_or_commit_new_approval(facts_case,actor):
    t=facts_case;hs,b,q,item=prepared_reapproval(t)
    no_effect(t,b,expected=403,user=actor)
    before=full(t);assert approval_read(t['f'],t['p'],actor).status_code==403
    assert delivery_recover(t['f'],t['p'],uuid4().hex,actor).status_code==403 and full(t)==before


@pytest.mark.parametrize('damage',['resource_revision','resource_aba','plan_revision','authority_aba','preparation_revision'])
def test_approved_new_object_never_revives_after_original_source_change(facts_case,damage):
    t=facts_case;f,p=t['f'],t['p'];hs,b,q,item=prepared_reapproval(t)
    if damage=='plan_revision':assert lock(f,p,'P1').status_code==200
    elif damage=='preparation_revision':
        current=dict(prep_read(f,p).json()['preparation'],preparation_id=p['preparation_id']);r=prepare(f,current,'REOPEN',reason='SYNTHETIC after-approval source change');assert r.status_code==200,r.text
    elif damage=='authority_aba':
        with f[1].connect() as db:db.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='EXECUTE'")
        with f[1].connect() as db:db.execute("UPDATE capability_grants SET active=true,revision=revision+1 WHERE principal_id='fixture-a' AND capability='EXECUTE'")
    else:
        with f[1].connect() as db:row=db.execute('SELECT capacity FROM synthetic_resources WHERE id=%s',(hs[0]['resource_id'],)).fetchone();db.execute('UPDATE synthetic_resources SET capacity=capacity+1 WHERE id=%s',(hs[0]['resource_id'],))
        if damage=='resource_aba':
            with f[1].connect() as db:db.execute('UPDATE synthetic_resources SET capacity=%s WHERE id=%s',(row['capacity'],hs[0]['resource_id']))
    no_effect(t,b);assert states(f,hs)==['HELD']*3


@pytest.mark.parametrize('field',['reason','expected_link_revision','approval_id','valid_until'])
def test_exact_old_key_replay_rejects_changed_reapproval_parameters(facts_case,field):
    t=facts_case;hs,b,q,item=prepared_reapproval(t);key=uuid4().hex;r=commit(t['f'],t['p'],b,key);assert r.status_code==201,r.text
    changed=deepcopy(b)
    if field=='reason':changed[field]+=' changed'
    elif field=='expected_link_revision':changed[field]+=1
    elif field=='approval_id':changed[field]=str(uuid4())
    else:changed[field]='2099-01-01T00:00:00Z'
    no_effect(t,changed,key=key)


def test_unknown_original_key_get_never_executes_reapproval(facts_case):
    t=facts_case;source_adopt(t);hs,data=fresh_holds(t);before=full(t)
    r=delivery_recover(t['f'],t['p'],uuid4().hex);assert r.status_code==200 and r.json()['status']=='NOT_OBSERVED' and full(t)==before
    assert states(t['f'],hs)==['HELD']*3


def html_controls(t,state):
    f,u,p=t['f'],t['u'],t['p']
    def change():
        change_fact(t,refresh=False)
        current=dict(prep_read(f,p).json()['preparation'],preparation_id=p['preparation_id'])
        if current['state'] in ('REVIEWED','LOCAL_CONFIRMED'):
            r=prepare(f,current,'REOPEN',reason='SYNTHETIC actual HTML source update');assert r.status_code==200,r.text;current=r.json()
        r=add_material(f,current,slot='need_summary',text='SYNTHETIC actual HTML reapproval context v2');assert r.status_code==200,r.text
    def material():chain.material_decision(u,p,'REVIEW');chain.material_decision(u,p,'CONFIRM')
    def holds():
        hs,data=fresh_holds(t);state['holds']=hs;state['members']=data
        return dict(holds=[h['id'] for h in hs])
    def before():state['old_rows']=original_rows(t);state['old_ledger']=deepcopy(ledger(f,p));state['plan']=deepcopy(stored(f,p))
    def after():
        assert effects(f)==[2,6,2,2,2] and states(f,state['holds'])==['CONFIRMED']*3
        assert_prefix_preserved(state['old_rows'],original_rows(t));assert ledger(f,p)['events'][:-1]==state['old_ledger']['events']
        assert ledger(f,p)['revision']==state['old_ledger']['revision']+1
        assert stored(f,p)==state['plan'], 'new resource commit never auto-verifies original plan'
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
        state['denied']=full(t)
    def restore():
        assert full(t)==state['denied']
        with f[1].connect() as db:db.execute("UPDATE capability_grants SET active=true,revision=revision+1 WHERE principal_id='fixture-a' AND capability='READ'")
    def denied():assert full(t)==state['denied']
    return dict(change_sources=change,repair_material=material,fresh_holds=holds,before_commit=before,after_commit=after,reoffer_accept=dispatch,new_report_ack=report,revalidate_local=local,final_evidence=lambda:final(t),revoke=revoke,restore=restore,assert_denied_read_no_write=denied)


def run_html(t,mode):
    OUT.mkdir(parents=True,exist_ok=True);state={};controls=html_controls(t,state)
    config=dict(base=str(t['f'][3].base_url).rstrip('/'),token=t['f'][2]['fixture-a'],mode=mode,A=t['p'])
    if mode=='late_403':
        config['B']=create_declared_case(t['u'],t['release'],t['selected'],number=351)
        from parkweave.service_plan_approval import IsolatedPlanApproval
        bridge=IsolatedPlanApproval(t['f'][1],t['f'][1]._case_fact_fixture_receipt,preparation_ids=[t['p']['preparation_id'],config['B']['preparation_id']],enabled_for_isolated_tests=True,enabled_for_source_reapproval_tests=True);bridge.attach_store(t['f'][0]);state['bridge']=bridge
    script=Path(__file__).with_name('plan_source_reapproval_real_html.js')
    process=subprocess.Popen(['node',str(script)],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    incoming=queue.Queue();lines=[];err='';result=None
    def consume():
        for line in process.stdout:incoming.put(line)
        incoming.put(None)
    reader=threading.Thread(target=consume,daemon=True);reader.start();attempt=mode+'-'+uuid4().hex[:8]
    try:
        process.stdin.write(json.dumps(config)+'\n');process.stdin.flush()
        while True:
            try:line=incoming.get(timeout=45)
            except queue.Empty:raise AssertionError('Original reapproval HTML made no progress for45 seconds')
            if line is None:break
            lines.append(line);msg=json.loads(line)
            if 'trace' in msg:continue
            if 'control' in msg:
                reply=controls[msg['control']]();process.stdin.write(json.dumps(reply or {})+'\n');process.stdin.flush()
            else:result=msg;break
        code=process.wait(timeout=10);err=process.stderr.read();assert code==0,err
        assert result and result['scope']=='FULL_ORIGINAL_HTML_PLAN_SOURCE_REAPPROVAL_ACTUAL_HTTP_ASGI_OWNED_PG'
        assert result['fake_dto'] is False and result['real_browser']=='NOT_RUN'
        record('html-results',mode=mode,checks=result['checks'],nativefetch_calls=len(result['calls']),trace=attempt+'.stdout.jsonl',actual_http=True,real_browser='NOT_RUN',python_control_api_count='NOT_RECORDED')
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=5)
        reader.join(timeout=5)
        while not incoming.empty():
            line=incoming.get_nowait()
            if line is not None:lines.append(line)
        (OUT/(attempt+'.stdout.jsonl')).write_text(''.join(lines));(OUT/(attempt+'.stderr.log')).write_text(err+process.stderr.read())


@pytest.mark.parametrize('mode',['positive','lost_ack','current_403','late_403'])
def test_full_original_html_source_reapproval_and_original_authority(facts_case,mode):run_html(facts_case,mode)


@pytest.mark.parametrize('capability',['READ','EXECUTE','PREPARE','resource_READ','resource_HOLD'])
def test_actual_original_revocation_denies_new_reapproval_without_effect(facts_case,capability):
    t=facts_case;f,p=t['f'],t['p'];hs,b,q,item=prepared_reapproval(t)
    with f[1].connect() as db:
        if capability.startswith('resource_'):
            db.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability=%s",(capability.split('_',1)[1],))
        elif capability=='PREPARE':db.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
        else:db.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability=%s",(capability,))
    no_effect(t,b,expected=403);assert states(f,hs)==['HELD']*3


def test_expired_new_hold_refuses_quote_and_never_uses_old_approval(facts_case):
    t=facts_case;source_adopt(t);hs,data=fresh_holds(t)
    with t['f'][1].connect() as db:db.execute("UPDATE synthetic_resource_holds SET expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",(hs[0]['id'],))
    before=full(t);r=delivery_preview(t['f'],t['p'],{**data,'expected_link_revision':1});assert r.status_code==409 and full(t)==before


def test_no_explicit_source_opt_in_refuses_new_mode_under_original_issued_fixture(facts_case):
    t=facts_case;source_adopt(t);hs,data=fresh_holds(t)
    from parkweave.service_plan_approval import IsolatedPlanApproval
    bridge=IsolatedPlanApproval(t['f'][1],t['f'][1]._case_fact_fixture_receipt,preparation_ids=[t['p']['preparation_id']],enabled_for_isolated_tests=True);bridge.attach_store(t['f'][0])
    before=full(t);r=delivery_preview(t['f'],t['p'],{**data,'expected_link_revision':1});assert r.status_code==403 and full(t)==before
    assert states(t['f'],hs)==['HELD']*3


@pytest.mark.parametrize('fault_table',['synthetic_resource_combination_receipts','resource_case_claims','case_resource_links'])
def test_owned_pg_fault_rolls_back_entire_reapproval_transaction(facts_case,fault_table):
    import psycopg
    from uuid import UUID
    from parkweave import case_resource_delivery as delivery
    t=facts_case;f,p=t['f'],t['p'];hs,b,q,item=prepared_reapproval(t)
    with f[1].connect() as db:
        db.execute("CREATE FUNCTION reapproval_fault() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN RAISE EXCEPTION 'synthetic isolated reapproval rollback';END$$")
        db.execute('CREATE TRIGGER reapproval_fault BEFORE INSERT ON '+fault_table+' FOR EACH ROW EXECUTE FUNCTION reapproval_fault()')
    before=full(t)
    # Original Python service entry, original SQL transaction, owned PG fault;
    # this fault probe is not labelled nativeHTTP.
    with pytest.raises(psycopg.Error):delivery.deliver(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,delivery.Deliver(**b))
    assert full(t)==before and states(f,hs)==['HELD']*3
    record('rollback',fault_table=fault_table,actual_pg=True,actual_http=False,no_business_writes=True)
