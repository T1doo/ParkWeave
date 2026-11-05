"""Launch the fixed builder without ambient PostgreSQL configuration.

Hosted Windows images ship PGDATA/PGBIN/PGROOT. Exclude PG* only in the
child, preserving proxy/CA policy and the builder's original source admission.
No database process, source grant, retry, or parent environment mutation.
"""
import os
from pathlib import Path
import subprocess
import sys


def builder_environment(source):
    return {key: value for key, value in source.items()
            if not key.upper().startswith('PG')}


def main():
    command = [sys.executable, '-I', '-B', '-S',
               str(Path(__file__).with_name('native_candidate_build.py'))]
    try:
        result = subprocess.run(command, env=builder_environment(os.environ),
                                timeout=340, check=False)
        return result.returncode
    except subprocess.TimeoutExpired:
        print('{"candidate":"NOT_BUILT_OR_UNKNOWN","stage":"BUILDER_TIMEOUT"}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
