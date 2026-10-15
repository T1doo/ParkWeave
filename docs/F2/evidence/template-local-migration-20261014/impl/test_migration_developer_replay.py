"""Independent original AT25–27 oracles against owned PG and original ASGI.

Expected impact is literal, never copied from the implementation's impact output.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID, uuid4
from pathlib import Path
import json
import pytest

from test_template_upgrade import (upgrade_case, publication, instance, confirmed, check, choose,
                                  snapshot, plan_read, plan_command, adopt, adopt_body, verified,
                                  accepted, receipt_act, headers, GOALS)
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture

ALL = ('P1', 'P2', 'P3', 'P4', 'P5')


@pytest.fixture(autouse=True)
def private_fixture_sessions(upgrade_case):
    p=Path('.runtime/template-migration-tests-20261014/redaction-values.private.json')
    p.parent.mkdir(parents=True,exist_ok=True)
    values=json.loads(p.read_text()) if p.exists() else []
    values=sorted(set(values)|set(upgrade_case['f'][2].values()))
    p.write_text(json.dumps(values));p.chmod(0o600)


def stored(u, row):
    with u['f'][1].connect() as c:
        return c.execute('SELECT service_case_plan FROM preparations WHERE id=%s', (row['preparation_id'],)).fetchone()['service_case_plan']


def facts(u):
    with u['f'][1].connect() as c:
        # Preparations is the one coordination row intentionally changed by Apply;
        # all actual business facts and every permission table remain byte-identical.
        tables = [r['tablename'] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename NOT IN ('authorization_audit','preparations') ORDER BY tablename")]
        return {t:c.execute('SELECT * FROM '+t+' ORDER BY to_jsonb('+t+')::text').fetchall() for t in tables}


def full(u):
    row, old = instance(u, [GOALS[-1]])
    p = confirmed(u, row)
    # Fixture premise only: original synthetic actors' existing roles need this
    # newly created Run assignment. Runtime upgrade must never add permissions.
    with u['f'][1].connect() as c:
        for actor in ('prep-specialist-fixture-a', 'executor-a'):
            c.execute('INSERT INTO run_assignments(run_id,principal_id,park_id,org_id) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING', (row['run_id'],actor,'park-a','org-a'))
    current=plan_read(u['f'],p).json()
    assert adopt(u['f'],p,{**adopt_body(u['f'],p),'expected_plan_revision':current['revision'],'local_revision':True}).status_code==201
    group, dispatch=accepted(u['f'],p);verified(u['f'],p,'P3')
    receipt=u['f'][3].get('/api/executor-receipts/'+dispatch['receipt_step_id'],headers=headers(u['f'][2],'executor-a')).json()
    receipt=receipt_act(u['f'],receipt,'SUBMIT').json();receipt=receipt_act(u['f'],receipt,'ACKNOWLEDGE').json();verified(u['f'],p,'P4')
    from test_case_lifecycle import read as lr, act as la
    assert la(u['f'],p,lr(u['f'],p).json(),'REVALIDATE').status_code==200
    verified(u['f'],p,'P5')
    return row, old, p


def admit(u,row,target,choice='REQUEST_RECHECK'):
    x=check(u,row,target);assert x.status_code==200,x.text
    x=x.json();r=choose(u,row,x,choice);assert r.status_code==200,r.text
    # A second pure read supplies current application CAS, not a new decision.
    view=check(u,row,target);assert view.status_code==200,view.text
    v=view.json();a=v['application'];event=r.json()['event']
    data=dict(expected_instance_id=row['instance_id'],target_release_id=target['release_id'],
              expected_target_sha256=target['release_sha256'],expected_check_sha256=v['check_sha256'],
              expected_choice_revision=event['revision'],expected_choice_event_sha256=event['event_sha256'],
              expected_plan_id=a['plan_id'],expected_plan_revision=a['plan_revision'],
              expected_preparation_revision=a['preparation_revision'],expected_source_sha256=a['source_sha256'],
              reason='SYNTHETIC independent explicit template execution adoption')
    return v,data


def apply(u,row,data,key=None,user='fixture-a'):
    return u['client'].post('/api/template-upgrade/'+row['instance_id']+'/apply',headers=headers(u['f'][2],user,key or uuid4().hex),json=data)


def recovery(u,row,key,user='fixture-a'):
    return u['client'].get('/api/template-upgrade/'+row['instance_id']+'/apply-requests/'+key,headers=headers(u['f'][2],user))


def assert_preserved(old,new,before,after):
    assert before==after, 'business effects, histories or authority unexpectedly changed'
    assert new['id']==old['id']
    assert [s['id'] for s in new['steps']]==[s['id'] for s in old['steps']]
    assert [s['contract'] for s in new['steps']]==[s['contract'] for s in old['steps']]
    assert new['events'][:len(old['events'])]==old['events']
    assert new.get('history',[])==old.get('history',[])
    for a,b in zip(old['steps'],new['steps']):
        assert a['verified_sha256']==b['verified_sha256'] and a['verified_sources']==b['verified_sources']


@pytest.mark.parametrize('source,affected', [('1',()),('2',ALL)])
def test_independent_actual_effects_stable_ids_and_exact_reverify(upgrade_case,source,affected):
    u=upgrade_case;row,old_release,p=full(u);old=deepcopy(stored(u,row));before=facts(u)
    binding=deepcopy(u['consumer'].read(u['f'][2]['fixture-a'],row['instance_id'])['binding']) if 'binding' in row else None
    target=publication(u,[GOALS[-1]],source,'Independent compatible version')
    v,data=admit(u,row,target)
    ids={s['adapter_id']:s['id'] for s in old['steps']}
    assert set(v['application']['affected'])=={ids[a] for a in affected}
    assert set(v['application']['preserved'])=={ids[a] for a in ALL if a not in affected}
    r=apply(u,row,data,'independent-main');assert r.status_code in (200,201),r.text
    new=stored(u,row);assert_preserved(old,new,before,facts(u))
    assert new['revision']==old['revision']+1 and new['events'][-1]['action']=='TEMPLATE_UPGRADE'
    view=plan_read(u['f'],p);assert view.status_code==200,view.text
    states={s['adapter_id']:s['state'] for s in view.json()['steps']}
    if affected:
        assert all(states[a]!='VERIFIED' for a in affected)
        for a in ALL:verified(u['f'],p,a)
        assert all(s['state']=='VERIFIED' for s in plan_read(u['f'],p).json()['steps'])
    else:
        assert new['steps']==old['steps'] and all(states[a]=='VERIFIED' for a in ALL)
    assert facts(u)==before
    # No hidden rewrite of original consumer binding or old release snapshot.
    with u['consumer'].repository.connect() as c:
        inst=c.execute('SELECT * FROM consumer_instances WHERE id=?',(row['instance_id'],)).fetchone()
        assert old_release['release_id'] in inst['binding'] and target['release_id'] not in inst['binding']
    saved=deepcopy(stored(u,row));before=snapshot(u)
    assert recovery(u,row,'independent-main').json()['status']=='COMMITTED'
    assert snapshot(u)==before and stored(u,row)==saved


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a'])
def test_independent_current_owner_and_tenant_gate(upgrade_case,user):
    u=upgrade_case;row,_=instance(u);confirmed(u,row);target=publication(u,source='2');_,data=admit(u,row,target)
    before=snapshot(u);r=apply(u,row,data,user=user)
    assert r.status_code==403 and snapshot(u)==before
    assert recovery(u,row,'unseen-key',user).status_code==403


@pytest.mark.parametrize('cap',['READ','PREPARE','EXECUTE'])
def test_independent_revocation_before_send_and_recovery(upgrade_case,cap):
    u=upgrade_case;row,_=instance(u);confirmed(u,row);target=publication(u,source='2');_,data=admit(u,row,target)
    with u['f'][1].connect() as c:
        u['f'][1].lock_principal(c,'fixture-a',exclusive=True)
        table='preparation_grants' if cap=='PREPARE' else 'capability_grants'
        c.execute('UPDATE '+table+" SET active=false WHERE principal_id='fixture-a' AND capability=%s",(cap,))
    before=snapshot(u);assert apply(u,row,data).status_code==403
    assert recovery(u,row,'unseen-key').status_code==403 and snapshot(u)==before


@pytest.mark.parametrize('same_key',[True,False])
def test_independent_real_concurrent_cas_and_fingerprint(upgrade_case,same_key):
    u=upgrade_case;row,_=instance(u);confirmed(u,row);target=publication(u,source='2');_,data=admit(u,row,target)
    old=deepcopy(stored(u,row));before=facts(u)
    keys=['independent-same','independent-same' if same_key else 'independent-other']
    with ThreadPoolExecutor(2) as pool:rs=list(pool.map(lambda k:apply(u,row,data,k),keys))
    codes=sorted(r.status_code for r in rs)
    assert codes in ([200,200],[201,201]) if same_key else codes in ([200,409],[201,409]),[r.text for r in rs]
    new=stored(u,row);assert new['revision']==old['revision']+1
    assert_preserved(old,new,before,facts(u))
    winner=next(k for k,r in zip(keys,rs) if r.status_code in (200,201))
    assert apply(u,row,{**data,'reason':'SYNTHETIC changed body'},winner).status_code==409
    assert recovery(u,row,winner).json()['status']=='COMMITTED'
    if not same_key:
        loser=next(k for k,r in zip(keys,rs) if r.status_code==409)
        assert recovery(u,row,loser).json()['status']=='NOT_OBSERVED'


def test_independent_lock_conflict_then_original_unlock(upgrade_case):
    u=upgrade_case;row,_=instance(u);p=confirmed(u,row);verified(u['f'],p,'P1')
    view=plan_read(u['f'],p).json();s=view['steps'][0]
    assert plan_command(u['f'],p,'P1','LOCK',row=view,expected_source_sha256=s['source_sha256']).status_code==200
    target=publication(u,source='2');x=check(u,row,target).json()
    assert x['check']['classification']=='LOCK_CONFLICT'
    assert choose(u,row,x,'REQUEST_RECHECK').status_code==409
    old=deepcopy(stored(u,row));before=facts(u)
    assert old['steps'][0]['manual_lock'] and facts(u)==before
    assert plan_command(u['f'],p,'P1','UNLOCK').status_code==200
    _,data=admit(u,row,target);assert apply(u,row,data).status_code in (200,201)
    assert stored(u,row)['steps'][0]['id']==old['steps'][0]['id'] and facts(u)==before


@pytest.mark.parametrize('action',['withdraw','expire','supersede'])
def test_independent_target_invalid_after_confirm_refuses_atomically(upgrade_case,action):
    u=upgrade_case;row,_=instance(u);confirmed(u,row);target=publication(u,source='2');_,data=admit(u,row,target)
    if action=='expire':u['engine'].clock=lambda:datetime(2100,1,1,tzinfo=timezone.utc)
    elif action=='supersede':publication(u,source='3')
    else:
        from parkweave.template_candidate import Command
        view=u['engine'].read('template-publisher',u['scope'])
        u['engine'].command('template-publisher',u['scope'],uuid4().hex,Command.model_validate(dict(action='WITHDRAW',expected_revision=view['revision'],expected_definition_sha256=view['definition_sha256'],reason='SYNTHETIC independent withdraw')))
    before=snapshot(u);r=apply(u,row,data)
    assert r.status_code in (403,409),r.text
    assert snapshot(u)==before and recovery(u,row,'independent-absent').json()['status']=='NOT_OBSERVED'


def test_independent_added_goal_refuses_execution_preserving_old_plan(upgrade_case):
    u=upgrade_case;row,_=instance(u);confirmed(u,row);target=publication(u,GOALS[:2]);v,data=admit(u,row,target)
    before=snapshot(u);r=apply(u,row,data)
    assert r.status_code==409,r.text
    assert 'UPGRADE_SCOPE_UNSUPPORTED' in r.text and snapshot(u)==before


def test_independent_pg_event_failure_rolls_back_entire_application(upgrade_case,monkeypatch):
    from fastapi.testclient import TestClient
    from parkweave import service_case_steps as plans
    u=upgrade_case;row,_=instance(u);confirmed(u,row);target=publication(u,source='2');_,data=admit(u,row,target)
    old=deepcopy(stored(u,row));before=snapshot(u);original=plans._save
    def fail_after_save(*args,**kwargs):
        original(*args,**kwargs)
        raise RuntimeError('SYNTHETIC independent transaction failure after actual UPDATE')
    monkeypatch.setattr(plans,'_save',fail_after_save)
    with TestClient(u['client'].app,raise_server_exceptions=False) as client:
        r=client.post('/api/template-upgrade/'+row['instance_id']+'/apply',headers=headers(u['f'][2],key='independent-event-fault'),json=data)
    assert r.status_code in (500,503),r.text
    assert snapshot(u)==before and stored(u,row)==old
    assert recovery(u,row,'independent-event-fault').json()['status']=='NOT_OBSERVED'


def test_independent_committed_lost_reply_only_get_and_cold_original_key(upgrade_case,monkeypatch):
    from fastapi.testclient import TestClient
    from parkweave.template_upgrade import TemplateUpgradeChecker
    u=upgrade_case;row,_=instance(u);confirmed(u,row);target=publication(u,source='2');_,data=admit(u,row,target)
    original=u['checker'].apply;calls=[]
    def committed_lost(*args,**kwargs):
        result=original(*args,**kwargs);calls.append(result)
        raise RuntimeError('SYNTHETIC independent committed response lost')
    monkeypatch.setattr(u['checker'],'apply',committed_lost)
    with TestClient(u['client'].app,raise_server_exceptions=False) as client:
        r=client.post('/api/template-upgrade/'+row['instance_id']+'/apply',headers=headers(u['f'][2],key='independent-lost'),json=data)
    assert r.status_code in (500,503),r.text
    assert len(calls)==1
    before=snapshot(u)
    def forbidden(*args,**kwargs):raise AssertionError('GET must never resend Apply')
    monkeypatch.setattr(u['checker'],'apply',forbidden)
    r=recovery(u,row,'independent-lost');assert r.status_code==200,r.text
    assert r.json()['status']=='COMMITTED' and snapshot(u)==before
    cold=TemplateUpgradeChecker(u['consumer'],u['repository'],enabled_for_isolated_tests=True)
    result=cold.recover_application(u['f'][2]['fixture-a'],UUID(row['instance_id']),'independent-lost')
    assert result['status']=='COMMITTED' and snapshot(u)==before and len(calls)==1


def test_independent_multihop_uses_effective_release_and_preserves_locked_decision(upgrade_case):
    u=upgrade_case;row,v1,p=full(u)
    v2=publication(u,[GOALS[-1]],'2','Independent v2 source revision')
    _,data2=admit(u,row,v2);r2=apply(u,row,data2,'independent-v2');assert r2.status_code in (200,201),r2.text
    for adapter in ALL:verified(u['f'],p,adapter)
    view=plan_read(u['f'],p).json();s=next(s for s in view['steps'] if s['adapter_id']=='P1')
    assert plan_command(u['f'],p,'P1','LOCK',row=view,expected_source_sha256=s['source_sha256']).status_code==200
    old=deepcopy(stored(u,row));before=facts(u)
    v3=publication(u,[GOALS[-1]],'2','Independent v3 description only')
    x=check(u,row,v3);assert x.status_code==200,x.text
    assert x.json()['check']['classification']=='COMPATIBLE'
    v,data3=admit(u,row,v3,'ACK_COMPATIBLE')
    assert v['application']['affected']==[]
    assert set(v['application']['preserved'])=={s['id'] for s in old['steps']}
    r3=apply(u,row,data3,'independent-v3');assert r3.status_code in (200,201),r3.text
    new=stored(u,row);assert_preserved(old,new,before,facts(u));assert new['steps']==old['steps']
    previous=recovery(u,row,'independent-v2');assert previous.status_code==200,previous.text
    assert previous.json()['status']=='COMMITTED' and previous.json()['effective_release_id']==v2['release_id']
    for target in (v1,v2):
        original=snapshot(u);r=check(u,row,target)
        assert r.status_code in (403,409),r.text
        assert snapshot(u)==original


def test_independent_old_code_read_never_reverses_already_happened_business(upgrade_case,tmp_path):
    import io,os,subprocess,tarfile
    u=upgrade_case;row,_,p=full(u);target=publication(u,[GOALS[-1]],'2');_,data=admit(u,row,target)
    r=apply(u,row,data,'independent-before-code-rollback');assert r.status_code in (200,201),r.text
    before=facts(u)
    # Read original unmodified baseline source against the very same owned DB.
    # No checkout mutation, deployment, schema or business command occurs.
    archive=subprocess.run(['git','archive','adf867156fcf0b22d15a18007cf8fa3fc65f34a2','src'],capture_output=True,check=True).stdout
    old=tmp_path/'old-code';old.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive)) as t:t.extractall(old,filter='data')
    script="""import json,sys
from uuid import UUID
from parkweave.store import Store,Conflict,Denied
from parkweave import service_case_steps
x=json.load(sys.stdin)
try:
 service_case_steps.read(Store(x['dsn']),x['token'],UUID(x['preparation_id']))
 print(json.dumps({'status':200}))
except (Conflict,Denied) as e:
 print(json.dumps({'status':409 if isinstance(e,Conflict) else 403}))
"""
    env=os.environ.copy();env['PYTHONPATH']=str(old/'src')
    probe=subprocess.run([os.sys.executable,'-c',script],input=json.dumps(dict(dsn=u['f'][0].dsn,token=u['f'][2]['fixture-a'],preparation_id=row['preparation_id'])),text=True,capture_output=True,env=env)
    assert probe.returncode==0, 'old-code reader failed without a bounded original refusal'
    assert json.loads(probe.stdout)['status'] in (200,403,409)
    assert facts(u)==before, 'code rollback reversed already happened business facts'
