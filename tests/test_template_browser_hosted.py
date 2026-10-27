"""Admission/dispatch only; no network, browser, PG, credentials or watchdog."""
from types import SimpleNamespace
import pytest
from scripts import template_browser_hosted as m


def environment():
    return dict(GITHUB_REPOSITORY='T1doo/ParkWeave',GITHUB_REF=m.REF,GITHUB_EVENT_NAME='push',GITHUB_RUN_ATTEMPT='1',GITHUB_RUN_NUMBER='49',RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Linux',PW_PUBLIC='true',GITHUB_SHA='a'*40)


def test_exact_host_gate_and_disabled_contract(monkeypatch):
    calls=[]
    monkeypatch.setattr(m.activation,'regular_bytes',lambda *a:(b'{"invocation":"PW_HTTP_SYNTHETIC_ONLY"}',(1,2)))
    monkeypatch.setattr(m.activation,'load',lambda invocation,mode:SimpleNamespace(invocation=invocation))
    monkeypatch.setattr(m.activation,'verify_source',lambda *a:calls.append(a))
    assert m.gate(environment())==('a'*40,'PW_HTTP_SYNTHETIC_ONLY') and len(calls)==1
    for key in ('GITHUB_REPOSITORY','GITHUB_REF','GITHUB_EVENT_NAME','GITHUB_RUN_ATTEMPT','GITHUB_RUN_NUMBER','RUNNER_ENVIRONMENT','RUNNER_OS','PW_PUBLIC','GITHUB_SHA'):
        with pytest.raises(m.activation.Closed):m.gate({**environment(),key:'OTHER'})
    with pytest.raises(m.activation.Closed):m.gate({**environment(),'PARKWEAVE_SESSION':'SYNTHETIC'})
    def disabled(*a):raise m.activation.Closed('window closed')
    monkeypatch.setattr(m.activation,'load',disabled)
    with pytest.raises(m.activation.Closed):m.gate(environment())
    assert len(calls)==1


def test_prepare_never_falls_back_or_consumes_when_chrome_missing(monkeypatch,tmp_path):
    monkeypatch.setattr(m,'gate',lambda env:('a'*40,'PW_HTTP_SYNTHETIC_ONLY'))
    monkeypatch.setattr(m.client,'CHROME',tmp_path/'missing')
    monkeypatch.setattr(m,'stage_asset',lambda *a:pytest.fail('download before Chrome admission'))
    with pytest.raises(FileNotFoundError):m.prepare({})


def test_execute_rechecks_source_and_only_dispatches_fixed_browser_mode(monkeypatch):
    import scripts.template_upgrade_http_once as integration
    monkeypatch.setattr(m,'gate',lambda env:('a'*40,'PW_HTTP_SYNTHETIC_ONLY'))
    calls=[]
    monkeypatch.setattr(integration,'main',lambda *a,**kw:calls.append((a,kw)) or 7)
    assert m.main(['execute'])==7
    assert calls==[((['--source','a'*40,'--invocation','PW_HTTP_SYNTHETIC_ONLY'],),{'mode':'BROWSER'})]
    assert m.main(['other'])==1 and len(calls)==1
