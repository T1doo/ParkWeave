"""Independent pure DI counterexamples; no OS/private FD/PG/start operations."""
from copy import deepcopy
from pathlib import Path
import stat
from types import SimpleNamespace
import pytest
from parkweave import native_run_access_restricted_host as host
from parkweave import native_run_access_restricted_runtime as runtime
from parkweave.store import Denied,_AccessConnection
from test_native_run_access_restricted_adapter import adapter_inputs


@pytest.mark.parametrize('suffix',['__pycache__/store.cpython-312.pyc','native_run_access_writer.cpython-312-x86_64-linux-gnu.so'])
def test_protected_source_rejects_unverified_executable_nodes(monkeypatch,suffix):
    _,_,data,_=adapter_inputs()
    layout=host.RuntimeLayout.model_validate(data)
    source=Path(next(iter(data['source_files'])))
    unsafe=Path(data['source_root']+'/parkweave/'+suffix)
    monkeypatch.setattr(host.Path,'rglob',lambda self,pattern:iter([source,unsafe]))
    def metadata(path):
        return SimpleNamespace(st_mode=stat.S_IFREG|(0o666 if path==unsafe else 0o444),st_uid=data['api_uid'] if path==unsafe else 0)
    monkeypatch.setattr(host.Path,'lstat',metadata)
    monkeypatch.setattr(host,'_protected_bytes',lambda *args,**kwargs:b'SYNTHETIC_CODE_BYTES')
    with pytest.raises(Denied):host._code_check(layout)


def test_cursor_first_sql_cannot_bypass_live_guard(monkeypatch):
    events=[]
    class Cursor:
        def execute(self,query,*args,**kwargs):events.append('backend:'+query);return self
    monkeypatch.setattr(_AccessConnection,'cursor',lambda *args,**kwargs:Cursor())
    connection=object.__new__(runtime._RestrictedConnection)
    connection._runtime_checked=connection._runtime_checking=False
    def denied(connection):events.append('guard');raise Denied('SYNTHETIC stale runtime')
    connection._restricted_runtime=SimpleNamespace(check=denied)
    with pytest.raises(Denied):connection.cursor().execute('UPDATE public.run_assignments SET active=true')
    assert events==['guard']


def test_unknown_host_identity_is_not_treated_as_existing(monkeypatch):
    spec,_,layout,_=adapter_inputs()
    import hashlib,hmac,json,pwd,grp,os
    from parkweave import native_run_access_writer as writer
    key=b'SYNTHETIC_FIXED_KEY_NOT_REAL______'[:32]
    def signed(payload):
        return json.dumps({'payload':payload,'hmac_sha256':hmac.new(key,writer._canonical(payload).encode(),hashlib.sha256).hexdigest()}).encode()
    policy=spec['policy']
    creation=dict(action='ORIGINAL_NEW_OWNED_DATABASE',database_name=policy['database_name'],database_oid=policy['database_oid'],system_identifier=policy['system_identifier'],owner=spec['installer_role'],trial_root=layout['trial_root'],absent_from_initial_databases=True,initial_databases=['postgres','template0','template1'])
    creation_raw=signed(creation)
    layout['creation_receipt_sha256']=hashlib.sha256(creation_raw).hexdigest()
    controller=host.LinuxHost(spec,layout)
    request=host.launch_request(spec,layout)
    def supplied(path,*args,**kwargs):
        if path==controller.layout.approval_key_path:return key
        if path==controller.layout.approval_path:return signed(request)
        if path==controller.layout.creation_path:return creation_raw
        pytest.fail('unapproved DI private path')
    monkeypatch.setattr(host,'_protected_bytes',supplied)
    monkeypatch.setattr(host,'_code_check',lambda *args:None)
    monkeypatch.setattr(host,'_dependencies_check',lambda *args:None)
    monkeypatch.setattr(os,'geteuid',lambda:0)
    monkeypatch.setattr(pwd,'getpwuid',lambda uid:(_ for _ in ()).throw(KeyError(uid)))
    monkeypatch.setattr(grp,'getgrgid',lambda gid:(_ for _ in ()).throw(KeyError(gid)))
    with pytest.raises(Denied):controller._approve(controller.layout.approval_path)


def test_restricted_runtime_default_does_not_issue_public_authority(monkeypatch):
    spec,_,layout,private=adapter_inputs()
    engine=runtime.RestrictedEngine(spec,private,layout['boot_id'],lambda:None,store_factory=lambda:pytest.fail('server boundary must deny before Store'))
    with pytest.raises(Denied):runtime.serve_restricted(engine,None)
    with pytest.raises(Denied):runtime.serve_restricted(engine,True)
    assert runtime.main([])==4
