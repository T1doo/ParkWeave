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
OUT=ROOT/'.runtime/fact-provenance-independent/artifacts'
SCOPE='EMPLOYEES_USER_ASSERTION_V1'
ALL=('P1','P2','P3','P4','P5')
RUN_ID=uuid4().hex
ORACLE=json.loads((ROOT/'docs/F2/EmployeesFactProvenanceOracle-20261015.json').read_text())
ANSWERS={r['id']:r['expected'] for r in ORACLE['rows']}


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

def endpoint(t):return '/api/preparations/'+t['p']['preparation_id']+'/employees-fact-impact'

def impact(t,card=None,user='fixture-a'):
    return t['f'][3].get(endpoint(t),headers=headers(t['f'][2],user),params={'card_id':card['id']} if card else {})

def view(t,card=None):
    r=impact(t,card);assert r.status_code==200,r.text
    v=r.json();assert v['scope']=='EMPLOYEES_FACT_PROVENANCE_PREVIEW'
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
    b=deepcopy(v['adoption']);assert b['fact_provenance_scope']==SCOPE and b['local_revision'] and b['opportunity_proof']
    old=deepcopy(stored(t['f'],t['p']));key=uuid4().hex;r=send(t,b,key);assert r.status_code==201,r.text
    now=stored(t['f'],t['p']);proof=now['events'][-1]['local_revision']['source_change']
    assert proof['version']==3 and proof['fact_provenance']
    assert now['id']==old['id'] and now['required_goals']==ALL_GOALS
    assert now['events'][:-1]==old['events'] and now['history']==old['history']
    assert [s['id'] for s in now['steps']]==[s['id'] for s in old['steps']]
    assert [s['verified_sources'] for s in now['steps']]==[s['verified_sources'] for s in old['steps']]
    record('adoptions',key=key,proof_version=3,plan_id=now['id'],original_verify_evidence_retained=True)
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


def assert_exact_projection(t,v,selected_changed):
    proof=v['fact_provenance'];assert proof['scope']==SCOPE and proof['version']==1
    assert proof['selected_changed'] is selected_changed and proof['authenticity']=='USER_ASSERTED_UNVERIFIED'
    assert proof['sha256']==literal_sha({k:x for k,x in proof.items() if k!='sha256'})
    history=fact_read(t['f'],t['p']).json()['history']
    for side in ('before','current'):
        node=proof[side];event=next(e for e in history if e['id']==node['decision_ref'])
        choice=next(c for c in event['choices'] if c['field']=='employees')
        row=next(r for r in event['source_snapshot']['sources'] if r['id']==choice['assertion_id'])
        assert node['assertion_ref']==choice['assertion_id'] and node['assertion_revision']==choice['expected_assertion_revision']
        assert node['assertion_fingerprint']==choice['expected_assertion_fingerprint']==row['fingerprint']
        assert node['assertion_sha256']==literal_sha(row) and node['source_ref_sha256']==literal_sha(row['source_ref'])
        assert node['decision_sha256']==event['decision_sha256'] and node['source_sha256']==event['source_sha256']
        assert node['valid_from']==row['valid_from'] and node['valid_until']==row['valid_until']
        assert node['source_kind']=='USER_ASSERTED_SYNTHETIC' and node['authenticity']=='USER_ASSERTED_UNVERIFIED'
        assert not {'value','unit','source_excerpt','source_ref'} & set(node)
        assert node['sha256']==literal_sha({k:x for k,x in node.items() if k!='sha256'})
    record('exact-provenance',selected_changed=selected_changed,actual_registered_before_ref=proof['before']['decision_ref'],actual_current_ref=proof['current']['decision_ref'],original_row_hashes_dates_match=True,no_raw_values_in_projection=True)


