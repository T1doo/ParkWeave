"""Scoped raw resource graph via original HTTP/ASGI and owned synthetic PG."""
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
from uuid import uuid4
import pytest
from parkweave.api import create_app
from parkweave.store import Store
from parkweave import resource_query_graph as rg,resource_combinations as combinations
from test_registered_local_revision import http_f,link_fixture,receipt_fixture,preparation_fixture,add_resource
from test_case_goal_results import complete
from test_case_opportunities import imported,post,body,get as opportunity_read
from test_service_plan_manual_lock import stored,lock
from test_service_case_steps import command,adopt,setup,GOALS
from test_preparation import headers
from test_new_enterprise_local_chain import actual_http
from test_typed_dependency_opportunity_preview import database_state

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('PARKWEAVE_RESOURCE_GRAPH_EVIDENCE',ROOT/'.runtime/resource-query-members-20261018/development'))
PARAMS={'dependency_scope':'BOUNDED_MULTI_SOURCE_V1','graph_preview':'RESOURCE_QUERY_MEMBERS_V1'}


def endpoint(p,card):return '/api/preparations/'+p['preparation_id']+'/opportunities/'+card['id']+'/plan-revision'
def get(f,p,card,params=None,user='fixture-a'):
    return f[3].get(endpoint(p,card),params=PARAMS if params is None else params,headers=headers(f[2],user))
def refresh(f,p):
    r=post(f,p,body(opportunity_read(f,p).json(),'REFRESH'));assert r.status_code==200,r.text
    return r.json()['current']['cards'][0]
def imported_card(f,p):return imported(f,p)[1]['cards'][0]
def record(name,value):
    OUT.mkdir(parents=True,exist_ok=True);(OUT/(name+'-'+uuid4().hex[:8]+'.json')).write_text(json.dumps(value,indent=2)+'\n')


def test_actual_member_insert_cold_get_old_hash_and_adopt_keep_history(http_f):
    f=http_f;p,*_=complete(f,local=True)
    for adapter in ('P1','P3'):assert lock(f,p,adapter).status_code==200
    imported_card(f,p);new_id=str(add_resource(f));card=refresh(f,p);before=database_state(f);old=stored(f,p)
    r=get(f,p,card);assert r.status_code==200,r.text;v=r.json();x=v['resource_dependency_preview'];ids={s['adapter_id']:s['id'] for s in old['steps']}
    assert x['membership']['state']=='KNOWN' and x['membership']['added']==[new_id] and not x['membership']['removed']
    assert x['before_basis']['observed_row_count']==4 and x['before_basis']['complete']
    assert x['current_basis']['observed_row_count']==6 and x['current_basis']['complete']
    assert 'resource:'+new_id not in {n['id'] for n in x['before']['nodes']}
    assert 'resource:'+new_id in {n['id'] for n in x['current']['nodes']}
    assert set(x['impact']['affected'])&set(ids.values())=={ids[a] for a in ('P2','P3','P4','P5')}
    assert ids['P1'] in x['impact']['preserved'] and not x['impact']['uncertain']
    assert {l['node_id'] for l in x['lock_conflicts']}=={ids['P3']}
    legacy=get(f,p,card,params={**PARAMS,'graph_preview':'VERSIONED_TYPED_GRAPH_V1'});assert legacy.status_code==200,legacy.text
    assert {k:z for k,z in v.items() if k!='resource_dependency_preview'}==legacy.json()
    with actual_http(create_app(Store(f[0].dsn))) as (client,trace):
        q=client.get(endpoint(p,card),params=PARAMS,headers=headers(f[2]));assert q.status_code==200,q.text
        assert q.json()==v and all(t['method']=='GET' for t in trace)
    assert database_state(f)==before
    assert command(f,p,'P3','UNLOCK').status_code==200
    old_v4=get(f,p,card,params={'dependency_scope':PARAMS['dependency_scope']}).json();history=stored(f,p)
    assert adopt(f,p,old_v4['adoption']).status_code==201
    now=stored(f,p);assert now['events'][:-1]==history['events'] and now['steps'][0]==history['steps'][0]
    assert now['events'][-1]['local_revision']['source_change']['version']==4
    assert 'resource_dependency_preview' not in json.dumps(now)
    record('insert-cold-original-v4',dict(preparation_id=p['preparation_id'],query_node_id=x['query_node_id'],
        membership=x['membership'],before_basis=x['before_basis'],current_basis=x['current_basis'],
        current_graph_sha256=x['current']['sha256'],impact=x['impact'],cold_get_only=True,old_v4_preserved=True))


def test_partial_history_and_current_read_gate_never_fill_missing_members(http_f):
    f=http_f;unselected=str(add_resource(f));p,*_=complete(f,local=True);card=imported_card(f,p)
    before=database_state(f);r=get(f,p,card);assert r.status_code==200,r.text;x=r.json()['resource_dependency_preview']
    assert x['membership']['state']=='UNKNOWN' and not x['before_basis']['complete'] and x['current_basis']['complete']
    assert x['membership']['newly_observed']==[unselected] and not x['membership']['added']
    assert 'resource:'+unselected not in {n['id'] for n in x['before']['nodes']}
    assert x['impact']['uncertain'] and database_state(f)==before
    with f[1].connect() as c:c.execute("UPDATE synthetic_resource_grants SET active=false WHERE resource_id=%s AND principal_id='fixture-a' AND capability='READ'",(unselected,))
    before=database_state(f);r=get(f,p,card);assert r.status_code==200,r.text;masked=r.json()['resource_dependency_preview']
    assert masked['membership']['state']=='UNKNOWN' and not masked['current_basis']['complete']
    assert unselected not in json.dumps(masked) and database_state(f)==before
    assert get(f,p,card,user='fixture-b').status_code==403 and database_state(f)==before
    record('partial-and-current-read',dict(before_basis=x['before_basis'],current_basis=masked['current_basis'],
        current_member_ids=[n['id'] for n in masked['current']['nodes'] if n['type']=='RESOURCE'],unknown=True,unreadable_id_absent=True))


