"""Bounded commands; native_suite owns a Windows job, others a direct child.

No shell, process discovery or cluster control here.
"""
import argparse
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
    'native_suite': 900, 'app_stop': 60,
}


def execute(executable, arguments, phase, timeout, directory, capture=False):
    if phase not in LIMITS or not 0 < timeout <= LIMITS[phase]:
        raise ValueError('unknown phase or excessive command deadline')
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
            if phase == 'native_suite' and os.name == 'nt':
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
    if capture and result['exit_code'] == 0:
        if stdout_path.stat().st_size > 65536:
            result['exit_code'] = 126
            result['error_category'] = 'CaptureLimitExceeded'
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
