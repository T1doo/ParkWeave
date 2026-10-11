"""New owned synthetic PG/ASGI probes; no listeners, browser or proof chain."""
from uuid import UUID
from fastapi.testclient import TestClient
import pytest
from parkweave import dispatch_notices as dn
from parkweave.store import Store, digest, Denied
from parkweave.api import create_app
from test_preparation import preparation_fixture,headers
from test_executor_receipts import receipt_fixture
from test_dispatch_notice_pagination import seed_candidates,snapshot,BASE

def get(f,cursor=None,token=None,**kwargs):
    return f[3].get('/api/dispatch-notices',headers={'Authorization':'Bearer '+(token or f[2]['executor-a'])},
        params={} if cursor is None else {'cursor':cursor},**kwargs)

def rejected(r,*private):
    assert r.status_code==403,r.text
    assert r.json()=={'detail':'record unavailable or authorization denied'}
    assert all(x not in r.text for x in private)
    assert r.headers['cache-control']=='no-store'

def collect(f,response):
    seen=[]
    for _ in range(20):
        assert response.status_code==200,response.text
        data=response.json()
        assert set(data)=={'scope','items','check_limit','page_limit','next_cursor','external_send','case_goal_completed'}
        assert len(data['items'])<=20 and data['check_limit']==100 and data['page_limit']==20
        assert data['external_send'] is False and data['case_goal_completed'] is False
        seen.extend(n['event_id'] for n in data['items'])
        if data['next_cursor'] is None:return seen
        response=get(f,data['next_cursor'])
    raise AssertionError('bounded synthetic traversal did not terminate')

def test_tied_delivery_full_traversal_and_highwater(receipt_fixture):
    f=receipt_fixture;ids,_=seed_candidates(f,123,same_time=True)
    first=get(f);before=snapshot(f)
    expected=sorted(ids,key=lambda x:UUID(x).int,reverse=True)
    assert collect(f,first)==expected
    assert snapshot(f)==before
    old=get(f).json();fresh,_=seed_candidates(f,2,start=10000)
    rest=collect(f,get(f,old['next_cursor']))
    assert [n['event_id'] for n in old['items']]+rest==expected
    assert collect(f,get(f))==list(reversed(fresh))+expected

def test_filtered_scan_limit_advances_across_zero_item_page(receipt_fixture,monkeypatch):
    f=receipt_fixture;allowed,_=seed_candidates(f,51);blocked,parents=seed_candidates(f,100,start=1000)
    with f[1].connect() as c:
        for p in parents:c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a' AND run_id=%s",(p['run_id'],))
    source=dn._source;seen=[]
    def record(c,event_id):seen.append(str(event_id));return source(c,event_id)
    monkeypatch.setattr(dn,'_source',record)
    before=snapshot(f);first=get(f)
    assert first.status_code==200 and first.json()['items']==[] and first.json()['next_cursor']
    assert len(seen)==100
    for hidden in blocked+[p['case_id'] for p in parents]+[p['preparation_id'] for p in parents]:
        assert hidden not in first.text
    assert 'PRIVATE NOTICE BODY' not in first.text and 'total' not in first.json()
    assert collect(f,first)==list(reversed(allowed))
    assert snapshot(f)==before

def test_replaying_same_position_observes_current_assignment(receipt_fixture):
    f=receipt_fixture;ids,_=seed_candidates(f,44);cursor=get(f).json()['next_cursor']
    old=get(f,cursor).json();assert len(old['items'])==20
    with f[1].connect() as c:c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a'")
    before=snapshot(f);new=get(f,cursor)
    assert new.status_code==200 and new.json()['items']==[]
    assert all(x not in new.text for x in ids)
    assert snapshot(f)==before

def test_rotated_session_cannot_use_prior_session_handle(receipt_fixture):
    f=receipt_fixture;ids,_=seed_candidates(f,45);cursor=get(f).json()['next_cursor']
    new_token='SYNTHETIC-NEW-SESSION-INDEPENDENT'
    with f[1].connect() as c:c.execute("UPDATE principals SET token_hash=%s WHERE id='executor-a'",(digest(new_token),))
    before=snapshot(f)
    rejected(get(f,cursor,token=new_token),cursor,*ids)
    assert get(f,token=new_token).status_code==200
    assert snapshot(f)==before

