"""One reviewed native observation window, not product activation.

--plan is pure. --execute is currently refused before native imports or IO.
A future approval binds a committed JSON data record and its exact source
change/workflow. No CLI/env switch issues approval; passing reports grant none.
"""
import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
import time

PRODUCT_SOURCE='5a048dbef9da4e82a1cb0eb51b4813d75dda54e1'
PRODUCT_ZIP='58486d0c92833d2358a9c0198c082065ebf3bd91cd1b76364132555ff7dbbbaf'
PRODUCT_MANIFEST='2ab9b9ef3ad24cdeecca7775f5e6dae9dbbd5cb9c252838304f0096d5a55e8d2'
OPERATIONS=frozenset(('NEW_PROTECTED_TEST_OBJECTS','FIXED_SLOT_IO','OWN_DERIVED_TOKEN_OWNER',
    'OWN_DERIVED_TOKEN_DEFAULT_DACL','TEMP_CURRENT_USER_DPAPI_IDENTITIES','OWN_CREATED_FILE_DISPOSITION'))
PHASES=('fixed_journal','derived_token','dpapi_identities')


@dataclass(frozen=True)
class Window:
    repository:str
    ref:str
    job:str
    run_number:int
    expires_utc:int
    reviewed_parent:str
    workflow_sha256:str
    operations:frozenset
    run_id:str|None=None
    seconds:int=180


_spent=set()
_unknown=[]


def need(ok):
    if not ok:raise RuntimeError('NATIVE_ACCEPTANCE_WINDOW_REFUSED')


def plan():
    return dict(schema='parkweave-native-acceptance-plan/1',product_source=PRODUCT_SOURCE,
        product_zip_sha256=PRODUCT_ZIP,product_manifest_sha256=PRODUCT_MANIFEST,
        operations=sorted(OPERATIONS),window='APPROVAL_RECORD_NOT_READ',
        work_seconds=180,cleanup_seconds=30,required_job_timeout_minutes=6,
        new_test_objects=['one protected empty-marker directory','lock.bin','journal.bin','torn.bin','identities.dpapi'],
        credentials='six temporary random application tokens; CURRENT_USER DPAPI only; no OS accounts or database principals',
        cleanup='original FILE_CREATED handles/IDs only; unknown retained; empty one-shot root retained',
        os_side_effects='DPAPI may use/create keys in this disposable runner user profile; never manually delete OS key files',
        not_run=['cross-OS-user DPAPI','initdb/PG/API/worker','full Job/backend loading','crash/power-loss durability'],
        activation_allowed=False,usable_product=False)


def window_context(context,window=None):
    # This check precedes platform imports, Git, manifest, RNG, temp files or
    # token/DPAPI construction, including when called directly by the CLI.
    w=window
    need(type(w) is Window)
    need(w.repository=='T1doo/ParkWeave' and w.ref.startswith('refs/heads/dev/')
         and type(w.run_number) is int and w.run_number>0 and type(w.operations) is frozenset and w.operations==OPERATIONS
         and w.seconds==180 and type(w.expires_utc) is int and 360<w.expires_utc-time.time()<=86400
         and re.fullmatch('[a-f0-9]{40}',w.reviewed_parent)
         and re.fullmatch('[a-f0-9]{64}',w.workflow_sha256))
    expected={'GITHUB_ACTIONS':'true','RUNNER_ENVIRONMENT':'github-hosted','RUNNER_OS':'Windows','NATIVE_PUBLIC':'true',
        'GITHUB_REPOSITORY':w.repository,'GITHUB_REF':w.ref,'GITHUB_JOB':w.job,
        'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ATTEMPT':'1','GITHUB_RUN_NUMBER':str(w.run_number)}
    expected['GITHUB_WORKFLOW_REF']=w.repository+'/.github/workflows/native-local-acceptance-once.yml@'+w.ref
    need(all(context.get(k)==v for k,v in expected.items()) and os.name=='nt' and sys.maxsize>2**32
         and context.get('GITHUB_WORKFLOW_SHA')==context.get('GITHUB_SHA')
         and sys.flags.isolated and sys.dont_write_bytecode and sys.version_info[:2]==(3,12))
    need(re.fullmatch('[1-9][0-9]{0,19}',context.get('GITHUB_RUN_ID',''))
         and re.fullmatch('[a-f0-9]{40}',context.get('GITHUB_SHA','')))
    need(context.get('PSYCOPG_IMPL')=='binary' and not any(key.upper().startswith('PG') for key in context))
    need(w.run_id is None or w.run_id==context['GITHUB_RUN_ID'])
    # If run_id is not known before dispatch, the exact workflow identity and
    # approved ordinal bind the one window. The actual run_id is recorded only.
    key=(w.repository,expected['GITHUB_WORKFLOW_REF'],w.run_number,w.job)
    need(key not in _spent);_spent.add(key);return w,key


