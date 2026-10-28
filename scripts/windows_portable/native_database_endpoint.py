"""Owned Windows PostgreSQL connection, kernel witness BEFORE authentication.

No native calls at import. This does not enable the Windows owner/payload gates.
The retained backend handle must belong to the original created Job and image;
an endpoint PID by itself is never authority. No privileges/ACLs are changed.
"""
import ctypes as C
import math
import os
import selectors
import socket
import time
import weakref

import psycopg
from psycopg import pq
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row

from .controller import CandidateRefused
from .processes import PrivateProcessAdapter
from .windows_process_handles import WindowsJobProcess
from .windows_endpoint import connection_owner

_witnesses=weakref.WeakKeyDictionary()
_unknown_witnesses=[]


def need(value):
    if not value:raise CandidateRefused('NATIVE_OWNED_DATABASE_ENDPOINT_REFUSED')


def remaining(deadline):
    need(type(deadline) in (int,float) and math.isfinite(deadline))
    left=deadline-time.monotonic()
    need(0<left<=30)
    return left


def _wait(raw,events,deadline):
    with selectors.DefaultSelector() as selector:
        selector.register(raw.socket,events)
        need(bool(selector.select(remaining(deadline))))


class _BackendWitness:
    """Retain this socket's actual backend HANDLE, birth, image and Job."""
    def __init__(self,endpoint,connection):
        need(type(endpoint) is NativeOwnedDatabaseEndpoint)
        endpoint.verify()
        self.endpoint,self.socket=endpoint,connection.fileno()
        self.handle=None;self.close_attempted=False
        self.client,self.server=connection.getsockname(),connection.getpeername()
        self.pid=connection_owner(connection)
        k=C.WinDLL('kernel32.dll',use_last_error=True,winmode=0x800)
        self.kernel=k
        for name,args,result in (
            ('OpenProcess',[C.c_uint32,C.c_int32,C.c_uint32],C.c_void_p),
            ('CloseHandle',[C.c_void_p],C.c_int32),
            ('WaitForSingleObject',[C.c_void_p,C.c_uint32],C.c_uint32),
            ('IsProcessInJob',[C.c_void_p,C.c_void_p,C.POINTER(C.c_int32)],C.c_int32),
        ):
            fn=getattr(k,name);fn.argtypes,fn.restype=args,result
        handle=k.OpenProcess(0x101000,False,self.pid)  # query + synchronize only
        need(handle not in (None,0,C.c_void_p(-1).value))
        self.handle=handle  # retain before every fallible observation
        try:
            self.birth=endpoint.backend.birth(handle)
            need(self.birth[0]==self.pid)
            _witnesses[self]=(endpoint,handle,self.birth,self.client,self.server)
            self.verify()
        except BaseException:
            self.close()
            raise

    def verify(self):
        need(not self.close_attempted and _witnesses.get(self)==(
            self.endpoint,self.handle,self.birth,self.client,self.server))
        endpoint=self.endpoint;endpoint.verify()
        need(self.kernel.WaitForSingleObject(self.handle,0)==258)
        inside=C.c_int32()
        need(self.kernel.IsProcessInJob(self.handle,endpoint.job,C.byref(inside)) and inside.value==1)
        need(endpoint.backend.birth(self.handle)==self.birth)
        image=C.create_unicode_buffer(4096);length=C.c_uint32(len(image))
        need(endpoint.backend.image(self.handle,1,image,C.byref(length)) and 0<length.value<len(image)
             and image.value.casefold()==endpoint.image.casefold())
        borrowed=socket.socket(fileno=self.socket)
        try:
            need(borrowed.getsockname()==self.client and borrowed.getpeername()==self.server
                 and connection_owner(borrowed)==self.pid)
        finally:
            borrowed.detach()
        need(endpoint.backend.birth(self.handle)==self.birth and self.kernel.WaitForSingleObject(self.handle,0)==258)
        endpoint.verify()

    def close(self):
        if self.close_attempted:return
        self.close_attempted=True
        _witnesses.pop(self,None)
        if self.handle is not None:
            try:need(self.kernel.CloseHandle(self.handle))
            except BaseException:
                _unknown_witnesses.append(self)  # original handle, never retry
                raise

    def __reduce__(self):raise TypeError('database endpoint witness cannot be serialized')


class _OwnedConnection(psycopg.Connection):
    def wait(self,gen,interval=.1,timeout=None):
        # psycopg's default interrupt path may add a cancellation roundtrip.
        # This owned startup path instead consumes only the remaining budget;
        # its caller closes the original connection on any unknown outcome.
        from psycopg import waiting
        budget=remaining(self._deadline)
        if timeout is not None:budget=min(budget,timeout)
        value=waiting.wait(gen,self.pgconn.socket,interval=min(.1,budget),timeout=budget)
        remaining(self._deadline)
        return value

    def close(self):
        errors=[]
        try:super().close()
        except BaseException as error:errors.append(error)
        witness=getattr(self,'_endpoint_witness',None)
        if witness is not None:
            self._endpoint_witness=None
            try:witness.close()
            except BaseException as error:errors.append(error)
        if errors:raise BaseExceptionGroup('OWNED_DATABASE_CONNECTION_CLOSE_UNKNOWN',errors)


