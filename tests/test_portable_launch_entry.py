"""Cloud launch protocol checks. No Windows interpreter, setter, or native acceptance."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts.windows_portable import entry
from scripts.windows_portable import native_web_login
from scripts.windows_portable.endpoint_plan import PlanMode


@pytest.fixture
def launcher(tmp_path,monkeypatch):
    events=[]
    # Explicit entry boundary seam, never production identity/admission input.
    monkeypatch.setattr(entry,'verified_payload',lambda:(tmp_path,{'source_commit':'a'*40},b'FROZEN_MANIFEST'))
    gate=Mock(return_value={'status':'BLOCKED','reason':'OWNER_MUTATION_PAUSED'})
    monkeypatch.setattr(entry,'readiness',gate)
    enrollment=Mock(return_value=object())
    monkeypatch.setattr(native_web_login,'prompt_enrollment',enrollment)
    class Invocation:
        failure=None
        def create(self,path,use):return self.run('new',path,use)
        def reopen(self,path,use):return self.run('reopen',path,use)
        def run(self,mode,path,use):
            events.append((mode,path))
            if self.failure:raise self.failure
            use(SimpleNamespace(application=SimpleNamespace(port=58761)))
            return {'scope':'SYNTHETIC_LOCAL_PREPARATION_ONLY','protocol_test_only':True}
    instance=Invocation()
    factory=Mock(return_value=instance)
    monkeypatch.setattr(entry,'native_invocation',factory)
    return SimpleNamespace(root=tmp_path,events=events,gate=gate,enrollment=enrollment,
                           invocation=instance,factory=factory)


def answers(*values):
    source=iter(values)
    return lambda prompt:next(source)


def test_double_click_choice_reopens_existing_and_preserves_frozen_inputs(launcher):
    directory=launcher.root/'existing installation';directory.mkdir()
    assert entry.main([],read=answers('1',str(directory),''))==0
    assert launcher.events==[('reopen',str(directory))]
    launcher.gate.assert_not_called();launcher.enrollment.assert_not_called()
    args,kwargs=launcher.factory.call_args
    assert args[2]==directory and args[3] is PlanMode.REOPEN
    assert kwargs==dict(manifest_raw=b'FROZEN_MANIFEST',database_port=None,api_port=None,enrollment=None)


def test_explicit_reopen_and_default_with_instance_never_query_new_owner_gate(launcher):
    directory=launcher.root/'existing';directory.mkdir()
    for argv in (['--action','reopen','--instance',str(directory)],['--instance',str(directory)]):
        assert entry.main(argv,read=answers(''))==0
    assert launcher.events==[('reopen',str(directory))]*2
    launcher.gate.assert_not_called();launcher.enrollment.assert_not_called()


def test_missing_install_never_turns_into_new_and_ports_cannot_be_overridden(launcher,capsys):
    missing=launcher.root/'missing'
    assert entry.main(['--instance',str(missing)],read=answers())==2
    assert 'INSTALLATION_MISSING_USE_EXPLICIT_NEW' in capsys.readouterr().err
    existing=launcher.root/'existing';existing.mkdir()
    assert entry.main(['--action','reopen','--instance',str(existing),'--api-port','58761'],read=answers())==2
    assert not launcher.events and not launcher.factory.called and not launcher.enrollment.called


def test_new_and_status_keep_original_owner_pause_before_any_enrollment(launcher,capsys):
    for argv,read in (([],answers('2')),(['--action','new'],answers()),(['--action','status'],answers())):
        assert entry.main(argv,read=read)==2
    assert capsys.readouterr().out.count('OWNER_MUTATION_PAUSED')==3
    assert not launcher.events and not launcher.factory.called and not launcher.enrollment.called


def test_explicit_new_is_single_creation_with_exact_path_and_port_arguments(launcher):
    launcher.gate.return_value={'status':'READY'}  # Controlled branch exercise; no native gate changed.
    missing=launcher.root/'new installation'
    assert entry.main(['--action','new','--instance',str(missing),'--database-port','55432','--api-port','58761'],read=answers(''))==0
    args,kwargs=launcher.factory.call_args
    assert args[2]==missing and args[3] is PlanMode.NEW
    assert kwargs['database_port']==55432 and kwargs['api_port']==58761
    assert kwargs['enrollment'] is launcher.enrollment.return_value
    assert launcher.events==[('new',str(missing))] and not missing.exists()


def test_interactive_new_requires_explicit_directory_and_ports(launcher):
    launcher.gate.return_value={'status':'READY'}
    missing=launcher.root/'new'
    assert entry.main([],read=answers('2',str(missing),'55432','58761',''))==0
    assert launcher.events==[('new',str(missing))]


def test_existing_or_invalid_new_targets_refuse_before_enrollment(launcher):
    launcher.gate.return_value={'status':'READY'}
    existing=launcher.root/'exists';existing.mkdir()
    for path,ports in ((str(existing),['55432','58761']),('relative',['55432','58761']),
                       (str(launcher.root/'new'),['58761','58761'])):
        assert entry.main(['--action','new','--instance',path,'--database-port',ports[0],'--api-port',ports[1]],read=answers())==2
    assert not launcher.factory.called and not launcher.enrollment.called


def test_failed_initialization_and_failed_reopen_are_never_retried(launcher):
    launcher.gate.return_value={'status':'READY'}
    existing=launcher.root/'existing';existing.mkdir()
    launcher.invocation.failure=RuntimeError('controlled unavailable/uncertain lifecycle')
    assert entry.main(['--action','new','--instance',str(launcher.root/'new'),
        '--database-port','55432','--api-port','58761'],read=answers())==2
    assert entry.main(['--action','reopen','--instance',str(existing)],read=answers())==2
    assert [event[0] for event in launcher.events]==['new','reopen']
    assert launcher.factory.call_count==2


def test_duplicate_start_reaches_original_real_lease_lock_once(launcher):
    from scripts.windows_portable.fixed_directories import FixedPrivateDirectories
    from scripts.windows_portable.directories import LeaseRefused
    # Real Linux lease contention only, not Windows locking acceptance.
    directories=FixedPrivateDirectories(str(launcher.root))
    directory=launcher.root/'held'
    lease=directories.claim_fresh(str(directory))
    calls=[]
    def reopen(path,use):
        calls.append(path)
        other=directories.open_existing(path)
        other.release()
        pytest.fail('occupied lease unexpectedly acquired')
    launcher.invocation.reopen=reopen
    try:
        assert entry.main(['--instance',str(directory)],read=answers())==2
        assert calls==[str(directory)] and lease.active
        assert not launcher.enrollment.called
    finally:lease.release()


def test_cancel_invalid_choice_eof_and_status_do_not_launch(launcher):
    assert entry.main([],read=answers('0'))==0
    assert entry.main([],read=answers('unsupported'))==2
    def interrupted(prompt):raise EOFError()
    assert entry.main([],read=interrupted)==2
    assert not launcher.events and not launcher.factory.called


@pytest.mark.parametrize('signal',[EOFError,KeyboardInterrupt])
def test_stop_prompt_after_owned_start_returns_through_normal_lifecycle(launcher,signal):
    directory=launcher.root/'existing';directory.mkdir()
    def stop(prompt):raise signal()
    assert entry.main(['--instance',str(directory)],read=stop)==0
    assert launcher.events==[('reopen',str(directory))]
    launcher.gate.assert_not_called()


def test_batch_forwards_arguments_without_system_interpreter_or_delayed_expansion():
    batch=Path('scripts/windows_portable/ParkWeave.cmd').read_text()
    assert '"%~dp0runtime\\python\\python.exe" -I -B "%~dp0launcher\\entry.py" %*' in batch
    assert 'setlocal DisableDelayedExpansion' in batch


def test_nested_native_refusals_show_exact_safe_code_without_private_exception_text(launcher,capsys):
    from scripts.windows_portable.controller import ControlFailure
    directory=launcher.root/'existing';directory.mkdir()
    launcher.invocation.failure=ControlFailure('ACQUIRE',
        RuntimeError('WINDOWS_FIXED_FILE_NATIVE_ACCEPTANCE_NOT_ESTABLISHED'),[])
    assert entry.main(['--instance',str(directory)],read=answers())==2
    assert 'WINDOWS_FIXED_FILE_NATIVE_ACCEPTANCE_NOT_ESTABLISHED' in capsys.readouterr().err
    launcher.invocation.failure=RuntimeError('PRIVATE_TEST_VALUE_MUST_NOT_APPEAR')
    assert entry.main(['--instance',str(directory)],read=answers())==2
    assert 'PRIVATE_TEST_VALUE_MUST_NOT_APPEAR' not in capsys.readouterr().err


def test_integrity_failure_never_imports_application_or_prompts(launcher,monkeypatch,capsys):
    import builtins
    original=builtins.__import__
    def no_application(name,*args,**kwargs):
        if name.startswith(('scripts.windows_portable.controller','scripts.windows.lifecycle')):
            pytest.fail('application imported after failed payload integrity')
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',no_application)
    def fail():raise entry.PayloadRefused('PAYLOAD_HASH')
    monkeypatch.setattr(entry,'verified_payload',fail)
    assert entry.main([],read=Mock(side_effect=AssertionError('must not prompt')))==2
    assert 'PAYLOAD_HASH' in capsys.readouterr().err
    assert not launcher.factory.called and not launcher.enrollment.called


def test_lifecycle_reason_attribute_is_fixed_code_and_unverified_errors_are_type_only():
    from scripts.windows.lifecycle import BoundaryError
    error=BoundaryError('PRIVATE_TEST_EXPLANATION','OWNER_MUTATION_PAUSED')
    assert entry.public_failure_reason(error,verified=True)=='OWNER_MUTATION_PAUSED'
    assert entry.public_failure_reason(error)=='BoundaryError'


def test_system_crt_missing_or_unverified_has_official_help_without_install(launcher,capsys):
    directory=launcher.root/'existing';directory.mkdir()
    launcher.invocation.failure=RuntimeError('SYSTEM_CRT_PREREQUISITE_UNVERIFIED')
    assert entry.main(['--instance',str(directory)],read=answers())==2
    error=capsys.readouterr().err
    assert 'https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist' in error
    assert not launcher.enrollment.called and launcher.events==[('reopen',str(directory))]
