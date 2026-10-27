"""One actual database, two fixed synthetic scopes, independent user decisions.

Setup is the only initializer. SQL below observes business state; no ready Case,
Run assignment, copied evidence or approval is inserted by a fixture.
"""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import json
import pytest
from parkweave.store import Store,Denied,digest
from scripts import ordinary_synthetic_demo as demo
from test_ordinary_synthetic_demo import (
    demo_state,server,call,port,PrivateTokens,prepare_case,adopt_case,new_case,
    verify,complete,html,GOALS,
)

TABLES=('runs','cases','preparations','preparation_events','preparation_evidence',
    'synthetic_resource_holds','synthetic_resource_receipts','synthetic_resource_combinations',
    'synthetic_resource_combination_members','synthetic_resource_combination_receipts',
    'case_resource_links','resource_case_claims','service_dispatches','service_dispatch_offers',
    'service_dispatch_events','service_receipt_steps','service_step_receipts','service_receipt_events',
    'case_local_lifecycles','case_local_events','controlled_plans','controlled_plan_events')


def sessions(tokens,scope):
    return PrivateTokens({actor:tokens[key] for actor,key in scope['sessions'].items()})


def business(p):
    with Store(demo.lifecycle.dsn(p)).connect() as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        rows={t:c.execute('SELECT * FROM '+t+' ORDER BY to_jsonb('+t+')::text').fetchall() for t in TABLES}
        return digest(json.dumps(rows,sort_keys=True,default=str)),{t:len(v) for t,v in rows.items()}


def denied(api,tokens,path,records,body=None,actor='enterprise',status=403):
    result=call(api,tokens,path,body,actor=actor,expected=status)
    records.append(dict(method='GET' if body is None else 'POST',path=path,actor=actor,status=status,response=result))


def catalog(api,tokens,scope):
    row=call(api,tokens,'/api/preparation-catalog')
    assert row['reviewers']==[dict(id=scope['ids']['specialist'])]
    assert len(row['services'])==1 and row['services'][0]['source']['id']==scope['source_id']
    resources=call(api,tokens,'/api/synthetic-resources')['items']
    assert {r['id'] for r in resources}=={r['id'] for r in scope['resources']}


def foreign_reads(api,tokens,p,dispatch,group,records):
    base='/api/preparations/'+p['preparation_id']
    paths=['/api/runs/'+p['run_id'],base,base+'/planning-preview',base+'/service-case-plan',
        base+'/goal-results',base+'/local-case',base+'/resource-link',
        '/api/resource-combinations/'+group['id'],
        '/api/resource-holds/'+group['members'][0]['id'],
        '/api/service-dispatches/'+dispatch['dispatch_id']]
    for path in paths:denied(api,tokens,path,records)
    for actor in ('enterprise','specialist','executor'):
        denied(api,tokens,'/api/executor-receipts/'+dispatch['receipt_step_id'],records,actor=actor)
        denied(api,tokens,'/api/service-dispatches/'+dispatch['dispatch_id'],records,actor=actor)
    denied(api,tokens,base,records,actor='specialist')


def pack(api,tokens,directory,p,results):
    fixture=(None,None,{'fixture-a':tokens['enterprise'],'executor-a':tokens['executor']},api)
    result=html(fixture,directory,p,results['plan_id'],'LOCAL_OUTPUTS_VERIFIED',goal_count=5)
    assert result['checks']==19 and all(c['method']=='GET' for c in result['calls'])
    return result


