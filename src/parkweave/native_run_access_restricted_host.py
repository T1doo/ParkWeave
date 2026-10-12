"""Explicit approved Linux host adapter; no installer, credential or UID creator.

Pure predicates and injected observation tests cannot issue a live launch token.
The real host uses protected signed approval, creation proof and sealed memfd.
"""
from datetime import datetime, timezone
import fcntl
import hashlib
import hmac
import json
import os
import re
from pathlib import Path
import signal
import stat
import subprocess
import time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import native_run_access as native, native_run_access_writer as writer
from . import native_run_access_preflight as preflight
from .native_run_access_trial_plan import _local_database_host
from .store import Denied

MAX_PRIVATE = 524288
SHA = r'^[a-f0-9]{64}$'
_ISSUER = object()
_FD_ISSUER = object()


def canonical_path(value):
    return (isinstance(value,str) and value.startswith('/') and
            all(p and p not in ('.','..') for p in value.split('/')[1:]) and
            '\\' not in value and not any(ord(c)<32 for c in value))


class RuntimeLayout(BaseModel):
    model_config = ConfigDict(strict=True,extra='forbid',frozen=True)
    trial_root: str = Field(pattern=r'^/tmp/parkweave-trial-[a-f0-9]{32}$')
    source_sha: str = Field(pattern=r'^[a-f0-9]{40}$')
    source_root: str
    source_files: dict[str,str]
    interpreter: str
    interpreter_sha256: str = Field(pattern=SHA)
    dependency_roots: list[str]
    api_uid: int = Field(gt=0)
    api_gid: int = Field(gt=0)
    writer_uid: int = Field(gt=0)
    ipc_gid: int = Field(gt=0)
    boot_id: str
    private_bootstrap_sha256: str = Field(pattern=SHA)
    creation_receipt_sha256: str = Field(pattern=SHA)

    @model_validator(mode='after')
    def exact(self):
        if (self.api_uid == self.writer_uid or str(UUID(self.boot_id)) != self.boot_id or
                not all(canonical_path(p) for p in [self.source_root,self.interpreter,*self.source_files,*self.dependency_roots]) or
                not self.dependency_roots or len(self.dependency_roots)>8 or
                not any(self.interpreter.startswith(p+'/') for p in self.dependency_roots) or
                not self.source_files or len(self.source_files)>512 or
                any(not p.startswith(self.source_root+'/parkweave/') or len(v)!=64 or
                    any(c not in '0123456789abcdef' for c in v) for p,v in self.source_files.items())):
            raise ValueError('exact protected Linux source and independent identities required')
        return self

    @property
    def command_path(self):return self.trial_root+'/writer/command.sock'
    @property
    def verify_path(self):return self.trial_root+'/writer/verify.sock'
    @property
    def bootstrap_path(self):return self.trial_root+'/writer/bootstrap.json'
    @property
    def approval_path(self):return self.trial_root+'/host/start-approval.json'
    @property
    def approval_key_path(self):return self.trial_root+'/host/approval.key'
    @property
    def creation_path(self):return self.trial_root+'/host/creation-receipt.json'
    @property
    def binding_path(self):return self.trial_root+'/host/api-binding.json'
    @property
    def claim_path(self):return self.trial_root+'/host/start-claim.json'


def launch_request(spec, layout):
    spec = preflight.InstallationSpec.model_validate(spec);layout = RuntimeLayout.model_validate(layout)
    p = spec.policy
    if (p is None or p.environment != 'PRODUCTION' or spec.permission_strategy != 'DIRECT_DML' or
            spec.transport != 'LINUX_UNIX' or (spec.api_uid,spec.writer_uid)!=(layout.api_uid,layout.writer_uid) or
            not _local_database_host(p.database_host,layout.trial_root) or
            not re.fullmatch(r'fixture_[a-f0-9]{32}',p.database_name)):
        raise Denied('exact isolated restricted host contract required')
    return dict(action='START_BIND_OWNED_LINUX_RESTRICTED_TRIAL',
        spec_sha256=writer._sha(spec.model_dump()),layout_sha256=writer._sha(layout.model_dump()),
        valid_from=p.valid_from,valid_until=p.valid_until,
        socket_mode='0660',public_binding_mode='0640',writer_umask='0117',
        supplemental_groups=[],start_claim_mode='0600',
        cleanup='OWNED_CHILD_ONLY; no automatic database/path removal')


