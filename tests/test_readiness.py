"""Source-bound tri-state assessments on real PG and scoped application API."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from test_preparation import preparation_fixture,create,filled,add,command,headers,read as prep_read
from test_executor_receipts import receipt_fixture
from test_request_intents import save
from parkweave import preparation as prep
from parkweave.store import digest

def read(f,p,user='fixture-a'):
    return f[3].get('/api/preparations/'+p['preparation_id']+'/readiness',headers=headers(f[2],user))

def assess(f,p,user='fixture-a',key=None,view=None):
    v=view or read(f,p,user).json()
    return f[3].post('/api/preparations/'+p['preparation_id']+'/readiness',headers=headers(f[2],user,key or uuid4().hex),json={'expected_preparation_revision':v['preparation_revision'],'expected_source_sha256':v['source_sha256']})

def rows(f):
    with f[1].connect() as c:
        return {t:c.execute('SELECT * FROM '+t+' ORDER BY 1').fetchall() for t in ('preparations','preparation_events','preparation_evidence','run_assignments','capability_grants','preparation_grants')}

def test_missing_materials_unknown_read_only_and_persistent_reload(preparation_fixture):
    f=preparation_fixture;p,_,_=create(f);before=rows(f);v=read(f,p).json()
    assert rows(f)==before and v['state']=='NOT_ASSESSED' and v['current_truth']=='UNKNOWN'
    assert v['current_inputs']['missing_slots']==list(prep.SLOTS)
    a=assess(f,p).json();x=read(f,p).json();assert x['latest']==a and x['state']=='CURRENT' and x['current_truth']=='UNKNOWN'
    assert x['sources']['rule']['publication_status']=='DRAFT' and not a['result']['business_publication'] and a['result']['qualification_truth']=='UNKNOWN'
    after=rows(f);assert after['preparation_events']==before['preparation_events'] and after['run_assignments']==before['run_assignments']
    assert after['preparations'][0]['revision']==before['preparations'][0]['revision']

def test_review_correction_false_fill_unknown_manual_true_stale_and_refresh(preparation_fixture):
    f=preparation_fixture;p,_,_=create(f);assess(f,p)
    p=command(f,p,'REQUEST_CHANGES','prep-specialist-fixture-a',reason='SYNTHETIC 必须补完整材料').json()
    assert read(f,p).json()['state']=='STALE' and read(f,p).json()['current_truth']=='UNKNOWN'
    assert assess(f,p,'prep-specialist-fixture-a').json()['result']['local_preparation_truth']=='FALSE'
    p=add(f,p).json();p=add(f,p,'material_outline').json()
    assert assess(f,p).json()['result']['local_preparation_truth']=='UNKNOWN'
    p=command(f,p,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC 当前两项人工核对').json()
    a=assess(f,p).json();assert a['result']['local_preparation_truth']=='TRUE' and a['result']['qualification_truth']=='UNKNOWN'
    assert all(i['authenticity']=='UNVERIFIED' and i['source_label'] for i in a['sources']['materials'])
    p=command(f,p,'CONFIRM',reason='SYNTHETIC 本地确认').json();assess(f,p)
    p=add(f,p,text='SYNTHETIC 新版本').json();v=read(f,p).json()
    assert v['state']=='STALE' and v['current_truth']=='UNKNOWN' and v['latest']['result']['local_preparation_truth']=='TRUE'
    assert v['sources']['manual_review']['state']=='IN_PREPARATION' and v['sources']['manual_review']['review_sha256'] is None
    assert v['sources']['manual_review']['decision']==a['sources']['manual_review']['decision'] and v['current_inputs']['conditions'][1]['truth']=='UNKNOWN'
    assert len(v['history'])==5 and v['sources']['materials'][0]['version'] in (1,2)
    assert assess(f,p).json()['result']['local_preparation_truth']=='UNKNOWN'
    assert prep_read(f,p).json()['preparation']['state']=='IN_PREPARATION'

def test_request_change_invalidates_and_private_text_not_shared(preparation_fixture):
    f=preparation_fixture;p=filled(f);assess(f,p);p=save(f,p,text='PRIVATE_ENG086_request',goals=['PRIVATE_GOAL']).json()
    v=read(f,p,'prep-specialist-fixture-a');assert v.status_code==200 and v.json()['state']=='STALE'
    assert 'PRIVATE_ENG086_request' not in v.text and 'PRIVATE_GOAL' not in v.text and 'request_intent_sha256' not in v.text
    assert 'readiness_assessments' not in prep_read(f,p).json()['preparation']

@pytest.mark.parametrize('user',['fixture-b','fixture-c','executor-a'])
def test_cross_scope_executor_denied_without_mutation(receipt_fixture,user):
    f=receipt_fixture;p,_,_=create(f);before=rows(f)
    assert read(f,p,user).status_code==403
    assert assess(f,p,user,view=read(f,p).json()).status_code==403 and rows(f)==before

def test_same_key_concurrency_case_binding_and_stale_inputs(preparation_fixture):
    f=preparation_fixture;p,_,_=create(f);v=read(f,p).json();key=uuid4().hex
    with ThreadPoolExecutor(2) as pool:r=list(pool.map(lambda _:assess(f,p,key=key,view=v),range(2)))
    assert [x.status_code for x in r]==[200,200] and r[0].json()==r[1].json()
    p2,_,_=create(f);assert assess(f,p2,key=key).status_code==409
    p=add(f,p).json();assert assess(f,p,view=v).status_code==409
    assert assess(f,p,key=key).status_code==409
    assert len(read(f,p).json()['history'])==1

@pytest.mark.parametrize('capability',['READ','EXECUTE','PREPARE'])
def test_current_owner_revocation_denies_replay(preparation_fixture,capability):
    f=preparation_fixture;p,_,_=create(f);key=uuid4().hex;v=read(f,p).json();assert assess(f,p,key=key,view=v).status_code==200
    with f[1].connect() as c:
        table='preparation_grants' if capability=='PREPARE' else 'capability_grants'
        c.execute('UPDATE '+table+' SET active=false WHERE principal_id=%s AND capability=%s',('fixture-a',capability))
    before=rows(f);assert assess(f,p,key=key,view=v).status_code==403 and rows(f)==before

def test_reviewer_revocation_invalidates_true_snapshot(preparation_fixture):
    f=preparation_fixture;p=filled(f);p=command(f,p,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC checked').json()
    assert assess(f,p).json()['result']['local_preparation_truth']=='TRUE'
    with f[1].connect() as c:c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='prep-specialist-fixture-a'")
    v=read(f,p).json();assert v['state']=='STALE' and v['current_truth']=='UNKNOWN'
    assert assess(f,p).json()['result']['local_preparation_truth']=='UNKNOWN'
    assert read(f,p,'prep-specialist-fixture-a').status_code==403

def test_additive_migration_preserves_history_and_authorization(preparation_fixture):
    f=preparation_fixture;p=filled(f);before=rows(f)
    with f[1].connect() as c:
        c.execute('ALTER TABLE preparations DROP COLUMN readiness_assessments');c.execute('DELETE FROM schema_version WHERE version>=20')
    f[1].migrate();f[1].migrate();after=rows(f)
    assert after==before and read(f,p).json()['state']=='NOT_ASSESSED'

def test_assessment_rollback_and_bounded_history(preparation_fixture,monkeypatch):
    f=preparation_fixture;p,_,_=create(f);before=rows(f)
    from parkweave import readiness
    original=readiness._evaluate;v=read(f,p).json()
    def fail(source):raise RuntimeError('SYNTHETIC rollback')
    monkeypatch.setattr(readiness,'_evaluate',fail)
    with pytest.raises(RuntimeError):assess(f,p,view=v)
    assert rows(f)==before
    monkeypatch.setattr(readiness,'_evaluate',original)
    for _ in range(32):assert assess(f,p).status_code==200
    assert assess(f,p).status_code==409 and len(read(f,p).json()['history'])==32


def test_catalog_source_change_stales_prior_assessment_and_replay_is_historical(preparation_fixture):
    f=preparation_fixture;p=filled(f);v=read(f,p).json();key=uuid4().hex;a=assess(f,p,key=key,view=v).json()
    with f[1].connect() as c:
        c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{revision}','2') WHERE park_id='park-a'")
    x=read(f,p).json();assert x['state']=='STALE' and x['current_truth']=='UNKNOWN'
    assert x['latest']==a and assess(f,p,key=key,view=v).json()==a
    assert read(f,p).json()['state']=='STALE' and assess(f,p,view=v).status_code==409
    assert assess(f,p).status_code==200

def test_owner_assessment_and_assigned_reviewer_command_concurrent_without_lock_cycle(preparation_fixture):
    f=preparation_fixture;p=filled(f)
    for _ in range(4):
        v=read(f,p).json()
        with ThreadPoolExecutor(2) as pool:
            a=pool.submit(assess,f,p,view=v)
            b=pool.submit(command,f,p,'REQUEST_CHANGES','prep-specialist-fixture-a',reason='SYNTHETIC concurrent correction')
            ar,br=a.result(timeout=10),b.result(timeout=10)
        assert ar.status_code in (200,409) and br.status_code==200
        p=br.json()
    assert read(f,p).status_code==200
