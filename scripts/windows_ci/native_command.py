"""Bounded commands; native_suite owns a Windows job, others a direct child.

No shell, process discovery or cluster control here.
"""
import argparse
import math
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from parkweave.process_env import minimal_environment
try:
    from .owned_job import run as run_owned_job
except ImportError:
    from owned_job import run as run_owned_job

LIMITS = {
    'python_guard': 30, 'postgres_version': 15, 'allocate_port': 15,
    'initdb': 120, 'pg_status': 15, 'pg_start': 60, 'pg_stop': 60,
    'create_role': 30, 'create_database': 30, 'venv': 60,
    'pip_dependencies': 240, 'pip_project': 120, 'python_version': 15,
    'native_suite': 900, 'native_lifecycle': 300, 'native_validation': 1300,
    'summary_publish': 15, 'app_stop': 60,
}



def publication_capture(data):
    """A complete safe JSON plus complete LF annotation batch, never fragments."""
    text=data.decode('utf-8',errors='strict')
    public,end=json.JSONDecoder().raw_decode(text)
    if not isinstance(public,dict) or public.get('scope')!='WINDOWS_SERVER_ENGINEERING_NOT_WIN11' or public.get('production_R4')!='DISABLED' or public.get('whole_AT_EX')!='NOT_RUN' or public.get('Win11')!='NOT_RUN' or public.get('real_model_calls')!=0 or public.get('real_budget')!=0 or not isinstance(public.get('cases'),list) or len(text[:end].encode('utf-8'))>64*1024:
        raise ValueError('incomplete safe publication')
    lines=text[end:].splitlines()
    if lines and not lines[0]:lines=lines[1:]
    prefix='::notice title=ParkWeave safe diagnostics::'
    if not 1<=len(lines)<=8 or sum(len((line+'\n').encode('utf-8')) for line in lines)>16*1024:
        raise ValueError('incomplete annotation batch')
    for line in lines:
        if not line.startswith(prefix) or len((line+'\n').encode('utf-8'))>2048:
            raise ValueError('invalid annotation batch')
        value=json.loads(line[len(prefix):])
        if not isinstance(value,dict) or value.get('kind') not in ('publication','case'):
            raise ValueError('invalid annotation payload')
    # A short write may stop exactly after a complete line. Rebuild the
    # entire original allowlisted batch and compare every byte/omission field.
    from publish_summary import annotation_commands
    expected,_=annotation_commands(public)
    if lines!=expected:raise ValueError('incomplete or unknown annotation batch')
    # A truncated final write that omitted LF is not a complete batch.
    if not text.endswith('\n'):raise ValueError('incomplete annotation sink')
    return text.rstrip('\n')


def unavailable_publication():
    public={'scope':'WINDOWS_SERVER_ENGINEERING_NOT_WIN11','publication_state':'PUBLICATION_CAPTURE_UNAVAILABLE','cases':[],
            'real_model_calls':0,'real_budget':0,'production_R4':'DISABLED','whole_AT_EX':'NOT_RUN','Win11':'NOT_RUN'}
    return json.dumps(public)+'\n::notice title=ParkWeave safe diagnostics::{"kind":"publication","state":"ANNOTATIONS_UNAVAILABLE"}'

def uptime_milliseconds():
    if os.name == 'nt':
        import ctypes
        get_tick=ctypes.WinDLL('kernel32',use_last_error=True).GetTickCount64
        get_tick.argtypes=[];get_tick.restype=ctypes.c_ulonglong
        return int(get_tick())
    # Portable synthetic contract only, never Windows native evidence.
    return int(time.monotonic()*1000)


