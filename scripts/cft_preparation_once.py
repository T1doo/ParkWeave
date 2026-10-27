"""One fixed official CfT acquisition/unpack, never a browser or business run.

Stdlib only. Both original business contracts stay closed. New private files
are created with private modes; existing image objects/permissions are untouched.
"""
import argparse
import base64
from hashlib import md5,sha256
import json
import os
from pathlib import Path,PurePosixPath
import re
import stat
import struct
import subprocess
import sys
import threading
import time
import types
import urllib.request
from uuid import uuid4
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PARENT='149febc95800789e5e454ab804754d6dc7523b57'
BRANCH='dev/pgdata-inheritance-source-20261026'
PATHS={'.github/workflows/cft-preparation-once.yml','scripts/cft_preparation_once.py','tests/test_cft_preparation_once.py'}
GENERATION='1791250380097835';SIZE=198195769;MD5='lK7krcvsKsrVgyUPt+qhEA==';CRC32C='vpjgUg=='
OBJECT='155.0.8059.39/linux64/chrome-linux64.zip'
META='https://storage.googleapis.com/storage/v1/b/chrome-for-testing-public/o/155.0.8059.39%2Flinux64%2Fchrome-linux64.zip?generation='+GENERATION+'&fields=name,size,md5Hash,crc32c,generation'
MEDIA='https://storage.googleapis.com/chrome-for-testing-public/'+OBJECT+'?generation='+GENERATION
INVOCATION='PW_HTTP_CFT_PREPARATION_RUN1'
MiB=1024*1024;UNPACK=768*MiB;SINGLE=512*MiB;CONTENT=960*MiB;EARLY=1152*MiB;MONITOR=1280*MiB
WORK=150;TREE=165;TOTAL=180;REPORT=16384


class Closed(RuntimeError):
    # Every callsite is a reviewed literal (AST contract test), never remote text.
    def __init__(self,code):
        super().__init__(code);self.code=code.upper().replace(' ','_')


def fault(error):
    return {'error_type':type(error).__name__,'reason_code':error.code if isinstance(error,Closed) else 'UNCLASSIFIED_FAILURE','http_status':getattr(error,'code',None) if isinstance(getattr(error,'code',None),int) else None}


def left(deadline,maximum=10):
    value=deadline-time.monotonic()
    if value<=0:raise TimeoutError('deadline')
    return min(maximum,value)


def regular(path,limit):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd)
        if not stat.S_ISREG(a.st_mode) or a.st_size>limit:raise Closed('ordinary bounded file')
        raw=b''
        while len(raw)<=limit:
            part=os.read(fd,min(65536,limit+1-len(raw)))
            if not part:break
            raw+=part
        b=os.fstat(fd)
        if len(raw)>limit or (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)!=(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns) or not os.path.samestat(b,path.lstat()):raise Closed('file drift')
        return raw
    finally:os.close(fd)


def git(args,started):
    return subprocess.check_output(['git',*args],cwd=ROOT,timeout=left(started+WORK,5),stderr=subprocess.DEVNULL)


def gate(source,started):
    expected={'GITHUB_REPOSITORY':'T1doo/ParkWeave','GITHUB_REF':'refs/heads/'+BRANCH,'GITHUB_EVENT_NAME':'push','GITHUB_RUN_ATTEMPT':'1','GITHUB_RUN_NUMBER':'1','RUNNER_ENVIRONMENT':'github-hosted','RUNNER_OS':'Linux','PW_PUBLIC':'true'}
    if any(os.environ.get(k)!=v for k,v in expected.items()) or any(k.startswith('PARKWEAVE_') for k in os.environ):raise Closed('host gate')
    if not re.fullmatch('[a-f0-9]{40}',source) or source!=os.environ.get('GITHUB_SHA'):raise Closed('source shape')
    if git(['rev-parse','HEAD'],started).decode().strip()!=source or git(['branch','--show-current'],started).decode().strip()!=BRANCH or git(['status','--porcelain'],started):raise Closed('source checkout')
    if git(['rev-parse','HEAD^'],started).decode().strip()!=PARENT or set(git(['diff','--name-only',PARENT,source],started).decode().splitlines())!=PATHS:raise Closed('source parent paths')
    for name in ('template_browser_approval.json','template_http_approval.json'):
        if json.loads(regular(ROOT/'scripts'/name,2048))!={'version':1,'enabled':False,'reviewed_source':None,'invocation':None,'expires_utc':None}:raise Closed('business gate not closed')


