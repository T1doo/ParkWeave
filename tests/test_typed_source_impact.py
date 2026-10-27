"""Literal impact answers, old history compilers, and real owner HTTP reads."""
from copy import deepcopy
from uuid import uuid4
import json
import pytest
from psycopg.types.json import Jsonb
from parkweave import typed_source_impact as typed, registered_dependencies as deps, controlled_plans as cp
from parkweave import source_change_adoption as adoption
from test_registered_local_revision import http_f,link_fixture,receipt_fixture,preparation_fixture,add_resource
from test_service_case_steps import read,adopt,step,setup,GOALS,verified
from test_case_goal_results import complete,snapshot,get
from test_service_plan_manual_lock import stored,lock
from test_source_change_adoption import changed,preview
from test_preparation import headers
from test_service_plan_recovery import recover


def sample():
    parent={k:str(uuid4()) for k in ('id','case_id','run_id')}
    parent.update(owner_id='owner',park_id='park',org_id='org',service_id='service',namespace='SYNTHETIC')
    steps=[dict(id=str(uuid4()),adapter_id='P'+str(i),depends_on=[] if i==1 else ['P'+str(i-1)]) for i in range(1,6)]
    plan=dict(id=str(uuid4()),steps=steps)
    sources={s['adapter_id']:{'preparation_revision':1,'preparation_sha256':'a'*64} for s in steps[:-1]}
    sources['P5']={'sources':{'preparation_revision':1,'preparation_sha256':'a'*64},'local_lifecycle':None}
    values={name:dict(known=True,count=1,sha256='a'*64) for name in ('resources','existing_access')}
    manifest=deps.manifest(steps,values)
    return parent,plan,sources,manifest


def literal_ids(plan,adapters):return [s['id'] for s in plan['steps'] if s['adapter_id'] in adapters]


@pytest.mark.parametrize('adapter,field,value,expected',[
 ('P1','preparation_revision',2,('P1','P2','P3','P4','P5')),
 ('P1','fact_clarification',{'satisfied':True,'source_sha256':'b'*64},('P1','P2','P3','P4','P5')),
 ('P2','resource_collection',{'known':True,'count':2,'sha256':'b'*64},('P2','P3','P4','P5')),
 ('P3','dispatch_revision',2,('P3','P4','P5')),
 ('P4','receipt_sha256','b'*64,('P4','P5')),
 ('P5','local_lifecycle',{'cycle':2},('P5',)),
])
def test_pure_group_differences_follow_literal_existing_step_answers(adapter,field,value,expected):
    parent,plan,before,manifest=sample();current=deepcopy(before);current[adapter][field]=value
    graph=typed.build(parent,plan,before,current,manifest,manifest)
    assert graph['unknown_scope'] is None and graph['affected']==literal_ids(plan,expected)
    assert graph['preserved']==literal_ids(plan,set(('P1','P2','P3','P4','P5'))-set(expected))
    assert graph['changed_node_ids'] and len({n['id'] for n in graph['nodes']})==len(graph['nodes'])
    assert graph['step_endpoints']==[dict(id=s['id'],type='PLAN_STEP',adapter_id=s['adapter_id']) for s in plan['steps']]
    assert graph['sha256']==cp._hash({k:v for k,v in graph.items() if k!='sha256'})
    original=typed.build(parent,plan,before,before,manifest,manifest)
    assert [n['id'] for n in graph['nodes']]==[n['id'] for n in original['nodes']]
    assert all(n['aggregate'] is True for n in graph['nodes'])


def test_unknown_field_is_hashed_and_expands_this_case_without_echo_or_authority():
    parent,plan,before,manifest=sample();current=deepcopy(before)
    poison='PRIVATE_ASSERTION_BODY_TOKEN';current['P4'][poison]={'value':poison}
    graph=typed.build(parent,plan,before,current,manifest,manifest)
    assert graph['unknown_scope']=='THIS_CASE' and graph['affected']==literal_ids(plan,('P1','P2','P3','P4','P5'))
    assert graph['unknown_reasons']==['UNMAPPED_SOURCE_FIELDS'] and poison not in json.dumps(graph)
    assert not next(n for n in graph['nodes'] if n['facet']=='UNMAPPED_SOURCE_FIELDS')['known']


