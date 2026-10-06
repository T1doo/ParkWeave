"""Existing checkpoint hooks with aggregate timings and <=20 read-only DB samples."""
import threading
import time
import pytest
from .regression_progress import write,TIMINGS,DB_COUNTS

CLOCK=time.monotonic


class Progress:
    def __init__(self,config,*,clock=CLOCK):
        self.clock=clock;self.path=config.getoption('--parkweave-progress');self.started=self.clock();self.lock=threading.RLock()
        self.phase='pytest_collect';self.nodeid=None;self.phase_started=self.started;self.fixture_started=self.started
        self.values={**{k:0 for k in TIMINGS},'completed':0,'collected':0,'ordinal':0,'fixture_stage':'NONE','sample_attempts':0,'sample_state':'NOT_SAMPLED'}
        self.totals={'setup':0.0,'call':0.0,'teardown':0.0};self.stage_totals={}
        self.stop=threading.Event();self.thread=None;self.maintenance=None;self.sample_budget=0

    def publish(self):
        with self.lock:
            now=self.clock();values=dict(self.values);values['elapsed_ms']=int((now-self.started)*1000);values['phase_ms']=int((now-self.phase_started)*1000)
            values['fixture_ms']=int((now-self.fixture_started)*1000) if values['fixture_stage'] not in ('NONE','DONE') else 0
            for phase,total in self.totals.items():values[phase+'_ms']=int(total*1000)
            for stage,key in (('CREATE_DB','create_ms'),('MIGRATE','migrate_ms'),('SEED','seed_ms'),('GRANTS','grants_ms'),('DROP_DB','drop_ms')):values[key]=int(self.stage_totals.get(stage,0)*1000)
            write(self.path,self.phase,self.nodeid,telemetry=values)

    def mark(self,phase,nodeid=None):
        with self.lock:
            self.phase=phase;self.nodeid=nodeid;self.phase_started=self.clock();self.publish()

    def fixture_stage(self,stage):
        with self.lock:
            now=self.clock();before=self.values['fixture_stage']
            if before not in ('NONE','DONE'):self.stage_totals[before]=self.stage_totals.get(before,0)+now-self.fixture_started
            self.fixture_started=now;self.values['fixture_stage']=stage;self.publish()

    def sample(self):
        # Separate short maintenance connection; no locks/DSN changes on test connections.
        with self.lock:
            if self.maintenance is None or self.sample_budget>=20:return
            self.sample_budget+=1;dsn=self.maintenance
        before=self.clock();result={}
        try:
            from psycopg.conninfo import make_conninfo,conninfo_to_dict
            options=conninfo_to_dict(dsn).get('options','')+' -c statement_timeout=1000 -c lock_timeout=500'
            with self.connect(make_conninfo(dsn,connect_timeout=2,options=options),autocommit=True) as c:
                row=c.execute("SELECT count(*) FILTER(WHERE backend_type='client backend'),count(*) FILTER(WHERE backend_type='client backend' AND datname ~ '^fixture_[0-9a-f]{32}$'),count(*) FILTER(WHERE state='idle in transaction'),count(*) FILTER(WHERE wait_event_type='Lock'),count(*) FILTER(WHERE cardinality(pg_blocking_pids(pid))>0),(SELECT count(*) FROM pg_database WHERE datname ~ '^fixture_[0-9a-f]{32}$') FROM pg_stat_activity WHERE pid<>pg_backend_pid()").fetchone()
                if len(row)!=6 or any(type(v) is not int or not 0<=v<=10000 for v in row):raise ValueError('invalid count-only sample')
                result=dict(zip(('client_connections','fixture_connections','idle_txn','lock_waiters','blocked','fixture_databases'),row))
            state='AVAILABLE'
        except Exception:state='UNAVAILABLE'
        with self.lock:
            for key in DB_COUNTS:self.values.pop(key,None)
            self.values.update(result,sample_attempts=self.sample_budget,sample_state=state,sample_elapsed_ms=int((self.clock()-self.started)*1000),sample_cost_ms=int((self.clock()-before)*1000));self.publish()

    def report(self,report):
        with self.lock:
            self.totals[report.when]+=report.duration
            if report.when=='teardown':self.values['completed']+=1
            self.publish()

    def start_sampler(self,server):
        if self.path is None or self.thread is not None:return
        import psycopg
        self.maintenance=server.get_uri();self.connect=psycopg.connect
        def run():
            for _ in range(20):
                if self.stop.is_set():break
                self.sample()
                if self.stop.wait(30):break
        self.thread=threading.Thread(target=run,name='parkweave-bounded-db-observer',daemon=True);self.thread.start()


def state(config):return getattr(config,'_parkweave_progress',None)


def pytest_addoption(parser):parser.addoption('--parkweave-progress',default=None)


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    global _CURRENT
    session.config._parkweave_progress=Progress(session.config);_CURRENT=state(session.config);_CURRENT.publish()


def pytest_collection_finish(session):
    progress=state(session.config)
    if progress:
        progress.values['collected']=len(session.items);progress.publish()


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    progress=state(item.config)
    if progress:
        with progress.lock:
            progress.values['ordinal']+=1;progress.values['fixture_stage']='NONE';progress.fixture_started=progress.clock();progress.mark('pytest_setup',item.nodeid)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_call(item):
    progress=state(item.config)
    if progress:progress.mark('pytest_call',item.nodeid)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_teardown(item):
    progress=state(item.config)
    if progress:progress.mark('pytest_teardown',item.nodeid)


def pytest_runtest_logreport(report):
    # Report objects expose config indirectly only via the session's plugin state.
    progress=_CURRENT
    if progress:progress.report(report)


_CURRENT=None


@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(fixturedef,request):
    result=yield
    progress=state(request.config)
    if progress and fixturedef.argname=='pg' and result.excinfo is None:
        try:progress.start_sampler(result.get_result())
        except Exception:pass


def fixture_stage(request,stage):
    try:
        progress=state(request.config)
        if progress:progress.fixture_stage(stage)
    except Exception:pass


@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session):
    progress=state(session.config)
    if progress:
        progress.stop.set()
        if progress.thread:progress.thread.join(timeout=3.5)
        progress.mark('pytest_finish')
