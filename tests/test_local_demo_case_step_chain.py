"""Existing pinned demo inputs -> ordinary worker -> original P1–P5 -> cold read.

Fresh owned SYNTHETIC setup and input file construction are test preparation,
outside the product's read-only loader. No Run assignment or model fixture.
"""
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import json,subprocess
import pytest
from fastapi.testclient import TestClient
from parkweave import local_synthetic_demo as catalog,case_step_assignments as cs
from parkweave.api import create_app
from parkweave.store import Store,Denied
from parkweave.ordinary_runtime_read import catalog_hash
from test_ordinary_synthetic_demo import demo_state,server,prepare_case,complete,call,html,demo,ROOT
from test_local_synthetic_demo import demo_inputs,write,receipt_fixture,preparation_fixture,prepared,headers


def existing_inputs(p,directory):
    directory.mkdir()
    with demo.lifecycle.postgres(p):
        with Store(demo.lifecycle.dsn(p,application=True)).connect() as c:
            c.execute('SET TRANSACTION READ ONLY')
            now=c.execute('SELECT clock_timestamp() t').fetchone()['t'];database=catalog.database_binding(c)
            row=c.execute('SELECT service_id,version,name,source,namespace,qualification,xmin::text row_generation FROM preparation_catalog WHERE park_id=%s AND service_id=%s AND version=1',(demo.PARK,'synthetic-material-preparation')).fetchone()
    generation=row.pop('row_generation')
    value=dict(schema_version='parkweave-local-synthetic-demo-pack/1',kind='SYNTHETIC',id='local-demo-ordinary-chain',revision=1,
        validity=dict(valid_from=(now-timedelta(days=1)).isoformat(),valid_until=(now+timedelta(days=1)).isoformat(),timezone='UTC'),
        park_id=demo.PARK,org_id=demo.ORG,
        roles=dict(enterprise_operator=demo.IDS['enterprise'],park_specialist=demo.IDS['specialist'],service_executor=demo.IDS['executor']),
        resources={key:row['id'] for key,row in zip(('primary','secondary'),demo.SCOPES['primary']['resources'])},
        fields={slot:dict(slot=slot,input_field='demo_'+slot) for slot in ('need_summary','material_outline')},services=list(catalog.contract.SERVICE_GOALS))
    pack=directory/'pack.json';journal=directory/'journal.json'
    pack_sha=write(pack,value)
    cfg=dict(schema_version='parkweave-local-synthetic-demo-config/1',pack_path=str(pack),pack_sha256=pack_sha,
        journal_path=str(journal),database=database,catalog_sha256=catalog_hash(row),catalog_generation=generation)
    cfg['journal_sha256']=write(journal,dict(schema_version='parkweave-local-synthetic-demo-journal/1',kind='SYNTHETIC',pack_sha256=pack_sha,
        database=database,park_id=demo.PARK,org_id=demo.ORG,catalog_sha256=cfg['catalog_sha256'],catalog_generation=generation))
    journal.chmod(0o600);config=directory/'config.json';write(config,cfg)
    return config


def selected_html(api,tokens,p,directory):
    directory.mkdir();config=dict(base=str(api.base_url).rstrip('/'),preparation_id=p['preparation_id'],tokens=dict(owner=tokens['enterprise']))
    result=subprocess.run(['node','tests/local_demo_case_step_chain_html.js'],cwd=ROOT,input=json.dumps(config)+'\n',text=True,capture_output=True,timeout=60)
    (directory/'html.stdout').write_text(result.stdout);(directory/'html.stderr').write_text(result.stderr)
    assert result.returncode==0,result.stderr
    return json.loads(result.stdout.splitlines()[-1])


