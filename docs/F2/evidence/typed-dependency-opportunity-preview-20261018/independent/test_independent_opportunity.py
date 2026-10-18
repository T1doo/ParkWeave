"""Frozen literal HTTP/UI integration oracles, separate from graph algorithms."""
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import queue
import subprocess
import threading

import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.types.json import Jsonb
from parkweave.api import create_app
from parkweave.store import Store
from test_registered_local_revision import http_f,link_fixture,receipt_fixture,preparation_fixture
from test_source_change_adoption import changed
from test_case_goal_results import complete
from test_case_opportunities import imported
from test_service_case_steps import setup,GOALS,adopt,verified
from test_service_plan_manual_lock import lock,stored
from test_preparation import headers

BASE=Path(__file__).resolve().parent
PARAMS=dict(dependency_scope='BOUNDED_MULTI_SOURCE_V1',graph_preview='VERSIONED_TYPED_GRAPH_V1')


def digest(value):
    return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def path(p,card):
    return '/api/preparations/'+p['preparation_id']+'/opportunities/'+card['id']+'/plan-revision'


def get(f,p,card,actor='fixture-a',params=PARAMS):
    return f[3].get(path(p,card),headers=headers(f[2],actor),params=params)


def state(f):
    # Authorization audit is intentionally separate from business/authority rows.
    with f[1].connect() as c:
        tables=[r['tablename'] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'authorization_audit' ORDER BY tablename")]
        return {t:[r['row'] for r in c.execute(sql.SQL('SELECT to_jsonb(t)::text AS row FROM {} t ORDER BY to_jsonb(t)::text').format(sql.Identifier(t)))] for t in tables}


def test_independent_api_literal_locks_legacy_identity_cold_and_source_aba(http_f):
    f=http_f;p,*_=complete(f,local=True)
    for name in ('P1','P3'):assert lock(f,p,name).status_code==200
    card=changed(f,p);original=deepcopy(stored(f,p));ids={s['adapter_id']:s['id'] for s in original['steps']}
    ordinary=get(f,p,card,params={});unified=get(f,p,card,params={'dependency_scope':'BOUNDED_MULTI_SOURCE_V1'})
    assert ordinary.status_code==unified.status_code==200
    before=state(f);response=get(f,p,card);assert response.status_code==200,response.text
    value=response.json();x=value['typed_dependency_preview'];impact=x['impact']
    assert {k:v for k,v in value.items() if k!='typed_dependency_preview'}==unified.json()
    assert get(f,p,card,params={}).json()==ordinary.json()
    assert get(f,p,card,params={'dependency_scope':'BOUNDED_MULTI_SOURCE_V1'}).json()==unified.json()
    assert set(impact['affected'])&set(ids.values())=={ids[k] for k in ('P2','P3','P4','P5')}
    assert set(impact['preserved'])&set(ids.values())=={ids['P1']}
    assert impact['uncertain']==[] and impact['removed']==[]
    assert {row['node_id'] for row in x['current_manual_locks']}=={ids['P1'],ids['P3']}
    assert [row['node_id'] for row in x['lock_conflicts']]==[ids['P3']]
    for record in [x,x['before'],x['current'],impact]:
        assert record['sha256']==digest({k:v for k,v in record.items() if k!='sha256'})
    for snapshot in (x['before'],x['current']):
        assert all(n['locked_fields']==[] for n in snapshot['nodes'])
        assert snapshot['legacy_sha256']==x['legacy_graph_sha256']==value['dependency_propagation']['sha256']
    assert impact['lock_conflicts']==[] and x['read_only'] is True
    assert all(x[k] is False for k in ['can_adopt','execution_authorized','authority_verified','automatic_execution','new_grants','history_rewritten'])
    assert all(not o['changed'] for o in value['dependency_propagation']['observations'] if o['step_id']==ids['P1'])
    with TestClient(create_app(Store(f[0].dsn))) as client:
        cold=client.get(path(p,card),headers=headers(f[2]),params=PARAMS)
        assert cold.status_code==200 and cold.json()==response.json()
    assert state(f)==before and stored(f,p)==original
    # External temporary-fixture row rewrite A→B→A changes epoch, even after
    # business row values return to A. GET itself still writes nothing.
    with f[1].connect() as c:
        resource=c.execute('SELECT id,capacity FROM synthetic_resources ORDER BY id LIMIT 1').fetchone()
    with f[1].connect() as c:c.execute('UPDATE synthetic_resources SET capacity=capacity+1 WHERE id=%s',(resource['id'],))
    with f[1].connect() as c:c.execute('UPDATE synthetic_resources SET capacity=%s WHERE id=%s',(resource['capacity'],resource['id']))
    after_change=state(f);fresh=get(f,p,card);assert fresh.status_code==200,fresh.text
    y=fresh.json()['typed_dependency_preview']
    assert y['binding']['source_epochs_sha256']!=x['binding']['source_epochs_sha256']
    assert y['binding']['legacy_preview_sha256']!=x['binding']['legacy_preview_sha256']
    assert y['impact']['affected']==impact['affected'] and y['impact']['preserved']==impact['preserved']
    assert state(f)==after_change and stored(f,p)==original
    (BASE/'api-literal-evidence.json').write_text(json.dumps(dict(affected_adapters=['P2','P3','P4','P5'],preserved_adapters=['P1'],current_conflicted_locks=['P3'],preserved_locks=['P1'],all_public_tables_checked=len(before),legacy_ordinary_and_unified_unchanged=True,cold_api_equal=True,source_epoch_ABA_observed=True,read_get_no_writes=True),sort_keys=True,indent=2)+'\n')


def test_independent_denied_roles_unknown_query_and_corrupt_lock_are_closed(http_f):
    f=http_f;p=setup(f,GOALS[0]);assert adopt(f,p).status_code==201
    _,opportunity,_=imported(f,p);card=opportunity['cards'][0]
    before=state(f);r=get(f,p,card);assert r.status_code==200,r.text
    x=r.json()['typed_dependency_preview'];ids={s['id'] for s in stored(f,p)['steps']}
    assert ids<=set(x['impact']['uncertain']) and not x['can_adopt']
    for actor in ['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a']:
        denied=get(f,p,card,actor);assert denied.status_code==403
        assert 'typed_dependency_preview' not in denied.text and state(f)==before
    for query,expected in [({'graph_preview':'VERSIONED_TYPED_GRAPH_V1'},409),
        ({**PARAMS,'ignored':'x'},409),({**PARAMS,'dependency_scope':'unsupported'},422),
        ([*PARAMS.items(),('graph_preview','VERSIONED_TYPED_GRAPH_V1')],409)]:
        assert get(f,p,card,params=query).status_code==expected and state(f)==before
    for table,capability in [('capability_grants','READ'),('preparation_grants','PREPARE')]:
        with f[1].connect() as c:c.execute(sql.SQL("UPDATE {} SET active=false WHERE principal_id='fixture-a' AND capability=%s").format(sql.Identifier(table)),(capability,))
        denied_state=state(f);assert get(f,p,card).status_code==403 and state(f)==denied_state
        with f[1].connect() as c:c.execute(sql.SQL("UPDATE {} SET active=true WHERE principal_id='fixture-a' AND capability=%s").format(sql.Identifier(table)),(capability,))
    verified(f,p,'P1');assert lock(f,p,'P1').status_code==200
    plan=stored(f,p);plan['steps'][0]['manual_lock']['source_sha256']='0'*64
    with f[1].connect() as c:c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),p['preparation_id']))
    corrupted=state(f);r=get(f,p,card);assert r.status_code==409 and 'typed_dependency_preview' not in r.text
    assert state(f)==corrupted