class NativeOwnedDatabaseEndpoint:
    """One exact PostgreSQL Job capability; no caller-supplied PID/port proof."""
    native_acceptance=False

    def __init__(self,adapter,token):
        need(os.name=='nt' and C.sizeof(C.c_void_p)==8 and type(adapter) is PrivateProcessAdapter
             and type(adapter.backend) is WindowsJobProcess)
        group=adapter._group(token)
        need(group.command.relative_executable=='runtime/postgresql/bin/postgres.exe'
             and group.command.model=='WINDOWS_JOB' and group.resources.get('bound') is True)
        args=group.command.arguments
        need(len(args)==14 and args[:1]==('-D',) and args[2:5]==('-h','127.0.0.1','-p')
             and args[6:]==('-c','unix_socket_directories=','-c','ssl=off',
                 '-c','logging_collector=off','-c','log_statement=none')
             and args[5].isascii() and args[5].isdigit() and 1<=int(args[5])<=65535)
        self.port=args[5]
        self.adapter,self.token,self.backend=adapter,token,adapter.backend
        self.group=group;self.birth=adapter.live_identity(token)
        self.job=group.resources['job'];self.image=group.executable.native_path
        self.verify()

    def verify(self):
        need(self.adapter._group(self.token) is self.group and self.adapter.backend is self.backend
             and type(self.backend) is WindowsJobProcess and self.group.resources['job']==self.job
             and self.adapter.live_identity(self.token)==self.birth)
        self.group.executable.verify()

    def verify_connection(self,connection):
        need(type(connection) is _OwnedConnection)
        witness=getattr(connection,'_endpoint_witness',None)
        need(type(witness) is _BackendWitness and witness.endpoint is self
             and connection.pgconn.socket==witness.socket)
        witness.verify()

    def wait_for_listener(self,deadline):
        """Read-only probes before any libpq startup or credential dispatch."""
        while True:
            self.verify();budget=remaining(deadline)
            try:
                with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as connection:
                    connection.settimeout(min(.2,budget))
                    connection.connect(('127.0.0.1',int(self.port)))
                    witness=_BackendWitness(self,connection)
                    try:witness.verify()
                    finally:witness.close()
                return
            except ConnectionRefusedError:
                # A completed refusal sent no startup packet/password. Closing
                # the original socket succeeded; only this condition may poll.
                if self.adapter.observe(self.token,min(.05,remaining(deadline))) is not None:
                    need(False)

    def connect(self,parsed,*,autocommit=False,deadline=None):
        from parkweave.installed_fixture_receipt import _dsn,refuse_inherited_configuration
        need(type(parsed) is dict and type(autocommit) is bool)
        database=parsed.get('dbname')
        need(database in ('postgres','parkweave'))
        checked=_dsn(make_conninfo(**parsed),database)
        need(checked['host']=='127.0.0.1' and checked['port']==self.port
             and checked['user'] in ('postgres','parkweave_app'))
        refuse_inherited_configuration();self.verify()
        deadline=time.monotonic()+10 if deadline is None else deadline
        remaining(deadline)
        # libpq 18 pqConnectDBStart returns after CONNECTION_STARTED/MADE,
        # before the startup packet/authentication step. Reject unknown ABI
        # families/states instead of making an unproved pre-auth claim.
        # https://github.com/postgres/postgres/blob/REL_18_STABLE/src/interfaces/libpq/fe-connect.c
        need(180000<=pq.version()<190000)
        milliseconds=max(1,int(remaining(deadline)*1000))
        options={**checked,'hostaddr':'127.0.0.1','password':checked.get('password',''),
            'passfile':os.devnull,'sslmode':'disable','gssencmode':'disable',
            'require_auth':'scram-sha-256','target_session_attrs':'any',
            'options':f'-c lock_timeout={min(3000,milliseconds)} -c statement_timeout={milliseconds}'}
        raw=connection=witness=borrowed=None
        try:
            raw=pq.PGconn.connect_start(make_conninfo(**options).encode())
            need(raw.status in (pq.ConnStatus.STARTED,pq.ConnStatus.MADE) and raw.socket>=0)
            original_socket=raw.socket
            _wait(raw,selectors.EVENT_WRITE,deadline)
            borrowed=socket.socket(fileno=original_socket)
            witness=_BackendWitness(self,borrowed)  # before the first connect_poll
            while True:
                remaining(deadline);witness.verify()
                need(raw.socket==original_socket)
                status=raw.connect_poll()
                need(raw.socket==original_socket)
                if status==pq.PollingStatus.OK:break
                if status==pq.PollingStatus.READING:_wait(raw,selectors.EVENT_READ,deadline)
                elif status==pq.PollingStatus.WRITING:_wait(raw,selectors.EVENT_WRITE,deadline)
                else:need(False)
            witness.verify();remaining(deadline)
            raw.nonblocking=1
            connection=_OwnedConnection(raw,row_factory=dict_row)
            connection._deadline=deadline
            connection.autocommit=autocommit
            connection._endpoint_witness=witness
            witness=None;raw=None
            # Only the wrapper is borrowed; libpq owns this socket's close.
            borrowed.detach();borrowed=None
            return connection
        except BaseException as primary:
            cleanup=[]
            for value,method in ((connection,'close'),(raw,'finish'),(witness,'close')):
                if value is not None:
                    try:getattr(value,method)()
                    except BaseException as error:cleanup.append(error)
            if cleanup:raise BaseExceptionGroup('NATIVE_DATABASE_CONNECT_AND_CLOSE_UNKNOWN',[primary,*cleanup]) from None
            raise
        finally:
            if borrowed is not None:borrowed.detach()
