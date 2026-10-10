"""Fresh Case inputs across the original fixed scopes; actual HTTP and PG only."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import socket
import threading
import time
from uuid import uuid4

import httpx
import pytest
import uvicorn
from psycopg.conninfo import conninfo_to_dict

from parkweave import isolated_local_execution, resource_holds as rh, resource_combinations as rc
from parkweave.isolated_run_access import IsolatedRunAccessBridge
from parkweave.service_plan_approval import IsolatedPlanApproval
from parkweave.template_candidate import TemplateConfig, TemplateEngine, TemplateRepository, Scope
from parkweave.template_consumer import TemplateConsumer, ConsumerConfig, ConsumerRepository
from parkweave.template_isolated_app import create_isolated_template_app
from test_template_candidate import template_config, definition, VALID
from test_template_consumer import template_consumption
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture, headers
from test_isolated_run_access import permission_snapshot
from test_service_case_steps import GOALS
from test_resource_holds import body as hold_body

ALL_GOALS = GOALS + ['LOCAL_SYNTHETIC_COORDINATION_RECORDS']
OUT = Path('.runtime/new-enterprise-chain/api')


@contextmanager
def actual_http(app):
    listener=socket.socket();listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='warning',access_log=False))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True);thread.start()
    try:
        end=time.monotonic()+10
        while not server.started and thread.is_alive() and time.monotonic()<end:time.sleep(.02)
        assert server.started
        requests=[]
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=20,event_hooks={'request':[lambda r:requests.append(dict(method=r.method,path=r.url.path))]}) as client:
            yield client,requests
    finally:
        server.should_exit=True;thread.join(10);listener.close();assert not thread.is_alive()


@pytest.fixture
def fresh_chain(link_fixture, tmp_path):
    original = link_fixture
    cfg = template_config().model_dump()
    for permit in cfg['permits']: permit['scope']['park_id'] = 'park-a'
    engine = TemplateEngine(TemplateConfig.model_validate(cfg), TemplateRepository(tmp_path/'fresh.template.candidate.sqlite3'))
    consumer = TemplateConsumer(original[0], engine, ConsumerConfig(enabled_for_isolated_tests=True,
        allowed_database_names=[conninfo_to_dict(original[0].dsn)['dbname']],
        allowed_orgs=[dict(park_id='park-a', org_id='org-a'), dict(park_id='park-a', org_id='org-b')]),
        ConsumerRepository(tmp_path/'fresh.consumer.candidate.sqlite3'))
    before = permission_snapshot(original[1])
    access = IsolatedRunAccessBridge(original[1], original[1]._case_fact_fixture_receipt,
        tmp_path/'fresh.run-access.candidate.sqlite3', approver_ids={'prep-specialist-fixture-a', 'prep-specialist-fixture-b'}, enabled_for_isolated_tests=True)
    access.attach_store(original[0])
    local = isolated_local_execution.IsolatedLocalExecutor(access, enabled_for_isolated_tests=True)
    local.attach_store(original[0])
    assert permission_snapshot(original[1]) == before
    with original[1].connect() as c:
        assert all(c.execute('SELECT count(*) n FROM '+t).fetchone()['n'] == 0 for t in ['runs','cases','preparations','service_step_receipts','run_assignments'])
    app = create_isolated_template_app(original[0], engine, consumer)
    with actual_http(app) as (client,requests):
        f=original[:3]+(client,)
        yield dict(f=f,engine=engine,consumer=consumer,access=access,local=local,scope=Scope(park_id='park-a',template_id='new-enterprise-material-template'),base=str(client.base_url).rstrip('/'),requests=requests,permissions=before)


def ok(response, expected=200):
    assert response.status_code == expected, response.text
    return response.json()


def call(u,path,*,actor='fixture-a',data=None,key=None,expected=200):
    f=u['f']
    if data is None:response=f[3].get(path,headers=headers(f[2],actor))
    else:response=f[3].post(path,headers=headers(f[2],actor,key or uuid4().hex),json=data)
    return ok(response,expected)


def publish(u,goals=ALL_GOALS):
    base='/api/template-candidate/park-a/'+u['scope'].template_id
    for action,actor in [('SAVE_DRAFT','template-author'),('SUBMIT','template-author'),('REVIEW','template-reviewer'),('CANDIDATE_PUBLISH','template-publisher')]:
        h={'X-Isolated-Template-Actor':actor,'Idempotency-Key':uuid4().hex}
        view=ok(u['f'][3].get(base,headers=h))
        data=dict(action=action,expected_revision=view['revision'],expected_definition_sha256=view['definition_sha256'],reason='SYNTHETIC independent original '+action)
        if action=='SAVE_DRAFT':data['draft']=definition(goals).model_dump(mode='json')
        if action=='CANDIDATE_PUBLISH':data['validity']=VALID
        ok(u['f'][3].post(base+'/commands',headers=h,json=data))
    catalog=call(u,'/api/template-consumer/catalog')
    assert len(catalog['templates'])==1
    return catalog['templates'][0]


def input_body(release,owner='fixture-a',number=0):
    return dict(release_id=release['release_id'],expected_release_sha256=release['release_sha256'],
        goal=f'SYNTHETIC PRIVATE_FRESH_{owner}_{number} independently submitted request',reviewer_id='prep-specialist-'+owner,
        materials=[dict(slot='need_summary',text=f'SYNTHETIC PRIVATE_FRESH_NEED_{owner}_{number}',source_kind='USER_STATEMENT',source_label='Current new enterprise statement'),
                   dict(slot='material_outline',text=f'SYNTHETIC PRIVATE_FRESH_OUTLINE_{owner}_{number}',source_kind='DOCUMENT_EXCERPT',source_label='Current explicitly provided synthetic document')],
        reason='Explicit original template with entirely new inputs')


def new_case(u,release,owner='fixture-a',number=0):
    row=call(u,'/api/template-consumer/instances',actor=owner,data=input_body(release,owner,number),expected=201)
    assert row['state']=='PENDING_RUN' and not row['case_id']
    work=u['f'][0].claim('new-enterprise-original-worker');assert work and str(work['id'])==row['run_id']
    u['f'][0].finish(work)
    row=call(u,'/api/template-consumer/instances/'+row['instance_id']+'/resume',actor=owner,data={})
    assert row['state']=='PLAN_ADOPTED' and not row['new_grants'] and not row['automatic_execution']
    assert row['service_case_plan']['required_goals']==ALL_GOALS
    return row


def parent(u,row,owner='fixture-a'):
    return call(u,'/api/preparations/'+row['preparation_id'],actor=owner)['preparation']


def material_decision(u,row,action,owner='fixture-a'):
    actor='prep-specialist-'+owner if action=='REVIEW' else owner
    p=parent(u,row,owner)
    return call(u,'/api/preparations/'+row['preparation_id']+'/commands',actor=actor,data=dict(action=action,expected_revision=p['revision'],reason='SYNTHETIC independent '+action))


def verify(u,row,adapter,owner='fixture-a'):
    path='/api/preparations/'+row['preparation_id']+'/service-case-plan'
    view=call(u,path,actor=owner);step=next(s for s in view['steps'] if s['adapter_id']==adapter)
    result=call(u,path+'/commands',actor=owner,data=dict(action='VERIFY',step_id=step['id'],expected_revision=view['revision'],expected_source_sha256=step['source_sha256'],reason='SYNTHETIC original owner verifies actual '+adapter))
    assert next(s for s in result['steps'] if s['adapter_id']==adapter)['state']=='VERIFIED'
    return result


def adopt_existing_access_change(u,row,owner='fixture-a'):
    """Owner explicitly adopts the original approved Run collection; never implicit."""
    path='/api/preparations/'+row['preparation_id']+'/service-case-plan'
    before=call(u,path,actor=owner);assert before['local_revision_required'] and before['can_adopt']
    original=original_rows(u,row)
    q=before['current_preview'];body=dict(expected_preparation_revision=before['preparation_revision'],
        expected_request_revision=before['request_revision'],expected_plan_revision=before['revision'],
        expected_source_sha256=q['source_sha256'],required_goals=q['required_goals'],local_revision=True,
        reason='SYNTHETIC owner explicitly adopts existing approved Run access change')
    after=call(u,path,actor=owner,data=body,expected=201)
    assert after['plan_id']==before['plan_id'] and after['revision']==before['revision']+1
    assert after['events'][:-1]==before['events']
    event=after['events'][-1]['local_revision'];ids={s['adapter_id']:s['id'] for s in before['steps']}
    assert set(event['affected'])=={ids['P3'],ids['P4'],ids['P5']} and set(event['preserved'])=={ids['P1'],ids['P2']}
    assert after['steps'][0]==before['steps'][0]
    current=original_rows(u,row)
    for table in original:
        if table=='preparations':
            for old,new in zip(original[table],current[table]):
                assert {k:v for k,v in old.items() if k!='service_case_plan'}=={k:v for k,v in new.items() if k!='service_case_plan'}
        else:assert current[table]==original[table]
    return after


def request_access(u,row,owner='fixture-a',action='REQUEST'):
    path='/api/runs/'+row['run_id']+'/access'
    actor='prep-specialist-'+owner if action=='APPROVE' else owner
    view=call(u,path,actor=actor)
    data=dict(action=action,expected_revision=view['revision'],expected_run_revision=view['run_revision'],expected_authority_sha256=view['authority_sha256'],reason='SYNTHETIC explicit exact Run '+action)
    if action=='REQUEST':
        now=datetime.now(timezone.utc);data.update(target_id='executor-'+owner[-1],target_role='service_executor',capability='READ',requested_validity=dict(valid_from=now.isoformat(),valid_until=(now+timedelta(minutes=20)).isoformat(),timezone='UTC'))
    if action=='APPROVE':data['approved_validity']=view['request']['requested_validity']
    return call(u,path+'/commands',actor=actor,data=data)


def holds(u,owner='fixture-a',offset=0):
    f=u['f'];base=hold_body(f,ttl=300);start=datetime.fromisoformat(base['starts_at'])+timedelta(hours=offset);rows=[]
    for i,id in enumerate([rh.RESOURCE_ID,rc.SECOND_RESOURCE_ID,rh.RESOURCE_ID]):
        data={**base,'starts_at':(start+timedelta(hours=3*i)).isoformat(),'ends_at':(start+timedelta(hours=3*i+1)).isoformat(),'purpose':'SYNTHETIC original resource for '+owner}
        rows.append(call(u,'/api/synthetic-resources/'+str(id)+'/holds',actor=owner,data=data,expected=201)['hold'])
    return rows,dict(members=[dict(hold_id=h['id'],expected_revision=h['resource_revision']) for h in rows])


def enable_approval(u,rows):
    f=u['f'];bridge=IsolatedPlanApproval(f[1],f[1]._case_fact_fixture_receipt,preparation_ids=[r['preparation_id'] for r in rows],enabled_for_isolated_tests=True);bridge.attach_store(f[0]);return bridge


def delivery(u,row,data,owner='fixture-a'):
    path='/api/preparations/'+row['preparation_id']
    q=call(u,path+'/resource-delivery/preview',actor=owner,data=data)
    body={**data,**{k:q[k] for k in ['expected_preparation_revision','expected_plan_revision']},'expected_source_sha256':q['source_sha256'],'valid_until':q['valid_until'],'reason':'SYNTHETIC actual original capacity delivery'}
    approval=call(u,path+'/plan-approval/proposals',actor=owner,data=dict(expected_revision=0,delivery=body),expected=201);item=approval['items'][-1]
    approval=call(u,path+'/plan-approval/commands',actor=owner,data=dict(action='APPROVE',approval_id=item['id'],expected_revision=approval['revision'],expected_binding_sha256=item['binding_sha256'],reason='SYNTHETIC explicit original Approval'))
    key=uuid4().hex;result=call(u,path+'/resource-delivery',actor=owner,key=key,data={**body,'approval_id':item['id']},expected=201)
    assert result['independent_check']['status']=='CURRENT' and not result['case_goal_completed']
    assert result['receipt']['plan_approval']['id']==item['id']
    return result,key


def acceptance(u,row,owner='fixture-a'):
    p=parent(u,row,owner);executor='executor-'+owner[-1]
    offer=call(u,'/api/preparations/'+row['preparation_id']+'/dispatch',actor='prep-specialist-'+owner,data=dict(expected_preparation_revision=p['revision'],expected_dispatch_revision=0,executor_id=executor,reason='SYNTHETIC explicit original assigned responsibility'),expected=201)
    assert not offer['receipt_step_id']
    accepted=call(u,'/api/service-dispatches/'+offer['dispatch_id']+'/commands',actor=executor,data=dict(action='ACCEPT',expected_revision=offer['revision'],reason='SYNTHETIC actual counterparty accepts'))
    return accepted


def report_and_ack(u,row,dispatch,owner='fixture-a'):
    executor='executor-'+owner[-1];path='/api/executor-receipts/'+dispatch['receipt_step_id'];view=call(u,path,actor=executor)
    report=call(u,path+'/execute-local',actor=executor,data=dict(expected_revision=view['step']['revision'],reason='SYNTHETIC explicitly generate original local report'))
    receipt=report['current_receipt'];metadata=receipt['adapter_execution']['report']
    assert metadata['binding']['case_id']==row['case_id'] and metadata['binding']['run_id']==row['run_id'] and metadata['binding']['executor_id']==executor
    assert hashlib.sha256(receipt['text'].encode()).hexdigest()==receipt['source_sha256']
    assert not report['case_goal_completed']
    ack=call(u,path+'/commands',actor=owner,data=dict(action='ACKNOWLEDGE',expected_revision=report['step']['revision'],receipt_sha256=receipt['source_sha256'],reason='SYNTHETIC original enterprise checks actual report'))
    assert ack['step']['state']=='LOCAL_ACKNOWLEDGED'
    return ack


def finish_chain(u,row,owner='fixture-a',offset=0):
    material_decision(u,row,'REVIEW',owner);material_decision(u,row,'CONFIRM',owner);verify(u,row,'P1',owner)
    catalog=call(u,'/api/service-dispatches/catalog?preparation_id='+row['preparation_id'],actor='prep-specialist-'+owner)
    assert catalog['executors']==[] and not catalog['ready']
    request_access(u,row,owner);request_access(u,row,owner,'APPROVE')
    adopt_existing_access_change(u,row,owner)
    hs,data=holds(u,owner,offset);sent,key=delivery(u,row,data,owner);verify(u,row,'P2',owner)
    dispatch=acceptance(u,row,owner);verify(u,row,'P3',owner);ack=report_and_ack(u,row,dispatch,owner);verify(u,row,'P4',owner)
    path='/api/preparations/'+row['preparation_id'];local=call(u,path+'/local-case',actor=owner)
    call(u,path+'/local-case/commands',actor=owner,data=dict(action='REVALIDATE',expected_revision=local['revision'],expected_cycle=local['cycle'],expected_snapshot_sha256=local['current_snapshot_sha256'],reason='SYNTHETIC explicit original local record recheck'))
    verify(u,row,'P5',owner)
    results=call(u,path+'/goal-results',actor=owner)
    assert results['state']=='LOCAL_OUTPUTS_VERIFIED' and len(results['results'])==6 and all(r['state']=='LOCAL_OUTPUT_VERIFIED' for r in results['results'])
    out=next(x['actual_output'] for x in results['results'] if x['goal']==GOALS[3])
    assert out['kind']=='ISOLATED_SYNTHETIC_HANDOFF_REPORT_ACKNOWLEDGEMENT' and out['execution_id']==ack['current_receipt']['adapter_execution']['report']['execution_id']
    run=call(u,'/api/runs/'+row['run_id'],actor=owner);assert run['case']['state']=='WAITING_CONFIRMATION' and not results['case_goal_completed']
    return dict(row=row,owner=owner,results=results,delivery=sent,delivery_key=key,dispatch=dispatch,receipt=ack,holds=hs)


def original_rows(u,row):
    with u['f'][1].connect() as c:
        saved={t:c.execute('SELECT * FROM '+t+' WHERE '+field+'=%s ORDER BY to_jsonb('+t+')::text',(row[id],)).fetchall() for t,field,id in [('cases','id','case_id'),('runs','id','run_id'),('preparations','id','preparation_id'),('preparation_evidence','preparation_id','preparation_id'),('preparation_events','preparation_id','preparation_id'),('case_resource_links','preparation_id','preparation_id'),('service_dispatches','preparation_id','preparation_id'),('service_receipt_steps','preparation_id','preparation_id'),('controlled_plans','preparation_id','preparation_id'),('controlled_plan_events','preparation_id','preparation_id')]}
        for table in ['service_step_receipts','service_receipt_events']:
            saved[table]=c.execute('SELECT * FROM '+table+' WHERE step_id IN (SELECT id FROM service_receipt_steps WHERE preparation_id=%s) ORDER BY to_jsonb('+table+')::text',(row['preparation_id'],)).fetchall()
        return saved


def test_two_fresh_enterprises_and_third_new_input_real_whole_local_chain(fresh_chain):
    u=fresh_chain;release=publish(u);a=new_case(u,release);b=new_case(u,release,'fixture-b');again=new_case(u,release,'fixture-a',1)
    enable_approval(u,[a,b,again]);done_a=finish_chain(u,a);preserved=original_rows(u,a);done_b=finish_chain(u,b,'fixture-b');assert original_rows(u,a)==preserved
    # The original a lease is not a grant on the new Run.
    assert call(u,'/api/service-dispatches/catalog?preparation_id='+again['preparation_id'],actor='prep-specialist-fixture-a')['executors']==[]
    done_again=finish_chain(u,again,offset=24);assert original_rows(u,a)==preserved
    assert permission_snapshot(u['f'][1])==u['permissions']
    for field in ['instance_id','run_id','case_id','preparation_id','plan_id']:assert len({r[field] for r in [a,b,again]})==3
    assert len({d['receipt']['current_receipt']['id'] for d in [done_a,done_b,done_again]})==3
    with u['f'][1].connect() as c:
        for row,owner,number in [(a,'fixture-a',0),(b,'fixture-b',0),(again,'fixture-a',1)]:
            materials=c.execute('SELECT * FROM preparation_evidence WHERE preparation_id=%s',(row['preparation_id'],)).fetchall()
            assert {m['text'] for m in materials}=={m['text'] for m in input_body(release,owner,number)['materials']}
            assert all(hashlib.sha256(m['text'].encode()).hexdigest()==m['source_sha256'] for m in materials)
        assignments=c.execute('SELECT * FROM run_assignments ORDER BY run_id').fetchall();assert len(assignments)==3 and all(isinstance(x['managed_access'],dict) for x in assignments)
        assert not c.execute("SELECT 1 FROM cases WHERE state='FULFILLED'").fetchone()
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'whole-local-chain.json').write_text(json.dumps(dict(actual_http=True,actual_pg=True,new_fixed_fixture_enterprises=['fixture-a','fixture-b'],fresh_inputs=3,goals_per_case=6,distinct_case_ids=[r['case_id'] for r in [a,b,again]],reports=3,explicit_run_requests=3,explicit_independent_run_approvals=3,original_permissions_unchanged=True,first_case_rows_preserved=True,fulfilled=False,external_acceptance='NOT_SUBMITTED',offline_fulfillment='NO_EVIDENCE'))+'\n')


@pytest.mark.parametrize('bad',['empty-material','foreign-reviewer','extra-authority'])
def test_invalid_new_inputs_never_create_case_or_copy_prior_result(fresh_chain,bad):
    u=fresh_chain;release=publish(u);data=input_body(release)
    if bad=='empty-material':data['materials'][1]['text']=''
    elif bad=='foreign-reviewer':data['reviewer_id']='prep-specialist-fixture-b'
    else:data['run_id']=str(uuid4())
    response=u['f'][3].post('/api/template-consumer/instances',headers=headers(u['f'][2],key=uuid4().hex),json=data)
    assert response.status_code==(403 if bad=='foreign-reviewer' else 422)
    with u['f'][1].connect() as c:
        assert all(c.execute('SELECT count(*) n FROM '+t).fetchone()['n']==0 for t in ['runs','cases','preparations','run_assignments','service_step_receipts'])
    assert permission_snapshot(u['f'][1])==u['permissions']


def test_new_run_cannot_reuse_other_enterprise_approval_acceptance_or_result(fresh_chain):
    u=fresh_chain;release=publish(u);a=new_case(u,release);enable_approval(u,[a]);done=finish_chain(u,a);before=original_rows(u,a)
    for suffix in ['/goal-results','/plan-approval','/resource-delivery/recovery/'+done['delivery_key']]:
        r=u['f'][3].get('/api/preparations/'+a['preparation_id']+suffix,headers=headers(u['f'][2],'fixture-b'));assert r.status_code==403 and 'PRIVATE_FRESH' not in r.text
    r=u['f'][3].post('/api/service-dispatches/'+done['dispatch']['dispatch_id']+'/commands',headers=headers(u['f'][2],'executor-b',uuid4().hex),json=dict(action='ACCEPT',expected_revision=1,reason='SYNTHETIC foreign attempt'));assert r.status_code==403
    assert original_rows(u,a)==before and permission_snapshot(u['f'][1])==u['permissions']


def test_eng098_new_enterprise_material_path_stops_at_actual_original_permission_boundary(template_consumption):
    from test_template_consumer import consume,finish,resume,headers as th
    from template_candidate_support import ENTERPRISES,REVIEWERS,grant_snapshot
    f=dict(template_consumption);before=grant_snapshot(f['owner']);evidence=[]
    with actual_http(create_isolated_template_app(f['store'],f['engine'],f['consumer'])) as (client,requests):
        f['client']=client
        for index in (0,1):
            row=ok(consume(f,index,key='actual-eng098-'+str(index)),201);finish(f);row=ok(resume(f,row,index,key='actual-resume-'+str(index)));path='/api/preparations/'+row['preparation_id']
            for action,actor in [('REVIEW',REVIEWERS[index]),('CONFIRM',ENTERPRISES[index])]:
                p=ok(client.get(path,headers=th(f,index)))['preparation'];ok(client.post(path+'/commands',headers={'Authorization':'Bearer '+f['tokens'][actor],'Idempotency-Key':uuid4().hex},json=dict(action=action,expected_revision=p['revision'],reason='SYNTHETIC explicit original material '+action)))
            view=ok(client.get(path+'/service-case-plan',headers=th(f,index)));step=view['steps'][0]
            ok(client.post(path+'/service-case-plan/commands',headers=th(f,index,key=uuid4().hex),json=dict(action='VERIFY',step_id=step['id'],expected_revision=view['revision'],expected_source_sha256=step['source_sha256'],reason='SYNTHETIC only actual original material result')))
            result=ok(client.get(path+'/goal-results',headers=th(f,index)));assert result['results'][0]['state']=='LOCAL_OUTPUT_VERIFIED' and not result['case_goal_completed']
            assert ok(client.get('/api/synthetic-resources',headers=th(f,index)))['items']==[]
            catalog=ok(client.get('/api/service-dispatches/catalog',params={'preparation_id':row['preparation_id']},headers={'Authorization':'Bearer '+f['tokens'][REVIEWERS[index]]}));assert catalog['executors']==[] and not catalog['ready']
            assert client.get(path+'/plan-approval',headers=th(f,index)).status_code==403 and grant_snapshot(f['owner'])==before
            evidence.append(dict(enterprise=ENTERPRISES[index],case_id=row['case_id'],material_goal='LOCAL_OUTPUT_VERIFIED',resource_catalog=[],executor_catalog=[],approval_status=403,grant_rows_unchanged=True,whole_chain_accepted=False))
        OUT.mkdir(parents=True,exist_ok=True);(OUT/'eng098-permission-boundary.json').write_text(json.dumps(dict(actual_http=True,actual_pg=True,enterprises=evidence,requests=requests))+'\n')
