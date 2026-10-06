"""Native Windows only CLI; shared policies exercised with Linux mock processes.
Never installs a database, discovers credentials, enables LIVE or removes data.
"""
import argparse
import errno
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parent))
from lifecycle_diagnostics import staged,stage,failure,command as diagnostic_command,start_status_command

REPO = Path(__file__).resolve().parents[2]
RUNTIME = REPO / '.runtime'
CONFIG = RUNTIME / 'windows-config.json'
STATE = RUNTIME / 'windows-processes.json'
sys.path.insert(0,str(REPO/'src'))
from parkweave.process_env import minimal_environment
from parkweave.synthetic_session_file import create_synthetic_config_file

ACTIONS = {'doctor','setup','start','status','stop','test'}


class BoundaryError(Exception):
    def __init__(self,message,code='BOUNDARY_REFUSED'):
        super().__init__(message)
        self.parkweave_lifecycle_reason=code


def require_windows(platform=None):
    if (platform or os.name) != 'nt':raise BoundaryError('NOT_RUN: native Windows required','NATIVE_PLATFORM_REQUIRED')


def config_template(repo,python):
    return {'project':'ParkWeave','schema':1,'host':'127.0.0.1','port':8765,
            'database':'parkweave','python':str(Path(python).resolve()),
            'private_root':str(Path(repo).resolve()/'.runtime'),'model':'DISABLED','data':'SYNTHETIC'}


@staged('configuration')
def validate_config(config,repo):
    expected={'project','schema','host','port','database','python','private_root','model','data'}
    if set(config)!=expected or config['project']!='ParkWeave' or config['schema']!=1:
        raise BoundaryError('unrecognized configuration; refuse to overwrite','CONFIG_INVALID')
    if config['host']!='127.0.0.1' or config['database']!='parkweave' or config['model']!='DISABLED' or config['data']!='SYNTHETIC':
        raise BoundaryError('configuration exceeds this synthetic local scope','CONFIG_SCOPE_REFUSED')
    if type(config['port']) is not int or not 8765<=config['port']<=8999:raise BoundaryError('invalid local port','PORT_INVALID')
    managed=Path(repo).resolve()/'.venv-windows'/'Scripts'/'python.exe'
    if Path(config['python']).resolve()!=managed:raise BoundaryError('only managed project Python is allowed','PYTHON_BINDING_REFUSED')
    if Path(config['private_root']).resolve()!=Path(repo).resolve()/'.runtime':raise BoundaryError('private root mismatch','PRIVATE_ROOT_MISMATCH')
    return config


def write_exclusive(path,value):
    # os.open with EXCL protects existing configuration even in a creation race.
    stream=create_synthetic_config_file(path) if os.name=='nt' and Path(path)==CONFIG else Path(path).open('x',encoding='utf-8')
    with stream as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')


def acl_check_command():
    # Read only: resolve owner/rules directly as SIDs, never parse display names.
    # Errors belong to the existing rejection contract, not a successful check.
    return """$ErrorActionPreference='Stop'
$script:AclObject=$null
function Refuse-Acl([int]$Code) {
    if($script:AclObject -in @('ROOT','SESSIONS','CONFIG')) { [Console]::Out.WriteLine($script:AclObject) }
    exit $Code
}
try {
    $p=$env:PARKWEAVE_ACL_ROOT
    $sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User
    if ($null -eq $sid -or [string]::IsNullOrWhiteSpace($sid.Value)) { throw 'SID unavailable' }
    $paths=@($p)
    foreach($name in @('files','synthetic-sessions.json','windows-config.json','windows-processes.json','windows-services.log')) {
        $script:AclObject=if($name -eq 'synthetic-sessions.json'){'SESSIONS'}elseif($name -eq 'windows-config.json'){'CONFIG'}else{$null}
        $q=Join-Path $p $name
        if(Test-Path -LiteralPath $q){$paths+=$q}
    }
    foreach($q in $paths){
        $script:AclObject=if($q -eq $p){'ROOT'}elseif($q -eq (Join-Path $p 'synthetic-sessions.json')){'SESSIONS'}elseif($q -eq (Join-Path $p 'windows-config.json')){'CONFIG'}else{$null}
        $acl=Get-Acl -LiteralPath $q -ErrorAction Stop
        $owner=$acl.GetOwner([System.Security.Principal.SecurityIdentifier])
        if ($null -eq $owner -or [string]::IsNullOrWhiteSpace($owner.Value)) { throw 'Owner SID unavailable' }
        if($q -eq $p -and -not $acl.AreAccessRulesProtected){Refuse-Acl 4}
        if($owner.Value -ne $sid.Value){Refuse-Acl 2}
        $rules=$acl.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier])
        if ($null -eq $rules) { throw 'Rules unavailable' }
        foreach($rule in $rules){
            if($rule.AccessControlType -eq 'Allow'){
                $id=$rule.IdentityReference.Value
                if ([string]::IsNullOrWhiteSpace($id)) { throw 'Rule SID unavailable' }
                if($id -notin @($sid.Value,'S-1-5-18','S-1-5-32-544')){Refuse-Acl 3}
            }
        }
    }
} catch { Refuse-Acl 5 }
exit 0
"""


