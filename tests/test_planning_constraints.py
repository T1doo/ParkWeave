"""Owned API checks for declared planning constraints, not NLP or authority."""
from uuid import uuid4
import pytest
from parkweave import controlled_plans as cp
from test_preparation import preparation_fixture,create,headers,add
from test_request_intents import save
from test_isolated_run_access import permission_snapshot

P1='LOCAL_MATERIAL_PREPARATION';P5='LOCAL_CASE_RECORD_RECHECK'
def update(f,p,goals,constraints='omit',key=None,text='SYNTHETIC explicit current request'):
    data=dict(expected_preparation_revision=p['revision'],request_text=text,required_goals=goals)
    if constraints!='omit':data['planning_constraints']=constraints
    return f[3].post('/api/preparations/'+p['preparation_id']+'/request-intent',headers=headers(f[2],key=key or uuid4().hex),json=data)
def preview(f,p):return f[3].get('/api/preparations/'+p['preparation_id']+'/planning-preview',headers=headers(f[2])).json()['current']
def adopt(f,p,v,goals):return f[3].post('/api/preparations/'+p['preparation_id']+'/service-case-plan',headers=headers(f[2],key=uuid4().hex),json=dict(expected_preparation_revision=v['preparation_revision'],expected_request_revision=p['revision'],expected_source_sha256=v['source_sha256'],required_goals=goals,reason='SYNTHETIC explicitly confirm this exact preview'))
def prep(f):p,_,_=create(f);return p

def test_compatible_material_contract_and_conflicting_full_contract_keep_all_goals(preparation_fixture):
    f=preparation_fixture;permissions=permission_snapshot(f[1]);c={'excluded_roles':['service_executor']}
    for goal,n,state in [(P1,1,'COVERED_PREVIEW_ONLY'),(P5,5,'CONSTRAINT_BLOCKED')]:
        p=prep(f);r=update(f,p,[goal],c);assert r.status_code==200;r=r.json();p['revision']=r['revision'];v=preview(f,p)
        assert v['state']==state and v['required_goals']==[goal] and len(v['steps'])==n
        assert all(s['responsibility'] and s['preconditions'] and s['output'] and s['executable'] is False for s in v['steps'])
        result=adopt(f,p,v,[goal]);assert result.status_code==(201 if goal==P1 else 409),result.text
        if goal==P5:assert [s['constraint_impact']['state'] for s in v['steps']]==['COMPATIBLE','COMPATIBLE','CONFLICT','CONFLICT','CONFLICT']
    assert permission_snapshot(f[1])==permissions

@pytest.mark.parametrize('value',[None,{'excluded_roles':['admin']},{'unknown':'execute'},{'additional_requirements':['']},{'excluded_roles':['service_executor']*4}])
def test_invalid_constraint_contract_is_422_without_request_write(preparation_fixture,value):
    f=preparation_fixture;p=prep(f);r=update(f,p,[P1],value);assert r.status_code==422
    with f[1].connect() as c:assert c.execute('SELECT request_intent FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['request_intent'] is None

def test_preserve_constraints_on_omission_clear_explicitly_and_do_not_drop_required_goals(preparation_fixture):
    f=preparation_fixture;p=prep(f);r=update(f,p,[P1,P5],{'excluded_roles':['service_executor']});p['revision']=r.json()['revision'];before=preview(f,p)
    assert update(f,p,[P1],{}).status_code==409
    r=update(f,p,[P1,P5]);assert r.status_code==200;p['revision']=r.json()['revision'];assert preview(f,p)['state']=='CONSTRAINT_BLOCKED'
    assert before['source_sha256']!=preview(f,p)['source_sha256']
    r=update(f,p,[P1,P5],{});assert r.status_code==200;p['revision']=r.json()['revision'];assert preview(f,p)['state']=='COVERED_PREVIEW_ONLY'

def test_unsupported_requirement_and_stale_source_cannot_adopt(preparation_fixture):
    f=preparation_fixture;p=prep(f);r=update(f,p,[P1],{'additional_requirements':['SYNTHETIC external formal receipt']});p['revision']=r.json()['revision'];v=preview(f,p)
    assert v['state']=='PARTIAL' and v['required_goals']==[P1,'SYNTHETIC external formal receipt'] and v['constraint_evaluation']['unsupported_requirements']==['SYNTHETIC external formal receipt'];assert adopt(f,p,v,[P1]).status_code==409
    assert update(f,p,[P1],{}).status_code==409
    p=prep(f);r=update(f,p,[P1],{});p['revision']=r.json()['revision'];v=preview(f,p);r=update(f,p,[P1],{'excluded_roles':['park_specialist']});p['revision']=r.json()['revision'];assert adopt(f,p,v,[P1]).status_code==409

def test_legacy_fixed_plan_cannot_bypass_constraint_conflict(preparation_fixture):
    f=preparation_fixture;p=prep(f);goal='LOCAL_SYNTHETIC_COORDINATION_RECORDS';r=update(f,p,[goal],{'excluded_roles':['service_executor']});p['revision']=r.json()['revision']
    path='/api/preparations/'+p['preparation_id']+'/controlled-plan';view=f[3].get(path,headers=headers(f[2])).json();assert 'DECLARED_PLANNING_CONSTRAINT_CONFLICT' in view['creation_blockers'] and not view['can_create']
    r=f[3].post(path,headers=headers(f[2],key=uuid4().hex),json={'expected_preparation_revision':p['revision'],'template_sha256':cp.TEMPLATE_SHA,'required_goals':[goal]});assert r.status_code==409

def test_legacy_request_key_fingerprint_and_new_constraint_key_conflict(preparation_fixture):
    f=preparation_fixture;p=prep(f);key=uuid4().hex;r=update(f,p,[P1],key=key);assert r.status_code==200;assert update(f,p,[P1],key=key).json()==r.json();assert update(f,p,[P1],{},key).status_code==409


def test_omitted_constraint_two_step_goal_removal_bypass_is_rejected(preparation_fixture):
    f=preparation_fixture;p=prep(f);r=update(f,p,[P1,P5]);p['revision']=r.json()['revision']
    assert update(f,p,[P1]).status_code==409
    assert update(f,p,[P1],{'excluded_roles':['service_executor']}).status_code==409
    assert preview(f,p)['required_goals']==[P1,P5]


@pytest.mark.parametrize('mode',['pending_fields','dirty_constraint','empty403','nonjson403','read500','late403'])
def test_original_planning_constraint_guards(mode):
    import subprocess,json
    from pathlib import Path
    result=subprocess.run(['node',str(Path(__file__).with_name('planning_constraint_guards.js')),mode],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['checks']>=3


def test_role_order_is_canonical_for_ui_and_old_request_shape_replays_after_update(preparation_fixture):
    f=preparation_fixture;p=prep(f);key=uuid4().hex;old=update(f,p,[P1],key=key);p['revision']=old.json()['revision']
    r=update(f,p,[P1],{'excluded_roles':['service_executor','park_specialist','service_executor']});assert r.status_code==200
    assert r.json()['request_intent']['planning_constraints']['excluded_roles']==['park_specialist','service_executor']
    stale=dict(p,revision=1);assert update(f,stale,[P1],key=key).json()==old.json()
