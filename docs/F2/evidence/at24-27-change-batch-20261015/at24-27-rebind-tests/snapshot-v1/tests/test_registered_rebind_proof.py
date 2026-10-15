"""Independent refusals for fully registered six-goal resource comparisons.

Original actual HTTP, isolated PG and the original fresh TemplateConsumer chain.
Only owned fixture corruption/admin revocation produces negative premises; the
comparison and confirm routes retain their original validation and permissions.
"""
from copy import deepcopy
import hashlib
import json
import sqlite3
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from test_preparation import preparation_fixture, headers
from test_executor_receipts import receipt_fixture
from test_case_resources import link_fixture
from test_new_enterprise_local_chain import (
    ALL_GOALS, fresh_chain, publish, new_case, enable_approval, finish_chain,
    holds, call,
)
from test_resource_combinations import write as confirm_combination
from parkweave import controlled_plans as cp


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()


def pg_rows(u):
    with u['f'][1].connect() as c:
        tables=[r['tablename'] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]
        return {t:c.execute('SELECT * FROM "'+t+'" ORDER BY to_jsonb("'+t+'")::text').fetchall() for t in tables}


def private_journals(u):
    result={}
    for repository in (u['engine'].repository,u['consumer'].repository,u['access'].repository):
        with sqlite3.connect('file:'+str(repository.path)+'?mode=ro',uri=True) as c:
            tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            result[repository.path.name]={t:sorted(json.dumps(tuple(r),default=str) for r in c.execute('SELECT * FROM "'+t+'"')) for t in tables}
    return result


def business(rows):return {k:v for k,v in rows.items() if k!='authorization_audit'}


def comparison(u,row,candidate):
    return u['f'][3].get('/api/preparations/'+row['preparation_id']+'/resource-plan-binding',
        headers=headers(u['f'][2]),params={'candidate_combination_id':candidate['id']})


def confirm_body(row,candidate,value):
    current=value['comparison']
    return dict(combination_id=candidate['id'],expected_preparation_revision=current['preparation_revision'],
        expected_link_revision=current['link_revision'],expected_comparison_sha256=current['sha256'],
        reason='SYNTHETIC independent exact current comparison refusal probe')


@pytest.fixture
def registered_case(fresh_chain):
    u=fresh_chain;release=publish(u);row=new_case(u,release)
    enable_approval(u,[row]);done=finish_chain(u,row)
    assert done['results']['state']=='LOCAL_OUTPUTS_VERIFIED'
    assert len(done['results']['results'])==6 and set(r['goal'] for r in done['results']['results'])==set(ALL_GOALS)
    # A distinct original confirmed combination is a legitimate candidate. Its
    # two members use a separate time window; no old occupancy is canceled.
    # The original fixed combination route accepts exactly two members.
    _,requested=holds(u,offset=24);data=dict(members=requested['members'][:2])
    response=confirm_combination(u['f'],data)
    assert response.status_code==201,response.text;candidate=response.json()['combination']
    baseline=pg_rows(u);journals=private_journals(u)
    response=comparison(u,row,candidate);assert response.status_code==200,response.text;value=response.json()
    assert value['comparison']['can_confirm'],value['comparison']['blockers']
    assert 'CURRENT_PLAN_P1_REQUIRED' not in value['checkpoints']['P1']['issues']
    assert value['current']['required_goals']==ALL_GOALS and not value['business_writes'] and not value['new_grants']
    assert digest(pg_rows(u))==digest(baseline) and private_journals(u)==journals
    return u,row,candidate,value


@pytest.mark.parametrize('premise',[
    'bad_initial_adopt_fingerprint',
    'missing_p1_verification',
    'damaged_p1_source_proof',
    'changed_catalog_binding',
    'execute_revoked',
])
def test_registered_comparison_preserves_strict_original_proof_and_authority(registered_case,premise):
    u,row,candidate,initial=registered_case;f=u['f']
    with f[1].connect() as c:
        if premise=='execute_revoked':
            f[1].lock_principal(c,'fixture-a',exclusive=True)
            c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='EXECUTE'")
        elif premise=='changed_catalog_binding':
            c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{revision}','999'::jsonb) WHERE (park_id,service_id,version) IN (SELECT park_id,service_id,service_version FROM preparations WHERE id=%s)",(row['preparation_id'],))
        else:
            plan=deepcopy(c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()['service_case_plan'])
            p1=next(s for s in plan['steps'] if s['adapter_id']=='P1')
            if premise=='bad_initial_adopt_fingerprint':plan['events'][0]['fingerprint']='0'*64
            elif premise=='missing_p1_verification':
                p1.update(coordination_state='PENDING',verified_sha256=None,verified_sources=None,invalidated=True)
            else:
                p1['verified_sources']['preparation_sha256']='0'*64
                p1['verified_sha256']=cp._hash(p1['verified_sources'])
            c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),row['preparation_id']))
    baseline=pg_rows(u);journals=private_journals(u)
    response=comparison(u,row,candidate)
    if premise=='bad_initial_adopt_fingerprint':
        assert response.status_code==409,response.text;body=confirm_body(row,candidate,initial)
    else:
        assert response.status_code==200,response.text;value=response.json()
        assert value['comparison']['can_confirm'] is False
        if premise=='execute_revoked':assert 'OWNER_EXECUTE_REQUIRED' in value['comparison']['blockers']
        else:assert 'CURRENT_PLAN_P1_REQUIRED' in value['comparison']['blockers']
        # Echo the currently blocked comparison hash, so confirmation refuses
        # its actual proof/authority gate rather than merely a stale request.
        body=confirm_body(row,candidate,value)
    assert digest(pg_rows(u))==digest(baseline), 'comparison GET wrote PG state'
    assert private_journals(u)==journals
    response=f[3].post('/api/preparations/'+row['preparation_id']+'/resource-plan-binding/confirm',
        headers=headers(f[2],key=uuid4().hex),json=body)
    assert response.status_code==(403 if premise=='execute_revoked' else 409),response.text
    after=pg_rows(u)
    assert digest(business(after))==digest(business(baseline)), 'refused confirmation changed business, authority or history'
    assert private_journals(u)==journals
    old_audit={str(r['id']):r for r in baseline['authorization_audit']}
    audit={str(r['id']):r for r in after['authorization_audit']}
    assert all(audit.get(key)==value for key,value in old_audit.items())
    added=[r for key,r in audit.items() if key not in old_audit]
    assert len(added)==(1 if premise=='execute_revoked' else 0)
    assert all(r['principal_id']=='fixture-a' and r['outcome']=='DENIED' for r in added)
