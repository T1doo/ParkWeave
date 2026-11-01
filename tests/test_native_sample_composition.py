"""Native sample SOURCE and supported SQL/HTTP components only.

No native setters, DPAPI, enrollment, Windows processes or acceptance are run.
Controlled public/ciphertext data is never claimed as protected OS identity.
"""
from copy import deepcopy
import hashlib,json,secrets
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from parkweave import local_synthetic_demo as demo
from parkweave.local_workspace import mount_workspace
from parkweave.api import create_app
from parkweave.local_resource_approval import configure
from parkweave.store import Denied
from scripts.windows_portable import native_sample as sample,native_web_login as login
from scripts.windows_portable.local_preparation_identity import (
    ENTERPRISES,REVIEWERS,EXECUTOR,RESOURCE_ADMIN,PreparationIdentities,PreparationProfile,PreparationDatabaseOperations)
from scripts.windows_portable.controller import CandidateRefused


def identities(tokens):
    return PreparationIdentities.from_mapping({**{k:tokens[k] for k in ENTERPRISES},
        **{k:secrets.token_urlsafe(32) for k in (*REVIEWERS,EXECUTOR,RESOURCE_ADMIN)}},profile=PreparationProfile.SAMPLE)


def setup_components(fixture):
    store,owner,tokens,_=fixture;value=identities(tokens)
    owner.migrate_local_resource_approval_fixture()  # Original Linux issuer, not a native proof.
    with owner.connect() as c:sample.seed_sample_rows(c,value)
    with store.connect() as c:
        c.execute('SET TRANSACTION READ ONLY');raw=sample.public_inputs(c)
    return store,owner,value,raw


def test_profile_fixed_identity_set_and_actual_factory_remain_behind_original_owner_gate():
    from scripts.windows_portable.native_composition import compose_native_local_preparation
    from scripts.windows_portable.endpoint_plan import PlanMode,EndpointRequest
    from scripts.windows import lifecycle
    value=identities({k:'PUBLIC_CONTROLLED_ENTERPRISE_'+k for k in ENTERPRISES})
    assert len(value.mapping())==8 and set(value.enterprises())==set(ENTERPRISES)
    with pytest.raises(CandidateRefused):PreparationIdentities.from_mapping(value.mapping())
    with pytest.raises(CandidateRefused):PreparationIdentities.from_mapping({**value.mapping(),'other':'PUBLIC_TEST'})
    enrollment=login.NativeLoginEnrollment({n:'PUBLIC_TEST_PASSWORD_'+n for n in login.SAMPLE_ACCOUNTS},profile=PreparationProfile.SAMPLE)
    invocation=compose_native_local_preparation(base=r'C:\private',mode=PlanMode.NEW,request=EndpointRequest(55432,58761),
        runtime=dict(source_commit='a'*40,manifest_sha256='b'*64),initdb_sha256='c'*64,initdb_size=1,
        postgres_sha256='d'*64,postgres_size=1,python_sha256='e'*64,python_size=1,challenge='f'*64,
        enrollment=enrollment,profile=PreparationProfile.SAMPLE)
    assert invocation.security.provider.profile is invocation.controller.database.profile is PreparationProfile.SAMPLE
    with pytest.raises(lifecycle.BoundaryError):invocation.create(r'C:\private\new-sample',lambda w:None)
    assert invocation.security.provider._created is False


