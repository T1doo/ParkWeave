"""Independent cold-entry ownership/history probes on actual owned Linux PG."""
from uuid import uuid4
import pytest
from parkweave.store import Denied
from test_preparation import preparation_fixture, headers
from test_service_capability_catalog_actual import capability_catalog
from test_service_instance_consumer import setup, stage
from service_release_acceptance_support import authority_snapshot

@pytest.mark.parametrize('capability',['EXECUTE','PREPARE','case.create'])
def test_read_history_survives_write_authority_revocation(capability_catalog,tmp_path,monkeypatch,capability):
    a=capability_catalog
    facade,data=setup(a,tmp_path)
    store,owner,tokens,api=a['f']
    key=uuid4().hex
    original=facade.prepare(tokens['fixture-c'],key,data)
    command=stage(original,'CREATE_RUN')
    response=api.post('/api/runs',headers=headers(tokens,'fixture-c',command['request_key']),json=command['body'])
    assert response.status_code==202,response.text
    with owner.connect() as c:
        owner.lock_principal(c,'fixture-c',exclusive=True)
        if capability=='PREPARE':
            c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-c' AND capability='PREPARE'")
        elif capability=='case.create':
            c.execute("UPDATE action_grants SET active=false WHERE principal_id='fixture-c' AND action='case.create'")
        else:
            c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-c' AND capability='EXECUTE'")
    authority=authority_snapshot(owner)
    def forbidden(*args,**kwargs):raise AssertionError('historical recovery acquired source writer lease')
    monkeypatch.setattr(a['catalog'],'source_lease',forbidden)
    recovered=facade.read(tokens['fixture-c'],key)
    assert recovered['input']==original['input']
    assert recovered['product_observations'][0]['status']=='COMMITTED'
    assert recovered['product_observations'][0]['result']['run_state']=='QUEUED'
    assert recovered['automatic_execution'] is False
    assert authority_snapshot(owner)==authority
    with pytest.raises(Denied):facade.prepare(tokens['fixture-c'],key,data)
