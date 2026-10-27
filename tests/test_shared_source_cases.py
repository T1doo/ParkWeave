"""Real owner HTTP/PostgreSQL reverse lookup, literal source-specific oracles."""
from copy import deepcopy
from uuid import uuid4
import json
import pytest
from parkweave import shared_source_cases as shared
from test_registered_local_revision import http_f,link_fixture,receipt_fixture,preparation_fixture,add_resource
from test_case_goal_results import complete,snapshot
from test_service_case_steps import setup,GOALS,adopt,verified,read,step
from test_service_plan_manual_lock import lock,stored
from test_preparation import headers,command as preparation_act


def query(f,p,kind='OWNER_RESOURCE_QUERY_SET',limit=10,cursor=None,user='fixture-a'):
    params=dict(source_kind=kind,limit=limit)
    if cursor is not None:params['cursor']=cursor
    return f[3].get('/api/preparations/'+p['preparation_id']+'/shared-source-cases',params=params,headers=headers(f[2],user))


def indexed(response):return {x['preparation_id']:x for x in response['items']}
def ids(plan,adapters):return [s['id'] for s in plan['steps'] if s['adapter_id'] in adapters]


def test_two_actual_cases_share_owner_resource_pool_and_unaffected_p1_lock(http_f):
    f=http_f;p,_,_,_=complete(f,local=True);q,_,_,_=complete(f,local=True)
    assert lock(f,p,'P1').status_code==200
    oldp=stored(f,p);oldq=stored(f,q);before=snapshot(f)
    r=query(f,p);assert r.status_code==200,r.text;x=r.json();assert x['candidate_count']==2 and x['all_cases_checked']
    assert x['projection_schema']==1 and all(v['source_impact_schema']==1 for v in x['items'])
    assert all(v['state']=='UNCHANGED' for v in x['items']) and snapshot(f)==before
    add_resource(f);before=snapshot(f);r=query(f,p);assert r.status_code==200,r.text;x=r.json()
    for parent,plan in ((p,oldp),(q,oldq)):
        row=indexed(x)[parent['preparation_id']]
        assert row['relationship']=='SHARED_SOURCE' and row['source_changed'] is True
        assert row['affected']==ids(plan,('P2','P3','P4','P5')) and row['preserved']==ids(plan,('P1',))
    assert snapshot(f)==before and stored(f,p)['steps'][0]['manual_lock']==oldp['steps'][0]['manual_lock']


def test_selected_source_never_inherits_unrelated_material_or_receipt_impact(http_f):
    f=http_f;p,_,_,_=complete(f,local=True)
    p=preparation_act(f,p,'REOPEN',reason='SYNTHETIC actual unrelated material update').json()
    before=snapshot(f);r=query(f,p);assert r.status_code==200,r.text;row=indexed(r.json())[p['preparation_id']]
    assert row['state']=='UNCHANGED' and row['source_changed'] is False and not row['affected']
    assert row['case_affected']==ids(stored(f,p),('P1','P2','P3','P4','P5')) and snapshot(f)==before
    add_resource(f);before=snapshot(f);row=indexed(query(f,p).json())[p['preparation_id']]
    assert row['affected']==ids(stored(f,p),('P2','P3','P4','P5')) and row['preserved']==ids(stored(f,p),('P1',)) and snapshot(f)==before


def test_p1_only_not_dependent_and_no_plan_remains_visible_unknown(http_f):
    f=http_f;p,_,_,_=complete(f);q=setup(f,GOALS[0]);assert adopt(f,q).status_code==201;verified(f,q,'P1');pending=setup(f,GOALS[0])
    add_resource(f);before=snapshot(f);r=query(f,p);assert r.status_code==200,r.text;x=r.json();rows=indexed(x)
    assert x['candidate_count']==3 and not x['all_cases_checked'] and x['unknown_scope']=='CURRENT_OWNER_CASE_SET'
    assert rows[q['preparation_id']]['state']=='NOT_DEPENDENT' and not rows[q['preparation_id']]['affected']
    assert rows[pending['preparation_id']]['state']=='NO_PLAN' and rows[pending['preparation_id']]['relationship']=='UNKNOWN'
    assert rows[pending['preparation_id']]['source_impact_schema'] is None
    assert snapshot(f)==before


