"""Real local decisions and atomic consumers over explicit owned synthetic data."""
from copy import deepcopy
from uuid import UUID,uuid4
from concurrent.futures import ThreadPoolExecutor
import pytest,psycopg
from fastapi.testclient import TestClient
from parkweave.api import create_app
from parkweave.store import Store,Denied,Conflict
from parkweave import local_resource_approval as local,service_plan_approval as core,case_resource_delivery as delivery
from test_case_resources import link_fixture
from test_preparation import preparation_fixture,headers
from test_executor_receipts import receipt_fixture
from test_case_resource_delivery import quoted,submit,recover,effects
from test_ordinary_case_goal_results import start
from test_service_case_steps import verified,GOALS
from test_resource_bundles import bundle,states
from test_service_plan_approval import propose,decide,read


@pytest.fixture
def local_fixture(link_fixture):
    f=link_fixture
    f[1].migrate_local_resource_approval_fixture()
    bridge=local.LocalResourceApproval(f[0])
    from parkweave.case_step_assignments import OrdinaryCaseStepAssignments
    with TestClient(create_app(f[0],case_step_assignments=OrdinaryCaseStepAssignments(f[0]),local_resource_approval=bridge)) as api:
        yield (*f[:3],api),bridge


def setup(local_fixture):
    f,bridge=local_fixture;p=start(f,goals=[GOALS[1]]);verified(f,p,'P1');hs,members=bundle(f);data=quoted(f,p,members)
    return f,bridge,p,hs,data


def approved(f,p,data):
    x=propose(f,p,data);assert x.status_code==201,x.text
    x=x.json();assert x['scope']==local.SCOPE
    y=decide(f,p,x['items'][-1],x['revision']);assert y.status_code==200,y.text
    return y.json()['items'][-1],y.json()


