"""Independent literal resource-query oracles; execute from private mirror/tests."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import queue
import subprocess
import threading

import pytest
from psycopg import sql
from parkweave import resource_query_graph as product,resource_combinations
from test_registered_local_revision import http_f,link_fixture,receipt_fixture,preparation_fixture,add_resource
from test_case_goal_results import complete
from test_case_opportunities import imported,post,body,get as opportunity_read
from test_service_case_steps import setup,GOALS,adopt
from test_preparation import headers
from test_service_plan_manual_lock import stored,lock

BASE=Path(__file__).resolve().parents[2]
PARAMS=dict(dependency_scope='BOUNDED_MULTI_SOURCE_V1',graph_preview='RESOURCE_QUERY_MEMBERS_V1')
FIELDS=('id','revision','source','capacity','buffer_seconds','open_from','open_until','enabled')
A='11111111-1111-1111-1111-111111111111';B='22222222-2222-2222-2222-222222222222';C='33333333-3333-3333-3333-333333333333'


def digest(value):return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def rule(id):return dict(id=id,revision=7,source={'kind':'SYNTHETIC','id':'independent-original'},capacity=4,buffer_seconds=2,open_from='2026-01-01T00:00:00+00:00',open_until='2099-01-01T00:00:00+00:00',enabled=True,namespace='SYNTHETIC',authority='LOCAL_AUTHORITY')
def rows(rules):return sorted([{**{k:r[k] for k in FIELDS},'capability':cap,'active':True} for r in rules for cap in ('READ','HOLD')],key=lambda r:(r['id'],r['capability']))
def stamp(values):return dict(known=True,count=len(values),sha256=digest(values))
def source(rules):return dict(resource_rules=deepcopy(rules),resource_grants=[dict(resource_id=r['id'],capability=cap,active=True) for r in rules for cap in ('READ','HOLD')],resource_collection=stamp(rows(rules)))


def test_independent_literal_reconstruction_partial_duplicates_and_confirmed_changes():
    parent=dict(owner_id='owner',park_id='park',org_id='org',case_id='case')
    plan=dict(id='plan',steps=[dict(id='step-'+a,adapter_id=a,depends_on=[] if a=='P1' else ['P'+str(int(a[1])-1)]) for a in ('P1','P2','P3','P4','P5')])
    old=source([rule(A),rule(B)])
    def compare(saved,current):return product.preview(parent,plan,saved,current,stamp(current),{'independent_literal':True},[])
    same=compare(old,rows([rule(A),rule(B)]));assert same['membership']['state']=='KNOWN' and same['impact']['affected']==[]
    duplicate=deepcopy(old);duplicate['resource_grants']*=3
    assert compare(duplicate,rows([rule(A),rule(B)]))==same
    inserted=compare(old,rows([rule(A),rule(B),rule(C)]))
    assert inserted['membership']['added']==[C] and not inserted['membership']['newly_observed']
    assert 'resource:'+C not in {n['id'] for n in inserted['before']['nodes']}
    assert {x for x in inserted['impact']['affected'] if x.startswith('step-')}=={'step-P2','step-P3','step-P4','step-P5'}
    assert 'step-P1' in inserted['impact']['preserved']
    partial=deepcopy(old);partial['resource_collection']=stamp(rows([rule(A),rule(B),rule(C)]))
    x=compare(partial,rows([rule(A),rule(B),rule(C)]))
    assert x['membership']['state']=='UNKNOWN' and x['membership']['added']==x['membership']['removed']==x['membership']['changed']==[]
    assert x['membership']['newly_observed']==[C] and 'resource:'+C not in {n['id'] for n in x['before']['nodes']}
    assert {'step-P2','step-P3','step-P4','step-P5'}<=set(x['impact']['uncertain'])
    false=deepcopy(old);false['resource_grants'][1]['active']=False
    prior=rows([rule(A),rule(B)]);prior[0]['active']=False;false['resource_collection']=stamp(prior)
    y=compare(false,rows([rule(A),rule(B)]))
    assert y['membership']['state']=='UNKNOWN' and y['membership']['changed']==[] and y['membership']['observation_changed']==[A]
    assert y['before_basis']['observed_row_count']==3
    conflict=deepcopy(old);conflict['resource_grants'].append(dict(resource_id=A,capability='HOLD',active=False))
    assert not compare(conflict,rows([rule(A),rule(B)]))['before_basis']['complete']
    revised=[rule(A),rule(B)];revised[1]['capacity']=9
    assert compare(old,rows(revised))['membership']['changed']==[B]
    assert old==source([rule(A),rule(B)])


def state(f):
    with f[1].connect() as c:
        names=[r['tablename'] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'authorization_audit' ORDER BY tablename")]
        return {t:[r['row'] for r in c.execute(sql.SQL('SELECT to_jsonb(t)::text AS row FROM {} t ORDER BY to_jsonb(t)::text').format(sql.Identifier(t)))] for t in names}
def path(p,card):return '/api/preparations/'+p['preparation_id']+'/opportunities/'+card['id']+'/plan-revision'
def get(f,p,card,params=PARAMS):return f[3].get(path(p,card),params=params,headers=headers(f[2]))
def refresh(f,p):
    r=post(f,p,body(opportunity_read(f,p).json(),'REFRESH'));assert r.status_code==200,r.text
    return r.json()['current']['cards'][0]


def test_independent_actual_read_gate_does_not_confirm_unobserved_member_removal(http_f):
    f=http_f;p,*_=complete(f,local=True);assert lock(f,p,'P3').status_code==200
    imported(f,p);new=str(add_resource(f));card=refresh(f,p);history=deepcopy(stored(f,p));before=state(f)
    r=get(f,p,card);assert r.status_code==200,r.text;x=r.json()['resource_dependency_preview'];ids={s['adapter_id']:s['id'] for s in history['steps']}
    assert x['before_basis']['complete'] and x['current_basis']['complete'] and x['membership']['added']==[new]
    assert set(x['impact']['affected'])&set(ids.values())=={ids[a] for a in ('P2','P3','P4','P5')}
    old=get(f,p,card,params={**PARAMS,'graph_preview':'VERSIONED_TYPED_GRAPH_V1'});assert old.status_code==200
    assert {k:v for k,v in r.json().items() if k!='resource_dependency_preview'}==old.json()
    assert state(f)==before and stored(f,p)==history
    removed=str(resource_combinations.SECOND_RESOURCE_ID)
    with f[1].connect() as c:c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND resource_id=%s AND capability='READ'",(removed,))
    before=state(f);r=get(f,p,card);assert r.status_code==200,r.text;y=r.json()['resource_dependency_preview']
    assert not y['current_basis']['complete'] and y['membership']['state']=='UNKNOWN'
    assert y['membership']['removed']==[] and y['membership']['no_longer_observed']==[removed]
    assert 'resource:'+removed not in {n['id'] for n in y['current']['nodes']}
    assert 'resource:'+removed in {n['id'] for n in y['before']['nodes']}
    assert {ids[a] for a in ('P2','P3','P4','P5')}<=set(y['impact']['uncertain']) and ids['P1'] in y['impact']['preserved']
    assert state(f)==before and stored(f,p)==history
    (BASE/'independent-api-evidence.json').write_text(json.dumps(dict(known_added=[new],unreadable_before_member=removed,confirmed_removed_after_revoke=[],no_longer_observed=[removed],current_hidden=True,history_not_filled=True,public_tables=len(before),GET_business_rows_unchanged=True),sort_keys=True,indent=2)+'\n')


def test_independent_full_html_resource_A_late_to_P1_B_and_current403(http_f):
    f=http_f;a,*_=complete(f,local=True);assert lock(f,a,'P1').status_code==200
    imported(f,a);add_resource(f);card_a=refresh(f,a)
    b=setup(f,GOALS[0]);assert adopt(f,b).status_code==201;card_b=imported(f,b)[1]['cards'][0]
    config=dict(base=str(f[3].base_url).rstrip('/'),token=f[2]['fixture-a'],A=a,B=b,card=card_a['id'],cardB=card_b['id'])
    child=subprocess.Popen(['node',str(BASE/'independent_resource_members_full_html.js')],cwd=Path.cwd(),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
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
                else:raise AssertionError(action)
                child.stdin.write('{}\n');child.stdin.flush()
            else:result=message;break
        assert child.wait(timeout=10)==0
        assert result and result['scope']=='INDEPENDENT_FULL_HTML_RESOURCE_MEMBER_TWO_CASE_ACTUAL_ASGI_PG'
        assert result['real_browser']=='NOT_RUN' and result['probes']==dict(cases=6,rejected=6)
        assert all(c['method']=='GET' for c in result['calls'])
    finally:
        if child.poll() is None:child.terminate();child.wait(timeout=5)
        reader.join(timeout=5)
        while not incoming.empty():
            line=incoming.get_nowait()
            if line is not None:lines.append(line)
        (BASE/'independent-html.stdout.jsonl').write_text(''.join(lines));(BASE/'independent-html.stderr.log').write_text(child.stderr.read())
