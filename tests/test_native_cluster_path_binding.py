"""Controlled capability-call seams only; no native admission, PG or OS calls."""
from dataclasses import replace
import ctypes as C
from pathlib import PureWindowsPath
from threading import RLock
from types import SimpleNamespace
import time

import pytest

from scripts.windows_portable import cluster_processes as base
from scripts.windows_portable import native_instance_security as native
from scripts.windows_portable.controller import DatabaseInputs,CandidateRefused
from scripts.windows_portable.endpoint_plan import PlanMode
from scripts.windows_portable.instance_processes import InstanceProcesses
from scripts.windows_portable.native_cluster import NativeProtectedClusterProcesses
from scripts.windows_portable import native_cluster, native_database_endpoint, native_trial_authority, pgdata_probe_boundary
from scripts.windows_portable import restricted_startup_candidate, restricted_token_candidate
from scripts.windows_portable.windows_process_handles import WindowsJobProcess
from scripts.windows_portable.pgdata_candidate import pg_command_path


@pytest.fixture
def bound(monkeypatch):
    # These two representations name the same held target in production. The
    # stand-ins here validate dispatch/identity checks, not a real Windows lease.
    guid=PureWindowsPath(r'\\?\Volume{11111111-2222-3333-4444-555555555555}\pw\one')
    command=pg_command_path(r'\\?\C:\pw\one\data\postgresql')[0]
    lease=SimpleNamespace(_verify=lambda:None,status=lambda:'CLUSTER')
    security=native.NativeFixedStoreSecurity(PlanMode.REOPEN,request=None,
        runtime=dict(source_commit='a'*40,manifest_sha256='b'*64))
    inputs=DatabaseInputs('host=127.0.0.1 port=55432 user=postgres dbname=postgres sslmode=disable',
        'host=127.0.0.1 port=55432 user=postgres dbname=parkweave sslmode=disable',
        'host=127.0.0.1 port=55432 user=parkweave_app dbname=parkweave sslmode=disable',command)
    security.inputs=inputs;security.lease=lease;security.target=object();security.plan=object()
    calls=[]
    def under(actual,operation,**kwargs):
        assert actual is lease
        return operation(time.monotonic()+5)
    def path(actual,target):
        assert actual is lease and target is security.target
        calls.append('HELD_PGDATA_PATH');return command
    def endpoints(actual,plan,*,mode):
        assert actual is lease and plan is security.plan and mode is PlanMode.REOPEN
        return dict(database_port=55432,api_port=58761)
    monkeypatch.setattr(security,'_run',under)
    monkeypatch.setattr(native,'_path_held',path)
    monkeypatch.setattr(native.ep,'_record_held',endpoints)
    monkeypatch.setattr(base,'private_root',lambda actual:guid)
    prerequisites=native.NativeClusterPrerequisites(security)
    monkeypatch.setattr(prerequisites,'configuration',lambda *args:inputs)
    cluster=NativeProtectedClusterProcesses(prerequisites,initdb_sha256='c'*64,initdb_size=1,
        postgres_sha256='d'*64,postgres_size=1)
    cluster.lease=lease
    return SimpleNamespace(guid=guid,command=command,lease=lease,security=security,inputs=inputs,
        cluster=cluster,prerequisites=prerequisites,calls=calls)


def test_native_configuration_uses_original_held_command_path_not_guid_string(bound):
    b=bound
    assert b.inputs.data_directory!=str(b.guid/'data'/'postgresql')
    inputs,port=b.cluster._configuration(b.lease,object(),time.monotonic()+5)
    assert inputs is b.inputs and port=='55432' and b.calls==['HELD_PGDATA_PATH']
    legacy=base.FixedClusterProcesses(b.prerequisites,initdb_sha256='c'*64,initdb_size=1,
        postgres_sha256='d'*64,postgres_size=1)
    legacy.lease=b.lease
    with pytest.raises(CandidateRefused):legacy._configuration(b.lease,object(),time.monotonic()+5)


