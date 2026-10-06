"""Native Windows only CLI; shared policies exercised with Linux mock processes.
Never installs a database, discovers credentials, enables LIVE or removes data.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parent))
from lifecycle_diagnostics import staged,stage,failure,command as diagnostic_command

REPO = Path(__file__).resolve().parents[2]
RUNTIME = REPO / '.runtime'
CONFIG = RUNTIME / 'windows-config.json'
STATE = RUNTIME / 'windows-processes.json'
sys.path.insert(0,str(REPO/'src'))
from parkweave.process_env import minimal_environment

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
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')


def acl_check_command():
    # Read only: resolve owner/rules directly as SIDs, never parse display names.
    # Errors belong to the existing rejection contract, not a successful check.
    return """$ErrorActionPreference='Stop'
try {
    $p=$env:PARKWEAVE_ACL_ROOT
    $sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User
    if ($null -eq $sid -or [string]::IsNullOrWhiteSpace($sid.Value)) { throw 'SID unavailable' }
    $paths=@($p)
    foreach($name in @('files','synthetic-sessions.json','windows-config.json','windows-processes.json','windows-services.log')) {
        $q=Join-Path $p $name
        if(Test-Path -LiteralPath $q){$paths+=$q}
    }
    foreach($q in $paths){
        $acl=Get-Acl -LiteralPath $q -ErrorAction Stop
        $owner=$acl.GetOwner([System.Security.Principal.SecurityIdentifier])
        if ($null -eq $owner -or [string]::IsNullOrWhiteSpace($owner.Value)) { throw 'Owner SID unavailable' }
        if($q -eq $p -and -not $acl.AreAccessRulesProtected){exit 4}
        if($owner.Value -ne $sid.Value){exit 2}
        $rules=$acl.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier])
        if ($null -eq $rules) { throw 'Rules unavailable' }
        foreach($rule in $rules){
            if($rule.AccessControlType -eq 'Allow'){
                $id=$rule.IdentityReference.Value
                if ([string]::IsNullOrWhiteSpace($id)) { throw 'Rule SID unavailable' }
                if($id -notin @($sid.Value,'S-1-5-18','S-1-5-32-544')){exit 3}
            }
        }
    }
} catch { exit 5 }
exit 0
"""


@staged('private_acl')
def native_acl_check(root):
    require_windows()
    if root.is_symlink() or getattr(root,'is_junction',lambda:False)():raise BoundaryError('private root reparse point refused','REPARSE_REFUSED')
    code=acl_check_command()
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',code],
                          env=minimal_environment(os.environ,PARKWEAVE_ACL_ROOT=str(root)),capture_output=True)
    if result.returncode:
        reason={2:'ACL_OWNER_MISMATCH',3:'ACL_ALLOW_REFUSED',4:'ACL_INHERITANCE_REFUSED'}.get(result.returncode,'ACL_INSPECTION_FAILED')
        raise BoundaryError('existing private ACL unsafe/unreadable; ask installer to adjust explicitly; nothing changed',reason)


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


def identify_process(proc,record,repo):
    # PID reuse or a foreign command line cannot authorize termination.
    try:
        return (trusted_command(record['command'],repo) and abs(proc.create_time()-record['created'])<.01 and
                proc.cwd()==str(Path(repo).resolve()) and
                proc.cmdline()==record['command'])
    except Exception:return False


@staged('process_stop')
def stop_record(record,repo,process_factory):
    import psutil
    try:proc=process_factory(record['pid'])
    except (ProcessLookupError,psutil.NoSuchProcess):return 'ABSENT'
    except Exception:raise BoundaryError('cannot inspect recorded PID; process/record preserved') from None
    if not identify_process(proc,record,repo):return 'FOREIGN_REFUSED'
    proc.terminate()
    try:proc.wait(timeout=10)
    except Exception:raise BoundaryError('managed process did not stop; no force kill or unrelated PID termination')
    return 'STOPPED'


@staged('configuration')
def load_config():
    if not CONFIG.exists():raise BoundaryError('setup not completed; run Setup.ps1 first','CONFIG_MISSING')
    return validate_config(json.loads(CONFIG.read_text(encoding='utf-8')),REPO)


@staged('port_check')
def port_available(port):
    with socket.socket() as sock:
        try:sock.bind(('127.0.0.1',port))
        except OSError:raise BoundaryError('local port occupied; nothing terminated','PORT_OCCUPIED')


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
    port_available(config['port']);protect_private_root(RUNTIME)
    commands=[[config['python'],'-m','uvicorn','parkweave.api:configured_app','--factory','--host','127.0.0.1','--port',str(config['port'])],
              [config['python'],'-m','parkweave.worker']]
    records=[];children=[];state_written=False
    with stage('service_log'):log=(RUNTIME/'windows-services.log').open('a',encoding='utf-8')
    try:
        for command in commands:
            with stage('process_spawn'):
                child=psutil.Popen(command,cwd=REPO,env=app_environment(dsn,os.environ),stdout=log,stderr=log)
            children.append(child)
            with stage('process_identity'):records.append({'pid':child.pid,'created':child.create_time(),'command':command})
        with stage('process_record'):write_exclusive(STATE,{'project':'ParkWeave','schema':1,'processes':records})
        state_written=True
        import urllib.request
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for _ in range(50):
            if any(c.poll() is not None for c in children):
                with stage('health_readiness'):raise BoundaryError('managed service exited; inspect private log','SERVICE_EXITED')
            try:
                with stage('health_readiness'):
                    with opener.open(f"http://127.0.0.1:{config['port']}/health",timeout=1) as r:
                        health=json.load(r)
                with stage('health_readiness'):
                    if health.get('execution_mode')=='LOCAL' and health.get('model')=='MODEL_MOCK' and health.get('process_id')==children[0].pid:break
            except OSError:pass
            time.sleep(.1)
        else:
            with stage('health_readiness'):raise BoundaryError('local health readiness timeout','READINESS_TIMEOUT')
        print(f"Open http://127.0.0.1:{config['port']} ; synthetic local mode only.")
    except Exception as primary:
        # Keep the existing cleanup/exit behavior; retain the original failure's
        # fixed metadata if a cleanup exception replaces it.
        try:
            for record in records:stop_record(record,REPO,psutil.Process)
            if state_written:STATE.unlink(missing_ok=True)
        except Exception as cleanup:
            cleanup.parkweave_lifecycle_primary=failure(primary)
            raise
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
            try:proc=psutil.Process(record['pid']);owned=identify_process(proc,record,REPO)
            except psutil.NoSuchProcess:owned=False
            rows.append({'pid':record['pid'],'identity_matches':owned})
    print(json.dumps({'project':'ParkWeave','processes':rows,'port':config['port'],'model':'DISABLED'},indent=2))


def stop():
    import psutil
    if not STATE.exists():print('No managed process record. No process/data changed.');return
    state=json.loads(STATE.read_text(encoding='utf-8'))
    if state.get('project')!='ParkWeave' or state.get('schema')!=1:raise BoundaryError('foreign process record refused')
    results=[stop_record(record,REPO,psutil.Process) for record in state['processes']]
    if 'FOREIGN_REFUSED' in results:raise BoundaryError('PID identity mismatch; foreign process and record preserved')
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
        if args.action in ('doctor','start','setup'):
            try:print(diagnostic_command(args.action,exc),flush=True)
            except Exception:pass  # Diagnostic emission never changes the exit verdict.
        # No exception/DSN/HTTP payload strings are emitted; they may contain secrets.
        print('ParkWeave '+args.action+' failed: '+(str(exc) if isinstance(exc,BoundaryError) else type(exc).__name__),file=sys.stderr)
        raise SystemExit(1)


if __name__=='__main__':main()
