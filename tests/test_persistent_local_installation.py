"""Focused real install outside /tmp and two independent normal HTTP processes."""
from dataclasses import replace
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

import httpx
import pytest

if sys.platform!='linux':pytest.skip('Linux persistent installation only',allow_module_level=True)
pytest.importorskip('cryptography')
pytest.importorskip('pgserver')

from scripts.local_product import install
from scripts import material_only_demo as material
from parkweave.local_identity import LocalSessionVault
from parkweave.local_installation import PersistentInstallation, create_database, STATE
from parkweave.store import Denied


def test_persistent_root_real_create_and_reopen_without_fixture_receipt(tmp_path):
    parent=Path(__file__).resolve().parents[1]/'.runtime'/'pv'
    if parent.is_relative_to('/tmp'):pytest.skip('checkout outside temporary storage required')
    parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    passwords={role:secrets.token_urlsafe(24) for role in ('enterprise','specialist')}
    oldmask=os.umask(0o077)
    try:path=install(LocalSessionVault(passwords),parent)
    finally:os.umask(oldmask)
    assert not path.is_relative_to('/tmp')
    assert json.loads((path/STATE).read_text())['phase']=='RELEASE_PENDING'
    marker=json.loads((path/'state.json').read_text())
    assert marker['schema']=='parkweave-local-material-installation/1'
    assert not (path/'sessions.json').exists()
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    server=None
    log=(path/'logs/persistent-integration.log').open('a')
    def start():
        nonlocal server
        server=subprocess.Popen([sys.executable,'-B','-m','scripts.local_product','start',
            '--state-dir',str(path),'--port',str(port)],cwd=material.ROOT,
            env={**os.environ,'PYTHONPATH':str(material.ROOT/'src')},stdout=log,stderr=log)
        for _ in range(100):
            assert server.poll() is None,'owned persistent server exited; private log retained'
            try:
                if httpx.get(base+'/health',timeout=.3).status_code==200:return
            except httpx.TransportError:pass
            time.sleep(.1)
        raise AssertionError('persistent HTTP startup timeout')
    def stop():
        nonlocal server
        if server is not None and server.poll() is None:
            server.send_signal(signal.SIGINT);server.wait(timeout=25)
            assert server.returncode==0
        server=None
        assert not (path/'data/postmaster.pid').exists()
    def login():
        response=httpx.post(base+'/api/local/session',headers={'Origin':base},
            json=dict(role='enterprise',password=passwords['enterprise']))
        assert response.status_code==200
        value=response.json()
        return {'Authorization':'Bearer '+value['bearer']},value['installation_id'],value
    def post(route,headers,body,expected):
        response=httpx.post(base+route,headers={**headers,'Idempotency-Key':str(uuid4())},json=body)
        assert response.status_code==expected,'original persistent HTTP command refused'
        return response.json()
    try:
        start();headers,installation_id,identity=login()
        run=post('/api/runs',headers,dict(goal='SYNTHETIC persistent installation',source='SYNTHETIC'),202)['run_id']
        for _ in range(50):
            if httpx.get(base+'/api/runs/'+run,headers=headers).json()['state']=='SUCCEEDED':break
            time.sleep(.1)
        else:raise AssertionError('normal worker did not finish')
        reviewer=httpx.get(base+'/api/preparation-catalog',headers=headers).json()['reviewers'][0]['id']
        reference=post('/api/preparations',headers,dict(run_id=run,service_id='synthetic-material-preparation',
            service_version=1,reviewer_id=reviewer),201)
        route='/api/preparations/'+reference['preparation_id']
        key=str(uuid4())
        command=dict(action='ADD_EVIDENCE',expected_revision=1,slot='need_summary',text='SYNTHETIC persistent source',
            source_kind='DOCUMENT_EXCERPT',source_label='SYNTHETIC v1')
        # Forward exactly one real command, then truncate its committed HTTP
        # acknowledgement. No mock API/store and no write replay during recovery.
        committed=[]
        class TruncateAcknowledgement(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                assert self.path==route+'/commands' and self.headers['Idempotency-Key']==key
                count=int(self.headers['Content-Length']);assert 0<count<16384
                response=httpx.post(base+self.path,headers={**headers,'Idempotency-Key':key,'Content-Type':'application/json'},
                    content=self.rfile.read(count),timeout=5)
                assert response.status_code==200
                committed.append(response.json())
                self.send_response(200);self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(response.content)));self.end_headers()
                self.wfile.write(b'{');self.wfile.flush();self.close_connection=True
        with ThreadingHTTPServer(('127.0.0.1',0),TruncateAcknowledgement) as proxy:
            thread=threading.Thread(target=proxy.serve_forever,daemon=True);thread.start()
            try:
                result=subprocess.run(['node','tests/local_workspace_interruption.js'],cwd=material.ROOT,
                    input=json.dumps(dict(proxy=f'http://127.0.0.1:{proxy.server_port}',base=base,route=route,
                        command=command,key=key,installation=installation_id,identity=identity)),
                    capture_output=True,text=True,timeout=25)
                assert result.returncode==0,result.stderr
                print(result.stdout.strip())
                assert len(committed)==1
            finally:proxy.shutdown();thread.join(timeout=2)
        original=committed[0]
        before=httpx.get(base+route,headers=headers).json()
        stop()
        assert json.loads((path/STATE).read_text())['phase']=='RELEASE_PENDING'
        start();headers,reopened_id,_=login()
        assert reopened_id==installation_id
        after=httpx.get(base+route,headers=headers).json()
        assert after==before
        recovery=httpx.get(base+route+'/command-recovery',headers={**headers,'Idempotency-Key':key}).json()
        assert recovery['status']=='COMMITTED' and recovery['event']==original
        assert len(after['history'])==2  # no recovery replay or startup seed
        stop()
        with PersistentInstallation.open_existing(path) as reopened:
            with pytest.raises(Denied):create_database(reopened)
        summary=dict(source_commit=material.source_binding()['source_commit'],
            runtime_source_sha256=marker['runtime_source_sha256'],persistent_root_outside_tmp=True,
            issuer='LocalDatabaseCreationEvidence',fixture_contract_unchanged=True,
            independent_http_process_reopen_exact=True,original_evidence_recovery_read_only=True,
            committed_response_truncated=True,actual_page_api_two_contexts_one_post=True,
            actual_logout_and_recovery_handlers=True,other_identity_recovery_reads=0,
            reloaded_original_identity_recovery_gets=2,write_replay_count=0,
            data_retained=True,system_reboot='NOT_RUN',browser='NOT_RUN_NATIVE_SANDBOX_REFUSAL')
        (tmp_path/'persistent-local-product-result.json').write_text(json.dumps(summary,indent=2))
    finally:
        stop();log.close()


def test_forged_persistent_receipt_and_repeat_create_are_denied(tmp_path):
    parent=Path(__file__).resolve().parents[1]/'.runtime'/'pv'
    if parent.is_relative_to('/tmp'):pytest.skip('checkout outside temporary storage required')
    parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    previous=os.umask(0o077)
    try:
        with PersistentInstallation.create_new(parent) as lease:
            lease.initialize()
            with lease.postgres():
                owner=create_database(lease)
                with pytest.raises(Denied):create_database(lease)
                receipt=owner._case_fact_fixture_receipt
                with lease.connect() as connection:
                    with pytest.raises(Denied):replace(receipt).authorize_migration(connection)
                    receipt.authorize_migration(connection)
    finally:os.umask(previous)
