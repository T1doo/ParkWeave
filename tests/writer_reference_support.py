"""Controller-owned subprocesses; secrets never enter an API configuration."""
from datetime import datetime,timedelta,timezone
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
from time import monotonic,sleep
from uuid import UUID,uuid4

from parkweave import native_run_access as native, native_run_access_activation as activation
from parkweave import native_run_access_writer as writer
from test_native_run_access import APPROVER,snapshot
from test_preparation import filled,command as material


def child_environment():
    result={k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL','HOME','SYSTEMROOT','TMPDIR')}
    result['PYTHONPATH']=str(Path('src').resolve())+os.pathsep+str(Path('tests').resolve())
    return result


def write_private(path,value):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:json.dump(value,stream)


class Harness:
    def __init__(self,f,request,*,seconds=600,parent=None):
        self.f,self.request=f,request
        self.directory=Path(tempfile.mkdtemp(prefix='pw-writer-'))
        self.processes=[];self.observations=[]
        self.parent=parent or filled(f)
        if parent is None:
            self.parent=material(f,self.parent,'REVIEW',APPROVER,reason='SYNTHETIC current material review').json()
            self.parent=material(f,self.parent,'CONFIRM',reason='SYNTHETIC owner confirms').json()
        self.before=snapshot(f[1])
        proof=f[1]._case_fact_fixture_receipt
        native.install_owned_test_storage(f[1],proof)
        activation.install_owned_test_activation_storage(f[1],proof)
        self.bootstrap=writer.reference_bootstrap(f[1],proof,run_id=UUID(self.parent['run_id']),
            approver_id=APPROVER,beneficiary_id='executor-a',
            valid_until=(datetime.now(timezone.utc)+timedelta(seconds=seconds)).isoformat())
        try:
            self.start_writer()
            self.bind()
        except BaseException:
            for process in reversed(self.processes):self.stop(process)
            shutil.rmtree(self.directory)
            raise

    def observe(self,kind,**data):
        self.observations.append(dict(kind=kind,recorded_utc=datetime.now(timezone.utc).isoformat(),**data))
        if kind in {'WRITER_PROCESS_READY','OWNED_PROCESS_STOP_BEGIN','OWNED_PROCESS_SIGINT_SENT','OWNED_PROCESS_EXITED','API_PROCESS_READY'}:
            from owned_connection_diagnostics import emit
            emit(kind,**data)

    def start_writer(self):
        root=self.directory/('writer-'+str(len(self.processes)));root.mkdir(mode=0o700)
        bootstrap={**self.bootstrap,'boot_id':str(uuid4())}
        from owned_connection_diagnostics import writer_dsn
        bootstrap['writer_dsn']=writer_dsn(bootstrap['writer_dsn'],str(len(self.processes)))
        path=root/'private.json';write_private(path,bootstrap)
        command,verify=str(root/'c.sock'),str(root/'v.sock')
        output=root/'stdout.log';error=root/'stderr.log'
        out=output.open('w');err=error.open('w')
        process=subprocess.Popen([str(Path('.venv/bin/python').absolute()),'-m','parkweave.native_run_access_writer',
            '--reference-bootstrap',str(path),'--command-socket',command,'--verify-socket',verify],
            env=child_environment(),stdout=out,stderr=err)
        out.close();err.close();self.processes.append(process)
        deadline=monotonic()+10
        while monotonic()<deadline:
            if process.poll() is not None:raise AssertionError('writer exited: '+error.read_text())
            if Path(command).exists() and Path(verify).exists():break
            sleep(.02)
        else:raise AssertionError('reference writer did not become ready')
        self.pin=writer.pin_reference_endpoint(bootstrap['policy'],command,verify,process.pid,os.getuid(),bootstrap['boot_id'])
        self.writer_process=process
        self.observe('WRITER_PROCESS_READY',pid=process.pid,boot_id=bootstrap['boot_id'],policy_sha256=self.pin.policy_sha256)

    def bind(self,store=None):
        store=store or self.f[0]
        client=writer.WriterClient(store,self.bootstrap['policy'],self.pin)
        bridge=native.NativeRunAccess(store,writer=client)
        store._native_run_access=bridge
        self.bridge=bridge
        return bridge

    @property
    def a(self):return self.f,self.parent,self.bridge,self.before

    def stop(self,process):
        self.observe('OWNED_PROCESS_STOP_BEGIN',pid=process.pid,already_exited=process.poll() is not None)
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
            self.observe('OWNED_PROCESS_SIGINT_SENT',pid=process.pid)
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.terminate();process.wait(timeout=5)
        self.observe('OWNED_PROCESS_EXITED',pid=process.pid,exit_code=process.returncode)

    def close(self):
        try:
            for process in reversed(self.processes):self.stop(process)
            target=os.environ.get('PARKWEAVE_WRITER_EVIDENCE_DIR')
            if target:
                from hashlib import sha256
                out=Path(target);out.mkdir(parents=True,exist_ok=True)
                path=out/(sha256(self.request.node.nodeid.encode()).hexdigest()[:12]+'.json')
                assert not path.exists()
                with self.f[1].connect() as c:
                    run=c.execute('SELECT id,state,revision,native_run_access_protocol,native_run_access_activation FROM runs WHERE id=%s',
                                  (self.parent['run_id'],)).fetchone()
                    assignments=c.execute('SELECT * FROM run_assignments WHERE run_id=%s',(self.parent['run_id'],)).fetchall()
                with self.f[0].connect() as c:
                    role=c.execute("SELECT current_user app_role,has_table_privilege(current_user,'run_assignments','UPDATE') assignment_write").fetchone()
                path.write_text(json.dumps(dict(test_id=self.request.node.nodeid,scope='OWNED_SYNTHETIC_REFERENCE_WRITER',
                    policy_sha256=self.pin.policy_sha256,observations=self.observations,run=run,assignments=assignments,
                    application=role,actual_production_installation=False,production_permission_changes=False,
                    browser_attempts=0,formal_AT35=False),indent=2,default=str)+'\n')
                logs=out/(path.stem+'-process-logs');logs.mkdir()
                for child in sorted(self.directory.iterdir()):
                    if not child.is_dir():continue
                    for name in ('stdout.log','stderr.log'):
                        source=child/name
                        if source.exists():shutil.copyfile(source,logs/(child.name+'-'+name))
        finally:shutil.rmtree(self.directory)


def start_api(harness,port,*,enabled=True):
    root=harness.directory/('api-'+str(len(harness.processes)));root.mkdir(mode=0o700)
    config=dict(app_dsn=harness.f[0].dsn,port=port)
    if enabled:config.update(policy=harness.bootstrap['policy'],pin=harness.pin.model_dump())
    assert 'writer_dsn' not in config and 'key' not in config
    path=root/'public-scope-and-app.json';write_private(path,config)
    out=(root/'stdout.log').open('w');err=(root/'stderr.log').open('w')
    process=subprocess.Popen([str(Path('.venv/bin/python').absolute()),str(Path('tests/writer_reference_api.py').resolve()),str(path)],
        env=child_environment(),stdout=out,stderr=err)
    out.close();err.close();harness.processes.append(process)
    import httpx
    deadline=monotonic()+10
    while monotonic()<deadline:
        if process.poll() is not None:raise AssertionError('API exited: '+(root/'stderr.log').read_text())
        try:
            r=httpx.get('http://127.0.0.1:'+str(port)+'/health',timeout=.3)
            if r.status_code==200 and r.json()['process_id']==process.pid:break
        except httpx.HTTPError:pass
        sleep(.03)
    else:raise AssertionError('owned API did not become ready')
    harness.observe('API_PROCESS_READY',pid=process.pid,writer_explicitly_bound=enabled,
                    configuration_keys=sorted(config),owner_credentials_supplied=False)
    return process,httpx.Client(base_url='http://127.0.0.1:'+str(port),timeout=10)
