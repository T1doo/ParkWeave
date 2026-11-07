"""Actual entry wiring with a captured factory; no native startup or credentials."""
from hashlib import sha256
import pytest
from scripts.windows_portable import entry,native_composition
from scripts.windows_portable.endpoint_plan import PlanMode


@pytest.mark.parametrize('source',[
    {'source_commit':'a'*40},
    {'source_commit':None,'source_snapshot_sha256':'b'*64},
])
def test_entry_preserves_exact_source_kind_to_native_factory(monkeypatch,tmp_path,source):
    monkeypatch.setattr(native_composition,'compose_native_local_preparation',lambda **kwargs:kwargs)
    manifest={**source,'files':{name:{'sha256':'c'*64,'bytes':100} for name in (
        'runtime/postgresql/bin/initdb.exe','runtime/postgresql/bin/postgres.exe','runtime/python/python.exe')}}
    raw=b'synthetic frozen manifest bytes'
    value=entry.native_invocation(tmp_path,manifest,tmp_path/'instance',PlanMode.NEW,
        manifest_raw=raw,database_port=55432,api_port=8765)
    expected={k:v for k,v in source.items() if v is not None}
    assert value['runtime']=={**expected,'manifest_sha256':sha256(raw).hexdigest()}
    assert value['payload_source'].manifest==raw
    assert value['initdb_sha256']=='c'*64


def test_entry_rejects_ambiguous_source_before_factory(monkeypatch,tmp_path):
    called=[]
    monkeypatch.setattr(native_composition,'compose_native_local_preparation',lambda **kwargs:called.append(kwargs))
    manifest={'source_commit':'a'*40,'source_snapshot_sha256':'b'*64,'files':{name:{'sha256':'c'*64,'bytes':100} for name in (
        'runtime/postgresql/bin/initdb.exe','runtime/postgresql/bin/postgres.exe','runtime/python/python.exe')}}
    with pytest.raises(ValueError,match='RUNTIME_SOURCE_IDENTITY'):
        entry.native_invocation(tmp_path,manifest,tmp_path/'instance',PlanMode.NEW,
            manifest_raw=b'synthetic',database_port=55432,api_port=8765)
    assert not called
