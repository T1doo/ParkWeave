"""Normal Linux getpass CLI and served page JS; no direct install/auth API setup.

Actual owned PG/API/worker and HTTP. DOM/Web Locks/storage are controlled Node
seams, not browser or visual evidence. New private synthetic state is retained.
"""
import sys,os,json,secrets,pty,termios,subprocess,select,time,signal,socket,http.client,hashlib
from pathlib import Path
from urllib.request import urlopen
import pytest
pytestmark=pytest.mark.skipif(sys.platform!='linux',reason='Linux local product only')

def test_normal_cli_install_page_business_keepalive_stop_and_readonly_reopen():
    parent=Path(__file__).resolve().parents[1]/'.runtime'/'ce'
    parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    out=parent/secrets.token_hex(4);out.mkdir(mode=0o700);(out/'p').mkdir(mode=0o700)
    ROOT=Path(__file__).resolve().parents[1]
    python=sys.executable;passwords={r:secrets.token_urlsafe(24) for r in ('enterprise','specialist')}
    env=dict(os.environ)
    env.pop('PYTHONPATH',None)
    assert not any(k.upper().startswith('PG') for k in env),'ordinary clean environment required before installation'
    # The ordinary environment is pre-existing; no secret environment value is inspected or logged.
    report=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
     scope='NORMAL_LINUX_CLI_INSTALL_START_AND_FULL_PAGE_JS_REAL_HTTP_NOT_BROWSER',
     source_checkout=str(ROOT),python=python,manual_authority_or_database_setup=False,commands=[],page_visual='NOT_RUN_SANDBOX_REFUSAL',windows_native=False)
    server=None;state=None;log=None;keep=None;installer=None;master=None;phase='INSTALL'
    def command(args):
     cmd=[python,'-B','-m','scripts.local_product',*args];report['commands'].append(cmd);return cmd
    try:
     master,slave=pty.openpty()
     cmd=command(['install','--parent',str(out/'p')]);proc=subprocess.Popen(cmd,cwd=ROOT,env=env,stdin=slave,stdout=slave,stderr=slave);installer=proc;os.close(slave)
     data=b'';prompts=['企业独立密码（至少12字符）: ','再次输入企业密码: ','专员独立密码（至少12字符）: ','再次输入专员密码: ']
     deadline=time.monotonic()+40;sent=0
     while time.monotonic()<deadline:
      ready,_,_=select.select([master],[],[],.1)
      if ready:
       try:chunk=os.read(master,16384)
       except OSError:break
       if not chunk:break
       data+=chunk
      if sent<4 and prompts[sent].encode() in data:
       assert not termios.tcgetattr(master)[3]&termios.ECHO,'getpass must disable echo before any password input'
       os.write(master,(passwords['enterprise' if sent<2 else 'specialist']+'\n').encode());sent+=1
      if proc.poll() is not None:break
     proc.wait(timeout=5);os.close(master);master=None
     assert proc.returncode==0 and sent==4,'normal getpass install refused'
     assert all(p.encode() not in data for p in passwords.values()),'TTY echoed a password'
     objects=[]
     for line in data.decode().splitlines():
      pos=line.find('{')
      if pos>=0:
       try:objects.append(json.loads(line[pos:]))
       except ValueError:pass
     state=Path(next(o['state_dir'] for o in objects if 'state_dir' in o));report['state_dir']=str(state)
     assert not (state/'sessions.json').exists();report['normal_getpass_noecho']=True;report['install_exit_code']=proc.returncode
     marker=json.loads((state/'state.json').read_text())
     report['runtime_source_sha256']=marker['runtime_source_sha256']
     report['entry_sha256']=hashlib.sha256((ROOT/'scripts/local_product.py').read_bytes()).hexdigest()
     (out/'install-output-redacted.json').write_text(json.dumps(objects,indent=2)+'\n')
     with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
     base=f'http://127.0.0.1:{port}';report['base']=base
     log=(out/'normal-service.log').open('ab')
     def start():
      nonlocal server
      server=subprocess.Popen(command(['start','--state-dir',str(state),'--port',str(port)]),cwd=ROOT,env=env,stdout=log,stderr=log)
      end=time.monotonic()+15
      while time.monotonic()<end:
       assert server.poll() is None,'normal start refused; private log retained'
       try:
        with urlopen(base+'/health',timeout=.3) as r:
         value=json.load(r)
         if value.get('data')=='SYNTHETIC' and value.get('process_id')==server.pid:return
       except OSError:pass
       time.sleep(.1)
      raise AssertionError('normal readiness timeout')
     def stop():
      nonlocal server
      assert server and server.poll() is None
      server.send_signal(signal.SIGINT);server.wait(timeout=25);assert server.returncode==0
      report.setdefault('stop_exit_codes',[]).append(server.returncode);server=None
      assert not (state/'data/postmaster.pid').exists() and not (state/'stop-unconfirmed').exists()
     def page(reopen=None):
      payload=dict(base=base,passwords=passwords,**(dict(reopen=True,preparation_id=reopen) if reopen else {}))
      result=subprocess.run(['node',str(ROOT/'tests/local_product_page_http.js')],cwd=ROOT,input=json.dumps(payload),text=True,capture_output=True,timeout=35)
      if result.returncode:
       (out/'page-failure-redacted.json').write_text(result.stderr)
       raise AssertionError('real page handlers failed; no private input logged')
      value=json.loads(result.stdout);(out/('page-reopen.json' if reopen else 'page-first.json')).write_text(json.dumps(value,indent=2)+'\n');return value
     phase='FIRST_START';start();first_pid=int((state/'data/postmaster.pid').read_text().splitlines()[0]);report['first_pg_pid']=first_pid
     phase='DUPLICATE_START_REFUSAL'
     duplicate=subprocess.run(command(['start','--state-dir',str(state),'--port',str(port)]),cwd=ROOT,env=env,capture_output=True,timeout=10)
     assert duplicate.returncode==1 and server.poll() is None and int((state/'data/postmaster.pid').read_text().splitlines()[0])==first_pid
     report['duplicate_start_refused_without_stopping_owner']=True
     phase='PAGE_BUSINESS';first=page();report['page_business']=dict(preparation_id=first['preparation_id'],state=first['snapshot']['preparation']['state'],revision=first['snapshot']['preparation']['revision'])
     phase='STOP_WITH_BROWSER_EQUIVALENT_KEEPALIVE'
     keep=http.client.HTTPConnection('127.0.0.1',port,timeout=5);keep.request('GET','/health');assert keep.getresponse().read()
     stop();keep.close();keep=None
     phase='OCCUPIED_PORT_REFUSAL'
     control=hashlib.sha256((state/'data/global/pg_control').read_bytes()).hexdigest()
     pglog=(state/'logs/postgres.log').stat().st_size
     with socket.socket() as other:
      other.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);other.bind(('127.0.0.1',port));other.listen()
      refused=subprocess.run(command(['start','--state-dir',str(state),'--port',str(port)]),cwd=ROOT,env=env,capture_output=True,timeout=10)
      assert refused.returncode==1 and other.getsockopt(socket.SOL_SOCKET,socket.SO_ACCEPTCONN)==1
     assert not (state/'data/postmaster.pid').exists()
     assert hashlib.sha256((state/'data/global/pg_control').read_bytes()).hexdigest()==control
     assert (state/'logs/postgres.log').stat().st_size==pglog
     report['occupied_port_refused_before_pg_without_takeover']=True
     phase='RESTART_SAME_PORT';start();report['second_pg_pid']=int((state/'data/postmaster.pid').read_text().splitlines()[0]);assert report['second_pg_pid']!=first_pid
     phase='READ_PERSISTED';second=page(first['preparation_id']);assert first['snapshot']==second['snapshot'];report['whole_readback_exact']=True
     phase='FINAL_STOP';stop();report['result']='PASS'
    except BaseException as error:
     report.update(result='FAIL',failure_stage=phase,error_type=type(error).__name__)
     raise
    finally:
     if installer is not None and installer.poll() is None:
      installer.send_signal(signal.SIGINT)
      try:installer.wait(timeout=5)
      except subprocess.TimeoutExpired:report['installer_cleanup']='UNKNOWN_NO_AUTOMATIC_RETRY'
     if master is not None:os.close(master)
     if keep:keep.close()
     if server and server.poll() is None:
      server.send_signal(signal.SIGINT)
      try:server.wait(timeout=25)
      except subprocess.TimeoutExpired:report['cleanup']='UNKNOWN_NO_AUTOMATIC_RETRY'
     if log:log.close()
     (out/'normal-cli-result.json').write_text(json.dumps(report,indent=2)+'\n')
     print(json.dumps({k:v for k,v in report.items() if k not in ('commands',)}))
