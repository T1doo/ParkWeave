"""One reviewed Linux invocation; default contract is disabled.

This is an operator activation record, not proof of user/platform authorization.
expires_utc is an admission deadline, not a continuous revocation timer; it
must leave at least360s when loaded. Only the separately authorized activation
commit may enable it. No service or
credential operation occurs here. Same-UID hostile mutation is outside scope.
"""
from dataclasses import dataclass
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
RELATIVE='scripts/template_http_approval.json'
PROFILES={'NODE':RELATIVE,'BROWSER':'scripts/template_browser_approval.json'}
BRANCH='dev/pgdata-inheritance-source-20261026'


class Closed(RuntimeError):pass


def regular_bytes(path,limit):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size>limit:raise Closed('bounded ordinary file required')
        raw=os.read(fd,limit+1);after=os.fstat(fd)
        if len(raw)>limit or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):raise Closed('file changed during read')
        if not os.path.samestat(after,path.lstat()):raise Closed('file name changed during read')
        return raw,(after.st_dev,after.st_ino)
    finally:os.close(fd)


def unique_pairs(items):
    result={}
    for key,value in items:
        if key in result:raise Closed('duplicate contract field')
        result[key]=value
    return result


@dataclass(frozen=True)
class Approval:
    reviewed_source:str
    invocation:str
    expires:float
    raw:bytes
    identity:tuple
    relative:str=RELATIVE
    def check(self):
        raw,identity=regular_bytes(ROOT/self.relative,2048)
        if raw!=self.raw or identity!=self.identity or time.time()>=self.expires:raise Closed('activation changed or expired')


def load(invocation,mode='NODE'):
    if mode not in PROFILES:raise Closed('fixed profile required')
    relative=PROFILES[mode]
    raw,identity=regular_bytes(ROOT/relative,2048)
    value=json.loads(raw,object_pairs_hook=unique_pairs)
    if type(value) is not dict or set(value)!={'version','enabled','reviewed_source','invocation','expires_utc'} or type(value['version']) is not int or value['version']!=1 or type(value['enabled']) is not bool:raise Closed('activation shape')
    if value['enabled'] is not True:raise Closed('window closed')
    if (type(value['reviewed_source']) is not str or re.fullmatch('[0-9a-f]{40}',value['reviewed_source']) is None
            or type(value['invocation']) is not str or re.fullmatch('PW_HTTP_[A-Z0-9_]{8,80}',value['invocation']) is None
            or invocation!=value['invocation'] or type(value['expires_utc']) is not str
            or re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z',value['expires_utc']) is None):raise Closed('activation binding')
    expires=datetime.strptime(value['expires_utc'],'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).timestamp()
    if not time.time()+360<=expires<=time.time()+3600:raise Closed('admission must cover360s and expire within one hour')
    return Approval(value['reviewed_source'],invocation,expires,raw,identity,relative)


def git(args,started):
    left=started+360-time.monotonic()
    if left<=0:raise TimeoutError('original absolute deadline')
    return subprocess.check_output(['git',*args],cwd=ROOT,timeout=min(5,left),stderr=subprocess.DEVNULL)


def verify_source(source,approval,started):
    approval.check()
    if re.fullmatch('[0-9a-f]{40}',source) is None:raise Closed('source format')
    if git(['rev-parse','HEAD'],started).decode().strip()!=source:raise Closed('execution source changed')
    if git(['branch','--show-current'],started).decode().strip()!=BRANCH:raise Closed('fixed development branch required')
    if git(['status','--porcelain'],started):raise Closed('dirty source')
    if git(['rev-parse','HEAD^'],started).decode().strip()!=approval.reviewed_source:raise Closed('reviewed direct parent required')
    if git(['diff','--name-only','-z',approval.reviewed_source,source],started)!=approval.relative.encode()+b'\0':raise Closed('activation may change only its contract')
    if git(['show',source+':'+approval.relative],started)!=approval.raw:raise Closed('activation not committed exactly')
    approval.check()


class TotalDeadline:
    """Dedicated CLI only: leave watchdog alive through interpreter shutdown.

    At 360s it exits only this process, with 124; it never signals an unverified
    PID or deletes files. pidfd cleanup starts at315s, finishes by330s; unknown
    processes/directories remain unknown. This is not a kernel realtime SLA.
    """
    def __init__(self,started):self.started=started;self.timer=None
    def arm(self):
        left=self.started+360-time.monotonic()
        if left<=0:raise TimeoutError('original absolute deadline')
        self.timer=threading.Timer(left,lambda:os._exit(124));self.timer.daemon=True;self.timer.start()
        # Deliberately no cancel, even on normal return: final flush/exit included.


class OnceClaim:
    def __init__(self,path,identity,file_identity,value):self.path=path;self.identity=identity;self.file_identity=file_identity;self.value=value
    @staticmethod
    def path_for(invocation):return Path('/tmp')/('pw-http-once-'+str(os.geteuid())+'-'+sha256(invocation.encode()).hexdigest())
    @classmethod
    def create(cls,source,invocation,started,birth):
        path=cls.path_for(invocation);path.mkdir(mode=0o700,exist_ok=False)
        # Keep this nonsecret claim permanently for the life of this environment;
        # failed/unknown execution is never automatically eligible for replay.
        value=dict(source=source,invocation=invocation,started=started,parent_pid=os.getpid(),parent_birth=birth)
        fd=os.open(path/'claim.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            raw=json.dumps(value,sort_keys=True).encode()
            if os.write(fd,raw)!=len(raw):raise Closed('short claim write')
            os.fsync(fd);file_identity=(os.fstat(fd).st_dev,os.fstat(fd).st_ino)
        finally:os.close(fd)
        result=cls(path,(path.stat().st_dev,path.stat().st_ino),file_identity,value);result.check(source,invocation);return result
    @classmethod
    def restore(cls,path,identity,file_identity,source,invocation,parent_pid,parent_birth):
        path=Path(path);before=path.lstat()
        if (path!=cls.path_for(invocation) or path.resolve()!=path or not stat.S_ISDIR(before.st_mode)
                or before.st_uid!=os.geteuid() or before.st_mode&0o077 or (before.st_dev,before.st_ino)!=identity):raise Closed('original claim directory required')
        value=json.loads(regular_bytes(Path(path)/'claim.json',2048)[0],object_pairs_hook=unique_pairs)
        if type(value) is not dict or set(value)!={'source','invocation','started','parent_pid','parent_birth'}:raise Closed('claim shape')
        result=cls(Path(path),identity,file_identity,value);result.check(source,invocation)
        if value['parent_pid']!=parent_pid or value['parent_birth']!=parent_birth:raise Closed('original parent birth required')
        return result
    def check(self,source,invocation):
        before=self.path.lstat()
        if (self.path!=self.path_for(invocation) or self.path.resolve()!=self.path or not stat.S_ISDIR(before.st_mode)
                or before.st_uid!=os.geteuid() or before.st_mode&0o077 or (before.st_dev,before.st_ino)!=self.identity):raise Closed('claim directory drift')
        raw,identity=regular_bytes(self.path/'claim.json',2048)
        if identity!=self.file_identity:raise Closed('claim file identity drift')
        value=json.loads(raw,object_pairs_hook=unique_pairs)
        if value!=self.value or value.get('source')!=source or value.get('invocation')!=invocation or type(value.get('started')) not in (int,float) or not 0<=time.monotonic()-value['started']<360:raise Closed('original invocation claim required')
