"""Cloud source, transport and real SQL checks. No Windows native acceptance."""
import base64
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from parkweave import preparation
from parkweave.api import create_app
from parkweave.local_workspace import mount_workspace
from parkweave.store import Denied
from scripts.windows_portable import native_web_login as login
from scripts.windows_portable import credential_envelope as e
from scripts.windows_portable import dpapi_native_candidate as dpapi
from scripts.windows_portable import payload
from scripts.windows_portable.native_runtime_staging import installation_plan, RuntimeSource
from scripts.windows_portable.controller import CandidateRefused
from scripts.windows_portable.processes import Command, ProcessRefused


def manifest(names):
    return json.dumps(dict(schema=payload.SCHEMA,status='INITIALIZATION_NOT_ENABLED',source_commit='a'*40,
        files={name:dict(bytes=0,sha256=hashlib.sha256(b'').hexdigest()) for name in names})).encode()


def test_staging_rejects_ancestor_alias_reserved_and_foreign_top_level_before_io():
    for names in (['runtime/x','runtime/x/a'],['runtime/X/a','runtime/x/b'],
                  ['data/a'],['DATA/a'],['.parkweave-entry.lock'],['.parkweave-lease.json/x'],
                  ['payload-manifest.json/a'],['runtime/a~1'],['unknown/a'],['runtime']):
        with pytest.raises(Exception): installation_plan(manifest(names))
    raw=manifest(['app/a.py','vendor/lib/data/empty.py','runtime/python/python.exe'])
    directories,files=RuntimeSource(r'C:\private\payload',raw).plan(dict(source_commit='a'*40,
        manifest_sha256=hashlib.sha256(raw).hexdigest()))
    assert 'vendor/lib/data' in directories and len(files)==4
    assert files[-1][0]=='vendor/lib/data/empty.py'
    with pytest.raises(CandidateRefused):
        RuntimeSource(r'C:\private\payload',raw+b' ').plan(dict(source_commit='a'*40,manifest_sha256=hashlib.sha256(raw).hexdigest()))