def ledger(f,p):
    with f[1].connect() as c:return c.execute('SELECT local_resource_approvals FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['local_resource_approvals']


def test_explicit_mode_requires_existing_schema_and_does_not_install_or_use_isolated_owner(link_fixture):
    f=link_fixture
    assert local.configure(f[0],None) is None
    with pytest.raises(Denied,match='existing local resource approval storage'):local.configure(f[0],'CURRENT_OWNER')
    with pytest.raises(Denied,match='explicit CURRENT_OWNER'):local.configure(f[0],'AUTOMATIC')
    with f[1].connect() as c:
        assert not c.execute("SELECT 1 FROM information_schema.columns WHERE table_name='preparations' AND column_name=%s",(local.COLUMN,)).fetchone()
    with pytest.raises(Denied,match='issued Linux fixture'):Store(f[1].dsn).migrate_local_resource_approval_fixture()


def test_real_local_producer_consumer_cold_history_and_exact_once(local_fixture):
    f,bridge,p,hs,data=setup(local_fixture)
    before=read(f,p).json();assert before['revision']==0 and not before['items']  # ADOPT is not Approval.
    assert submit(f,p,data).status_code==409 and effects(f)==[0]*5
    item,x=approved(f,p,data);key=uuid4().hex;actual={**data,'approval_id':item['id']}
    result=submit(f,p,actual,key);assert result.status_code==201,result.text
    result=result.json();assert result['receipt']['plan_approval']['scope']==local.SCOPE
    assert result['independent_check']['status']=='CURRENT' and effects(f)==[1,3,1,1,1]
    assert states(f,hs)==['CONFIRMED']*3 and ledger(f,p)['revision']==3
    assert recover(f,p,key).json()['receipt']==result['receipt']
    assert submit(f,p,actual,key).json()['receipt']==result['receipt']
    assert submit(f,p,actual).status_code==409
    cold_store=Store(f[0].dsn);cold=local.LocalResourceApproval(cold_store);cold.attach_store(cold_store)
    value=cold.read(cold_store,f[2]['fixture-a'],UUID(p['preparation_id']))
    assert value['items'][0]['state']=='CONSUMED' and not value['items'][0]['current_available']
    with f[1].connect() as c:
        parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
        assert parent.get(core.COL) is None and local.ledger(parent)[1][item['id']]['state']=='CONSUMED'
        core.verify_receipt(parent,result['receipt'],link_revision=1)
        damaged=deepcopy(result['receipt']);del damaged['plan_approval']
        with pytest.raises(Conflict,match='local approval receipt reference missing'):core.verify_receipt(parent,damaged)
    assert not result['case_goal_completed'] and result['formal_approval']=='NOT_IMPLEMENTED'


def test_explicit_revoke_keeps_history_and_never_releases_or_confirms(local_fixture):
    f,_,p,hs,data=setup(local_fixture);item,x=approved(f,p,data);prefix=deepcopy(ledger(f,p)['events'])
    response=decide(f,p,item,x['revision'],'REVOKE');assert response.status_code==200,response.text
    assert response.json()['items'][0]['state']=='REVOKED' and ledger(f,p)['events'][:2]==prefix
    assert submit(f,p,{**data,'approval_id':item['id']}).status_code==409
    assert effects(f)==[0]*5 and states(f,hs)==['HELD']*3


@pytest.mark.parametrize('change',['source','materials','plan','resource','grant','read','execute','prepare','expiry'])
def test_changed_source_authority_or_expiry_cannot_consume(local_fixture,change):
    f,_,p,hs,data=setup(local_fixture);item,_=approved(f,p,data)
    with f[1].connect() as c:
        if change=='source':c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{revision}','2')")
        elif change=='materials':c.execute('UPDATE preparations SET revision=revision+1 WHERE id=%s',(p['preparation_id'],))
        elif change=='plan':c.execute("UPDATE preparations SET service_case_plan=jsonb_set(service_case_plan,'{revision}',to_jsonb((service_case_plan->>'revision')::int+1)) WHERE id=%s",(p['preparation_id'],))
        elif change=='resource':c.execute('UPDATE synthetic_resources SET revision=revision+1 WHERE id=%s',(hs[0]['resource_id'],))
        elif change=='grant':c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a'")
        elif change=='read':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
        elif change=='execute':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
        elif change=='prepare':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
        else:c.execute("UPDATE synthetic_resource_holds SET expires_at=clock_timestamp()-interval '1 second',created_at=clock_timestamp()-interval '1 hour' WHERE id=%s",(hs[0]['id'],))
    response=submit(f,p,{**data,'approval_id':item['id']});assert response.status_code in (403,409),response.text
    assert effects(f)==[0]*5 and ledger(f,p)['revision']==2


def test_consume_exception_rolls_back_decision_capacity_association_and_receipt(local_fixture,monkeypatch):
    f,bridge,p,hs,data=setup(local_fixture);item,_=approved(f,p,data);original=bridge.consume
    def fail(*args,**kwargs):original(*args,**kwargs);raise RuntimeError('controlled after local consume')
    monkeypatch.setattr(bridge,'consume',fail)
    with pytest.raises(RuntimeError,match='controlled after local consume'):submit(f,p,{**data,'approval_id':item['id']})
    assert ledger(f,p)['revision']==2 and effects(f)==[0]*5 and states(f,hs)==['HELD']*3


def test_revoke_consume_race_has_one_atomic_winner(local_fixture):
    f,bridge,p,hs,data=setup(local_fixture);item,x=approved(f,p,data)
    actual=delivery.Deliver.model_validate({**data,'approval_id':item['id']})
    revoke=core.Command(action='REVOKE',approval_id=item['id'],expected_revision=x['revision'],expected_binding_sha256=item['binding_sha256'],reason='explicit local revoke')
    def run(fn):
        try:fn();return 'COMMITTED'
        except Conflict:return 'CONFLICT'
    with ThreadPoolExecutor(2) as pool:
        a=pool.submit(run,lambda:bridge.command(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,revoke))
        b=pool.submit(run,lambda:delivery.deliver(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,actual))
        assert sorted([a.result(10),b.result(10)])==['COMMITTED','CONFLICT']
    state=read(f,p).json()['items'][0]['state'];assert state in ('CONSUMED','REVOKED')
    assert effects(f)==([1,3,1,1,1] if state=='CONSUMED' else [0]*5)
    assert ledger(f,p)['revision']==3


def test_ledger_prefix_is_database_immutable_and_other_identity_cannot_decide(local_fixture):
    f,_,p,_,data=setup(local_fixture);item,x=approved(f,p,data)
    assert decide(f,p,item,x['revision'],user='fixture-b').status_code==403
    with pytest.raises(psycopg.Error,match='candidate Approval'):
        with f[1].connect() as c:c.execute('UPDATE preparations SET local_resource_approvals=NULL WHERE id=%s',(p['preparation_id'],))
    assert ledger(f,p)['revision']==2


def test_actual_ui_local_scope_label_and_foreign_namespace_rejection():
    import json,subprocess
    result=subprocess.run(['node','tests/plan_reapproval_client_probes.js','local_scope'],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['checks']==3


def test_fresh_owned_launcher_explicit_storage_and_configured_consumer(tmp_path):
    import json,subprocess
    from test_ordinary_synthetic_demo import command,environment,server,ROOT
    result=subprocess.run(command('setup','--with-local-catalog','--with-local-resource-approval'),cwd=ROOT,env=environment(),capture_output=True,text=True,timeout=45)
    (tmp_path/'setup.stdout').write_text(result.stdout);(tmp_path/'setup.stderr').write_text(result.stderr)
    assert result.returncode==0,result.stderr
    from pathlib import Path
    state=Path(json.loads(result.stdout.splitlines()[-1])['state_dir'])
    marker=json.loads((state/'state.json').read_text());assert marker['local_resource_approval'] is True
    sessions=json.loads((state/'sessions.json').read_text())
    with server(state,tmp_path/'serve',local_demo_config=state/'local-demo/config.json') as (api,ready):
        from scripts.ordinary_synthetic_demo import SCOPES
        token=sessions[SCOPES['primary']['sessions']['enterprise']]
        response=api.get('/api/plan-approval/status',headers={'Authorization':'Bearer '+token})
        assert response.status_code==200,response.text
        status=response.json();assert status['enabled'] is True and status['approval_scope']==local.SCOPE
        assert status['source_reapproval_enabled'] is True
        assert all(status[k] is False for k in ('plan_replacement_enabled','production_execution_enabled','formal_release'))
        from test_ordinary_synthetic_demo import prepare_case,verify,call
        from test_local_demo_case_step_chain import selected_html
        tokens={actor:sessions[key] for actor,key in SCOPES['primary']['sessions'].items()}
        p,_=prepare_case(api,tokens,'本地资源明确批准')
        selected_html(api,tokens,p,tmp_path/'selected-plan')
        verify(api,tokens,p,'P1');base='/api/preparations/'+p['preparation_id']
        from datetime import datetime,timedelta,timezone
        now=datetime.now(timezone.utc);holds=[]
        resources=SCOPES['primary']['resources']
        for i in range(3):
            resource=resources[i%2]['id']
            hold=call(api,tokens,'/api/synthetic-resources/'+resource+'/holds',dict(starts_at=(now+timedelta(hours=1+3*i)).isoformat(),ends_at=(now+timedelta(hours=2+3*i)).isoformat(),quantity=1,expected_revision=1,ttl_seconds=120,purpose='SYNTHETIC local explicit capacity'),expected=201)['hold']
            holds.append(dict(hold_id=hold['id'],expected_revision=hold['resource_revision']))
        quote=call(api,tokens,base+'/resource-delivery/preview',dict(members=holds))
        assert quote['synthetic_plan_approval_required'] is True
        data=dict(members=holds,expected_preparation_revision=quote['expected_preparation_revision'],expected_plan_revision=quote['expected_plan_revision'],expected_source_sha256=quote['source_sha256'],valid_until=quote['valid_until'],reason='SYNTHETIC explicit local resource delivery')
        proposed=call(api,tokens,base+'/plan-approval/proposals',dict(expected_revision=0,delivery=data),expected=201)
        item=proposed['items'][0];decided=call(api,tokens,base+'/plan-approval/commands',dict(action='APPROVE',approval_id=item['id'],expected_revision=proposed['revision'],expected_binding_sha256=item['binding_sha256'],reason='SYNTHETIC original owner local APPROVE'))
        assert decided['items'][0]['current_available'] is True
        delivered=call(api,tokens,base+'/resource-delivery',{**data,'approval_id':item['id']},expected=201)
        assert delivered['receipt']['plan_approval']['scope']==local.SCOPE and delivered['independent_check']['status']=='CURRENT'
        assert call(api,tokens,base+'/plan-approval')['items'][0]['state']=='CONSUMED'
        verify(api,tokens,p,'P2')
    assert not (state/'data/postmaster.pid').exists()


def test_corrupt_local_head_never_downgrades_a_missing_proof_to_legacy():
    parent={local.COLUMN:None,local.HEAD:dict(revision=1,sha256='a'*64)}
    with pytest.raises(Conflict,match='original head required'):core.verify_receipt(parent,{},link_revision=1)
    core.verify_receipt({local.COLUMN:None,local.HEAD:None},{},link_revision=1)


def cold_without_local_approval(f,consumer,monkeypatch):
    """Same existing database, new application object; no runtime local mode."""
    if consumer=='new-store':
        from parkweave.case_step_assignments import OrdinaryCaseStepAssignments
        cold=Store(f[0].dsn)
        return create_app(cold,case_step_assignments=OrdinaryCaseStepAssignments(cold))
    from parkweave.api import configured_app
    from test_ordinary_case_steps import CONFIGS
    for name in CONFIGS:monkeypatch.delenv(name,raising=False)
    monkeypatch.delenv('PARKWEAVE_LOCAL_RESOURCE_APPROVAL_MODE',raising=False)
    monkeypatch.setenv('PARKWEAVE_DSN',f[0].dsn);monkeypatch.setenv('PARKWEAVE_MODE','LOCAL')
    monkeypatch.setenv('PARKWEAVE_CASE_STEP_MODE','CURRENT_PREPARATION')
    return configured_app()


def enter_local_state(f,p,data,state):
    x=propose(f,p,data);assert x.status_code==201,x.text
    x=x.json();item=x['items'][0]
    if state!='PROPOSED':
        x=decide(f,p,item,x['revision']);assert x.status_code==200,x.text
        x=x.json();item=x['items'][0]
    if state=='REVOKED':
        x=decide(f,p,item,x['revision'],'REVOKE');assert x.status_code==200,x.text
    return item


@pytest.mark.parametrize('state',['PROPOSED','APPROVED','REVOKED'])
@pytest.mark.parametrize('consumer',['new-store','configured-app'])
def test_entered_local_case_cannot_downgrade_after_cold_missing_mode(local_fixture,monkeypatch,state,consumer):
    f,_,p,hs,data=setup(local_fixture);enter_local_state(f,p,data,state)
    original=deepcopy(ledger(f,p));app=cold_without_local_approval(f,consumer,monkeypatch)
    with TestClient(app) as api:
        fresh=(*f[:3],api)
        response=submit(fresh,p,data)  # Intentionally omit approval_id.
        import os,json
        from pathlib import Path
        evidence=os.environ.get('PARKWEAVE_LOCAL_APPROVAL_DOWNGRADE_EVIDENCE')
        if evidence:
            out=Path(evidence);out.mkdir(parents=True,exist_ok=True)
            (out/(consumer+'-'+state+'.json')).write_text(json.dumps(dict(state=state,consumer=consumer,http_status=response.status_code,
                effects=effects(f),hold_states=states(f,hs),receipt_has_plan_approval=bool(response.json().get('receipt',{}).get('plan_approval')),
                ledger_unchanged=ledger(f,p)==original),indent=2)+'\n')
        assert response.status_code==403,response.text
        assert response.json()=={'detail':'record unavailable or authorization denied'}
        preview=api.post('/api/preparations/'+p['preparation_id']+'/resource-delivery/preview',headers=headers(f[2]),json=dict(members=data['members']))
        assert preview.status_code==403,preview.text
    assert ledger(f,p)==original and effects(f)==[0]*5 and states(f,hs)==['HELD']*3


@pytest.mark.parametrize('state',['PROPOSED','APPROVED','REVOKED','CONSUMED'])
def test_any_entered_local_history_requires_exact_local_proof(local_fixture,state):
    f,_,p,_,data=setup(local_fixture);item=enter_local_state(f,p,data,state)
    if state=='CONSUMED':assert submit(f,p,{**data,'approval_id':item['id']}).status_code==201
    with f[1].connect() as c:parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
    for proof in (None,dict(scope=core.SCOPE),dict(scope='UNKNOWN')):
        receipt=dict(combination_id=str(uuid4()))
        if proof is not None:receipt['plan_approval']=proof
        with pytest.raises(Conflict,match='local approval receipt reference missing'):
            core.verify_receipt(parent,receipt,link_revision=1)
    broken=deepcopy(parent);broken[local.COLUMN]=None
    with pytest.raises(Conflict,match='original head required'):
        delivery._approval(Store(f[0].dsn),broken)


@pytest.mark.parametrize('consumer',['new-store','configured-app'])
def test_unentered_legacy_case_in_same_database_keeps_original_delivery(local_fixture,monkeypatch,consumer):
    f,_,enrolled,_,enrolled_data=setup(local_fixture)
    enter_local_state(f,enrolled,enrolled_data,'PROPOSED');original=deepcopy(ledger(f,enrolled))
    p=start(f,goals=[GOALS[1]]);verified(f,p,'P1');hs,members=bundle(f);data=quoted(f,p,members)
    assert ledger(f,p) is None
    with TestClient(cold_without_local_approval(f,consumer,monkeypatch)) as api:
        fresh=(*f[:3],api);key=uuid4().hex
        result=submit(fresh,p,data,key);assert result.status_code==201,result.text
        assert result.json()['receipt'].get('plan_approval') is None
        assert recover(fresh,p,key).json()['receipt']==result.json()['receipt']
    assert ledger(f,enrolled)==original and ledger(f,p) is None and states(f,hs)==['CONFIRMED']*3


@pytest.mark.parametrize('consumer',['new-store','configured-app'])
def test_consumed_local_original_receipt_survives_cold_missing_mode(local_fixture,monkeypatch,consumer):
    f,_,p,hs,data=setup(local_fixture);item=enter_local_state(f,p,data,'APPROVED')
    key=uuid4().hex;actual={**data,'approval_id':item['id']}
    result=submit(f,p,actual,key);assert result.status_code==201,result.text
    receipt=result.json()['receipt'];original=deepcopy(ledger(f,p));before=effects(f)
    with TestClient(cold_without_local_approval(f,consumer,monkeypatch)) as api:
        fresh=(*f[:3],api)
        recovered=recover(fresh,p,key);assert recovered.status_code==200,recovered.text
        assert recovered.json()['receipt']==receipt
        repeated=submit(fresh,p,actual,key);assert repeated.status_code==201,repeated.text
        assert repeated.json()['receipt']==receipt
        assert submit(fresh,p,data).status_code==403
    assert ledger(f,p)==original and effects(f)==before and states(f,hs)==['CONFIRMED']*3


@pytest.mark.parametrize('state',['PROPOSED','APPROVED','REVOKED'])
def test_same_database_actual_api_restart_without_local_mode_is_closed(local_fixture,tmp_path,monkeypatch,state):
    import json
    import ordinary_case_step_support as support
    f,_,p,hs,data=setup(local_fixture);original_environment=support.environment
    with monkeypatch.context() as patch:
        patch.setattr(support,'environment',lambda fixture:{**original_environment(fixture),'PARKWEAVE_LOCAL_RESOURCE_APPROVAL_MODE':'CURRENT_OWNER'})
        with support.ordinary_api(f,tmp_path/'warm') as api:
            fresh=(*f[:3],api)
            status=api.get('/api/plan-approval/status',headers=headers(f[2])).json()
            assert status['enabled'] and status['approval_scope']==local.SCOPE
            enter_local_state(fresh,p,data,state)
    original=deepcopy(ledger(f,p))
    with support.ordinary_api(f,tmp_path/'cold') as api:
        fresh=(*f[:3],api)
        assert api.get('/api/plan-approval/status',headers=headers(f[2])).json()['enabled'] is False
        result=submit(fresh,p,data);assert result.status_code==403,result.text
        preview=api.post('/api/preparations/'+p['preparation_id']+'/resource-delivery/preview',headers=headers(f[2]),json=dict(members=data['members']))
        assert preview.status_code==403,preview.text
    warm=json.loads((tmp_path/'warm/process.json').read_text());cold=json.loads((tmp_path/'cold/process.json').read_text())
    assert warm[0]['api_pid']!=cold[0]['api_pid']
    assert warm[-1]['owned_child_exit'] is not None and cold[-1]['owned_child_exit'] is not None
    assert ledger(f,p)==original and effects(f)==[0]*5 and states(f,hs)==['HELD']*3
