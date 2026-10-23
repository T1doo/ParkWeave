"""Actual private pipes/ASGI; DB and Win APIs remain explicit stand-ins."""
import ctypes as C
import hashlib
import os
import socket
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from fastapi.testclient import TestClient
from parkweave.api import create_app
from parkweave.store import Store,digest,Denied
from parkweave import runtime_readiness as r
from . import application_readiness as a
from . import processes as p
from . import windows_endpoint as e

NONCE='0123456789abcdef0123456789abcdef'
ACTOR=dict(id='fictional-owner',park_id='fictional-park',org_id='fictional-org',role='enterprise_operator')
DB=dict(name='parkweave',role='parkweave_app',login='parkweave_app',oid=16400,address='127.0.0.1',port=55432,
        postmaster='2026-10-23 00:00:00+00',schema=32,safe=True)
TOKEN='SYNTHETIC_TEST_LITERAL_NOT_REAL_SESSION'


class ReadOnlyConnection:
    def __init__(self, store): self.store=store;self.row=None
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def execute(self,sql,params=None):
        self.store.sql.append(sql)
        if sql.startswith('SET '): self.row=None
        elif sql==r.DATABASE_SQL:self.row=dict(self.store.db)
        elif sql.startswith('SELECT * FROM principals WHERE token_hash='):
            self.row={**ACTOR,'active':True} if self.store.active and params==(digest(TOKEN),) else None
        else:raise AssertionError('unexpected readiness SQL')
        return self
    def fetchone(self):return self.row


class ReadOnlyStore(Store):
    def __init__(self):super().__init__('NO_REAL_DATABASE');self.sql=[];self.db=dict(DB);self.active=True
    def connect(self):return ReadOnlyConnection(self)
    def audit_denial(self,*args):raise AssertionError('readiness must not write audit')


