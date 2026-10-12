"""Pure synthetic/DI adapter evidence only. Never request PG/OS fixtures."""
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import hmac
import json
import os
import socket
import stat
import struct
import subprocess
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest

from parkweave import native_run_access as native,native_run_access_writer as writer
from parkweave import native_run_access_restricted_runtime as runtime
from parkweave import native_run_access_restricted_host as host
from parkweave.store import Denied,_AccessConnection
from test_native_run_access_trial_plan import inputs


def adapter_inputs():
    spec,catalog,_ = inputs()
    layout = dict(trial_root='/tmp/parkweave-trial-'+'b'*32,source_sha='c'*40,
        source_root='/opt/parkweave/src',source_files={'/opt/parkweave/src/parkweave/store.py':'d'*64},
        interpreter='/opt/parkweave/env/bin/python',interpreter_sha256='e'*64,
        dependency_roots=['/opt/parkweave/env'],
        api_uid=10001,api_gid=10004,writer_uid=10002,ipc_gid=10003,boot_id=str(uuid4()),
        private_bootstrap_sha256='f'*64,creation_receipt_sha256='a'*64)
    p=spec['policy']
    private=dict(writer_dsn="host=127.0.0.1 port=5432 dbname="+p['database_name']+
        " user=synthetic_writer password=SYNTHETIC_NOT_A_REAL_CREDENTIAL",key='22'*32)
    catalog['database'].update(session_user=p['writer_role'],current_user=p['writer_role'])
    return spec,catalog,layout,private


@pytest.fixture(autouse=True)
def no_real_actions(monkeypatch):
    def forbidden(*args,**kwargs):pytest.fail('real PG/OS/permission action forbidden in DI window')
    for obj,name in [(psycopg,'connect'),(psycopg.Connection,'connect'),(subprocess,'Popen'),
        (socket.socket,'bind'),(socket.socket,'connect'),(os,'chmod'),(os,'chown'),
        (os,'fchmod'),(os,'fchown'),(os,'umask'),(os,'memfd_create')]:
        monkeypatch.setattr(obj,name,forbidden)


class FakeConnection:
    def __init__(self,spec):
        self.p=spec['policy'];self.queries=[];self.closed=False;self.rolled_back=False
        self.info=SimpleNamespace(host=self.p['database_host'],port=self.p['database_port'])
    def execute(self,query,args=None):
        self.queries.append((query,args));return self
    def fetchone(self):
        query=self.queries[-1][0]
        if 'current_schemas' in query:return {'value':['pg_catalog','public']}
        if 'pg_database' in query:return dict(database_name=self.p['database_name'],database_oid=self.p['database_oid'],
            database_owner='synthetic_installer',database_role=self.p['writer_role'],started=datetime.now(timezone.utc))
        if 'pg_control_system' in query:return {'value':self.p['system_identifier']}
        if 'pg_roles' in query:return dict(rolsuper=False,rolcreaterole=False,rolcreatedb=False)
        if 'clock_timestamp' in query:return {'now':datetime.now(timezone.utc)}
        if 'SELECT * FROM runs' in query:return dict(principal_id=self.p['owner_id'],park_id=self.p['source']['park_id'],
            org_id=self.p['source']['org_id'],native_run_access_protocol=None)
        raise AssertionError('unhandled DI query')
    def rollback(self):self.rolled_back=True
    def close(self):self.closed=True
    def __enter__(self):return self
    def __exit__(self,*error):pass


def guard_inputs():
    spec,catalog,layout,private=adapter_inputs();calls=[]
    identity=dict(session_name=spec['policy']['writer_role'],current_name=spec['policy']['writer_role'],
        owner_name='synthetic_installer')
    extras={k:False for k in runtime.EXTRA_CHECKS}
    guard=runtime.RuntimeGuard(spec,lambda:calls.append('host'),catalog_reader=lambda *a:deepcopy(catalog),
        identity_reader=lambda c:deepcopy(identity),extra_reader=lambda *a:deepcopy(extras))
    return spec,catalog,guard,identity,extras,calls