def test_exact_historical_selection_read_without_card_is_pure(facts_case):
    t=facts_case;before=full(t);v=view(t)
    assert not v['can_adopt'] and v.get('adoption') is None
    assert full(t)==before and opp_read(t['f'],t['p']).json()['cards']==[]
    c=card(t);before=full(t);v=view(t,c);partition(t,v,'FP01');assert full(t)==before
    assert_exact_projection(t,v,False)
    text=json.dumps(v);assert 'PRIVATE_REGION_SELECTED' not in text and 'PRIVATE_FACT_EXCERPT_' not in text


@pytest.mark.parametrize('kind,answer',[('employees','FP02'),('same_value','FP03'),('unselected','FP08'),('region','FP09')])
def test_actual_fact_confirmation_then_explicit_original_adopt_verify(facts_case,kind,answer):
    t=facts_case;c=change_fact(t,kind);v=view(t,c);partition(t,v,answer)
    assert_exact_projection(t,v,kind in ('employees','same_value'))
    accepted(t,c);repair_material(t)


def test_resource_change_preserves_original_p1_lock_and_verify_evidence(facts_case):
    t=facts_case;assert lock(t['f'],t['p'],'P1').status_code==200;old=deepcopy(stored(t['f'],t['p']))
    add_resource(t['f']);c=card(t);partition(t,view(t,c),'FP10');accepted(t,c);repair_tail(t,('P2','P3','P4','P5'));final(t)
    assert stored(t['f'],t['p'])['steps'][0]==old['steps'][0]


def test_receipt_change_preserves_three_original_locks(facts_case):
    t=facts_case;f,p=t['f'],t['p']
    for a in ('P1','P2','P3'):assert lock(f,p,a).status_code==200
    old=deepcopy(stored(f,p));id=t['completed']['A']['dispatch']['receipt_step_id']
    q=f[3].get('/api/executor-receipts/'+id,headers=headers(f[2])).json();r=receipt_act(f,q,'REOPEN');assert r.status_code==200,r.text
    chain.report_and_ack(t['u'],p,dict(receipt_step_id=id));c=card(t);partition(t,view(t,c),'FP12')
    accepted(t,c);repair_tail(t,('P4','P5'));final(t);assert stored(f,p)['steps'][:3]==old['steps'][:3]


