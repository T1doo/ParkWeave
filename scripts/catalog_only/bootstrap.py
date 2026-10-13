"""Pending-approval, one fresh hosted VM, catalog-only entry. Stdlib gate first."""
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import traceback
from contextlib import redirect_stdout, redirect_stderr

BRANCH = 'refs/heads/dev/f2-catalog-only-once-20261013'
APPROVAL_FILE = 'scripts/catalog_only/approval.json'
APPROVAL_REF = 'USER_CONFIRMED_CATALOG_ONLY_ONCE_20261013'
CASES = ('GATE', 'DEPENDENCIES', 'PG16_START', 'OWNED_EMPTY_STORAGE',
         'BEFORE_RIGHTS', 'BEFORE_CALLS', 'BEFORE_COMPARE', 'APPLY_FIX', 'AFTER_RIGHTS',
         'APP_CALL_DENIED', 'WRITER_CALL_ALLOWED', 'AFTER_COMPARE', 'CLEANUP')
STATES = ('PASS', 'FAIL', 'UNKNOWN', 'NOT_RUN')
COMPARISON = dict(call=('NOT_RUN', 'RETURNED', 'RAISED', 'UNKNOWN'),
    status=('NOT_RUN', 'UNKNOWN', 'PASS', 'REFUSED', 'APPROVAL_REQUIRED', 'MISSING_CONFIG', 'NOT_CONNECTED'),
    changes=('NOT_RUN', 'UNKNOWN', 'EMPTY', 'NONEMPTY'),
    nonpass=('NOT_RUN', 'UNKNOWN', 'NONE', 'APP_EXECUTE_ONLY', 'OTHER'))


def initial(sha):
    return dict(source_sha=sha if type(sha) is str and re.fullmatch('[a-f0-9]{40}', sha) else '0'*40,
        failure_logs='NOT_NEEDED',
        cases={name: 'NOT_RUN' for name in CASES},
        rights={name: 'NOT_RUN' for name in ('before_app', 'before_writer', 'after_app', 'after_writer')},
        comparisons={name: {key: 'NOT_RUN' for key in COMPARISON} for name in ('before', 'after')})


def public_summary(value):
    """Whitelist every field/value; never project arbitrary reports or exceptions."""
    if type(value) is not dict or set(value) != set(initial('')):
        raise ValueError('CLOSED_SUMMARY_REQUIRED')
    if type(value['source_sha']) is not str or not re.fullmatch('[a-f0-9]{40}', value['source_sha']):
        raise ValueError('CLOSED_SUMMARY_REQUIRED')
    if type(value['failure_logs']) is not str or value['failure_logs'] not in ('NOT_NEEDED', 'SAVED', 'UNAVAILABLE'):
        raise ValueError('CLOSED_SUMMARY_REQUIRED')
    for field, keys, states in [('cases', CASES, STATES),
            ('rights', initial('')['rights'], ('NOT_RUN', 'UNKNOWN', 'ALLOW', 'DENY'))]:
        if (type(value[field]) is not dict or set(value[field]) != set(keys) or
                any(type(v) is not str or v not in states for v in value[field].values())):
            raise ValueError('CLOSED_SUMMARY_REQUIRED')
    if type(value['comparisons']) is not dict or set(value['comparisons']) != {'before', 'after'}:
        raise ValueError('CLOSED_SUMMARY_REQUIRED')
    for row in value['comparisons'].values():
        if (type(row) is not dict or set(row) != set(COMPARISON) or
                any(type(v) is not str or v not in COMPARISON[k] for k, v in row.items())):
            raise ValueError('CLOSED_SUMMARY_REQUIRED')
    return json.loads(json.dumps(value))


def approved_context(env, uid, sha, approval):
    return (type(uid) is int and uid > 0 and type(sha) is str and
        re.fullmatch('[a-f0-9]{40}', sha) is not None and
        type(approval) is dict and set(approval) == {'approved', 'source_sha', 'approval_ref'} and
        approval['approved'] is True and approval['approval_ref'] == APPROVAL_REF and
        type(approval['source_sha']) is str and re.fullmatch('[a-f0-9]{40}', approval['source_sha']) is not None and
        all(env.get(k) == v for k, v in dict(CATALOG_REPOSITORY='T1doo/ParkWeave', CATALOG_REF=BRANCH,
            CATALOG_EVENT='push', CATALOG_ATTEMPT='1', CATALOG_NUMBER='1', CATALOG_PUBLIC='true',
            RUNNER_ENVIRONMENT='github-hosted', RUNNER_OS='Linux').items()))


