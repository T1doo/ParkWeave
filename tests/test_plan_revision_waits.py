"""Controlled waits in the last-recorded recovery path, not Windows root-cause proof."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import pytest
import psycopg
from psycopg.conninfo import make_conninfo
from test_plan_revision import bounded_recovery_sql,oracle,get
from test_model_chain import provision,submit,chain,rows,budget,no_provider_sockets
from parkweave.intern_adapter import ModelBoundaryError
from parkweave.process_env import minimal_environment


def interrupted_recovery(fixture,monkeypatch):
    store,owner,*_=fixture;provision(owner);run=submit(fixture);ch=chain(store);old=ch.insert_artifact;connections=[]
    def crash(c,claim,document,call_id):
        old(c,claim,document,call_id)
        if document['revision']==2:connections.append(c);raise RuntimeError('SYNTHETIC interruption')
    monkeypatch.setattr(ch,'insert_artifact',crash)
    with pytest.raises(RuntimeError,match='SYNTHETIC interruption'):ch.execute(store.claim('lost'))
    assert len(connections)==1 and connections[0].closed
    r,op,case=rows(owner,run);assert r['state']=='RUNNING' and op['state']=='VERIFIED' and case['state']=='NEEDS_INPUT'
    assert len(get(fixture,run).json()['revisions'])==1
    with owner.connect() as c:
        assert c.execute('SELECT count(*) n FROM shared_model_quota.reservations').fetchone()['n']==2
        assert not c.execute("SELECT 1 FROM outbox WHERE run_id=%s AND payload->>'state'='SUCCEEDED'",(run,)).fetchone()
        c.execute("UPDATE runs SET lease_until=clock_timestamp()-interval '1 second' WHERE id=%s",(run,))
    return run,store.claim('replacement')


@pytest.mark.parametrize('bounded',[False,True])
def test_recovery_run_row_wait_before_and_local_deadline_after(fixture,monkeypatch,tmp_path,bounded_recovery_sql,bounded):
    store,owner,*_=fixture;run,claim=interrupted_recovery(fixture,monkeypatch)
    label='eng045_'+uuid.uuid4().hex
    child_dsn=make_conninfo(store.dsn if bounded else bounded_recovery_sql['app'],application_name=label)
    code='''import json,os,sys,psycopg
from pydantic import SecretStr
from parkweave.store import Store
from parkweave.model_chain import ModelChain,synthetic_transport,FAKE_TOKEN
store=Store(os.environ['PARKWEAVE_DSN']);claim=json.loads(os.environ['PARKWEAVE_PROBE_CLAIM'])
ch=ModelChain(store,quota_dsn=store.dsn,account='synthetic-shared-account',transport=synthetic_transport(),token=SecretStr(FAKE_TOKEN))
print('SYNTHETIC_RECOVERY_STARTED',flush=True)
try:ch.execute(claim)
except psycopg.errors.LockNotAvailable:print('SYNTHETIC_LOCK_TIMEOUT',flush=True);sys.exit(3)
print('SYNTHETIC_RECOVERY_COMPLETED',flush=True)
'''
    output=tmp_path/'owned-child.stdout';errors=tmp_path/'owned-child.stderr';process=None
    try:
        with output.open('wb') as out,errors.open('wb') as err:
            with owner.connect() as blocker:
                blocker.execute('SELECT id FROM runs WHERE id=%s FOR UPDATE',(run,))
                process=subprocess.Popen([sys.executable,'-c',code],stdout=out,stderr=err,env=minimal_environment(os.environ,PARKWEAVE_DSN=child_dsn,PARKWEAVE_PROBE_CLAIM=json.dumps({'id':str(claim['id']),'fence':claim['fence']})))
                start=time.monotonic();wait_seen=False
                while time.monotonic()-start<4:
                    with owner.connect() as observer:
                        wait_seen=observer.execute("SELECT count(*) n FROM pg_locks l JOIN pg_stat_activity a ON a.pid=l.pid WHERE a.application_name=%s AND NOT l.granted",(label,)).fetchone()['n']==1
                    if wait_seen:break
                    assert process.poll() is None;time.sleep(.01)
                assert wait_seen and 'SYNTHETIC_RECOVERY_STARTED' in output.read_text()
                if bounded:
                    assert process.wait(timeout=3)==3 and time.monotonic()-start<4
                    assert 'SYNTHETIC_LOCK_TIMEOUT' in output.read_text()
                else:
                    with pytest.raises(subprocess.TimeoutExpired):process.wait(timeout=.05)
            # Release our own blocker before any completion/cleanup wait.
            if not bounded:assert process.wait(timeout=5)==0
        assert errors.read_text()=='' and process.poll() is not None
        if bounded:
            r,op,case=rows(owner,run);assert r['state']=='RUNNING' and op['state']=='VERIFIED'
            assert len(get(fixture,run).json()['revisions'])==1
            chain(store).execute(claim)
        oracle(fixture,run)
        with owner.connect() as c:
            assert c.execute('SELECT count(*) n FROM shared_model_quota.reservations').fetchone()['n']==2
            assert c.execute("SELECT count(*) n FROM outbox WHERE run_id=%s AND payload->>'state'='SUCCEEDED'",(run,)).fetchone()['n']==1
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=3)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=3)


def test_recovery_read_principal_lock_fails_bounded_and_releases(fixture,bounded_recovery_sql):
    store,owner,*_=fixture;provision(owner);run=submit(fixture)
    with owner.connect() as blocker:
        owner.lock_principal(blocker,'fixture-a',exclusive=True);start=time.monotonic()
        with pytest.raises(psycopg.errors.LockNotAvailable):get(fixture,run)
        assert time.monotonic()-start<3
    assert get(fixture,run).status_code==200


def test_recovery_quota_direct_connection_inherits_deadline_without_send(fixture,bounded_recovery_sql):
    store,owner,*_=fixture;provision(owner);b=budget(store)
    with owner.connect() as blocker:
        blocker.execute("SELECT account FROM shared_model_quota.accounts WHERE account='synthetic-shared-account' FOR UPDATE")
        start=time.monotonic()
        with pytest.raises(ModelBoundaryError,match='QUOTA_DENIED'):b.reserve()
        assert time.monotonic()-start<3
    with owner.connect() as c:
        assert c.execute('SELECT count(*) n FROM shared_model_quota.reservations').fetchone()['n']==0
        assert c.execute("SELECT calls FROM shared_model_quota.accounts WHERE account='synthetic-shared-account'").fetchone()['calls']==0
    assert b.reserve()['state']=='RESERVED'


def test_recovery_local_statement_deadline_cancels_owned_synthetic_query(fixture,bounded_recovery_sql):
    store,*_=fixture;start=time.monotonic()
    with pytest.raises(psycopg.errors.QueryCanceled):
        with store.connect() as c:c.execute('SELECT pg_sleep(20)')
    assert time.monotonic()-start<7
    with store.connect() as c:assert c.execute('SELECT 1 ok').fetchone()['ok']==1
