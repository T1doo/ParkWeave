"""Default backend authorization check with no real backend/private input access."""
import pytest
from parkweave import native_run_access_restricted_runtime as runtime
from parkweave.store import Denied
from test_native_run_access_restricted_adapter import adapter_inputs


def test_default_real_backend_is_unreachable_with_unissued_host_callable(monkeypatch):
    spec,_,layout,private=adapter_inputs();calls=[]
    def backend(*args,**kwargs):
        calls.append('default-real-backend-route')
        raise Denied('SYNTHETIC backend sentinel; no connection occurred')
    monkeypatch.setattr(runtime,'RestrictedStore',backend)
    with pytest.raises(Denied):
        engine=runtime.RestrictedEngine(spec,private,layout['boot_id'],lambda:None)
        engine.execute({'operation':'VALIDATE','nonce':'a'*32,'run_id':spec['policy']['source']['run_id']},True)
    assert calls==[], 'unissued host callback reached default real backend constructor'
