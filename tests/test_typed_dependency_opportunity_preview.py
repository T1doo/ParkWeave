"""Read-only original opportunity wiring: actual HTTP/ASGI and owned synthetic PG."""
from copy import deepcopy
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
from uuid import uuid4

import pytest
from psycopg import sql
from parkweave.api import create_app
from parkweave.store import Store
from test_registered_local_revision import http_f,link_fixture,receipt_fixture,preparation_fixture
from test_source_change_adoption import changed
from test_case_goal_results import complete
from test_case_opportunities import imported
from test_service_case_steps import setup,GOALS,adopt,step,read,command
from test_service_plan_manual_lock import lock,stored
from test_preparation import headers
from test_new_enterprise_local_chain import actual_http

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('PARKWEAVE_TYPED_PREVIEW_EVIDENCE',ROOT/'.runtime/typed-dependency-opportunity-preview-20261018/development'))
SCOPE={'dependency_scope':'BOUNDED_MULTI_SOURCE_V1','graph_preview':'VERSIONED_TYPED_GRAPH_V1'}


def endpoint(p,card):return '/api/preparations/'+p['preparation_id']+'/opportunities/'+card['id']+'/plan-revision'
def get(f,p,card,user='fixture-a',params=None):
    return f[3].get(endpoint(p,card),params=SCOPE if params is None else params,headers=headers(f[2],user))


