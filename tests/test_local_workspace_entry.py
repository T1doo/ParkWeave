"""Password entry transport and adapter; does not claim real identity issuance."""
from pathlib import Path
import subprocess
import sys
from fastapi.testclient import TestClient
from fastapi import FastAPI
from scripts import local_product as product
from parkweave.local_workspace import full_workspace_page, mount_workspace


def test_mounted_workspace_reuses_login_and_keeps_original_script(tmp_path):
    calls=[]
    def unlock(role,password):
        calls.append((role,password))
        return dict(bearer='PUBLIC_SYNTHETIC_TEST_ONLY')
    base='http://127.0.0.1:58763'
    app=mount_workspace(FastAPI(),unlock,58763,[('enterprise','企业'),('specialist','专员')])
    with TestClient(app,base_url=base,client=('127.0.0.1',12345)) as client:
        root=client.get('/');page=client.get('/workspace');script=client.get('/local-workspace-login.js')
        assert root.status_code==page.status_code==script.status_code==200
        assert 'id="nav-workspace"' in root.text and "location.assign('/workspace')" in root.text
        original=(Path(__file__).parents[1]/'src/parkweave/web.html').read_text()
        original_js=original.split('<script>')[1].split('</script>')[0]
        assert original_js in page.text and 'data-local-workspace="locked"' in page.text
        assert 'id="local-workspace-login"' in page.text and '/local-workspace-login.js' in page.text
        assert page.headers['cache-control']=='no-store' and page.headers['referrer-policy']=='no-referrer'
        assert 'PUBLIC_SYNTHETIC_TEST_ONLY' not in page.text and calls==[]
        assert client.post('/api/local/session',json={'role':'enterprise','password':'PUBLIC_TEST'}).status_code==403
        assert calls==[]
        assert client.post('/api/local/session',headers={'Origin':base},json={'role':'enterprise','password':'PUBLIC_TEST'}).status_code==200
        assert calls==[('enterprise','PUBLIC_TEST')]


def test_linux_password_installation_serves_same_workspace_adapter(tmp_path):
    with TestClient(product.application(tmp_path,{},58764),base_url='http://127.0.0.1:58764') as client:
        assert 'id="local-workspace-login"' in client.get('/workspace').text
        script=client.get('/local-workspace-login.js')
        assert script.status_code==200 and 'originalStoredWritePending' in script.text


def test_account_labels_are_not_executable_html():
    root=Path(__file__).parents[1]/'src/parkweave'
    page=full_workspace_page(root,[('x"<>','<script>not executable</script>')])
    assert '<script>not executable</script>' not in page
    assert '&lt;script&gt;not executable&lt;/script&gt;' in page
    assert 'value="x&quot;&lt;&gt;"' in page


def test_password_adapter_unknown_and_late_response_contract():
    for script in ('local_workspace_login.js','local_workspace_login_with_page.js'):
        result=subprocess.run(['node','tests/'+script],cwd=Path(__file__).parents[1],text=True,capture_output=True,timeout=15)
        assert result.returncode==0,result.stderr
        assert result.stdout.startswith('PASS ')
