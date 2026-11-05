"""Original security budget handoff with controlled time, no OS/backend calls."""
from types import SimpleNamespace
import pytest
from scripts.windows_portable import native_instance_security as n
from scripts.windows_portable import native_protected_bootstrap as bootstrap
from scripts.windows_portable import native_trial_authority as authority
from scripts.windows_portable.controller import DatabaseInputs,CandidateRefused


def prepared(monkeypatch,cap=140):
    clock=[110.0];held=[False];calls=[]
    monkeypatch.setattr(n.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(authority,'budget',lambda resource,end,*a,**kw:min(end,cap))
    def under(lease,operation):
        assert not held[0];held[0]=True
        try:return operation()
        finally:held[0]=False
    monkeypatch.setattr(n,'_under_lease',under)
    value=object.__new__(n.NativeFixedStoreSecurity)
    value.failed=False;value.store=value.layout=None
    value.target=SimpleNamespace(deadline=105.0)
    value.inputs=DatabaseInputs('maintenance','owner','application','OWNED_DATA')
    value.mode=n.ep.PlanMode.NEW;value.plan=object()
    value._context=lambda lease:calls.append(('context',value.target.deadline))
    def path(lease,target):
        assert clock[0]<target.deadline;return 'OWNED_DATA'
    monkeypatch.setattr(n,'_path_held',path)
    monkeypatch.setattr(n.ep,'_record_held',lambda *a,**kw:None)
    def initialize(security,lease,inputs,specification,register,deadline):
        assert not held[0], 'public bootstrap cannot run under nested lease entry'
        calls.append(('bootstrap',deadline,security.target.deadline));return 'BOUNDARY_ONLY'
    monkeypatch.setattr(bootstrap,'initialize',initialize)
    return value,n.NativeClusterPrerequisites(value),calls


def test_previous_short_observation_deadline_is_rebound_to_existing_caller_budget(monkeypatch):
    value,prerequisites,calls=prepared(monkeypatch)
    assert prerequisites.initialize_protected(object(),value.inputs,object(),lambda t:None,132.0)=='BOUNDARY_ONLY'
    assert calls==[('context',132.0),('context',132.0),('bootstrap',132.0,132.0)]
    assert not value.failed


def test_source_budget_clamps_resource_deadline_without_a_fresh_window(monkeypatch):
    value,prerequisites,calls=prepared(monkeypatch,cap=125.0)
    prerequisites.initialize_protected(object(),value.inputs,object(),lambda t:None,132.0)
    assert calls[-1]==('bootstrap',132.0,125.0)


@pytest.mark.parametrize('end',[109.0,110.0,141.0])
def test_expired_or_unbounded_caller_never_reaches_bootstrap(monkeypatch,end):
    value,prerequisites,calls=prepared(monkeypatch,cap=200.0)
    with pytest.raises(CandidateRefused):prerequisites.initialize_protected(object(),value.inputs,object(),lambda t:None,end)
    assert value.failed and not calls


def test_same_inputs_identity_still_required_before_bootstrap(monkeypatch):
    value,prerequisites,calls=prepared(monkeypatch)
    other=DatabaseInputs('maintenance','owner','application','OWNED_DATA')
    with pytest.raises(CandidateRefused):prerequisites.initialize_protected(object(),other,object(),lambda t:None,132.0)
    assert value.failed and not any(row[0]=='bootstrap' for row in calls)


@pytest.mark.parametrize('probe_present',[False,True])
def test_nested_security_probe_shares_the_same_clamped_observation_budget(monkeypatch,probe_present):
    value,prerequisites,calls=prepared(monkeypatch,cap=125.0)
    value.store=SimpleNamespace(api=SimpleNamespace(deadline=105.0))
    value.layout=SimpleNamespace(deadline=105.0,probe=SimpleNamespace(deadline=105.0) if probe_present else None)
    def context(lease):
        deadlines=[value.target.deadline,value.store.api.deadline,value.layout.deadline]
        if probe_present:deadlines.append(value.layout.probe.deadline)
        assert all(end==125.0 for end in deadlines)
    value._context=context
    assert prerequisites.initialize_protected(object(),value.inputs,object(),lambda t:None,132.0)=='BOUNDARY_ONLY'
    assert calls==[('bootstrap',132.0,125.0)]
