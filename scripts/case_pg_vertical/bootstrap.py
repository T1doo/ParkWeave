"""One reviewed fresh hosted VM; no host/credentials or existing PG entry."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import traceback

BRANCH = 'refs/heads/dev/f2-case-pg-vertical-once-20261013'
APPROVAL_FILE = 'scripts/case_pg_vertical/approval.json'
APPROVAL_REF = 'USER_CONFIRMED_CASE_PG_VERTICAL_ONCE_20261013'
STAGES = ('GATE', 'DEPENDENCIES', 'PG16_START', 'COLLECTION', 'TESTS', 'FIXTURE_CLEANUP', 'PG_CLEANUP')
STATES = ('PASS', 'FAIL', 'ERROR', 'SKIP', 'UNKNOWN', 'NOT_RUN')


def selection():
    rows = json.loads(Path('scripts/case_pg_vertical/selection.json').read_text())
    if (type(rows) is not list or len(rows) != 27 or
            any(type(r) is not dict or set(r) != {'id', 'nodeid', 'group'} or
                r['id'] != 'PG%02d' % (i+1) or r['group'] != ('PREFLIGHT' if i < 7 else 'CASE') or
                type(r['nodeid']) is not str or not r['nodeid'].startswith('tests/test_')
                for i, r in enumerate(rows)) or len({r['nodeid'] for r in rows}) != len(rows)):
        raise ValueError('EXACT_REVIEWED_SELECTION_REQUIRED')
    return rows


def initial(sha):
    return dict(source_sha=sha if type(sha) is str and re.fullmatch('[a-f0-9]{40}', sha) else '0'*40,
        stages={s: 'NOT_RUN' for s in STAGES}, tests={'PG%02d' % i: 'NOT_RUN' for i in range(1, 28)},
        failure_logs='NOT_NEEDED', diagnostics=[])


def public_summary(value):
    if type(value) is not dict or set(value) != set(initial('')):
        raise ValueError('CLOSED_RESULT_REQUIRED')
    if type(value['source_sha']) is not str or not re.fullmatch('[a-f0-9]{40}', value['source_sha']):
        raise ValueError('CLOSED_SOURCE_REQUIRED')
    for key in ('stages', 'tests'):
        if (type(value[key]) is not dict or set(value[key]) != set(initial('')[key]) or
                any(type(v) is not str or v not in STATES for v in value[key].values())):
            raise ValueError('CLOSED_STATES_REQUIRED')
    if value['failure_logs'] not in ('NOT_NEEDED', 'SAVED', 'UNAVAILABLE') or type(value['diagnostics']) is not list or len(value['diagnostics']) > 81:
        raise ValueError('CLOSED_DIAGNOSTICS_REQUIRED')
    for d in value['diagnostics']:
        if (type(d) is not dict or set(d) != {'id', 'phase', 'line', 'trace_sha256'} or
                d['id'] not in initial('')['tests'] or d['phase'] not in ('setup', 'call', 'teardown') or
                type(d['line']) is not int or not 0 <= d['line'] <= 10000 or
                type(d['trace_sha256']) is not str or not re.fullmatch('[a-f0-9]{64}', d['trace_sha256'])):
            raise ValueError('CLOSED_DIAGNOSTIC_REQUIRED')
    return json.loads(json.dumps(value))


def gate(checkout, sha, env):
    path = checkout / APPROVAL_FILE
    if not stat.S_ISREG(path.lstat().st_mode):raise PermissionError('REGULAR_APPROVAL_REQUIRED')
    def unique(pairs):
        if len(pairs) != len({k for k, _ in pairs}):raise ValueError('DUPLICATE_APPROVAL_KEY')
        return dict(pairs)
    approval = json.loads(path.read_text(), object_pairs_hook=unique)
    if (type(sha) is not str or not re.fullmatch('[a-f0-9]{40}', sha) or os.geteuid() <= 0 or
            type(approval) is not dict or set(approval) != {'approved', 'source_sha', 'approval_ref'} or
            approval['approved'] is not True or approval['approval_ref'] != APPROVAL_REF or
            type(approval['source_sha']) is not str or not re.fullmatch('[a-f0-9]{40}', approval['source_sha']) or
            any(env.get(k) != v for k, v in dict(VERTICAL_REPOSITORY='T1doo/ParkWeave', VERTICAL_REF=BRANCH,
                VERTICAL_EVENT='push', VERTICAL_ATTEMPT='1', VERTICAL_NUMBER='1', VERTICAL_PUBLIC='true',
                RUNNER_ENVIRONMENT='github-hosted', RUNNER_OS='Linux').items())):
        raise PermissionError('EXACT_NEW_ONCE_AUTHORIZATION_REQUIRED')
    def git(*args):
        return subprocess.check_output(['/usr/bin/git', *args], cwd=checkout, stderr=subprocess.PIPE,
            env={'LANG': 'C.UTF-8'}, timeout=5, text=True).strip()
    if (git('rev-parse', 'HEAD') != sha or git('rev-list', '--parents', '-n', '1', 'HEAD').split() != [sha, approval['source_sha']] or
            git('diff', '--name-only', approval['source_sha'], sha) != APPROVAL_FILE or git('status', '--porcelain') or
            json.loads(git('show', approval['source_sha']+':'+APPROVAL_FILE)) != dict(approved=False, source_sha=None, approval_ref=None)):
        raise PermissionError('REVIEWED_SINGLE_PARENT_APPROVAL_ONLY_REQUIRED')
    selection()
    return approval['source_sha']


def bootstrap(sha):
    result = initial(sha); root = None; stage = 'GATE'
    try:
        checkout = Path.cwd(); result['source_sha'] = gate(checkout, sha, os.environ)
        with open('/tmp/parkweave-case-pg-vertical-once-20261013.claim', 'x') as claim:
            claim.write(result['source_sha']+'\n')
        result['stages']['GATE'] = 'PASS'
        root = Path(tempfile.mkdtemp(prefix='parkweave-case-pg-'))
        stage = 'DEPENDENCIES'; site = root/'dependencies'; netrc = root/'empty.netrc'
        fd = os.open(netrc, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600); os.close(fd)
        with (root/'dependencies.log').open('wb') as log:
            subprocess.run(['/usr/bin/python3.12', '-I', '-m', 'pip', '--isolated', 'install', '--no-input',
                '--keyring-provider=disabled', '--disable-pip-version-check', '--no-cache-dir', '--no-compile',
                '--only-binary=:all:', '--target', str(site), 'fastapi==0.142.2', 'uvicorn==0.54.0',
                'psycopg[binary]==3.3.6', 'pydantic==2.13.5', 'httpx==0.28.1', 'pytest==9.1.1'],
                env={'LANG': 'C.UTF-8', 'PATH': '/usr/bin:/bin', 'NETRC': str(netrc), 'PIP_CONFIG_FILE': os.devnull},
                stdout=log, stderr=log, timeout=180, check=True)
        result['stages'][stage] = 'PASS'; stage = 'PG16_START'
        sys.path[:0] = [str(checkout), str(checkout/'src'), str(site)]
        from scripts.catalog_only.bootstrap import private_output
        with private_output(root/'private-pytest.log'):
            from scripts.case_pg_vertical.probe import run
            candidate = public_summary(run(root, result['source_sha']))
        if (candidate['source_sha'] != result['source_sha'] or
                any(candidate['stages'][s] != 'PASS' for s in ('GATE', 'DEPENDENCIES'))):
            raise ValueError('EXACT_PROBE_RESULT_REQUIRED')
        result = candidate
    except BaseException:
        result['stages'][stage] = 'FAIL'
        if stage == 'PG16_START':result['stages']['PG_CLEANUP'] = 'UNKNOWN'
        try:
            if root is None:raise OSError('NO_PRIVATE_TARGET')
            (root/'bootstrap-failure.log').write_text(traceback.format_exc()); result['failure_logs'] = 'SAVED'
        except BaseException:result['failure_logs'] = 'UNAVAILABLE'
    print(json.dumps(public_summary(result), sort_keys=True))
    return 0 if all(v == 'PASS' for key in ('stages', 'tests') for v in result[key].values()) else 1


if __name__ == '__main__':
    raise SystemExit(bootstrap(sys.argv[1] if len(sys.argv) == 2 else ''))