def verify_invocation(context,w,payload,archive):
    import subprocess
    repo=Path(context['GITHUB_WORKSPACE']).resolve(strict=True)
    need(Path(__file__).resolve()==repo/'scripts/windows_ci/native_acceptance_harness.py')
    def git(*args):return subprocess.check_output(['git','--no-optional-locks',*args],cwd=repo,timeout=10)
    need(git('rev-parse','HEAD').decode().strip()==context['GITHUB_SHA']
         and git('rev-parse','HEAD^').decode().strip()==w.reviewed_parent
         and not git('status','--porcelain=v1'))
    workflow='.github/workflows/native-local-acceptance-once.yml'
    need(set(git('diff','--name-only','HEAD^','HEAD').decode().splitlines())<=
         {'scripts/windows_ci/native_acceptance_window.json',workflow})
    for name in ('scripts/windows_ci/native_acceptance_harness.py','scripts/windows_ci/native_acceptance_entry.py',
                 'scripts/windows_ci/native_acceptance_window.py','scripts/windows_ci/native_acceptance_storage.py'):
        need((repo/name).read_bytes()==git('show','HEAD^:'+name))
    from scripts.windows_ci.native_acceptance_window import _pairs
    committed=json.loads(git('show','HEAD:scripts/windows_ci/native_acceptance_window.json'),object_pairs_hook=_pairs)
    need(type(committed) is dict)
    committed['operations']=frozenset(committed['operations'])
    need(w==Window(**committed))  # Bind the consumed data to the actual approved Git blob.
    raw=(repo/workflow).read_bytes();need(sha256(raw).hexdigest()==w.workflow_sha256)
    need(b'timeout-minutes: 6' in raw and b'persist-credentials: false' in raw and b'contents: read' in raw)
    # Exact frozen product bytes and updated harness source are separate pins.
    before=archive.stat();need(archive.is_file() and not archive.is_symlink()
        and not getattr(before,'st_file_attributes',0)&0x400 and before.st_size==51637700)
    with archive.open('rb') as stream:need(sha256(stream.read(51637701)).hexdigest()==PRODUCT_ZIP)
    after=archive.stat();need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
                             (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns))
    raw=(payload/'payload-manifest.json').read_bytes();need(sha256(raw).hexdigest()==PRODUCT_MANIFEST)
    manifest=json.loads(raw);need(manifest['source_commit']==PRODUCT_SOURCE and manifest['usable_product'] is False)
    actual=set()
    for parent,dirs,names in os.walk(payload,followlinks=False):
        base=Path(parent)
        for entry in (base,*(base/name for name in dirs)):
            info=entry.lstat();need(entry.is_dir() and not entry.is_symlink()
                and not getattr(info,'st_file_attributes',0)&0x400)
        actual.update((base/name).relative_to(payload).as_posix() for name in names)
    need(len(manifest['files'])==3011 and actual==set(manifest['files'])|{'payload-manifest.json'})
    for name,row in manifest['files'].items():
        parts=name.split('/');need(not any(p in ('','..','.') for p in parts) and not any(c in name for c in '\\:'))
        path=payload/name;info=path.lstat()
        need(path.is_file() and not path.is_symlink() and not getattr(info,'st_file_attributes',0)&0x400
             and info.st_size==row['bytes'] and sha256(path.read_bytes()).hexdigest()==row['sha256'])
    need(sys.executable and Path(sys.executable).resolve()==payload/'runtime/python/python.exe')
    # Only reviewed checkout code plus the original pinned vendor/runtime.
    sys.path[:]=[str(repo),str(repo/'src'),str(payload/'vendor'),
                 str(payload/'runtime/python/python312.zip'),str(payload/'runtime/python')]
    return repo


