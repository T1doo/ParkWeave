from pathlib import Path
from unittest.mock import patch
import hashlib,json,os,pwd,grp,subprocess,socket,sys,stat,builtins
from datetime import datetime,timezone
root=Path.cwd();sys.path[:0]=[str(root),str(root/'src'),str(root/'tests')]
import psycopg
from parkweave import native_run_access_restricted_host as host
from test_native_run_access_trial_plan import inputs
spec,_,_=inputs();uid=os.geteuid();gid=os.getegid();other=pwd.getpwnam('nobody').pw_uid
spec['api_uid']=uid;spec['writer_uid']=other
interpreter=Path(sys.executable).resolve();envroot=interpreter.parent.parent
paths=subprocess.check_output(['git','ls-files','src/parkweave'],text=True).splitlines();sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
layout=dict(trial_root='/tmp/parkweave-trial-'+'b'*32,source_sha=sha,source_root=str(root/'src'),source_files={str(root/p):hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths},interpreter=str(interpreter),interpreter_sha256=hashlib.sha256(interpreter.read_bytes()).hexdigest(),dependency_roots=[str(envroot)],import_paths=[str(envroot/'lib/python3.12')],api_uid=uid,api_gid=gid,writer_uid=other,ipc_gid=gid,boot_id='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',private_bootstrap_sha256='0'*64,creation_receipt_sha256='0'*64)
controller=host.LinuxHost(spec,layout);hits=[]
def forbidden(*a,**kw):hits.append(True);raise AssertionError('OBSERVATION_MUST_NOT_READ_CONTENT_OR_PERFORM_ACTIONS')
with patch.object(host,'_protected_bytes',forbidden),patch.object(builtins,'open',forbidden),patch.object(os,'open',forbidden),patch.object(Path,'open',forbidden),patch.object(subprocess,'Popen',forbidden),patch.object(psycopg,'connect',forbidden),patch.object(psycopg.Connection,'connect',staticmethod(forbidden)),patch.object(socket.socket,'bind',forbidden),patch.object(socket.socket,'connect',forbidden),patch.object(os,'chmod',forbidden),patch.object(os,'chown',forbidden),patch.object(os,'fchmod',forbidden),patch.object(os,'fchown',forbidden),patch.object(os,'memfd_create',forbidden):
 result=controller.inspect_prerequisites()
assert not hits and result['status']=='BLOCKED' and result['actual_run']=='NOT_RUN' and result['can_start'] is False
facts=dict(euid=uid,egid=gid,supplementary_groups=os.getgroups(),declared_api_uid=uid,declared_writer_uid=other,declared_ipc_gid=gid,designated_trial_ipc_group_exists=any(g.gr_name=='pwci_ipc' for g in grp.getgrall()),source_owner=(root/'src/parkweave').lstat().st_uid,interpreter_owner=interpreter.lstat().st_uid)
record=dict(source_sha=sha,observed_utc=datetime.now(timezone.utc).isoformat(),result=result,actual_environment_metadata=facts,forbidden_action_attempts=len(hits),qualification='Actual current-process/path/account metadata only. Nobody/gid declarations are diagnostic candidates, not adopted trial identities. No source-content integrity, signed approval, secret, SQL or host/IPC execution proof.',host_IPC='NOT_RUN',prior27_repeated=False)
(root/'.runtime/host-prerequisites-20261013/actual-environment.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
