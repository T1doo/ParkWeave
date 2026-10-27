"""Real synthetic children: bounded waits, EOF, descendants, safe phase diagnostics."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('ci_native_command', ROOT / 'scripts/windows_ci/native_command.py')
NATIVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NATIVE)


def test_regular_output_arguments_and_stdin_eof(tmp_path):
    code = 'import sys,json;print(json.dumps([sys.argv[1:],sys.stdin.read()]))'
    result = NATIVE.execute(sys.executable, ['-c', code, 'SYNTHETIC path with spaces'],
                            'python_guard', 5, tmp_path, capture=True)
    assert result['exit_code'] == 0 and not result['timed_out']
    assert json.loads(result['stdout']) == [['SYNTHETIC path with spaces'], '']
    failed = NATIVE.execute(sys.executable, ['-c', 'raise SystemExit(17)'],
                            'pg_status', 5, tmp_path)
    assert failed['exit_code'] == 17 and not failed['timed_out']


def test_timeout_stops_only_exact_child_and_keeps_private_output(tmp_path):
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(20)'])
    try:
        result = NATIVE.execute(sys.executable,
                                ['-c', 'import time;print("SYNTHETIC_PRIVATE_OUTPUT",flush=True);time.sleep(20)'],
                                'pg_start', 1, tmp_path)
        assert result['exit_code'] == 124 and result['timed_out']
        assert result['cleanup'] == 'DIRECT_CHILD_STOPPED' and result['elapsed_seconds'] < 6
        assert unrelated.poll() is None
        assert 'stdout' not in result and 'SYNTHETIC_PRIVATE_OUTPUT' not in json.dumps(result)
        assert 'SYNTHETIC_PRIVATE_OUTPUT' in (tmp_path / result['stdout_file']).read_text()
    finally:
        unrelated.terminate()
        unrelated.wait(timeout=5)


def test_descendant_file_handle_does_not_hold_controller_completion(tmp_path):
    marker = tmp_path / 'descendant-finished'
    child = 'import time,pathlib;time.sleep(2);print("SYNTHETIC child",flush=True);pathlib.Path(' + repr(str(marker)) + ').write_text("done")'
    parent = 'import subprocess,sys;subprocess.Popen([sys.executable,"-c",' + repr(child) + ']);print("SYNTHETIC controller exited")'
    result = NATIVE.execute(sys.executable, ['-c', parent], 'pg_start', 5, tmp_path)
    assert result['exit_code'] == 0 and result['elapsed_seconds'] < 1.8
    assert not marker.exists()
    deadline = time.monotonic() + 5
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(.05)
    assert marker.read_text() == 'done'
    assert 'SYNTHETIC child' in (tmp_path / result['stdout_file']).read_text()


def test_unknown_phase_and_excessive_deadline_refused_without_launch(tmp_path):
    for phase, timeout in [('invented', 1), ('pg_status', 16), ('pg_start', 0)]:
        with pytest.raises(ValueError):
            NATIVE.execute(sys.executable, ['-c', 'raise SystemExit(99)'], phase, timeout, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_app_stop_uses_existing_os_whitelist(tmp_path, monkeypatch):
    for name in ('GITHUB_TOKEN', 'PGPASSWORD', 'PARKWEAVE_DSN', 'PARKWEAVE_OWNER_DSN', 'PARKWEAVE_TEST_OWNER_DSN'):
        monkeypatch.setenv(name, 'SYNTHETIC_POISON')
    result = NATIVE.execute(sys.executable, ['-c', 'import os,json;print(json.dumps(sorted(os.environ)))'],
                            'app_stop', 5, tmp_path, capture=True)
    assert result['exit_code'] == 0
    assert not any(name.startswith('PARKWEAVE_') or name in ('GITHUB_TOKEN', 'PGPASSWORD')
                   for name in json.loads(result['stdout']))


def test_powershell_bridge_preserves_arguments_and_public_phase_metadata(tmp_path):
    pwsh = ROOT / '.cache/powershell/bin/pwsh'
    if os.name == 'nt' or not pwsh.exists():
        pytest.skip('portable PowerShell bridge oracle; native Server separate')
    script = tmp_path / 'bridge.ps1'
    script.write_text(r'''
param($Module,$Python,$Logs)
$ErrorActionPreference='Stop'
Import-Module $Module -Force
$r=Invoke-BoundedNative $Python $Python @('-c','import sys,json;print(json.dumps(sys.argv[1:]))','SYNTHETIC value with spaces') 'python_guard' 5 $Logs -Capture
if ($r.exit_code -ne 0 -or @($r.stdout | ConvertFrom-Json)[0] -ne 'SYNTHETIC value with spaces') { throw 'bridge arguments changed' }
$r=Invoke-BoundedNative $Python $Python @('-c','import time;print("SYNTHETIC_PRIVATE_OUTPUT",flush=True);time.sleep(20)') 'pg_stop' 1 $Logs
if (!$r.timed_out -or $r.exit_code -ne 124) { throw 'bridge timeout not retained' }
''')
    from parkweave.process_env import minimal_environment
    env = minimal_environment(os.environ, XDG_CACHE_HOME=str(tmp_path / 'cache'),
                              XDG_CONFIG_HOME=str(tmp_path / 'config'), XDG_DATA_HOME=str(tmp_path / 'data'))
    result = subprocess.run([str(pwsh), '-NoProfile', '-NonInteractive', '-File', str(script),
                             str(ROOT / 'scripts/windows_ci/NativeCommand.psm1'), sys.executable, str(tmp_path)],
                            env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert 'python_guard START' in result.stdout and 'pg_stop END exit=124' in result.stdout
    assert 'SYNTHETIC_PRIVATE_OUTPUT' not in result.stdout + result.stderr
