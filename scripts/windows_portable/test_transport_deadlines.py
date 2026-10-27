"""Linux owned helper + synthetic PostgreSQL wire stalls; no PG/business.

Native Windows pipe/Job execution remains NOT_RUN. Tests create no credentials.
"""
import hashlib
import os
from pathlib import Path
import shutil
import select
import socket
import struct
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from .directories import PrivateDirectories
from . import processes as p
from . import isolated_pipe as pipe
from . import polling_database as db

NONCE='a'*32


@unittest.skipUnless(sys.platform=='linux','actual Linux pidfd helper only')
class PipeChecks(unittest.TestCase):
    def setUp(self):
        self.count=len(os.listdir('/proc/self/fd'))
        self.temp=tempfile.TemporaryDirectory(prefix='parkweave-pipe-deadline-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'instance'
        self.lease=PrivateDirectories(self.temp.name).claim_fresh(str(self.root))
        (self.root/'runtime').mkdir(mode=0o700);(self.root/'runtime/probe').mkdir(mode=0o700)
        dest=self.root/'runtime/probe/python';shutil.copyfile(Path(sys.executable).resolve(),dest);dest.chmod(0o700)
        # Test-only existing runtime stdlib locator; no install/download.
        (dest.parent/'pyvenv.cfg').write_text('home = '+str(Path(sys.executable).resolve().parent)+'\ninclude-system-site-packages = false\n')
        raw=dest.read_bytes()
        command=p.Command('runtime/probe/python',hashlib.sha256(raw).hexdigest(),len(raw),
                          ('--readiness-challenge',NONCE),model='WINDOWS_JOB',stdio_contract='WORKER_READINESS_V1')
        # Only parent business process identity is a stand-in. Every helper is
        # an actual copied Python image, gated fork, birth/pidfd and exact reap.
        self.adapter=p.PrivateProcessAdapter(self.lease,{'worker':command},_backend=SimpleNamespace(observe=lambda *a:None))
        self.token=p.OwnedGroup();self.state=p._ProcessState(command,None,resources={'pid':1,'birth':(1,2)},creating=False,started=True)
        self.adapter._issued[id(self.token)]=(self.token,self.state)
        self.fds=[];self.addCleanup(self.finish)

    def pair(self):
        r,w=os.pipe();self.fds.extend((r,w));return r,w

    def finish(self):
        self.assertEqual(self.state.resources.get('active_pipe_helpers',[]),[])
        for fd in self.fds:os.close(fd)
        self.lease.release()
        self.assertEqual(len(os.listdir('/proc/self/fd')),self.count)
        self.assertEqual(len(os.listdir('/proc/self/task')),1)

    def test_blocked_read_exits_reaps_and_releases_original_operation_lock(self):
        r,w=self.pair();self.state.resources['worker_ready_r']=r
        start=time.monotonic()
        with self.assertRaises(pipe.PipeFailure) as caught:self.adapter.worker_ready_frame(self.token,start+.85)
        self.assertEqual(caught.exception.phase,'DEADLINE');self.assertTrue(caught.exception.cleanup_confirmed)
        self.assertLess(time.monotonic()-start,.85)
        self.assertTrue(self.state.operation_lock.acquire(False));self.state.operation_lock.release()
        with self.assertRaisesRegex(p.ProcessRefused,'UNCONSUMED'):self.adapter.worker_ready_frame(self.token,time.monotonic()+1)
        print('ACTUAL_LINUX blocked read: helper exact pidfd TERM/reap, lock released, no replay',flush=True)

    def test_full_pipe_go_unknown_never_reissued_and_cleanup_confirmed(self):
        r,w=self.pair();self.state.resources.update(worker_go_w=w,ready_read_attempted=True,readiness_challenge=NONCE)
        os.set_blocking(w,False)
        while True:
            try:os.write(w,b'x'*4096)
            except BlockingIOError:break
        os.set_blocking(w,True)
        start=time.monotonic()
        with self.assertRaises(pipe.PipeFailure) as caught:self.adapter.worker_go(self.token,NONCE,start+.85)
        self.assertEqual(caught.exception.phase,'DEADLINE')
        self.assertTrue(caught.exception.go_may_have_been_sent);self.assertTrue(caught.exception.cleanup_confirmed)
        self.assertEqual(caught.exception.outcome,'UNKNOWN');self.assertLess(time.monotonic()-start,.85)
        with self.assertRaisesRegex(p.ProcessRefused,'EXACT_WORKER_GO'):self.adapter.worker_go(self.token,NONCE,time.monotonic()+1)
        print('ACTUAL_LINUX full pipe GO: UNKNOWN, helper exited/reaped, consumed once',flush=True)

    def test_success_read_go_and_written_but_late_result_is_unknown(self):
        r,w=self.pair();self.state.resources['worker_ready_r']=r
        os.write(w,b'{"synthetic":"bounded"}\n')
        self.assertEqual(self.adapter.worker_ready_frame(self.token,time.monotonic()+1),{'synthetic':'bounded'})
        r2,w2=self.pair();self.state.resources['worker_go_w']=w2
        self.adapter.worker_go(self.token,NONCE,time.monotonic()+1)
        self.assertTrue(select.select([r2],[],[],.5)[0])
        self.assertIn(b'"command":"GO"',os.read(r2,4096))
        old=self.state
        self.state=p._ProcessState(old.command,None,resources={'pid':1,'birth':(1,2),'worker_go_w':w2,'ready_read_attempted':True,'readiness_challenge':NONCE},creating=False,started=True)
        self.token=p.OwnedGroup();self.adapter._issued[id(self.token)]=(self.token,self.state)
        original=pipe._LinuxHelper.close_observed
        def delayed(backend,state):original(backend,state);time.sleep(.65)
        with patch.object(pipe._LinuxHelper,'close_observed',delayed):
            with self.assertRaises(pipe.PipeFailure) as caught:self.adapter.worker_go(self.token,NONCE,time.monotonic()+.65)
        self.assertEqual(caught.exception.phase,'LATE_RESULT');self.assertTrue(caught.exception.go_may_have_been_sent)
        self.assertTrue(select.select([r2],[],[],.5)[0])
        self.assertIn(b'"command":"GO"',os.read(r2,4096))
        with self.assertRaisesRegex(p.ProcessRefused,'EXACT_WORKER_GO'):self.adapter.worker_go(self.token,NONCE,time.monotonic()+1)
        print('ACTUAL_LINUX GO observed in borrowed pipe yet late result UNKNOWN; no resend',flush=True)

    def test_go_actual_write_with_malformed_ack_preserves_unknown_and_one_shot(self):
        r,w=self.pair();self.state.resources.update(worker_go_w=w,ready_read_attempted=True,readiness_challenge=NONCE)
        from parkweave.runtime_readiness import parse
        def corrupt(raw):return parse(b'{')  # Result decoding fault, after helper exit.
        with patch.object(pipe,'_decode',side_effect=corrupt):
            with self.assertRaises(pipe.PipeFailure) as caught:self.adapter.worker_go(self.token,NONCE,time.monotonic()+1)
        self.assertEqual(caught.exception.phase,'GO_UNKNOWN');self.assertTrue(caught.exception.cleanup_confirmed)
        self.assertTrue(caught.exception.go_may_have_been_sent);self.assertIsNotNone(caught.exception.__cause__)
        self.assertTrue(select.select([r],[],[],.5)[0])
        self.assertIn(b'"command":"GO"',os.read(r,4096))
        with self.assertRaisesRegex(p.ProcessRefused,'EXACT_WORKER_GO'):self.adapter.worker_go(self.token,NONCE,time.monotonic()+1)
        print('ACTUAL_LINUX GO written + injected malformed result: UNKNOWN with cause, no replay',flush=True)

    def test_cleanup_unknown_retains_exact_helper_and_persists_lease_unknown(self):
        r,w=self.pair();self.state.resources['worker_ready_r']=r
        with patch.object(pipe._LinuxHelper,'stop',return_value=False):
            with self.assertRaises(pipe.PipeFailure) as caught:self.adapter.worker_ready_frame(self.token,time.monotonic()+.75)
        self.assertFalse(caught.exception.cleanup_confirmed);self.assertTrue(self.adapter.unknown)
        self.assertEqual(self.lease.status(),'UNKNOWN')
        active=self.state.resources['active_pipe_helpers'];self.assertEqual(len(active),1)
        backend,state=active[0]
        self.assertIsNone(backend.observe(state,time.monotonic()))
        # Test-only disposal after fault injection ends, using retained pidfd.
        # Production never retries unknown cleanup; the owner remains UNKNOWN.
        self.assertTrue(backend.stop(state,time.monotonic()+1));backend.close_observed(state);state.executable.close()
        for key in ('pipe_result_r','pipe_result_w'):
            fd=state.resources.pop(key,None)
            if fd is not None:os.close(fd)
        active.clear()
        with self.assertRaises(p.ProcessRefused):self.adapter.worker_ready_frame(self.token,time.monotonic()+1)
        print('ACTUAL_LINUX injected stop refusal: live helper retained; lease UNKNOWN; test-only exact disposal',flush=True)


class DatabaseChecks(unittest.TestCase):
    def test_actual_libpq_connect_and_query_wire_blackholes_close_socket_by_shared_deadline(self):
        for phase in ('connect','query'):
            with self.subTest(phase=phase):
                before=len(os.listdir('/proc/self/fd'));events=[];errors=[]
                listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(1);listener.settimeout(2)
                port=listener.getsockname()[1]
                def exact(connection,count):
                    raw=b''
                    while len(raw)<count:
                        chunk=connection.recv(count-len(raw))
                        if not chunk:raise EOFError()
                        raw+=chunk
                    return raw
                def stub():
                    try:
                        with listener.accept()[0] as connection:
                            connection.settimeout(2)
                            size=struct.unpack('!I',exact(connection,4))[0]
                            startup=exact(connection,size-4)
                            if b'default_transaction_read_only=on' not in startup:raise AssertionError('startup read-only missing')
                            events.append('STARTUP')
                            if phase=='query':
                                # Minimal synthetic wire response, not PostgreSQL.
                                connection.sendall(b'R'+struct.pack('!II',8,0)+b'Z'+struct.pack('!I',5)+b'I')
                                if exact(connection,1)!=b'Q':raise AssertionError('not SELECT protocol')
                                size=struct.unpack('!I',exact(connection,4))[0]
                                sql=exact(connection,size-4)
                                if not sql.startswith(b'SELECT '):raise AssertionError('non-SELECT')
                                events.append('QUERY')
                            while True:
                                raw=connection.recv(1024)
                                if not raw:events.append('CLIENT_EOF');break
                    except ConnectionResetError:events.append('CLIENT_RESET')
                    except BaseException as error:errors.append(type(error).__name__)
                thread=threading.Thread(target=stub);thread.start()
                start=time.monotonic()
                try:
                    inputs=SimpleNamespace(application_dsn=f'host=127.0.0.1 port={port} user=parkweave_app dbname=parkweave sslmode=disable')
                    with self.assertRaises(db.DatabaseProbeFailure) as caught:db.probe(inputs,start+.35)
                    elapsed=time.monotonic()-start
                    self.assertEqual(caught.exception.phase,'DEADLINE');self.assertTrue(caught.exception.cleanup_confirmed)
                    self.assertLess(elapsed,.65)
                finally:thread.join(2);listener.close()
                self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
                self.assertIn('CLIENT_EOF' if 'CLIENT_EOF' in events else 'CLIENT_RESET',events)
                if phase=='query':self.assertIn('QUERY',events)
                self.assertEqual(len(os.listdir('/proc/self/fd')),before)
                print('ACTUAL_LIBPQ_SYNTHETIC_WIRE',phase,events,'elapsed',round(elapsed,4),'no real PG',flush=True)


if __name__=='__main__':unittest.main()
