"""Ordinary default Store construction boundary; connector sentinel only, no PG."""
from types import SimpleNamespace
import pytest
from parkweave import native_run_access_restricted_runtime as runtime
from parkweave import native_run_access_preflight as preflight
from parkweave.store import Denied
from test_native_run_access_restricted_adapter import adapter_inputs


def test_default_store_rejects_ducktyped_guard_before_default_connector(monkeypatch):
    spec,_,_,private=adapter_inputs();calls=[]
    def sentinel(*args,**kwargs):
        calls.append('default-connector-route')
        raise Denied('SYNTHETIC connector sentinel; no PG connection occurred')
    monkeypatch.setattr(runtime._RestrictedConnection,'connect',sentinel)
    guard=SimpleNamespace(spec=preflight.InstallationSpec.model_validate(spec),
        require_live_host=lambda:None,host_check=lambda:None)
    with pytest.raises(Denied):
        runtime.RestrictedStore(private['writer_dsn'],guard).connect()
    assert calls==[], 'unissued ducktyped guard reached default connector'