def source_bytes(source,relative,started):
    raw=git(['show',source+':'+relative],started)
    if raw!=regular(ROOT/relative,128*1024):raise Closed('reviewed bytes drift')
    return raw


def helper(source,name,started):
    raw=source_bytes(source,'scripts/'+name+'.py',started)
    module=types.ModuleType('_cft_'+name);module.__file__=str(ROOT/'scripts'/(name+'.py'));sys.modules[module.__name__]=module
    exec(compile(raw,module.__file__,'exec'),module.__dict__)
    return module


def root_verify(path,fd,identity):
    a=path.lstat();b=os.fstat(fd)
    if path.parent!=Path(os.environ['RUNNER_TEMP']) or not re.fullmatch('cft-private-[a-f0-9]{32}',path.name) or path.resolve()!=path or not stat.S_ISDIR(a.st_mode) or a.st_uid!=os.geteuid() or stat.S_IMODE(a.st_mode)!=0o700 or (a.st_dev,a.st_ino)!=identity or not os.path.samestat(a,b):raise Closed('held private root drift')


def disk(path,deadline,report=None):
    left(deadline);logical=allocated=0
    for current,dirs,files in os.walk(path,followlinks=False):
        for child in dirs:
            if not stat.S_ISDIR((Path(current)/child).lstat().st_mode):raise Closed('unknown private directory')
        for name in [Path(current),*[Path(current)/n for n in files]]:
            st=name.lstat()
            if not (stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode)) or stat.S_ISLNK(st.st_mode):raise Closed('unexpected private object')
            if stat.S_ISREG(st.st_mode):logical+=st.st_size
            allocated+=st.st_blocks*512
    if report is not None:
        report['peak_logical_bytes']=max(report.get('peak_logical_bytes',0),logical)
        report['peak_allocated_bytes']=max(report.get('peak_allocated_bytes',0),allocated)
    if logical>CONTENT or allocated>=EARLY:raise Closed('disk monitoring stop')
    left(deadline)
    return logical,allocated


def save(path,value):
    raw=(json.dumps(value,sort_keys=True)+'\n').encode()
    if len(raw)>REPORT:raise Closed('report bound')
    temporary=path.with_name(path.name+'.next')
    with temporary.open('xb') as stream:stream.write(raw)
    os.replace(temporary,path)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kw):return None


def response(url,deadline):
    request=urllib.request.Request(url,headers={'Accept-Encoding':'identity'})
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    value=opener.open(request,timeout=left(deadline))
    if value.geturl()!=url or value.headers.get('Content-Encoding','identity')!='identity':value.close();raise Closed('HTTP response identity')
    return value


