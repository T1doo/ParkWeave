"""Dummy evidence and controlled clock only. No services/browser/CI."""
from contextlib import redirect_stdout
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
from scripts import fictional_park_browser_once as base
from scripts.fictional_park_restart_browser_once import PUBLIC_FILES

ROOT = Path(__file__).parent
PREFIX = b'PRIOR_STEP_CONTENT\n'
TOKEN = 'SYNTHETIC_UNIT_CREDENTIAL_ONLY_0123456789abcdef'
results = []

def fixture():
    root = Path(tempfile.mkdtemp(prefix='finalization-', dir=ROOT))
    candidate = root / 'candidate'; candidate.mkdir()
    for name in PUBLIC_FILES - {'result.json'}:
        (candidate / name).write_bytes(b'UNIT_FIXTURE_NOT_REAL_SCREENSHOT_OR_RECORD')
    summary = root / 'summary.md'; summary.write_bytes(PREFIX)
    return candidate, summary

def run(name, clocks, *, print_failure=False, permanent_stdout=False,
        summary_failure=False, permanent_summary=False, business_error=False,
        initial_seek_failure=False):
    public, summary = fixture(); report = dict(status='PASS', scope='UNIT_FIXTURE_ONLY')
    if business_error: report.update(status='FAIL', error_type='OriginalBusinessFailure', error='original business failure retained')
    output = StringIO(); real_print = print; calls = 0
    def emit(*args, **kwargs):
        nonlocal calls
        calls += 1
        if print_failure and (calls == 1 or permanent_stdout):
            raise BrokenPipeError('controlled stdout failure')
        real_print(*args, **kwargs)
    original_summary = base.write_summary; summary_calls = 0
    original_open = Path.open
    class SeekFailure:
        def __init__(self, stream): self.stream = stream
        def __getattr__(self, key): return getattr(self.stream, key)
        def seek(self, *args): raise OSError('controlled initial summary seek failure')
        def truncate(self, *args): raise AssertionError('unknown offset must never truncate')
    def opened(path, *args, **kwargs):
        stream = original_open(path, *args, **kwargs)
        return SeekFailure(stream) if initial_seek_failure and path == summary and args[0] == 'a+b' else stream
    def write_summary(*args):
        nonlocal summary_calls
        summary_calls += 1
        original_summary(*args)
        if summary_failure and (summary_calls == 1 or permanent_summary):
            raise OSError('controlled failure after summary bytes written')
    with redirect_stdout(output), patch.dict(base.os.environ, {'GITHUB_STEP_SUMMARY':str(summary)}), \
         patch.object(base.time, 'monotonic', side_effect=clocks), \
         patch('builtins.print', side_effect=emit), patch.object(base, 'write_summary', side_effect=write_summary), \
         patch.object(Path, 'open', new=opened):
        code = base.finish_report(report, [TOKEN], public, restart=True, started=0)
    terminal = json.loads((public.with_name('parkweave-fictional-browser-evidence')/'result.json').read_text())
    text = summary.read_text(); assert text.startswith(PREFIX.decode())
    observations=[]
    for line in output.getvalue().splitlines():
        data=json.loads(line.split(' ',1)[1] if line.startswith('FINALIZATION_OUTPUT_CHECKPOINT ') else line)
        observations.append(data); assert data['status'] != 'PASS'
    if name=='normal_success':
        assert code==0 and terminal['status']=='PASS' and '"status": "PASS"' in text
        assert all(x['status']=='PENDING_FINALIZATION' for x in observations)
    else:
        assert code==1 and terminal['status']=='FAIL' and '"status": "PASS"' not in text
        assert terminal['finalization_errors']
        if permanent_summary or initial_seek_failure: assert summary.read_bytes()==PREFIX
        else: assert '"status": "FAIL"' in text
        if business_error: assert terminal['error_type']=='OriginalBusinessFailure'
    assert TOKEN not in text and TOKEN not in output.getvalue()
    results.append(dict(name=name,result='PASS',exit_code=code,artifact_status=terminal['status'],
        summary_status='PREFIX_ONLY' if summary.read_bytes()==PREFIX else terminal['status'],
        stdout_statuses=[x['status'] for x in observations],
        error_type=terminal.get('error_type'),finalization_errors=terminal.get('finalization_errors',[])))

run('normal_success',[300,310,311,320,321])
run('deadline_after_PASS_summary_written',[300,310,311,361])
run('deadline_after_summary_close',[300,310,311,320,361])
run('stdout_exception',[300],print_failure=True)
run('stdout_permanent_exception',[],print_failure=True,permanent_stdout=True)
run('summary_exception_after_PASS_bytes_written',[300,310,311],summary_failure=True)
run('summary_permanent_exception_clears_own_section',[300,310,311],summary_failure=True,permanent_summary=True)
run('business_failure_retained_after_output_exception',[],print_failure=True,permanent_stdout=True,business_error=True)
run('opened_summary_initial_seek_failure_keeps_prefix',[],initial_seek_failure=True)
output=dict(source_sha='WORKTREE_CANDIDATE',source_sha256=sha256(Path(base.__file__).read_bytes()).hexdigest(),
    results=results,services_started=False,browser_started=False,CI_started=False,
    scope='Dummy bytes, deterministic clock and injected output errors only; no runtime acceptance')
(ROOT/'finalization-checks.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps(output,indent=2))