def test_public_and_synthetic_approval_cannot_reach_live_operations(monkeypatch,capsys):
    spec,_,layout,private=adapter_inputs();controller=host.LinuxHost(spec,layout)
    monkeypatch.setattr(host,'_protected_bytes',lambda *a,**k:pytest.fail('no private read before authority'))
    with pytest.raises(Denied):controller.start()
    for fake in (True,{'approved':True},SimpleNamespace(issuer=controller)):
        with pytest.raises(Denied):controller._spawn(fake,9)
        with pytest.raises(Denied):controller._publish(fake,{})
        with pytest.raises(Denied):controller._claim(fake)
    with pytest.raises(Denied):host._LiveApproval(controller,object(),{})
    copied_internal_type=host._LiveApproval(controller,host._ISSUER,host.launch_request(spec,layout))
    with pytest.raises(Denied):controller._spawn(copied_internal_type,9)
    with pytest.raises(Denied):host.bind_api(None)
    engine=runtime.RestrictedEngine(spec,private,layout['boot_id'],lambda:None)
    with pytest.raises(Denied):runtime.serve_restricted(engine,{'approved':True})
    typed_but_unissued=host._RuntimeAuthorization(host._ISSUER,{'spec':spec,'layout':layout,'private':private,
        'host_pid':1,'host_started':'SYNTHETIC'})
    with pytest.raises(Denied):runtime.serve_restricted(engine,typed_but_unissued)
    assert runtime.main([])==4 and 'actual_run=NOT_RUN' in capsys.readouterr().out
    with pytest.raises(SystemExit) as error:runtime.main(['--execute','SYNTHETIC_PRIVATE_VALUE'])
    assert error.value.code==4 and 'SYNTHETIC_PRIVATE_VALUE' not in capsys.readouterr().err


@pytest.mark.parametrize('mutation', ['spec','layout','signature','action'])
def test_host_approval_signature_binds_entire_action_and_never_issues_capability(mutation):
    spec,_,layout,_=adapter_inputs();request=host.launch_request(spec,layout);key=b'SYNTHETIC_ONLY_APPROVAL_KEY_32___'
    key=key.ljust(32,b'_')[:32]
    record=dict(payload=deepcopy(request),hmac_sha256=hmac.new(key,writer._canonical(request).encode(),hashlib.sha256).hexdigest())
    assert host.verified_record(record,key,request) is None
    if mutation=='signature':record['hmac_sha256']='0'*64
    elif mutation=='action':record['payload']['action']='INSTALL_PRODUCTION'
    elif mutation=='spec':spec['policy']['source']['preparation_revision']+=1;request=host.launch_request(spec,layout)
    else:layout['writer_uid']+=1;spec['writer_uid']+=1;request=host.launch_request(spec,layout)
    with pytest.raises(Denied):host.verified_record(record,key,request)


def test_launch_arguments_have_explicit_identity_fixed_entry_and_no_private_values():
    spec,_,layout,private=adapter_inputs();before=deepcopy(layout)
    args=host.launch_arguments(layout,9)
    assert layout==before and args['user']==layout['writer_uid'] and args['group']==layout['ipc_gid']
    assert args['extra_groups']==[] and args['close_fds'] and args['pass_fds']==(9,)
    assert args['shell'] is False and args['cwd']=='/' and args['umask']==0o117
    assert args['env']=={'LANG':'C.UTF-8'} and args['args'][1]=='-I'
    assert all(value not in json.dumps(args) for value in private.values())
    assert '--reference-bootstrap' not in args['args']


@pytest.mark.parametrize('change',[dict(api_uid=0),dict(writer_uid=0),dict(writer_uid=10001),
    dict(source_root='/opt/../outside'),dict(trial_root='/tmp/parkweave-trial-'+'b'*32+'/../outside')])
def test_layout_requires_nonroot_distinct_identities_and_canonical_scoped_paths(change):
    spec,_,layout,_=adapter_inputs();layout.update(change)
    with pytest.raises(ValueError):host.RuntimeLayout.model_validate(layout)