def test_existing_catalog_selection_original_ordinary_chain_and_physical_cold_restart(demo_state,tmp_path):
    p,marker,tokens=demo_state;config=existing_inputs(p,tmp_path/'existing-inputs')
    files=[p/'state.json',p/'sessions.json',config,config.parent/'pack.json',config.parent/'journal.json']
    before={str(path):sha256(path.read_bytes()).hexdigest() for path in files}
    with server(p,tmp_path/'first-start',local_demo_config=config) as (api,first):
        with Store(demo.lifecycle.dsn(p)).connect() as c:
            c.execute('SET TRANSACTION READ ONLY');assert demo.authority(c)==marker['authority']
            assert all(c.execute('SELECT count(*) n FROM '+table).fetchone()['n']==0 for table in ('runs','cases','preparations','run_assignments'))
        case,_=prepare_case(api,tokens,'目录选择后直接办理')
        selection=selected_html(api,tokens,case,tmp_path/'selection-html')
        dispatch,results=complete(api,tokens,case,'selected catalog')
        base='/api/preparations/'+case['preparation_id'];candidate=selection['candidate']
        assert results['source_trace']['candidate']['producer']['mode']=='NO_MODEL'
        assert results['source_trace']['service_selection']['profile']==catalog.PROFILE
        # Reads after ACCEPT must retain the ordinary managed transaction guard.
        capabilities=call(api,tokens,base+'/service-capabilities');assert capabilities['profile']==catalog.PROFILE
        pack=html((None,None,{'fixture-a':tokens['enterprise'],'executor-a':tokens['executor']},api),tmp_path/'first-pack',case,results['plan_id'],'LOCAL_OUTPUTS_VERIFIED',goal_count=5)
        original_plan=call(api,tokens,base+'/service-case-plan')
    with server(p,tmp_path/'cold-start',local_demo_config=config) as (api,cold):
        assert all(cold[key]!=first[key] for key in ('postgres_pid','api_pid','worker_pid'))
        assert call(api,tokens,base+'/goal-results')==results
        assert call(api,tokens,base+'/service-case-plan')==original_plan
        response=api.get(base+'/service-selections/recovery',headers={'Authorization':'Bearer '+tokens['enterprise'],'Idempotency-Key':selection['selection_key']})
        assert response.status_code==200,response.text
        recovered=response.json();assert recovered['status']=='COMMITTED' and recovered['items'][0]['candidate_id']==candidate['candidate_id']
        assert recovered['items'][0]['producer']==candidate['producer']
        assert call(api,tokens,'/api/service-dispatches/'+dispatch['dispatch_id'])['assignment_valid_until']==dispatch['assignment_valid_until']
        html((None,None,{'fixture-a':tokens['enterprise'],'executor-a':tokens['executor']},api),tmp_path/'cold-pack',case,results['plan_id'],'LOCAL_OUTPUTS_VERIFIED',goal_count=5)
        assert (tmp_path/'first-pack/download.txt').read_bytes()==(tmp_path/'cold-pack/download.txt').read_bytes()
        assert call(api,tokens,base+'/service-capabilities')['profile']==catalog.PROFILE
        with Store(demo.lifecycle.dsn(p)).connect() as c:
            c.execute('SET TRANSACTION READ ONLY');assert demo.authority(c)==marker['authority']
            assert not c.execute('SELECT 1 FROM run_assignments').fetchone()
            assert c.execute('SELECT count(*) n FROM cases').fetchone()['n']==1
            assert c.execute('SELECT count(*) n FROM case_local_events').fetchone()['n']==2
    assert {str(path):sha256(path.read_bytes()).hexdigest() for path in files}==before
    (tmp_path/'actual-chain.json').write_text(json.dumps(dict(mode=cs.LOCAL_DEMO_MODE,profile=catalog.PROFILE,
        ordinary_worker=True,case_count=1,run_assignments=0,authority_unchanged=True,input_hashes_unchanged=True,
        original_html_selection_adoption=True,adapters=['P1','P2','P3','P4','P5'],result_state=results['state'],result_count=5,
        real_model_calls=0,physical_pg_api_worker_restart=True,cold_plan_results_equal=True,cold_txt_equal=True,
        deadline_unchanged=True,pack_sha256=pack['pack_sha256'],browser=False,Windows=False,formal_AT=False,real_business=False),indent=2)+'\n')


def test_exact_pair_preserves_old_mode_and_all_other_provider_guards(demo_inputs):
    f,cfg,_,_=demo_inputs;store=Store(f[0].dsn)
    env=dict(PARKWEAVE_CASE_STEP_MODE=cs.LOCAL_DEMO_MODE,PARKWEAVE_SERVICE_PROFILE=catalog.PROFILE,PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG=json.dumps(cfg))
    for change in ({'PARKWEAVE_CASE_STEP_MODE':cs.ORDINARY_MODE},{'PARKWEAVE_SERVICE_PROFILE':None},{'PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG':None},
            *({key:'{}'} for key in ('PARKWEAVE_RUNTIME_READ_CONFIG','PARKWEAVE_RUNTIME_WRITE_CONFIG','PARKWEAVE_FORMAL_PREPARATION_READ_CONFIG','PARKWEAVE_RESOURCE_APPROVAL_READ_CONFIG'))):
        with pytest.raises(Denied):cs.from_environment(store,env|change)
    ordinary=cs.OrdinaryCaseStepAssignments(store);provider=catalog.configure(store,catalog.PROFILE,json.dumps(cfg))
    with pytest.raises(Denied):create_app(store,case_step_assignments=ordinary,local_synthetic_demo=provider)
    paired=cs.from_environment(store,env)
    create_app(store,case_step_assignments=paired,local_synthetic_demo=paired.local_synthetic_demo)
    with pytest.raises(Denied):
        with provider.catalog.connection():pass
    with pytest.raises(Denied):create_app(store,case_step_assignments=paired)
    with pytest.raises(Denied):create_app(store,case_step_assignments=paired,local_synthetic_demo=provider)
    for key in ('_native_run_access','_isolated_run_access','_isolated_plan_approval','_isolated_service_capability_catalog'):
        setattr(store,key,object())
        try:
            with pytest.raises(Denied):paired.validate(store)
        finally:delattr(store,key)
    store._local_synthetic_demo_catalog=provider.catalog
    with pytest.raises(Denied):paired.validate(store)


