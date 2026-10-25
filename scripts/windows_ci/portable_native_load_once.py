"""Preparation only: closed, bounded Windows Python/vendor loading candidate.

No PG asset, app entry, credentials, security mutation or system trust update.
Temporary files are retained until disposable-runner disposal, never recursively
deleted by pathname. Cooperative identity checks do not claim same-user attack
resistance or production directory/OWNER acceptance.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

from scripts.windows_portable import build, payload
from scripts.windows_ci import owned_job
from scripts.windows_ci import portable_native_load_probe as probe

WINDOW_APPROVED = False
EXPECTED_PARENT = 'd0b1403db07b76c152fc80a1b23070c974debad9'
EXPECTED_RUN_NUMBER = None  # Must be read and bound in a later approved change.
EXECUTION_REF = 'refs/heads/dev/portable-native-load-once-20261025'
LOCK_SHA256 = '05a1a24dba647e4f49a9988ee9fea6b67cfb2adf26275af277d8975aa3ba5154'
WORK_SECONDS = 180
NATIVE_SECONDS = 60
ROOT_SECONDS = 300
MAX_WORK_BYTES = 512 * 1024 * 1024
ASSET_BYTES = 20708411
ASSET_FILES = (
    'python-3.14.9-embed-amd64.zip',
    'wheels/annotated_doc-0.0.5-py3-none-any.whl',
    'wheels/annotated_types-0.8.0-py3-none-any.whl',
    'wheels/anyio-4.15.1-py3-none-any.whl',
    'wheels/certifi-2026.10.23-py3-none-any.whl',
    'wheels/click-8.5.0-py3-none-any.whl',
    'wheels/colorama-0.4.6-py2.py3-none-any.whl',
    'wheels/fastapi-0.142.2-py3-none-any.whl',
    'wheels/h11-0.16.0-py3-none-any.whl',
    'wheels/httpcore-1.0.9-py3-none-any.whl',
    'wheels/httpx-0.28.1-py3-none-any.whl',
    'wheels/idna-3.20-py3-none-any.whl',
    'wheels/opentelemetry_api-1.45.0-py3-none-any.whl',
    'wheels/psutil-7.2.2-cp37-abi3-win_amd64.whl',
    'wheels/psycopg-3.3.6-py3-none-any.whl',
    'wheels/psycopg_binary-3.3.6-cp314-cp314-win_amd64.whl',
    'wheels/pydantic-2.13.5-py3-none-any.whl',
    'wheels/pydantic_core-2.46.5-cp314-cp314-win_amd64.whl',
    'wheels/starlette-1.7.0-py3-none-any.whl',
    'wheels/typing_extensions-4.16.0-py3-none-any.whl',
    'wheels/typing_inspection-0.4.4-py3-none-any.whl',
    'wheels/tzdata-2026.5-py2.py3-none-any.whl',
    'wheels/uvicorn-0.54.0-py3-none-any.whl',
)
NEW_PATHS = frozenset((
    '.github/workflows/portable-native-load-once.yml',
    'scripts/windows_ci/portable_native_load_once.py',
    'scripts/windows_ci/portable_native_load_probe.py',
    'scripts/windows_ci/test_portable_native_load_once.py',
))


def require(value, reason):
    if not value:
        raise probe.ProbeRefused(reason)


def error_record(error):
    reason = str(error) if type(error) in (probe.ProbeRefused, owned_job.OwnedJobError) else 'UNEXPECTED_EXCEPTION'
    if not re.fullmatch('[A-Z][A-Z0-9_]{0,79}', reason): reason = 'UNEXPECTED_EXCEPTION'
    if type(error) is subprocess.TimeoutExpired: reason = 'NATIVE_DEADLINE'
    code = getattr(error, 'errno', None)
    return {'reason': reason, 'error_type': type(error).__name__,
            'errno': code if type(code) is int and 0 <= code <= 65535 else None}


def window_gate(context):
    require(WINDOW_APPROVED and probe.WINDOW_APPROVED and type(EXPECTED_RUN_NUMBER) is int,
            'WINDOW_NOT_APPROVED')
    require(context.get('GITHUB_ACTIONS') == 'true' and context.get('GITHUB_REPOSITORY') == 'T1doo/ParkWeave'
            and context.get('GITHUB_REF') == EXECUTION_REF and context.get('GITHUB_EVENT_NAME') == 'push'
            and context.get('GITHUB_RUN_ATTEMPT') == '1'
            and context.get('GITHUB_RUN_NUMBER') == str(EXPECTED_RUN_NUMBER)
            and context.get('NATIVE_PUBLIC') == 'true' and context.get('RUNNER_OS') == 'Windows',
            'HOSTED_INVOCATION_REFUSED')


def verify_source(repo, context):
    def git(*args):
        return subprocess.check_output(['git', '--no-optional-locks', *args], cwd=repo, timeout=10)
    require(git('rev-parse', 'HEAD').decode().strip() == context.get('GITHUB_SHA') and
            git('rev-parse', 'HEAD^').decode().strip() == EXPECTED_PARENT and
            not git('status', '--porcelain=v1'), 'SOURCE_OR_DIRTY_REFUSED')
    changed = set(git('diff', '--name-only', 'HEAD^', 'HEAD').decode().splitlines())
    require(changed and changed <= NEW_PATHS, 'INVOCATION_PATHS_REFUSED')
    for name in ('scripts/windows_portable/build.py', 'scripts/windows_portable/payload.py',
                 'scripts/windows_portable/runtime-assets.json', 'scripts/windows_ci/owned_job.py',
                 'scripts/windows_ci/job_stop_observation.py'):
        require((repo / name).read_bytes() == git('show', probe.PRODUCT_SOURCE + ':' + name), 'PRODUCT_SOURCE_DRIFT')
    for name in NEW_PATHS:
        require((repo / name).read_bytes() == git('show', 'HEAD:' + name), 'INVOCATION_SOURCE_DRIFT')


def selected_assets(raw):
    require(hashlib.sha256(raw).hexdigest() == LOCK_SHA256, 'LOCK_SOURCE_REFUSED')
    lock = json.loads(raw)
    rows = [a for a in lock['assets'] if a['kind'] in ('python', 'wheel')]
    require(len(rows) == 23 and {a['file'] for a in rows} == set(ASSET_FILES)
            and sum(a['bytes'] for a in rows) == ASSET_BYTES, 'ASSET_SET_REFUSED')
    return rows


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise probe.ProbeRefused('ASSET_REDIRECT_REFUSED')


def fetch_asset(row, deadline, *, opener=None, clock=time.monotonic):
    url = urllib.parse.urlsplit(row['url'])
    require(url.scheme == 'https' and url.hostname in ('www.python.org', 'files.pythonhosted.org')
            and not url.username and not url.password and not url.query and not url.fragment
            and url.port in (None, 443), 'ASSET_ORIGIN_REFUSED')
    require(clock() < deadline, 'PREPARATION_DEADLINE')
    if opener is None:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(row['url'], timeout=min(20, deadline - clock())) as response:
            require(response.status == 200 and response.geturl() == row['url'], 'ASSET_RESPONSE_REFUSED')
            result = bytearray()
            while True:
                require(clock() < deadline, 'PREPARATION_DEADLINE')
                chunk = response.read1(min(65536, row['bytes'] + 1 - len(result)))
                if not chunk:
                    break
                result.extend(chunk)
                require(len(result) <= row['bytes'], 'ASSET_BYTES_REFUSED')
    except urllib.error.HTTPError as error:
        raise probe.ProbeRefused('ASSET_HTTP_' + str(error.code)) from None
    require(len(result) == row['bytes'] and hashlib.sha256(result).hexdigest() == row['sha256'], 'ASSET_HASH_REFUSED')
    return bytes(result)


def identity(path):
    info = path.lstat()
    require(not path.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400,
            'WORKSPACE_OBJECT_CHANGED')
    return info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode)


class Workspace:
    """Fresh public-test-data directory. Never deletes files or foreign objects."""
    def __init__(self, base):
        self.root = Path(tempfile.mkdtemp(prefix='parkweave-native-load-', dir=base)).absolute()
        self.directories = {'': identity(self.root)}
        self.files = {}; self.total = 0; self.sequence = 0; self.evidence_bytes = 0
        self.mkdir('evidence')

    def check_directories(self):
        for name, expected in self.directories.items():
            require(identity(self.root / name) == expected, 'WORKSPACE_IDENTITY_CHANGED')

    def check_files(self):
        self.check_directories()
        for name, expected in self.files.items():
            require(probe.file_state(self.root / name) == expected, 'WORKSPACE_FILE_CHANGED')

    def mkdir(self, name):
        payload.safe_name(name)
        current = Path()
        for part in Path(name).parts:
            current /= part; key = current.as_posix()
            if key not in self.directories:
                self.check_directories(); (self.root / current).mkdir()
                self.directories[key] = identity(self.root / current)

    def put(self, name, raw):
        payload.safe_name(name)
        if '/' in name: self.mkdir(Path(name).parent.as_posix())
        self.check_directories()
        require(self.total + len(raw) <= MAX_WORK_BYTES, 'WORKSPACE_BYTE_BUDGET')
        path = self.root / name
        with path.open('xb') as output:
            require(output.write(raw) == len(raw), 'SHORT_WRITE')
        self.check_directories()
        observed, row = probe.file_state(path)
        require(row == {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}, 'WORKSPACE_WRITE_CHANGED')
        self.files[name] = observed, row; self.total += len(raw)
        return path

    def checkpoint(self, record):
        # New immutable checkpoint per stage: no replace/overwrite of an unknown file.
        self.sequence += 1
        raw = (json.dumps(dict(record, checkpoint_sequence=self.sequence), sort_keys=True) + '\n').encode()
        require(len(raw) <= 128 * 1024 and self.evidence_bytes + len(raw) <= 256 * 1024, 'EVIDENCE_BYTE_BUDGET')
        self.put('evidence/checkpoint-' + str(self.sequence).zfill(3) + '.json', raw)
        self.evidence_bytes += len(raw)
        # Closed immutable local bytes plus bounded live logs, not a directory
        # durability/power-loss claim. A failed checkpoint prevents dispatch.
        sys.stdout.write(raw.decode()); sys.stdout.flush()


def prepare(workspace, rows, deadline, checkpoint):
    files = {}
    for index, row in enumerate(rows):
        workspace.check_directories(); require(time.monotonic() < deadline, 'PREPARATION_DEADLINE')
        checkpoint(index, row['file'])  # Before dispatch, never a business/server success count.
        raw = fetch_asset(row, deadline)
        path = workspace.put('assets/' + row['file'], raw)
        members = payload.archive_files(path)
        for name, digest in row['license_files'].items():
            require(hashlib.sha256(members[name]).hexdigest() == digest, 'ASSET_LICENSE_REFUSED')
        if row['kind'] == 'wheel': build.verify_wheel(row, members, (3, 14, 9))
        for name, data in members.items():
            require(not name.endswith(('.pth', '.egg-link')) and '.data/' not in name, 'INSTALL_HOOK_REFUSED')
            target = ('runtime/python/' if row['kind'] == 'python' else 'vendor/') + name
            require(target.casefold() not in {n.casefold() for n in files}, 'SUBSET_COLLISION')
            files[target] = data
    files['runtime/python/python314._pth'] = build.PTH.replace(b'python312', b'python314')
    expected = payload.file_manifest(files)
    require(len(files) == 1351 and hashlib.sha256(probe.canonical(expected)).hexdigest() == probe.SUBSET_SHA256,
            'SUBSET_FINGERPRINT_REFUSED')
    for name, data in files.items():
        require(time.monotonic() < deadline, 'PREPARATION_DEADLINE')
        workspace.put('payload/' + name, data)
    checkpoint(len(rows), None)
    return expected


def child_environment(context, workspace):
    root = Path(context['SystemRoot'])
    return {'SystemRoot': str(root), 'WINDIR': str(root), 'PATH': str(root / 'System32'),
            'TEMP': str(workspace.root), 'TMP': str(workspace.root), 'PSYCOPG_IMPL': 'binary'}


def collect_report(stdout, stderr):
    stdout.seek(0); data = stdout.read(128 * 1024 + 1)
    stderr.seek(0); errors = stderr.read(128 * 1024 + 1)
    report = {'stdout_bytes': len(data), 'stderr_bytes': len(errors),
              'stderr_sha256': hashlib.sha256(errors).hexdigest()}
    require(len(data) <= 128 * 1024 and len(errors) <= 128 * 1024, 'PROBE_OUTPUT_BUDGET')
    if data:
        value = json.loads(data)
        require(type(value) is dict and set(value) <= {'status', 'reason', 'error_type', 'winerror',
                'module_name', 'product_source', 'pid', 'modules', 'business_requests',
                'database_connections', 'system_trust_modified'}, 'PROBE_REPORT_FIELDS_REFUSED')
        require(value.get('status') in ('OBSERVED', 'FAIL', 'NOT_RUN'), 'PROBE_REPORT_STATUS_REFUSED')
        for name in ('reason', 'error_type', 'module_name'):
            if name in value:
                require(type(value[name]) is str and re.fullmatch('[A-Za-z0-9_.-]{1,120}', value[name]),
                        'PROBE_REPORT_VALUE_REFUSED')
        if 'product_source' in value: require(value['product_source'] == probe.PRODUCT_SOURCE, 'PROBE_REPORT_SOURCE_REFUSED')
        if 'pid' in value: require(type(value['pid']) is int and 0 < value['pid'] < 2**32, 'PROBE_REPORT_PID_REFUSED')
        if 'winerror' in value:
            require(value['winerror'] is None or type(value['winerror']) is int and 0 <= value['winerror'] < 2**32,
                    'PROBE_REPORT_VALUE_REFUSED')
        for name in ('business_requests', 'database_connections'):
            if name in value: require(type(value[name]) is int and value[name] == 0, 'PROBE_REPORT_BUSINESS_REFUSED')
        if 'system_trust_modified' in value: require(value['system_trust_modified'] is False, 'PROBE_REPORT_BUSINESS_REFUSED')
        if 'modules' in value:
            require(type(value['modules']) is list and len(value['modules']) <= 1024, 'PROBE_REPORT_MODULES_REFUSED')
            for item in value['modules']:
                require(type(item) is dict and set(item) == {'kind', 'path'} and
                        item['kind'] in ('PACKAGE', 'SYSTEM_DIRECTORY'), 'PROBE_REPORT_MODULES_REFUSED')
                payload.safe_name(item['path'])
                require(item['path'].startswith(('runtime/python/', 'vendor/')) if item['kind'] == 'PACKAGE'
                        else item['path'].startswith('System32/') and item['path'][9:] in probe.SYSTEM_NAMES,
                        'PROBE_REPORT_MODULES_REFUSED')
        report['probe'] = value
    return report


class MonitoredBackend(owned_job.WindowsBackend):
    """Poll only our creation handle; output/path drift triggers original Job cleanup."""
    def __init__(self, workspace, outputs):
        super().__init__()
        self.workspace, self.outputs = workspace, outputs
        self.output_identities = [os.fstat(file.fileno()) for file in outputs]

    def wait(self, process, timeout):
        deadline = time.monotonic() + timeout
        while True:
            self.workspace.check_directories()
            for file, before in zip(self.outputs, self.output_identities):
                current = os.fstat(file.fileno()); named = Path(file.name).lstat()
                require((current.st_dev, current.st_ino) == (before.st_dev, before.st_ino) ==
                        (named.st_dev, named.st_ino), 'OUTPUT_IDENTITY_CHANGED')
                require(current.st_size <= 128 * 1024, 'PROBE_OUTPUT_BUDGET')
            remaining = deadline - time.monotonic()
            if remaining <= 0: raise subprocess.TimeoutExpired('OWNED_NATIVE_LOAD', timeout)
            state = self.win.WaitForSingleObject(process, min(50, max(1, int(remaining * 1000))))
            if state == self.win.WAIT_OBJECT_0: return self.win.GetExitCodeProcess(process)
            require(state == self.win.WAIT_TIMEOUT, 'OWNED_PROCESS_WAIT_REFUSED')


def run(repo, context):
    window_gate(context)
    started = time.monotonic()
    require(os.name == 'nt', 'WINDOWS_REQUIRED')
    verify_source(repo, context)
    rows = selected_assets((repo / 'scripts/windows_portable/runtime-assets.json').read_bytes())
    workspace = None
    result = {'status': 'PARTIAL', 'product_source': probe.PRODUCT_SOURCE, 'phase': 'PREPARATION',
              'invocation': {'sha': context['GITHUB_SHA'], 'ref': context['GITHUB_REF'],
                             'run_number': EXPECTED_RUN_NUMBER, 'attempt': 1},
              'primary_error': None, 'cleanup_errors': [], 'process_cleanup': 'NOT_STARTED',
              'file_cleanup': 'RETAINED_UNTIL_DISPOSABLE_RUNNER_DISPOSAL'}
    try:
        workspace = Workspace(context['RUNNER_TEMP']); workspace.checkpoint(result)
        def checkpoint(index, name):
            result['asset_completed_count'] = index; result['asset_in_flight'] = name
            workspace.checkpoint(result)
        expected = prepare(workspace, rows, started + WORK_SECONDS, checkpoint)
        contract = workspace.put('evidence/subset.json', probe.canonical({'files': expected}))
        root = workspace.root / 'payload'
        require(time.monotonic() < started + WORK_SECONDS, 'PREPARATION_DEADLINE')
        result['phase'] = 'NATIVE_LOAD'; workspace.checkpoint(result)
        executable = root / 'runtime/python/python.exe'
        workspace.check_files()
        require(time.monotonic() < started + WORK_SECONDS, 'PREPARATION_DEADLINE')
        with (workspace.root / 'evidence/stdout.json').open('x+b') as stdout, \
                (workspace.root / 'evidence/stderr.log').open('x+b') as stderr:
            backend = MonitoredBackend(workspace, (stdout, stderr))
            try:
                completed = owned_job.run([str(executable), '-I', '-B', '-S',
                    str(repo / 'scripts/windows_ci/portable_native_load_probe.py'), str(root), str(contract)],
                    timeout=NATIVE_SECONDS, stdout=stdout, stderr=stderr, cwd=workspace.root,
                    env=child_environment(context, workspace), _backend=backend)
            finally:
                try: result['probe_report'] = collect_report(stdout, stderr)
                except Exception as error: result['probe_report_error'] = error_record(error)
        result['process_cleanup'] = completed.cleanup
        require(completed.returncode == 0 and completed.cleanup == 'OWNED_TREE_STOPPED', 'NATIVE_PROCESS_FAILED')
        require('probe_report' in result and not result['probe_report']['stderr_bytes'], 'PROBE_REPORT_REFUSED')
        observation = result['probe_report'].get('probe', {})
        require(observation.get('status') == 'OBSERVED' and observation.get('product_source') == probe.PRODUCT_SOURCE
                and type(observation.get('pid')) is int and observation['pid'] == backend._owned_parent_pid,
                'PROBE_OBSERVATION_REFUSED')
        workspace.check_files()
        require(probe.verify_files(root, expected), 'FINAL_PAYLOAD_VERIFICATION_REFUSED')
        result['observation'] = observation
        result['phase'] = 'FINALIZATION'
        require(time.monotonic() < started + ROOT_SECONDS, 'ROOT_DEADLINE')
        result['status'] = 'OBSERVED_NOT_PRODUCT_ACCEPTANCE'
    except Exception as error:
        result['status'] = 'FAIL'; result['primary_error'] = error_record(error)
        result['process_cleanup'] = getattr(error, 'cleanup', result['process_cleanup'])
        if getattr(error, 'cleanup_error_category', None):
            result['cleanup_errors'].append({'error_type': error.cleanup_error_category})
    finally:
        result['elapsed_seconds'] = round(time.monotonic() - started, 3)
        if workspace is not None:
            try:
                workspace.check_directories()
                checkpoint_result = dict(result)
                if checkpoint_result['status'] == 'OBSERVED_NOT_PRODUCT_ACCEPTANCE':
                    checkpoint_result['status'] = 'PARTIAL_FINALIZATION'
                workspace.checkpoint(checkpoint_result)
            except Exception as error:
                result['status'] = 'FAIL'; result['cleanup_errors'].append(error_record(error))
        if time.monotonic() >= started + ROOT_SECONDS:
            result['status'] = 'FAIL'
            result['cleanup_errors'].append({'reason': 'ROOT_DEADLINE', 'error_type': 'ProbeRefused', 'errno': None})
        result['elapsed_seconds'] = round(time.monotonic() - started, 3)
    return result


def main():
    try:
        result = run(Path(__file__).resolve().parents[2], os.environ)
    except Exception as error:
        result = {'status': 'NOT_RUN', 'primary_error': error_record(error)}
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] == 'OBSERVED_NOT_PRODUCT_ACCEPTANCE' else 2


if __name__ == '__main__':
    raise SystemExit(main())