def test_actual_sample_rows_memory_catalog_roles_http_and_revoked_read(fixture):
    store,owner,value,raw=setup_components(fixture);values=value.mapping()
    # Native seed must still reject this actual Linux owner, before owner I/O.
    with pytest.raises(CandidateRefused):PreparationDatabaseOperations(profile=PreparationProfile.SAMPLE).seed(owner,value)
    steps=sample.dependencies(store,raw)
    app=create_app(store,local_synthetic_demo=steps.local_synthetic_demo,case_step_assignments=steps,local_resource_approval=configure(store,'CURRENT_OWNER'))
    workspace=sample.NativeSampleWorkspace(store,raw)
    def no_native_login(*args):raise Denied('native provider not executed on Linux')
    app=mount_workspace(app,no_native_login,58766,sample.LABELS,sample_workspace=workspace)
    with TestClient(app,base_url='http://127.0.0.1:58766') as client:
        assert 'id="local-sample-resource-panel"' in client.get('/').text
        admin={'Authorization':'Bearer '+values[RESOURCE_ADMIN]};owner_headers={'Authorization':'Bearer '+values['fixture-a']}
        response=client.get('/api/local-sample/resources',headers=admin)
        assert response.status_code==200 and len(response.json()['items'])==2
        assert response.json()['hold_allowed'] is response.json()['publish_allowed'] is False
        assert client.get('/api/local-sample/resources',headers=owner_headers).status_code==403
        assert len(client.get('/api/synthetic-resources',headers=owner_headers).json()['items'])==2
        assert client.get('/api/synthetic-resources',headers=admin).status_code==403
        assert client.get('/api/preparations',headers=admin).status_code==403
        owner.revoke_capability(RESOURCE_ADMIN,'READ')
        assert client.get('/api/local-sample/resources',headers=admin).status_code==403
    original=demo.NativeDemoInputs.parse(raw);metadata,pack,journal=original.values()
    assert isinstance(original.pack_bytes,bytes) and set(pack['roles'])=={'enterprise_operator','park_specialist','service_executor'}
    changed=json.loads(raw);changed['journal']['org_id']='other';changed['metadata']['journal_sha256']=demo.contract.digest(changed['journal'])
    with pytest.raises(Denied):sample.validate_public(demo.contract.canonical(changed))
    changed=json.loads(raw);changed['pack']['roles']['service_executor']='some-other-executor';changed['metadata']['pack_sha256']=demo.contract.digest(changed['pack'])
    with pytest.raises(Denied):sample.validate_public(demo.contract.canonical(changed))


def test_native_password_source_uses_original_dpapi_and_exact_four_account_scope(fixture,monkeypatch):
    from scripts.windows_portable import dpapi_native_candidate as native,credential_envelope as e
    store,owner,value,raw=setup_components(fixture);values=value.mapping();installation='a'*64;salt=bytes(range(32))
    passwords={n:'PUBLIC_TEST_PASSWORD_'+n for n in login.SAMPLE_ACCOUNTS}
    expected={n:login.entropy(passwords[n],salt,installation,n,PreparationProfile.SAMPLE) for n in passwords}
    cfg=dict(schema=login.SAMPLE_SCHEMA,profile=PreparationProfile.SAMPLE.value,installation=installation,port=58766,
        sample=raw,sample_sha256=hashlib.sha256(raw.encode()).hexdigest(),accounts={})
    import base64
    for n in passwords:cfg['accounts'][n]=dict(actor=login.actor_for(n,PreparationProfile.SAMPLE),token_sha256=hashlib.sha256(values[n].encode()).hexdigest(),salt=salt.hex(),ciphertext=base64.b64encode(n.encode()).decode())
    assert len(login.parse_config(e.canonical(cfg).decode())['accounts'])==4
    with pytest.raises(Denied):login.NativePasswordLogin(store,e.canonical(cfg).decode())
    class ControlledDPAPI:
        def unprotect(self,cipher,entropy):
            n=cipher.decode()
            if entropy!=expected[n]:raise native.NativeFailure('ALLOCATION','ProtectionRefused',[],13)
            return e.canonical(dict(schema=login.SAMPLE_SCHEMA,installation=installation,actor=login.actor_for(n,PreparationProfile.SAMPLE),bearer=values[n]))
    monkeypatch.setattr(native,'_NativeDPAPI',ControlledDPAPI)
    provider=object.__new__(login.NativePasswordLogin);provider.store=store;provider.config=cfg;provider.failed=False;provider.unknown_native=[]
    for n in passwords:assert provider.unlock(n,passwords[n])['actor']==login.actor_for(n,PreparationProfile.SAMPLE)
    with pytest.raises(Denied):provider.unlock(EXECUTOR,passwords['fixture-a'])
    with pytest.raises(Denied):provider.unlock('fixture-b',passwords['fixture-a'])
    with owner.connect() as c:c.execute('UPDATE principals SET active=false WHERE id=%s',(EXECUTOR,))
    with pytest.raises(Denied):provider.unlock(EXECUTOR,passwords[EXECUTOR])
    cfg['profile']='MATERIAL'
    with pytest.raises(Exception):login.parse_config(e.canonical(cfg).decode())