def test_second_enterprise_first_cold_case_after_restart_and_bidirectional_isolation(demo_state,tmp_path):
    state,marker,tokens=demo_state;primary=demo.SCOPES['primary'];secondary=demo.SCOPES['secondary']
    assert len(tokens)==6 and len(set(tokens.values()))==6
    assert marker['scopes']==demo.SCOPES
    assert primary['park_id']!=secondary['park_id'] and primary['org_id']!=secondary['org_id']
    assert set(primary['ids'].values()).isdisjoint(secondary['ids'].values())
    first_tokens=sessions(tokens,primary);second_tokens=sessions(tokens,secondary)
    original_marker=(state/'state.json').read_bytes();starts=[];refusals=[]
    with server(state,tmp_path/'first-scope') as (api,ready):
        starts.append(ready);assert len(ready['available_scopes'])==2
        catalog(api,first_tokens,primary);catalog(api,second_tokens,secondary)
        with Store(demo.lifecycle.dsn(state)).connect() as c:
            c.execute('SET TRANSACTION READ ONLY')
            assert marker['authority']['counts']==dict(principals=6,capability_grants=8,action_grants=2,
                preparation_grants=4,preparation_catalog=2,run_assignments=0,field_grants=0,
                synthetic_resources=4,synthetic_resource_grants=8)
            assert all(not c.execute('SELECT 1 FROM '+t+' LIMIT 1').fetchone() for t in TABLES)
        first,first_request_revision=prepare_case(api,first_tokens,'第一企业独立设备维护',primary)
        first_preview=call(api,first_tokens,'/api/preparations/'+first['preparation_id']+'/planning-preview')['current']
        adopt_case(api,first_tokens,first,first_request_revision)
        first_dispatch,first_results=complete(api,first_tokens,first,'第一企业',primary)
        link=call(api,first_tokens,'/api/preparations/'+first['preparation_id']+'/resource-link')
        first_group=link['current']['combination']
        first_pack=pack(api,first_tokens,tmp_path/'first-html',first,first_results)
        before=business(state)
        foreign_reads(api,second_tokens,first,first_dispatch,first_group,refusals)
        assert call(api,second_tokens,'/api/preparations')['items']==[]
        assert call(api,second_tokens,'/api/cases/worklist')['items']==[]
        denied(api,second_tokens,'/api/preparations',refusals,dict(run_id=first['run_id'],
            service_id='synthetic-material-preparation',service_version=1,reviewer_id=secondary['ids']['specialist']))
        assert business(state)==before
    assert not (state/'data/postmaster.pid').exists()
    with server(state,tmp_path/'second-scope-cold') as (api,ready):
        starts.append(ready)
        assert all(ready[k]!=starts[0][k] for k in ('api_pid','worker_pid','postgres_pid'))
        assert call(api,second_tokens,'/api/cases/worklist')['items']==[]
        assert call(api,second_tokens,'/api/preparations')['items']==[]
        assert call(api,first_tokens,'/api/preparations/'+first['preparation_id']+'/goal-results')==first_results
        cold_pack=pack(api,first_tokens,tmp_path/'first-cold-html',first,first_results)
        assert (tmp_path/'first-html/download.txt').read_bytes()==(tmp_path/'first-cold-html/download.txt').read_bytes()
        second,request_revision=prepare_case(api,second_tokens,'第二企业首次新员工培训',secondary)
        base='/api/preparations/'+second['preparation_id']
        own_preview=call(api,second_tokens,base+'/planning-preview')['current']
        assert own_preview['source_sha256']!=first_preview['source_sha256']
        before=business(state)
        denied(api,second_tokens,base+'/service-case-plan',refusals,dict(
            expected_preparation_revision=second['revision'],expected_request_revision=request_revision,
            expected_source_sha256=first_preview['source_sha256'],expected_plan_revision=0,
            required_goals=GOALS,reason='SYNTHETIC forbidden old enterprise proof'),status=409)
        denied(api,second_tokens,'/api/preparations',refusals,dict(run_id=second['run_id'],
            service_id='synthetic-material-preparation',service_version=1,reviewer_id=primary['ids']['specialist']))
        assert business(state)==before
        adopt_case(api,second_tokens,second,request_revision);verify(api,second_tokens,second,'P1')
        before=business(state)
        denied(api,second_tokens,base+'/resource-link',refusals,dict(combination_id=first_group['id'],
            expected_preparation_revision=second['revision'],expected_link_revision=0,reason='SYNTHETIC cross enterprise combination'))
        now=datetime.now(timezone.utc)
        denied(api,second_tokens,'/api/synthetic-resources/'+primary['resources'][0]['id']+'/holds',refusals,
            dict(starts_at=(now+timedelta(hours=1)).isoformat(),ends_at=(now+timedelta(hours=2)).isoformat(),
                quantity=1,expected_revision=1,ttl_seconds=120,purpose='SYNTHETIC denied cross park'))
        denied(api,second_tokens,base+'/dispatch',refusals,dict(expected_preparation_revision=second['revision'],
            expected_dispatch_revision=0,executor_id=primary['ids']['executor'],reason='SYNTHETIC foreign executor'),actor='specialist')
        assert business(state)==before
        second_dispatch,second_results=complete(api,second_tokens,second,'第二企业',secondary,p1_verified=True)
        second_link=call(api,second_tokens,base+'/resource-link');second_group=second_link['current']['combination']
        second_pack=pack(api,second_tokens,tmp_path/'second-html',second,second_results)
        before=business(state)
        foreign_reads(api,first_tokens,second,second_dispatch,second_group,refusals)
        assert business(state)==before
        assert all(first[k]!=second[k] for k in ('run_id','case_id','preparation_id'))
        assert first_results['plan_id']!=second_results['plan_id'] and first_dispatch['dispatch_id']!=second_dispatch['dispatch_id']
        assert first_dispatch['receipt_step_id']!=second_dispatch['receipt_step_id']
        assert {m['resource_id'] for m in second_group['members']}=={r['id'] for r in secondary['resources']}
        for own_tokens,own,other in ((first_tokens,first,second),(second_tokens,second,first)):
            for path in ('/api/preparations','/api/cases/worklist'):
                payload=call(api,own_tokens,path);assert other['preparation_id'] not in json.dumps(payload) and own['preparation_id'] in json.dumps(payload)
        assert call(api,first_tokens,'/api/preparations/'+first['preparation_id']+'/goal-results')==first_results
        assert call(api,first_tokens,'/api/service-dispatches/'+first_dispatch['dispatch_id'])['assignment_valid_until']==first_dispatch['assignment_valid_until']
        with Store(demo.lifecycle.dsn(state)).connect() as c:
            c.execute('SET TRANSACTION READ ONLY');assert demo.authority(c)==marker['authority']
            assert c.execute('SELECT count(*) n FROM runs').fetchone()['n']==2
            assert c.execute('SELECT count(*) n FROM cases').fetchone()['n']==2
            assert not c.execute('SELECT 1 FROM run_assignments').fetchone()
            materials=c.execute('SELECT preparation_id,id,text,source_label FROM preparation_evidence ORDER BY id').fetchall()
            assert len(materials)==4 and len({m['id'] for m in materials})==4
            assert all(('第二企业' in m['text'])==(str(m['preparation_id'])==second['preparation_id']) for m in materials)
    assert (state/'state.json').read_bytes()==original_marker
    (tmp_path/'two-scope-chain.json').write_text(json.dumps(dict(starts=starts,scopes=demo.SCOPES,
        first=first,second=second,first_plan=first_results['plan_id'],second_plan=second_results['plan_id'],
        dispatches=[first_dispatch['dispatch_id'],second_dispatch['dispatch_id']],
        receipts=[first_dispatch['receipt_step_id'],second_dispatch['receipt_step_id']],
        refusals=refusals,authority_unchanged=True,run_assignments=0,fixture_finish_calls=0,
        physical_pg_restart=True,first_case_preserved=True,second_scope_first_case=True,
        nodevm_checks=[first_pack['checks'],cold_pack['checks'],second_pack['checks']],browser=False),indent=2)+'\n')


def test_scope_binding_missing_or_changed_refuses_before_postgres(demo_state,monkeypatch,tmp_path):
    state,marker,_=demo_state;attempts=[]
    def forbidden(*a,**k):attempts.append(True);raise AssertionError('scope mismatch must not start PostgreSQL')
    monkeypatch.setattr(demo.lifecycle,'postgres',forbidden)
    changes=[]
    missing=deepcopy(marker);missing.pop('scopes');changes.append(missing)
    for key in ('park_id','org_id','ids','resources','sessions'):
        changed=deepcopy(marker);changed['scopes']['secondary'][key]='SYNTHETIC_WRONG_SCOPE';changes.append(changed)
    for changed in changes:
        (state/'state.json').write_text(json.dumps(changed))
        with pytest.raises(Denied):demo.serve(state,port())
    assert not attempts and not (state/'data/postmaster.pid').exists()
    (tmp_path/'scope-binding-denials.json').write_text(json.dumps(dict(changed_fields=['missing scopes','park_id','org_id','ids','resources','sessions'],
        process_creation_attempts=0,negative_state_retained=True,no_repair=True))+'\n')
