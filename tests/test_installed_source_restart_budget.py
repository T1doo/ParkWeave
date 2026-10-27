"""Failure injection for cumulative restart budget and original error retention."""
from contextlib import nullcontext
import json,time
from pathlib import Path
from types import SimpleNamespace
import pytest
from scripts import local_source_restart_installed_browser_once as candidate


def fake_run(tmp_path):
    run=SimpleNamespace(private=tmp_path,harness=tmp_path,state=tmp_path/'state',python=Path('/unused/python'),started=time.monotonic(),report={})
    run.budget=SimpleNamespace(internal_reads=0)
    return run


def inject(monkeypatch,run,attempts,*,failed=False,observation=True):
    observed=[]
    class Child:
        pid=404
        def __init__(self,argv,**kwargs):
            self.returncode=1 if failed else None
            observed.append(int(argv[-2]));self.attempts=next(attempts)
            if not failed:
                value=dict(url='http://127.0.0.1:'+argv[-3],state_dir=str(run.state),api_pid=405,postgres_pid=406,readiness_attempts=self.attempts)
                kwargs['stdout'].write(json.dumps(value)+'\n');kwargs['stdout'].flush()
            if observation:(run.harness/'owned-processes.json').write_text(json.dumps(dict(wrapper_pid=self.pid,generation=argv[-1],state_dir=str(run.state),children=[dict(role='postgres',pid=406,exit_code=0),dict(role='api',pid=405,exit_code=0)],cleanup_errors=[],postgres_marker_absent=True,readiness_attempts=self.attempts)))
        def poll(self):return self.returncode
        def terminate(self):self.returncode=0
        def wait(self,timeout):return self.returncode
    monkeypatch.setattr(candidate.subprocess,'Popen',Child)
    monkeypatch.setattr(candidate.httpx,'Client',lambda **kw:nullcontext(SimpleNamespace()))
    return observed


def test_both_generations_receive_only_remaining_readiness(monkeypatch,tmp_path):
    run=fake_run(tmp_path);observed=inject(monkeypatch,run,iter([5,7]))
    with candidate.server(run,'first'):assert run.budget.internal_reads==5
    with candidate.server(run,'restarted'):assert run.budget.internal_reads==12
    assert observed==[40,35] and run.budget.internal_reads==12
    assert [g['readiness_cumulative'] for g in run.report['service_generations']]==[5,12]
    assert (tmp_path/'first-owned-processes.json').exists() and (tmp_path/'restarted-owned-processes.json').exists()


def test_startup_failure_counts_attempts_and_keeps_primary_and_cleanup(monkeypatch,tmp_path):
    run=fake_run(tmp_path);run.budget.internal_reads=9;observed=inject(monkeypatch,run,iter([3]),failed=True)
    with pytest.raises(BaseExceptionGroup) as error:
        with candidate.server(run,'restarted'):pytest.fail('startup failure yielded a server')
    assert len(error.value.exceptions)==2 and all(isinstance(x,AssertionError) for x in error.value.exceptions)
    generation=run.report['service_generations'][0]
    assert generation['primary_error']['message'].startswith('installed server exited before readiness')
    assert generation['wrapper_exit']==1 and 'cleanup_error' in generation
    assert run.budget.internal_reads==12 and observed==[31]


def test_late_cold_stage_fails_without_start_or_shortened_wait(monkeypatch):
    run=SimpleNamespace(started=0,report=dict(service_generations=[dict(API_listener_refused_after_stop=True)]))
    monkeypatch.setattr(candidate.time,'monotonic',lambda:150.001)
    with pytest.raises(AssertionError,match='270s work reservation'):candidate.cold_gate(run)