@staged('private_acl')
def native_acl_check(root):
    require_windows()
    if root.is_symlink() or getattr(root,'is_junction',lambda:False)():
        error=BoundaryError('private root reparse point refused','REPARSE_REFUSED')
        error.parkweave_acl_object='ROOT'
        raise error
    code=acl_check_command()
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',code],
                          env=minimal_environment(os.environ,PARKWEAVE_ACL_ROOT=str(root)),capture_output=True)
    if result.returncode:
        reason={2:'ACL_OWNER_MISMATCH',3:'ACL_ALLOW_REFUSED',4:'ACL_INHERITANCE_REFUSED'}.get(result.returncode,'ACL_INSPECTION_FAILED')
        error=BoundaryError('existing private ACL unsafe/unreadable; ask installer to adjust explicitly; nothing changed',reason)
        value=getattr(result,'stdout',None)
        if isinstance(value,bytes):
            try:value=value.decode('ascii') if len(value)<=32 else None
            except UnicodeError:value=None
        if isinstance(value,str) and len(value)<=32:
            for name in ('ROOT','SESSIONS','CONFIG'):
                if value in (name,name+'\n',name+'\r\n'):error.parkweave_acl_object=name
        raise error


@staged('private_acl')
def protect_private_root(root):
    require_windows()
    if root.is_symlink() or getattr(root,'is_junction',lambda:False)():raise BoundaryError('private root reparse point refused','REPARSE_REFUSED')
    if root.exists():native_acl_check(root);return
    root.mkdir()  # Exclusive new directory only; never rewrite user existing ACL.
    code="$p=$env:PARKWEAVE_ACL_ROOT; $sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User; "
    code+="$acl=New-Object System.Security.AccessControl.DirectorySecurity; $acl.SetOwner($sid); $acl.SetAccessRuleProtection($true,$false); "
    code+="$rule=New-Object System.Security.AccessControl.FileSystemAccessRule($sid,'FullControl','ContainerInherit,ObjectInherit','None','Allow'); "
    code+="$acl.AddAccessRule($rule); Set-Acl -LiteralPath $p -AclObject $acl"
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',code],
                          env=minimal_environment(os.environ,PARKWEAVE_ACL_ROOT=str(root)),capture_output=True)
    if result.returncode:raise BoundaryError('new private directory ACL setup failed; no sessions/config written')
    native_acl_check(root)


@staged('python_guard')
def check_python(python):
    result=subprocess.run([str(python),'-c',"import sys,struct,json;print(json.dumps([sys.platform,*sys.version_info[:2],struct.calcsize('P')*8]))"],capture_output=True,text=True,env=minimal_environment(os.environ))
    if result.returncode or json.loads(result.stdout)!=['win32',3,12,64]:
        raise BoundaryError('native Python3.12 x64 required; no automatic download/downgrade','PYTHON_VERSION_REFUSED')


