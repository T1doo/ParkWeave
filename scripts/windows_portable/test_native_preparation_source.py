"""Actual ABI/source and negative pending-lifetime checks, native NOT_RUN."""
import ast
from contextlib import ExitStack
import ctypes as C
from pathlib import Path
from threading import RLock,Lock
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch

from . import native_layout_candidate as layout,initdb_client_candidate as client
from . import initdb_pipe_candidate as pipe
from .processes import ProcessRefused
from . import pgdata_candidate as pg
from .fixed_directories import FixedDirectoryLease
from .fixed_windows_journal import FixedWindowsFilesystem,NativeFixedLeaseAPI
from . import native_preparation_candidate as prep
from .fixed_directories import _exclusive_operation
from .fixed_secret_store import _under_lease
from . import endpoint_plan as ep
from .processes import Command
from threading import get_ident


class NativePreparationChecks(unittest.TestCase):
    def _refuse_new_ports(self, stack):
        # Patch the actual composition ports before construction; never mock the
        # owner gate or let any Windows security/credential operation execute.
        ports = [
            (prep.secrets, 'token_urlsafe'),
            (prep, '_under_lease'),
            (prep._NativeLayout, '__init__'),
            (prep, 'create_layout_held'),
            (prep.ep, '_register_held'),
            (prep._NativeFixedSecretStore, '__init__'),
            (prep._NativeFixedSecretStore, '_create_held'),
            (prep._NewDataTarget, '__init__'),
            (prep, '_create_target_held'),
            (prep.FixedDirectoryLease, 'checkpoint'),
            (prep._RestrictedPrimaryCandidate, '__init__'),
            (prep._RestrictedPrimaryCandidate, 'derive'),
            (prep._RestrictedPrimaryCandidate, 'prepare_default_dacl'),
            (prep._RestrictedPrimaryCandidate, 'prepare_owner'),
            (prep._OwnedInitdbPipe, '__init__'),
            (prep._OwnedInitdbPipe, 'create'),
            (prep, '_freeze'),
            (prep.RuntimePayloadPrerequisite, '__init__'),
            (prep._RestrictedInitdbBackend, '__init__'),
            (prep.PrivateProcessAdapter, '__init__'),
            (prep.PrivateProcessAdapter, 'launch'),
        ]
        return [stack.enter_context(patch.object(
            target, name, side_effect=AssertionError('SIDE_EFFECT_PORT_CALLED: '+name)))
            for target, name in ports]

    def test_composition_constructor_is_pure_and_original_owner_gate_precedes_all_new_ports(self):
        # Import outside the assertion: an import/dependency failure is a failure,
        # never evidence that the original owner gate refused initialization.
        from scripts.windows import lifecycle
        request=ep.EndpointRequest(54000,58000)
        command=Command('runtime/postgresql/bin/initdb.exe','a'*64,100,model='WINDOWS_JOB')
        with ExitStack() as stack:
            ports=self._refuse_new_ports(stack)
            owner=prep._NativePreparationController(ep.PlanMode.NEW,
                runtime=dict(source_commit='b'*40,manifest_sha256='c'*64),request=request,initdb=command)
            self.assertFalse(owner.started)
            self.assertEqual(owner._resources,[])
            self.assertIsNot(owner.spec.initdb,command)
            registered=[]
            with self.assertRaises(lifecycle.BoundaryError) as refused:
                owner.prepare(object(),deadline=time.monotonic()+5,register=registered.append)
            self.assertIs(type(refused.exception),lifecycle.BoundaryError)
            self.assertEqual(refused.exception.parkweave_lifecycle_reason,'OWNER_MUTATION_PAUSED')
            self.assertEqual(str(refused.exception),lifecycle.setup_readiness()['next_step'])
            self.assertEqual(registered,[])
            for port in ports:port.assert_not_called()
        self.assertFalse(owner.started);self.assertIsNone(owner.lease)
        self.assertFalse(owner.launch_ready)
        with self.assertRaisesRegex(prep.CandidateRefused,'^NATIVE_PREPARATION_CONTROLLER_NOT_ACCEPTED$'):
            prep.native_preparation_controller()

    def test_reopen_composition_refuses_new_inputs_and_invalid_lease_without_side_effects(self):
        runtime=dict(source_commit='b'*40,manifest_sha256='c'*64)
        with ExitStack() as stack:
            ports=self._refuse_new_ports(stack)
            with self.assertRaisesRegex(prep.CandidateRefused,'^NATIVE_PREPARATION_REFUSED$'):
                prep._NativePreparationController(ep.PlanMode.REOPEN,
                    runtime=runtime,request=ep.EndpointRequest(54000,58000))
            owner=prep._NativePreparationController(ep.PlanMode.REOPEN,runtime=runtime)
            with self.assertRaisesRegex(prep.CandidateRefused,'^NATIVE_PREPARATION_REFUSED$'):
                owner.prepare(object(),deadline=time.monotonic()+5)
            self.assertFalse(owner.started);self.assertEqual(owner._resources,[])
            for port in ports:port.assert_not_called()

    def test_preparation_cleanup_continues_after_first_owned_file_close_fails(self):
        owner=object.__new__(prep._NativePreparationController)
        owner.lease=None;owner._owned=[];owner.cleanup_errors=[];owner._secrets=None
        caps={'first':SimpleNamespace(close_attempted=False),'second':SimpleNamespace(close_attempted=False)}
        calls=[]
        def close(cap):
            calls.append(cap);caps[cap].close_attempted=True
            if cap=='first':raise OSError('INJECTED_FIRST_CLOSE')
        api=SimpleNamespace(caps=caps,unknown=[],close=close)
        owner._resources=[('store',SimpleNamespace(api=api,failed=False))]
        owner._cleanup()
        self.assertEqual(calls,['first','second'])
        self.assertTrue(owner.closed and owner.cleanup_errors)
        owner._cleanup()
        self.assertEqual(calls,['first','second'])

    def test_registration_callback_rechecks_in_original_held_gate_without_public_reentry(self):
        tree=ast.parse(Path(prep.__file__).read_text())
        callback=next(x for x in ast.walk(tree) if isinstance(x,ast.FunctionDef) and x.name=='record')
        lease=object.__new__(FixedDirectoryLease)
        lease._operation_owner=None;lease._operation_depth=0;lease._entry_lock=Lock()
        observed=[]
        def check(deadline):
            self.assertEqual(lease._operation_owner,get_ident())
            self.assertGreater(lease._operation_depth,0);observed.append('checked')
        owner=SimpleNamespace(_owned=[],_check=check)
        namespace=dict(self=owner,lease=lease,deadline=123,need=prep.need,
                       register=lambda token:observed.append('registered'),_under_lease=_under_lease)
        exec(compile(ast.Module(body=[callback],type_ignores=[]),'<actual-record-source>','exec'),namespace)
        @_exclusive_operation
        def invoke(lease):namespace['record'](object())
        invoke(lease)
        self.assertEqual(observed,['registered','checked'])

    def test_repeated_or_busy_create_cannot_replace_original_layout_binding(self):
        lease=object.__new__(FixedDirectoryLease)
        lease._operation_owner=None;lease._operation_depth=0;lease._entry_lock=Lock()
        lease.fs=object.__new__(FixedWindowsFilesystem);lease.fs.api=object.__new__(NativeFixedLeaseAPI)
        target=object.__new__(pg._NewDataTarget);target.lease=lease;original=object();target.layout=original
        pg._by_lease[lease]=target
        with self.assertRaises(Exception):target.create(layout=object())
        self.assertIs(target.layout,original)
        lease._entry_lock.acquire()
        try:
            with self.assertRaises(Exception):target.create(layout=object())
        finally:lease._entry_lock.release()
        self.assertIs(target.layout,original)

    def test_fixed_layout_scope_and_exclusive_native_creation_shape(self):
        self.assertEqual(layout.NAMES,('data','secrets','files','logs','tmp'))
        self.assertFalse(layout._NativeLayout.launch_ready)
        with self.assertRaises(layout.LayoutRefused):layout.native_private_layout()
        tree=ast.parse(Path(layout.__file__).read_text())
        method=next(x for x in ast.walk(tree) if isinstance(x,ast.FunctionDef) and x.name=='_create' and any(
            isinstance(y,ast.Call) and isinstance(y.func,ast.Attribute) and y.func.attr=='ntcreate' for y in ast.walk(x)))
        call=next(x for x in ast.walk(method) if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr=='ntcreate')
        self.assertEqual(call.args[7].value,2)
        self.assertEqual(call.args[6].value,3)
        need=next(x for x in ast.walk(method) if isinstance(x,ast.Call) and isinstance(x.func,ast.Name) and x.func.id=='need' and 'completed_nt_handle' in ast.unparse(x))
        own=next(x for x in ast.walk(method) if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr=='append' and ast.unparse(x.func)=='self.handles.append')
        self.assertLess(need.lineno,own.lineno)
        attrs={x.attr for x in ast.walk(tree) if isinstance(x,ast.Attribute)}
        self.assertFalse(attrs&{'SetSecurityInfo','SetNamedSecurityInfoW','DeleteFileW','RemoveDirectoryW','WriteFile'})

    def test_real_overlapped_memory_layout(self):
        self.assertEqual(C.sizeof(client.Overlapped),32)
        self.assertEqual(client.Overlapped.position.offset,16)
        self.assertEqual(client.Overlapped.event.offset,24)
        value=client.Overlapped();value.event=123;value.position.offset.high=7
        self.assertEqual(C.c_void_p.from_buffer(value,24).value,123)
        self.assertEqual(C.c_uint32.from_buffer(value,20).value,7)

    def _pending(self):
        server=object.__new__(pipe._OwnedInitdbPipe)
        server._lock=RLock();server._closed=False;server._ready=True;server.failed=False
        server._handle=777;server.cleanup_errors=[];server.winerror=None
        calls=[]
        op=object.__new__(client._Connection)
        op.server=server;op.pipe=777;op.event=888;op.ov=client.Overlapped()
        op.submitted=True;op.connect_returned=True;op.complete=False;op.connected=False
        op.cancel_attempted=False;op.event_close_attempted=False;op.event_closed=False;op.errors=[]
        op.kernel=SimpleNamespace(CancelIoEx=lambda *args:calls.append('cancel') or 1,
            WaitForSingleObject=lambda *args:258,GetOverlappedResult=lambda *args:0,
            CloseHandle=lambda *args:calls.append('close') or 1)
        server._kernel=op.kernel;server._pending_connection=op
        client._active[id(op)]=op
        self.addCleanup(client._active.pop,id(op),None)
        return server,op,calls

    def test_cancel_request_without_completion_keeps_pipe_event_and_overlapped(self):
        server,op,calls=self._pending()
        with patch.object(C,'get_last_error',return_value=996,create=True):
            self.assertFalse(op.cancel_and_observe(time.monotonic()+.01))
            self.assertFalse(op.cancel_and_observe(time.monotonic()+.01))
        self.assertEqual(calls,['cancel'])
        with self.assertRaises(ProcessRefused):op.finish()
        with self.assertRaises(pipe.PipeFailure):server.close()
        self.assertFalse(server._closed)
        self.assertEqual(server._handle,777)
        self.assertIs(server._pending_connection,op);self.assertIs(client._active[id(op)],op)
        self.assertEqual(calls,['cancel'])

    def test_unknown_event_close_is_not_retried_or_reported_finished(self):
        server,op,calls=self._pending();op.complete=True
        op.kernel.CloseHandle=lambda handle:calls.append('close') or 0
        with patch.object(C,'get_last_error',return_value=6,create=True):
            with self.assertRaises(ProcessRefused):op.finish()
            with self.assertRaises(ProcessRefused):op.finish()
        self.assertEqual(calls,['close'])
        self.assertIs(client._active[id(op)],op)
        self.assertFalse(op.event_closed)

    def test_event_close_exception_blocks_pipe_close_and_keeps_unknown_record(self):
        server,op,calls=self._pending();op.complete=True
        def close(handle):calls.append(handle);raise OSError('INJECTED_EVENT_CLOSE')
        op.kernel.CloseHandle=close
        with self.assertRaises(OSError):op.finish()
        self.assertTrue(server.cleanup_errors)
        with self.assertRaises(pipe.PipeFailure):server.close()
        self.assertFalse(server._closed);self.assertEqual(calls,[888])
        self.assertIs(client._active[id(op)],op)

    def test_verifier_has_no_resume_secret_or_pid_reopen_and_requires_live_original_handle(self):
        tree=ast.parse(Path(client.__file__).read_text())
        attrs={x.attr for x in ast.walk(tree) if isinstance(x,ast.Attribute)}
        self.assertFalse(attrs&{'ResumeThread','WriteFile','OpenProcess','DisconnectNamedPipe','GetNamedPipeInfo','ImpersonateNamedPipeClient'})
        method=next(x for x in ast.walk(tree) if isinstance(x,ast.FunctionDef) and x.name=='identity')
        text=ast.unparse(method)
        self.assertIn("self.kernel.WaitForSingleObject(r['process'], 0) == 258",text)
        self.assertIn("backend.birth(r['process']) == r['birth']",text)
        self.assertIn("backend.original.kernel.IsProcessInJob(r['process'], r['job']",text)
        self.assertIn('client.value == pid',text)
        with self.assertRaises(ProcessRefused):client.native_initdb_client()


if __name__=='__main__':unittest.main()