def test_native_seed_sql_consumer_rollback_preserves_original_rows(fixture):
    _,owner,tokens,_=fixture;value=identities(tokens)
    with pytest.raises(RuntimeError):
        with owner.connect() as c:
            sample.seed_sample_rows(c,value)
            raise RuntimeError('CONTROLLED_TRANSACTION_ABORT')
    with owner.connect() as c:
        assert c.execute('SELECT count(*) n FROM principals').fetchone()['n']==3
        assert c.execute('SELECT count(*) n FROM synthetic_resources').fetchone()['n']==0


def command_public(raw,port=55432):
    # Explicit public protocol fixture, not observed native database evidence.
    x=json.loads(raw);database=dict(name='parkweave',oid=123,address='127.0.0.1',port=port,user='parkweave_app')
    x['metadata']['database']=database;x['journal']['database']=database
    x['metadata']['journal_sha256']=demo.contract.digest(x['journal'])
    return demo.contract.canonical(x)


def test_fixed_native_child_commands_bind_sample_public_inputs_without_login_to_worker(fixture):
    from scripts.windows_portable.processes import Command,ProcessRefused
    from scripts.windows_portable.instance_processes import InstanceProcesses
    _,_,_,original=setup_components(fixture);raw=command_public(original)
    env=(('PARKWEAVE_DSN','host=127.0.0.1 port=55432 dbname=parkweave user=parkweave_app password=PUBLIC_PROTOCOL_ONLY sslmode=disable'),
        ('PARKWEAVE_MODE','LOCAL'),('PARKWEAVE_FILE_ROOT',r'C:\private\files'),(sample.ENVIRONMENT,raw))
    arguments=('-I','-B','-m','parkweave.worker','--readiness-stdio','--readiness-challenge','a'*64)
    value=Command('runtime/python/python.exe','a'*64,123,arguments,'WINDOWS_JOB','WORKER_READINESS_V1',env)
    assert dict(value.environment)[sample.ENVIRONMENT]==raw
    for changed in (env[:-1]+((sample.ENVIRONMENT,command_public(original,55433)),),env+(('UNTRUSTED','x'),)):
        with pytest.raises((ProcessRefused,Denied)):Command('runtime/python/python.exe','a'*64,123,arguments,'WINDOWS_JOB','WORKER_READINESS_V1',changed)
    with pytest.raises(ProcessRefused):Command('runtime/python/python.exe','a'*64,123,('-c','print(1)'), 'WINDOWS_JOB','WORKER_READINESS_V1',env)
    from parkweave.case_step_assignments import from_environment
    with pytest.raises(Denied):from_environment(None,{sample.ENVIRONMENT:raw})  # No native worker on Linux.


def test_bridge_and_entry_forward_explicit_mode_without_native_or_credential_execution(tmp_path,monkeypatch):
    import io
    from scripts.windows_portable import desktop_bridge,entry
    value=dict(action='reopen',instance=str(tmp_path),database_port=0,api_port=0,passwords={},initialize_profile=False,sample_collaboration=True)
    assert desktop_bridge.request(io.BytesIO((json.dumps(value)+'\n').encode()))['sample_collaboration'] is True
    with pytest.raises(ValueError):desktop_bridge.request(io.BytesIO((json.dumps({**value,'sample_collaboration':1})+'\n').encode()))
    calls=[]
    class Invocation:
        def reopen(self,path,callback):calls.append(('reopen',path));return dict(scope='CONTROLLED_ENTRY_ONLY')
    def compose(root,manifest,instance,mode,**kw):calls.append(kw);return Invocation()
    monkeypatch.setattr(entry,'verified_payload',lambda:(tmp_path,{},b'{}'))
    monkeypatch.setattr(entry,'native_invocation',compose)
    assert entry.main(['--action','reopen','--instance',str(tmp_path),'--sample-collaboration'])==0
    assert calls[0]['sample_collaboration'] is True and calls[0]['enrollment'] is None
    # No new install or native callback occurred; this is argv/mode forwarding.