def test_restart_missing_new_observation_never_reuses_first(monkeypatch,tmp_path):
    run=fake_run(tmp_path);inject(monkeypatch,run,iter([5]))
    with candidate.server(run,'first'):pass
    original=(tmp_path/'first-owned-processes.json').read_bytes()
    inject(monkeypatch,run,iter([3]),failed=True,observation=False)
    with pytest.raises(BaseExceptionGroup):
        with candidate.server(run,'restarted'):pytest.fail('failed restart yielded')
    last=run.report['service_generations'][-1]
    assert last['readiness_unconfirmed']==dict(confirmed_before=5,unconfirmed_allowance=35)
    assert run.budget.internal_reads==5 and 'cleanup' not in last
    assert not (tmp_path/'owned-processes.json').exists()
    assert (tmp_path/'first-owned-processes.json').read_bytes()==original


@pytest.mark.parametrize('extra_close_error',[False,True])
def test_telemetry_failure_always_closes_context_and_preserves_all_errors(extra_close_error):
    from types import SimpleNamespace
    telemetry=RuntimeError('controlled telemetry failure');close=ValueError('controlled context close failure');body=AssertionError('controlled original body')
    calls=[]
    class Page:
        def evaluate(self,*a):raise telemetry
        def locator(self,*a):return None
        def screenshot(self,*a,**kw):pass
    class Context:
        def close(self):
            calls.append('CLOSE')
            if extra_close_error:raise close
    flow=candidate.Flow.__new__(candidate.Flow);flow.run=SimpleNamespace(public=Path('/tmp'),report={});flow.page=Page();flow.context=Context();flow.cold=True
    with pytest.raises(BaseExceptionGroup) as raised:flow.close(body)
    assert calls==['CLOSE']
    assert raised.value.exceptions==((body,telemetry,close) if extra_close_error else (body,telemetry))


@pytest.mark.parametrize('cold',[False,True])
@pytest.mark.parametrize('enabled',[True,False])
def test_history_navigation_reidentifies_through_visible_UI_or_stops(cold,enabled):
    """Controlled locator model: tab clear hides history until authorized reads."""
    events=[]
    class Page:
        identified=False
        case=None
        def locator(self,selector):return Control(selector,self)
        def wait_for_load_state(self,state,timeout):assert state=='networkidle' and timeout==30000
        def wait_for_function(self,expression,timeout):
            assert timeout==30000
            if 'bundleActor!==null' in expression:
                if not self.identified:raise TimeoutError('original resource identity unavailable')
            elif 'planApprovalView?.items.length===2' in expression:
                assert 'CONSUMED' in expression and events[-1]=='#plan-approval-read'
    class Control:
        def __init__(self,selector,page):self.selector=selector;self.page=page
        def visible(self):return self.selector!='#plan-approval-read' or self.page.identified
        def scroll_into_view_if_needed(self,timeout):assert timeout==15000 and self.visible(),'hidden native approval history'
        def click(self):
            events.append(self.selector)
            if self.selector=='[data-tab="resource"]':self.page.identified=False
            elif self.selector=='#resource-catalog':self.page.identified=enabled
            elif self.selector=='#plan-approval-read':assert self.page.identified and self.page.case=='original-case'
        def fill(self,value):assert self.selector=='#delivery-case';self.page.case=value
    class Expect:
        def __init__(self,control):self.control=control
        def to_be_visible(self):assert self.control.visible()
        def to_be_enabled(self):assert self.control.visible()
    flow=candidate.Flow.__new__(candidate.Flow);flow.page=Page();flow.expect=Expect;flow.cold=cold
    flow.run=SimpleNamespace(started=time.monotonic(),report={},record={'preparation_id':'original-case'})
    if enabled:
        flow.read_consumed_approvals()
        assert events==['[data-tab="resource"]','#resource-catalog','#plan-approval-read']
    else:
        with pytest.raises(TimeoutError,match='identity unavailable'):flow.read_consumed_approvals()
        assert events==['[data-tab="resource"]','#resource-catalog']
    assert flow.run.report['stage']==('RESTARTED_APPROVAL_HISTORY_READ' if cold else 'HOT_APPROVAL_HISTORY_READ')
