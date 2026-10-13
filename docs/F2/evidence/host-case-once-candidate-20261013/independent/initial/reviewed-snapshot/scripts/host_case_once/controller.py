"""One root-sealed controller; fixed new resources, original host and Case API."""
from datetime import datetime,timezone
import hashlib,json,os,pwd,grp,re,select,shutil,signal,stat,subprocess,sys,time,traceback
from pathlib import Path
from uuid import uuid4

from psycopg.conninfo import make_conninfo
from parkweave import native_run_access_restricted_host as host,native_run_access_writer as writer
from parkweave.case_cancellation_business_binding import BusinessBinding
from scripts.linux_trial import controller as reference
from scripts.linux_trial.worker import sealed_input
from scripts.host_case_once.bootstrap import APPROVAL_REF,initial,public_summary

_BOOT_ISSUER=object()
USERS=('pwci_api','pwci_writer')
GROUPS=('pwci_ipc','pwci_api','pwci_writer')


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
        self.value=initial(context['source_sha']);self.issuer=issuer
        self.created_users={};self.created_groups={};self.creation_attempts=0
        self.business=None;self.setup_process=None;self.pg_process=None;self.root_instance=None

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
            self.tool(['/usr/sbin/useradd','--system','--no-create-home','--home-dir','/nonexistent',
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
        if not select.select([self.setup_process.stdout],[],[],120)[0]:raise TimeoutError('setup bounded response required')
        raw=self.setup_process.stdout.readline(524289)
        if len(raw)>524288:raise ValueError('bounded setup result required')
        frame=json.loads(raw)
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
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5);raise RuntimeError('forced stop is not cleanup PASS')
        if type(p.returncode) is not int or p.returncode not in allowed:raise RuntimeError('owned exit result required')

    def _close_owned(self,p):
        if p not in self.processes:raise PermissionError('retained child required')
        if p.poll() is None:
            if writer._pid_started(p.pid)!=self.starts[id(p)]:raise PermissionError('owned child instance changed')
            # CLOSE has no reply: the helper drains/exits normally, not an RPC result.
            p.stdin.write(b'{"operation":"CLOSE"}\n');p.stdin.flush()
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._stop_owned(p,{0,-signal.SIGTERM})
                raise RuntimeError('normal helper close required')
        if type(p.returncode) is not int or p.returncode!=0:raise RuntimeError('normal helper exit required')

    def _no_unknown_identity_users(self):
        uids={v[0] for v in self.created_users.values()};gids=set(self.created_groups.values())
        if not uids and not gids:return
        for path in Path('/proc').iterdir():
            if not path.name.isdigit():continue
            try:raw=(path/'status').read_text()
            except FileNotFoundError:continue
            fields={l.split(':',1)[0]:l.split(':',1)[1].split() for l in raw.splitlines() if ':' in l}
            if uids.intersection(map(int,fields['Uid'])) or gids.intersection(map(int,fields['Gid']+fields.get('Groups',[]))):
                raise PermissionError('identity/group still used; never stop unknown process')

    def cleanup(self):
        self.value['phase']='CLEANUP';ok=True
        # Original proof remains alive in the setup helper until the bounded DROP.
        for p in (self.business,getattr(self,'client',None)):
            if p is None:continue
            try:self._close_owned(p)
            except BaseException:
                ok=False
                try:self._stop_owned(p,{0,-signal.SIGTERM})
                except BaseException:pass
        if self.writer_process is not None:
            try:
                p=self.writer_process;self.linux_host.stop(p)
                if p.returncode not in (0,-signal.SIGTERM):raise RuntimeError('owned writer exit required')
            except BaseException:ok=False
        dropped=self.setup_process is None
        if self.setup_process is not None:
            try:dropped=self.call(self.setup_process,dict(operation='DROP'))==dict(dropped=True)
            except BaseException:dropped=False
            try:self._close_owned(self.setup_process)
            except BaseException:
                ok=False
                try:self._stop_owned(self.setup_process,{0,-signal.SIGTERM})
                except BaseException:pass
        self.value['cases']['DATABASE_REMOVED']='PASS' if dropped else 'FAIL'
        if self.pg_process is not None:
            try:self._stop_owned(self.pg_process,{0})
            except BaseException:ok=False
        for p in self.processes:
            if p.poll() is None:ok=False
        self.value['cases']['OWNED_STOP']='PASS' if ok else 'FAIL'
        identity_ok=ok and dropped
        try:
            if not identity_ok:raise RuntimeError('cleanup prerequisites failed')
            if self.creation_attempts!=len(self.created_groups)+len(self.created_users):raise RuntimeError('unconfirmed identity creation')
            self._no_unknown_identity_users()
            for name,(uid,gid) in self.created_users.items():
                p=pwd.getpwnam(name)
                if (p.pw_uid,p.pw_gid)!=(uid,gid):raise PermissionError('created identity instance changed')
                self.tool(['/usr/sbin/userdel',name])
            for name,gid in self.created_groups.items():
                try:g=grp.getgrnam(name)
                except KeyError:continue # Own userdel may remove its empty private group.
                if g.gr_gid!=gid:raise PermissionError('created group instance changed')
                self.tool(['/usr/sbin/groupdel',name])
        except BaseException:identity_ok=False
        self.value['cases']['IDENTITIES_REMOVED']='PASS' if identity_ok else 'FAIL'
        removed=False
        if identity_ok and self.value['error']=='NONE':
            try:
                s=self.root.lstat()
                if not stat.S_ISDIR(s.st_mode) or s.st_uid!=0 or (s.st_dev,s.st_ino)!=self.root_instance:raise PermissionError('new owned root instance required')
                shutil.rmtree(self.root);removed=True
            except BaseException:pass
        self.value['cases']['FILES_REMOVED']='PASS' if removed else 'FAIL'
        self.value['cleanup']=ok and dropped and identity_ok and removed
        return self.value['cleanup']

    def run(self):
        if self.issuer is not _BOOT_ISSUER or os.geteuid()!=0 or not context_valid(self.c):
            self.value['cases']['GATE']='FAIL';self.value['error']='REFUSED';return public_summary(self.value)
        parent=host._process(os.getppid())
        if (parent['pid'],parent['uid'],parent['started'])!=(self.c['bootstrap_pid'],0,self.c['bootstrap_started']):
            self.value['cases']['GATE']='FAIL';self.value['error']='REFUSED';return public_summary(self.value)
        s=self.root.lstat()
        if not stat.S_ISDIR(s.st_mode) or s.st_uid!=0 or stat.S_IMODE(s.st_mode)!=0o711:raise PermissionError('new root context required')
        self.root_instance=(s.st_dev,s.st_ino);self.value['cases']['GATE']='PASS'
        def deadline(*a):raise TimeoutError('one trial deadline')
        signal.signal(signal.SIGTERM,deadline);signal.signal(signal.SIGALRM,deadline);signal.setitimer(signal.ITIMER_REAL,900)
        try:self.identities();self.pg_start();self.host_start();self.acceptance()
        except BaseException:
            self.value['error']='FAILURE';self.value['cases'][self.current]='FAIL'
            raw=traceback.format_exc();self.value['diagnostics'].append(dict(case=self.current,line=0,trace_sha256=hashlib.sha256(raw.encode()).hexdigest()))
            try:(self.private/'failure.log').write_text(raw);self.value['failure_logs']='SAVED'
            except BaseException:self.value['failure_logs']='UNAVAILABLE'
        finally:
            signal.setitimer(signal.ITIMER_REAL,0);self.cleanup()
        if not self.value['cleanup'] and self.value['error']=='NONE':self.value['error']='FAILURE'
        if self.value['cleanup'] and self.value['error']=='NONE':self.value['phase']='COMPLETE'
        return public_summary(self.value)


def main():
    if len(sys.argv)!=2 or not sys.argv[1].isdigit():raise PermissionError('sealed root bootstrap context required')
    c=sealed_input(int(sys.argv[1]))
    result=Controller(c,_BOOT_ISSUER).run()
    print(json.dumps(result,sort_keys=True),flush=True)
    return 0 if result['cleanup'] and all(v=='PASS' for v in result['cases'].values()) else 1


if __name__=='__main__':raise SystemExit(main())