class ApiAndPipeChecks(unittest.TestCase):
    def test_actual_asgi_route_authenticates_current_actor_read_only_and_refusal_does_not_audit(self):
        store=ReadOnlyStore()
        with TestClient(create_app(store)) as client:
            headers={'Authorization':'Bearer '+TOKEN,'X-ParkWeave-Readiness-Challenge':NONCE}
            result=client.get('/api/runtime/readiness',headers=headers)
            self.assertEqual(result.status_code,200);self.assertEqual(result.headers['cache-control'],'no-store')
            frame=result.json();r.validate_frame(frame,'api');self.assertEqual(frame['actor'],ACTOR)
            self.assertEqual(frame['database'],DB);self.assertFalse(frame['business_authority'])
            store.active=False
            self.assertEqual(client.get('/api/runtime/readiness',headers=headers).status_code,403)
            self.assertEqual(client.get('/api/runtime/readiness').status_code,401)
            store.active=True;store.db['safe']=False
            self.assertEqual(client.get('/api/runtime/readiness',headers=headers).status_code,403)
        self.assertTrue(store.sql);self.assertTrue(all(sql.startswith(('SET ','SELECT ')) for sql in store.sql))
        self.assertEqual(store.sql[0],'SET TRANSACTION READ ONLY')
        print('ASGI_WITH_FAKE_DB: current Bearer actor, read-only identity; revoked/unsafe rejected, zero audit writes',flush=True)

    def test_real_private_pipe_worker_blocks_until_exact_go_and_eof_or_wrong_nonce_never_starts(self):
        before=len(os.listdir('/proc/self/fd')) if os.name=='posix' else None
        for action in ('GO','wrong','EOF'):
            go_r,go_w=os.pipe();ready_r,ready_w=os.pipe();completed=[];errors=[]
            def worker():
                try:r.worker_handshake(ReadOnlyStore(),NONCE,source_fd=go_r,sink_fd=ready_w);completed.append('claim-permitted')
                except BaseException as error:errors.append(error)
            thread=threading.Thread(target=worker);thread.start()
            try:
                frame=r.read_frame(ready_r,time.monotonic()+2);r.validate_frame(frame,'worker')
                self.assertEqual(frame['state'],'WAITING_GO');self.assertTrue(thread.is_alive());self.assertEqual(completed,[])
                if action=='EOF':os.close(go_w);go_w=None
                else:r.write_frame(go_w,dict(schema='parkweave-worker-go/1',challenge=NONCE if action=='GO' else 'f'*32,command='GO'))
                thread.join(2);self.assertFalse(thread.is_alive())
                if action=='GO':self.assertEqual(completed,['claim-permitted']);self.assertEqual(errors,[])
                else:self.assertEqual(completed,[]);self.assertEqual(len(errors),1);self.assertIsInstance(errors[0],Denied)
            finally:
                if go_w is not None:os.close(go_w)
                thread.join(2)
                for fd in (go_r,ready_r,ready_w):os.close(fd)
        if before is not None:self.assertEqual(len(os.listdir('/proc/self/fd')),before)
        print('ACTUAL_PIPES_WITH_FAKE_DB: worker WAITING_GO; exact GO alone permits first claim; wrong/EOF refuse',flush=True)

    def test_actual_worker_main_first_claim_is_after_pipe_go_with_database_and_business_ports_fake(self):
        from parkweave import worker
        from parkweave import case_step_assignments,dispatch_notices
        store=ReadOnlyStore();store.claim=Mock(return_value=None);store.consume=Mock(return_value=False)
        go_r,go_w=os.pipe();ready_r,ready_w=os.pipe();errors=[];handshake=r.worker_handshake
        def enter(store,nonce):return handshake(store,nonce,source_fd=go_r,sink_fd=ready_w)
        def main():
            try:worker.main()
            except BaseException as error:errors.append(error)
        with patch.object(worker,'Store',return_value=store),patch.object(worker,'ExecutionGateway'), \
             patch.object(case_step_assignments,'from_environment'),patch.object(dispatch_notices,'consume',return_value=False), \
             patch.object(r,'worker_handshake',side_effect=enter),patch('sys.argv',['worker','--once','--readiness-stdio','--readiness-challenge',NONCE]), \
             patch.dict(os.environ,{'PARKWEAVE_DSN':'NO_REAL_DATABASE','PARKWEAVE_MODE':'LOCAL'}):
            thread=threading.Thread(target=main);thread.start()
            try:
                r.read_frame(ready_r,time.monotonic()+2);store.claim.assert_not_called();store.consume.assert_not_called()
                r.write_frame(go_w,dict(schema='parkweave-worker-go/1',challenge=NONCE,command='GO'))
                thread.join(2);self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
                store.claim.assert_called_once();store.consume.assert_called_once()
            finally:
                os.close(go_w);thread.join(2)
                for fd in (go_r,ready_r,ready_w):os.close(fd)

    def test_strict_frame_types_duplicate_keys_and_length_refuse(self):
        base=dict(schema='parkweave-worker-ready/1',challenge=NONCE,pid=42,database=dict(DB),mode='LOCAL',state='WAITING_GO',business_started=False)
        for change in ({'pid':42.0},{'business_started':0},{'database':{**DB,'safe':1}},{'database':{**DB,'oid':16400.0}}):
            with self.assertRaises(Denied):r.validate_frame({**base,**change},'worker')
        with self.assertRaises(Denied):r.parse(b'{"a":1,"a":1}')
        with self.assertRaises(Denied):r.parse(b'x'*(r.LIMIT+1))