@pytest.mark.parametrize('malformed',[None,'PRIVATE_BAD_SHAPE',{},[None]])
def test_bad_resource_group_shape_is_unknown_instead_of_server_error(malformed):
    parent,plan,before,manifest=sample();current=deepcopy(before);current['P2']['resource_rules']=malformed
    graph=typed.build(parent,plan,before,current,manifest,manifest)
    assert graph['unknown_scope']=='THIS_CASE' and 'SOURCE_GROUP_SHAPE_UNAVAILABLE' in graph['unknown_reasons']
    assert 'PRIVATE_BAD_SHAPE' not in json.dumps(graph)
    assert next(n for n in graph['nodes'] if n['facet']=='RESOURCE_RULES')['date_evidence']['current']['state']=='UNKNOWN'


def test_missing_baseline_and_lost_p5_shape_are_never_empty_unchanged():
    parent,plan,before,manifest=sample();current=deepcopy(before);before.pop('P3')
    graph=typed.build(parent,plan,before,current,manifest,manifest)
    assert graph['unknown_scope']=='THIS_CASE' and not graph['preserved']
    parent,plan,before,manifest=sample();current=deepcopy(before);current['P5'].pop('sources')
    graph=typed.build(parent,plan,before,current,manifest,manifest)
    assert graph['unknown_scope']=='THIS_CASE' and not graph['preserved']


def test_absent_dates_do_not_invent_unknown_impact_or_material_slot_ids():
    parent,plan,before,manifest=sample();graph=typed.build(parent,plan,before,before,manifest,manifest)
    node=next(n for n in graph['nodes'] if n['facet']=='MATERIAL_PACKAGE')
    assert node['date_evidence']['before']['state']=='UNKNOWN'
    assert graph['unknown_scope'] is None and not graph['affected']
    assert set(node['fields'])=={'preparation_revision','preparation_sha256'}
    assert not {'value','sources','assertion_id','material_id','slot'} & set(node)


def impact(f,p,user='fixture-a'):
    return f[3].get('/api/preparations/'+p['preparation_id']+'/source-impact',headers=headers(f[2],user))


def test_real_owner_without_any_opportunity_can_inspect_current_case_without_writes(http_f):
    f=http_f;p,g,d,s=complete(f,local=True);before=snapshot(f)
    response=impact(f,p);assert response.status_code==200,response.text;view=response.json()
    assert view['read_only'] and view['state']=='UNCHANGED' and view['current_source_available'] is True
    assert view['qualification_decision']=='NOT_EVALUATED' and not view['source_impact']['unknown_scope']
    assert not view['source_impact']['affected'] and snapshot(f)==before
    assert all(n['fields']!=['material_id'] for n in view['source_impact']['nodes'])
    add_resource(f);before=snapshot(f);x=impact(f,p).json()
    assert x['state']=='CHANGED' and x['source_impact']['affected']==literal_ids(stored(f,p),('P2','P3','P4','P5')) and snapshot(f)==before


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a'])
def test_new_reader_reuses_current_owner_scope_and_never_shares_graph(http_f,user):
    f=http_f;p,g,d,s=complete(f);before=snapshot(f);response=impact(f,p,user)
    assert response.status_code==403 and 'source_impact' not in response.text and snapshot(f)==before


def test_no_plan_is_distinct_from_missing_verified_baseline(http_f):
    f=http_f;p=setup(f,GOALS[0]);r=impact(f,p);assert r.status_code==200 and r.json()['state']=='NO_PLAN' and r.json()['source_impact'] is None
    assert adopt(f,p).status_code==201;before=snapshot(f);r=impact(f,p);assert r.status_code==200
    assert r.json()['state']=='UNKNOWN' and r.json()['source_impact']['unknown_scope']=='THIS_CASE' and snapshot(f)==before


