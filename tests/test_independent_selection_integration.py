from uuid import UUID,uuid4
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from pathlib import Path
import json,sqlite3
import pytest
from parkweave import service_selection_candidates as sc,service_case_steps as steps,service_plan_candidates as legacy
from parkweave.store import Conflict
from parkweave.template_candidate import Command,TemplateEngine
from test_service_capability_catalog_actual import capability_catalog
from test_preparation import preparation_fixture,headers
from test_service_selection_candidates import arrangement,run,planner
from test_proposal_planner_offline import planner as echo_planner,echo_handler
from service_release_acceptance_support import wait_for_pg_blocker


def adoption(v):
    return steps.Adopt(expected_preparation_revision=v['preparation_revision'],expected_request_revision=v['request_revision'],expected_source_sha256=v['current_source_sha256'],expected_plan_revision=0,required_goals=v['required_goals'],reason='SYNTHETIC independent explicit original selection adoption',candidate_id=v['candidate_id'],expected_candidate_sha256=v['candidate_sha256'],expected_verification_sha256=v['verification_sha256'])


def generate(a):
    f,p,data,_=arrangement(a);f[0]._isolated_service_capability_catalog=a['catalog']
    v=run(a,f,p,data,uuid4().hex,planner([]))
    return f,p,v,adoption(v)


def withdrawal(a,engine):
    x=engine.read('template-publisher',a['scope'])
    return Command.model_validate(dict(action='WITHDRAW',expected_revision=x['revision'],expected_definition_sha256=x['definition_sha256'],reason='SYNTHETIC independent original source withdrawal'))


def test_mixed_v3_v4_legacy_read_and_adopt_do_not_require_new_source_lease(capability_catalog,monkeypatch):
    a=capability_catalog;f,p,data,_=arrangement(a);store=f[0];store._isolated_service_capability_catalog=a['catalog']
    x=f[3].get('/api/preparations/'+p['preparation_id']+'/planning-preview',headers=headers(f[2])).json()['current']
    old=legacy.generate(store,f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,legacy.bp.Capture(expected_preparation_revision=p['revision'],expected_source_sha256=x['source_sha256']),planner=echo_planner(echo_handler([])))
    v4=run(a,f,p,data,uuid4().hex,planner([]))
    read=legacy.read(store,f[2]['fixture-a'],UUID(p['preparation_id']))
    assert [i['candidate_id'] for i in read['items']]==[old['candidate_id']]
    assert sc.read(store,f[2]['fixture-a'],UUID(p['preparation_id']),catalog=a['catalog'])['items'][0]['candidate_id']==v4['candidate_id']
    @contextmanager
    def unavailable():
        raise AssertionError('Legacy adoption acquired new capability source lease')
        yield
    monkeypatch.setattr(a['catalog'],'source_lease',unavailable)
    view=steps.adopt(store,f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,adoption(old))
    assert view['candidate_consumption']['verification_basis']['validator_version']==3


def test_v4_new_adoption_refuses_withdrawal_and_original_key_stays_cold_readable(capability_catalog):
    a=capability_catalog;f,p,v,data=generate(a)
    a['engine'].command('template-publisher',a['scope'],uuid4().hex,withdrawal(a,a['engine']))
    with pytest.raises(Conflict):steps.adopt(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,data)
    cold=sc.read(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),candidate_id=v['candidate_id'],catalog=a['catalog'])
    assert cold['candidate_id']==v['candidate_id'] and not cold['can_adopt']
    with f[1].connect() as c:assert c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan'] is None


def test_v4_adoption_save_failure_rolls_back_plan_and_event(capability_catalog,monkeypatch):
    a=capability_catalog;f,p,v,data=generate(a)
    def fail(*args,**kwargs):raise RuntimeError('SYNTHETIC independent original plan event failure')
    monkeypatch.setattr(steps,'_save',fail)
    with pytest.raises(RuntimeError,match='event failure'):steps.adopt(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,data)
    with f[1].connect() as c:assert c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan'] is None
    assert sc.read(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),candidate_id=v['candidate_id'],catalog=a['catalog'])['can_adopt']


def test_actual_adoption_parent_wait_holds_original_source_lease_until_commit(capability_catalog,monkeypatch):
    a=capability_catalog;f,p,v,data=generate(a);entered=Event();proceed=Event();original=a['catalog'].source_lease
    @contextmanager
    def held():
        with original() as connection:
            entered.set();assert proceed.wait(5)
            yield connection
    monkeypatch.setattr(a['catalog'],'source_lease',held)
    second=TemplateEngine(a['engine'].config,a['engine'].repository,a['engine'].clock);cmd=withdrawal(a,second)
    with ThreadPoolExecutor(max_workers=2) as pool:
        future=pool.submit(steps.adopt,f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,data)
        assert entered.wait(5)
        with f[1].connect() as blocker:
            blocker.execute('SELECT id FROM preparations WHERE id=%s FOR UPDATE',(p['preparation_id'],));pid=blocker.execute('SELECT pg_backend_pid() pid').fetchone()['pid']
            proceed.set();waiters=wait_for_pg_blocker(f[1],pid)
            with sqlite3.connect(a['engine'].repository.path,timeout=0) as probe:
                with pytest.raises(sqlite3.OperationalError,match='locked'):probe.execute('BEGIN IMMEDIATE')
            withdraw=pool.submit(second.command,'template-publisher',a['scope'],uuid4().hex,cmd)
            assert not future.done() and not withdraw.done()
            Path('.runtime/service-capability-selection-20261014/adopt-source-pg-wait.json').write_text(json.dumps(dict(blocker_pid=pid,waiters=waiters,sqlite_source_gate_locked=True,withdrawal_pending=True),indent=2)+'\n')
        assert future.result(timeout=5)['candidate_consumption']['verification_basis']['validator_version']==4
        assert withdraw.result(timeout=5)['state']=='WITHDRAWN'


def test_adopted_v4_frozen_goal_trace_survives_current_registry_revision_change(capability_catalog,monkeypatch):
    from copy import deepcopy
    from test_plan_preview import digest
    from parkweave import bounded_planning as bp,case_goal_results
    a=capability_catalog;f,p,v,data=generate(a)
    plan=steps.adopt(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,data)
    initial=case_goal_results.read(f[0],f[2]['fixture-a'],UUID(p['preparation_id']))
    with f[1].connect() as c:row=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
    trace=case_goal_results.source_trace(row,row['service_case_plan'])
    registry=deepcopy(bp.REGISTRY);registry[0]['revision']=2
    monkeypatch.setattr(bp,'REGISTRY',registry)
    before=digest(f)
    reply=f[3].get('/api/preparations/'+p['preparation_id']+'/goal-results',headers=headers(f[2]))
    assert reply.status_code==200,reply.text
    current=reply.json()
    assert current['source_trace']==initial['source_trace']==trace
    assert 'REGISTRY_CHANGED' in current['binding_issues']
    assert digest(f)==before
    candidate=sc.read(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),candidate_id=v['candidate_id'],catalog=a['catalog'])
    assert not candidate['can_adopt']
    with pytest.raises(Conflict):steps.adopt(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,data)
    view=steps.read(f[0],f[2]['fixture-a'],UUID(p['preparation_id']))
    command=steps.Command(action='VERIFY',step_id=view['steps'][0]['id'],expected_revision=view['revision'],expected_source_sha256=view['steps'][0]['source_sha256'],reason='SYNTHETIC current registry cannot verify historical adapter')
    with pytest.raises(Conflict):steps.command(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,command)