def get_fixed_archive(path,deadline,report):
    report['phase']='OFFICIAL_OBJECT_METADATA'
    with response(META,deadline) as stream:
        raw=stream.read(REPORT+1)
    left(deadline)
    if len(raw)>REPORT:raise Closed('metadata bound')
    expected={'name':OBJECT,'size':str(SIZE),'md5Hash':MD5,'crc32c':CRC32C,'generation':GENERATION}
    if json.loads(raw)!=expected:raise Closed('official object metadata changed')
    report['object']=expected;report['phase']='FIXED_OFFICIAL_DOWNLOAD';report['received']=0
    digest=sha256();transport=md5(usedforsecurity=False)
    with response(MEDIA,deadline) as stream,(path/'original.zip.partial').open('xb') as output:
        if stream.headers.get('x-goog-generation')!=GENERATION or stream.headers.get('Content-Length')!=str(SIZE):raise Closed('fixed object headers')
        connection=stream.fp.raw._sock
        while True:
            connection.settimeout(left(deadline))
            block=stream.read1(min(MiB,SIZE-report['received']+1));left(deadline)
            if not block:break
            report['received']+=len(block)
            if report['received']>SIZE:raise Closed('download size exceeded')
            output.write(block);digest.update(block);transport.update(block);disk(path,deadline,report)
    if report['received']!=SIZE or base64.b64encode(transport.digest()).decode()!=MD5:raise Closed('download integrity')
    (path/'original.zip.partial').rename(path/'original.zip')
    archive=path/'original.zip';before=archive.lstat();actual=sha256();count=0
    with archive.open('rb') as stream:
        if not stat.S_ISREG(before.st_mode) or before.st_uid!=os.geteuid() or stat.S_IMODE(before.st_mode)!=0o600 or not os.path.samestat(before,os.fstat(stream.fileno())):raise Closed('archive readback identity')
        for block in iter(lambda:stream.read(MiB),b''):
            left(deadline);actual.update(block);count+=len(block)
            if count>SIZE:raise Closed('archive readback growth')
    if count!=SIZE or actual.digest()!=digest.digest() or not os.path.samestat(before,archive.lstat()):raise Closed('archive readback mismatch')
    report.update(archive_sha256=digest.hexdigest(),md5_verified=True,crc32c_recomputed=False,publisher_sha256_available=False)


def reject_zip64(extra):
    offset=0
    while offset<len(extra):
        if offset+4>len(extra):raise Closed('malformed ZIP extra')
        tag,size=struct.unpack('<HH',extra[offset:offset+4]);offset+=4
        if offset+size>len(extra) or tag==1:raise Closed('ZIP64 or malformed ZIP extra')
        offset+=size


def entries(archive):
    # Bound central directory BEFORE zipfile allocates it. ZIP64/multidisk are
    # deliberately unsupported; unknown formats fail rather than enlarge caps.
    with archive.open('rb') as stream:
        size=stream.seek(0,2);stream.seek(max(0,size-65557));tail=stream.read(65557)
    index=tail.rfind(b'PK\x05\x06')
    if index<0 or len(tail)-index<22:raise Closed('EOCD')
    sig,diskno,central_disk,on_disk,count,cd_size,cd_offset,comment=struct.unpack('<4s4H2LH',tail[index:index+22])
    eocd=size-len(tail)+index
    if diskno or central_disk or on_disk!=count or not 1<=count<=4096 or cd_size>4*MiB or cd_offset+cd_size!=eocd or len(tail)-index!=22+comment or count==65535:raise Closed('bounded central directory')
    z=zipfile.ZipFile(archive)
    try:
        info=z.infolist();seen=set();total=0
        if len(info)!=count:raise Closed('entry count')
        for item in info:
            name=item.filename;parts=PurePosixPath(name).parts
            if len(name)>512 or not parts or parts[0]!='chrome-linux64' or '\\' in name or '\x00' in name or any(n in ('','.','..') for n in name.rstrip('/').split('/')) or name.startswith('/') or any(not re.fullmatch('[A-Za-z0-9_.+-]+',n) for n in parts):raise Closed('archive path')
            if item.extract_version>=45:raise Closed('ZIP64 version refused')
            reject_zip64(item.extra)
            z.fp.seek(item.header_offset);header=z.fp.read(30)
            if len(header)!=30 or header[:4]!=b'PK\x03\x04' or struct.unpack('<H',header[4:6])[0]>=45:raise Closed('local ZIP64 header refused')
            nlength,elength=struct.unpack('<HH',header[26:30])
            if nlength>512 or elength>4096 or item.header_offset+30+nlength+elength+item.compress_size>cd_offset:raise Closed('bounded local ZIP header')
            localname=z.fp.read(nlength)
            if localname!=name.encode('ascii'):raise Closed('local ZIP name mismatch')
            reject_zip64(z.fp.read(elength))
            key=name.rstrip('/')
            if key in seen:raise Closed('duplicate archive path')
            seen.add(key);mode=item.external_attr>>16;kind=stat.S_IFMT(mode)
            if item.create_system!=3 or kind not in (0,stat.S_IFREG,stat.S_IFDIR) or bool(mode&0o7022) or item.flag_bits&1 or item.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED):raise Closed('archive type or permissions')
            if item.is_dir()!=(kind==stat.S_IFDIR) or item.is_dir() and item.file_size!=0 or not 0<=item.file_size<=SINGLE:raise Closed('archive file layout')
            total+=item.file_size
            if total>UNPACK:raise Closed('unpacked declaration bound')
        chrome=next((x for x in info if x.filename=='chrome-linux64/chrome'),None)
        if chrome is None or chrome.is_dir() or not (chrome.external_attr>>16)&0o111:raise Closed('Chrome ordinary executable entry required')
        return z,info,total
    except BaseException as primary:
        try:z.close()
        except BaseException as cleanup:primary.archive_close_error=fault(cleanup)
        raise