@staged('dsn_parse')
def check_dsn_scope(dsn,app=False):
    from psycopg.conninfo import conninfo_to_dict
    from parkweave.store import Store
    info=conninfo_to_dict(dsn)
    if info.get('dbname')!='parkweave' or info.get('host') not in ('127.0.0.1','localhost') or info.get('service') or info.get('hostaddr') not in (None,'127.0.0.1','::1'):
        raise BoundaryError('explicit localhost parkweave database DSN required','DSN_SCOPE_REFUSED')
    with stage('database_connect'):
        connection=Store(dsn).connect()
    with connection as c:
        with stage('database_role'):
            row=c.execute('SELECT current_database() db,current_user usr,r.rolsuper,r.rolcreatedb,r.rolcreaterole '
                          'FROM pg_roles r WHERE r.rolname=current_user').fetchone()
            if row['db']!='parkweave' or (app and (row['usr']!='parkweave_app' or row['rolsuper'] or row['rolcreatedb'] or row['rolcreaterole'])):
                raise BoundaryError('application must be a dedicated unprivileged parkweave_app role','APP_ROLE_REFUSED')
        with stage('database_version'):version=c.execute('SELECT version() version').fetchone()['version']
    return version


@staged('environment_binding')
def needed_environment(name):
    value=os.environ.get(name)
    if not value:raise BoundaryError(name+' required from authorized session injection; not stored in config','ENVIRONMENT_REQUIRED')
    return value


def app_environment(dsn,environment):
    env=minimal_environment(environment,PARKWEAVE_DSN=dsn,PARKWEAVE_MODE='LOCAL')
    # Do not pass owner or model secrets to either child; LIVE is disabled.
    for name in ('PARKWEAVE_OWNER_DSN','PARKWEAVE_TEST_OWNER_DSN','PARKWEAVE_INTERN_API_TOKEN','INTERN_API_TOKEN'):
        env.pop(name,None)
    env.pop('PARKWEAVE_FILE_ROOT',None)  # Native file backend is unverified and disabled.
    return env


def trusted_command(command,repo):
    python=str(Path(repo).resolve()/'.venv-windows'/'Scripts'/'python.exe')
    if command==[python,'-m','parkweave.worker']:return True
    prefix=[python,'-m','uvicorn','parkweave.api:configured_app','--factory','--host','127.0.0.1','--port']
    return (isinstance(command,list) and command[:8]==prefix and len(command)==9 and
            isinstance(command[8],str) and command[8].isdigit() and 8765<=int(command[8])<=8999)


def identify_process_reason(proc,record,repo):
    # Preserve ordered predicates and tolerances; return only fixed refusal codes.
    try:
        if not trusted_command(record['command'],repo):return 'TRUSTED_COMMAND_REFUSED'
        if not abs(proc.create_time()-record['created'])<.01:return 'CTIME_MISMATCH'
        if proc.cwd()!=str(Path(repo).resolve()):return 'CWD_MISMATCH'
        if proc.cmdline()!=record['command']:return 'COMMAND_MISMATCH'
    except Exception:return 'READ_FAILED'
    return None


def identify_process(proc,record,repo):
    return identify_process_reason(proc,record,repo) is None


def native_binding_enabled():return os.name=='nt'


def bind_execution(root,record,pid,repo):
    from server_identity import bind_server,redirector_authority
    return bind_server(root,record,pid,repo,identify=identify_process,identify_reason=identify_process_reason,
                       command_authority=redirector_authority if native_binding_enabled() else None)


def saved_child_matches(root,record,repo,refusals=None):
    child=record.get('server')
    if child is None:
        if not native_binding_enabled():return True
        result=bind_execution(root,record,record.get('pid'),repo)
        matched=result['relation']=='ROOT'
    else:
        result=bind_execution(root,record,child.get('pid'),repo)
        matched=result['relation']=='DIRECT_CHILD' and result['server']==child
    if not matched and isinstance(refusals,dict):
        from server_identity import refusal,validate_identity_refusal
        try:value=validate_identity_refusal(result.get('identity_refusal'))
        except ValueError:value=refusal('CHILD_POLICY','RECORD_MISMATCH')
        refusals.clear();refusals.update(value)
    return matched