@pytest.mark.parametrize('damage',['missing_receipt','wrong_receipt_payload','missing_historical_event'])
def test_missing_or_wrong_original_confirmation_history_stays_unknown(facts_case,damage):
    t=facts_case;f,p=t['f'],t['p'];c=change_fact(t);before_plan=deepcopy(stored(f,p))
    old_ref=before_plan['steps'][0]['verified_sources']['fact_clarification']['decision_ref']
    with f[1].connect() as db:
        if damage=='missing_receipt':db.execute("DELETE FROM preparation_events WHERE preparation_id=%s AND payload->>'decision_ref'=%s",(p['preparation_id'],old_ref))
        elif damage=='wrong_receipt_payload':db.execute("UPDATE preparation_events SET payload=jsonb_set(payload,'{decision_sha256}',to_jsonb(%s::text)) WHERE preparation_id=%s AND payload->>'decision_ref'=%s",('f'*64,p['preparation_id'],old_ref))
        else:
            row=db.execute('SELECT fact_clarifications FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['fact_clarifications']
            row['events']=[e for e in row['events'] if e['id']!=old_ref]
            db.execute('UPDATE preparations SET fact_clarifications=%s WHERE id=%s',(Jsonb(row),p['preparation_id']))
    before=full(t);v=view(t,c);partition(t,v,'FP14');assert not v['can_adopt'] and v['adoption'] is None
    assert full(t)==before and stored(f,p)==before_plan


def test_cross_tenant_owner_and_role_never_receive_private_provenance(facts_case):
    t=facts_case;c=change_fact(t);v=view(t,c)
    for actor in ('fixture-b','fixture-c','prep-specialist-fixture-a','executor-a'):
        before=full(t);r=impact(t,c,actor);assert r.status_code==403 and 'fact_provenance' not in r.text
        r=send(t,v['adoption'],user=actor);assert r.status_code==403 and full(t)==before


def test_same_key_changed_scope_parameters_and_cold_original_get(facts_case):
    t=facts_case;c=change_fact(t);b,key,r=accepted(t,c);before=full(t)
    q=recover(t['f'],t['p'],key);assert q.status_code==200 and q.json()['status']=='COMMITTED'
    assert full(t)==before
    assert send(t,b,key).status_code==201 and full(t)==before
    for changed in ({**b,'reason':'different original parameters'},{k:v for k,v in b.items() if k!='fact_provenance_scope'}):
        assert send(t,changed,key).status_code==409 and full(t)==before
    repair_material(t)


def test_affected_lock_requires_original_explicit_unlock(facts_case):
    t=facts_case;assert lock(t['f'],t['p'],'P1').status_code==200;c=change_fact(t);v=view(t,c)
    partition(t,v,'FP33');assert not v['can_adopt'] and any('LOCK' in s for s in v['blocking_reasons'])
    r=plan_command(t['f'],t['p'],'P1','UNLOCK');assert r.status_code==200,r.text
    accepted(t,c);repair_material(t)


def test_scope_cannot_bypass_original_local_revision_and_opportunity(facts_case):
    t=facts_case;c=change_fact(t);v=view(t,c);b=v['adoption']
    for changed in ({**b,'local_revision':False},{**b,'opportunity_proof':None},{**b,'fact_provenance_scope':'OTHER_FIELD_V1'}):
        before=full(t);r=send(t,changed);assert r.status_code in (409,422) and full(t)==before


def test_revoke_then_restore_does_not_revive_old_preview(facts_case):
    t=facts_case;c=change_fact(t);b=view(t,c)['adoption'];f=t['f']
    f[1].revoke_field('fixture-a','employees','WRITE')
    before=full(t);r=send(t,b);assert r.status_code in (403,409) and full(t)==before
    with f[1].connect() as db:db.execute("UPDATE field_grants SET active=true,revision=revision+1 WHERE principal_id='fixture-a' AND field_name='employees' AND capability='WRITE'")
    before=full(t);assert send(t,b).status_code==409 and full(t)==before


def test_source_row_aba_between_preview_and_original_adopt_refuses(facts_case):
    t=facts_case;c=change_fact(t);b=view(t,c)['adoption'];f=t['f'];id=t['selected']['employees']
    with f[1].connect() as db:
        original=db.execute('SELECT value FROM fact_assertions WHERE id=%s',(id,)).fetchone()['value']
        db.execute('UPDATE fact_assertions SET value=%s WHERE id=%s',(Jsonb(987),id))
    with f[1].connect() as db:db.execute('UPDATE fact_assertions SET value=%s WHERE id=%s',(Jsonb(original),id))
    before=full(t);assert send(t,b).status_code==409 and full(t)==before


def html_controls(t,mode,state):
    f,u,p=t['f'],t['u'],t['p']
    def before_adopt():state['before']=deepcopy(stored(f,p))
    def after_adopt():
        now=stored(f,p);old=state['before'];change=now['events'][-1]['local_revision']['source_change']
        assert change['version']==3 and change['fact_provenance']['scope']==SCOPE
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
        with f[1].connect() as db:db.execute("UPDATE field_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND field_name='employees' AND capability='READ'")
        state['denied_snapshot']=full(t)
    def restore():
        assert full(t)==state['denied_snapshot']
        with f[1].connect() as db:db.execute("UPDATE field_grants SET active=true,revision=revision+1 WHERE principal_id='fixture-a' AND field_name='employees' AND capability='READ'")
    def denied():assert full(t)==state['denied_snapshot']
    return dict(change_fact=lambda:change_fact(t,refresh=False),before_adopt=before_adopt,after_adopt=after_adopt,
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
    script=Path(__file__).with_name('employees_fact_provenance_real_html.js')
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
        assert result and result['scope']=='FULL_ORIGINAL_HTML_EMPLOYEES_PROVENANCE_ACTUAL_HTTP_ASGI_OWNED_PG'
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
def test_full_original_html_explicit_employees_adoption_and_authority(facts_case,mode):run_html(facts_case,mode)


def test_enhanced_history_then_default_adopt_is_nonsticky_and_cold_readable(facts_case):
    from test_source_change_adoption import preview as original_preview
    t=facts_case;c=change_fact(t);accepted(t,c);repair_material(t)
    first=deepcopy(stored(t['f'],t['p']))
    c=change_fact(t,value=31);v=original_preview(t['f'],t['p'],c).json()
    assert v['scope']=='SOURCE_CHANGE_LOCAL_REVISION_PREVIEW' and v['can_adopt']
    assert 'fact_provenance_scope' not in v['adoption']
    key=uuid4().hex;r=send(t,v['adoption'],key);assert r.status_code==201,r.text
    now=stored(t['f'],t['p']);change=now['events'][-1]['local_revision']['source_change']
    assert change['version']==2 and 'fact_provenance' not in change
    assert now['events'][:len(first['events'])]==first['events']
    before=full(t);r=recover(t['f'],t['p'],key);assert r.status_code==200 and r.json()['status']=='COMMITTED';assert full(t)==before
    repair_material(t)
    record('compatibility',enhanced_v3_then_legacy_v2=True,scope_not_sticky=True,original_cold_get=True)


@pytest.mark.parametrize('mode',['MANUAL','MATERIAL_PACKAGE'])
def test_existing_manual_or_package_combination_refuses_only_new_scope(facts_case,mode):
    from test_source_change_adoption import preview as original_preview
    t=facts_case;f,p=t['f'],t['p'];base='/api/preparations/'+p['preparation_id']
    v=f[3].get(base+'/plan-source-conflicts',headers=headers(f[2])).json()
    b=dict(schema=1,action='EDIT_NOTE',expected_plan_id=v['plan_id'],expected_plan_revision=v['plan_revision'],
        expected_note_revision=v['note']['revision'] if v['note'] else 0,expected_ledger_revision=v['opportunity_revision'],
        expected_preview_sha256=v['preview_sha256'],card_id=v['card_id'],text='SYNTHETIC original owner MANUAL note kept intact',reason='SYNTHETIC explicit original manual edit')
    r=f[3].post(base+'/plan-source-conflicts/commands',headers=headers(f[2],key=uuid4().hex),json=b);assert r.status_code==200,r.text
    c=card(t)
    if mode=='MATERIAL_PACKAGE':
        v=f[3].get(base+'/plan-material-package',headers=headers(f[2]),params={'card_id':c['id']}).json()
        b=dict(schema=2,action='KEEP_AND_CONTINUE',expected_plan_id=v['plan_id'],expected_plan_revision=v['plan_revision'],
            expected_note_revision=v['note']['revision'],expected_ledger_revision=v['opportunity_revision'],
            expected_preview_sha256=v['preview_sha256'],card_id=c['id'],text=None,reason='SYNTHETIC explicit original package enrollment',confirm_package=True)
        r=f[3].post(base+'/plan-material-package/commands',headers=headers(f[2],key=uuid4().hex),json=b);assert r.status_code==200,r.text
        assert r.json()['current']['package_confirmation']['active'] is True
    c=change_fact(t);before=full(t);v=view(t,c)
    assert not v['can_adopt'] and v['fact_provenance'] is None and v['unknown_scope']=='THIS_CASE' and v['preserved']==[]
    assert v['adoption'] is None and 'FACT_PROVENANCE_COMBINATION_UNSUPPORTED' in v['blocking_reasons']
    r=original_preview(f,p,c);assert r.status_code==200 and r.json()['scope']=='SOURCE_CHANGE_LOCAL_REVISION_PREVIEW'
    assert 'fact_provenance_scope' not in r.json()['adoption']
    assert full(t)==before
    record('compatibility',unsupported_combination=mode,enhanced_rejected=True,legacy_preview_unchanged=True)