def execute(executable, arguments, phase, timeout, directory, capture=False):
    if phase not in LIMITS or not 0 < timeout <= LIMITS[phase]:
        raise ValueError('unknown phase or excessive command deadline')
    if phase in ('native_lifecycle','native_validation'):
        started = os.environ.get('PARKWEAVE_CI_JOB_STARTED', '')
        if not started.isascii() or not started.isdigit() or not 10 <= len(started) <= 12:
            raise ValueError('explicit shared job clock required')
        boot_started=os.environ.get('PARKWEAVE_CI_JOB_UPTIME','')
        if not boot_started.isascii() or not boot_started.isdigit() or not 1<=len(boot_started)<=16:
            raise ValueError('explicit shared uptime clock required')
        boot_epoch=int(boot_started);boot_now=uptime_milliseconds()
        epoch = int(started); now = time.time()
        remaining=min(epoch+1300-now,(boot_epoch+1300000-boot_now)/1000)
        if not math.isfinite(now) or epoch > now or boot_epoch>boot_now or timeout>remaining:
            raise ValueError('shared job deadline exhausted or excessive')
    executable = Path(executable)
    directory = Path(directory)
    if not executable.is_absolute() or not executable.is_file() or not directory.is_dir():
        raise ValueError('explicit executable and prepared private log directory required')
    prefix = phase + '-' + uuid.uuid4().hex
    stdout_path, stderr_path = (directory / (prefix + suffix) for suffix in ('.stdout', '.stderr'))
    started = time.monotonic()
    result = {'phase': phase, 'exit_code': 125, 'timed_out': False,
              'cleanup': 'NOT_NEEDED', 'stdout_file': stdout_path.name,
              'stderr_file': stderr_path.name}
    with stdout_path.open('xb') as stdout, stderr_path.open('xb') as stderr:
        try:
            if phase in ('native_suite','native_lifecycle','native_validation') and os.name == 'nt':
                try:
                    completed = run_owned_job([str(executable), *arguments], timeout=timeout,
                                              stdout=stdout, stderr=stderr)
                    result.update(exit_code=completed.returncode, cleanup=completed.cleanup)
                except subprocess.TimeoutExpired as error:
                    result.update(exit_code=124, timed_out=True, cleanup=error.cleanup)
                except Exception as error:
                    result.update(error_category=type(error).__name__,
                                  cleanup=getattr(error, 'cleanup', 'OWNED_TREE_STOP_UNCONFIRMED'))
                process = None
            else:
                # Descendants may inherit files, never our stdout pipe.
                process = subprocess.Popen([str(executable), *arguments], stdin=subprocess.DEVNULL,
                                           stdout=stdout, stderr=stderr, shell=False,
                                           env=minimal_environment(os.environ) if phase == 'app_stop' else None)
        except OSError as error:
            result['error_category'] = type(error).__name__
        else:
            try:
                if process is not None:
                    result['exit_code'] = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                result.update(exit_code=124, timed_out=True)
                try:
                    # Terminate only the exact Popen child; PG uses its owned Stop path.
                    process.kill()
                    process.wait(timeout=5)
                    result['cleanup'] = 'DIRECT_CHILD_STOPPED'
                except (OSError, subprocess.TimeoutExpired) as error:
                    result.update(cleanup='DIRECT_CHILD_STOP_UNCONFIRMED',
                                  cleanup_error_category=type(error).__name__)
    result['elapsed_seconds'] = round(time.monotonic() - started, 3)
    if capture and (result['exit_code'] == 0 or phase == 'summary_publish'):
        # Publisher is a separately bounded safe projector: <=64KiB JSON
        # plus <=16KiB annotations. Other captures retain their 64KiB cap.
        capture_limit=96*1024 if phase == 'summary_publish' else 65536
        if stdout_path.stat().st_size > capture_limit:
            if result['exit_code']==0:result['exit_code'] = 126
            result['error_category'] = 'CaptureLimitExceeded'
            if phase == 'summary_publish':result['stdout']=unavailable_publication()
        elif phase == 'summary_publish':
            try:
                if result['timed_out'] or result.get('error_category'):raise ValueError('publication failed before completion')
                result['stdout']=publication_capture(stdout_path.read_bytes())
            except (ValueError,UnicodeError,TypeError):
                # Keep the original nonzero failure; incomplete exit0 is failure.
                if result['exit_code']==0:result['exit_code']=126
                result['stdout']=unavailable_publication()
        else:
            result['stdout'] = stdout_path.read_text(encoding='utf-8', errors='replace').strip()
    (directory / (prefix + '.json')).write_text(json.dumps(result, indent=2) + '\n',encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', required=True)
    parser.add_argument('--phase', required=True, choices=LIMITS)
    parser.add_argument('--timeout', required=True, type=int)
    parser.add_argument('--log-dir', required=True)
    parser.add_argument('--capture', action='store_true')
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    arguments = args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments
    print(json.dumps(execute(args.exe, arguments, args.phase, args.timeout,
                             args.log_dir, args.capture)))


if __name__ == '__main__':
    main()
