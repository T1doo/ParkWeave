"""Single-use reservation/clock protocol only, no native authority or IO."""
import time
import threading
from types import SimpleNamespace

import pytest

from scripts.windows_portable import preparation_business_trial as business,local_preparation as local
from scripts.windows_portable.controller import CandidateRefused


def test_startup_does_not_consume_business_clock_and_reopen_cannot_renew(monkeypatch):
    clock=[1000.]
    monkeypatch.setattr(business,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    trial=business.PreparationBusinessTrial(seconds=180)
    trial.reserve();assert trial.state=='RESERVED' and trial.deadline is None
    clock[0]+=400  # Startup consumes only its separate source window.
    assert trial.start_business(1900)==1580
    original=trial.deadline
    for action in (trial.reserve,trial.begin,lambda:trial.start_business(2000)):
        with pytest.raises(CandidateRefused):action()
    assert trial.deadline==original
    clock[0]=1570
    # A fresh scenario's business clock is still clamped to its original total.
    another=business.PreparationBusinessTrial();another.reserve()
    assert another.start_business(1575)==1575


@pytest.mark.parametrize('invalid',[True,float('nan'),float('inf'),-1])
def test_invalid_absolute_limit_issues_no_business_clock(invalid):
    trial=business.PreparationBusinessTrial();trial.reserve()
    with pytest.raises(CandidateRefused):trial.start_business(invalid)
    assert trial.deadline is None


def test_workspace_and_both_clients_only_tighten_existing_limit():
    workspace=object.__new__(local.PreparationWorkspace)
    workspace._active=True;workspace._check=lambda:None;workspace.deadline=None
    owner=local.PreparationClient(workspace,object())
    reviewer=local.PreparationClient(workspace,object())
    now=time.monotonic();first=now+60
    assert workspace.limit_deadline(first)==first
    assert workspace.limit_deadline(now+120)==first
    assert workspace.limit_deadline(now+30)==now+30
    assert owner.workspace.deadline==reviewer.workspace.deadline==now+30
    workspace.deadline=now-1
    with pytest.raises(CandidateRefused):workspace.limit_deadline(now+120)
    workspace.deadline=None;workspace.close()
    with pytest.raises(CandidateRefused):workspace.limit_deadline(now+120)


def test_bound_adapter_reserves_before_startup_and_starts_clock_at_first_callback(monkeypatch):
    from scripts.windows_portable import native_business_adapter as adapter,native_trial_authority as authority
    clock=[1000.];fake_time=SimpleNamespace(monotonic=lambda:clock[0])
    for module in (business,local,adapter):monkeypatch.setattr(module,'time',fake_time)
    state=SimpleNamespace(deadline=1900.)
    controller=object();calls=[]
    monkeypatch.setattr(authority,'require_owner',lambda resource:calls.append('owner boundary'))
    monkeypatch.setattr(authority,'bound_state',lambda resource:state if resource is controller else None)
    value=object.__new__(adapter.NativeBusinessTestAdapter)
    value.started=False;value._entry_lock=threading.Lock();value.root='not-opened'
    value.trial=business.PreparationBusinessTrial(seconds=180)
    workspace=object.__new__(local.PreparationWorkspace)
    workspace.deadline=None;workspace._active=True;workspace._check=lambda:None
    class StopBeforeBusinessIO(RuntimeError):pass
    def before_business(original):
        assert original is workspace and original.deadline==value.trial.deadline==1580.
        calls.append('business clock installed')
        raise StopBeforeBusinessIO()
    # This controlled adapter boundary stops BEFORE any HTTP/OS action or
    # acceptance. The actual HTTP scenario is covered in the integration test.
    value.trial.create=before_business
    def startup(root,callback,*,deadline):
        assert deadline is None and value.trial.state=='RESERVED' and value.trial.deadline is None
        calls.append('startup');clock[0]+=400;callback(workspace)
    value.first=SimpleNamespace(controller=controller,create=startup)
    with pytest.raises(StopBeforeBusinessIO):value.run()
    assert calls==['owner boundary','startup','business clock installed']
    with pytest.raises(CandidateRefused):value.run()
    assert calls.count('startup')==1 and value.trial.deadline==1580.
