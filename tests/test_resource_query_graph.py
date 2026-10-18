"""Literal member outcomes over original saved rows, plus actual scoped API."""
from copy import deepcopy
from uuid import UUID
import pytest
from parkweave import resource_query_graph as rg,controlled_plans as cp,dependency_graph as dg

R1='00000000-0000-0000-0000-000000000101'
R2='00000000-0000-0000-0000-000000000102'
R3='00000000-0000-0000-0000-000000000103'
CASE='00000000-0000-0000-0000-000000000010'
PLAN='00000000-0000-0000-0000-000000000020'
STEPS={name:f'00000000-0000-0000-0000-00000000020{i}' for i,name in enumerate(('P1','P2','P3','P4','P5'),1)}
PARENT=dict(owner_id='fixture-a',park_id='park-a',org_id='org-a',case_id=CASE)
PLAN_VALUE=dict(id=PLAN,steps=[dict(id=STEPS[a],adapter_id=a,depends_on=[] if a=='P1' else
    ['P1','P2','P3','P4'] if a=='P5' else ['P'+str(int(a[1])-1)]) for a in STEPS])


def rule(id):return dict(id=id,revision=1,source={'kind':'SYNTHETIC','id':'literal-original','revision':'1'},
    capacity=2,buffer_seconds=0,open_from='2026-01-01T00:00:00+00:00',
    open_until='2099-01-01T00:00:00+00:00',enabled=True,namespace='SYNTHETIC',authority='LOCAL_AUTHORITY')
def query(rules):
    return sorted([{**{k:r[k] for k in rg.RESOURCE_FIELDS},'capability':cap,'active':True}
        for r in rules for cap in ('READ','HOLD')],key=lambda r:(r['id'],r['capability']))
def source(rules):
    rows=query(rules)
    return dict(resource_rules=deepcopy(rules),resource_grants=[dict(resource_id=r['id'],capability=cap,active=True)
        for r in rules for cap in ('READ','HOLD')],resource_collection=dict(known=True,count=len(rows),sha256=cp._hash(rows)))
def preview(old,rows,plan=None):
    return rg.preview(PARENT,plan or PLAN_VALUE,old,rows,
        dict(known=True,count=len(rows),sha256=cp._hash(rows)),{'literal_original_binding':'test-only'},[])
def members(g):return {n['id'][9:] for n in g['nodes'] if n['type']=='RESOURCE'}


@pytest.mark.parametrize('operation',['added','removed','rule','partial','same_true_duplicates','false_row','false_absent','contradictory','missing'])
def test_original_evidence_literal_membership_and_paths(operation,monkeypatch):
    rules=[rule(R1),rule(R2)];old=source(rules);current=query(rules);known=True;added=[];removed=[];changed=[]
    if operation=='added':current=query(rules+[rule(R3)]);added=[R3]
    elif operation=='removed':current=query(rules[:1]);removed=[R2]
    elif operation=='rule':rules[1]['capacity']=3;current=query(rules);changed=[R2]
    elif operation=='partial':old['resource_collection']=source(rules+[rule(R3)])['resource_collection'];current=query(rules+[rule(R3)]);known=False
    elif operation=='same_true_duplicates':old['resource_grants']+=deepcopy(old['resource_grants'])
    elif operation in ('false_row','false_absent'):
        old['resource_grants'][1]['active']=False
        prior=query(rules)
        if operation=='false_row':prior[0]['active']=False;known=False
        else:prior=prior[1:]
        old['resource_collection']=dict(known=True,count=len(prior),sha256=cp._hash(prior))
        current=prior
    elif operation=='contradictory':old['resource_grants'].append({**old['resource_grants'][0],'active':False});known=False
    elif operation=='missing':old={};known=False
    def forbidden(*args,**kwargs):raise AssertionError('raw member adapter must not use old schema2 conversion')
    monkeypatch.setattr(dg,'from_unified_v1',forbidden)
    saved=deepcopy(old);x=preview(old,current);assert old==saved
    assert x['membership']['state']==('KNOWN' if known else 'UNKNOWN')
    assert x['membership']['added']==added and x['membership']['removed']==removed
    assert x['membership']['changed']==changed
    assert x['before']['graph_id']==x['current']['graph_id']=='resource-query:'+PLAN
    assert x['before']['scope']==dict(park_id='park-a',org_id='org-a',package_id=PLAN)
    assert x['membership']['semantics']=='QUERY_MEMBERSHIP_ONLY'
    assert x['can_adopt'] is x['execution_authorized'] is x['new_grants'] is False
    if operation=='partial':
        assert R3 not in members(x['before']) and R3 in members(x['current'])
        assert x['membership']['newly_observed']==[R3] and not x['membership']['added']
    if operation in ('added','removed','rule','partial','false_row','contradictory','missing'):
        assert STEPS['P1'] in x['impact']['preserved']
        assert set(STEPS.values())-{STEPS['P1']}<=set(x['impact']['affected'])
    if not known:assert set(STEPS.values())-{STEPS['P1']}<=set(x['impact']['uncertain'])
    if operation=='false_row':assert x['membership']['observation_changed']==[R1] and not x['membership']['changed']
    if operation in ('added','removed'):
        id='resource:'+(R3 if operation=='added' else R2);g=x['current' if operation=='added' else 'before']
        edge=next(e for e in g['edges'] if e['upstream']==id);assert edge['downstream']==x['query_node_id'] and edge['kind']=='CAPACITY'
        assert any(e['upstream']==x['query_node_id'] and e['downstream']==STEPS['P2'] for e in g['edges'])
        witness=next(r for r in x['impact']['propagation_reasons'] if r['node_id']==STEPS['P5'] and r['certainty']=='DEFINITE')
        assert witness['path'] and witness['path'][-1]['downstream']==STEPS['P5']


def test_strict_boundaries_and_no_invented_consumer():
    old=source([rule(R1),rule(R2)])
    for n in (97,129):
        rows=query([rule(str(UUID(int=1000+i))) for i in range(n)])
        with pytest.raises(dg.GraphError):preview(old,rows)
    with pytest.raises(dg.GraphError):preview(old,query([rule(R1)])*2)
    with pytest.raises(dg.GraphError):preview(old,query([rule(R1)]),{'id':PLAN,'steps':[PLAN_VALUE['steps'][0]]})
    for value in (1,'true'):
        bad=deepcopy(old);bad['resource_grants'][0]['active']=value
        assert not preview(bad,query([rule(R1),rule(R2)]))['before_basis']['complete']
    changed=deepcopy(old);changed['resource_rules'].append({**changed['resource_rules'][0],'capacity':999})
    assert not preview(changed,query([rule(R1),rule(R2)]))['before_basis']['complete']
    unmatched=deepcopy(old);unmatched['resource_grants'].append(dict(resource_id=R3,capability='READ',active=True))
    assert not preview(unmatched,query([rule(R1),rule(R2)]))['before_basis']['complete']