def test_no_preparation_case_is_not_silently_omitted(http_f):
    f=http_f;p=setup(f,GOALS[0])
    r=f[3].post('/api/runs',headers=headers(f[2],key=uuid4().hex),json={'goal':'SYNTHETIC no preparation original Case'})
    assert r.status_code==202,r.text;f[0].finish(f[0].claim('synthetic-no-preparation'))
    before=snapshot(f);r=query(f,p);assert r.status_code==200,r.text;x=r.json()
    assert x['candidate_count']==2 and any(v['state']=='NO_PREPARATION' and v['preparation_id'] is None for v in x['items'])
    assert not x['all_cases_checked'] and snapshot(f)==before


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a'])
def test_reverse_lookup_does_not_grant_other_owner_tenant_or_role_access(http_f,user):
    f=http_f;p,_,_,_=complete(f);before=snapshot(f);r=query(f,p,user=user)
    assert r.status_code==403 and 'items' not in r.text and 'source_ref' not in r.text and snapshot(f)==before


@pytest.mark.parametrize('mutation',['source_aba','preparation_aba','new_case','plan_revision','nonpage_receipt'])
def test_cursor_binds_all_candidate_case_versions_and_actual_source_epoch(http_f,mutation):
    f=http_f;p,_,_,s=complete(f);q=setup(f,GOALS[0]);assert adopt(f,q).status_code==201;verified(f,q,'P1')
    r=query(f,p,limit=1);assert r.status_code==200,r.text;cursor=r.json()['next_cursor'];assert cursor
    if mutation=='source_aba':
        from parkweave.resource_holds import RESOURCE_ID
        with f[1].connect() as c:capacity=c.execute('SELECT capacity FROM synthetic_resources WHERE id=%s',(RESOURCE_ID,)).fetchone()['capacity']
        with f[1].connect() as c:c.execute('UPDATE synthetic_resources SET capacity=capacity+1 WHERE id=%s',(RESOURCE_ID,))
        with f[1].connect() as c:c.execute('UPDATE synthetic_resources SET capacity=%s WHERE id=%s',(capacity,RESOURCE_ID))
    elif mutation=='preparation_aba':
        with f[1].connect() as c:original_goal=c.execute('SELECT goal FROM preparations WHERE id=%s',(q['preparation_id'],)).fetchone()['goal']
        with f[1].connect() as c:c.execute("UPDATE preparations SET goal=goal||' SYNTHETIC ABA' WHERE id=%s",(q['preparation_id'],))
        with f[1].connect() as c:c.execute('UPDATE preparations SET goal=%s WHERE id=%s',(original_goal,q['preparation_id']))
    elif mutation=='new_case':setup(f,GOALS[0])
    elif mutation=='plan_revision':assert lock(f,q,'P1').status_code==200
    else:
        from test_executor_receipts import act
        assert act(f,s,'REOPEN').status_code==200
    before=snapshot(f);r=query(f,p,limit=1,cursor=cursor);assert r.status_code==409,r.text;assert snapshot(f)==before


def test_pages_are_deterministic_and_cursor_cannot_change_source_or_subject(http_f):
    f=http_f;p,_,_,_=complete(f);q=setup(f,GOALS[0]);assert adopt(f,q).status_code==201;verified(f,q,'P1')
    before=snapshot(f);a=query(f,p,limit=1).json();b=query(f,p,limit=1,cursor=a['next_cursor']).json()
    assert len(a['items'])==len(b['items'])==1 and a['items'][0]['case_id']!=b['items'][0]['case_id'] and not b['has_more']
    assert a['enumeration_complete'] and b['enumeration_complete'] and not a['all_cases_checked'] and not b['all_cases_checked']
    for page in (a,b):
        assert page['state']=='UNKNOWN' and page['unknown_scope']=='CURRENT_OWNER_CASE_SET'
        assert 'CASE_PAGES_NOT_CHECKED' in page['blocking_reasons'] and page['source_ref']['available']
    assert query(f,p,'SERVICE_CATALOG_REFERENCE',limit=1,cursor=a['next_cursor']).status_code==409
    assert query(f,q,limit=1,cursor=a['next_cursor']).status_code==409 and snapshot(f)==before