def save_execution_bindings(records,original):
    # Only this Start's own metadata; CONFIG/SESSION and existing user files stay untouched.
    if STATE.read_bytes()!=original:raise BoundaryError('process record changed; binding refused')
    temporary=STATE.with_name('.process-binding-'+uuid.uuid4().hex+'.json')
    try:
        write_exclusive(temporary,{'project':'ParkWeave','schema':1,'processes':records})
        if STATE.read_bytes()!=original:raise BoundaryError('process record changed; binding refused')
        os.replace(temporary,STATE)
    finally:temporary.unlink(missing_ok=True)


@staged('process_stop')
def stop_record(record,repo,process_factory,refusals=None):
    import psutil
    from server_identity import refusal,validate_identity_refusal
    local_refusal=None
    def refused(stage,reason='CHECK_FAILED',value=None):
        nonlocal local_refusal
        try:local_refusal=validate_identity_refusal(value)
        except ValueError:local_refusal=refusal(stage,reason)
        if isinstance(refusals,dict):refusals.clear();refusals.update(local_refusal)
        return 'FOREIGN_REFUSED'
    try:proc=process_factory(record['pid'])
    except (ProcessLookupError,psutil.NoSuchProcess):
        if record.get('server'):
            try:process_factory(record['server']['pid'])
            except (ProcessLookupError,psutil.NoSuchProcess):return 'ABSENT'
            except Exception:pass
            return refused('ROOT_POLICY','ORPHAN_REFUSED')  # No orphan discovery or termination.
        return 'ABSENT'
    except Exception:
        error=BoundaryError('cannot inspect recorded PID; process/record preserved')
        error.parkweave_identity_refusal=refusal('ROOT_SNAPSHOT','READ_FAILED')
        raise error from None
    if not identify_process(proc,record,repo):return refused('ROOT_POLICY','POLICY_REFUSED')
    native_process=native_binding_enabled() and isinstance(proc,psutil.Process)
    if native_process or record.get('server'):
        from contextlib import ExitStack
        from server_identity import PinnedProcess,IdentityRefused
        pin_stage='ROOT_PIN'
        try:
            with ExitStack() as stack:
                root_pin=stack.enter_context(PinnedProcess(record['pid'],record['created']))
                if not identify_process(proc,record,repo):return refused('ROOT_POLICY','POLICY_REFUSED')
                # Recover only a current unique direct child of the known launcher,
                # for failure before a health response could persist its binding.
                if native_process and not record.get('server'):
                    direct=proc.children(recursive=False)
                    if len(direct)>1:return refused('CHILD_POLICY','AMBIGUOUS')
                    if direct:
                        bound=bind_execution(proc,record,direct[0].pid,repo)
                        if bound['relation']!='DIRECT_CHILD':return refused('CHILD_POLICY','POLICY_REFUSED',bound.get('identity_refusal'))
                        record={**record,'server':bound['server']}
                child_record=record.get('server');child=None
                if child_record:
                    try:child=process_factory(child_record['pid'])
                    except (ProcessLookupError,psutil.NoSuchProcess):pass
                    except Exception:return refused('CHILD_SNAPSHOT','READ_FAILED')
                if child is not None:
                    pin_stage='CHILD_PIN'
                    child_pin=stack.enter_context(PinnedProcess(child_record['pid'],child_record['created']))
                    chain_refusal={}
                    if not saved_child_matches(proc,record,repo,chain_refusal):return refused('CHILD_POLICY','POLICY_REFUSED',chain_refusal)
                    pin_stage='ROOT_PIN';root_pin.verify()
                    pin_stage='CHILD_PIN';child_pin.verify()
                    child.terminate()
                    child.wait(timeout=10)
                # Its original held handle can confirm autonomous launcher exit.
                pin_stage='ROOT_PIN';root_pin.verify(require_live=False)
                if not root_pin.alive:return 'STOPPED'
                if not identify_process(proc,record,repo):return refused('ROOT_POLICY','POLICY_REFUSED')
                root_pin.verify()
                proc.terminate();proc.wait(timeout=10)
                return 'STOPPED'
        except IdentityRefused as error:
            if local_refusal is not None:return refused('UNKNOWN',value=local_refusal)
            return refused('CLOSE' if error.reason=='CLOSE_FAILED' else pin_stage,error.reason)
        except Exception:
            error=BoundaryError('verified execution did not stop; record preserved')
            error.parkweave_identity_refusal=refusal('UNKNOWN','CHECK_FAILED')
            raise error from None
    proc.terminate()
    try:proc.wait(timeout=10)
    except Exception:raise BoundaryError('managed process did not stop; no force kill or unrelated PID termination')
    return 'STOPPED'


