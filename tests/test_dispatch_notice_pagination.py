"""Owned synthetic PG/API pagination; positions never grant access."""
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
import json
import re

from fastapi.testclient import TestClient
import pytest
from psycopg.types.json import Jsonb
from parkweave.api import create_app
from parkweave import dispatch_notices as dn
from parkweave.store import Denied, Store
from test_preparation import preparation_fixture, headers
from test_executor_receipts import receipt_fixture
from test_service_dispatches import offer

BASE=datetime(2026,10,10,tzinfo=timezone.utc)


def seed_candidates(f, count, *, start=0, same_time=False):
    """Fixture owner seeds bounded, referential synthetic event/delivery rows.

    Uses original Case/offer/assignment setup, not new app roles or permissions.
    This tests listing historical records, not business event generation.
    """
    ids=[];parents=[]
    for offset in range(0,count,63):
        response,parent,_=offer(f)
        assert response.status_code==201
        parents.append(parent)
        with f[1].connect() as c:
            original=c.execute('SELECT * FROM service_dispatch_events WHERE dispatch_id=%s',
                               (response.json()['dispatch_id'],)).fetchone()
            for index in range(min(63,count-offset)):
                event_id=uuid4();ids.append(str(event_id))
                stamp=BASE if same_time else BASE+timedelta(microseconds=start+offset+index)
                c.execute('''INSERT INTO service_dispatch_events
                    (id,dispatch_id,offer_id,actor_id,request_key,fingerprint,revision,action,payload)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,'REOFFER',%s)''',
                    (event_id,original['dispatch_id'],original['offer_id'],original['actor_id'],
                     uuid4().hex,original['fingerprint'],index+2,
                     Jsonb({'private':'PRIVATE NOTICE BODY'})))
                c.execute("INSERT INTO dispatch_notice_outbox(event_id,recipient_id,state,consumed_at) VALUES(%s,'executor-a','DELIVERED',%s)",
                          (event_id,stamp))
                c.execute("INSERT INTO dispatch_notices(event_id,recipient_id,delivered_at) VALUES(%s,'executor-a',%s)",
                          (event_id,stamp))
    return ids,parents


def page(f,cursor=None,user='executor-a'):
    return f[3].get('/api/dispatch-notices',params={} if cursor is None else {'cursor':cursor},
                    headers=headers(f[2],user))


def all_pages(f, first=None):
    result=first or page(f);seen=[]
    for _ in range(40):
        assert result.status_code==200
        assert result.headers['cache-control']=='no-store'
        body=result.json()
        assert set(body)=={'scope','items','check_limit','page_limit','next_cursor','external_send','case_goal_completed'}
        assert body['check_limit']==100 and body['page_limit']==20 and len(body['items'])<=20
        assert 'PRIVATE NOTICE BODY' not in result.text
        seen.extend(item['event_id'] for item in body['items'])
        if body['next_cursor'] is None:return seen
        assert re.fullmatch(r'[A-Za-z0-9_-]{43}',body['next_cursor'])
        result=page(f,body['next_cursor'])
    raise AssertionError('pagination did not terminate within synthetic bound')


def snapshot(f):
    tables=('dispatch_notices','dispatch_notice_outbox','service_dispatches','service_dispatch_offers',
            'service_dispatch_events','preparations','preparation_events','service_receipt_steps',
            'service_step_receipts','service_receipt_events','outbox')
    with f[1].connect() as c:
        return {t:c.execute('SELECT jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text) rows FROM '+t+' t').fetchone()['rows']
                for t in tables}


@pytest.mark.parametrize('same_time',[False,True])
def test_101_plus_all_reachable_ordered_no_duplicates_and_get_writes_no_business_state(receipt_fixture,same_time):
    f=receipt_fixture;ids,_=seed_candidates(f,127,same_time=same_time)
    before=snapshot(f)
    seen=all_pages(f)
    expected=sorted(ids,key=lambda x:UUID(x).int,reverse=True) if same_time else list(reversed(ids))
    assert seen==expected and len(set(seen))==127
    assert snapshot(f)==before


def test_first_100_revoked_does_not_false_empty_or_expose_denied_records(receipt_fixture,monkeypatch):
    f=receipt_fixture;allowed,_=seed_candidates(f,23)
    denied,parents=seed_candidates(f,100,start=1000)
    with f[1].connect() as c:
        f[1].lock_principal(c,'executor-a',exclusive=True)
        for parent in parents:
            c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a' AND run_id=%s",(parent['run_id'],))
    examined=[];original_source=dn._source
    def source(c,event_id):
        examined.append(event_id)
        return original_source(c,event_id)
    monkeypatch.setattr(dn,'_source',source)
    first=page(f);body=first.json()
    assert len(examined)==100
    assert first.status_code==200 and body['items']==[] and body['next_cursor']
    for private in denied+[p['preparation_id'] for p in parents]+[p['case_id'] for p in parents]:
        assert private not in first.text
    assert all_pages(f,first)==list(reversed(allowed))