@pytest.mark.parametrize('change',['service','options','missing_password','role','database','multi_host'])
def test_private_dsn_refuses_discovery_overrides_and_hides_values(change):
    spec,_,layout,private=adapter_inputs();dsn=private['writer_dsn']
    if change=='missing_password':dsn=dsn.split(' password=')[0]
    elif change=='role':dsn=dsn.replace('user=synthetic_writer','user=synthetic_installer')
    elif change=='database':dsn=dsn.replace(spec['policy']['database_name'],'production')
    elif change=='multi_host':dsn=dsn.replace('host=127.0.0.1','host=127.0.0.1,10.0.0.1')
    else:dsn+=' '+change+'=SYNTHETIC_PRIVATE_VALUE'
    with pytest.raises(Denied) as error:runtime.private_connection_dsn(dsn,writer.WriterPolicy.model_validate(spec['policy']))
    assert 'SYNTHETIC_PRIVATE_VALUE' not in str(error.value) and 'SYNTHETIC_NOT_A_REAL_CREDENTIAL' not in str(error.value)


def test_guard_compares_live_metadata_again_without_material_or_lease_locking():
    spec,catalog,guard,_,extras,calls=guard_inputs();c=FakeConnection(spec)
    guard.check(c);assert calls==['host']
    catalog['roles']['synthetic_writer']['bypass_rls']=True
    with pytest.raises(Denied):guard.check(c)
    assert calls==['host','host']
    assert all('FOR UPDATE' not in q and 'advisory' not in q for q,_ in c.queries)
    assert ('writer','SELECT','schema_version',None) in runtime.required_privileges('revision')


def test_private_context_runs_exact_runtime_guard_before_existing_validation():
    spec,catalog,guard,_,_,calls=guard_inputs();_,_,_,private=adapter_inputs()
    store=SimpleNamespace(mode='LOCAL',_restricted_runtime=guard)
    context=writer.WriterContext(store,spec['policy'],bytes.fromhex(private['key']))
    permit=context.validate(FakeConnection(spec))
    assert permit.policy_sha256==writer._sha(context.policy.model_dump()) and calls==['host']
    catalog['privileges']['app:assignment_write']=True
    with pytest.raises(Denied):context.validate(FakeConnection(spec))
    store._restricted_runtime=SimpleNamespace(policy_json=guard.policy_json,check=lambda c:pytest.fail('unknown provider must not run'))
    with pytest.raises(Denied):context.validate(FakeConnection(spec))


@pytest.mark.parametrize('field',sorted(runtime.EXTRA_CHECKS))
def test_runtime_rejects_extra_actual_authority_and_unknown_summary(field):
    spec,_,guard,_,extra,_=guard_inputs();extra[field]=True
    with pytest.raises(Denied):guard.check(FakeConnection(spec))
    extra[field]=None
    with pytest.raises(Denied):guard.check(FakeConnection(spec))


@pytest.mark.parametrize('field',['session_name','current_name','owner_name'])
def test_actual_session_role_and_ownership_cannot_be_substituted(field):
    spec,_,guard,identity,_,_=guard_inputs()
    identity[field]=spec['policy']['writer_role'] if field=='owner_name' else 'synthetic_other_login'
    with pytest.raises(Denied):guard.check(FakeConnection(spec))


def test_store_sets_search_path_without_preventing_readonly_header_and_refuses_dsn_override():
    spec,_,guard,_,_,calls=guard_inputs();_,_,_,private=adapter_inputs();c=FakeConnection(spec)
    # This connector records only; global real connect sentinel remains installed.
    store=runtime.RestrictedStore(private['writer_dsn'],guard,connector=lambda *a,**k:c)
    assert store._guarded_connect() is c
    assert c.queries==[('SET LOCAL search_path=pg_catalog,public,pg_temp',None)]
    assert calls==['host']
    with pytest.raises(Denied):store._guarded_connect('SYNTHETIC_OWNER_DSN')