@staged('configuration')
def load_config():
    if not CONFIG.exists():raise BoundaryError('setup not completed; run Setup.ps1 first','CONFIG_MISSING')
    return validate_config(json.loads(CONFIG.read_text(encoding='utf-8')),REPO)


@staged('port_check')
def port_available(port,retry_seconds=0,*,clock=time.monotonic,pause=time.sleep):
    if type(retry_seconds) not in (int,float) or not 0<=retry_seconds<=1:raise ValueError('bounded port retry required')
    deadline=clock()+retry_seconds;first=True
    while True:
        if not first and clock()>=deadline:raise BoundaryError('local port occupied; nothing terminated','PORT_OCCUPIED')
        first=False
        with socket.socket() as sock:
            try:
                if os.name=='nt':sock.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
            except OSError:raise BoundaryError('exclusive port check refused','PORT_CHECK_REFUSED') from None
            try:
                sock.bind(('127.0.0.1',port));return
            except OSError as error:
                winerror=getattr(error,'winerror',None)
                busy=winerror==10048 if winerror is not None else error.errno in (errno.EADDRINUSE,10048)
                if not busy:raise BoundaryError('exclusive port check refused','PORT_CHECK_REFUSED') from None
        if not retry_seconds or clock()>=deadline:raise BoundaryError('local port occupied; nothing terminated','PORT_OCCUPIED')
        # A live listener, permission/read error or inconclusive transport never
        # becomes available. A refused connection permits only another exclusive
        # bind, without SO_REUSEADDR, process discovery or termination.
        with socket.socket() as probe:
            try:
                probe.settimeout(min(.1,max(0,deadline-clock())))
                result=probe.connect_ex(('127.0.0.1',port))
            except OSError:raise BoundaryError('local listener check refused','PORT_CHECK_REFUSED') from None
        if result==0:raise BoundaryError('local port occupied; nothing terminated','PORT_OCCUPIED')
        if result not in (errno.ECONNREFUSED,10061):raise BoundaryError('local listener check refused','PORT_CHECK_REFUSED')
        remaining=deadline-clock()
        if remaining<=0:raise BoundaryError('local port occupied; nothing terminated','PORT_OCCUPIED')
        pause(min(.05,remaining))


def setup():
    if CONFIG.exists():raise BoundaryError('existing configuration protected; use Doctor/Start, not overwrite setup')
    check_python(sys.executable)
    managed=REPO/'.venv-windows'
    python=managed/'Scripts'/'python.exe'
    if managed.exists():
        if not python.exists():raise BoundaryError('existing incomplete managed environment protected; review manually')
        check_python(python)  # Preserve existing environment; do not reinstall it silently.
    else:
        subprocess.run([sys.executable,'-m','venv',str(managed)],check=True,env=minimal_environment(os.environ))
        subprocess.run([str(python),'-m','pip','install','-r',str(REPO/'requirements-windows-candidate.txt')],check=True,env=minimal_environment(os.environ))
        subprocess.run([str(python),'-m','pip','install','--no-deps','-e',str(REPO)],check=True,env=minimal_environment(os.environ))
    if Path(sys.executable).resolve()!=python.resolve():
        # The managed interpreter performs DB/setup work after dependency install.
        subprocess.run([str(python),str(Path(__file__).resolve()),'setup'],check=True,env=minimal_environment(os.environ,PARKWEAVE_OWNER_DSN=needed_environment('PARKWEAVE_OWNER_DSN'),PARKWEAVE_DSN=needed_environment('PARKWEAVE_DSN')));return
    check_dsn_scope(needed_environment('PARKWEAVE_OWNER_DSN'))
    check_dsn_scope(needed_environment('PARKWEAVE_DSN'),app=True)
    from parkweave.store import Store
    owner=Store(needed_environment('PARKWEAVE_OWNER_DSN'));owner.migrate()
    with owner.connect() as c:c.execute((REPO/'src/parkweave/roles.sql').read_text(encoding='utf-8'))
    protect_private_root(RUNTIME)
    sessions=RUNTIME/'synthetic-sessions.json'
    if not sessions.exists():
        env=minimal_environment(os.environ,PARKWEAVE_DSN=needed_environment('PARKWEAVE_OWNER_DSN'))
        subprocess.run([str(python),'-m','parkweave.cli','seed-synthetic'],env=env,check=True,cwd=REPO)
    # Existing sessions and grants remain unchanged; setup never reactivates them.
    write_exclusive(CONFIG,config_template(REPO,python))
    native_acl_check(RUNTIME)  # Read-only final postcondition includes new files.
    print('Setup candidate complete. Config/data protected; LIVE disabled. Run Doctor.ps1 next.')


