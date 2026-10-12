"""Independent pure framing and action-order observations; no physical actions."""
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import json
import sys
import pytest

ROOT=Path(__file__).resolve().parents[3]


def bootstrap():
    spec=importlib.util.spec_from_file_location('independent_diagnostic_bootstrap',ROOT/'scripts/linux_trial/bootstrap.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


@pytest.mark.parametrize('nested',['diagnostic','result'])
def test_nested_duplicate_keys_are_rejected_before_private_projection(nested):
    m=bootstrap()
    if nested=='diagnostic':
        raw=b'{"outcome":"FAIL","diagnostic":{"substage":"MIGRATION","check_id":"MIGRATION","status_code":0,"status_code":403}}'
        code=1
    else:
        raw=b'{"outcome":"PASS","diagnostic":{"substage":"OUTPUT","check_id":"RESULT","status_code":0},"result":{"writer_dsn":"SYNTHETIC_PRIVATE_A","writer_dsn":"SYNTHETIC_PRIVATE_B"}}'
        code=0
    with pytest.raises(ValueError) as error:m.setup_frame(raw,code)
    assert str(error.value)=='SETUP_FRAME_CONTRACT'


@pytest.mark.parametrize('check_id',['ROLE_CREATE','DATABASE_ACL','WRITER_ACL'])
def test_sql_acl_check_cannot_carry_http_status(check_id):
    m=bootstrap();value=dict(substage='ACL',check_id=check_id,status_code=403)
    with pytest.raises(ValueError) as error:m.setup_diagnostic(value)
    assert str(error.value)=='SETUP_DIAGNOSTIC_CONTRACT'


def test_signal_exit_cannot_be_accepted_as_reported_setup_failure():
    m=bootstrap();raw=json.dumps(dict(outcome='FAIL',diagnostic=dict(substage='OWNERSHIP',check_id='CLUSTER_PROOF',status_code=0))).encode()
    with pytest.raises(ValueError):m.setup_frame(raw,-15)


@pytest.mark.parametrize('boundary',['MIGRATION','SEED'])
def test_worker_records_check_before_synthetic_operation_failure(monkeypatch,capsys,boundary):
    import scripts.linux_trial.worker as worker
    m=bootstrap();poison='SYNTHETIC_PRIVATE_DIAGNOSTIC_POISON'
    config=dict(pg_uid=7001,data='/synthetic',owner_maintenance_dsn=poison,database='fixture_'+'a'*32,
        tokens={k:poison for k in ('fixture-a','fixture-b','fixture-c')})
    class Connection:
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def execute(self,*args):return self
    class Owner:
        def connect(self):return Connection()
        def migrate(self):
            if boundary=='MIGRATION':raise RuntimeError(poison)
        def seed(self,tokens):raise RuntimeError(poison)
    monkeypatch.setattr(sys,'argv',['helper','SETUP','42'])
    monkeypatch.setattr(worker,'sealed_input',lambda fd:config)
    monkeypatch.setattr(worker.os,'geteuid',lambda:7001)
    monkeypatch.setattr(worker,'capture_fixture_cluster',lambda *args:SimpleNamespace(record_created_database=lambda c:object()))
    monkeypatch.setattr(worker.psycopg,'connect',lambda *args,**kwargs:Connection())
    monkeypatch.setattr(worker,'make_conninfo',lambda *args,**kwargs:poison)
    monkeypatch.setattr(worker,'Store',lambda dsn:Owner())
    assert worker.main()==1
    capture=capsys.readouterr()
    outcome,diag,result=m.setup_frame(capture.out.encode(),1)
    assert outcome=='FAIL' and result is None and diag['check_id']==boundary and diag['status_code']==0
    assert poison not in capture.out and poison in capture.err
