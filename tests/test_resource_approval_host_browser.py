"""Real Chromium/API/host/PG; host installation uses named SYNTHETIC boundary DI."""
from contextlib import contextmanager
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx
import pytest
from playwright.sync_api import sync_playwright,expect

from parkweave.process_env import minimal_environment
from resource_approval_host_support import running_host
from resource_approval_read_support import seeded
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture,headers
from test_ordinary_runtime_read import snapshot
from test_native_preparation_entry_browser import open_record


@contextmanager
def api_process(f,directory,cfg,*,fixture=True):
    directory.mkdir();root=Path(__file__).resolve().parents[1]
    env=minimal_environment(os.environ,PYTHONPATH=os.pathsep.join([str(root/'tests'),str(root/'src')]),PYTHONDONTWRITEBYTECODE='1',
        PARKWEAVE_DSN=f[0].dsn,PARKWEAVE_MODE='LOCAL',PARKWEAVE_RESOURCE_APPROVAL_READ_CONFIG=cfg.model_dump_json())
    # Pass an already-listening owned socket; no close-and-rebind port race.
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));listener.listen(8)
        port=listener.getsockname()[1]
        factory='resource_approval_host_support:fixture_app' if fixture else 'parkweave.api:configured_app'
        with (directory/'api.log').open('w') as log:
            child=subprocess.Popen([sys.executable,'-B','-m','uvicorn',factory,'--factory','--fd',str(listener.fileno()),'--log-level','warning','--no-access-log'],
                cwd=root,env=env,pass_fds=(listener.fileno(),),stdout=log,stderr=subprocess.STDOUT)
            try:
                if not fixture:
                    assert child.wait(timeout=10)!=0
                    yield None,child.pid
                else:
                    with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=3) as api:
                        until=time.monotonic()+10
                        while time.monotonic()<until:
                            assert child.poll() is None,(directory/'api.log').read_text()
                            try:
                                r=api.get('/health')
                                if r.status_code==200 and r.json()['process_id']==child.pid:break
                            except httpx.TransportError:pass
                            time.sleep(.03)
                        else:pytest.fail('owned API readiness deadline exceeded')
                        yield api,child.pid
            finally:
                if child.poll() is None:child.terminate()
                try:child.wait(timeout=5)
                except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)


def test_existing_source_survives_api_process_restart_and_current_revocation(receipt_fixture,tmp_path,monkeypatch):
    f=receipt_fixture;p,source,_,_=seeded(f,tmp_path,monkeypatch);before=snapshot(f[1]);proof=[]
    with running_host(tmp_path/'host',source) as (cfg,_,host_process),sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        for phase in ('first','fresh-api'):
            with api_process(f,tmp_path/phase,cfg) as (api,pid):
                page=browser.new_page(viewport={'width':320,'height':900});seen=[];page.on('request',lambda r:seen.append(dict(method=r.method,url=r.url)))
                open_record(page,api,f,p);page.locator('#resource-plan-approval-read').click()
                expect(page.locator('#resource-plan-approval-status')).to_contain_text('本次读取已核对已有资源方案批准')
                expect(page.locator('#resource-plan-approval-result')).to_contain_text('合成契约样本，不证明真实批准')
                expect(page.locator('#resource-plan-approval-result')).to_contain_text(source.record()['approval_id'])
                if phase=='fresh-api':
                    record=source.record();record.update(state='REVOKED',record_revision=2,revoked_at=datetime.now(timezone.utc).isoformat());source.write(record)
                    page.locator('#resource-plan-approval-original').click()
                    expect(page.locator('#resource-plan-approval-status')).to_contain_text('原批准已撤销')
                assert all(x['method']=='GET' for x in seen) and snapshot(f[1])==before
                assert api.get('/api/plan-approval/status',headers=headers(f[2])).json()['enabled'] is False
                assert api.get('/api/run-access/status',headers=headers(f[2])).json()['enabled'] is False
                page.screenshot(path=str(tmp_path/(phase+'.png')),full_page=True)
                proof.append(dict(phase=phase,api_pid=pid,host_pid=host_process.pid,requests=seen));page.close()
        browser.close()
        assert proof[0]['api_pid']!=proof[1]['api_pid']
        calls=[json.loads(x) for x in (tmp_path/'host/calls.jsonl').read_text().splitlines()]
        assert len(calls)==15
        for start in (0,5,10):assert [x['operation'] for x in calls[start:start+5]]==['READ_EXISTING','VERIFY_EXISTING','READ_EXISTING','VERIFY_EXISTING','VERIFY_EXISTING']
    (tmp_path/'proof.json').write_text(json.dumps(dict(scope='SYNTHETIC_SAME_UID_HOST_INSTALLATION_BOUNDARY_DI_ACTUAL_IPC_API_CHROMIUM_PG',
        production_host_installation_verified=False,real_approval_verified=False,execution_authorized=False,
        same_host_different_api_processes=True,observations=proof),indent=2)+'\n')


def test_unmodified_cli_refuses_same_uid_synthetic_binding_before_any_backend_read(receipt_fixture,tmp_path,monkeypatch):
    f=receipt_fixture;p,source,_,_=seeded(f,tmp_path,monkeypatch);before=snapshot(f[1])
    with running_host(tmp_path/'host',source) as (cfg,_,_):
        for phase in ('first','cold'):
            with api_process(f,tmp_path/phase,cfg,fixture=False):pass
            assert 'existing protected approval host binding invalid or unavailable; values not echoed' in (tmp_path/phase/'api.log').read_text()
        assert not (tmp_path/'host/calls.jsonl').exists() and snapshot(f[1])==before