def unpack(path,deadline,report):
    report['phase']='VALIDATE_ARCHIVE_LAYOUT';z,info,total=entries(path/'original.zip')
    report.update(entries=len(info),declared_unpacked=total,actual_unpacked=0,license_files=[],elf_sha256=None)
    primary=None
    try:
        for item in info:
            left(deadline);target=path/item.filename
            if item.is_dir():target.mkdir(mode=0o700,parents=True,exist_ok=True);continue
            target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            if target.parent.resolve()!=target.parent:raise Closed('extraction parent drift')
            mode=0o700 if (item.external_attr>>16)&0o111 else 0o600
            fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
            digest=sha256();written=0;report['phase']='BOUNDED_UNPACK'
            with os.fdopen(fd,'wb') as output,z.open(item) as source:
                while True:
                    left(deadline);block=source.read(MiB)
                    if not block:break
                    written+=len(block);report['actual_unpacked']+=len(block)
                    if written>item.file_size or report['actual_unpacked']>UNPACK:raise Closed('actual unpack size exceeded')
                    output.write(block);digest.update(block);disk(path,deadline,report)
            if written!=item.file_size:raise Closed('entry size mismatch')
            # Readback identity + bytes, with bounded streaming, not a whole-ELF allocation.
            before=target.lstat();check=sha256();read=0
            with target.open('rb') as stream:
                if not stat.S_ISREG(before.st_mode) or before.st_uid!=os.geteuid() or stat.S_IMODE(before.st_mode)!=mode or not os.path.samestat(before,os.fstat(stream.fileno())):raise Closed('extracted file identity')
                for block in iter(lambda:stream.read(MiB),b''):
                    left(deadline);check.update(block);read+=len(block)
                    if read>item.file_size:raise Closed('readback growth')
            if not os.path.samestat(before,target.lstat()) or read!=written or check.digest()!=digest.digest():raise Closed('extracted readback drift')
            if item.filename=='chrome-linux64/chrome':
                with target.open('rb') as binary:header=binary.read(64)
                if len(header)!=64 or header[:7]!=b'\x7fELF\x02\x01\x01' or struct.unpack('<H',header[16:18])[0] not in (2,3) or struct.unpack('<H',header[18:20])[0]!=62:raise Closed('ELF64 x86_64 required')
                report.update(elf_sha256=digest.hexdigest(),private_chrome_mode=oct(mode),elf_architecture='ELF64_X86_64',declared_browser_version='155.0.8059.39',browser_version_executed=False)
            if re.fullmatch(r'(ABOUT|LICENSE.*|COPYING.*|NOTICE.*|CREDITS.*)',target.name,re.I):
                if len(report['license_files'])>=32:raise Closed('license inventory bound')
                report['license_files'].append({'path':item.filename,'bytes':written,'sha256':digest.hexdigest()})
        if report['actual_unpacked']!=total:raise Closed('whole unpack mismatch')
        report['phase']='PRIVATE_LAYOUT_VERIFIED';report['status']='BYTES_LAYOUT_VERIFIED_REVIEW_REQUIRED'
        report.update(binary_license_inventory_complete=False,terms='https://www.google.com/chrome/terms/',new_terms_accepted=False,launch_authorized=False)
    except BaseException as error:primary=error
    try:z.close()
    except BaseException as cleanup:
        if primary is None:raise
        primary.archive_close_error=fault(cleanup)
    if primary is not None:raise primary


