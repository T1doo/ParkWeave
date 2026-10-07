"""Actual existing authorities cannot silently become rule publication rights.
Uses standard isolated synthetic fixtures, never the preserved product database.
"""
import pytest
from psycopg.errors import InsufficientPrivilege
from test_preparation import preparation_fixture,filled,command,headers
from test_v1_contracts import service

def snapshot(f):
    with f[1].connect() as c:
        return {t:c.execute('SELECT * FROM '+t+' ORDER BY 1').fetchall() for t in ('preparation_catalog','preparation_grants','capability_grants','run_assignments','preparations','preparation_events')}

def test_existing_application_cannot_write_trusted_service_catalog(preparation_fixture):
    f=preparation_fixture;before=snapshot(f)
    with f[0].connect() as c:
        assert c.execute("SELECT count(*) n FROM preparation_catalog").fetchone()['n']>0
        assert not c.execute("SELECT has_table_privilege(current_user,'preparation_catalog','UPDATE') allowed").fetchone()['allowed']
    # Exercise a real denied write, rather than infer policy from roles.sql text.
    with pytest.raises(InsufficientPrivilege):
        with f[0].connect() as c:c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{publication}','\"PUBLISHED\"')")
    assert snapshot(f)==before

@pytest.mark.parametrize('user',['fixture-a','prep-specialist-fixture-a'])
def test_claimed_review_metadata_validates_without_publication_or_authority_mutation(preparation_fixture,user):
    f=preparation_fixture;before=snapshot(f)
    payload=service();payload['reviewer_id']='prep-specialist-fixture-a'
    response=f[3].post('/api/contracts/service',headers=headers(f[2],user),json=payload)
    assert response.status_code==200 and response.json()['published'] is False
    assert response.json()['validation_scope']=='STRUCTURE_ONLY' and snapshot(f)==before

def test_assigned_material_review_does_not_publish_rules(preparation_fixture):
    f=preparation_fixture;p=filled(f);before=snapshot(f)
    p=command(f,p,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC material review only').json()
    view=f[3].get('/api/preparations/'+p['preparation_id']+'/readiness',headers=headers(f[2])).json()
    assert view['current_inputs']['local_preparation_truth']=='TRUE'
    assert view['current_inputs']['qualification_truth']=='UNKNOWN' and not view['business_publication']
    assert view['sources']['rule']['publication_status']=='DRAFT'
    after=snapshot(f)
    for table in ('preparation_catalog','preparation_grants','capability_grants','run_assignments'):assert after[table]==before[table]