def test_exact_catalog_row_scope_changes_without_implicating_resource_pool(http_f):
    f=http_f;p,_,_,_=complete(f);before=snapshot(f);r=query(f,p,'SERVICE_CATALOG_REFERENCE');assert r.status_code==200,r.text
    assert r.json()['source_ref']['service_version']==1 and indexed(r.json())[p['preparation_id']]['state']=='UNCHANGED' and snapshot(f)==before
    with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{revision}','\"2\"') WHERE park_id='park-a' AND service_id=%s AND version=1",('synthetic-material-preparation',))
    before=snapshot(f);x=query(f,p,'SERVICE_CATALOG_REFERENCE').json();row=indexed(x)[p['preparation_id']]
    assert row['state']=='CHANGED' and row['affected']==ids(stored(f,p),('P1','P2','P3','P4')) and snapshot(f)==before
    assert indexed(query(f,p).json())[p['preparation_id']]['state']=='UNCHANGED'


def test_unavailable_catalog_never_becomes_unchanged_valid_shared_source(http_f):
    f=http_f;p,_,_,_=complete(f)
    with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{kind}','\"UNKNOWN\"') WHERE park_id='park-a'")
    before=snapshot(f);r=query(f,p,'SERVICE_CATALOG_REFERENCE');assert r.status_code==200,r.text;x=r.json()
    assert not x['source_ref']['available'] and x['state']=='UNKNOWN' and not x['all_cases_checked']
    assert indexed(x)[p['preparation_id']]['state']=='UNKNOWN' and snapshot(f)==before


def test_candidate_limit_unknown_is_explicit_and_never_invents_complete_enumeration(http_f,monkeypatch):
    f=http_f;p=setup(f,GOALS[0]);setup(f,GOALS[0]);monkeypatch.setattr(shared,'MAX_CANDIDATES',1)
    before=snapshot(f);r=query(f,p);assert r.status_code==200,r.text;x=r.json()
    assert x['state']=='UNKNOWN' and x['candidate_count'] is None and not x['items'] and not x['has_more'] and x['next_cursor'] is None
    assert not x['enumeration_complete'] and not x['all_cases_checked'] and snapshot(f)==before


def test_current_read_revocation_precedes_even_an_old_cursor(http_f):
    f=http_f;p,_,_,_=complete(f);q=setup(f,GOALS[0]);cursor=query(f,p,limit=1).json()['next_cursor']
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True)
        c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='READ'")
    before=snapshot(f);r=query(f,p,limit=1,cursor=cursor);assert r.status_code==403 and snapshot(f)==before


def test_busy_original_parent_is_bounded_409_without_read_time_business_update(http_f):
    f=http_f;p=setup(f,GOALS[0]);before=snapshot(f)
    with f[1].connect() as c:
        c.execute('SELECT id FROM preparations WHERE id=%s FOR UPDATE',(p['preparation_id'],))
        r=query(f,p);assert r.status_code==409 and 'busy' in r.text
    assert snapshot(f)==before


@pytest.mark.parametrize('cursor',['['*1200+']'*1200,'{"schema":1,"schema":1}',json.dumps({'unknown':'SYNTHETIC private'})])
def test_recursive_duplicate_and_untrusted_cursor_are_constant_rejections(http_f,cursor):
    f=http_f;p=setup(f,GOALS[0]);before=snapshot(f);r=query(f,p,cursor=cursor)
    assert r.status_code==409 and 'SYNTHETIC private' not in r.text and snapshot(f)==before


def test_malformed_other_case_plan_is_unknown_without_raw_content_or_omission(http_f):
    from psycopg.types.json import Jsonb
    f=http_f;p=setup(f,GOALS[0]);q=setup(f,GOALS[0])
    # The database rejects scalar plans itself. Exercise the reachable damaged
    # object shape without dropping or bypassing that existing constraint.
    with f[1].connect() as c:c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb({'unexpected':'SYNTHETIC PRIVATE_BAD_PLAN'}),q['preparation_id']))
    before=snapshot(f);r=query(f,p);assert r.status_code==200,r.text;x=r.json();row=indexed(x)[q['preparation_id']]
    assert row['state']=='UNKNOWN' and row['plan_id'] is None and 'PRIVATE_BAD_PLAN' not in r.text and snapshot(f)==before