def test_pinned_inputs_rechecked_after_transaction_and_never_repaired(demo_inputs):
    f,cfg,_,_=demo_inputs;store=Store(f[0].dsn)
    paired=cs.from_environment(store,dict(PARKWEAVE_CASE_STEP_MODE=cs.LOCAL_DEMO_MODE,PARKWEAVE_SERVICE_PROFILE=catalog.PROFILE,PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG=json.dumps(cfg)))
    path=Path(cfg['pack_path']);raw=path.read_bytes()
    with pytest.raises(Denied):
        with paired._connection(store) as c:
            c.execute("INSERT INTO authorization_audit(id,principal_id,category,outcome) VALUES('bab18908-8bdc-483b-a2f4-83530547ac61','fixture-a','LOCAL_DEMO_ROLLBACK_TEST','DENIED')")
            path.write_bytes(raw+b' ')
    with f[1].connect() as c:
        c.execute('SET TRANSACTION READ ONLY')
        assert not c.execute("SELECT 1 FROM authorization_audit WHERE category='LOCAL_DEMO_ROLLBACK_TEST'").fetchone()
    assert path.read_bytes()==raw+b' '
    with pytest.raises(Denied):paired.validate(store)


@pytest.mark.parametrize('permission',['PREPARE','REVIEW_ASSIGNED'])
def test_combined_selection_rechecks_existing_current_permissions(demo_inputs,permission):
    f,cfg,_,_=demo_inputs;p=prepared(f);store=Store(f[0].dsn)
    service=cs.from_environment(store,dict(PARKWEAVE_CASE_STEP_MODE=cs.LOCAL_DEMO_MODE,PARKWEAVE_SERVICE_PROFILE=catalog.PROFILE,PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG=json.dumps(cfg)))
    base='/api/preparations/'+p['preparation_id']
    with TestClient(create_app(store,case_step_assignments=service,local_synthetic_demo=service.local_synthetic_demo)) as api:
        response=api.get(base+'/service-capabilities',headers=headers(f[2]));assert response.status_code==200,response.text
        current=response.json()
        with f[1].connect() as c:
            c.execute('UPDATE preparation_grants SET active=false WHERE principal_id=%s AND capability=%s',
                ('fixture-a' if permission=='PREPARE' else 'prep-specialist-fixture-a',permission))
        response=api.post(base+'/service-selections',headers=headers(f[2],key='missing-current-'+permission),json=dict(
            expected_preparation_revision=p['revision'],expected_source_sha256=current['source_sha256'],expected_capability_catalog_sha256=current['capability_catalog_sha256']))
        assert response.status_code==403,response.text
    with store.connect() as c:
        c.execute('SET TRANSACTION READ ONLY')
        assert c.execute('SELECT planning_previews FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['planning_previews'] in (None,[])
        assert not c.execute('SELECT 1 FROM service_dispatches').fetchone()


def test_combined_parent_and_executor_mapping_are_not_authority(demo_inputs):
    f,cfg,_,_=demo_inputs;p=prepared(f);store=Store(f[0].dsn)
    service=cs.from_environment(store,dict(PARKWEAVE_CASE_STEP_MODE=cs.LOCAL_DEMO_MODE,PARKWEAVE_SERVICE_PROFILE=catalog.PROFILE,PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG=json.dumps(cfg)))
    with service._connection(store) as c:
        with pytest.raises(Denied):service._context(c,p['preparation_id'],executor='unassigned')
    with f[1].connect() as c:
        c.execute('UPDATE preparations SET reviewer_id=%s WHERE id=%s',('prep-specialist-fixture-b',p['preparation_id']))
    with pytest.raises(Denied):
        with service._connection(store) as c:service._context(c,p['preparation_id'])
    with store.connect() as c:
        c.execute('SET TRANSACTION READ ONLY');assert not c.execute('SELECT 1 FROM service_dispatches').fetchone()