@staged('doctor_output')
def doctor():
    check_python(sys.executable)
    info={'project':'ParkWeave','platform':sys.platform,'python':sys.version.split()[0],'native_windows':'UNVERIFIED_RUN',
          'model':'DISABLED','file_backend':'NOT_RUN: native backend disabled','cwd':str(REPO)}
    if RUNTIME.exists():native_acl_check(RUNTIME);info['private_acl']='CHECKED_READ_ONLY: native run evidence only'
    if CONFIG.exists():
        config=load_config();check_python(config['python']);info['port']=config['port']
        info['postgresql']=check_dsn_scope(needed_environment('PARKWEAVE_DSN'),app=True)
        with stage('database_schema'):
            with __import__('parkweave.store',fromlist=['Store']).Store(needed_environment('PARKWEAVE_DSN')).connect() as c:
                info['schema']=c.execute('SELECT max(version) v FROM schema_version').fetchone()['v']
        with stage('dependency_freeze'):
            result=subprocess.run([config['python'],'-m','pip','freeze'],capture_output=True,text=True,check=True,env=minimal_environment(os.environ))
        info['dependencies']=result.stdout.splitlines()
    print(json.dumps(info,ensure_ascii=False,indent=2))  # No DSN/session/environment dump.


@staged('process_record')
def start():
    import psutil
    config=load_config();check_python(config['python'])
    dsn=needed_environment('PARKWEAVE_DSN');check_dsn_scope(dsn,app=True)
    if STATE.exists():raise BoundaryError('process record exists; run Status/Stop before restarting','PROCESS_RECORD_EXISTS')
    port_available(config['port'],1);protect_private_root(RUNTIME)
    commands=[[config['python'],'-m','uvicorn','parkweave.api:configured_app','--factory','--host','127.0.0.1','--port',str(config['port'])],
              [config['python'],'-m','parkweave.worker']]
    records=[];children=[];state_written=False
    observation={**{k:0 for k in ('created','attempts','responses','refused','timeouts','http_errors','other_errors','mismatches','alive_refused','cleanup_attempted','stopped','absent','foreign')},**{k:'NOT_CREATED' for k in ('api','worker','after_api','after_worker')},'last':'NOT_PROBED'}
    with stage('service_log'):log=(RUNTIME/'windows-services.log').open('a',encoding='utf-8')
    try:
        for command in commands:
            with stage('process_spawn'):
                child=psutil.Popen(command,cwd=REPO,env=app_environment(dsn,os.environ),stdout=log,stderr=log)
            children.append(child);observation['created']+=1;observation[('api','worker')[len(children)-1]]='UNKNOWN';observation[('after_api','after_worker')[len(children)-1]]='UNKNOWN'
            with stage('process_identity'):records.append({'pid':child.pid,'created':child.create_time(),'command':command})
        with stage('process_record'):write_exclusive(STATE,{'project':'ParkWeave','schema':1,'processes':records})
        state_written=True
        original_state=STATE.read_bytes()
        import urllib.request
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for _ in range(50):
            states=[c.poll() for c in children]
            for key,code in zip(('api','worker'),states):observation[key]='RUNNING' if code is None else 'EXIT_ZERO' if code==0 else 'EXIT_NONZERO'
            if any(code is not None for code in states):
                observation['last']='CHILD_EXITED'
                with stage('health_readiness'):raise BoundaryError('managed service exited; inspect private log','SERVICE_EXITED')
            observation['attempts']+=1
            request_complete=False
            try:
                with stage('health_readiness'):
                    with opener.open(f"http://127.0.0.1:{config['port']}/health",timeout=1) as r:
                        health=json.load(r)
                request_complete=True
                with stage('health_readiness'):
                    pid=health.get('process_id');valid_pid=type(pid) is int and 0<pid<=0xffffffff
                    binding=bind_execution(children[0],records[0],pid,REPO) if native_binding_enabled() else {'relation':'ROOT' if valid_pid and pid==children[0].pid else 'REFUSED','server':None}
                    if records[0].get('server') and binding['relation'] in ('ROOT','DIRECT_CHILD') and binding['server']!=records[0]['server']:binding={'relation':'REFUSED','server':None,'identity_refusal':{'stage':'CHILD_POLICY','reason':'RECORD_MISMATCH'}}
                    matches={'mode_matches':health.get('execution_mode')=='LOCAL','model_matches':health.get('model')=='MODEL_MOCK','process_matches':binding['relation'] in ('ROOT','DIRECT_CHILD')}
                    observation['responses']+=1;observation.update(matches)
                    if native_binding_enabled():
                        observation.update(server_pid_valid=valid_pid,server_relation=binding['relation'])
                        observation.pop('identity_refusal',None)
                        if binding['relation']=='REFUSED':
                            from server_identity import refusal,validate_identity_refusal
                            try:observation['identity_refusal']=validate_identity_refusal(binding.get('identity_refusal'))
                            except ValueError:observation['identity_refusal']=refusal('UNKNOWN')
                    if native_binding_enabled() and binding['server'] is not None and 'server' not in records[0]:
                        records[0]['server']=binding['server']
                        with stage('process_record'):save_execution_bindings(records,original_state)
                        original_state=STATE.read_bytes()
                    if all(matches.values()):
                        if native_binding_enabled():
                            worker_children=children[1].children(recursive=False)
                            if len(worker_children)>1:
                                error=BoundaryError('worker launcher relation ambiguous; record preserved')
                                error.parkweave_identity_refusal={'stage':'CHILD_POLICY','reason':'AMBIGUOUS'}
                                raise error
                            worker_pid=worker_children[0].pid if worker_children else children[1].pid
                            worker_binding=bind_execution(children[1],records[1],worker_pid,REPO)
                            if worker_binding['relation'] not in ('ROOT','DIRECT_CHILD'):
                                error=BoundaryError('worker execution identity refused; record preserved')
                                error.parkweave_identity_refusal=worker_binding.get('identity_refusal',{'stage':'UNKNOWN','reason':'CHECK_FAILED'})
                                raise error
                            for record,resolved in zip(records,(binding,worker_binding)):
                                if resolved['server'] is not None:record['server']=resolved['server']
                            if any('server' in record for record in records):
                                with stage('process_record'):save_execution_bindings(records,original_state)
                        observation['last']='HEALTH_MATCH';break
                    observation['mismatches']+=1;observation['last']='HEALTH_MISMATCH'
            except OSError as error:
                # Metadata/process errors must reach fail-closed cleanup, not
                # masquerade as a transport error and retry an unsaved binding.
                if request_complete:raise
                import urllib.error
                cause=getattr(error,'reason',None)
                if isinstance(error,urllib.error.HTTPError):key,last='http_errors','HTTP_NON_SUCCESS'
                elif isinstance(error,TimeoutError) or isinstance(cause,TimeoutError):key,last='timeouts','TRANSPORT_TIMEOUT'
                elif isinstance(error,ConnectionRefusedError) or isinstance(cause,ConnectionRefusedError):
                    key,last='refused','CONNECTION_REFUSED'
                    if all(code is None for code in states):observation['alive_refused']+=1
                else:key,last='other_errors','TRANSPORT_OTHER'
                observation[key]+=1;observation['last']=last
            time.sleep(.1)
        else:
            with stage('health_readiness'):raise BoundaryError('local health readiness timeout','READINESS_TIMEOUT')
        try:print(start_status_command(observation))
        except Exception:pass  # Telemetry cannot turn successful readiness into failure.
        print(f"Open http://127.0.0.1:{config['port']} ; synthetic local mode only.")
    except Exception as primary:
        # Keep the existing cleanup/exit behavior; retain the original failure's
        # fixed metadata if a cleanup exception replaces it.
        primary.parkweave_start_observation=observation
        def observe_after_cleanup():
            for key,child in zip(('after_api','after_worker'),children):
                try:
                    code=child.poll();observation[key]='RUNNING' if code is None else 'EXIT_ZERO' if code==0 else 'EXIT_NONZERO'
                except Exception:observation[key]='UNKNOWN'
        cleanup_refusal={}
        try:
            results=[]
            for record in records:
                observation['cleanup_attempted']+=1
                result=stop_record(record,REPO,psutil.Process,cleanup_refusal);results.append(result)
                if result in ('STOPPED','ABSENT','FOREIGN_REFUSED'):observation[{'STOPPED':'stopped','ABSENT':'absent','FOREIGN_REFUSED':'foreign'}[result]]+=1
            if any(result not in ('STOPPED','ABSENT') for result in results):
                cleanup_error=BoundaryError('managed process cleanup unconfirmed; process record preserved')
                if cleanup_refusal:cleanup_error.parkweave_identity_refusal=cleanup_refusal
                raise cleanup_error
            if state_written:STATE.unlink(missing_ok=True)
        except Exception as cleanup:
            observe_after_cleanup()
            cleanup.parkweave_lifecycle_primary=failure(primary)
            raise
        observe_after_cleanup()
        raise
    finally:log.close()


