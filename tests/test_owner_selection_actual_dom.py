"""Actual whole shipped HTML + ordinary ASGI + PostgreSQL, jsdom only."""
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import time

import pytest
from fastapi.testclient import TestClient
from parkweave.api import create_app
from test_preparation import preparation_fixture,headers,add
from test_service_capability_catalog_actual import capability_catalog
from test_owner_service_selection import alternatives
from service_release_acceptance_support import authority_snapshot


@pytest.mark.parametrize('mode',['normal','lost','lost_stale'])
def test_owner_choice_actual_dom_api_recovery_and_adopt(capability_catalog,mode,tmp_path):
    a=capability_catalog;f,p,_=alternatives(a);before=authority_snapshot(f[1]);root=Path(__file__).resolve().parents[1]
    env=dict(os.environ)
    if not shutil.which('node') or subprocess.run(['node','-e',"require('jsdom')"],env=env,capture_output=True).returncode:
        pytest.skip('Node and externally installed jsdom are required for this DOM integration test')
    proc=subprocess.Popen(['node','tests/owner_selection_actual_dom.cjs',p['preparation_id'],mode],cwd=root,env=env,text=True,
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=1)
    selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ);result=None;traffic=[]
    try:
        with TestClient(create_app(f[0],capability_catalog=a['catalog'])) as api:
            until=time.monotonic()+25
            while time.monotonic()<until:
                if not selector.select(.1):
                    if proc.poll() is not None:break
                    continue
                line=proc.stdout.readline()
                if not line:break
                message=json.loads(line)
                if message['type']=='result':result=message;break
                assert message['type']=='request'
                options=message['options'];assert options['headers']['Authorization']=='Bearer SYNTHETIC_OWNER_DOM_SESSION'
                actual={**options['headers'],'Authorization':'Bearer '+f[2]['fixture-a']}
                reply=api.request(options.get('method','GET'),message['path'],headers=actual,content=options.get('body'))
                traffic.append(dict(path=message['path'],method=options.get('method','GET'),status=reply.status_code,
                    manual_selection=('manual_selections' in json.loads(options['body'])) if options.get('body') else False))
                if mode=='lost_stale' and options.get('method')=='POST' and message['path'].endswith('/service-selections'):
                    assert reply.status_code==201,reply.text
                    assert add(f,p,text='SYNTHETIC later actual material revision after manual commit').status_code==200
                proc.stdin.write(json.dumps(dict(id=message['id'],status=reply.status_code,body=reply.json()))+'\n');proc.stdin.flush()
        proc.wait(timeout=5);stderr=proc.stderr.read()
        assert proc.returncode==0,stderr
        assert result and result['status']=='PASS'
        generated=[row for row in traffic if row['method']=='POST' and row['path'].endswith('/service-selections')]
        assert len(generated)==1 and generated[0]['manual_selection'] and generated[0]['status']==201
        adopted=[row for row in traffic if row['method']=='POST' and row['path'].endswith('/service-case-plan')]
        assert len(adopted)==(0 if mode=='lost_stale' else 1)
        assert all(row['status']<300 for row in traffic)
        assert authority_snapshot(f[1])==before
        (tmp_path/('owner-selection-dom-'+mode+'.json')).write_text(json.dumps(dict(mode=mode,status='PASS',result=result,traffic=traffic,authority_changed=False,pixel_engine=False),indent=2)+'\n')
    finally:
        selector.close()
        if proc.poll() is None:proc.kill();proc.wait(timeout=5)