def database_state(f):
    """All public business/authority rows; denied-read authorization audit is separate."""
    with f[1].connect() as c:
        tables=[r['tablename'] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'authorization_audit' ORDER BY tablename")]
        return {name:[r['row'] for r in c.execute(sql.SQL('SELECT to_jsonb(t)::text AS row FROM {} t ORDER BY to_jsonb(t)::text').format(sql.Identifier(name)))] for name in tables}


def test_actual_readonly_projection_locks_cold_store_and_old_adopt(http_f):
    f=http_f;p,*_=complete(f,local=True)
    for adapter in ('P1','P3'):assert lock(f,p,adapter).status_code==200
    card=changed(f,p);plan=stored(f,p);before=database_state(f)
    legacy=get(f,p,card,params={'dependency_scope':SCOPE['dependency_scope']});assert legacy.status_code==200,legacy.text
    r=get(f,p,card);assert r.status_code==200,r.text;v=r.json();x=v.pop('typed_dependency_preview');assert v==legacy.json()
    assert get(f,p,card,params={'dependency_scope':SCOPE['dependency_scope']}).json()==legacy.json()
    assert database_state(f)==before
    ids={s['adapter_id']:s['id'] for s in plan['steps']};i=x['impact']
    assert set(i['affected'])&set(ids.values())=={ids[a] for a in ('P2','P3','P4','P5')}
    assert set(i['preserved'])&set(ids.values())=={ids['P1']} and not i['uncertain'] and not i['removed']
    assert {l['node_id'] for l in x['current_manual_locks']}=={ids['P1'],ids['P3']}
    assert {l['node_id'] for l in x['lock_conflicts']}=={ids['P3']}
    assert not i['lock_conflicts'] and all(not n['locked_fields'] for g in (x['before'],x['current']) for n in g['nodes'])
    assert all(x[k] is False for k in ('can_adopt','execution_authorized','authority_verified','new_grants','automatic_execution','history_rewritten','automatically_replayed','case_goal_completed'))
    assert x['before']['legacy_sha256']==x['current']['legacy_sha256']==x['legacy_graph_sha256']==v['dependency_propagation']['sha256']
    assert x['binding']['legacy_preview_sha256']==v['preview_sha256'] and x['binding']['plan_revision']==plan['revision']
    with actual_http(create_app(Store(f[0].dsn))) as (client,trace):
        q=client.get(endpoint(p,card),params=SCOPE,headers=headers(f[2]));assert q.status_code==200,q.text
        assert q.json()==r.json() and all(t['method']=='GET' for t in trace)
    assert database_state(f)==before
    assert command(f,p,'P3','UNLOCK').status_code==200
    old=get(f,p,card,params={'dependency_scope':SCOPE['dependency_scope']}).json()
    fresh=get(f,p,card).json();assert {k:z for k,z in fresh.items() if k!='typed_dependency_preview'}==old
    old_plan=stored(f,p);assert adopt(f,p,old['adoption']).status_code==201
    now=stored(f,p);assert now['steps'][0]==old_plan['steps'][0] and now['events'][:-1]==old_plan['events']
    assert now['events'][-1]['local_revision']['source_change']['version']==4
    assert 'typed_dependency_preview' not in json.dumps(now)


@pytest.mark.parametrize('which',['READ','PREPARE','ROLE','CROSS_CASE'])
def test_current_authority_still_required_and_denial_has_no_business_write(http_f,which):
    f=http_f;p,*_=complete(f);card=changed(f,p)
    with f[1].connect() as c:
        if which=='READ':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
        elif which=='PREPARE':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
        elif which=='ROLE':c.execute("UPDATE principals SET role='resource_admin' WHERE id='fixture-a'")
    before=database_state(f);assert get(f,p,card,'fixture-b' if which=='CROSS_CASE' else 'fixture-a').status_code==403
    assert database_state(f)==before


def test_unknown_base_and_exact_query_and_adapter_failure(http_f,monkeypatch):
    f=http_f;p=setup(f,GOALS[0]);assert adopt(f,p).status_code==201
    _,v,_=imported(f,p);card=v['cards'][0];before=database_state(f)
    r=get(f,p,card);assert r.status_code==200,r.text;x=r.json()['typed_dependency_preview'];ids={s['id'] for s in stored(f,p)['steps']}
    assert ids<=set(x['impact']['uncertain']) and x['impact']['unknown_ranges'] and not x['can_adopt']
    for params,status in [({'graph_preview':SCOPE['graph_preview']},409),({**SCOPE,'other':'x'},409),([*SCOPE.items(),('graph_preview',SCOPE['graph_preview'])],409),({**SCOPE,'graph_preview':'other'},422)]:
        assert get(f,p,card,params=params).status_code==status
    from parkweave import dependency_graph as dg
    def unavailable(*args,**kwargs):raise dg.GraphError('SYNTHETIC bounded rejection')
    monkeypatch.setattr(dg,'from_unified_v1',unavailable)
    r=get(f,p,card);assert r.status_code==409 and r.json()['detail']=='versioned dependency preview unavailable'
    assert database_state(f)==before


def run_html(f,p,card,mode):
    OUT.mkdir(parents=True,exist_ok=True);calls=[];lines=[];err='';result=None
    config=dict(base=str(f[3].base_url).rstrip('/'),token=f[2]['fixture-a'],mode=mode,A=p,card=card['id'])
    process=subprocess.Popen(['node',str(Path(__file__).with_name('typed_dependency_opportunity_real_html.js'))],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    incoming=queue.Queue()
    def consume():
        for line in process.stdout:incoming.put(line)
        incoming.put(None)
    reader=threading.Thread(target=consume,daemon=True);reader.start();attempt=mode+'-'+uuid4().hex[:8];before={}
    try:
        process.stdin.write(json.dumps(config)+'\n');process.stdin.flush()
        while True:
            try:line=incoming.get(timeout=45)
            except queue.Empty:raise AssertionError('original HTML made no progress for45 seconds')
            if line is None:break
            lines.append(line);msg=json.loads(line)
            if 'trace' in msg:calls.append(msg['trace']);continue
            if 'control' in msg:
                action=msg['control']
                if action=='snapshot':before['state']=database_state(f)
                elif action=='assert_readonly':assert database_state(f)==before['state']
                elif action=='revoke':
                    with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
                    before['denied']=database_state(f)
                elif action=='assert_denied_read_no_write':assert database_state(f)==before['denied']
                elif action=='restore':
                    with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=true WHERE principal_id='fixture-a' AND capability='READ'")
                else:raise AssertionError(action)
                process.stdin.write('{}\n');process.stdin.flush()
            else:result=msg;break
        code=process.wait(timeout=10);err=process.stderr.read();assert code==0,err
        assert result and result['scope']=='FULL_ORIGINAL_HTML_VERSIONED_GRAPH_ACTUAL_HTTP_ASGI_OWNED_PG'
        assert result['real_browser']=='NOT_RUN' and result['calls'] and all(c['method']=='GET' for c in result['calls'])
        assert result['preview_checks']>0
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=5)
        reader.join(timeout=5)
        while not incoming.empty():
            line=incoming.get_nowait()
            if line is not None:lines.append(line)
        (OUT/(attempt+'.stdout.jsonl')).write_text(''.join(lines));(OUT/(attempt+'.stderr.log')).write_text(err+process.stderr.read())


@pytest.mark.parametrize('mode',['positive','current_403','late_200','late_403','late_json','late_transport','hash_aba'])
def test_full_original_html_readonly_button_and_context_guards(http_f,mode):
    f=http_f;p,*_=complete(f,local=True);assert lock(f,p,'P1').status_code==200;assert lock(f,p,'P3').status_code==200
    run_html(f,p,changed(f,p),mode)
