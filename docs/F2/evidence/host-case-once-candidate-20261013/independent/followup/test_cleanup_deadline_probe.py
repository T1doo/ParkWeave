"""Pure independent counterexample: expiry must stop further cleanup work."""
from types import SimpleNamespace
import pytest
from scripts.host_case_once import controller as c

def test_cleanup_deadline_is_not_swallowed_before_another_helper_close(monkeypatch):
 context=dict(root='/tmp/parkweave-trial-'+'1'*32,source_sha='2'*40)
 controller=c.Controller(context);first=SimpleNamespace(poll=lambda:0);second=SimpleNamespace(poll=lambda:0)
 controller.business=first;controller.client=second;controller.processes=[first,second];seen=[]
 timeout=getattr(c,'CleanupTimeout',TimeoutError)
 def close(p):
  seen.append(('close',id(p)))
  if p is first:raise timeout('synthetic cleanup deadline')
 monkeypatch.setattr(controller,'_close_owned',close)
 monkeypatch.setattr(controller,'_stop_owned',lambda *a:seen.append(('stop',id(a[0]))))
 monkeypatch.setattr(controller,'tool',lambda *a,**kw:pytest.fail('no identity action allowed in probe'))
 with pytest.raises(timeout,match='synthetic cleanup deadline'):controller.cleanup()
 assert ('close',id(second)) not in seen
