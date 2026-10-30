"""Actual harmless Linux private sleep/true copies; Windows handle stand-ins.

No PostgreSQL, credentials, model, network, Windows API or ACL mutation runs.
"""
import ctypes as C
import errno
from hashlib import sha256
import json
import os
from pathlib import Path
import pickle
import shutil
import signal
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from .directories import PrivateDirectories, LeaseRefused
from . import processes as p
from . import windows_process_handles as w


@unittest.skipUnless(sys.platform == 'linux', 'actual Linux harmless process profile only')
class ActualProcessChecks(unittest.TestCase):
    def setUp(self):
        self.fd_count = len(os.listdir('/proc/self/fd'))
        self.temp = tempfile.TemporaryDirectory(prefix='parkweave-owned-process-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'instance'
        self.directories = PrivateDirectories(self.temp.name)
        self.lease = self.directories.claim_fresh(str(self.root))
        (self.root / 'runtime').mkdir(mode=0o700)
        (self.root / 'runtime/probe').mkdir(mode=0o700)
        self.commands = {}
        for name in ('sleep', 'true'):
            dest = self.root / 'runtime/probe' / name
            shutil.copyfile(Path('/usr/bin') / name, dest); dest.chmod(0o700)
            raw = dest.read_bytes()
            self.commands[name] = p.Command('runtime/probe/' + name, sha256(raw).hexdigest(), len(raw),
                                             ('5',) if name == 'sleep' else ())
        self.adapter = p.PrivateProcessAdapter(self.lease, self.commands)
        self.addCleanup(self.finish)

    def finish(self):
        for token, group in self.adapter._issued.values():
            if not group.attempted_stop: self.adapter.stop_owned(token)
            if not group.stopped:
                # Test-only disposal after a controlled observation fault has
                # ended. Exact retained capability, no PID lookup or new target.
                self.assertTrue(self.adapter.backend.stop(group, time.monotonic() + 2))
                self.adapter.backend.close_observed(group)
                group.executable.close()
        if self.lease.active: self.lease.release()
        self.assertEqual(len(os.listdir('/proc/self/fd')), self.fd_count)

    def state(self, token):
        return self.adapter._group(token)  # Test instrumentation only, never a public capability.

    def test_registration_precedes_real_exec_and_stop_reaps_exact_pidfd_child(self):
        registered = []
        def register(group):
            self.assertFalse(self.state(group).started)
            self.assertIn('pidfd', self.state(group).resources)
            image = os.readlink(f"/proc/{self.state(group).resources['pid']}/exe")
            self.assertNotEqual(image, str(self.root / 'runtime/probe/sleep'))
            registered.append(group)
        group = self.adapter.launch('sleep', register)
        self.assertEqual(registered, [group])
        self.assertEqual(os.readlink(f"/proc/{self.state(group).resources['pid']}/exe"), str(self.root / 'runtime/probe/sleep'))
        self.assertIsNone(self.adapter.observe(group))
        self.assertTrue(self.adapter.stop_owned(group))
        self.assertEqual(self.state(group).returncode, -signal.SIGTERM)
        self.assertTrue(self.state(group).resources['reaped'])
        self.assertEqual(self.adapter.describe(group)['registration'], 'ACKNOWLEDGED')
        print('ACTUAL_LINUX: registered gated pidfd child before fd-exec; private image observed; TERM exit/reap confirmed', flush=True)

    def test_natural_exit_observed_wnowait_then_reaped_once_without_signalling(self):
        group = self.adapter.launch('true', lambda cap: None)
        self.assertEqual(self.adapter.observe(group, 2), 0)
        self.assertNotIn('reaped', self.state(group).resources)
        with patch.object(signal, 'pidfd_send_signal', side_effect=AssertionError('unnecessary signal')):
            self.assertTrue(self.adapter.stop_owned(group))
            self.assertTrue(self.adapter.stop_owned(group))
        self.assertTrue(self.state(group).resources['reaped']); self.assertEqual(self.adapter.observe(group), 0)

    def test_actual_shared_adapter_child_has_no_ambient_database_or_provider_configuration(self):
        # Environment-only observation of our original harmless ELF child;
        # this is not a PostgreSQL/API/worker business or Windows observation.
        with patch.dict(os.environ, {'PGUNKNOWN':'SYNTHETIC_ENV_ONLY','pgpassword':'',
                'PgServiceFile':'SYNTHETIC_ENV_ONLY','GITHUB_TOKEN':'SYNTHETIC_ENV_ONLY',
                'PYTHONPATH':'SYNTHETIC_ENV_ONLY','HTTPS_PROXY':'SYNTHETIC_ENV_ONLY'}):
            token=self.adapter.launch('sleep',lambda cap:None)
            group=self.state(token);self.assertIsNone(self.adapter.observe(token))
            raw=Path('/proc',str(group.resources['pid']),'environ').read_bytes()
            environment=dict(row.split(b'=',1) for row in raw.split(b'\0') if row)
            self.assertFalse(any(key.upper().startswith(b'PG') for key in environment))
            self.assertFalse({b'GITHUB_TOKEN',b'PYTHONPATH',b'HTTPS_PROXY',b'HOME'}&environment.keys())
            self.assertEqual(environment[b'PATH'],os.fsencode(self.root/'runtime/probe'))
            for key in (b'TEMP',b'TMP',b'TMPDIR'):self.assertEqual(environment[key],os.fsencode(self.root))
            self.assertTrue(self.adapter.stop_owned(token));self.assertTrue(group.resources['reaped'])

    def test_registration_cannot_reenter_stop_and_close_before_creation_finishes(self):
        callbacks = []
        def register(token):
            with self.assertRaises(p.ProcessRefused): self.adapter.stop_owned(token)
            self.assertFalse(self.state(token).attempted_stop)
            callbacks.append(token)
        token = self.adapter.launch('sleep', register)
        self.assertEqual(callbacks, [token])
        self.assertTrue(self.adapter.stop_owned(token))

    def test_registration_error_never_executes_target_and_preserves_original_error(self):
        original = ValueError('private registration detail')
        def register(cap): raise original
        with self.assertRaises(p.ProcessStartFailure) as result: self.adapter.launch('sleep', register)
        self.assertIs(result.exception.primary, original)
        group = result.exception.group
        self.assertFalse(self.state(group).started); self.assertTrue(self.state(group).stopped)
        self.assertEqual(self.state(group).registration, 'CALLED')
        self.assertNotIn('private registration detail', json.dumps(self.adapter.describe(group)))

    def test_exec_error_uses_cloexec_error_pipe_not_fake_success(self):
        with patch.object(p.LinuxSingleProcess, '_exec', side_effect=OSError(errno.ENOEXEC, 'injected exec failure')):
            with self.assertRaises(p.ProcessStartFailure) as result:
                self.adapter.launch('true', lambda cap: None)
        group = result.exception.group
        self.assertFalse(self.state(group).started); self.assertTrue(self.state(group).stopped)
        self.assertEqual(self.state(group).resources['exec_errno'], errno.ENOEXEC)
        self.assertEqual(self.adapter.describe(group)['outcome'], 'FAILED')
        self.assertEqual(self.adapter.describe(group)['exec_error_pipe'], 'ERROR_RECEIVED')

    def test_go_then_signal_before_exec_eof_is_not_target_or_ready_success(self):
        def signal_before_exec(group, env): os.kill(os.getpid(), signal.SIGTERM)
        with patch.object(p.LinuxSingleProcess, '_exec', side_effect=signal_before_exec):
            try: token = self.adapter.launch('sleep', lambda cap: None)
            except p.ProcessStartFailure as error: token = error.group
        # EOF may precede pidfd readability; either result must withhold image
        # and readiness claims, then confirm the exact original child's exit.
        self.assertTrue(self.adapter.stop_owned(token))
        state = self.state(token)
        self.assertTrue(state.exec_error_pipe_closed)
        self.assertFalse(state.target_image_observed); self.assertFalse(state.started)
        self.assertEqual(state.returncode, -signal.SIGTERM)
        self.assertTrue(state.stopped)
        self.assertEqual(self.adapter.describe(token)['business_readiness'], 'NOT_CHECKED')

    def test_quick_zero_exit_without_exec_never_retroactively_observes_target(self):
        with patch.object(p.LinuxSingleProcess, '_exec', side_effect=lambda group, env: os._exit(0)):
            token = self.adapter.launch('true', lambda cap: None)
        self.assertFalse(self.state(token).started)
        self.assertEqual(self.adapter.describe(token)['target_image'], 'NOT_OBSERVED')
        self.assertEqual(self.adapter.describe(token)['exec_error_pipe'], 'NO_ERROR_RECEIVED')
        self.assertTrue(self.adapter.stop_owned(token))
        self.assertEqual(self.state(token).returncode, 0)

    def test_pin_failure_after_fork_aborts_by_gate_eof_never_numeric_pid_signal(self):
        original = os.pidfd_open
        def opened(pid, flags=0):
            if pid != os.getpid(): raise OSError(errno.EMFILE, 'injected pidfd refusal')
            return original(pid, flags)
        with patch.object(os, 'pidfd_open', side_effect=opened), \
                patch.object(signal, 'pidfd_send_signal', side_effect=AssertionError('no pidfd authority')):
            with self.assertRaises(p.ProcessStartFailure) as result:
                self.adapter.launch('sleep', lambda cap: self.fail('unbound child registered'))
        group = result.exception.group
        self.assertTrue(self.state(group).stopped); self.assertFalse(self.state(group).started)
        self.assertEqual(self.state(group).returncode, 126); self.assertTrue(self.state(group).resources['reaped'])
        print('ACTUAL_LINUX: injected child pidfd-open failure -> gate EOF -> exit126/reap, zero signals', flush=True)

    def test_actual_kill_fallback_uses_same_retained_pidfd(self):
        group = self.adapter.launch('sleep', lambda cap: None)
        original, seen = signal.pidfd_send_signal, []
        def send(fd, sig, info, flags):
            seen.append((fd, sig))
            if sig == signal.SIGTERM: return None  # Deterministic lost-TERM stand-in.
            return original(fd, sig, info, flags)
        pidfd = self.state(group).resources['pidfd']
        with patch.object(signal, 'pidfd_send_signal', side_effect=send):
            self.assertTrue(self.adapter.stop_owned(group))
        self.assertEqual(seen, [(pidfd, signal.SIGTERM), (pidfd, signal.SIGKILL)])
        self.assertEqual(self.state(group).returncode, -signal.SIGKILL)

    def test_observation_failure_retains_capability_poisoning_lease_and_reopen(self):
        group = self.adapter.launch('sleep', lambda cap: None)
        original, calls = self.adapter.backend.observe, []
        def observe(cap, deadline):
            calls.append(True)
            if len(calls) == 2: raise OSError('injected wait observation failure')
            return original(cap, deadline)
        with patch.object(self.adapter.backend, 'observe', side_effect=observe):
            self.assertFalse(self.adapter.stop_owned(group))
        self.assertIn('pidfd', self.state(group).resources); os.fstat(self.state(group).resources['pidfd'])
        self.assertFalse(self.state(group).stopped); self.assertEqual(self.lease.status(), 'UNKNOWN')
        with patch.object(signal, 'pidfd_send_signal', side_effect=AssertionError('unknown auto retry')):
            self.assertFalse(self.adapter.stop_owned(group))
        with self.assertRaises(p.ProcessRefused): self.adapter.launch('true', lambda cap: None)
        fresh_adapter = p.PrivateProcessAdapter(self.lease, self.commands)
        with self.assertRaises(p.ProcessRefused): fresh_adapter.launch('true', lambda cap: None)
        # Read-only observation may learn exit, but never clears UNKNOWN.
        self.assertIsNotNone(self.adapter.observe(group, 2))
        self.assertEqual(self.adapter.describe(group)['outcome'], 'UNKNOWN')
        self.lease.release()
        with self.assertRaises(LeaseRefused): self.directories.open_existing(str(self.root))

    def test_foreign_copied_or_serialized_caps_cannot_signal_anything(self):
        group = self.adapter.launch('sleep', lambda cap: None)
        foreign = p.PrivateProcessAdapter(self.lease, self.commands)
        forged = p.OwnedGroup()
        with patch.object(signal, 'pidfd_send_signal', side_effect=AssertionError('foreign capability')):
            with self.assertRaises(p.ProcessRefused): foreign.stop_owned(group)
            with self.assertRaises(p.ProcessRefused): self.adapter.stop_owned(forged)
        with self.assertRaises(TypeError): pickle.dumps(group)
        self.assertTrue(self.adapter.stop_owned(group))

    def test_legitimate_token_cannot_replace_signal_or_close_authority(self):
        group = self.adapter.launch('sleep', lambda cap: None)
        original_fd = self.state(group).resources['pidfd']
        with patch.object(signal, 'pidfd_send_signal', side_effect=AssertionError('token mutation signalled')):
            for field, value in (('resources', {'pidfd': -999}), ('executable', object()),
                                 ('stopped', True), ('attempted_stop', False)):
                with self.assertRaises(AttributeError): setattr(group, field, value)
            self.assertFalse(hasattr(group, '__dict__'))
        self.assertEqual(self.state(group).resources['pidfd'], original_fd)
        self.assertTrue(self.adapter.stop_owned(group))

    def test_catalogue_is_frozen_and_hash_or_symlink_drift_refused_before_fork(self):
        with self.assertRaises(TypeError): self.adapter.commands['other'] = self.commands['true']
        exe = self.root / 'runtime/probe/true'; exe.write_bytes(b'changed')
        with patch.object(os, 'fork', side_effect=AssertionError('unverified image forked')):
            with self.assertRaises(p.ProcessRefused): self.adapter.launch('true', lambda cap: None)
        exe.unlink(); exe.symlink_to('/usr/bin/true')
        with patch.object(os, 'fork', side_effect=AssertionError('symlink image forked')):
            with self.assertRaises(OSError): self.adapter.launch('true', lambda cap: None)

    def test_go_time_image_or_directory_swap_is_refused_without_exec(self):
        def replace_after_register(group):
            (self.root / 'runtime/probe').rename(self.root / 'runtime/test-owned-old-probe')
            (self.root / 'runtime/probe').mkdir(mode=0o700)
        with self.assertRaises(p.ProcessStartFailure) as result:
            self.adapter.launch('sleep', replace_after_register)
        self.assertFalse(self.state(result.exception.group).started); self.assertTrue(self.state(result.exception.group).stopped)
        self.assertIsInstance(result.exception.primary, p.ProcessRefused)

    def test_start_deadline_expires_before_go_not_after_running_target(self):
        self.adapter.startup_seconds = .02
        with self.assertRaises(p.ProcessStartFailure) as result:
            self.adapter.launch('sleep', lambda cap: time.sleep(.04))
        self.assertFalse(self.state(result.exception.group).started); self.assertTrue(self.state(result.exception.group).stopped)

    def test_environment_failure_before_create_closes_pin_without_child(self):
        from parkweave import process_env
        original = ValueError('injected private environment failure')
        with patch.object(process_env, 'minimal_environment', side_effect=original), \
                patch.object(os, 'fork', side_effect=AssertionError('environment failure forked')):
            with self.assertRaises(p.ProcessStartFailure) as result:
                self.adapter.launch('true', lambda cap: None)
        self.assertIs(result.exception.primary, original)
        self.assertTrue(self.state(result.exception.group).stopped)
        self.assertIsNone(self.state(result.exception.group).executable.file)

    def test_partial_pipe_creation_failure_closes_all_already_returned_descriptors(self):
        original, calls = os.pipe2, []
        def pipe(flags):
            calls.append(True)
            if len(calls) == 2: raise OSError(errno.EMFILE, 'injected pipe failure')
            return original(flags)
        with patch.object(os, 'pipe2', side_effect=pipe), patch.object(os, 'fork', side_effect=AssertionError('partial pipes fork')):
            with self.assertRaises(p.ProcessStartFailure) as result:
                self.adapter.launch('true', lambda cap: None)
        self.assertTrue(self.state(result.exception.group).stopped)
        self.assertNotIn('pid', self.state(result.exception.group).resources)


class ProcessContractChecks(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'linux', 'Linux waitid contract')
    def test_pre_pidfd_observation_distinguishes_signal_from_normal_exit(self):
        backend = p.LinuxSingleProcess()
        group = SimpleNamespace(resources={'pid': 123}, returncode=None)
        for code, status, expected in ((os.CLD_EXITED, 126, 126), (os.CLD_KILLED, signal.SIGTERM, -signal.SIGTERM)):
            with patch.object(os, 'waitid', return_value=SimpleNamespace(si_status=status, si_code=code)) as wait:
                self.assertEqual(backend.observe(group, time.monotonic() + 1), expected)
                wait.assert_called_once_with(os.P_PID, 123, os.WEXITED | os.WNOHANG | os.WNOWAIT)


class WindowsProcessStandInChecks(unittest.TestCase):
    def backend(self, *, abort_error=None, query_zero=True):
        calls = []
        def terminate(process, code): calls.append(('abort_exact', process, code))
        def wait(process, timeout):
            calls.append(('wait_exact', process))
            if abort_error is not None: raise abort_error
            return 125
        def terminate_job(job, code): calls.append(('terminate_job', job)); return 1
        def query(job, cls, state, size, length):
            from scripts.windows_ci.owned_job import Accounting, DWORD
            C.cast(state, C.POINTER(Accounting))[0].ActiveProcesses = 0 if query_zero else 1
            C.cast(length, C.POINTER(DWORD))[0] = C.sizeof(Accounting)
            return 1
        original = SimpleNamespace(win=SimpleNamespace(TerminateProcess=terminate), wait=wait,
            kernel=SimpleNamespace(TerminateJobObject=terminate_job, QueryInformationJobObject=query),
            close=lambda handle: calls.append(('close_exact', handle)))
        backend = object.__new__(w.WindowsJobProcess); backend.original = original
        return backend, calls

    def test_unassigned_created_child_must_abort_and_wait_before_empty_job_can_confirm(self):
        backend, calls = self.backend()
        group = SimpleNamespace(resources=dict(job=77, process=88, thread=99, bound=False), returncode=None)
        self.assertTrue(backend.stop(group, time.monotonic() + 1))
        self.assertEqual(calls[:2], [('abort_exact', 88, 125), ('wait_exact', 88)])
        self.assertIn(('terminate_job',77), calls); self.assertTrue(group.resources['unbound_stopped'])

    def test_abort_wait_unknown_keeps_process_handle_does_not_substitute_job_zero(self):
        error = OSError('stand-in exact child wait failed')
        backend, calls = self.backend(abort_error=error)
        group = SimpleNamespace(resources=dict(job=77, process=88, thread=99, bound=False), returncode=None)
        with self.assertRaises(OSError): backend.stop(group, time.monotonic() + 1)
        self.assertNotIn(('terminate_job',77), calls)
        self.assertEqual(group.resources['process'],88)
        self.assertFalse(any(name=='close_exact' for name,*_ in calls))

    def test_close_consumes_creation_handles_once_not_pids(self):
        backend, calls = self.backend()
        group = SimpleNamespace(resources=dict(job=77, process=88, thread=99))
        backend.close_observed(group); backend.close_observed(group)
        self.assertEqual(calls, [('close_exact',99),('close_exact',88),('close_exact',77)])

    def created_backend(self, *, stdio_error=False, bind_error=False):
        backend, calls = self.backend()
        original = backend.original
        duplicate = iter((10,11,12))
        original.win.GetCurrentProcess = lambda: 1
        original.win.DUPLICATE_SAME_ACCESS = 2
        original.win.STARTF_USESTDHANDLES = 0x100
        original.win.DuplicateHandle = lambda *args: next(duplicate)
        def create(*args):
            calls.append(('create_suspended', args[0], args[5], tuple(args[-1].lpAttributeList['handle_list'])))
            return 88,99,100,101
        original.win.CreateProcess = create
        original.crt = SimpleNamespace(get_osfhandle=lambda fd: fd)
        original.kernel.CreateJobObjectW = lambda *args: 77
        original.kernel.SetInformationJobObject = lambda *args: 1
        def close(handle):
            calls.append(('close_exact',handle))
            if stdio_error and handle == 12: raise OSError('stand-in stdio close failed')
        original.close = close
        def bind(*args):
            calls.append(('bind_job',args))
            if bind_error: raise OSError('stand-in assignment failed')
        original.bind = bind
        original.resume = lambda thread: calls.append(('resume',thread))
        backend.birth = lambda handle: (100,123456)
        def image(process, flags, buffer, size):
            buffer.value = '\\Device\\Volume\\private.exe'; size._obj.value = len(buffer.value); return 1
        backend.image = image
        executable = SimpleNamespace(path='C:\\private\\private.exe', root_path='C:\\private',
            native_path='\\Device\\Volume\\private.exe', verify=lambda: calls.append(('verify_exe',)))
        group = SimpleNamespace(resources={}, command=SimpleNamespace(arguments=()), executable=executable, started=False, returncode=None)
        return backend, group, calls

    def test_job_configuration_and_close_double_fault_records_unknown_before_any_child(self):
        backend, calls = self.backend()
        backend.original.kernel.CreateJobObjectW = lambda *args: 77
        original = OSError('stand-in job configuration failed')
        def configure(*args):
            calls.append(('configure_job', args[0]))
            raise original
        backend.original.kernel.SetInformationJobObject = configure
        def close(handle):
            calls.append(('close_unknown', handle))
            raise OSError('stand-in job close unknown')
        backend.original.close = close
        lease = SimpleNamespace(status=lambda: 'CLUSTER', mark_unknown=lambda phase: calls.append(('mark_unknown', phase)))
        command = p.Command('runtime/private.exe', '0' * 64, 1, model='WINDOWS_JOB')
        adapter = p.PrivateProcessAdapter(lease, {'app': command}, _backend=backend)
        executable = SimpleNamespace(path='/private/runtime/private.exe', close=lambda: calls.append(('close_exe',)))
        registered = []
        with patch.object(p, 'PinnedExecutable', return_value=executable):
            with self.assertRaises(p.ProcessStartFailure) as result:
                adapter.launch('app', lambda token: registered.append(token))
        self.assertIs(result.exception.primary, original)
        self.assertEqual(registered, [result.exception.group])
        self.assertEqual(calls[0], ('configure_job', 77))
        self.assertIn(('terminate_job', 77), calls)
        self.assertIn(('close_unknown', 77), calls)
        self.assertIn(('mark_unknown', 'RUNNING'), calls)
        self.assertFalse(adapter._group(result.exception.group).stopped)
        self.assertEqual(adapter.describe(result.exception.group)['outcome'], 'UNKNOWN')
        before = list(calls)
        self.assertFalse(adapter.stop_owned(result.exception.group))
        self.assertEqual(calls, before)  # Unknown handle never retried.
        # Test fixture pin has no OS resource; the real adapter retains its pin
        # on failed cleanup and must not report a usable/reopenable instance.

    def test_created_handles_survive_stdio_cleanup_error_before_job_assignment(self):
        backend, group, calls = self.created_backend(stdio_error=True)
        registered = []
        def register(cap): registered.append(dict(cap.resources))
        with patch('subprocess.STARTUPINFO', SimpleNamespace, create=True):
            with self.assertRaises(BaseExceptionGroup): backend.create(group,register,{},time.monotonic()+1)
        self.assertEqual(registered,[{'job':77}])
        self.assertEqual((group.resources['process'],group.resources['thread'],group.resources['bound']),(88,99,False))
        self.assertFalse(group.started)
        self.assertEqual(group.resources['stdio_close_unknown'],[12])
        self.assertEqual([x for x in calls if x[0]=='create_suspended'],
                         [('create_suspended','C:\\private\\private.exe',0x4|0x400|0x80000,(10,11,12))])
        self.assertTrue(backend.stop(group,time.monotonic()+1))
        self.assertIn(('abort_exact',88,125),calls)

    def test_worker_stdio_uses_private_pipes_and_closes_owned_crt_descriptors(self):
        before=len(os.listdir('/proc/self/fd')) if sys.platform=='linux' else None
        backend,group,calls=self.created_backend()
        group.command.stdio_contract='WORKER_READINESS_V1'
        with patch('subprocess.STARTUPINFO',SimpleNamespace,create=True):
            backend.create(group,lambda cap:None,{},time.monotonic()+1)
        self.assertNotIn('worker_go_r',group.resources);self.assertNotIn('worker_ready_w',group.resources)
        self.assertIn('worker_go_w',group.resources);self.assertIn('worker_ready_r',group.resources)
        self.assertTrue(backend.stop(group,time.monotonic()+1));backend.close_observed(group)
        if before is not None:self.assertEqual(len(os.listdir('/proc/self/fd')),before)

    def test_child_stdio_crt_close_unknown_never_signs_whole_stop(self):
        before=len(os.listdir('/proc/self/fd'))
        backend,group,calls=self.created_backend()
        group.command.stdio_contract='WORKER_READINESS_V1'
        original=os.close;unknown=[]
        def close_once(fd):
            original(fd)
            if not unknown:
                unknown.append(fd);raise OSError('injected close outcome unknown')
        with patch('subprocess.STARTUPINFO',SimpleNamespace,create=True),patch.object(os,'close',side_effect=close_once):
            with self.assertRaises(BaseExceptionGroup):backend.create(group,lambda cap:None,{},time.monotonic()+1)
        self.assertEqual(group.resources['stdio_close_unknown'],[('CRT',unknown[0])])
        group.creating=False;group.attempted_stop=False;group.stopped=False;group.errors=[];group.operation_lock=threading.Lock()
        group.executable.close=lambda:None
        marks=[];lease=SimpleNamespace(mark_unknown=lambda phase:marks.append(phase))
        adapter=p.PrivateProcessAdapter(lease,{'app':p.Command('runtime/private.exe','0'*64,1,model='WINDOWS_JOB')},_backend=backend)
        token=p.OwnedGroup();adapter._issued[id(token)]=(token,group)
        self.assertFalse(adapter.stop_owned(token));self.assertTrue(adapter.unknown);self.assertEqual(marks,['RUNNING'])
        self.assertFalse(group.stopped)
        self.assertEqual(len(os.listdir('/proc/self/fd')),before)

    def test_assignment_failure_never_resumes_and_exact_unassigned_handle_is_stopped(self):
        backend, group, calls = self.created_backend(bind_error=True)
        with patch('subprocess.STARTUPINFO', SimpleNamespace, create=True):
            with self.assertRaises(OSError): backend.create(group,lambda cap: None,{},time.monotonic()+1)
        self.assertFalse(group.resources['bound']); self.assertFalse(group.started)
        self.assertFalse(any(x[0]=='resume' for x in calls))
        self.assertTrue(backend.stop(group,time.monotonic()+1))
        self.assertIn(('abort_exact',88,125),calls)


if __name__ == '__main__': unittest.main()