class ConsumerAndEndpointChecks(unittest.TestCase):
    def fixture(self):
        lease=SimpleNamespace(_verify=lambda:None,status=lambda:'APPLICATION')
        backend=SimpleNamespace(observe=lambda *args:None,scope='STANDIN_ONLY')
        command=p.Command('runtime/private.exe','0'*64,1,model='WINDOWS_JOB',stdio_contract='WORKER_READINESS_V1')
        adapter=p.PrivateProcessAdapter(lease,{'app':command},_backend=backend)
        tokens=[]
        for pid in (41,42):
            token=p.OwnedGroup();state=p._ProcessState(command,object(),resources=dict(pid=pid,birth=(pid,100)),creating=False,started=True)
            adapter._issued[id(token)]=(token,state);tokens.append(token)
        app=a.RegisteredApplication(adapter,*tokens,12345,NONCE)
        probe=a.ExistingActorProbe(TOKEN,tuple(ACTOR.values()))
        return lease,adapter,app,probe,tokens

    def test_missing_native_endpoint_witness_refuses_before_database_or_http_send(self):
        lease,adapter,app,probe,tokens=self.fixture()
        with patch.object(a,'_get',side_effect=AssertionError('Bearer sent')) as get, \
             patch.object(a,'_database',side_effect=AssertionError('unexpected DB')) as db:
            with self.assertRaises(p.ProcessRefused):a.require_application_ready(lease,None,app,probe,tokens)
        get.assert_not_called();db.assert_not_called()

    def test_connected_socket_witness_refusal_precedes_any_application_bytes(self):
        _,adapter,app,_,_=self.fixture()
        connection=Mock();connection.recv.side_effect=AssertionError('read before identity')
        with patch.object(adapter,'require_endpoint_support'),patch.object(adapter,'verify_api_connection',side_effect=p.ProcessRefused('wrong owner')), \
             patch.object(a.socket,'socket') as factory:
            factory.return_value.__enter__.return_value=connection
            with self.assertRaises(p.ProcessRefused):a._get(app,TOKEN,NONCE,time.monotonic()+1)
        connection.connect.assert_called_once_with(('127.0.0.1',12345));connection.sendall.assert_not_called()

    def test_logical_pair_gate_waits_for_running_before_one_go_and_rejects_stale_actor(self):
        lease,adapter,app,probe,tokens=self.fixture()
        worker=dict(schema='parkweave-worker-ready/1',challenge=NONCE,pid=42,database=dict(DB),mode='LOCAL',state='WAITING_GO',business_started=False)
        api=dict(schema='parkweave-api-ready/1',challenge=NONCE,pid=41,database=dict(DB),actor=dict(ACTOR),mode='LOCAL',business_authority=False)
        # Logical consumer only: native connection and physical DB are NOT proven.
        with patch.object(adapter,'require_endpoint_support'),patch.object(a,'_database',return_value=dict(DB)), \
             patch.object(adapter,'worker_ready_frame',return_value=worker),patch.object(a,'_get',return_value=api), \
             patch.object(adapter,'worker_go') as go:
            receipt=a.require_application_ready(lease,None,app,probe,tokens)
            a.check_before_running(receipt);go.assert_not_called()
            lease.status=lambda:'RUNNING';a.activate_application(receipt);go.assert_called_once_with(app.worker,NONCE)
            with self.assertRaises(a.CandidateRefused):a.activate_application(receipt)
            lease.status=lambda:'APPLICATION';api['actor']={**ACTOR,'id':'different-owner'}
            with self.assertRaises(a.CandidateRefused):a.require_application_ready(lease,None,app,probe,tokens)

    def test_private_pipe_read_keeps_same_cap_stop_from_closing_descriptors(self):
        _,adapter,app,_,_=self.fixture();read_fd,write_fd=os.pipe()
        adapter._group(app.worker).resources['worker_ready_r']=read_fd
        values=[];errors=[];entered=threading.Event();original=r.read_frame
        def read(fd,deadline):entered.set();return original(fd,deadline)
        def observe():
            try:values.append(adapter.worker_ready_frame(app.worker,time.monotonic()+2))
            except BaseException as error:errors.append(error)
        with patch.object(r,'read_frame',side_effect=read),patch.object(adapter.backend,'stop',create=True) as stop:
            thread=threading.Thread(target=observe);thread.start()
            try:
                self.assertTrue(entered.wait(2))
                with self.assertRaisesRegex(p.ProcessRefused,'OWNED_OPERATION_BUSY'):adapter.stop_owned(app.worker)
                stop.assert_not_called()
                r.write_frame(write_fd,{'synthetic':'frame'})
                thread.join(2);self.assertFalse(thread.is_alive());self.assertEqual(values,[{'synthetic':'frame'}]);self.assertEqual(errors,[])
            finally:
                os.close(write_fd);thread.join(2);os.close(read_fd)

    def test_win32_endpoint_table_fixture_exact_tuple_owner_and_bounds(self):
        self.assertEqual(C.sizeof(e.Row),24);self.assertEqual(e.Table.rows.offset,4)
        client=('127.0.0.1',50000);server=('127.0.0.1',12345)
        address=int.from_bytes(socket.inet_aton('127.0.0.1'),'little')
        row=e.Row(5,address,socket.htons(server[1]),address,socket.htons(client[1]),41)
        raw=(1).to_bytes(4,'little')+bytes(row)
        e.unique_owner(raw,len(raw),client,server,41)
        for bad in (42,0):
            with self.assertRaises(p.ProcessRefused):e.unique_owner(raw,len(raw),client,server,bad)
        duplicated=(2).to_bytes(4,'little')+bytes(row)*2
        with self.assertRaises(p.ProcessRefused):e.unique_owner(duplicated,len(duplicated),client,server,41)
        with self.assertRaises(p.ProcessRefused):e.unique_owner(raw,len(raw)-1,client,server,41)
        row.state=2
        with self.assertRaises(p.ProcessRefused):e.unique_owner((1).to_bytes(4,'little')+bytes(row),len(raw),client,server,41)


if __name__=='__main__':unittest.main()