def status():
    import psutil
    config=load_config()
    rows=[]
    if STATE.exists():
        state=json.loads(STATE.read_text(encoding='utf-8'))
        if state.get('project')!='ParkWeave':raise BoundaryError('foreign process record refused')
        for record in state['processes']:
            try:proc=psutil.Process(record['pid']);owned=identify_process(proc,record,REPO) and saved_child_matches(proc,record,REPO)
            except psutil.NoSuchProcess:owned=False
            rows.append({'pid':record['pid'],'identity_matches':owned})
    print(json.dumps({'project':'ParkWeave','processes':rows,'port':config['port'],'model':'DISABLED'},indent=2))


def stop():
    import psutil
    if not STATE.exists():print('No managed process record. No process/data changed.');return
    state=json.loads(STATE.read_text(encoding='utf-8'))
    if state.get('project')!='ParkWeave' or state.get('schema')!=1:raise BoundaryError('foreign process record refused')
    refusals={}
    results=[stop_record(record,REPO,psutil.Process,refusals) for record in state['processes']]
    if 'FOREIGN_REFUSED' in results:
        error=BoundaryError('PID identity mismatch; foreign process and record preserved')
        error.parkweave_lifecycle_phase='process_stop'
        if refusals:error.parkweave_identity_refusal=refusals
        raise error
    STATE.unlink()  # Only private PID metadata; never remove DB/files/sessions.
    print('Managed API/worker stopped; database service/data/config/sessions remain.')


def test():
    config=load_config()
    needed_environment('PARKWEAVE_TEST_OWNER_DSN')
    subprocess.run([config['python'],str(REPO/'scripts/run_acceptance.py'),'--report',str(RUNTIME/'windows-engineering-report.json')],check=True,cwd=REPO,env=minimal_environment(os.environ,PARKWEAVE_TEST_OWNER_DSN=needed_environment('PARKWEAVE_TEST_OWNER_DSN')))
    print('Engineering subset only; full AT/EX and native manual gates do not auto-PASS.')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=sorted(ACTIONS));args=parser.parse_args()
    try:
        require_windows()
        globals()[args.action]()
    except Exception as exc:
        if args.action in ('doctor','start','setup','stop'):
            try:print(diagnostic_command(args.action,exc),flush=True)
            except Exception:pass  # Diagnostic emission never changes the exit verdict.
        # No exception/DSN/HTTP payload strings are emitted; they may contain secrets.
        print('ParkWeave '+args.action+' failed: '+(str(exc) if isinstance(exc,BoundaryError) else type(exc).__name__),file=sys.stderr)
        raise SystemExit(1)


if __name__=='__main__':main()