def valid_worker(value,source):
    expected={'name':OBJECT,'size':str(SIZE),'md5Hash':MD5,'crc32c':CRC32C,'generation':GENERATION}
    return (type(value) is dict and value.get('source')==source and value.get('executed') is False
        and value.get('status')=='BYTES_LAYOUT_VERIFIED_REVIEW_REQUIRED'
        and value.get('object')==expected and value.get('received')==SIZE
        and value.get('md5_verified') is True and value.get('launch_authorized') is False
        and value.get('crc32c_recomputed') is False and value.get('publisher_sha256_available') is False
        and bool(re.fullmatch('[0-9a-f]{64}',value.get('archive_sha256','')))
        and bool(re.fullmatch('[0-9a-f]{64}',value.get('elf_sha256','')))
        and value.get('elf_architecture')=='ELF64_X86_64' and value.get('browser_version_executed') is False
        and type(value.get('entries')) is int and 1<=value['entries']<=4096
        and type(value.get('declared_unpacked')) is int and 0<value['declared_unpacked']<=UNPACK
        and value.get('actual_unpacked')==value['declared_unpacked'])


def remove(path,fd,identity,deadline):
    root_verify(path,fd,identity)
    def walk(held):
        for name in os.listdir(held):
            left(deadline);before=os.stat(name,dir_fd=held,follow_symlinks=False)
            if stat.S_ISDIR(before.st_mode):
                child=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=held)
                try:
                    if not os.path.samestat(before,os.fstat(child)):raise Closed('cleanup child drift')
                    walk(child)
                finally:os.close(child)
                if not os.path.samestat(before,os.stat(name,dir_fd=held,follow_symlinks=False)):raise Closed('cleanup directory replaced')
                os.rmdir(name,dir_fd=held)
            elif stat.S_ISREG(before.st_mode):os.unlink(name,dir_fd=held)
            else:raise Closed('unknown cleanup object')
    walk(fd);root_verify(path,fd,identity);os.rmdir(path)


def worker(args):
    global ROOT
    ROOT=Path(args.repo)
    if ROOT.resolve()!=ROOT or ROOT!=Path(os.environ['GITHUB_WORKSPACE']).resolve():return 2
    handshake=json.loads(sys.stdin.buffer.readline(1025))
    if set(handshake)!={'parent_pid','worker_pid','started'} or handshake['worker_pid']!=os.getpid() or handshake['parent_pid']!=os.getppid():return 2
    started=handshake['started'];gate(args.source,started)
    activation=helper(args.source,'template_http_activation',started);tree=helper(args.source,'template_http_supervision',started)
    parent=tree.identity(os.getppid());claim=activation.OnceClaim.restore(args.claim,tuple(args.claim_identity),tuple(args.claim_file_identity),args.source,INVOCATION,os.getppid(),parent['start_ticks'])
    if claim.value['started']!=started:return 2
    path=Path(args.worker);fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);identity=tuple(args.identity)
    report={'status':'FAIL','phase':'WORKER_GATE','source':args.source,'executed':False}
    try:
        root_verify(path,fd,identity)
        if regular(Path(__file__),128*1024)!=git(['show',args.source+':scripts/cft_preparation_once.py'],started):raise Closed('frozen worker source drift')
        get_fixed_archive(path,started+WORK,report);root_verify(path,fd,identity);unpack(path,started+WORK,report);root_verify(path,fd,identity)
    except BaseException as error:
        report.update(status='FAIL',**fault(error))
        if hasattr(error,'archive_close_error'):report['archive_close_error']=error.archive_close_error
    finally:
        try:os.close(fd)
        except BaseException as cleanup:report.update(status='FAIL',root_close_error=fault(cleanup))
        try:save(path/'worker-result.json',report)
        except BaseException as publication:
            report['status']='FAIL'
            print(json.dumps({'stage':'WORKER_FINALIZATION','phase':report['phase'],
                'primary':{k:report[k] for k in ('error_type','reason_code','http_status') if k in report},
                'root_close_error':report.get('root_close_error'),'archive_close_error':report.get('archive_close_error'),
                'publication_error':fault(publication)}),flush=True)
    return 0 if report['status']=='BYTES_LAYOUT_VERIFIED_REVIEW_REQUIRED' else 1