def test_high_water_keeps_original_pages_and_refresh_sees_concurrent_insert(receipt_fixture):
    f=receipt_fixture;original,_=seed_candidates(f,105)
    first=page(f);first_ids=[n['event_id'] for n in first.json()['items']]
    fresh,_=seed_candidates(f,3,start=10000)
    rest=all_pages(f,page(f,first.json()['next_cursor']))
    assert first_ids+rest==list(reversed(original))
    assert all_pages(f)==list(reversed(fresh))+list(reversed(original))


@pytest.mark.parametrize('change',['assignment','read','inactive','role','tenant','token'])
def test_each_page_and_handle_replay_recheck_current_authority(receipt_fixture,change):
    f=receipt_fixture;ids,_=seed_candidates(f,101)
    cursor=page(f).json()['next_cursor']
    assert page(f,cursor).status_code==200
    with f[1].connect() as c:
        f[1].lock_principal(c,'executor-a',exclusive=True)
        if change=='assignment':c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a'")
        elif change=='read':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
        else:
            clause={'inactive':'active=false','role':"role='resource_admin'",'tenant':"org_id='org-b'",'token':"token_hash=token_hash||'rotated'"}[change]
            c.execute('UPDATE principals SET '+clause+" WHERE id='executor-a'")
    after=snapshot(f)
    for _ in range(2):
        result=page(f,cursor)
        assert result.status_code==403 or result.json()['items']==[]
        assert all(private not in result.text for private in ids)
    assert snapshot(f)==after


@pytest.mark.parametrize('user',['fixture-a','fixture-b','executor-b','executor-c','unassigned'])
def test_navigation_is_bound_to_identity_tenant_and_list_with_generic_refusal(receipt_fixture,user):
    f=receipt_fixture;ids,_=seed_candidates(f,101)
    cursor=page(f).json()['next_cursor']
    result=page(f,cursor,user)
    assert result.status_code==403
    assert result.json()=={'detail':'record unavailable or authorization denied'}
    assert cursor not in result.text and all(private not in result.text for private in ids)
    assert page(f,cursor).status_code==200


@pytest.mark.parametrize('bad',['','short','a'*42,'a'*44,'a'*43,'<PRIVATE_CURSOR>', 'a'*42+'!'])
def test_invalid_expired_tampered_or_wrong_query_cursor_never_echoes(receipt_fixture,bad):
    f=receipt_fixture
    result=page(f,bad)
    assert result.status_code==403 and result.json()=={'detail':'record unavailable or authorization denied'}


def test_duplicate_or_cross_purpose_query_refused_and_app_restart_requires_refresh(receipt_fixture):
    f=receipt_fixture;seed_candidates(f,101)
    cursor=page(f).json()['next_cursor']
    for query in [[('cursor',cursor),('cursor',cursor)], [('cursor',cursor),('purpose','other-list')]]:
        result=f[3].get('/api/dispatch-notices',params=query,headers=headers(f[2],'executor-a'))
        assert result.status_code==403 and result.json()=={'detail':'record unavailable or authorization denied'}
    with TestClient(create_app(Store(f[0].dsn))) as restarted:
        assert restarted.get('/api/dispatch-notices',params={'cursor':cursor},headers=headers(f[2],'executor-a')).status_code==403
        assert restarted.get('/api/dispatch-notices',headers=headers(f[2],'executor-a')).status_code==200


def test_absolute_navigation_ttl_capacity_and_scope_are_bounded_without_renewal():
    now=[10.0];nav=dn.Navigation(capacity=2,ttl=10,clock=lambda:now[0])
    binding=(dn.SCOPE,'person','park','org','role','synthetic-token-hash')
    high=(BASE,UUID(int=3));after=(BASE,UUID(int=2))
    one=nav.issue(binding,high,after,20)
    now[0]=15;position=nav.resolve(one,binding)
    child=nav.issue(binding,position.high_water,position.after,position.expires)
    assert nav.resolve(child,binding).expires==20
    nav.issue(binding,high,after,20)
    with pytest.raises(Denied):nav.resolve(one,binding)
    with pytest.raises(Denied):nav.resolve(child,('OTHER_LIST',*binding[1:]))
    now[0]=20
    with pytest.raises(Denied):nav.resolve(child,binding)
    assert len(nav._positions)==0


def test_api_handle_expiry_is_generic_and_refresh_restarts_browsing(receipt_fixture):
    f=receipt_fixture;seed_candidates(f,101)
    nav=f[3].app.state.notice_navigation
    now=[10.0];nav._clock=lambda:now[0]
    cursor=page(f).json()['next_cursor'];now[0]=310.0
    result=page(f,cursor)
    assert result.status_code==403 and result.json()=={'detail':'record unavailable or authorization denied'}
    assert page(f).status_code==200


def test_direct_store_navigation_rechecks_instead_of_caching_permission(receipt_fixture):
    f=receipt_fixture;seed_candidates(f,101)
    first=dn.list_items(f[0],f[2]['executor-a'])
    second=dn.list_items(f[0],f[2]['executor-a'],cursor=first['next_cursor'])
    assert len(first['items'])==len(second['items'])==20
    assert set(n['event_id'] for n in first['items']).isdisjoint(n['event_id'] for n in second['items'])
