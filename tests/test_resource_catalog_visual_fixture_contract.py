"""Exact regression for the original page's read-only identity status request."""
import json
import pytest
from scripts import resource_catalog_feedback_browser_once as driver


def test_original_identity_status_is_closed_and_exactly_bounded(monkeypatch):
    monkeypatch.setattr(driver,'FIXTURE_READS',{})
    monkeypatch.setattr(driver,'REPORT',{'unexpected_GET':[]})
    route='/api/run-access/status'
    assert driver.FIXTURE_LIMITS[route]==4
    assert sum(driver.FIXTURE_LIMITS.values())==25
    for _ in range(4):
        status,kind,body=driver.fixture_response(route)
        assert status==200 and kind=='application/json'
        assert json.loads(body)==dict(enabled=False,read_available=False,role=None,
            can_approve=False,can_revoke=False,actual_run_access=False,deployment_enabled=False)
    assert driver.fixture_response(route)[0]==404
    assert driver.REPORT['unexpected_GET']==[route]


@pytest.mark.parametrize('suffix',['?unexpected=1','/other'])
def test_identity_status_does_not_open_other_routes(monkeypatch,suffix):
    monkeypatch.setattr(driver,'FIXTURE_READS',{})
    monkeypatch.setattr(driver,'REPORT',{'unexpected_GET':[]})
    route='/api/run-access/status'+suffix
    assert driver.fixture_response(route)[0]==404
    assert driver.REPORT['unexpected_GET']==[route]
