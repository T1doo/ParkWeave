"""One root-sealed controller; fixed new resources, original host and Case API."""
from datetime import datetime,timezone
import hashlib,json,os,pwd,grp,re,select,shutil,signal,stat,subprocess,sys,time,traceback,types
from pathlib import Path
from uuid import uuid4

from psycopg.conninfo import make_conninfo
from parkweave import native_run_access_restricted_host as host,native_run_access_writer as writer
from parkweave.case_cancellation_business_binding import BusinessBinding
from scripts.linux_trial import controller as reference
from scripts.linux_trial.worker import sealed_input
from scripts.host_case_once.bootstrap import APPROVAL_REF,initial,public_summary,Diagnostic,register_source

_BOOT_ISSUER=object()
USERS=('pwci_api','pwci_writer')
GROUPS=('pwci_ipc','pwci_api','pwci_writer')

class CleanupTimeout(TimeoutError):
    """Escape every per-resource cleanup handler when the absolute budget expires."""


def context_valid(c):
    keys={'root','source_sha','source','environment','imports','approval_ref','bootstrap_pid','bootstrap_started'}
    if (type(c) is not dict or set(c)!=keys or c['approval_ref']!=APPROVAL_REF or
            type(c['root']) is not str or not re.fullmatch('/tmp/parkweave-trial-[a-f0-9]{32}',c['root']) or
            type(c['source_sha']) is not str or not re.fullmatch('[a-f0-9]{40}',c['source_sha']) or
            c['source']!=c['root']+'/source' or c['environment']!=c['root']+'/environment' or
            c['imports']!=[c['source'],c['environment']+'/lib/python3.12',
                c['environment']+'/lib/python3.12/lib-dynload',c['environment']+'/lib/python3.12/site-packages'] or
            type(c['bootstrap_pid']) is not int or c['bootstrap_pid']<=0 or type(c['bootstrap_started']) is not str):
        return False
    return True