def run_protocol(backend,seconds=180,*,clock=time.monotonic):
    """Controlled port tests exercise orchestration, never native approval."""
    need(seconds==180);deadline=clock()+seconds;observed=[];phase='NOT_STARTED';error=None
    try:
        for phase in PHASES:
            need(clock()<deadline)
            facts=getattr(backend,phase)(deadline)
            need(type(facts) is tuple and len(facts)<=8 and all(type(x) is str for x in facts))
            observed.extend(facts);need(clock()<deadline)
    except BaseException as failure:
        error=type(failure).__name__
        _retain(backend)
    finally:
        try:cleanup=backend.cleanup(clock()+30)
        except BaseException:
            _retain(backend);cleanup='RETAINED_UNKNOWN';error=error or 'CLEANUP_UNKNOWN'
    if cleanup!='OWN_CHILDREN_DELETED_EMPTY_MARKER_RETAINED':error=error or 'CLEANUP_UNKNOWN'
    from scripts.windows_portable.native_acceptance_contract import coverage
    return dict(schema='parkweave-native-acceptance-observations/1',product_source=PRODUCT_SOURCE,
        product_zip_sha256=PRODUCT_ZIP,phase=phase,result='OBSERVED_ONLY' if error is None else 'UNKNOWN',
        observations=observed,error_type=error,cleanup=cleanup,**coverage(tuple(observed)))


def _retain(backend):
    if backend not in _unknown:_unknown.append(backend)
    try:backend.unknown()
    except BaseException:pass  # Retention never authorizes a second cleanup.


