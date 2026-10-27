"""Exact opaque evidence handles are read-only and require current owner scope."""
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import pytest
from test_material_preparation_drafts import draft_fixture
from test_preparation import preparation_fixture,create,add,headers,read,counts,command


def recover(f,row,key,user='fixture-a'):
    return f[3].get('/api/preparations/'+row['preparation_id']+'/command-recovery',headers=headers(f[2],user,key))


def test_committed_handle_after_response_loss_is_exact_read_only(preparation_fixture):
    f=preparation_fixture;row,_,_=create(f);key=str(uuid4());saved=add(f,row,key=key).json();before=counts(f[1])
    for _ in range(3):
        r=recover(f,row,key);assert r.status_code==200
        assert r.json()['status']=='COMMITTED' and r.json()['event']==saved
        assert r.json()['historical_only'] and not r.json()['automatically_replayed']
        assert 'text' not in r.json() and 'request_key' not in r.json()
    assert counts(f[1])==before


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a','prep-specialist-fixture-b'])
def test_handle_is_not_access_authority_or_cross_user_lookup(preparation_fixture,user):
    f=preparation_fixture;row,_,_=create(f);key=str(uuid4());add(f,row,key=key);before=counts(f[1]);r=recover(f,row,key,user)
    assert r.status_code==403 and 'event' not in r.json()
    assert counts(f[1])==before


@pytest.mark.parametrize('target',['READ','PREPARE'])
def test_current_revocation_denies_historical_handle(preparation_fixture,target):
    f=preparation_fixture;row,_,_=create(f);key=str(uuid4());saved=add(f,row,key=key).json()
    table='capability_grants' if target=='READ' else 'preparation_grants'
    with f[1].connect() as c:c.execute('UPDATE '+table+' SET active=false WHERE principal_id=%s AND capability=%s',('fixture-a',target))
    assert recover(f,row,key).status_code==403
    with f[1].connect() as c:c.execute('UPDATE '+table+' SET active=true WHERE principal_id=%s AND capability=%s',('fixture-a',target))
    assert recover(f,row,key).json()['event']==saved
    assert read(f,row).json()['preparation']['state']=='IN_PREPARATION'


def test_unobserved_handle_and_concurrent_late_request_use_original_cas(preparation_fixture):
    f=preparation_fixture;row,_,_=create(f);key=str(uuid4());before=counts(f[1]);r=recover(f,row,key)
    assert r.status_code==200 and r.json()['status']=='NOT_OBSERVED' and r.json()['event'] is None
    assert counts(f[1])==before
    with ThreadPoolExecutor(2) as pool:
        results=list(pool.map(lambda k:add(f,row,text='SYNTHETIC explicit owner reentry',key=k),[key,str(uuid4())]))
    assert sorted(r.status_code for r in results)==[200,409]
    pack=read(f,row).json();assert len(pack['material_history'])==1
    assert recover(f,row,key).json()['status'] in ('COMMITTED','NOT_OBSERVED')


def test_later_revision_does_not_turn_original_event_into_current_result(preparation_fixture):
    f=preparation_fixture;row,_,_=create(f);key=str(uuid4());saved=add(f,row,key=key).json();new=add(f,saved,text='SYNTHETIC new owner version').json()
    r=recover(f,row,key).json();assert r['event']==saved and r['current_revision']==new['revision'] and r['historical_only']
    pack=read(f,row).json();assert pack['current_materials'][0]['text']=='SYNTHETIC new owner version' and len(pack['material_history'])==2


def test_handle_cannot_find_another_case_or_replay_non_evidence(preparation_fixture):
    f=preparation_fixture;row,_,_=create(f);other,_,_=create(f);key=str(uuid4());add(f,row,key=key)
    assert recover(f,other,key).status_code==409
    decision_key=str(uuid4());command(f,other,'REQUEST_CHANGES','prep-specialist-fixture-a',key=decision_key,reason='SYNTHETIC explicit review')
    assert recover(f,other,decision_key).json()['status']=='NOT_OBSERVED'
    assert recover(f,row,'not-a-uuid').status_code==422


def test_recovery_does_not_reactivate_generated_brief_after_source_change(draft_fixture):
    from test_material_preparation_drafts import preview,save,body
    f,parent,_=draft_fixture
    shared=save(f,parent,body(preview(f,parent).json())).json()
    key=str(uuid4());parent=add(f,shared,'material_outline','SYNTHETIC original directory',key=key).json()
    with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{revision}','\"recovery-source-changed\"')")
    before=counts(f[1]);r=recover(f,parent,key)
    assert r.status_code==200 and r.json()['status']=='COMMITTED' and r.json()['historical_only']
    pack=read(f,parent).json();brief=next(m for m in pack['current_materials'] if m['slot']=='need_summary')
    assert not brief['material_draft_source']['source_current']
    assert command(f,parent,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC no stale recovery').status_code==409
    assert counts(f[1])==before