def test_real_v2_graph_binds_adopt_and_frozen_schema_survives_new_current_compiler(http_f,monkeypatch):
    f=http_f;p,g,d,s=complete(f,local=True);assert lock(f,p,'P1').status_code==200;card=changed(f,p)
    x=preview(f,p,card).json();assert x['can_adopt'] and x['source_impact']['schema']==1
    old=stored(f,p);key=uuid4().hex;r=adopt(f,p,x['adoption'],key);assert r.status_code==201,r.text
    now=stored(f,p);change=now['events'][-1]['local_revision']['source_change']
    assert change['version']==2 and change['source_impact']==x['source_impact'] and now['steps'][0]==old['steps'][0]
    original=typed.build
    def future(*args,**kwargs):raise AssertionError('current compiler must not reinterpret schema 1 history')
    monkeypatch.setattr(typed,'build',future);assert read(f,p).status_code==200 and recover(f,p,key).status_code==200 and get(f,p).status_code==200
    monkeypatch.setattr(typed,'build',original)
    for adapter in ('P2','P3','P4','P5'):verified(f,p,adapter)
    assert get(f,p).json()['state']=='LOCAL_OUTPUTS_VERIFIED' and now['steps'][0]==stored(f,p)['steps'][0]


def test_preview_rejects_typed_partition_mismatch_before_saving_any_event(http_f,monkeypatch):
    f=http_f;p,g,d,s=complete(f);card=changed(f,p);original=typed.build
    def wrong(*args,**kwargs):
        graph=original(*args,**kwargs);graph['affected']=[];graph['preserved']=[s['id'] for s in stored(f,p)['steps']];return graph
    monkeypatch.setattr(typed,'build',wrong);before=snapshot(f)
    assert preview(f,p,card).status_code==409 and snapshot(f)==before


def test_v1_source_change_history_still_uses_original_algorithm_without_graph(http_f,monkeypatch):
    from parkweave.service_case_steps import Adopt,_adopt_request
    f=http_f;p,g,d,s=complete(f);card=changed(f,p);x=preview(f,p,card).json();key=uuid4().hex
    assert adopt(f,p,x['adoption'],key).status_code==201
    plan=stored(f,p);event=plan['events'][-1];change=event['local_revision']['source_change']
    change['version']=1;change.pop('source_impact');change['sha256']=cp._hash({k:v for k,v in change.items() if k!='sha256'})
    request=event['local_revision']['request'];request['opportunity_proof']['expected_preview_sha256']=change['sha256']
    event['fingerprint']=cp._hash(dict(preparation_id=p['preparation_id'],action='ADOPT',**_adopt_request(Adopt.model_validate(request))))
    with f[1].connect() as c:c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),p['preparation_id']))
    monkeypatch.setattr(typed,'build_v1',lambda *args,**kwargs:(_ for _ in ()).throw(AssertionError('v1 source proof has no graph')))
    assert read(f,p).status_code==200 and recover(f,p,key).status_code==200 and get(f,p).status_code==200


@pytest.mark.parametrize('replacement',[True,1.0])
def test_scalar_type_change_never_disappears_behind_python_numeric_equality(replacement):
    parent,plan,before,manifest=sample();current=deepcopy(before);current['P1']['preparation_revision']=replacement
    graph=typed.build(parent,plan,before,current,manifest,manifest)
    node=next(n for n in graph['nodes'] if n['adapter_id']=='P1' and n['facet']=='MATERIAL_PACKAGE')
    assert node['before_sha256']!=node['current_sha256'] and node['changed']
    assert graph['unknown_scope']=='THIS_CASE' and graph['unknown_reasons']==['SOURCE_PARTITION_UNEXPLAINED']
    assert graph['affected']==literal_ids(plan,('P1','P2','P3','P4','P5')) and not graph['preserved']