def test_independent_full_page_two_case_late_responses_draft_and_cold_get(http_f):
    f=http_f;a,*_=complete(f,local=True)
    for name in ('P1','P3'):assert lock(f,a,name).status_code==200
    card_a=changed(f,a);b=setup(f,GOALS[0]);assert adopt(f,b).status_code==201
    _,opportunity,_=imported(f,b);card_b=opportunity['cards'][0]
    config=dict(base=str(f[3].base_url).rstrip('/'),token=f[2]['fixture-a'],A=a,B=b,card=card_a['id'],cardB=card_b['id'])
    child=subprocess.Popen(['node',str(BASE/'independent_opportunity_full_html.js')],cwd=Path.cwd(),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    incoming=queue.Queue();lines=[];result=None;snapshots={}
    def consume():
        for line in child.stdout:incoming.put(line)
        incoming.put(None)
    reader=threading.Thread(target=consume,daemon=True);reader.start()
    try:
        child.stdin.write(json.dumps(config)+'\n');child.stdin.flush()
        while True:
            line=incoming.get(timeout=45)
            if line is None:break
            lines.append(line);message=json.loads(line)
            if 'trace' in message:continue
            if 'control' in message:
                action=message['control']
                if action=='snapshot':snapshots['before']=state(f)
                elif action=='assert_readonly':assert state(f)==snapshots['before']
                elif action=='revoke':
                    with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
                    snapshots['denied']=state(f)
                elif action=='assert_denied_read_no_write':assert state(f)==snapshots['denied']
                elif action=='restore':
                    with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=true WHERE principal_id='fixture-a' AND capability='READ'")
                else:raise AssertionError(action)
                child.stdin.write('{}\n');child.stdin.flush()
            else:result=message;break
        assert child.wait(timeout=10)==0
        assert result and result['scope']=='INDEPENDENT_FULL_HTML_TYPED_GRAPH_TWO_CASE_ACTUAL_ASGI_PG'
        assert result['real_browser']=='NOT_RUN' and result['probes']==dict(cases=7,rejected=7)
        assert all(c['method']=='GET' for c in result['calls'])
    finally:
        if child.poll() is None:child.terminate();child.wait(timeout=5)
        reader.join(timeout=5)
        while not incoming.empty():
            line=incoming.get_nowait()
            if line is not None:lines.append(line)
        (BASE/'full-html.stdout.jsonl').write_text(''.join(lines))
        (BASE/'full-html.stderr.log').write_text(child.stderr.read())