def verified_record(record, key, expected):
    """Pure crypto comparison only; this returns no live capability."""
    if (not isinstance(record,dict) or set(record)!={'payload','hmac_sha256'} or
            record['payload']!=expected or not isinstance(key,bytes) or len(key)!=32 or
            not isinstance(record['hmac_sha256'],str) or
            not hmac.compare_digest(record['hmac_sha256'],
                hmac.new(key,writer._canonical(expected).encode(),hashlib.sha256).hexdigest())):
        raise Denied('protected host approval/creation signature mismatch; values not echoed')


def _write_all(fd,raw):
    offset=0
    while offset<len(raw):
        written=os.write(fd,raw[offset:])
        if written<=0:raise Denied('owned private/public output incomplete; no retry startup')
        offset+=written


def _path_chain(path, allowed_owners):
    if not canonical_path(path):raise Denied('canonical protected path required')
    p = Path(path)
    for parent in p.parents:
        s = parent.lstat()
        sticky_tmp = str(parent)=='/tmp' and s.st_uid==0 and bool(s.st_mode&stat.S_ISVTX)
        if (not stat.S_ISDIR(s.st_mode) or s.st_uid not in allowed_owners or
                s.st_mode&0o022 and not sticky_tmp):
            raise Denied('protected ancestor ownership/mode unavailable')


def _protected_bytes(path, owner, *, private=False, expected=None, limit=MAX_PRIVATE):
    _path_chain(path,{0,owner})
    fd = os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        a = os.fstat(fd)
        if (not stat.S_ISREG(a.st_mode) or a.st_uid!=owner or a.st_mode&0o022 or
                private and a.st_mode&0o077 or a.st_size>limit):
            raise Denied('protected regular input ownership/mode unavailable')
        raw = os.read(fd,limit+1);b = os.fstat(fd);current = Path(path).lstat()
        fields = lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_uid,s.st_gid,s.st_mode)
        if (len(raw)>limit or fields(a)!=fields(b) or fields(a)!=fields(current) or
                expected is not None and hashlib.sha256(raw).hexdigest()!=expected):
            raise Denied('protected input instance/content changed')
        return raw
    finally:os.close(fd)


def _code_check(layout):
    _protected_bytes(layout.interpreter,0,expected=layout.interpreter_sha256,limit=64*1024*1024)
    expected = {str(p) for p in Path(layout.source_root+'/parkweave').rglob('*') if p.suffix in ('.py','.sql')}
    if expected!=set(layout.source_files):raise Denied('complete protected source bundle required')
    for path,digest in layout.source_files.items():_protected_bytes(path,0,expected=digest)


def _dependencies_check(layout):
    # An approved interpreter environment includes its config, .pth, libraries
    # and dependencies. No writable app/writer import tree or symlink fallback.
    for root in layout.dependency_roots:
        _path_chain(root,{0})
        count=0
        for p in (Path(root),*Path(root).rglob('*')):
            count+=1;s=p.lstat()
            if (count>100000 or s.st_uid!=0 or s.st_mode&0o022 or
                    not (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode))):
                raise Denied('protected complete interpreter environment unavailable')


def _process(pid):
    raw = Path('/proc/'+str(pid)+'/status').read_text().splitlines()
    fields = {r.split(':',1)[0]:r.split(':',1)[1].strip() for r in raw if ':' in r}
    uids,gids = [int(v) for v in fields['Uid'].split()],[int(v) for v in fields['Gid'].split()]
    return dict(pid=pid,uid=uids[1],gid=gids[1],uids=uids,gids=gids,
        groups=[int(v) for v in fields['Groups'].split()],started=writer._pid_started(pid))


def _endpoint(path, layout):
    _path_chain(path,{0,layout.writer_uid})
    s = Path(path).lstat()
    if (not stat.S_ISSOCK(s.st_mode) or s.st_uid!=layout.writer_uid or
            s.st_gid!=layout.ipc_gid or stat.S_IMODE(s.st_mode)!=0o660):
        raise Denied('restricted endpoint ownership/mode unavailable')
    return dict(device=s.st_dev,inode=s.st_ino,uid=s.st_uid,gid=s.st_gid,mode=0o660)


