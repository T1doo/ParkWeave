"""Case-bound proposal before adoption; actual PG/API, no permissions generated."""
import hashlib,json
from uuid import uuid4
import pytest
from parkweave import controlled_plans as cp
from test_preparation import preparation_fixture,create as prepare,add,headers
from test_controlled_plans import create as adopt

GOAL=cp.TEMPLATE['goal']
def preview(f,p,goals=None,user='fixture-a'):
    return f[3].post('/api/preparations/'+p['preparation_id']+'/controlled-plan/preview',
      headers=headers(f[2],user),json={'required_goals':goals or [GOAL]})
def denial_count(f):
    with f[1].connect() as c:return c.execute("SELECT count(*) n FROM authorization_audit WHERE outcome='DENIED'").fetchone()['n']

def digest(f):
    with f[1].connect() as c:
        tables=[r['tablename'] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename!='authorization_audit' ORDER BY tablename")]
        data={t:sorted(json.dumps(dict(r),sort_keys=True,default=str) for r in c.execute('SELECT * FROM "'+t+'"')) for t in tables}
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()

def test_preview_is_read_only_complete_proposal_and_preserves_uncovered_goal(preparation_fixture):
    f=preparation_fixture;p,_,_=prepare(f);before=digest(f)
    r=preview(f,p,[GOAL,'需要外部机构受理回执']);assert r.status_code==200,r.text
    x=r.json();assert x['namespace']=='PREVIEW' and x['state']=='PARTIAL' and not x['can_adopt']
    assert x['required_goals']==[GOAL,'需要外部机构受理回执'] and x['unsupported_goals']==['需要外部机构受理回执']
    assert len(x['steps'])==4 and x['steps'][0]['depends_on']==[] and x['steps'][3]['depends_on']==['P3']
    assert all(all(s[k] for k in ('responsibility','preconditions','output','acceptance')) for s in x['steps'])
    assert 'CURRENT_MATERIAL_CONFIRMATION_REQUIRED' in x['steps'][0]['issues']
    assert 'EXISTING_RUN_ASSIGNMENT_REQUIRED' in x['steps'][2]['issues']
    assert not x['persisted'] and not x['executed'] and not x['business_publication'] and not x['case_goal_completed']
    assert digest(f)==before
    assert adopt(f,p,required_goals=x['required_goals'],expected_preview_sha256=x['preview_sha256']).status_code==422
    assert digest(f)==before

@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a'])
def test_preview_only_current_case_owner(preparation_fixture,user):
    f=preparation_fixture;p,_,_=prepare(f);before=digest(f);audit=denial_count(f)
    assert preview(f,p,user=user).status_code==403 and digest(f)==before
    assert denial_count(f)==audit+1

def test_current_preview_adoption_idempotency_and_changed_input_rejected(preparation_fixture):
    f=preparation_fixture;p,_,_=prepare(f);before=digest(f);x=preview(f,p).json()
    assert x['can_adopt'] and x['state']=='READY_TO_ADOPT' and digest(f)==before
    p=add(f,p).json();changed=digest(f)
    assert adopt(f,p,expected_preview_sha256=x['preview_sha256']).status_code==409 and digest(f)==changed
    x=preview(f,p).json();key=uuid4().hex
    r=adopt(f,p,key=key,expected_preview_sha256=x['preview_sha256']);assert r.status_code==201,r.text
    assert r.json()['state']!='LOCAL_RECORDS_CHECKED' and not r.json()['case_goal_completed']
    retry=adopt(f,p,key=key,expected_preview_sha256=x['preview_sha256'])
    assert retry.status_code==201 and retry.json()['event']==r.json()['event']
    x=preview(f,p).json();assert not x['can_adopt'] and 'PLAN_ALREADY_EXISTS' in x['creation_blockers']

def test_execute_revocation_blocks_preview_adoption_without_hiding_proposal(preparation_fixture):
    f=preparation_fixture;p,_,_=prepare(f)
    with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
    before=digest(f);x=preview(f,p).json()
    assert not x['can_adopt'] and x['creation_blockers']==['CURRENT_EXECUTE_AUTHORITY_REQUIRED']
    assert len(x['steps'])==4 and digest(f)==before
    audit=denial_count(f)
    assert adopt(f,p,expected_preview_sha256=x['preview_sha256']).status_code==403 and digest(f)==before
    assert denial_count(f)==audit+1

@pytest.mark.parametrize('goals',[[],[' '],['x'*161],[GOAL]*9])
def test_preview_bounded_input(preparation_fixture,goals):
    f=preparation_fixture;p,_,_=prepare(f)
    r=f[3].post('/api/preparations/'+p['preparation_id']+'/controlled-plan/preview',headers=headers(f[2]),json={'required_goals':goals})
    assert r.status_code==422