@pytest.mark.parametrize('source_end,server_end', [(200,176),(160,160)])
def test_cluster_phases_keep_individual_windows_under_source_end(bound,monkeypatch,source_end,server_end):
    b=bound
    clock=[100]
    windows=[]

    def configure(lease,credentials,deadline):
        windows.append(('configure',deadline))
        clock[0]+=20
        return b.inputs,'55432'

    def initialize(lease,inputs,specification,register,deadline):
        windows.append(('initdb',deadline))
        clock[0]+=26
        assert clock[0]<deadline

    def before_server(lease,inputs,mode,deadline):
        windows.append(('server',deadline))

    monkeypatch.setattr(native_cluster,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    monkeypatch.setattr(native_trial_authority,'budget',lambda lease,end:min(end,source_end))
    monkeypatch.setattr(pgdata_probe_boundary,'stop_before_initdb',lambda *args:None)
    monkeypatch.setattr(b.cluster,'_time',lambda end,reserve=0:pytest.fail('expired stage') if clock[0]+reserve>=end else None)
    monkeypatch.setattr(b.cluster,'_configuration',configure)
    monkeypatch.setattr(b.prerequisites,'initialize_protected',initialize)
    monkeypatch.setattr(b.prerequisites,'before_server',before_server)
    monkeypatch.setattr(b.prerequisites,'server_ready',lambda lease,inputs,adapter,token,deadline:windows.append(('ready',deadline)))
    monkeypatch.setattr(native_cluster,'PrivateProcessAdapter',lambda *args,**kwargs:SimpleNamespace(launch=lambda *args:object(),live_identity=lambda token:'same-process'))
    b.security.endpoint=object()
    assert b.cluster._run('NEW',b.lease,object(),lambda token:None) is b.inputs
    assert windows==[('configure',130),('initdb',150),('server',server_end),('ready',server_end-3)]


@pytest.mark.parametrize('matching_child',[True,False])
def test_postgres_launch_checks_actual_child_token_and_retains_created_handles(monkeypatch,matching_child):
    lease=object()
    command=SimpleNamespace(arguments=('-D','C:/pw/one/data/postgresql'))
    owner=object.__new__(restricted_token_candidate._RestrictedPrimaryCandidate)
    owner._lock=RLock()
    owner._derived=71
    owner._closed=owner._failed=False
    owner._restricted_snapshot,owner._prepared_owner,owner._prepared_dacl=({},b'sid',b'dacl')
    expected=owner._restricted_snapshot,owner._prepared_owner,owner._prepared_dacl
    owner._primary_full=lambda token:expected if token==71 or matching_child else ({},b'other',b'dacl')
    calls=[]

    def create(token,application,argv,proc_security,thread_security,inherit,flags,environment,cwd,startup,result):
        assert token==71 and inherit is True and flags&4
        calls.append('create_suspended')
        info=result._obj
        info.process,info.thread,info.pid,info.thread_id=80,81,19,20
        return 1

    def open_token(process,access,out):
        assert (process,access)==(80,8)
        out._obj.value=82
        return 1

    owner._adv=SimpleNamespace(CreateProcessAsUserW=create,OpenProcessToken=open_token)
    security=SimpleNamespace(lease=lease,resources=[owner])
    trial=SimpleNamespace(deadline=time.monotonic()+10)
    monkeypatch.setattr(native_trial_authority,'bound_state',lambda resource,**kwargs:trial)
    monkeypatch.setattr(restricted_startup_candidate,'_OwnedStartup',lambda:SimpleNamespace(
        info=C.c_uint32(),prepare=lambda handles:calls.append(handles),
        close=lambda:calls.append('close_startup'),cleanup_errors=[]))
    backend=object.__new__(WindowsJobProcess)
    backend._postgres_authority=(security,lease,command,owner,time.monotonic()+5)
    backend.original=SimpleNamespace(crt=SimpleNamespace(get_osfhandle=lambda fd:fd+100),close=calls.append)
    backend.kernel=SimpleNamespace(GetThreadId=lambda thread:20,GetProcessIdOfThread=lambda thread:19)
    exe=SimpleNamespace(lease=lease,command=command,command_path='C:/pw/one/runtime/postgresql/bin/postgres.exe',
                        root_path='C:/pw/one',verify=lambda:None)
    group=SimpleNamespace(executable=exe,command=command,registration='ACKNOWLEDGED',resources={})
    if matching_child:
        backend._create_postgres_suspended(group,{},[1,2,3],time.monotonic()+3)
    else:
        from scripts.windows_portable.processes import ProcessRefused
        with pytest.raises(ProcessRefused,match='RESTRICTED_POSTGRES_CHILD_TOKEN_CHANGED'):
            backend._create_postgres_suspended(group,{},[1,2,3],time.monotonic()+3)
    assert group.resources==dict(process=80,thread=81,pid=19,bound=False)
    assert calls==[(101,102,103),'create_suspended',82,'close_startup']
    assert backend._postgres_authority is None


@pytest.mark.parametrize('witness_times_out',[False,True])
def test_listener_retries_only_connect_timeout_after_closing_probe(monkeypatch,witness_times_out):
    calls=[]
    sockets=[]

    class Probe:
        def __init__(self,*_):
            sockets.append(self)
            self.number=len(sockets)

        def __enter__(self):
            return self

        def __exit__(self,*_):
            calls.append(('close_socket',self.number))

        def settimeout(self,value):
            assert 0<value<=.2

        def connect(self,address):
            assert address==('127.0.0.1',55431)
            calls.append(('connect',self.number))
            if self.number==1:raise TimeoutError('TCP connect not completed')

    class Witness:
        def __init__(self,endpoint,connection,deadline):
            assert connection is sockets[1]

        def verify(self):
            calls.append('verify_witness')
            if witness_times_out:raise TimeoutError('witness verification timed out')

        def close(self):
            calls.append('close_witness')

    def observe(token,seconds):
        assert calls[-1]==('close_socket',1)
        assert 0<seconds<=.05
        calls.append('observe_original')

    monkeypatch.setattr(native_database_endpoint.socket,'socket',Probe)
    monkeypatch.setattr(native_database_endpoint,'_BackendWitness',Witness)
    endpoint=object.__new__(native_database_endpoint.NativeOwnedDatabaseEndpoint)
    endpoint.verify=lambda:calls.append('verify_endpoint')
    endpoint.adapter=SimpleNamespace(observe=observe)
    endpoint.port,endpoint.token='55431',object()
    if witness_times_out:
        with pytest.raises(TimeoutError,match='witness verification'):
            endpoint.wait_for_listener(time.monotonic()+1)
    else:
        endpoint.wait_for_listener(time.monotonic()+1)
    assert calls==['verify_endpoint',('connect',1),('close_socket',1),'observe_original',
                   'verify_endpoint',('connect',2),'verify_witness','close_witness',('close_socket',2)]


@pytest.mark.parametrize('socket_pid,in_job,child_ticks,accepted',[
    (19,True,200,True), (20,True,200,True), (21,True,200,False),
    (19,False,200,False), (19,True,99,False),
])
def test_authenticated_backend_retains_job_and_postmaster_socket_binding(monkeypatch,socket_pid,in_job,child_ticks,accepted):
    closed=[]
    endpoint=object.__new__(native_database_endpoint.NativeOwnedDatabaseEndpoint)
    endpoint.verify=lambda:None
    endpoint.birth=(19,(19,100),'original-command')
    endpoint.job,endpoint.image,endpoint.crt_witness=31,'pinned-postgres-image',None

    def image(handle,flags,buffer,length):
        buffer.value=endpoint.image
        length._obj.value=len(endpoint.image)
        return True

    def is_in_job(handle,job,out):
        assert job==endpoint.job
        out._obj.value=int(in_job)
        return True

    endpoint.backend=SimpleNamespace(birth=lambda handle:(20,child_ticks),image=image)
    kernel=SimpleNamespace(OpenProcess=lambda access,inherit,pid:pid+50,
                           CloseHandle=lambda handle:closed.append(handle) or True,
                           WaitForSingleObject=lambda handle,milliseconds:258,IsProcessInJob=is_in_job)
    connection=SimpleNamespace(fileno=lambda:27,getsockname=lambda:('127.0.0.1',50001),
                               getpeername=lambda:('127.0.0.1',55431),detach=lambda:None)
    monkeypatch.setattr(native_database_endpoint.C,'WinDLL',lambda *args,**kwargs:kernel,raising=False)
    monkeypatch.setattr(native_database_endpoint,'connection_owner',lambda connection:socket_pid)
    monkeypatch.setattr(native_database_endpoint.socket,'socket',lambda **kwargs:connection)
    if accepted:
        witness=native_database_endpoint._BackendWitness(endpoint,connection,time.monotonic()+1,authenticated_pid=20)
        assert (witness.socket_pid,witness.pid,witness.birth)==(socket_pid,20,(20,child_ticks))
        witness.close()
    else:
        with pytest.raises(CandidateRefused):
            native_database_endpoint._BackendWitness(endpoint,connection,time.monotonic()+1,authenticated_pid=20)
    assert closed==([] if socket_pid==21 else [70])


def test_native_instance_checks_same_cluster_security_and_inputs(bound,monkeypatch):
    b=bound
    def opened(lease,credentials,register):
        assert lease is b.lease
        b.cluster.lease=lease;b.cluster.inputs=b.inputs;register(object());return b.inputs
    monkeypatch.setattr(b.cluster,'open_cluster',opened)
    instance=InstanceProcesses(b.cluster,python_sha256='e'*64,python_size=1,challenge='f'*32,endpoint_source=b.security)
    assert instance.open_cluster(b.lease,object(),lambda token:None) is b.inputs
    assert b.calls==['HELD_PGDATA_PATH']
    copied=replace(b.inputs)
    with pytest.raises(CandidateRefused):b.cluster.require_bound_inputs(b.lease,copied,b.security)
    with pytest.raises(CandidateRefused):b.cluster.require_bound_inputs(object(),b.inputs,b.security)
    other=native.NativeFixedStoreSecurity(PlanMode.REOPEN,request=None,runtime=b.security.runtime)
    with pytest.raises(CandidateRefused):b.cluster.require_bound_inputs(b.lease,b.inputs,other)
    assert b.calls==['HELD_PGDATA_PATH']


def test_security_rejects_cloned_or_wrong_path_inputs_without_normalizing(bound):
    b=bound
    with pytest.raises(CandidateRefused):b.security.require_inputs(b.lease,replace(b.inputs))
    assert b.calls==[]
    wrong=replace(b.inputs,data_directory=b.command.lower())
    b.security.inputs=wrong
    with pytest.raises(CandidateRefused):b.security.require_inputs(b.lease,wrong)
    assert b.calls==['HELD_PGDATA_PATH']
