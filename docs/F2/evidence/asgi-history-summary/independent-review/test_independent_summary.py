"""Independent in-process probes; isolated synthetic PG fixture only."""
from dataclasses import replace
from uuid import UUID, uuid4
import json
import pytest
from fastapi.testclient import TestClient
from parkweave import history_summary as hs, case_fact_clarifications as facts, resource_combinations
from parkweave.api import create_app
from test_preparation import preparation_fixture, headers, filled
from test_fact_history_read_source_store import selected, memory_reader, snapshot

def url(p, stage='P4', case=None):
    return f"/api/cases/{case or p['case_id']}/preparations/{p['preparation_id']}/history-summary/{stage}"

def unchanged_except_audit(f, before, delta):
    after = snapshot(f)
    assert len(after.pop('authorization_audit')) == len(before['authorization_audit']) + delta
    assert after == {k:v for k,v in before.items() if k != 'authorization_audit'}

@pytest.mark.parametrize('stage', ['P4', 'P5'])
def test_success_fixed_shape_read_only(preparation_fixture, stage):
    f = preparation_fixture; p = selected(f); reader = memory_reader(f,p,stage)
    before = snapshot(f)
    with TestClient(create_app(f[0],summary_reader=reader)) as client:
        response = client.get(url(p,stage),headers=headers(f[2]))
    assert response.status_code == 200,response.text
    result = response.json()
    assert set(result) == {'scope','namespace','preparation_id','history','summary_only','read_only',
        'execution_available','execution_qualification','automatically_replayed','formal_writes',
        'new_grants','case_goal_completed','source_atomicity','source_consistency','case_id','stage'}
    assert result['stage'] == stage and result['case_id'] == p['case_id']
    assert result['execution_available'] is False and result['new_grants'] is False
    assert result['formal_writes'] == 0 and result['execution_qualification'] == 'NOT_EVALUATED'
    assert response.headers['cache-control'] == 'no-store'
    for private in ('proof','source_excerpt','source_snapshot','地区甲','fact_clarifications'):
        assert private not in json.dumps(result,ensure_ascii=False)
    unchanged_except_audit(f,before,0)

@pytest.mark.parametrize('field', facts.FIELDS)
def test_each_field_read_precedes_private_access(preparation_fixture,monkeypatch,field):
    f = preparation_fixture; p = selected(f); reader = memory_reader(f,p,'P4')
    f[1].revoke_field('fixture-a',field,'READ')
    def forbidden(*args,**kwargs):
        raise AssertionError('private/history data touched before current field READ')
    monkeypatch.setattr(f[0],'facts_query',forbidden)
    monkeypatch.setattr(reader,'_rows',forbidden)
    before = snapshot(f)
    with TestClient(create_app(f[0],summary_reader=reader)) as client:
        response = client.get(url(p),headers=headers(f[2]))
    assert response.status_code == 403,response.text
    unchanged_except_audit(f,before,1)

def test_wrong_case_precedes_private_sources_and_memory(preparation_fixture,monkeypatch):
    f = preparation_fixture; p = selected(f); reader = memory_reader(f,p,'P4')
    def forbidden(*args,**kwargs):
        raise AssertionError('wrong Case accessed private/history data')
    monkeypatch.setattr(f[0],'facts_query',forbidden)
    monkeypatch.setattr(reader,'_rows',forbidden)
    monkeypatch.setattr(hs,'summaries',forbidden)
    before = snapshot(f)
    with TestClient(create_app(f[0],summary_reader=reader)) as client:
        response = client.get(url(p,case=uuid4()),headers=headers(f[2]))
    assert response.status_code == 403,response.text
    unchanged_except_audit(f,before,1)

@pytest.mark.parametrize('change',['baseline_expiry','capability','source_expiry'])
def test_final_guard_checks_validity_after_projection(preparation_fixture,monkeypatch,change):
    f = preparation_fixture; p = selected(f); reader = memory_reader(f,p,'P5'); original = hs.summaries
    def project_then_change(*args,**kwargs):
        result = original(*args,**kwargs)
        if change == 'baseline_expiry':
            with f[1].connect() as c:
                now = c.execute('SELECT clock_timestamp() now').fetchone()['now']
            reader.baselines[p['preparation_id']] = replace(reader.baselines[p['preparation_id']],valid_until=now)
        else:
            with f[1].connect() as c:
                if change == 'capability':
                    c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
                else:
                    c.execute("UPDATE fact_assertions SET valid_until=clock_timestamp() WHERE field_name='region'")
        return result
    monkeypatch.setattr(hs,'summaries',project_then_change)
    with TestClient(create_app(f[0],summary_reader=reader)) as client:
        response = client.get(url(p,'P5'),headers=headers(f[2]))
    assert response.status_code == 403,response.text

def test_default_none_ignores_request_and_store_registration(preparation_fixture,monkeypatch):
    f = preparation_fixture; p = selected(f); reader = memory_reader(f,p,'P4')
    f[0].summary_reader = reader
    monkeypatch.setenv('PARKWEAVE_SUMMARY_READER','P4')
    before = snapshot(f)
    with TestClient(create_app(f[0])) as client:
        response = client.get(url(p),headers=headers(f[2]),params={'summary_reader':'P4'})
    assert response.status_code == 403,response.text
    unchanged_except_audit(f,before,1)

def test_route_stage_cannot_change_between_api_check_and_reader_capture(preparation_fixture,monkeypatch):
    f = preparation_fixture; p = selected(f)
    reader = memory_reader(f,p,'P4'); other = memory_reader(f,p,'P5'); original = reader.read_case
    def change_before_reader(*args,**kwargs):
        reader.stage = other.stage
        reader.baselines = other.baselines
        reader.records = other.records
        return original(*args,**kwargs)
    monkeypatch.setattr(reader,'read_case',change_before_reader)
    with TestClient(create_app(f[0],summary_reader=reader)) as client:
        response = client.get(url(p,'P4'),headers=headers(f[2]))
    assert response.status_code == 403, 'P4 route returned '+response.text

def test_undeclared_lawful_source_change_is_stale_not_authority(preparation_fixture):
    f = preparation_fixture; resource_combinations.seed_synthetic(f[1]); p = filled(f)
    reader = memory_reader(f,p,'P4')
    with f[1].connect() as c:
        c.execute('UPDATE preparations SET revision=revision+1 WHERE id=%s',(UUID(p['preparation_id']),))
    before = snapshot(f)
    with TestClient(create_app(f[0],summary_reader=reader)) as client:
        response = client.get(url(p),headers=headers(f[2]))
    assert response.status_code == 200,response.text
    assert response.json()['history'][0]['source_state'] == 'STALE'
    assert response.json()['execution_available'] is False
    unchanged_except_audit(f,before,0)