class NativeBackend:
    """Future explicit native calls; no private-dictionary identity backend."""
    def __init__(self,parent,key):
        self.parent,self.key=parent,key;self.storage=None;self.token=None;self.crypto=[]
    def unknown(self):
        if self.storage is not None:self.storage.failed=True
        if self not in _unknown:_unknown.append(self)
    def fixed_journal(self,deadline):
        from scripts.windows_ci.native_acceptance_storage import OwnedNativeObjects,NativeSlotIO
        from scripts.windows_portable import fixed_journal as j
        from uuid import uuid4
        name='parkweave-native-acceptance-'+sha256(json.dumps(self.key).encode()).hexdigest()[:24]
        self.storage=object.__new__(OwnedNativeObjects)
        OwnedNativeObjects.__init__(self.storage,self.parent,deadline,name)
        s=self.storage;lock=s.file('lock.bin');node=s.file('journal.bin')
        io=NativeSlotIO(s,node,lock);store=j.FixedJournal(io,format=j.FixedFormat.INSTANCE_V2)
        record=dict(schema=j.schema(j.FixedFormat.INSTANCE_V2),root=s.root_id,lock=io.lock_id,
            journal=io.identity(),generation=1,sequence=2,phase='NEW',initialized=False,
            runtime='STOPPED',handoff='OWNED',instance_id=str(uuid4()))
        first=store.write(j.encode(record),None)
        record.update(sequence=3,phase='CREDENTIALS',runtime='STARTING')
        expected=store.write(j.encode(record),first);s.exclusive_refused(node)
        node=s.reopen(node);io=NativeSlotIO(s,node,lock)
        need(j.FixedJournal(io,format=j.FixedFormat.INSTANCE_V2).read()==expected)
        torn=s.file('torn.bin');raw=bytearray(expected[1]);raw[-1]^=1
        s.write(torn,0,bytes(raw));s.flush(torn)
        try:j.FixedJournal(NativeSlotIO(s,torn,lock),format=j.FixedFormat.INSTANCE_V2).read()
        except Exception as error:need(type(error) is j.LeaseRefused and str(error)=='FIXED_SLOT_TORN')
        else:need(False)
        need(s.read(torn,0,len(raw))==bytes(raw))
        return ('protected_new_objects','original_fixed_slots_write_flush_readback','same_file_reopen',
                'exclusive_open_refused','torn_slot_refused_without_repair')
    def _original(self):
        s=self.storage;s._anchor();return s.read_primary((1,2,3,4,6,8))
    def derived_token(self,deadline):
        from scripts.windows_portable.restricted_token_candidate import _RestrictedPrimaryCandidate,TokenProfile
        self.storage.deadline=deadline;before=self._original()
        self.token=object.__new__(_RestrictedPrimaryCandidate)
        _RestrictedPrimaryCandidate.__init__(self.token,TokenProfile.CREATE_CANDIDATE)
        self.token.derive();self.token.prepare_default_dacl();self.token.prepare_owner()
        need(self.token._prepared_owner==before[1] and self.token._prepared_dacl is not None
             and self._original()==before)
        self.token.close();need(self._original()==before)
        return ('derived_token_owner_and_default_dacl','original_primary_token_unchanged')
    def dpapi_identities(self,deadline):
        from scripts.windows_portable.dpapi_native_candidate import _NativeDPAPI,NativeFailure
        from scripts.windows_portable.local_preparation_identity import ENTERPRISES,REVIEWERS,PreparationIdentities
        from scripts.windows_portable.credential_envelope import canonical
        import base64
        import secrets
        s=self.storage;s.deadline=deadline;s._anchor()
        identities=PreparationIdentities.from_mapping({name:secrets.token_urlsafe(48) for name in ENTERPRISES+REVIEWERS})
        binding=dict(schema='parkweave-ephemeral-native-identities/1',window=self.key,
            root=s.root_id,source=PRODUCT_SOURCE)
        crypto=_NativeDPAPI();self.crypto.append(crypto)
        originals={};entropies={};sealed={}
        for name,value in identities.mapping().items():
            aad={**binding,'actor':name,'role':'enterprise' if name in ENTERPRISES else 'specialist'}
            entropies[name]=sha256(canonical(aad)).digest()
            originals[name]=canonical(dict(binding=aad,value=value))
            sealed[name]=base64.b64encode(crypto.protect(originals[name],entropies[name])).decode('ascii')
        cipher=canonical(dict(schema='parkweave-ephemeral-sealed-actors/1',sealed=sealed))
        node=s.file('identities.dpapi')
        s.write(node,0,cipher);s.flush(node);node=s.reopen(node)
        saved=s.read(node,0,node.size);need(saved==cipher)
        recovered=json.loads(saved);need(recovered['sealed']==sealed and len(sealed)==6)
        for name,value in recovered['sealed'].items():
            need(crypto.unprotect(base64.b64decode(value,validate=True),entropies[name])==originals[name])
        wrong=_NativeDPAPI();self.crypto.append(wrong)
        try:wrong.unprotect(base64.b64decode(sealed[ENTERPRISES[0]],validate=True),entropies[REVIEWERS[0]])
        except NativeFailure as error:
            need(not wrong.unknown and not error.cleanup_types and error.winerror==13
                 and error.primary_type=='ProtectionRefused' and error.phase=='ALLOCATION')
        else:need(False)
        # Plaintext never enters argv/env/files/logs; immutable Python copies
        # cannot be promised erased, so no process-memory secrecy claim.
        originals=identities=entropies=sealed=cipher=saved=recovered=None
        return ('dpapi_current_user_roundtrip','dpapi_wrong_entropy_refused')
    def cleanup(self,deadline):
        if self.token is not None:self.token.close()
        if any(getattr(value,'unknown',()) for value in self.crypto):self.unknown()
        if self.storage is None:return 'NO_OBJECTS_CREATED'
        self.storage.deadline=deadline;return self.storage.cleanup()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute',action='store_true')
    p.add_argument('--payload',type=Path)
    p.add_argument('--candidate-zip',type=Path)
    args=p.parse_args(argv)
    if not args.execute:print(json.dumps(plan(),ensure_ascii=False));return 0
    try:
        w,key=window_context(os.environ)
        need(args.payload is not None and args.candidate_zip is not None and not args.payload.is_symlink())
        repo=verify_invocation(os.environ,w,args.payload.resolve(strict=True),args.candidate_zip)
        parent=os.environ['RUNNER_TEMP']
        backend=NativeBackend(parent,key);result=run_protocol(backend,w.seconds)
        result['harness_commit']=os.environ['GITHUB_SHA'];result['harness_sha256']=sha256(Path(__file__).read_bytes()).hexdigest()
        raw=json.dumps(result,ensure_ascii=False);need(len(raw.encode())<=65536);print(raw)
        return 0 if result['result']=='OBSERVED_ONLY' else 2
    except BaseException as error:
        print(json.dumps(dict(result='NOT_EXECUTED_OR_UNKNOWN',error_type=type(error).__name__,
            activation_allowed=False,usable_product=False)));return 2


if __name__=='__main__':raise SystemExit(main())