def test_password_context_is_separate_and_native_constructor_refuses_cloud(fixture,monkeypatch):
    store,owner,tokens,_=fixture
    import secrets
    tokens={**tokens,**{name:secrets.token_urlsafe(32) for name in login.REVIEWERS}}
    preparation.seed_synthetic(owner,tokens)
    installation='a'*64
    passwords={name:'PUBLIC_TEST_PASSWORD_'+name for name in login.ACCOUNTS}
    salt=bytes(range(32)); keys={name:login.entropy(passwords[name],salt,installation,name) for name in login.ACCOUNTS}
    assert len(set(keys.values()))==6
    assert login.entropy(passwords['fixture-a'],salt,'b'*64,'fixture-a')!=keys['fixture-a']
    config=dict(schema=login.SCHEMA,installation=installation,port=58761,accounts={name:dict(
        actor=login.actor_for(name),token_sha256=hashlib.sha256(token.encode()).hexdigest(),salt=salt.hex(),
        ciphertext=base64.b64encode(name.encode()).decode()) for name,token in tokens.items()})
    raw=e.canonical(config).decode()
    with pytest.raises(Denied):login.NativePasswordLogin(store,raw)
    # Explicit native-call seam ONLY: real current SQL authorization and HTTP
    # routes below, no claim that this verifies DPAPI encryption on Windows.
    class ControlledDPAPI:
        def unprotect(self,cipher,extra):
            name=cipher.decode()
            if extra!=keys[name]:raise dpapi.NativeFailure('ALLOCATION','ProtectionRefused',[],13)
            return e.canonical(dict(schema=login.SCHEMA,installation=installation,actor=login.actor_for(name),bearer=tokens[name]))
    monkeypatch.setattr(dpapi,'_NativeDPAPI',ControlledDPAPI)
    provider=object.__new__(login.NativePasswordLogin)
    provider.store=store;provider.config=login.parse_config(raw)
    provider.failed=False;provider.unknown_native=[]
    app=mount_workspace(create_app(store),provider.unlock,58761,tuple((n,n) for n in login.ACCOUNTS))
    with TestClient(app,base_url='http://127.0.0.1:58761',client=('127.0.0.1',12345)) as client:
        headers={'Origin':'http://127.0.0.1:58761'}
        assert client.get('/').text.count('<option value="prep-specialist-fixture-')==3
        assert client.get('/').headers['cache-control']=='no-store'
        for name in login.ACCOUNTS:
            result=client.post('/api/local/session',headers=headers,json=dict(role=name,password=passwords[name]))
            assert result.status_code==200,result.text
            assert result.json()['actor']==login.actor_for(name)
            assert result.json()['installation_id']==installation
        result=client.post('/api/local/session',headers=headers,json=dict(role='fixture-a',password=passwords['prep-specialist-fixture-a']))
        assert result.status_code==403 and passwords['prep-specialist-fixture-a'] not in result.text
        assert client.post('/api/local/session',json=dict(role='fixture-a',password=passwords['fixture-a'])).status_code==403
        result=client.post('/api/local/session',headers=headers,json=dict(role='fixture-a',password=passwords['fixture-a'],extra='PRIVATE_TEST_VALUE'))
        assert result.status_code==422 and 'PRIVATE_TEST_VALUE' not in result.text
        with owner.connect() as connection:connection.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
        assert client.post('/api/local/session',headers=headers,json=dict(role='fixture-a',password=passwords['fixture-a'])).status_code==403
    env=(('PARKWEAVE_DSN','host=127.0.0.1 port=55432 user=parkweave_app dbname=parkweave sslmode=disable'),
         ('PARKWEAVE_MODE','LOCAL'),('PARKWEAVE_FILE_ROOT',r'C:\private\instance\files'),(login.ENVIRONMENT,raw))
    args=('-I','-B','-m','uvicorn','scripts.windows_portable.native_web_login:configured_app',
          '--factory','--host','127.0.0.1','--port','58761','--no-access-log')
    command=Command('runtime/python/python.exe','a'*64,1,args,'WINDOWS_JOB','NONE',env)
    assert raw not in repr(command) and not any(token in raw for token in tokens.values())
    with pytest.raises(ProcessRefused):Command('runtime/python/python.exe','a'*64,1,(), 'WINDOWS_JOB','NONE',env)
    with pytest.raises(ProcessRefused):Command('runtime/python/python.exe','a'*64,1,args,'WINDOWS_JOB','WORKER_READINESS_V1',env)
    calls=[]
    class UncertainDPAPI:
        def unprotect(self,*args):
            calls.append(self)
            raise dpapi.NativeFailure('COPY','ProtectionRefused',['NATIVE_DPAPI_FREE_UNKNOWN'])
    monkeypatch.setattr(dpapi,'_NativeDPAPI',UncertainDPAPI)
    with pytest.raises(RuntimeError):provider.unlock('fixture-b',passwords['fixture-b'])
    with pytest.raises(Denied):provider.unlock('fixture-b',passwords['fixture-b'])
    assert len(calls)==1 and provider.unknown_native==calls


def test_actual_factory_bridges_only_original_provider():
    from scripts.windows_portable.native_composition import compose_native_local_preparation
    from scripts.windows_portable.endpoint_plan import PlanMode,EndpointRequest
    value=compose_native_local_preparation(base=r'C:\private',mode=PlanMode.NEW,request=EndpointRequest(55432,58761),
        runtime=dict(source_commit='a'*40,manifest_sha256='b'*64),initdb_sha256='c'*64,initdb_size=1,
        postgres_sha256='d'*64,postgres_size=1,python_sha256='e'*64,python_size=1,challenge='f'*32)
    assert value.processes.session_provider is value.security.provider
    assert value.processes.endpoint_source is value.security.security
    from scripts.windows import lifecycle
    with pytest.raises(lifecycle.BoundaryError):login.prompt_enrollment()
