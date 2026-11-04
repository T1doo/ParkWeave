"""Fresh ordinary four-password setup, actual PG/API/worker and served handlers.

No owner SQL, synthetic token fixture, Windows/native operation or model HTTP.
The only setup is the product's normal explicit CLI, through a no-echo PTY.
"""
import hashlib,json,os,pty,secrets,select,signal,socket,subprocess,sys,termios,time
from pathlib import Path
from urllib.request import urlopen
import pytest

pytestmark=pytest.mark.skipif(sys.platform!='linux',reason='normal Linux sample only')


def assert_persistent_readback(first,cold):
    # A mutation response carries its own event receipt; a plain GET never
    # claims to have performed that command. Its complete persisted history
    # must still include that exact event, with every other field unchanged.
    original=dict(first['plan']);current=dict(cold['plan'])
    event=original.pop('event');receipt=original.pop('command_receipt')
    assert current.pop('event') is None and current.pop('command_receipt') is None
    assert original==current
    assert event in cold['plan']['events'] and event['id']==receipt['id']
    assert first['receipt']==cold['receipt'] and cold['cold_business_POSTs']==0


def test_explicit_sample_install_four_password_roles_full_collaboration_and_cold_read():
    root=Path(__file__).parents[1]
    base_dir=Path('/workspace/pwsc');base_dir.mkdir(mode=0o700,exist_ok=True)
    output=base_dir/secrets.token_hex(4);output.mkdir(mode=0o700);parent=output/'p';parent.mkdir(mode=0o700)
    passwords={r:secrets.token_urlsafe(24) for r in ('enterprise','specialist','executor','resource-admin')}
    env=dict(os.environ);env.pop('PYTHONPATH',None);assert not any(k.upper().startswith('PG') for k in env)
    report=dict(scope='NORMAL_PASSWORD_INSTALLED_LINUX_SYNTHETIC_COLLABORATION_NOT_WINDOWS_OR_BROWSER',
        source_commit_at_start=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        runtime_files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [root/'scripts/local_product.py',root/'src/parkweave/local_sample.py',root/'src/parkweave/local_identity.py',root/'src/parkweave/local_installation.py']},
        source_tree_dirty_at_start=bool(subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip()),
        commands=[],Windows=False,browser=False,real_model_calls=0,owner_SQL=False)
    started=time.monotonic();server=installer=None;master=None;log=None;state=None;phase='INSTALL'
    def cmd(*args):
        value=[sys.executable,'-B','-m','scripts.local_product',*args];report['commands'].append(value);return value
    def stop():
        nonlocal server
        assert server is not None and server.poll() is None
        server.send_signal(signal.SIGINT);server.wait(timeout=25);assert server.returncode==0
        report.setdefault('stop_exit_codes',[]).append(server.returncode);server=None
        assert not (state/'data/postmaster.pid').exists() and not (state/'stop-unconfirmed').exists()
    try:
        master,slave=pty.openpty();installer=subprocess.Popen(cmd('install','--sample-collaboration','--parent',str(parent)),cwd=root,env=env,stdin=slave,stdout=slave,stderr=slave);os.close(slave)
        prompts=[]
        for account,label in [('enterprise','企业'),('specialist','专员'),('executor','执行者'),('resource-admin','资源管理员')]:
            prompts.extend([(f'{label}独立密码（至少12字符）: ',account),(f'再次输入{label}密码: ',account)])
        raw=b'';sent=0;end=time.monotonic()+50
        while time.monotonic()<end:
            ready,_,_=select.select([master],[],[],.1)
            if ready:
                try:chunk=os.read(master,32768)
                except OSError:break
                if not chunk:break
                raw+=chunk
            if sent<len(prompts) and prompts[sent][0].encode() in raw:
                assert not termios.tcgetattr(master)[3]&termios.ECHO
                os.write(master,(passwords[prompts[sent][1]]+'\n').encode());sent+=1
            if installer.poll() is not None:break
        installer.wait(timeout=5);os.close(master);master=None
        assert all(v.encode() not in raw for v in passwords.values())
        report['installer_exit']=installer.returncode;report['noecho_password_prompts']=sent
        objects=[]
        for line in raw.decode().splitlines():
            i=line.find('{')
            if i>=0:
                try:objects.append(json.loads(line[i:]))
                except ValueError:pass
        (output/'install-receipts.json').write_text(json.dumps(objects,indent=2)+'\n')
        if installer.returncode!=0:
            (output/'install-error-redacted.log').write_bytes(raw)
        assert installer.returncode==0 and sent==8,'normal sample installation failed; retained receipt/log'
        receipt=next(o for o in objects if o.get('installed')=='LOCAL_SYNTHETIC_COLLABORATION_ONLY');state=Path(receipt['state_dir']);report['state_dir']=str(state)
        marker=json.loads((state/'state.json').read_text());report['initial_authority']=marker['authority'];report['sample']=marker['sample']
        assert marker['authority']['counts']==dict(principals=4,capability_grants=5,action_grants=1,preparation_grants=2,preparation_catalog=1,run_assignments=0,field_grants=0,synthetic_resources=2,synthetic_resource_grants=4)
        assert not (state/'sessions.json').exists()
        sealed=(state/'local-identities.sealed').read_bytes();assert all(v.encode() not in sealed for v in passwords.values())
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        base=f'http://127.0.0.1:{port}';log=(output/'service.log').open('ab')
        def start():
            nonlocal server
            server=subprocess.Popen(cmd('start','--state-dir',str(state),'--port',str(port)),cwd=root,env=env,stdout=log,stderr=log)
            end=time.monotonic()+20
            while time.monotonic()<end:
                assert server.poll() is None,'normal sample start failed; owned log retained'
                try:
                    with urlopen(base+'/health',timeout=.3) as response:
                        health=json.load(response)
                        if health.get('process_id')==server.pid and health.get('data')=='SYNTHETIC':
                            report.setdefault('generations',[]).append(dict(api_pid=server.pid,postgres_pid=int((state/'data/postmaster.pid').read_text().splitlines()[0])));return
                except OSError:pass
                time.sleep(.1)
            raise AssertionError('sample readiness deadline')
        def page(first=None):
            value=dict(base=base,passwords=passwords)
            if first:value.update(reopen=True,preparation_id=first['preparation_id'],step=first['step'])
            result=subprocess.run(['node','tests/local_sample_page_http.js'],cwd=root,env={k:v for k,v in env.items() if not k.endswith('_API_TOKEN')},input=json.dumps(value),text=True,capture_output=True,timeout=80)
            assert all(p not in result.stdout+result.stderr for p in passwords.values())
            (output/('cold-page.stdout' if first else 'first-page.stdout')).write_text(result.stdout)
            (output/('cold-page.stderr' if first else 'first-page.stderr')).write_text(result.stderr)
            assert result.returncode==0,'normal page flow failed; sanitized trace retained'
            return json.loads(result.stdout)
        phase='FIRST_START';start();phase='NORMAL_PASSWORD_PAGE_FLOW';first=page();report['first']=first
        phase='FIRST_STOP';stop();phase='SECOND_START';start();phase='COLD_PASSWORD_READ';cold=page(first);report['cold']=cold
        assert_persistent_readback(first,cold)
        assert report['generations'][0]['api_pid']!=report['generations'][1]['api_pid'] and report['generations'][0]['postgres_pid']!=report['generations'][1]['postgres_pid']
        phase='FINAL_STOP';stop();report['result']='PASS'
    except BaseException as error:
        report.update(result='FAIL',stage=phase,error_type=type(error).__name__);raise
    finally:
        if installer is not None and installer.poll() is None:
            installer.send_signal(signal.SIGINT)
            try:installer.wait(timeout=5)
            except subprocess.TimeoutExpired:report['installer_cleanup']='UNKNOWN_NO_RETRY'
        if master is not None:os.close(master)
        if server is not None and server.poll() is None:
            server.send_signal(signal.SIGINT)
            try:server.wait(timeout=25);report['failure_stop_exit']=server.returncode
            except subprocess.TimeoutExpired:report['cleanup']='UNKNOWN_NO_RETRY'
        if log:log.close()
        report['elapsed_seconds']=round(time.monotonic()-started,3)
        (output/'result.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
        print(json.dumps({'evidence':str(output),'result':report['result'],'stage':phase,'seconds':report['elapsed_seconds']}))