def gate(checkout, sha, env):
    # A future explicitly approved commit may ONLY change the approval receipt.
    # The receipt is pending in this candidate; there is no currently valid entry.
    path = checkout / APPROVAL_FILE
    if not stat.S_ISREG(path.lstat().st_mode):raise PermissionError('REGULAR_APPROVAL_REQUIRED')
    def unique(pairs):
        if len(pairs) != len({k for k, _ in pairs}):raise ValueError('DUPLICATE_APPROVAL_KEY')
        return dict(pairs)
    approval = json.loads(path.read_text(), object_pairs_hook=unique)
    if not approved_context(env, os.geteuid(), sha, approval):
        raise PermissionError('PENDING_OR_UNAPPROVED_CONTEXT')
    def git(*args):
        return subprocess.check_output(['/usr/bin/git', *args], cwd=checkout,
            stderr=subprocess.PIPE, env={'LANG': 'C.UTF-8'}, timeout=5, text=True).strip()
    if (git('rev-parse', 'HEAD') != sha or git('rev-list', '--parents', '-n', '1', 'HEAD').split() != [sha, approval['source_sha']] or
            git('diff', '--name-only', approval['source_sha'], sha) != APPROVAL_FILE or
            git('status', '--porcelain')):
        raise PermissionError('EXACT_REVIEWED_SOURCE_AND_APPROVAL_ONLY_COMMIT_REQUIRED')
    previous = json.loads(git('show', approval['source_sha'] + ':' + APPROVAL_FILE))
    if previous != dict(approved=False, source_sha=None, approval_ref=None):
        raise PermissionError('ORIGINAL_PENDING_RECEIPT_REQUIRED')
    return approval['source_sha']


def bootstrap(sha):
    value = initial(sha); stage = 'GATE'; root = None
    try:
        checkout = Path.cwd()
        value['source_sha'] = gate(checkout, sha, os.environ)
        # Local O_EXCL claim also prevents a second invocation inside this VM.
        with open('/tmp/parkweave-catalog-only-once-20261013.claim', 'x') as claim:
            claim.write(value['source_sha'] + '\n')
        value['cases']['GATE'] = 'PASS'
        root = Path(tempfile.mkdtemp(prefix='parkweave-catalog-'))
        stage = 'DEPENDENCIES'; site = root / 'dependencies'
        packages = ['fastapi==0.142.2', 'uvicorn==0.54.0', 'psycopg[binary]==3.3.6',
                    'pydantic==2.13.5', 'httpx==0.28.1']
        with (root / 'dependencies.log').open('wb') as log:
            subprocess.run(['/usr/bin/python3.12', '-I', '-m', 'pip', '--isolated', 'install',
                '--disable-pip-version-check', '--no-cache-dir', '--no-compile', '--only-binary=:all:',
                '--target', str(site), *packages], env={'LANG': 'C.UTF-8', 'PATH': '/usr/bin:/bin'},
                stdout=log, stderr=log, timeout=180, check=True)
        value['cases']['DEPENDENCIES'] = 'PASS'
        stage = 'PG16_START'
        sys.path[:0] = [str(checkout), str(checkout / 'src'), str(site)]
        with (root / 'probe.log').open('w') as private, redirect_stdout(private), redirect_stderr(private):
            from scripts.catalog_only.probe import run
            candidate = public_summary(run(root, value['source_sha']))
        if (candidate['source_sha'] != value['source_sha'] or candidate['cases']['GATE'] != 'PASS' or
                candidate['cases']['DEPENDENCIES'] != 'PASS'):
            raise ValueError('BOUND_PROBE_RESULT_REQUIRED')
        value = candidate
    except BaseException:
        try:
            if root is None:raise OSError('NO_PRIVATE_LOG_TARGET')
            (root / 'bootstrap-failure.log').write_text(traceback.format_exc())
            value['failure_logs'] = 'SAVED'
        except BaseException:
            # A secondary logging failure must never escape to public stderr.
            value['failure_logs'] = 'UNAVAILABLE'
        value['cases'][stage] = 'FAIL'
        if stage == 'PG16_START':
            # No valid child cleanup observation: never guess that cleanup passed.
            value['cases']['CLEANUP'] = 'UNKNOWN'
    print(json.dumps(public_summary(value), sort_keys=True))
    return 0 if all(s == 'PASS' for s in value['cases'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(bootstrap(sys.argv[1] if len(sys.argv) == 2 else ''))