class Controller(reference.Controller):
    def __init__(self,context,issuer=None):
        super().__init__(context)
        self.value=initial(context['source_sha']);self.issuer=issuer;self.diag=Diagnostic(self.value['diagnostics'])
        self.created_users={};self.created_groups={};self.creation_attempts=0
        self.business=None;self.setup_process=None;self.pg_process=None;self.root_instance=None
        self.deadline=time.monotonic()+750
        self.cleanup_deadline=None

    def budget(self,timeout):
        if self.cleanup_deadline is not None:
            remaining=self.cleanup_deadline-time.monotonic()
            if remaining<=0:raise CleanupTimeout('bounded cleanup deadline')
            return min(timeout,remaining)
        return timeout

    def tool(self,args,*,uid=0,gid=0,timeout=60):
        return super().tool(args,uid=uid,gid=gid,timeout=self.budget(timeout))

    def write_frame(self,p,value,timeout=12):
        if p not in self.processes:raise PermissionError('retained helper required')
        raw=(writer._canonical(value)+'\n').encode()
        if len(raw)>524288:raise ValueError('bounded request required')
        until=time.monotonic()+self.budget(timeout);offset=0
        while offset<len(raw):
            remaining=self.budget(until-time.monotonic())
            if remaining<=0 or not select.select([],[p.stdin],[],remaining)[1]:raise TimeoutError('bounded private write required')
            count=os.write(p.stdin.fileno(),raw[offset:offset+4096])
            if count<=0:raise ValueError('private pipe closed')
            offset+=count

    def read_frame(self,p,timeout):
        if p not in self.processes:raise PermissionError('retained helper required')
        until=time.monotonic()+self.budget(timeout);raw=bytearray()
        while True:
            remaining=self.budget(until-time.monotonic())
            if remaining<=0 or not select.select([p.stdout],[],[],remaining)[0]:raise TimeoutError('bounded private frame required')
            chunk=os.read(p.stdout.fileno(),min(65536,524289-len(raw)))
            if not chunk:raise ValueError('private frame missing')
            raw.extend(chunk)
            if len(raw)>524288:raise ValueError('private frame too large')
            if b'\n' in raw:
                if not raw.endswith(b'\n') or raw.count(b'\n')!=1:raise ValueError('one private frame required')
                return json.loads(raw)

    def call(self,p,value):
        if p not in self.processes:raise PermissionError('retained helper required')
        until=time.monotonic()+self.budget(12)
        self.write_frame(p,value,timeout=until-time.monotonic())
        remaining=until-time.monotonic()
        if remaining<=0:raise TimeoutError('bounded private response required')
        frame=self.read_frame(p,remaining)
        if type(frame) is not dict or set(frame)!={'result'}:raise ValueError('closed private response required')
        return frame['result']

    def identities(self):
        self.current='REAL_IDENTITIES';self.value['phase']='IDENTITIES'
        self.pg=pwd.getpwnam('postgres') # Existing account only; no modification.
        for name in USERS:
            try:pwd.getpwnam(name)
            except KeyError:pass
            else:raise PermissionError('new identity collision; no adoption')
        for name in GROUPS:
            try:grp.getgrnam(name)
            except KeyError:pass
            else:raise PermissionError('new group collision; no adoption')
        for name in GROUPS:
            self.creation_attempts+=1;self.tool(['/usr/sbin/groupadd','--system',name])
            g=grp.getgrnam(name);self.created_groups[name]=g.gr_gid
        for name in USERS:
            self.creation_attempts+=1
            self.tool(['/usr/sbin/useradd','--system','--no-log-init','--no-create-home','--home-dir','/nonexistent',
                '--gid',name,'--groups','pwci_ipc','--shell','/usr/sbin/nologin',name])
            p=pwd.getpwnam(name);self.created_users[name]=(p.pw_uid,p.pw_gid)
        self.api=pwd.getpwnam('pwci_api');self.worker=pwd.getpwnam('pwci_writer');self.ipc=grp.getgrnam('pwci_ipc')
        self.mark('REAL_IDENTITIES',self.api.pw_uid>0 and self.worker.pw_uid>0 and self.api.pw_uid!=self.worker.pw_uid and
            all(x.pw_name in self.ipc.gr_mem for x in (self.api,self.worker)))

    def helper(self,mode,config,uid,gid,groups):
        fd=reference.sealed(config)
        entry='import sys;sys.path[:]='+repr(self.c['imports'])+';from scripts.host_case_once.worker import main;raise SystemExit(main())'
        with (self.private/('helper-'+mode+'-'+uuid4().hex+'.log')).open('wb') as err:
            try:return self.own(subprocess.Popen([self.c['environment']+'/bin/python3.12','-I','-S','-B','-c',entry,mode,str(fd)],
                user=uid,group=gid,extra_groups=groups,pass_fds=(fd,),close_fds=True,cwd='/',env={'LANG':'C.UTF-8'},
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err))
            finally:os.close(fd)

    def pg_start(self):
        self.current='FRESH_CLUSTER';self.value['phase']='PG_START'
        pgroot=self.root/'pg';pgroot.mkdir(mode=0o711)
        data=pgroot/'data';data.mkdir(mode=0o700);os.chown(data,self.pg.pw_uid,self.ipc.gr_gid)
        socket=pgroot/'socket';socket.mkdir(mode=0o750);os.chown(socket,self.pg.pw_uid,self.ipc.gr_gid)
        import secrets
        self.passwords={k:secrets.token_hex(32) for k in ('pwci_owner','pwci_app','pwci_writer','pwci_case')}
        password=pgroot/'init-password';reference.private_file(password,self.passwords['pwci_owner'].encode()+b'\n',self.pg.pw_uid,self.ipc.gr_gid)
        binaries=Path('/usr/lib/postgresql/16/bin')
        for name in ('initdb','postgres'):
            p=binaries/name;s=p.lstat();host._path_chain(str(p),{0})
            if not stat.S_ISREG(s.st_mode) or s.st_uid!=0 or s.st_mode&0o022:raise PermissionError('official PG16 binary required')
        self.tool([str(binaries/'initdb'),'-D',str(data),'--username=pwci_owner','--auth-local=scram-sha-256',
            '--auth-host=reject','--pwfile='+str(password),'--no-locale','--encoding=UTF8'],uid=self.pg.pw_uid,gid=self.ipc.gr_gid,timeout=60)
        with (self.private/'owned-pg.log').open('wb') as log:
            self.pg_process=self.own(subprocess.Popen([str(binaries/'postgres'),'-D',str(data),'-k',str(socket),'-p','55439',
                '-c','listen_addresses=','-c','unix_socket_permissions=0770','-c','log_statement=none',
                '-c','log_min_error_statement=panic','-c','log_error_verbosity=terse'],user=self.pg.pw_uid,
                group=self.ipc.gr_gid,extra_groups=[],cwd='/',env={'LANG':'C.UTF-8'},stdout=log,stderr=log))
        maintenance=make_conninfo(host=str(socket),port=55439,dbname='postgres',user='pwci_owner',password=self.passwords['pwci_owner'])
        import psycopg
        from psycopg.rows import dict_row
        until=time.monotonic()+10
        # Readiness comes from this exact retained process's own log, not connection retries.
        while b'database system is ready to accept connections' not in (self.private/'owned-pg.log').read_bytes()[:1048576]:
            if self.pg_process.poll() is not None or time.monotonic()>until:raise TimeoutError('owned PG not ready')
            time.sleep(.05)
        with psycopg.connect(maintenance,row_factory=dict_row,connect_timeout=2) as c:
            initial_db={r['datname'] for r in c.execute('SELECT datname FROM pg_database').fetchall()}
        self.mark('FRESH_CLUSTER',initial_db=={'postgres','template0','template1'})
        actors=('fixture-a','fixture-b','fixture-c','prep-specialist-fixture-a','prep-specialist-fixture-b',
            'prep-specialist-fixture-c','executor-a','unassigned')
        self.tokens={k:secrets.token_urlsafe(32) for k in actors}
        self.current='SETUP';self.value['phase']='PG_SETUP'
        config=dict(pg_uid=self.pg.pw_uid,data=str(data),root=str(self.root),owner_maintenance_dsn=maintenance,
            database='fixture_'+uuid4().hex,tokens=self.tokens,passwords=self.passwords,
            api_uid=self.api.pw_uid,writer_uid=self.worker.pw_uid)
        self.setup_process=self.helper('SETUP',config,self.pg.pw_uid,self.ipc.gr_gid,[])
        frame=self.read_frame(self.setup_process,120)
        if set(frame)!= {'outcome','result'} or frame['outcome']!='PASS':raise AssertionError('original owned setup failed')
        self.setup=frame['result'];self.spec=self.setup['spec'];self.parent=self.setup['parent']
        self.owner_dsn=make_conninfo(maintenance,dbname=config['database'])
        self.mark('SETUP',True);self.mark('BUSINESS_ACL',True)

    def acceptance(self):
        self.value['phase']='ACCEPTANCE';self.current='REQUEST_APPROVE'
        requested=self.request(self.client,'POST',self.access+'/commands',key='ci-request',body=self.command_body('REQUEST'))
        approved=self.request(self.client,'POST',self.access+'/commands',actor='prep-specialist-fixture-a',key='ci-approve',body=self.command_body('APPROVE'))
        self.mark('REQUEST_APPROVE',requested['status']==approved['status']==200 and approved['body']['state']=='APPROVED')
        key='ci-native-activate';activated=self.request(self.client,'POST',self.access+'/activate',key=key,body=self.activation_body())
        self.mark('NATIVE_ACTIVATION',activated['status']==200 and activated['body']['actual_assignment_written'])
        b=BusinessBinding.from_spec(self.spec,business_role='pwci_case',trial_root=str(self.root))
        cfg=dict(api_uid=self.api.pw_uid,api_gid=self.api.pw_gid,ipc_gid=self.ipc.gr_gid,spec=self.spec,
            business_binding=b.model_dump(),business_dsn=self.setup['business_dsn'],tokens=self.tokens)
        self.business=self.helper('BUSINESS',cfg,self.api.pw_uid,self.api.pw_gid,[self.ipc.gr_gid])
        identity=self.call(self.business,dict(operation='IDENTITY'))
        self.mark('BUSINESS_BIND',identity==dict(session='pwci_case',role='pwci_case',control=False))
        before=self.call(self.setup_process,dict(operation='SNAPSHOT'))
        view=self.call(self.business,dict(operation='READ'))
        if view['status']!=200 or not view['body']['can_cancel']:raise AssertionError('explicit current cancellation view required')
        v=view['body'];body=dict(case_id=v['case_id'],expected_preparation_revision=v['preparation_revision'],
            expected_lifecycle_revision=v['lifecycle_revision'],expected_source_sha256=v['source_sha256'],
            confirm_cancel=True,reason='SYNTHETIC owner explicitly cancels this one Case')
        b.check_cancel_request(self.parent['preparation_id'],body)
        self.current='CASE_CANCEL';original_key='ci-cancel-dropped'
        sent=self.call(self.business,dict(operation='CANCEL_DROP',key=original_key,body=body))
        self.mark('CASE_CANCEL',sent==dict(sent_once=True))
        recovery=self.call(self.business,dict(operation='RECOVER',key=original_key))
        self.mark('ORIGINAL_KEY_RECOVERY',recovery['status']==200 and recovery['body']['status']=='COMMITTED' and
            recovery['body']['current']['case_state']=='CANCELLED' and not recovery['body']['automatically_replayed'])
        after=self.call(self.setup_process,dict(operation='SNAPSHOT'))
        events=[r['value'] for r in after['case_local_events'] if r['value']['request_key']==original_key]
        if (len(after['case_local_events'])!=len(before['case_local_events'])+1 or len(events)!=1 or
                events[0]['id']!=recovery['body']['event_id'] or events[0]['action']!='CANCEL_BEFORE_ACCEPT' or
                events[0]['payload']['request']!=body or events[0]['payload']['resource_release_automatic'] is not False or
                len(after['cases'])!=1 or after['cases'][0]['value']['id']!=body['case_id'] or
                after['cases'][0]['value']['state']!='CANCELLED' or
                len(after['case_local_lifecycles'])!=1 or after['case_local_lifecycles'][0]['value']['state']!='CANCELLED'):
            raise AssertionError('one original atomic cancellation event/state required')
        native_history=self.request(self.client,'GET',self.access+'/commands/'+key)
        changed={'cases','case_local_lifecycles','case_local_events'}
        self.mark('HISTORY_RETAINED',all(before[t]==after[t] for t in before if t not in changed) and
            native_history['status']==200 and native_history['body']['actual_assignment_written'] and
            all(r['value']['state']=='SUCCEEDED' for r in after['runs']))
        conflict=self.call(self.business,dict(operation='CHANGED_KEY',key=original_key,body={**body,'reason':'SYNTHETIC changed reason'}))
        late=self.call(self.business,dict(operation='LATE_MATERIAL'))
        final=self.call(self.setup_process,dict(operation='SNAPSHOT'))
        self.mark('LATE_WRITE_REFUSED',conflict['status']==late['status']==409 and final==after)

    def _stop_owned(self,p,allowed):
        if p not in self.processes:raise PermissionError('retained child required')
        if p.poll() is None:
            if writer._pid_started(p.pid)!=self.starts[id(p)]:raise PermissionError('owned child instance changed')
            p.terminate()
            try:p.wait(timeout=self.budget(10))
            except subprocess.TimeoutExpired:p.kill();p.wait(timeout=self.budget(5));raise RuntimeError('forced stop is not cleanup PASS')
        if type(p.returncode) is not int or p.returncode not in allowed:raise RuntimeError('owned exit result required')

    def _close_owned(self,p):
        if p not in self.processes:raise PermissionError('retained child required')
        if p.poll() is None:
            if writer._pid_started(p.pid)!=self.starts[id(p)]:raise PermissionError('owned child instance changed')
            # CLOSE has no reply: the helper drains/exits normally, not an RPC result.
            self.write_frame(p,dict(operation='CLOSE'))
            try:p.wait(timeout=self.budget(10))
            except subprocess.TimeoutExpired:
                self._stop_owned(p,{0,-signal.SIGTERM})
                raise RuntimeError('normal helper close required')
        if type(p.returncode) is not int or p.returncode!=0:raise RuntimeError('normal helper exit required')

    def _no_unknown_identity_users(self):
        uids={v[0] for v in self.created_users.values()};gids=set(self.created_groups.values())
        if not uids and not gids:return
        for path in Path('/proc').iterdir():
            self.budget(1)
            if not path.name.isdigit():continue
            try:raw=(path/'status').read_text()
            except FileNotFoundError:continue
            fields={l.split(':',1)[0]:l.split(':',1)[1].split() for l in raw.splitlines() if ':' in l}
            if uids.intersection(map(int,fields['Uid'])) or gids.intersection(map(int,fields['Gid']+fields.get('Groups',[]))):
                raise PermissionError('identity/group still used; never stop unknown process')

    def cleanup(self):
        self.cleanup_deadline=time.monotonic()+120
        self.value['phase']='CLEANUP';ok=True
        # Original proof remains alive in the setup helper until the bounded DROP.
        for p in (self.business,getattr(self,'client',None)):
            if p is None:continue
            try:
                self.diag.checkpoint('C_CLOSE');self._close_owned(p)
            except CleanupTimeout:raise
            except BaseException:
                self.diag.capture();ok=False
                try:
                    self.diag.checkpoint('C_FALLBACK_STOP');self._stop_owned(p,{0,-signal.SIGTERM})
                except CleanupTimeout:raise
                except BaseException:self.diag.capture()
        if self.writer_process is not None:
            try:
                self.diag.checkpoint('C_WRITER_STOP')
                p=self.writer_process;self.linux_host.stop(p)
                if p.returncode not in (0,-signal.SIGTERM):raise RuntimeError('owned writer exit required')
            except CleanupTimeout:raise
            except BaseException:self.diag.capture();ok=False
        dropped=self.setup_process is None
        if self.setup_process is not None:
            try:
                self.diag.checkpoint('C_DROP')
                dropped=self.call(self.setup_process,dict(operation='DROP'))==dict(dropped=True)
                if not dropped:self.diag.capture()
            except CleanupTimeout:raise
            except BaseException:self.diag.capture();dropped=False
            try:
                self.diag.checkpoint('C_SETUP_CLOSE');self._close_owned(self.setup_process)
            except CleanupTimeout:raise
            except BaseException:
                self.diag.capture();ok=False
                try:
                    self.diag.checkpoint('C_FALLBACK_STOP');self._stop_owned(self.setup_process,{0,-signal.SIGTERM})
                except CleanupTimeout:raise
                except BaseException:self.diag.capture()
        self.value['cases']['DATABASE_REMOVED']='PASS' if dropped else 'FAIL'
        if self.pg_process is not None:
            try:
                self.diag.checkpoint('C_PG_STOP');self._stop_owned(self.pg_process,{0})
            except CleanupTimeout:raise
            except BaseException:self.diag.capture();ok=False
        self.diag.checkpoint('C_CHILDREN')
        for p in self.processes:
            if p.poll() is None:self.diag.capture();ok=False
        self.value['cases']['OWNED_STOP']='PASS' if ok else 'FAIL'
        # On failure keep both protected files and their exact live identity owners.
        # Never orphan a writer-owned secret by deleting/recycling its UID first.
        identity_ok=ok and dropped and self.value['error']=='NONE'
        try:
            self.diag.checkpoint('C_IDENTITY_CHECK')
            if not identity_ok:raise RuntimeError('cleanup prerequisites failed')
            if self.creation_attempts!=len(self.created_groups)+len(self.created_users):raise RuntimeError('unconfirmed identity creation')
            self._no_unknown_identity_users()
            s=self.root.lstat()
            if not stat.S_ISDIR(s.st_mode) or s.st_uid!=0 or (s.st_dev,s.st_ino)!=self.root_instance:
                raise PermissionError('new owned root instance required')
            # Retain no non-root-owned credential if later file removal fails.
            self.diag.checkpoint('C_SECRET_RECLAIM')
            for path,uid in ((self.root/'writer/bootstrap.json',self.worker.pw_uid),
                    (self.root/'pg/init-password',self.pg.pw_uid)):
                fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
                try:
                    s=os.fstat(fd)
                    if not stat.S_ISREG(s.st_mode) or s.st_uid!=uid or s.st_nlink!=1 or stat.S_IMODE(s.st_mode)!=0o600:
                        raise PermissionError('owned private credential instance required')
                    os.fchown(fd,0,0);os.fchmod(fd,0o600)
                finally:os.close(fd)
            self.diag.checkpoint('C_USER_DELETE')
            for name,(uid,gid) in self.created_users.items():
                p=pwd.getpwnam(name)
                if (p.pw_uid,p.pw_gid)!=(uid,gid):raise PermissionError('created identity instance changed')
                self.tool(['/usr/sbin/userdel',name])
            self.diag.checkpoint('C_GROUP_DELETE')
            for name,gid in self.created_groups.items():
                try:g=grp.getgrnam(name)
                except KeyError:continue # Own userdel may remove its empty private group.
                if g.gr_gid!=gid:raise PermissionError('created group instance changed')
                self.tool(['/usr/sbin/groupdel',name])
        except CleanupTimeout:raise
        except BaseException:self.diag.capture();identity_ok=False
        self.value['cases']['IDENTITIES_REMOVED']='PASS' if identity_ok else 'FAIL'
        removed=False
        if identity_ok and self.value['error']=='NONE':
            try:
                self.diag.checkpoint('C_FILES_REMOVE')
                s=self.root.lstat()
                if not stat.S_ISDIR(s.st_mode) or s.st_uid!=0 or (s.st_dev,s.st_ino)!=self.root_instance:raise PermissionError('new owned root instance required')
                shutil.rmtree(self.root);removed=True
            except CleanupTimeout:raise
            except BaseException:self.diag.capture()
        self.value['cases']['FILES_REMOVED']='PASS' if removed else 'FAIL'
        self.value['cleanup']=ok and dropped and identity_ok and removed
        return self.value['cleanup']

    def run(self):
        self.diag.checkpoint('C_CONTEXT')
        if self.issuer is not _BOOT_ISSUER or os.geteuid()!=0 or not context_valid(self.c):
            self.value['cases']['GATE']='FAIL';self.value['error']='REFUSED';self.diag.capture();return public_summary(self.value)
        try:
            self.diag.checkpoint('C_PARENT')
            parent=host._process(os.getppid())
            if (parent['pid'],parent['uid'],parent['started'])!=(self.c['bootstrap_pid'],0,self.c['bootstrap_started']):
                self.value['cases']['GATE']='FAIL';self.value['error']='REFUSED';self.diag.capture();return public_summary(self.value)
            self.diag.checkpoint('C_ROOT')
            s=self.root.lstat()
            if not stat.S_ISDIR(s.st_mode) or s.st_uid!=0 or stat.S_IMODE(s.st_mode)!=0o711:raise PermissionError('new root context required')
            self.root_instance=(s.st_dev,s.st_ino);self.value['cases']['GATE']='PASS'
        except BaseException:
            self.diag.capture();self.value['cases']['GATE']='FAIL';self.value['error']='FAILURE'
            self.value['failure_logs']='UNAVAILABLE';return public_summary(self.value)
        def deadline(*a):
            if self.value['phase']=='CLEANUP':raise CleanupTimeout('bounded cleanup deadline')
            raise TimeoutError('one trial deadline')
        signal.signal(signal.SIGTERM,deadline);signal.signal(signal.SIGALRM,deadline);signal.setitimer(signal.ITIMER_REAL,750)
        try:
            self.current='REAL_IDENTITIES';self.diag.checkpoint('C_IDENTITIES');self.identities()
            self.current='FRESH_CLUSTER';self.diag.checkpoint('C_PG');self.pg_start()
            self.current='PROTECTED_RUNTIME';self.diag.checkpoint('C_HOST');self.host_start()
            self.current='REQUEST_APPROVE';self.diag.checkpoint('C_ACCEPTANCE');self.acceptance()
        except BaseException:
            self.value['error']='FAILURE';self.value['cases'][self.current]='FAIL'
            self.diag.capture(case=self.current);raw=traceback.format_exc()
            try:
                self.diag.checkpoint('C_PRIVATE_LOG',case=self.current)
                (self.private/'failure.log').write_text(raw);self.value['failure_logs']='SAVED'
            except BaseException:
                self.diag.capture();self.value['failure_logs']='UNAVAILABLE'
        finally:
            signal.signal(signal.SIGTERM,signal.SIG_IGN)
            signal.setitimer(signal.ITIMER_REAL,120)
            try:
                self.diag.checkpoint('C_CLEANUP');self.cleanup()
            except BaseException:
                self.value['cleanup']=False;self.value['error']='FAILURE'
                self.value['failure_logs']='SAVED'
                raw=traceback.format_exc()
                failed=self.diag.capture();self.value['cases'][failed['case']]='FAIL'
                try:
                    self.diag.checkpoint('C_PRIVATE_LOG',case=failed['case'])
                    (self.private/'cleanup-failure.log').write_text(raw)
                except BaseException:
                    self.diag.capture();self.value['failure_logs']='UNAVAILABLE'
                for k in ('OWNED_STOP','DATABASE_REMOVED','FILES_REMOVED','IDENTITIES_REMOVED'):
                    if self.value['cases'][k]=='NOT_RUN':self.value['cases'][k]='UNKNOWN'
            finally:signal.setitimer(signal.ITIMER_REAL,0)
        if not self.value['cleanup'] and self.value['error']=='NONE':self.value['error']='FAILURE'
        if self.value['cleanup'] and self.value['error']=='NONE':self.value['phase']='COMPLETE'
        return public_summary(self.value)


def main():
    if len(sys.argv)!=2 or not sys.argv[1].isdigit():raise PermissionError('sealed root bootstrap context required')
    c=sealed_input(int(sys.argv[1]))
    result=Controller(c,_BOOT_ISSUER).run()
    print(json.dumps(result,sort_keys=True),flush=True)
    return 0 if result['cleanup'] and all(v=='PASS' for v in result['cases'].values()) else 1


register_source('CONTROLLER',[v.__code__ for v in Controller.__dict__.values() if isinstance(v,types.FunctionType)])

if __name__=='__main__':raise SystemExit(main())