def test_first_sql_and_commit_guard_failure_roll_back_before_business_commit(monkeypatch):
    events=[];c=object.__new__(runtime._RestrictedConnection)
    c._runtime_checked=c._runtime_checking=False
    c._restricted_runtime=SimpleNamespace(check=lambda c:events.append('guard'))
    monkeypatch.setattr(_AccessConnection,'execute',lambda c,q,*a,**k:events.append(q))
    monkeypatch.setattr(_AccessConnection,'commit',lambda c:events.append('business_commit'))
    monkeypatch.setattr(runtime._RestrictedConnection,'rollback',lambda c:events.append('rollback'))
    monkeypatch.setattr(runtime._RestrictedConnection,'close',lambda c:events.append('close'))
    c.execute('SET LOCAL search_path=pg_catalog,public,pg_temp');c.execute('SET TRANSACTION READ ONLY')
    assert 'guard' not in events
    c.execute('SELECT current_user');c.execute('SELECT session_user');c.commit()
    assert events[-2:]==['guard','business_commit'] and events.count('guard')==2
    def deny(c):events.append('changed_acl');raise Denied('SYNTHETIC commit refusal')
    c._restricted_runtime.check=deny
    with pytest.raises(Denied):c.commit()
    assert events[-3:]==['changed_acl','rollback','close']


def test_verify_is_mac_only_even_after_expiry_and_no_store_factory():
    spec,_,layout,private=adapter_inputs()
    spec['policy'].update(valid_from='2026-01-01T00:00:00+00:00',valid_until='2026-01-01T00:30:00+00:00')
    engine=runtime.RestrictedEngine(spec,private,layout['boot_id'],lambda:pytest.fail('MAC must not query host or current ACL'),
        store_factory=lambda:pytest.fail('MAC must not open Store'))
    receipt=writer.WriterContext(None,spec['policy'],bytes.fromhex(private['key'])).sign({'request_key':'original'})
    request=dict(operation='VERIFY',nonce='a'*32,run_id=spec['policy']['source']['run_id'],receipts=[receipt])
    assert engine.execute(request,True) is True
    request['receipts'][0]['request_key']='changed'
    assert engine.execute(request,True) is False


@pytest.mark.parametrize('change',[dict(operation='SQL'),dict(operation='SIGN'),dict(actor_id='SYNTHETIC_ACTOR'),
    dict(run_id=str(uuid4())),dict(nonce='invalid')])
def test_restricted_frames_deny_before_dependency_call(change):
    spec,_,layout,private=adapter_inputs()
    engine=runtime.RestrictedEngine(spec,private,layout['boot_id'],lambda:pytest.fail('invalid input touched host'),
        store_factory=lambda:pytest.fail('invalid input touched Store'))
    request=dict(operation='VERIFY',nonce='a'*32,run_id=spec['policy']['source']['run_id'],receipts=[]);request.update(change)
    with pytest.raises(Denied):engine.execute(request,True)
    with pytest.raises(Denied):engine.execute(dict(operation='VALIDATE',nonce='a'*32,run_id=spec['policy']['source']['run_id']),False)


@pytest.mark.parametrize('operation',['COMMAND','ACTIVATE'])
def test_engine_dispatches_exact_original_business_types_and_original_key(monkeypatch,operation):
    spec,_,layout,private=adapter_inputs();calls=[]
    store=SimpleNamespace(mode='LOCAL')
    engine=runtime.RestrictedEngine(spec,private,layout['boot_id'],lambda:calls.append('host'),store_factory=lambda:store)
    def capture(bridge,token,run_id,key,data):
        assert bridge.store is store and type(bridge.writer) is writer.WriterContext
        calls.append((operation,token,str(run_id),key,type(data).__name__));return {'original_key':key}
    monkeypatch.setattr(native.NativeRunAccess,'command' if operation=='COMMAND' else 'activate',capture)
    command=dict(action='REVOKE',expected_revision=1,expected_run_revision=1,expected_authority_sha256='a'*64,reason='SYNTHETIC explicit')
    if operation=='ACTIVATE':command.update(action='ACTIVATE',lease_id=str(uuid4()),expected_activation_revision=0,
        activation_policy_sha256=writer._sha(spec['policy']),confirm_activate=True)
    request=dict(operation=operation,nonce='a'*32,run_id=spec['policy']['source']['run_id'],token='SYNTHETIC_SESSION',request_key='original-key',command=command)
    assert engine.execute(request,False)=={'original_key':'original-key'}
    assert calls==['host',(operation,'SYNTHETIC_SESSION',request['run_id'],'original-key','RunCommand' if operation=='COMMAND' else 'Activate')]