def test_absolute_ttl_not_extended_by_child_or_replay(receipt_fixture):
    f=receipt_fixture;seed_candidates(f,70);nav=f[3].app.state.notice_navigation
    now=[10.0];nav._clock=lambda:now[0]
    one=get(f).json()['next_cursor'];now[0]=309.0
    two=get(f,one).json()['next_cursor']
    assert two and nav._positions[one].expires==310 and nav._positions[two].expires==310
    replay=get(f,one);assert replay.status_code==200
    assert nav._positions[replay.json()['next_cursor']].expires==310
    before=snapshot(f);now[0]=310.0
    rejected(get(f,one),one);rejected(get(f,two),two)
    assert get(f).status_code==200 and snapshot(f)==before

def test_eviction_denies_old_handle_without_permission_effect(receipt_fixture):
    f=receipt_fixture;seed_candidates(f,80);nav=f[3].app.state.notice_navigation;nav._capacity=1
    one=get(f).json()['next_cursor'];two=get(f,one).json()['next_cursor']
    assert len(nav._positions)==1 and one not in nav._positions
    before=snapshot(f);rejected(get(f,one),one)
    assert get(f,two).status_code==200 and snapshot(f)==before

@pytest.mark.parametrize('count',[0,20,100])
def test_exact_bounds_end_with_explicit_terminal_page(receipt_fixture,count):
    f=receipt_fixture
    if count:seed_candidates(f,count)
    before=snapshot(f);seen=collect(f,get(f))
    assert len(seen)==count and len(set(seen))==count and snapshot(f)==before

def test_restart_and_foreign_tenant_handles_require_refresh(receipt_fixture):
    f=receipt_fixture;ids,_=seed_candidates(f,25);cursor=get(f).json()['next_cursor']
    before=snapshot(f)
    rejected(get(f,cursor,token=f[2]['executor-b']),cursor,*ids)
    with TestClient(create_app(Store(f[0].dsn))) as client:
        r=client.get('/api/dispatch-notices',params={'cursor':cursor},headers=headers(f[2],'executor-a'))
        rejected(r,cursor,*ids)
        assert client.get('/api/dispatch-notices',headers=headers(f[2],'executor-a')).status_code==200
    assert snapshot(f)==before

@pytest.mark.parametrize('query',['cursor=&cursor=PRIVATE','%63ursor=PRIVATE&cursor=PRIVATE',
    'cursor=PRIVATE&request_key=OTHER','scope=PRIVATE','cursor='+'A'*44])
def test_query_rejection_generic_and_no_data(receipt_fixture,query):
    f=receipt_fixture;before=snapshot(f)
    r=f[3].get('/api/dispatch-notices?'+query,headers=headers(f[2],'executor-a'))
    rejected(r,'PRIVATE','OTHER')
    assert snapshot(f)==before

@pytest.mark.parametrize('edit',['role','org','read'])
def test_position_never_overrides_current_principal_scope(receipt_fixture,edit):
    f=receipt_fixture;ids,_=seed_candidates(f,25);cursor=get(f).json()['next_cursor']
    with f[1].connect() as c:
        if edit=='role':c.execute("UPDATE principals SET role='resource_admin' WHERE id='executor-a'")
        elif edit=='org':c.execute("UPDATE principals SET org_id='org-b' WHERE id='executor-a'")
        else:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
    before=snapshot(f);rejected(get(f,cursor),cursor,*ids)
    assert snapshot(f)==before

def test_navigation_capacity_and_expiry_bounds():
    for kwargs in ({'capacity':257},{'capacity':True},{'ttl':301},{'ttl':False}):
        with pytest.raises(ValueError):dn.Navigation(**kwargs)
    now=[1.0];nav=dn.Navigation(clock=lambda:now[0]);binding=(dn.SCOPE,'p','park','org','role','synthetic-session')
    handles=[nav.issue(binding,(BASE,UUID(int=500)),(BASE,UUID(int=i+1)),301) for i in range(257)]
    assert len(nav._positions)==256
    with pytest.raises(Denied):nav.resolve(handles[0],binding)
    assert nav.resolve(handles[-1],binding).expires==301
    now[0]=301
    with pytest.raises(Denied):nav.resolve(handles[-1],binding)