def test_actual_query_removal_and_epoch_race_are_not_physical_delete_or_silent_retry(http_f,monkeypatch):
    f=http_f;p,*_=complete(f,local=True);card=imported_card(f,p)
    old=stored(f,p);removed=str(combinations.SECOND_RESOURCE_ID)
    assert removed in {r['id'] for r in old['steps'][1]['verified_sources']['resource_rules']}
    with f[1].connect() as c:c.execute("DELETE FROM synthetic_resource_grants WHERE resource_id=%s AND principal_id='fixture-a'",(removed,))
    card=refresh(f,p);before=database_state(f);r=get(f,p,card);assert r.status_code==200,r.text;x=r.json()['resource_dependency_preview']
    assert x['membership']['state']=='KNOWN' and x['membership']['removed']==[removed]
    assert x['membership']['semantics']=='QUERY_MEMBERSHIP_ONLY' and database_state(f)==before
    with f[1].connect() as c:assert c.execute('SELECT id FROM synthetic_resources WHERE id=%s',(removed,)).fetchone()
    original=rg.read_rows;state={}
    def changing(c,parent):
        rows=original(c,parent);inserted=add_resource(f)
        with f[1].connect() as owner:assert owner.execute("SELECT 1 FROM synthetic_resource_grants WHERE resource_id=%s AND principal_id='fixture-a' AND capability='READ' AND active",(inserted,)).fetchone()
        state['after_injected_source_change']=database_state(f);return rows
    monkeypatch.setattr(rg,'read_rows',changing)
    r=get(f,p,card);assert r.status_code==409 and r.json()['detail']=='resource source epochs changed during read'
    assert database_state(f)==state['after_injected_source_change']
    record('membership-removal-and-epoch',dict(membership=x['membership'],epoch_rejected=True,automatic_retry=False,original_resource_not_deleted=True))


def test_explicit_resource_scope_requires_original_p2_and_exact_query(http_f,monkeypatch):
    f=http_f;p=setup(f,GOALS[0]);assert adopt(f,p).status_code==201;card=imported_card(f,p);before=database_state(f)
    r=get(f,p,card);assert r.status_code==409 and r.json()['detail']=='original resource consumer required'
    assert get(f,p,card,params={**PARAMS,'other':'x'}).status_code==409
    assert get(f,p,card,params={'graph_preview':PARAMS['graph_preview']}).status_code==409
    old=get(f,p,card,params={**PARAMS,'graph_preview':'VERSIONED_TYPED_GRAPH_V1'});assert old.status_code==200,old.text
    assert database_state(f)==before


def run_html(f,p,card,mode):
    OUT.mkdir(parents=True,exist_ok=True);config=dict(base=str(f[3].base_url).rstrip('/'),token=f[2]['fixture-a'],A=p,card=card['id'],mode=mode)
    process=subprocess.Popen(['node',str(Path(__file__).with_name('resource_query_members_real_html.js'))],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    incoming=queue.Queue();lines=[];err='';result=None;state={};attempt=mode+'-'+uuid4().hex[:8]
    def consume():
        for line in process.stdout:incoming.put(line)
        incoming.put(None)
    reader=threading.Thread(target=consume,daemon=True);reader.start()
    try:
        process.stdin.write(json.dumps(config)+'\n');process.stdin.flush()
        while True:
            try:line=incoming.get(timeout=45)
            except queue.Empty:raise AssertionError('resource member original HTML made no progress for45 seconds')
            if line is None:break
            lines.append(line);msg=json.loads(line)
            if 'trace' in msg:continue
            if 'control' in msg:
                action=msg['control']
                if action=='snapshot':state['baseline']=database_state(f)
                elif action=='assert_readonly':assert database_state(f)==state['baseline']
                elif action=='revoke':
                    with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
                    state['denied']=database_state(f)
                elif action=='assert_denied_read_no_write':assert database_state(f)==state['denied']
                else:raise AssertionError(action)
                process.stdin.write('{}\n');process.stdin.flush()
            else:result=msg;break
        code=process.wait(timeout=10);err=process.stderr.read();assert code==0,err
        assert result and result['scope']=='ORIGINAL_FULL_HTML_RESOURCE_MEMBERS_ACTUAL_HTTP_ASGI_OWNED_PG'
        assert result['real_browser']=='NOT_RUN' and all(c['method']=='GET' for c in result['calls'])
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=5)
        reader.join(timeout=5)
        while not incoming.empty():
            line=incoming.get_nowait()
            if line is not None:lines.append(line)
        (OUT/(attempt+'.stdout.jsonl')).write_text(''.join(lines));(OUT/(attempt+'.stderr.log')).write_text(err+process.stderr.read())


@pytest.mark.parametrize('mode',['members','p1_only'])
def test_original_button_resource_members_or_explicit_p1_legacy_mode(http_f,mode):
    f=http_f
    if mode=='members':
        p,*_=complete(f,local=True);assert lock(f,p,'P1').status_code==200;imported_card(f,p);add_resource(f);card=refresh(f,p)
    else:p=setup(f,GOALS[0]);assert adopt(f,p).status_code==201;card=imported_card(f,p)
    run_html(f,p,card,mode)