def test_revoke_does_not_recheck_changed_material_or_beneficiary_generations(monkeypatch):
    spec,_,_,private=adapter_inputs();store=SimpleNamespace(mode='LOCAL',check_capability=lambda *a:None)
    context=writer.WriterContext(store,spec['policy'],bytes.fromhex(private['key']))
    bridge=native.NativeRunAccess(store,writer=context)
    monkeypatch.setattr(bridge,'_source',lambda *a:pytest.fail('REVOKE must not rebind changed source'))
    monkeypatch.setattr(bridge,'_parent',lambda *a:pytest.fail('REVOKE must not impose new parent validity'))
    actor=dict(id=spec['policy']['owner_id'],active=True,park_id=spec['policy']['source']['park_id'],org_id=spec['policy']['source']['org_id'])
    context.action(bridge,FakeConnection(spec),actor,'REVOKE')
    actor['active']=False
    with pytest.raises(Denied):context.action(bridge,FakeConnection(spec),actor,'REVOKE')


@pytest.mark.parametrize('uid,gid',[(10001,10003),(0,10004),(10002,10003)])
def test_peer_refused_before_frame_or_engine_call(uid,gid,monkeypatch):
    calls=[]
    fake=SimpleNamespace(request=SimpleNamespace(getsockopt=lambda *a:struct.pack('3i',99,uid,gid)),
        server=SimpleNamespace(expected_api_peer=(10001,10004)))
    monkeypatch.setattr(writer._Handler,'handle',lambda self:calls.append('frame'))
    runtime._PeerHandler.handle(fake)
    assert calls==[]


def test_expected_api_peer_may_reach_bounded_handler(monkeypatch):
    calls=[];fake=SimpleNamespace(request=SimpleNamespace(getsockopt=lambda *a:struct.pack('3i',99,10001,10004)),
        server=SimpleNamespace(expected_api_peer=(10001,10004)))
    # Use an uninitialized Python handler, never a socketserver or connection.
    instance=object.__new__(runtime._PeerHandler);instance.request=fake.request;instance.server=fake.server
    monkeypatch.setattr(writer._Handler,'handle',lambda self:calls.append('frame'))
    instance.handle();assert calls==['frame']


def test_pin_is_bound_to_host_observations_and_endpoint_instance():
    spec,_,layout,_=adapter_inputs()
    process=dict(pid=99,uid=10002,gid=10003,uids=[10002]*4,gids=[10003]*4,groups=[],started='SYNTHETIC_START')
    endpoint=dict(device=10,inode=11,uid=10002,gid=10003,mode=0o660)
    other={**endpoint,'inode':12}
    pin=host.observed_pin(spec['policy'],layout,process,endpoint,other)
    assert pin.pid==99 and pin.uid==10002 and pin.boot_id==layout['boot_id']
    with pytest.raises(Denied):host.observed_pin(spec['policy'],layout,process,endpoint,endpoint)
    process['groups']=[10001]
    with pytest.raises(Denied):host.observed_pin(spec['policy'],layout,process,endpoint,other)


def test_protected_reader_detects_fd_owner_mode_and_path_replacement_without_real_fd(monkeypatch):
    raw=b'SYNTHETIC_PUBLIC_INPUT';closed=[]
    observation=SimpleNamespace(st_mode=stat.S_IFREG|0o600,st_uid=0,st_gid=0,st_size=len(raw),st_dev=1,st_ino=2,st_mtime_ns=3)
    monkeypatch.setattr(host,'_path_chain',lambda *a:None)
    monkeypatch.setattr(os,'open',lambda *a:999)
    monkeypatch.setattr(os,'fstat',lambda fd:deepcopy(observation))
    monkeypatch.setattr(os,'read',lambda *a:raw)
    monkeypatch.setattr(os,'close',lambda fd:closed.append(fd))
    monkeypatch.setattr(host.Path,'lstat',lambda p:deepcopy(observation))
    assert host._protected_bytes('/synthetic/private',0,private=True)==raw and closed==[999]
    monkeypatch.setattr(host.Path,'lstat',lambda p:SimpleNamespace(**{**vars(observation),'st_ino':4}))
    with pytest.raises(Denied):host._protected_bytes('/synthetic/private',0,private=True)
    assert closed==[999,999]


