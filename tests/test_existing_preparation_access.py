"""Reviewed administrator code, exercised only in newly owned SYNTHETIC databases."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
import hashlib,json,os,secrets,subprocess,sys,time
import psycopg
import pytest
from parkweave import cli,preparation as prep,catalog_publication
from parkweave.preparation_access_configuration import Configuration,ExistingPreparationAccess,load,SCOPE
from parkweave.process_env import minimal_environment
from parkweave.store import Store,Conflict,Denied,digest
from test_preparation import preparation_fixture,headers
from test_executor_receipts import receipt_fixture
from test_ordinary_case_steps import ordinary
from test_case_step_assignments import prepared,ok,REVIEWER
from test_service_dispatches import offer,command as dispatch_command,read as dispatch
from ordinary_case_step_support import ordinary_api

ROOT=Path(__file__).resolve().parents[1]
OWNER='configured-owner';REVIEWER_ID='configured-reviewer'
TABLES=('principals','capability_grants','action_grants','field_grants','preparation_catalog',
        'preparation_grants','authorization_audit','runs','operations','cases','run_assignments',
        'preparations','preparation_events','preparation_evidence')


def data(owner=OWNER,reviewer=REVIEWER_ID):
    return dict(version=1,scope=SCOPE,park_id='park-a',org_id='org-a',owner_id=owner,reviewer_id=reviewer,
        catalog=dict(service_id=prep.SERVICE,version=1),reason='SYNTHETIC explicit administrator configuration')


def fingerprint(owner,tables=TABLES):
    with owner.connect() as c:
        rows={t:sorted((r['value'] for r in c.execute('SELECT row_to_json(t) value FROM public.'+t+' t')),key=lambda r:json.dumps(r,sort_keys=True,default=str)) for t in tables}
    return hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest()


def counts(owner):
    with owner.connect() as c:
        return [c.execute('SELECT count(*) n FROM public.'+t).fetchone()['n'] for t in ('preparation_grants','authorization_audit')]


@pytest.fixture
def configuration_fixture(fixture,tmp_path):
    app,owner,tokens,api=fixture;tokens=dict(tokens)
    # An already-existing synthetic directory. Product code never creates these
    # identities, capability/action grants, catalogue or credentials.
    with owner.connect() as c:
        for id,role,caps in ((OWNER,'enterprise_operator',('READ','EXECUTE')),(REVIEWER_ID,'park_specialist',('READ',))):
            tokens[id]=secrets.token_urlsafe(32)
            c.execute('INSERT INTO principals VALUES(%s,%s,%s,%s,%s,true)',(id,digest(tokens[id]),'park-a','org-a',role))
            for cap in caps:c.execute('INSERT INTO capability_grants(principal_id,capability,park_id,org_id) VALUES(%s,%s,%s,%s)',(id,cap,'park-a','org-a'))
        c.execute("INSERT INTO action_grants(principal_id,action,park_id,org_id) VALUES(%s,'case.create','park-a','org-a')",(OWNER,))
        from psycopg.types.json import Jsonb
        c.execute('INSERT INTO preparation_catalog VALUES(%s,%s,1,%s,%s,%s,%s)',('park-a',prep.SERVICE,'SYNTHETIC existing directory',Jsonb(dict(kind='SYNTHETIC',id='existing-directory-fixture',revision='1')),'SYNTHETIC','NOT_EVALUATED'))
    config=Configuration(**data());path=tmp_path/'已有配置 空格.json';path.write_text(json.dumps(data(),ensure_ascii=False),encoding='utf-8')
    return (app,owner,tokens,api),ExistingPreparationAccess(Store(owner.dsn)),config,path


def test_default_dry_run_is_read_only_then_explicit_two_grants_and_no_change(configuration_fixture):
    f,manager,config,path=configuration_fixture
    before=fingerprint(f[1]);owner=manager.preview(config)
    application=ExistingPreparationAccess(Store(f[0].dsn)).preview(load(path))
    assert application['plan_sha256']==owner['plan_sha256']
    assert application['read_only'] and not application['administrator_connection']
    assert owner['status']=='READY_TO_APPLY' and owner['administrator_connection']
    assert {r['capability'] for r in owner['changes']}=={'PREPARE','REVIEW_ASSIGNED'}
    assert fingerprint(f[1])==before and counts(f[1])==[0,0]
    protected=tuple(t for t in TABLES if t not in ('preparation_grants','authorization_audit'));stable=fingerprint(f[1],protected)
    applied=manager.apply(config,owner['plan_sha256']);assert applied['status']=='APPLIED' and not applied['read_only']
    assert len(applied['applied'])==2 and counts(f[1])==[2,2] and fingerprint(f[1],protected)==stable
    with f[1].connect() as c:
        assert {r['principal_id'] for r in c.execute('SELECT principal_id FROM authorization_audit')}=={OWNER,REVIEWER_ID}
        assert all(r['outcome']=='ALLOWED' and owner['plan_sha256'] in r['category'] for r in c.execute('SELECT * FROM authorization_audit'))
    with pytest.raises(Conflict):manager.apply(config,owner['plan_sha256'])
    current=manager.preview(config);before=fingerprint(f[1]);assert current['status']=='NO_CHANGE'
    assert manager.apply(config,current['plan_sha256'])['status']=='NO_CHANGE' and fingerprint(f[1])==before


def test_read_only_transaction_rejects_an_injected_write(configuration_fixture,monkeypatch):
    f,manager,config,_=configuration_fixture;before=fingerprint(f[1]);original=manager._snapshot
    def injected(c,data):
        result=original(c,data);manager.store.audit(c,OWNER,'SYNTHETIC_READONLY_NEGATIVE','ALLOWED');return result
    monkeypatch.setattr(manager,'_snapshot',injected)
    with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):manager.preview(config)
    assert fingerprint(f[1])==before


@pytest.mark.parametrize('change',['missing_owner','wrong_org','wrong_role','inactive_reviewer','missing_read','missing_execute','missing_catalog','source_unknown','inactive_grant','wrong_grant_scope'])
def test_existing_prerequisites_block_and_are_never_repaired(configuration_fixture,change):
    f,manager,config,_=configuration_fixture
    with f[1].connect() as c:
        if change=='missing_owner':config=Configuration(**dict(data(),owner_id='not-present'))
        elif change=='wrong_org':config=Configuration(**dict(data(),org_id='org-b'))
        elif change=='wrong_role':c.execute("UPDATE principals SET role='resource_admin' WHERE id=%s",(REVIEWER_ID,))
        elif change=='inactive_reviewer':c.execute('UPDATE principals SET active=false WHERE id=%s',(REVIEWER_ID,))
        elif change in ('missing_read','missing_execute'):c.execute('UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability=%s',(OWNER,'READ' if change=='missing_read' else 'EXECUTE'))
        elif change=='missing_catalog':c.execute('DELETE FROM preparation_catalog')
        elif change=='source_unknown':c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{kind}',to_jsonb('FORMAL'::text))")
        else:c.execute('INSERT INTO preparation_grants(principal_id,park_id,org_id,capability,active) VALUES(%s,%s,%s,%s,%s)',(OWNER,'park-b' if change=='wrong_grant_scope' else 'park-a','org-a','PREPARE',change!='inactive_grant'))
    before=fingerprint(f[1]);view=manager.preview(config);assert view['status']=='BLOCKED' and view['issues']
    with pytest.raises(Conflict):manager.apply(config,view['plan_sha256'])
    assert fingerprint(f[1])==before


def test_application_connection_cannot_apply_even_with_a_correct_preview(configuration_fixture):
    f,manager,config,_=configuration_fixture;before=fingerprint(f[1]);sha=manager.preview(config)['plan_sha256']
    with pytest.raises(Denied):ExistingPreparationAccess(Store(f[0].dsn)).apply(config,sha)
    assert fingerprint(f[1])==before


def test_audit_failure_rolls_back_both_grants_and_first_audit(configuration_fixture,monkeypatch):
    f,manager,config,_=configuration_fixture;sha=manager.preview(config)['plan_sha256'];before=fingerprint(f[1]);original=manager.store.audit
    def fail(c,id,category,outcome):
        if id==REVIEWER_ID:raise RuntimeError('SYNTHETIC second audit failure')
        original(c,id,category,outcome)
    monkeypatch.setattr(manager.store,'audit',fail)
    with pytest.raises(RuntimeError):manager.apply(config,sha)
    assert fingerprint(f[1])==before and counts(f[1])==[0,0]


def test_after_commit_error_requires_fresh_preview_without_automatic_replay(configuration_fixture,monkeypatch,capsys):
    f,manager,config,path=configuration_fixture;sha=manager.preview(config)['plan_sha256'];original=Store.connect
    @contextmanager
    def after_real_commit(self):
        with original(self) as c:yield c
        raise psycopg.OperationalError('SYNTHETIC after-commit connection error; private input omitted')
    with monkeypatch.context() as patch:
        patch.setattr(Store,'connect',after_real_commit)
        patch.setenv('PARKWEAVE_DSN',f[1].dsn)
        patch.setattr(sys,'argv',['parkweave.cli','prepare-access','--config',str(path),'--apply','--expected-plan-sha256',sha])
        with pytest.raises(SystemExit) as e:cli.main()
        output=capsys.readouterr()
        assert e.value.code==2 and not output.out and 'result not confirmed' in output.err
        assert 'after-commit' not in output.err and 'rollback' not in output.err.lower()
    assert counts(f[1])==[2,2] and manager.preview(config)['status']=='NO_CHANGE'


@pytest.mark.parametrize('change',['capability_revoke','capability_aba','catalog_aba'])
def test_actual_owner_lock_wait_rechecks_current_generation(configuration_fixture,change,tmp_path):
    f,manager,config,_=configuration_fixture;sha=manager.preview(config)['plan_sha256'];proof=dict(change=change,actual_pg_wait=False)
    with f[1].connect() as lock:
        if change=='catalog_aba':
            catalog_publication.lock(lock,('park-a',prep.SERVICE,1),exclusive=True)
            lock.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{revision}',to_jsonb('2'::text))")
            lock.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{revision}',to_jsonb('1'::text))")
        else:
            f[1].lock_principal(lock,REVIEWER_ID,exclusive=True)
            lock.execute("UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability='READ'",(REVIEWER_ID,))
            if change=='capability_aba':lock.execute("UPDATE capability_grants SET active=true WHERE principal_id=%s AND capability='READ'",(REVIEWER_ID,))
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(manager.apply,config,sha)
            try:
                for _ in range(80):
                    with f[1].connect() as c:
                        row=c.execute("SELECT clock_timestamp() now,query,wait_event FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE 'SELECT pg_advisory_xact_lock%%'").fetchone()
                    if row:proof.update(actual_pg_wait=True,observation={k:str(v) for k,v in row.items()});break
                    if future.done():break
                    time.sleep(.01)
                assert proof['actual_pg_wait']
            finally:lock.commit()
            with pytest.raises(Conflict):future.result(timeout=10)
    assert counts(f[1])==[0,0] and manager.preview(config)['plan_sha256']!=sha
    proof.update(result='CONFLICT',grant_and_audit_counts=[0,0],old_sha_rejected=True)
    (tmp_path/'administrator-wait-proof.json').write_text(json.dumps(proof,indent=2)+'\n')


@pytest.mark.parametrize('provider',['_native_run_access','_isolated_plan_approval','_ordinary_case_step_sources'])
def test_application_or_provider_store_is_not_an_administrator_context(provider):
    store=Store('not-a-dsn');setattr(store,provider,object())
    with pytest.raises(Denied):ExistingPreparationAccess(store)


@pytest.mark.parametrize('malformed',['credential','duplicate','boolean_version','wrong_scope','arbitrary_permissions','oversized','encoding','blank_reason'])
def test_strict_config_and_cli_do_not_echo_input_or_open_database(tmp_path,monkeypatch,capsys,malformed):
    private='SYNTHETIC_PRIVATE_INPUT_TOKEN_VALUE';value=data()
    if malformed=='credential':value['token']=private
    elif malformed=='boolean_version':value['version']=True
    elif malformed=='wrong_scope':value['scope']=private
    elif malformed=='arbitrary_permissions':value['permissions']=['EXECUTE']
    elif malformed=='blank_reason':value['reason']=' '
    raw=json.dumps(value).encode()
    if malformed=='duplicate':raw=raw[:-1]+(',"owner_id":"'+private+'"}').encode()
    elif malformed=='oversized':raw=b' '*8193
    elif malformed=='encoding':raw=b'\xff'+private.encode()
    path=tmp_path/'config.json';path.write_bytes(raw)
    monkeypatch.setenv('PARKWEAVE_DSN','not-a-dsn')
    def fail(*args,**kwargs):raise AssertionError('database must not be opened')
    monkeypatch.setattr(Store,'connect',fail);monkeypatch.setattr(sys,'argv',['parkweave.cli','prepare-access','--config',str(path)])
    with pytest.raises(SystemExit) as e:cli.main()
    assert e.value.code==2 and private not in capsys.readouterr().err


@pytest.mark.parametrize('arguments',[['seed-synthetic','--config',''],['prepare-access','--config','x','--apply'],['prepare-access','--config','x','--expected-plan-sha256',''],['prepare-access','--config','x','--principal','other']])
def test_cli_apply_is_explicit_and_new_flags_cannot_trigger_old_setup(tmp_path,monkeypatch,arguments):
    monkeypatch.chdir(tmp_path);monkeypatch.delenv('PARKWEAVE_DSN',raising=False);monkeypatch.setattr(sys,'argv',['parkweave.cli',*arguments])
    with pytest.raises(SystemExit) as e:cli.main()
    assert e.value.code==2 and not (tmp_path/'.runtime').exists()


def run_cli(f,path,directory,*arguments,owner=False):
    directory.mkdir(parents=True,exist_ok=True)
    env=minimal_environment(os.environ,PYTHONPATH=str(ROOT/'src'),PARKWEAVE_DSN=f[1 if owner else 0].dsn,PARKWEAVE_MODE='LOCAL',PYTHONDONTWRITEBYTECODE='1')
    result=subprocess.run([sys.executable,'-B','-m','parkweave.cli','prepare-access','--config',str(path),*arguments],cwd=ROOT,env=env,text=True,capture_output=True,timeout=15)
    (directory/'cli.stdout').write_text(result.stdout);(directory/'cli.stderr').write_text(result.stderr)
    assert result.returncode==0,result.stderr
    return json.loads(result.stdout)


def test_normal_cli_dry_apply_original_preparation_and_cold_api(configuration_fixture,tmp_path):
    f,manager,config,path=configuration_fixture;immutable=tuple(t for t in TABLES if t not in ('preparation_grants','authorization_audit','runs','operations','cases','preparations','preparation_events','preparation_evidence'));before=fingerprint(f[1],immutable)
    with ordinary_api(f,tmp_path/'first-api') as api:
        assert api.get('/api/preparation-catalog',headers=headers(f[2],OWNER)).status_code==403
        counts_before=counts(f[1]);preview=run_cli(f,path,tmp_path/'dry-run');assert preview['status']=='READY_TO_APPLY' and preview['read_only']
        assert counts(f[1])==counts_before
        applied=run_cli(f,path,tmp_path/'explicit-apply','--apply','--expected-plan-sha256',preview['plan_sha256'],owner=True)
        assert applied['status']=='APPLIED' and len(applied['applied'])==2
        run=ok(api.post('/api/runs',headers=headers(f[2],OWNER,uuid4().hex),json=dict(goal='SYNTHETIC existing configured user')),202)['run_id']
        f[0].finish(f[0].claim('SYNTHETIC existing-directory-user'))
        p=ok(api.post('/api/preparations',headers=headers(f[2],OWNER,uuid4().hex),json=dict(run_id=run,service_id=prep.SERVICE,service_version=1,reviewer_id=REVIEWER_ID)),201)
        for slot in prep.SLOTS:
            p=ok(api.post('/api/preparations/'+p['preparation_id']+'/commands',headers=headers(f[2],OWNER,uuid4().hex),json=dict(action='ADD_EVIDENCE',expected_revision=p['revision'],slot=slot,text='SYNTHETIC original explicit '+slot,source_kind='USER_STATEMENT',source_label='SYNTHETIC existing user')))
        for user,action in ((REVIEWER_ID,'REVIEW'),(OWNER,'CONFIRM')):
            p=ok(api.post('/api/preparations/'+p['preparation_id']+'/commands',headers=headers(f[2],user,uuid4().hex),json=dict(action=action,expected_revision=p['revision'],reason='SYNTHETIC independent '+action)))
        first=ok(api.get('/api/preparations/'+p['preparation_id'],headers=headers(f[2],OWNER)))
        assert first['preparation']['state']=='LOCAL_CONFIRMED'
    with ordinary_api(f,tmp_path/'cold-api') as api:
        cold=ok(api.get('/api/preparations/'+p['preparation_id'],headers=headers(f[2],OWNER)));assert cold==first
        assert api.get('/api/preparations/'+p['preparation_id'],headers=headers(f[2],'fixture-b')).status_code==403
    assert fingerprint(f[1],immutable)==before
    (tmp_path/'configuration-business-chain.json').write_text(json.dumps(dict(api_processes=2,cli_processes=2,worker_processes=0,
        test_fixture_finish=True,state=first['preparation']['state'],new_real_authority=False,plan_sha256=preview['plan_sha256'],grants_inserted=2),indent=2)+'\n')


def test_configuration_insert_cannot_revive_an_old_case_step_generation(ordinary):
    f,_=ordinary;p=prepared(f);d=ok(offer(f,p)[0],201)
    with f[1].connect() as c:c.execute("DELETE FROM preparation_grants WHERE principal_id='fixture-a' AND capability='PREPARE'")
    manager=ExistingPreparationAccess(Store(f[1].dsn));config=Configuration(**data('fixture-a',REVIEWER));preview=manager.preview(config)
    applied=manager.apply(config,preview['plan_sha256']);assert len(applied['applied'])==1
    ok(dispatch_command(f,d,'ACCEPT'),403)
    historical=ok(dispatch(f,d,'fixture-a'));assert historical['assignment_valid_until']==d['assignment_valid_until']
    with f[1].connect() as c:assert not c.execute('SELECT 1 FROM run_assignments').fetchone()