def safe_failure(value):
    if type(value) is not dict or value.get('stage') not in ('WORKER_ADMISSION','WORKER_FINALIZATION'):return False
    def check(item):
        if item is None or type(item) in (int,bool):return True
        if type(item) is str:return bool(re.fullmatch('[A-Za-z0-9_]{1,96}',item))
        if type(item) is dict:return all(k in {'stage','phase','error_type','reason_code','http_status','primary','root_close_error','archive_close_error','publication_error'} and check(v) for k,v in item.items())
        return False
    return check(value)


def finish(out,report):
    try:
        if out is not None:save(out/'result.json',report)
    except BaseException as error:
        print(json.dumps({'status':'FAIL','stage':'PARENT_FINAL_REPORT','phase':report.get('phase'),
            'primary':{k:report[k] for k in ('error_type','reason_code','http_status','root_close_error') if k in report},
            'publication_error':fault(error)}),flush=True)
        return 1
    try:print(json.dumps({'status':report['status'],'scope':report['scope'],
        'phase':report.get('phase'),'reason_code':report.get('reason_code'),'error_type':report.get('error_type')}),flush=True)
    except BaseException:return 1
    return 0 if report['status']=='PREPARED_FOR_REVIEW_REQUIRES_EXIT_0' else 1


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--source',required=True);parser.add_argument('--worker');parser.add_argument('--repo');parser.add_argument('--identity',nargs=2,type=int);parser.add_argument('--claim');parser.add_argument('--claim-identity',nargs=2,type=int);parser.add_argument('--claim-file-identity',nargs=2,type=int);args=parser.parse_args(argv)
    os.umask(0o077)
    if args.worker:
        try:return worker(args)
        except BaseException as error:
            print(json.dumps({'stage':'WORKER_ADMISSION',**fault(error)}),flush=True);return 1
    if any((args.repo,args.identity,args.claim,args.claim_identity,args.claim_file_identity)):return 2
    started=time.monotonic();timer=threading.Timer(TOTAL,lambda:os._exit(124));timer.daemon=True;timer.start()
    report={'status':'NOT_COMPLETED','source':args.source,'scope':'OFFICIAL_CFT_PREPARATION_ONLY','Chrome_PG_API_started':False,'business_GET':0,'business_POST':0,'system_permissions_changed':False,'publisher_sha256_available':False,'launch_authorized':False,'phase':'SOURCE_GATE','required_exit':0,'limits':{'work_seconds':WORK,'supervision_seconds':TREE,'total_seconds':TOTAL,'unpacked_bytes':UNPACK,'file_content_bytes':CONTENT,'early_stop_allocated_bytes':EARLY,'monitor_threshold_bytes':MONITOR,'disk_hard_quota':False}}
    path=out=None;fd=None;identity=None
    try:
        gate(args.source,started);tree=helper(args.source,'template_http_supervision',started);activation=helper(args.source,'template_http_activation',started)
        report['phase']='PRIVATE_ROOT_AND_ONCE_CLAIM'
        parent=Path(os.environ['RUNNER_TEMP']);st=parent.lstat()
        if parent.resolve()!=parent or not stat.S_ISDIR(st.st_mode) or st.st_uid!=os.geteuid():raise Closed('owned runner temporary directory')
        out=parent/'cft-preparation-evidence';out.mkdir(mode=0o700,exist_ok=False);save(out/'result.json',report)
        claim=activation.OnceClaim.create(args.source,INVOCATION,started,tree.identity(os.getpid())['start_ticks'])
        path=parent/('cft-private-'+uuid4().hex);path.mkdir(mode=0o700,exist_ok=False);fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);st=os.fstat(fd);identity=(st.st_dev,st.st_ino);root_verify(path,fd,identity)
        if os.statvfs(path).f_bavail*os.statvfs(path).f_frsize<1536*MiB:raise Closed('at least1.5GiB free before preparation')
        raw=source_bytes(args.source,'scripts/cft_preparation_once.py',started)
        frozen=path/'.cft-worker.py'
        with frozen.open('xb') as stream:stream.write(raw)
        env={k:os.environ[k] for k in (*('PATH','LANG','LC_ALL','TZ'),*('GITHUB_SHA','GITHUB_WORKSPACE','RUNNER_TEMP'),*('GITHUB_REPOSITORY','GITHUB_REF','GITHUB_EVENT_NAME','GITHUB_RUN_ATTEMPT','GITHUB_RUN_NUMBER','RUNNER_ENVIRONMENT','RUNNER_OS','PW_PUBLIC')) if k in os.environ}
        env['PYTHONDONTWRITEBYTECODE']='1'
        command=[sys.executable,'-I',str(frozen),'--source',args.source,'--worker',str(path),'--repo',str(ROOT),'--identity',*map(str,identity),'--claim',str(claim.path),'--claim-identity',*map(str,claim.identity),'--claim-file-identity',*map(str,claim.file_identity)]
        report['phase']='OWNED_WORKER'
        owned=tree.supervise(command,env=env,cwd=ROOT,directory=path,started=started,overall_seconds=TREE,work_seconds=WORK)
        report['owned']=owned;root_verify(path,fd,identity)
        report['phase']='WORKER_RESULT_VALIDATION'
        result=path/'worker-result.json';report['worker']=json.loads(regular(result,REPORT)) if result.exists() else {'status':'NOT_OBSERVED'}
        if not result.exists():
            log=regular(path/'worker-output.log',REPORT)
            report['worker_output_bytes']=len(log);report['worker_output_sha256']=sha256(log).hexdigest()
            try:
                admission=json.loads(log)
                if safe_failure(admission):report['worker_failure']=admission
            except (ValueError,TypeError):pass
        report['status']='PREPARED_FOR_REVIEW_REQUIRES_EXIT_0' if owned['status']=='CLEANUP_CONFIRMED' and owned['operation_status']=='PASS' and valid_worker(report['worker'],args.source) else 'FAIL'
        if owned['status']=='CLEANUP_CONFIRMED' and (result.exists() or 'worker_failure' in report):
            report['phase']='OWNED_DIRECTORY_CLEANUP'
            remove(path,fd,identity,started+TOTAL);report['private_directory_removed']=True
        else:report.update(status='FAIL',private_directory_retained=True)
    except BaseException as error:report.update(status='FAIL',private_directory_retained=path is not None,**fault(error))
    finally:
        if fd is not None:
            try:os.close(fd)
            except OSError as error:report.update(status='FAIL',root_close_error=type(error).__name__)
    report['elapsed_seconds']=round(time.monotonic()-started,3)
    if time.monotonic()>=started+TOTAL:report['status']='FAIL'
    return finish(out,report)


if __name__=='__main__':raise SystemExit(main())
