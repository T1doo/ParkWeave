"""One fresh VM's actual controller. Every child and all raw output stay owned/private."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import pwd
import grp
import secrets
import signal
import stat
import subprocess
import sys
import time
import traceback
from uuid import uuid4

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row

from parkweave import native_run_access_restricted_host as host
from parkweave import native_run_access_writer as writer
from scripts.linux_trial.bootstrap import CASES,public_summary,setup_diagnostic,setup_frame


def private_file(path,raw,uid=0,gid=0,mode=0o600):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
    try:os.fchown(fd,uid,gid);os.fchmod(fd,mode);host._write_all(fd,raw);os.fsync(fd)
    finally:os.close(fd)


def sealed(value):
    fd=os.memfd_create('pwci-this-job-private',os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
    try:
        host._write_all(fd,writer._canonical(value).encode())
        fcntl.fcntl(fd,fcntl.F_ADD_SEALS,fcntl.F_SEAL_SEAL|fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK)
        return fd
    except BaseException:os.close(fd);raise


def signed(payload,key):
    return writer._canonical(dict(payload=payload,hmac_sha256=hmac.new(key,writer._canonical(payload).encode(),hashlib.sha256).hexdigest())).encode()


class Controller:
    def __init__(self,context):
        self.c=context;self.root=Path(context['root']);self.private=self.root/'private'
        self.processes=[];self.starts={};self.linux_host=None;self.writer_process=None
        self.value=dict(source_sha=context['source_sha'],phase='PROTECTED_RUNTIME',error='NONE',
                        cases={c:'NOT_RUN' for c in CASES},cleanup=False,setup_diagnostic=None)
        self.current='PROTECTED_RUNTIME';self.deadline=time.monotonic()+900

    def mark(self,name,condition):
        self.current=name
        if not condition:self.value['cases'][name]='FAIL';raise AssertionError(name)
        self.value['cases'][name]='PASS'

    def tool(self,args,*,uid=0,gid=0,timeout=60):
        if time.monotonic()>self.deadline:raise TimeoutError('JOB_DEADLINE')
        with (self.private/'tools.log').open('ab') as out:
            subprocess.run(args,env={'LANG':'C.UTF-8','PATH':'/usr/bin:/bin'},cwd='/',
                user=uid,group=gid,extra_groups=[],stdout=out,stderr=out,timeout=timeout,check=True)

    def own(self,process):
        self.processes.append(process);self.starts[id(process)]=writer._pid_started(process.pid);return process

    def stop(self,process):
        if process not in self.processes:raise PermissionError('EXACT_CREATED_CHILD_REQUIRED')
        if process.poll() is None:
            if writer._pid_started(process.pid)!=self.starts[id(process)]:raise PermissionError('CHILD_INSTANCE_CHANGED')
            process.send_signal(signal.SIGTERM)
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)

    def helper(self,mode,config,uid,gid,groups):
        fd=sealed(config)
        entry='import sys;sys.path[:]='+repr(self.c['imports'])+';from scripts.linux_trial.worker import main;raise SystemExit(main())'
        err=(self.private/('helper-'+mode+'-'+uuid4().hex+'.log')).open('wb')
        try:
            return self.own(subprocess.Popen([self.c['environment']+'/bin/python3.12','-I','-S','-B','-c',entry,mode,str(fd)],
                user=uid,group=gid,extra_groups=groups,pass_fds=(fd,),close_fds=True,cwd='/',env={'LANG':'C.UTF-8'},
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err))
        finally:os.close(fd);err.close()

    def call(self,process,value):
        process.stdin.write((writer._canonical(value)+'\n').encode());process.stdin.flush()
        import select
        if not select.select([process.stdout],[],[],12)[0]:raise TimeoutError('PRIVATE_API_RESPONSE_TIMEOUT')
        raw=process.stdout.readline(524289)
        if not raw or len(raw)>524288:raise AssertionError('PRIVATE_API_FRAME_MISSING')
        response=json.loads(raw)
        if set(response)!={'result'}:raise AssertionError('PRIVATE_API_FRAME_CONTRACT')
        return response['result']

    def request(self,process,method,path,*,actor='fixture-a',key=None,body=None):
        value=dict(method=method,path=path,actor=actor)
        if key is not None:value['key']=key
        if body is not None:value['body']=body
        return self.call(process,dict(operation='REQUEST',request=value))

    def owner(self,autocommit=False):
        c=psycopg.connect(self.owner_dsn,row_factory=dict_row,autocommit=autocommit,connect_timeout=2)
        check=c.execute('SELECT current_database() db,current_user role,(SELECT system_identifier::text FROM pg_control_system()) system').fetchone()
        if (check['db'],check['role'],check['system'])!=(self.spec['policy']['database_name'],'pwci_owner',self.spec['policy']['system_identifier']):
            c.close();raise PermissionError('THIS_NEW_CLUSTER_AND_TARGET_ONLY')
        if not autocommit:c.rollback()
        return c

    def snapshot(self):
        with self.owner() as c:
            return {t:c.execute('SELECT row_to_json(t) value FROM '+t+' t ORDER BY row_to_json(t)::text').fetchall()
                    for t in ('runs','run_assignments','principals','capability_grants','field_grants','action_grants','preparation_grants')}

    def identities(self):
        self.current='REAL_IDENTITIES'
        self.value['phase']='IDENTITIES'
        for name in ('pwci_api','pwci_writer'):
            try:pwd.getpwnam(name)
            except KeyError:pass
            else:raise PermissionError('NEW_IDENTITY_REQUIRED_NO_ADOPTION')
        try:grp.getgrnam('pwci_ipc')
        except KeyError:pass
        else:raise PermissionError('NEW_IPC_GROUP_REQUIRED')
        self.tool(['/usr/sbin/groupadd','pwci_ipc'])
        for name in ('pwci_api','pwci_writer'):
            self.tool(['/usr/sbin/useradd','--system','--no-create-home','--user-group','--groups','pwci_ipc','--shell','/usr/sbin/nologin',name])
        self.api=pwd.getpwnam('pwci_api');self.worker=pwd.getpwnam('pwci_writer');self.ipc=grp.getgrnam('pwci_ipc')
        self.pg=pwd.getpwnam('postgres')
        self.mark('REAL_IDENTITIES',self.api.pw_uid>0 and self.worker.pw_uid>0 and self.api.pw_uid!=self.worker.pw_uid and
                  all(x.pw_name in self.ipc.gr_mem for x in (self.api,self.worker)))

    def pg_start(self):
        self.current='FRESH_CLUSTER'
        self.value['phase']='PG_START'
        pgroot=self.root/'pg';pgroot.mkdir(mode=0o711)
        data=pgroot/'data';data.mkdir(mode=0o700);os.chown(data,self.pg.pw_uid,self.pg.pw_gid)
        socket=pgroot/'socket';socket.mkdir(mode=0o755);os.chown(socket,self.pg.pw_uid,self.pg.pw_gid)
        self.passwords={name:secrets.token_hex(32) for name in ('pwci_owner','pwci_app','pwci_writer')}
        password=pgroot/'init-password';private_file(password,self.passwords['pwci_owner'].encode()+b'\n',self.pg.pw_uid,self.pg.pw_gid)
        binaries=Path('/usr/lib/postgresql/16/bin')
        for name in ('initdb','postgres'):
            path=binaries/name;s=path.lstat();host._path_chain(str(path),{0})
            if not stat.S_ISREG(s.st_mode) or s.st_uid!=0 or s.st_mode&0o022:raise PermissionError('OFFICIAL_PG_REGULAR_BINARY_REQUIRED')
        self.tool([str(binaries/'initdb'),'-D',str(data),'--username=pwci_owner','--auth-local=scram-sha-256',
                   '--auth-host=scram-sha-256','--pwfile='+str(password),'--no-locale','--encoding=UTF8'],uid=self.pg.pw_uid,gid=self.pg.pw_gid,timeout=90)
        out=(self.private/'owned-pg.log').open('wb')
        try:
            pg=self.own(subprocess.Popen([str(binaries/'postgres'),'-D',str(data),'-k',str(socket),'-p','55439',
                '-c',"listen_addresses=",'-c','unix_socket_permissions=0777','-c','log_statement=none',
                '-c','log_min_error_statement=panic','-c','log_error_verbosity=terse'],
                user=self.pg.pw_uid,group=self.pg.pw_gid,extra_groups=[],cwd='/',env={'LANG':'C.UTF-8'},stdout=out,stderr=out))
        finally:out.close()
        maintenance=make_conninfo(host=str(socket),port=55439,dbname='postgres',user='pwci_owner',password=self.passwords['pwci_owner'])
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            if pg.poll() is not None:raise AssertionError('OWNED_PG_EXITED')
            try:
                with psycopg.connect(maintenance,connect_timeout=1,row_factory=dict_row) as c:
                    initial=c.execute('SELECT datname FROM pg_database ORDER BY datname').fetchall()
                break
            except psycopg.OperationalError:time.sleep(.05)
        else:raise TimeoutError('OWNED_PG_NOT_READY')
        self.mark('FRESH_CLUSTER',{r['datname'] for r in initial}=={'postgres','template0','template1'})
        self.value['phase']='PG_SETUP'
        self.current='ACTUAL_ROLE_ACL'
        db='fixture_'+uuid4().hex
        actors=['fixture-a','fixture-b','fixture-c','prep-specialist-fixture-a','prep-specialist-fixture-b','prep-specialist-fixture-c','executor-a','unassigned']
        self.tokens={name:secrets.token_urlsafe(32) for name in actors}
        setup=dict(pg_uid=self.pg.pw_uid,data=str(data),root=str(self.root),owner_maintenance_dsn=maintenance,database=db,
                   tokens=self.tokens,passwords=self.passwords,api_uid=self.api.pw_uid,writer_uid=self.worker.pw_uid)
        self.value['setup_diagnostic']=setup_diagnostic(dict(substage='INPUT',check_id='HELPER_ENTRY',status_code=0))
        p=self.helper('SETUP',setup,self.pg.pw_uid,self.pg.pw_gid,[])
        self.value['setup_diagnostic']=setup_diagnostic(dict(substage='TRANSPORT',check_id='HELPER_FRAME',status_code=0))
        output,_=p.communicate(timeout=120)
        outcome,diagnostic,result=setup_frame(output,p.returncode)
        self.value['setup_diagnostic']=diagnostic
        if outcome!='PASS':raise AssertionError('ORIGINAL_ISSUED_SETUP_FAILED')
        self.setup=result;self.spec=self.setup['spec'];self.parent=self.setup['parent']
        self.owner_dsn=make_conninfo(maintenance,dbname=db)

    def host_start(self):
        self.current='PROTECTED_RUNTIME'
        self.value['phase']='HOST_START'
        for name,uid,gid,mode in [('host',0,self.ipc.gr_gid,0o750),('writer',self.worker.pw_uid,self.ipc.gr_gid,0o710)]:
            p=self.root/name;p.mkdir(mode=mode);os.chown(p,uid,gid);os.chmod(p,mode)
        secret=dict(writer_dsn=self.setup['writer_dsn'],key=secrets.token_hex(32));approval_key=secrets.token_bytes(32)
        private_file(self.root/'writer/bootstrap.json',writer._canonical(secret).encode(),self.worker.pw_uid,self.worker.pw_gid)
        private_file(self.root/'host/approval.key',approval_key)
        creation=signed(self.setup['creation'],approval_key);private_file(self.root/'host/creation-receipt.json',creation)
        source=Path(self.c['source']);env=Path(self.c['environment'])
        self.layout=host.RuntimeLayout(trial_root=str(self.root),source_sha=self.c['source_sha'],source_root=str(source),
            source_files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (source/'parkweave').rglob('*') if p.is_file()},
            interpreter=str(env/'bin/python3.12'),interpreter_sha256=hashlib.sha256((env/'bin/python3.12').read_bytes()).hexdigest(),
            dependency_roots=[str(env)],import_paths=self.c['imports'][1:],api_uid=self.api.pw_uid,api_gid=self.api.pw_gid,
            writer_uid=self.worker.pw_uid,ipc_gid=self.ipc.gr_gid,boot_id=str(uuid4()),
            private_bootstrap_sha256=hashlib.sha256((self.root/'writer/bootstrap.json').read_bytes()).hexdigest(),creation_receipt_sha256=hashlib.sha256(creation).hexdigest())
        host._code_check(self.layout);host._dependencies_check(self.layout);host._imports_check(self.layout);host._identities_check(self.layout)
        self.mark('PROTECTED_RUNTIME',True)
        self.linux_host=host.LinuxHost(self.spec,self.layout.model_dump())
        private_file(self.root/'host/start-approval.json',signed(host.launch_request(self.spec,self.layout),approval_key))
        self.current='HOST_CHANNELS';self.writer_process,pin=self.linux_host.start(self.layout.approval_path)
        observed=host._process(self.writer_process.pid)
        self.mark('HOST_CHANNELS',observed['uid']==self.worker.pw_uid and observed['gid']==self.ipc.gr_gid and
                  not observed['groups'] and pin.command_inode!=pin.verify_inode and os.geteuid()==0)
        self.api_config=dict(api_uid=self.api.pw_uid,api_gid=self.api.pw_gid,ipc_gid=self.ipc.gr_gid,
            app_dsn=self.setup['app_dsn'],tokens=self.tokens,binding_path=self.layout.binding_path,
            binding_sha256=hashlib.sha256(Path(self.layout.binding_path).read_bytes()).hexdigest(),writer_private_path=self.layout.bootstrap_path)
        self.client=self.helper('API',self.api_config,self.api.pw_uid,self.api.pw_gid,[self.ipc.gr_gid])
        view=self.call(self.client,{'operation':'IDENTITY'})
        self.mark('API_PRIVATE_BOUNDARY',view['uid']==self.api.pw_uid and view['gid']==self.api.pw_gid and view['ipc_member'] and view['writer_private_blocked'])
        self.mark('ACTUAL_ROLE_ACL',view['role']['role']==view['role']['session']=='pwci_app' and
                  not view['role']['assignment_write'] and not view['role']['identity_write'])
        self.access='/api/runs/'+self.parent['run_id']+'/access'
        closed=self.request(self.client,'GET',self.access)
        self.mark('EXPLICIT_BIND',closed['status']==200 and not closed['body']['enabled'] and self.call(self.client,{'operation':'BIND'})['bound'])

    def command_body(self,action):
        r=self.request(self.client,'GET',self.access,actor='prep-specialist-fixture-a' if action=='APPROVE' else 'fixture-a')
        if r['status']!=200:raise AssertionError('CURRENT_VIEW_REQUIRED')
        view=r['body'];body=dict(action=action,expected_revision=view['revision'],expected_run_revision=view['run_revision'],
            expected_authority_sha256=view['authority_sha256'],reason='SYNTHETIC one approved trial '+action)
        if action=='REQUEST':
            now=datetime.now(timezone.utc);self.lease_until=now+timedelta(seconds=90)
            body.update(confirm_request=True,target_id='executor-a',target_role='service_executor',capability='READ',
                requested_validity=dict(valid_from=now.isoformat(),valid_until=self.lease_until.isoformat(),timezone='UTC'))
        if action=='APPROVE':body['approved_validity']=view['request']['requested_validity']
        return body

    def activation_body(self):
        view=self.request(self.client,'GET',self.access)['body']
        return dict(action='ACTIVATE',lease_id=view['lease_id'],expected_revision=view['revision'],expected_run_revision=view['run_revision'],
            expected_activation_revision=view['activation_revision'],expected_authority_sha256=view['authority_sha256'],
            activation_policy_sha256=view['activation_policy_sha256'],confirm_activate=True,reason='SYNTHETIC explicit activation')

    def fault(self,field,enabled):
        with self.owner() as c:
            if enabled:
                c.execute("CREATE FUNCTION ci_atomic_failure() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'SYNTHETIC rollback'; END $$")
                c.execute('CREATE TRIGGER ci_atomic_failure BEFORE UPDATE OF '+field+' ON runs FOR EACH ROW EXECUTE FUNCTION ci_atomic_failure()')
            else:
                c.execute('DROP TRIGGER ci_atomic_failure ON runs');c.execute('DROP FUNCTION ci_atomic_failure()')

    def acceptance(self):
        self.value['phase']='ACCEPTANCE'
        before=self.snapshot();body=self.command_body('REQUEST')
        self.current='EVENT_ROLLBACK';self.fault('native_run_access_protocol',True)
        failed=self.request(self.client,'POST',self.access+'/commands',key='ci-event-failure',body=body)
        self.mark('EVENT_ROLLBACK',failed['status']==409 and self.snapshot()==before)
        self.fault('native_run_access_protocol',False)
        self.current='REAL_PARENT_LOCK';body=self.command_body('REQUEST')
        with self.owner() as blocker:
            blocker.execute('SELECT * FROM preparations WHERE id=%s FOR UPDATE',(self.parent['preparation_id'],))
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(self.request,self.client,'POST',self.access+'/commands',key='ci-request-once',body=body)
                deadline=time.monotonic()+3;seen=False
                while time.monotonic()<deadline:
                    with self.owner() as observer:
                        row=observer.execute("SELECT count(*) n FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE %s",('%FROM preparations WHERE%',)).fetchone()
                    if row['n']>=1:seen=True;break
                    time.sleep(.02)
                blocker.commit();result=future.result(timeout=12)
        self.mark('REAL_PARENT_LOCK',seen and result['status']==200)
        approved=self.request(self.client,'POST',self.access+'/commands',actor='prep-specialist-fixture-a',key='ci-approve-once',body=self.command_body('APPROVE'))
        self.mark('REQUEST_APPROVE',approved['status']==200 and approved['body']['state']=='APPROVED')
        activation=self.activation_body();before=self.snapshot();self.current='ACTIVATION_ROLLBACK';self.fault('native_run_access_activation',True)
        failed=self.request(self.client,'POST',self.access+'/activate',key='ci-activation-failure',body=activation)
        self.mark('ACTIVATION_ROLLBACK',failed['status']==409 and self.snapshot()==before)
        self.fault('native_run_access_activation',False)
        self.current='LOST_RESPONSE_GET';key='ci-activation-dropped'
        frame=dict(operation='ACTIVATE',nonce=uuid4().hex,run_id=self.parent['run_id'],token=self.tokens['fixture-a'],request_key=key,command=activation)
        self.call(self.client,dict(operation='RAW_WRITER_DROP',frame=frame))
        deadline=time.monotonic()+8;recovered=None
        # Only GET the original key, never resubmit the dropped frame.
        while time.monotonic()<deadline:
            r=self.request(self.client,'GET',self.access+'/commands/'+key)
            if r['status']==200 and r['body']['found']:recovered=r['body'];break
            time.sleep(.05)
        with self.owner() as c:
            count=c.execute("SELECT count(*) n FROM run_assignments WHERE principal_id='executor-a' AND run_id=%s",(self.parent['run_id'],)).fetchone()['n']
        self.mark('LOST_RESPONSE_GET',recovered is not None and recovered['actual_assignment_written'] and count==1)
        fresh=self.helper('API',self.api_config,self.api.pw_uid,self.api.pw_gid,[self.ipc.gr_gid])
        cold=self.request(fresh,'GET','/api/runs/'+self.parent['run_id'],actor='executor-a')
        self.call(fresh,{'operation':'BIND'})
        live=self.request(fresh,'GET','/api/runs/'+self.parent['run_id'],actor='executor-a')
        again=self.request(fresh,'GET',self.access+'/commands/'+key)
        self.mark('COLD_REBIND',cold['status']==403 and live['status']==200 and again['body']['receipt']==recovered['receipt'])
        self.current='LEASE_EXPIRY'
        while datetime.now(timezone.utc)<=self.lease_until+timedelta(milliseconds=150):
            if time.monotonic()>self.deadline:raise TimeoutError('JOB_DEADLINE')
            time.sleep(.1)
        expired=self.request(fresh,'GET','/api/runs/'+self.parent['run_id'],actor='executor-a')
        historical=self.request(fresh,'GET',self.access+'/commands/'+key)
        self.mark('LEASE_EXPIRY',expired['status']==403 and historical['status']==200 and historical['body']['receipt']==recovered['receipt'])
        # Real original material command changes the source after expiry; no identity/grant mutation.
        from parkweave import preparation as prep
        from parkweave.store import Store
        from uuid import UUID
        owner=Store(self.owner_dsn)
        prep.command(owner,self.tokens['fixture-a'],UUID(self.parent['preparation_id']),'ci-material-reopen',
            prep.PreparationCommand(action='REOPEN',expected_revision=self.parent['revision'],reason='SYNTHETIC changed source'))
        revoke=self.request(self.client,'POST',self.access+'/commands',key='ci-revoke-once',body=self.command_body('REVOKE'))
        self.mark('CHANGED_SOURCE_REVOKE',revoke['status']==200 and revoke['body']['state']=='REVOKED')
        renewal=self.request(self.client,'POST',self.access+'/commands',key='ci-no-renewal',body=self.command_body('REQUEST'))
        self.mark('NO_RENEWAL',renewal['status'] in (403,409))
        after=self.snapshot()
        self.mark('ACTUAL_ROLE_ACL',all(after[t]==before[t] for t in ('principals','capability_grants','field_grants','action_grants','preparation_grants')))

    def cleanup(self):
        self.value['phase']='CLEANUP';ok=True
        try:
            if self.writer_process is not None:self.linux_host.stop(self.writer_process)
        except BaseException:ok=False
        for p in reversed(self.processes):
            try:self.stop(p)
            except BaseException:ok=False
        self.value['cleanup']=ok
        self.value['cases']['OWNED_STOP']='PASS' if ok else 'FAIL'
        return ok

    def run(self):
        def terminate(signum,frame):raise TimeoutError('OWNED_CONTROLLER_TERMINATION')
        signal.signal(signal.SIGTERM,terminate)
        try:
            if os.geteuid()!=0 or self.c['approval']!='USER_CONFIRMED_ONE_FREE_GITHUB_VM_2026-10-12T12:49:49Z':raise PermissionError('APPROVED_ROOT_CONTROLLER_REQUIRED')
            self.identities();self.pg_start();self.host_start();self.acceptance()
        except BaseException as exc:
            self.value['cases'][self.current]='FAIL'
            self.value['error']='OS_REFUSED' if isinstance(exc,PermissionError) else 'TIMEOUT' if isinstance(exc,(TimeoutError,subprocess.TimeoutExpired)) else 'CHECK_FAILED' if isinstance(exc,(AssertionError,ValueError)) else 'ADAPTER_DENIED' if type(exc).__name__=='Denied' else 'INTERNAL_ERROR'
            private_file(self.private/'acceptance-failure.log',traceback.format_exc().encode())
        finally:
            prior=self.value['phase'];clean=self.cleanup()
            if self.value['error']=='NONE' and clean:self.value['phase']='COMPLETE'
            else:self.value['phase']=prior
        # Validate projection before returning it; no raw data or exception repr enters stdout.
        public_summary(self.value)
        sys.stdout.write(json.dumps(self.value,sort_keys=True));sys.stdout.flush()
        return 0 if self.value['error']=='NONE' and all(v=='PASS' for v in self.value['cases'].values()) else 1


def main():
    if len(sys.argv)!=2:raise ValueError('EXPLICIT_PROTECTED_CONTEXT_REQUIRED')
    path=Path(sys.argv[1]);s=path.lstat()
    if s.st_uid!=0 or stat.S_IMODE(s.st_mode)!=0o600 or not stat.S_ISREG(s.st_mode):raise PermissionError('ROOT_PRIVATE_CONTEXT_REQUIRED')
    return Controller(json.loads(path.read_text())).run()