def observed_pin(policy,layout,process,command,verify):
    """Pure observation predicate; observations themselves are not trusted proof."""
    layout = RuntimeLayout.model_validate(layout);policy = writer.WriterPolicy.model_validate(policy)
    if (process['pid']<=0 or process['uid']!=layout.writer_uid or process['gid']!=layout.ipc_gid or
            process['uids']!=[layout.writer_uid]*4 or process['gids']!=[layout.ipc_gid]*4 or process['groups'] or
            any((v['uid'],v['gid'],v['mode'])!=(layout.writer_uid,layout.ipc_gid,0o660) for v in (command,verify)) or
            (command['device'],command['inode'])==(verify['device'],verify['inode'])):
        raise Denied('host-observed independent restricted process/channels required')
    return writer.EndpointPin(command_path=layout.command_path,verify_path=layout.verify_path,
        command_device=command['device'],command_inode=command['inode'],
        verify_device=verify['device'],verify_inode=verify['inode'],pid=process['pid'],uid=process['uid'],
        process_started=process['started'],boot_id=layout.boot_id,policy_sha256=writer._sha(policy.model_dump()))


def launch_arguments(layout,fd):
    layout = RuntimeLayout.model_validate(layout)
    entry = 'import sys;sys.path.insert(0,'+repr(layout.source_root)+');from parkweave.native_run_access_restricted_runtime import main;raise SystemExit(main())'
    return dict(args=[layout.interpreter,'-I','-c',entry,'--host-fd',str(fd)],
        shell=False,cwd='/',env={'LANG':'C.UTF-8'},user=layout.writer_uid,group=layout.ipc_gid,
        extra_groups=[],umask=0o117,close_fds=True,pass_fds=(fd,),
        stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


class _LiveApproval:
    def __init__(self,issuer,token,request):
        if token is not _ISSUER:raise Denied('host-internal live approval required')
        self.issuer,self.request = issuer,writer._canonical(request)


class LinuxHost:
    """Production primitives are reachable only after protected live issuance."""
    def __init__(self,spec,layout):
        self._spec_json = writer._canonical(preflight.InstallationSpec.model_validate(spec).model_dump())
        self._layout_json = writer._canonical(RuntimeLayout.model_validate(layout).model_dump())
        launch_request(self.spec,self.layout)
        self._owned = {};self._consumed = False;self._live_approval = None

    @property
    def spec(self):return preflight.InstallationSpec.model_validate_json(self._spec_json)
    @property
    def layout(self):return RuntimeLayout.model_validate_json(self._layout_json)

    def _approve(self,authorization):
        if type(self) is not LinuxHost or authorization is None or type(authorization) is not str or authorization!=self.layout.approval_path:
            raise Denied('explicit protected host approval reference required before private reads/start')
        if os.name!='posix' or not hasattr(os,'memfd_create') or os.geteuid()!=0:
            raise Denied('approved privileged Linux host unavailable; no UID fallback')
        request = launch_request(self.spec,self.layout)
        now = datetime.now(timezone.utc)
        if not datetime.fromisoformat(request['valid_from'])<=now<datetime.fromisoformat(request['valid_until']):
            raise Denied('original host policy interval required; no renewal')
        key = _protected_bytes(self.layout.approval_key_path,0,private=True)
        verified_record(json.loads(_protected_bytes(authorization,0,private=True)),key,request)
        proof_raw = _protected_bytes(self.layout.creation_path,0,private=True,expected=self.layout.creation_receipt_sha256)
        p = self.spec.policy
        creation = dict(action='ORIGINAL_NEW_OWNED_DATABASE',database_name=p.database_name,
            database_oid=p.database_oid,system_identifier=p.system_identifier,
            owner=self.spec.installer_role,trial_root=self.layout.trial_root,
            absent_from_initial_databases=True,initial_databases=['postgres','template0','template1'])
        verified_record(json.loads(proof_raw),key,creation)
        _code_check(self.layout)
        _dependencies_check(self.layout)
        self._live_approval = _LiveApproval(self,_ISSUER,request)
        return self._live_approval

    def _authorized_action(self,approval):
        if (type(self) is not LinuxHost or type(approval) is not _LiveApproval or
                approval is not self._live_approval or approval.issuer is not self or
                approval.request!=writer._canonical(launch_request(self.spec,self.layout)) or os.geteuid()!=0):
            raise Denied('only protected live host issuance may enter real OS actions')
        request=json.loads(approval.request);now=datetime.now(timezone.utc)
        if not datetime.fromisoformat(request['valid_from'])<=now<datetime.fromisoformat(request['valid_until']):
            raise Denied('original live host action interval required; no renewal')

    def _claim(self,approval):
        self._authorized_action(approval)
        _path_chain(self.layout.claim_path,{0})
        fd = os.open(self.layout.claim_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            _write_all(fd,approval.request.encode());os.fsync(fd)
        finally:os.close(fd)

    def _spawn(self,approval,fd):
        self._authorized_action(approval)
        process = subprocess.Popen(**launch_arguments(self.layout,fd))
        self._owned[id(process)] = process
        return process

    def start(self,authorization=None):
        approval = self._approve(authorization)
        if self._consumed:raise Denied('host action consumed; no implicit restart/rebind')
        self._claim(approval) # Durable host action marker; no business Grant/registry.
        self._consumed = True
        raw = _protected_bytes(self.layout.bootstrap_path,self.layout.writer_uid,private=True,
                               expected=self.layout.private_bootstrap_sha256)
        private = json.loads(raw)
        from .native_run_access_restricted_runtime import RestrictedEngine
        RestrictedEngine(self.spec.model_dump(),private,self.layout.boot_id,lambda:None) # pure typed input check
        for path in (self.layout.command_path,self.layout.verify_path,self.layout.binding_path):
            if Path(path).exists() or Path(path).is_symlink():raise Denied('new host output required; no adoption/overwrite')
            _path_chain(path,{0,self.layout.writer_uid})
        host = _process(os.getpid())
        payload = dict(spec=self.spec.model_dump(),layout=self.layout.model_dump(),private=private,
                       host_pid=host['pid'],host_started=host['started'])
        fd = os.memfd_create('parkweave-approved-private-runtime',os.MFD_ALLOW_SEALING|os.MFD_CLOEXEC)
        process = None
        try:
            _write_all(fd,writer._canonical(payload).encode());os.lseek(fd,0,os.SEEK_SET)
            fcntl.fcntl(fd,fcntl.F_ADD_SEALS,fcntl.F_SEAL_SEAL|fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK)
            process = self._spawn(approval,fd)
            deadline = time.monotonic()+10
            while time.monotonic()<deadline:
                if process.poll() is not None:raise Denied('owned restricted child exited; no restart')
                if all(Path(p).exists() for p in (self.layout.command_path,self.layout.verify_path)):break
                time.sleep(.02)
            else:raise Denied('owned restricted endpoints not ready; no retry startup')
            _code_check(self.layout)
            pin = observed_pin(self.spec.policy.model_dump(),self.layout.model_dump(),_process(process.pid),
                               _endpoint(self.layout.command_path,self.layout),_endpoint(self.layout.verify_path,self.layout))
            public = dict(schema='parkweave-restricted-api-binding/1',policy=self.spec.policy.model_dump(),
                pin=pin.model_dump(),api_uid=self.layout.api_uid,api_gid=self.layout.api_gid,
                ipc_gid=self.layout.ipc_gid,source_sha=self.layout.source_sha)
            self._publish(approval,public)
            return process,pin
        except BaseException:
            if process is not None:self.stop(process)
            raise
        finally:os.close(fd)

    def _publish(self,approval,public):
        self._authorized_action(approval)
        _path_chain(self.layout.binding_path,{0})
        fd = os.open(self.layout.binding_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o640)
        try:
            os.fchown(fd,0,self.layout.ipc_gid)
            os.fchmod(fd,0o640) # Only this approved newly created public pin FD.
            _write_all(fd,writer._canonical(public).encode());os.fsync(fd)
        finally:os.close(fd)

    def stop(self,process):
        if self._owned.get(id(process)) is not process:
            raise Denied('only the exact host-created child may be stopped')
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
        del self._owned[id(process)]


class _RuntimeAuthorization:
    def __init__(self,token,payload):
        if token is not _ISSUER:raise Denied('live sealed host descriptor required')
        self._json = writer._canonical(payload)
        self._fd_issued = None
    @property
    def payload(self):return json.loads(self._json)
    @property
    def layout(self):return RuntimeLayout.model_validate(self.payload['layout'])
    def matches(self,engine):
        from .native_run_access_restricted_runtime import RestrictedEngine
        return (self._fd_issued is _FD_ISSUER and type(engine) is RestrictedEngine and not engine._injected_store and
                writer._sha(engine.policy.model_dump())==writer._sha(self.payload['spec']['policy']) and
                engine.boot_id==self.layout.boot_id and
                getattr(engine._guard.host_check,'__self__',None) is self and
                engine._dsn==self.payload['private']['writer_dsn'] and
                hmac.compare_digest(engine._key,bytes.fromhex(self.payload['private']['key'])))
    def check(self):
        p = self.payload;layout = self.layout
        if os.geteuid()!=layout.writer_uid or os.getegid()!=layout.ipc_gid or os.getgroups():
            raise Denied('actual distinct nonroot writer identity required')
        parent = _process(os.getppid())
        if (parent['pid'],parent['uid'],parent['started'])!=(p['host_pid'],0,p['host_started']):
            raise Denied('original trusted host process unavailable')
        _code_check(layout)
    def check_launch_window(self):
        policy=self.payload['spec']['policy'];now=datetime.now(timezone.utc)
        if not datetime.fromisoformat(policy['valid_from'])<=now<datetime.fromisoformat(policy['valid_until']):
            raise Denied('original launch interval required; no restart/renewal')
    def assert_new_endpoint(self,path):
        _path_chain(path,{0,self.layout.writer_uid})
        if Path(path).exists() or Path(path).is_symlink():raise Denied('new endpoint required')
    def check_endpoints(self):
        for path in (self.layout.command_path,self.layout.verify_path):_endpoint(path,self.layout)


def load_host_ticket(fd):
    seals = fcntl.F_SEAL_SEAL|fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK
    s = os.fstat(fd)
    if (s.st_uid!=0 or not stat.S_ISREG(s.st_mode) or s.st_size>MAX_PRIVATE or
            fcntl.fcntl(fd,fcntl.F_GET_SEALS)&seals!=seals):
        raise Denied('sealed trusted host descriptor unavailable')
    raw = os.pread(fd,MAX_PRIVATE+1,0);os.close(fd)
    if len(raw)>MAX_PRIVATE:raise Denied('bounded private host ticket required')
    payload = json.loads(raw)
    if set(payload)!={'spec','layout','private','host_pid','host_started'}:
        raise Denied('exact sealed private host ticket required')
    authorization = _RuntimeAuthorization(_ISSUER,payload);authorization.check()
    _dependencies_check(authorization.layout)
    authorization._fd_issued = _FD_ISSUER # Only after actual root-owned sealed FD and host/source checks.
    launch_request(payload['spec'],payload['layout'])
    from .native_run_access_restricted_runtime import RestrictedEngine
    engine = RestrictedEngine(payload['spec'],payload['private'],authorization.layout.boot_id,authorization.check)
    return engine,authorization


def bind_api(store,binding_path=None,expected_sha256=None):
    """Explicit protected public pin only; configured_app gains no auto binding."""
    if binding_path is None or expected_sha256 is None:
        raise Denied('explicit trusted public binding required')
    public = json.loads(_protected_bytes(binding_path,0,expected=expected_sha256))
    expected = {'schema','policy','pin','api_uid','api_gid','ipc_gid','source_sha'}
    if (set(public)!=expected or public['schema']!='parkweave-restricted-api-binding/1' or
            (os.geteuid(),os.getegid())!=(public['api_uid'],public['api_gid']) or
            public['ipc_gid'] not in [os.getegid(),*os.getgroups()]):
        raise Denied('actual designated API identity and protected pin required')
    client = writer.WriterClient(store,public['policy'],public['pin'])
    with store._guarded_connect() as c:
        c.execute('SET TRANSACTION READ ONLY')
        value = writer.WriterClient._database(client,c)
        session = c.execute('SELECT session_user value').fetchone()['value']
        if session!=value['database_role']:raise Denied('actual original API login required')
        from .native_run_access_restricted_runtime import _additional_acl,EXTRA_CHECKS
        extra=_additional_acl(c,[client.policy.application_role,client.policy.writer_role])
        if set(extra)!=EXTRA_CHECKS or any(v is not False for v in extra.values()):
            raise Denied('current API/writer role boundary unsafe')
    bridge = native.NativeRunAccess(store,writer=client)
    store._native_run_access = bridge
    return bridge
