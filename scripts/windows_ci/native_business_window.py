"""Fixed source approval for one disposable native BUSINESS trial, not READY.

The record is null by default. No caller path, environment switch, report or
previous four-file approval is accepted. A future approval commit may change
only this record and the disabled workflow, after executable source is frozen.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import threading
import time
import weakref

WORKFLOW = '.github/workflows/native-business-trial-once.yml'
RECORD = 'scripts/windows_ci/native_business_window.json'
OPERATIONS = frozenset(('NEW_TRIAL_ONLY_OBJECTS', 'OWN_DERIVED_TOKEN_OWNER',
    'OWN_DERIVED_TOKEN_DEFAULT_DACL', 'TEMP_CURRENT_USER_DPAPI_IDENTITIES',
    'PROTECTED_INITDB', 'OWN_PRIVATE_PG_API_WORKER', 'SYNTHETIC_TWO_ROLE_BUSINESS',
    'OWN_JOB_STOP_AND_REOPEN', 'FIXED_SLOT_AUXILIARY_PROBES','OWN_FIXED_SLOT_INTERRUPTION_CHILDREN',
    'TEMP_LOCAL_SERVICE_DPAPI_PEER','OWN_JOB_IMAGE_DEBUG_OBSERVATIONS'))


class WindowRefused(RuntimeError): pass


def need(value):
    if not value: raise WindowRefused('NATIVE_BUSINESS_SOURCE_WINDOW_REFUSED')


class SourceGrant:
    __slots__ = ('__weakref__',)
    def __reduce__(self): raise TypeError('source window cannot be transferred')
    def __copy__(self): raise TypeError('source window cannot be copied')
    def __deepcopy__(self, memo): raise TypeError('source window cannot be copied')


class VerifiedSource(SourceGrant): pass


@dataclass(frozen=True)
class FrozenWindow:
    repository: str
    ref: str
    job: str
    run_number: int
    run_id: str | None
    expires_utc: int
    reviewed_parent: str
    workflow_sha256: str
    archive_sha256: str
    archive_bytes: int
    manifest_sha256: str
    operations: tuple
    work_seconds: int
    cleanup_seconds: int


_issued = weakref.WeakKeyDictionary()
_verified = weakref.WeakKeyDictionary()
_spent = set()
CONTEXT_NAMES=('GITHUB_ACTIONS','RUNNER_ENVIRONMENT','RUNNER_OS','NATIVE_PUBLIC','GITHUB_REPOSITORY',
    'GITHUB_REF','GITHUB_JOB','GITHUB_EVENT_NAME','GITHUB_RUN_ATTEMPT','GITHUB_RUN_NUMBER','GITHUB_RUN_ID',
    'GITHUB_SHA','GITHUB_WORKFLOW_SHA','GITHUB_WORKFLOW_REF','GITHUB_WORKSPACE','RUNNER_TEMP','RUNNER_TOOL_CACHE','PSYCOPG_IMPL')


def current_context():
    return (tuple((k,os.environ.get(k)) for k in CONTEXT_NAMES),
        tuple(sorted(k for k in os.environ if k.upper().startswith('PG'))))


def pairs(items):
    result = {}
    for key, value in items:
        need(key not in result); result[key] = value
    return result


def _read(path, limit):
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and not path.is_symlink()
         and not getattr(before, 'st_file_attributes', 0) & 0x400 and before.st_size <= limit)
    with path.open('rb') as stream: raw = stream.read(limit+1)
    after = path.lstat()
    need(len(raw) <= limit and (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
         (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns))
    return raw


def _record():
    # The ONLY pre-admission I/O is this fixed source metadata read. Native
    # imports, candidate files, RNG, Git processes and temp creation follow it.
    raw = _read(Path(__file__).with_suffix('.json'), 8192)
    value = json.loads(raw, object_pairs_hook=pairs)
    need(type(value) is dict and set(value) == set(FrozenWindow.__dataclass_fields__))
    need(type(value['operations']) is list and len(set(value['operations'])) == len(value['operations']))
    value['operations'] = tuple(value['operations']); window = FrozenWindow(**value)
    need(window.repository == 'T1doo/ParkWeave' and type(window.ref) is str
         and window.ref == 'refs/heads/dev/local-product-runtime-20261028'
         and window.job == 'native-business-trial' and type(window.run_number) is int and window.run_number > 0
         and (window.run_id is None or type(window.run_id) is str and re.fullmatch('[1-9][0-9]{0,19}', window.run_id))
         and type(window.expires_utc) is int and 1020 < window.expires_utc-time.time() <= 86400
         and all(type(v) is str and re.fullmatch('[a-f0-9]{64}', v) for v in
            (window.workflow_sha256, window.archive_sha256, window.manifest_sha256))
         and type(window.reviewed_parent) is str and re.fullmatch('[a-f0-9]{40}', window.reviewed_parent)
         and type(window.archive_bytes) is int and 1 <= window.archive_bytes <= 128*1024*1024
         and frozenset(window.operations) == OPERATIONS
         and type(window.work_seconds) is int and window.work_seconds == 900
         and type(window.cleanup_seconds) is int and window.cleanup_seconds == 60)
    return window,raw


def load_source_window():
    window,raw=_record()
    expected = dict(GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted', RUNNER_OS='Windows',
        NATIVE_PUBLIC='true', GITHUB_REPOSITORY=window.repository, GITHUB_REF=window.ref,
        GITHUB_JOB=window.job, GITHUB_EVENT_NAME='push', GITHUB_RUN_ATTEMPT='1',
        GITHUB_RUN_NUMBER=str(window.run_number), PSYCOPG_IMPL='binary',
        GITHUB_WORKFLOW_REF=window.repository+'/'+WORKFLOW+'@'+window.ref)
    if window.run_id is not None:expected['GITHUB_RUN_ID']=window.run_id
    need(all(os.environ.get(k) == v for k,v in expected.items()) and os.name == 'nt' and sys.maxsize > 2**32
         and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and sys.version_info[:2] == (3,12)
         and os.environ.get('GITHUB_WORKFLOW_SHA') == os.environ.get('GITHUB_SHA')
         and re.fullmatch('[1-9][0-9]{0,19}',os.environ.get('GITHUB_RUN_ID',''))
         and re.fullmatch('[a-f0-9]{40}', os.environ.get('GITHUB_SHA', ''))
         and not any(k.upper().startswith('PG') for k in os.environ))
    key = (window.repository, window.ref, window.job, window.run_number, os.environ['GITHUB_RUN_ID'])
    need(key not in _spent); _spent.add(key)
    grant = SourceGrant()
    need(all(type(os.environ.get(k)) is str and os.environ[k] for k in ('RUNNER_TEMP','GITHUB_WORKSPACE','RUNNER_TOOL_CACHE')))
    _issued[grant] = (window, key, os.getpid(), threading.get_ident(),current_context(),
        os.environ['GITHUB_SHA'],sha256(raw).hexdigest())
    return grant


def _verify_archive_inputs(grant, payload, archive):
    need(type(grant) is SourceGrant and grant in _issued)
    window, key, pid, thread, context, approval_commit,record_digest = _issued.pop(grant)
    need(pid == os.getpid() and thread == threading.get_ident()
         and current_context()==context
         and os.environ.get('GITHUB_SHA') == approval_commit
         and not any(k.upper().startswith('PG') for k in os.environ))
    # Time consumed by byte verification counts against this one work window.
    deadline = min(time.monotonic()+window.work_seconds,
        time.monotonic()+window.expires_utc-time.time()-window.cleanup_seconds)
    temp=Path(dict(context[0])['RUNNER_TEMP'])
    need(type(payload) is type(temp) and type(archive) is type(temp)
         and payload.is_absolute() and archive.is_absolute()
         and payload!=temp and archive!=temp and payload.is_relative_to(temp) and archive.is_relative_to(temp)
         and not any(part in ('.','..') for part in (*payload.parts,*archive.parts)))
    repo = Path(os.environ['GITHUB_WORKSPACE']).resolve(strict=True)
    need(Path(__file__).resolve() == repo/RECORD.replace('.json', '.py'))
    def git(*args):
        need(time.monotonic() < deadline)
        return subprocess.check_output(['git', '--no-optional-locks', *args], cwd=repo,
            timeout=min(10, max(.001, deadline-time.monotonic())))
    need(git('rev-parse', 'HEAD').decode().strip() == approval_commit
         and git('rev-parse', 'HEAD^').decode().strip() == window.reviewed_parent
         and not git('status', '--porcelain=v1')
         and set(git('diff', '--name-only', 'HEAD^', 'HEAD').decode().splitlines()) <= {RECORD, WORKFLOW}
         and _read(repo/RECORD,8192) == git('show', 'HEAD:'+RECORD)
         and sha256(git('show','HEAD:'+RECORD)).hexdigest()==record_digest
         and sha256(_read(repo/WORKFLOW,65536)).hexdigest() == window.workflow_sha256)
    workflow = (repo/WORKFLOW).read_bytes()
    need(b'timeout-minutes: 19' in workflow and b'timeout-minutes: 6' in workflow
         and b'persist-credentials: false' in workflow
         and b'contents: read' in workflow and b'runs-on: windows-2025' in workflow)
    archive_raw=_read(archive,window.archive_bytes)
    need(sha256(archive_raw).hexdigest() == window.archive_sha256
         and archive.stat().st_size == window.archive_bytes)
    return window,key,payload,archive_raw,deadline,context


def _verify_inputs(grant,payload,archive):
    window,key,payload,archive_raw,deadline,context=_verify_archive_inputs(grant,payload,archive)
    raw = _read(payload/'payload-manifest.json',4*1024*1024)
    need(sha256(raw).hexdigest() == window.manifest_sha256)
    from scripts.windows_portable.payload import verify_directory
    manifest = verify_directory(payload, manifest_raw=raw)
    need(manifest['source_commit'] == window.reviewed_parent and manifest['usable_product'] is False
         and time.monotonic() < deadline)
    return window,key,payload,raw,manifest,deadline,context


def extract_approved_archive(grant,payload,archive):
    """Source/byte admission BEFORE exclusive extraction; no executable starts."""
    import io
    import zipfile
    from scripts.windows_portable.payload import parse_manifest,MANIFEST,MAX_FILES,MAX_BYTES
    window,key,payload,archive_raw,deadline,context=_verify_archive_inputs(grant,payload,archive)
    need(not payload.exists())
    with zipfile.ZipFile(io.BytesIO(archive_raw)) as stream:
        infos=stream.infolist();names=[row.filename for row in infos]
        need(len(names)<=MAX_FILES+1 and len(names)==len(set(names)))
        need(sum(row.file_size for row in infos)<=MAX_BYTES
            and all(0<=row.file_size<=MAX_BYTES and not row.is_dir()
                and (row.external_attr>>16)&0o170000==0o100000 for row in infos))
        need(stream.getinfo(MANIFEST).file_size<=4*1024*1024)
        with stream.open(MANIFEST) as entry:raw=entry.read(4*1024*1024+1)
        need(len(raw)<=4*1024*1024)
        need(sha256(raw).hexdigest()==window.manifest_sha256)
        manifest=parse_manifest(raw)
        need(manifest['source_commit']==window.reviewed_parent and manifest['usable_product'] is False
            and set(names)==set(manifest['files'])|{MANIFEST}
            and sum(row.file_size for row in infos)<=MAX_BYTES)
        payload.mkdir(mode=0o700)
        for name in sorted(names):
            need(time.monotonic()<deadline and current_context()==context)
            row=manifest['files'].get(name,dict(bytes=len(raw),sha256=window.manifest_sha256))
            with stream.open(name) as entry:data=entry.read(row['bytes']+1)
            need(len(data)==row['bytes'] and sha256(data).hexdigest()==row['sha256'])
            path=payload/name;path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as output:output.write(data)
    # The execution coordinator independently rechecks and holds all bytes.
    return None


def verify_staged_bytes(grant,payload,archive):
    _verify_inputs(grant,payload,archive)  # Metadata only; NEVER issues execution authority.


def verify_bootstrap_and_consume(grant,payload,archive):
    window,key,payload,raw,manifest,deadline,context=_verify_inputs(grant,payload,archive)
    # Existing official runner interpreter is the coordinator; never execute
    # an input-selected candidate interpreter between path hashing and pinning.
    executable=Path(sys.executable)
    cache=Path(dict(context[0])['RUNNER_TOOL_CACHE'])/'Python'
    need(executable.name.lower()=='python.exe' and executable.parent.name=='x64'
         and re.fullmatch('3[.]12[.][0-9]+',executable.parent.parent.name)
         and executable.parent.parent.parent==cache)
    from .native_business_pins import NativeBootstrapPins
    pins=NativeBootstrapPins(payload,raw,manifest,deadline,context)
    pins.verify()
    cap = VerifiedSource()
    _verified[cap] = (window, key, payload, raw, manifest, deadline,context,pins,os.getpid(),threading.get_ident())
    return cap


def consume_verified(cap):
    need(type(cap) is VerifiedSource and cap in _verified)
    value = _verified.pop(cap)
    need(value[-2:] == (os.getpid(), threading.get_ident()) and time.monotonic() < value[5]
         and current_context()==value[6])
    value[7].verify()
    return value[:8]