def test_portable_source_allowlist_contains_real_sample_module_and_no_linux_vault_dependency():
    from scripts.windows_portable.build import RUNTIME_SOURCES
    assert 'scripts/windows_portable/native_sample.py' in RUNTIME_SOURCES
    import ast
    tree=ast.parse(Path('scripts/windows_portable/native_sample.py').read_text())
    imported=[n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
    assert 'parkweave.local_identity' not in imported and 'parkweave.local_sample' not in imported


@pytest.mark.parametrize('profile',list(PreparationProfile))
def test_reopen_discovers_protected_profile_once_without_checkbox_entropy_or_reseed(profile,monkeypatch):
    # Pure reader protocol. The injected plaintext is NOT native DPAPI evidence.
    from types import SimpleNamespace
    from scripts.windows_portable.native_preparation_sessions import NativePreparationSessionProvider,PreparationFile
    from scripts.windows_portable.endpoint_plan import PlanMode
    from scripts.windows_portable import credential_envelope as envelope
    from scripts.windows_portable.local_preparation_identity import identity_names
    values={n:'PUBLIC_PROTOCOL_'+n for n in identity_names(profile)}
    provider=NativePreparationSessionProvider()
    provider.database=PreparationDatabaseOperations()
    provider.security=SimpleNamespace(mode=PlanMode.REOPEN,state=SimpleNamespace(sessions={n:values[n] for n in ENTERPRISES}))
    store=SimpleNamespace(binding=SimpleNamespace(record=lambda:{'PUBLIC':'INSTALLATION'}),runtime=b'{"PUBLIC":"RUNTIME"}')
    aad=provider._aad(store,PreparationFile.IDENTITIES)
    assert aad==dict(schema='parkweave-native-preparation-identities/1',installation={'PUBLIC':'INSTALLATION'},runtime={'PUBLIC':'RUNTIME'},purpose='IDENTITIES')
    reads=[]
    monkeypatch.setattr(provider,'_operation',lambda lease,operation:operation(store))
    def read(original,kind):
        assert original is store and kind is PreparationFile.IDENTITIES
        reads.append(kind);return values
    monkeypatch.setattr(provider,'_file',read)
    assert provider.load_existing(object()).mapping()==values
    assert reads==[PreparationFile.IDENTITIES]
    assert provider.profile is provider.database.profile is profile
    assert envelope.canonical(provider._aad(store,PreparationFile.IDENTITIES))==envelope.canonical(aad)
    assert provider._created is False and provider.enrollment is None
    with pytest.raises(CandidateRefused):provider.load_existing(object())
    assert len(reads)==1


def test_reopen_rejects_missing_identity_or_wrong_original_session_without_second_read(monkeypatch):
    from types import SimpleNamespace
    from scripts.windows_portable.native_preparation_sessions import NativePreparationSessionProvider
    from scripts.windows_portable.endpoint_plan import PlanMode
    from scripts.windows_portable.local_preparation_identity import identity_names
    original={n:'PUBLIC_PROTOCOL_'+n for n in identity_names(PreparationProfile.SAMPLE)}
    for values,sessions in (({k:v for k,v in original.items() if k!=EXECUTOR},{n:original[n] for n in ENTERPRISES}),
                            (original,{n:'DIFFERENT_'+n for n in ENTERPRISES})):
        provider=NativePreparationSessionProvider();provider.database=PreparationDatabaseOperations()
        provider.security=SimpleNamespace(mode=PlanMode.REOPEN,state=SimpleNamespace(sessions=sessions))
        reads=[]
        monkeypatch.setattr(provider,'_operation',lambda lease,operation:operation(None))
        monkeypatch.setattr(provider,'_file',lambda store,kind:reads.append(kind) or values)
        with pytest.raises(CandidateRefused):provider.load_existing(object())
        assert len(reads)==1 and provider._identities is None and not provider._created
        assert provider.profile is provider.database.profile is PreparationProfile.MATERIAL