def test_unknown_child_cannot_be_adopted_or_stopped():
    spec,_,layout,_=adapter_inputs();controller=host.LinuxHost(spec,layout)
    with pytest.raises(Denied):controller.stop(SimpleNamespace(pid=99))


def test_owned_output_handles_partial_write_and_zero_progress_without_real_fd(monkeypatch):
    written=[]
    def partial(fd,value):written.append(value[:3]);return min(3,len(value))
    monkeypatch.setattr(os,'write',partial)
    host._write_all(999,b'SYNTHETIC_PUBLIC_BYTES')
    assert b''.join(written)==b'SYNTHETIC_PUBLIC_BYTES'
    monkeypatch.setattr(os,'write',lambda *a:0)
    with pytest.raises(Denied):host._write_all(999,b'SYNTHETIC')


@pytest.mark.parametrize('query',["SET LOCAL lock_timeout='5s'; UPDATE public.runs SET state='changed'",'SET LOCAL ROLE synthetic_installer'])
def test_unapproved_set_or_multiple_statements_cannot_bypass_first_sql_guard(monkeypatch,query):
    events=[];c=object.__new__(runtime._RestrictedConnection)
    c._runtime_checked=c._runtime_checking=False
    def denied(c):events.append('guard');raise Denied('SYNTHETIC unsafe current role')
    c._restricted_runtime=SimpleNamespace(check=denied)
    monkeypatch.setattr(_AccessConnection,'execute',lambda *a:pytest.fail('unsafe query reached backend'))
    with pytest.raises(Denied):c.execute(query)
    assert events==['guard']


@pytest.mark.parametrize('change',[dict(token=None),dict(request_key=[]),dict(request_key=''),dict(request_key='x'*257)])
def test_bad_session_or_key_is_rejected_before_host_or_store(change):
    spec,_,layout,private=adapter_inputs()
    engine=runtime.RestrictedEngine(spec,private,layout['boot_id'],lambda:pytest.fail('bad credentials reached host'),
        store_factory=lambda:pytest.fail('bad credentials reached Store'))
    request=dict(operation='COMMAND',nonce='a'*32,run_id=spec['policy']['source']['run_id'],
        token='SYNTHETIC_SESSION',request_key='original-key',command={});request.update(change)
    with pytest.raises(Denied):engine.execute(request,False)


def test_extra_acl_query_is_catalog_qualified_and_metadata_only():
    query=[]
    class Reader:
        def execute(self,sql,params):query.append((sql,params));return self
        def fetchone(self):return {name:False for name in runtime.EXTRA_CHECKS}
    assert runtime._additional_acl(Reader(),['synthetic_app','synthetic_writer'])=={name:False for name in runtime.EXTRA_CHECKS}
    sql,params=query[0]
    assert sql.count('%s')==len(params)
    assert sql.startswith('SELECT') and 'FOR UPDATE' not in sql and 'advisory' not in sql
    assert 'r.rolreplication' in sql and 'r.rolbypassrls' in sql and 'a.is_grantable' in sql
    assert "'TEMP'" in sql and 'pg_catalog.pg_my_temp_schema()' in sql


def test_validate_channel_sets_readonly_before_live_guard_and_never_business_dispatch(monkeypatch):
    spec,_,guard,_,_,calls=guard_inputs();_,_,layout,private=adapter_inputs();c=FakeConnection(spec)
    store=SimpleNamespace(mode='LOCAL',_restricted_runtime=guard,_guarded_connect=lambda:c)
    engine=runtime.RestrictedEngine(spec,private,layout['boot_id'],lambda:calls.append('engine-host'),store_factory=lambda:store)
    monkeypatch.setattr(native.NativeRunAccess,'command',lambda *a:pytest.fail('VALIDATE cannot invoke business command'))
    result=engine.execute(dict(operation='VALIDATE',nonce='a'*32,run_id=spec['policy']['source']['run_id']),True)
    assert c.queries[0][0]=='SET TRANSACTION READ ONLY'
    assert result['system_identifier']==spec['policy']['system_identifier']
    assert calls==['engine-host','host']
