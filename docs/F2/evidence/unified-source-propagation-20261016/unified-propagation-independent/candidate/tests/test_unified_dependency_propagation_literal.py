"""Independent frozen literal partitions, never computed by product closure."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from uuid import uuid4
import pytest
from parkweave import unified_dependency_propagation as unified
from parkweave import registered_dependencies as deps

ALL=('P1','P2','P3','P4','P5')
LITERAL={
 'UP01':((),ALL,None), 'UP02':(('P4','P5'),('P1','P2','P3'),None),
 'UP03':(('P3','P4','P5'),('P1','P2'),None), 'UP04':(('P2','P3','P4','P5'),('P1',),None),
 'UP05':(('P2','P3','P4','P5'),('P1',),None), 'UP06':(ALL,(),None), 'UP07':(ALL,(),None),
 'UP08':(ALL,(),None), 'UP09':(ALL,(),None), 'UP10':(('P2','P3','P4','P5'),('P1',),None),
 'UP11':(('P3','P4','P5'),('P1','P2'),None), 'UP12':(('P2','P3','P4','P5'),('P1',),None),
 'UP13':(('P2','P3','P4','P5'),('P1',),None), 'UP14':(('P5',),('P1','P2','P3','P4'),None),
 'UP15':(('P5',),('P1','P2','P3','P4'),None), 'UP16':(('P5',),('P1','P2','P3','P4'),None),
 'UP17':(('P5',),('P1','P2','P3','P4'),None),
 **{k:(ALL,(),'THIS_CASE') for k in ('UP18','UP19','UP20','UP21','UP22','UP23','UP24')},
}


def sha(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def sample():
    parent={k:str(uuid4()) for k in ('id','case_id','run_id')}
    parent.update(owner_id='owner',park_id='park',org_id='org',service_id='service',namespace='SYNTHETIC')
    steps=[dict(id=str(uuid4()),adapter_id=a,depends_on=[] if a=='P1' else ['P'+str(int(a[1])-1)]) for a in ALL]
    plan=dict(id=str(uuid4()),steps=steps)
    values={a:dict(preparation_revision=2,preparation_sha256='b'*64) for a in ALL[:-1]}
    values['P1']['fact_clarification']=dict(satisfied=True,source_sha256='b'*64)
    values['P2']['resource_rules']=[dict(revision=2)]
    values['P2']['resource_link_revision']=2
    values['P3']['dispatch_revision']=2
    values['P4']['receipt_sha256']='b'*64
    values['P5']=dict(sources=dict(preparation_revision=2,preparation_sha256='b'*64,
         fact_clarification=dict(satisfied=True,source_sha256='b'*64),resource_link_revision=2),local_lifecycle=None)
    manifest=deps.manifest(steps,{k:dict(known=True,count=1,sha256='a'*64) for k in ('resources','existing_access')})
    return parent,plan,deepcopy(values),deepcopy(values),manifest,deepcopy(manifest)


def scenario(name):
    p,plan,b,c,dm,cm=sample()
    def old_material(a):
        v=b[a]['sources'] if a=='P5' else b[a];v.update(preparation_revision=1,preparation_sha256='a'*64)
    def old_fact(a):
        v=b[a]['sources'] if a=='P5' else b[a];v['fact_clarification']=dict(satisfied=True,source_sha256='a'*64)
    if name in ('UP02','UP05','UP06','UP12'):b['P4']['receipt_sha256']='a'*64
    if name=='UP03':b['P3']['dispatch_revision']=1
    if name in ('UP04','UP05'):b['P2']['resource_rules']=[dict(revision=1)]
    if name in ('UP06','UP09'):b['P1']['service_catalog']={'revision':1};c['P1']['service_catalog']={'revision':2}
    if name=='UP07':old_fact('P1');old_fact('P5')
    if name=='UP08':
        for a in ALL:old_material(a)
    if name=='UP09':old_material('P1');old_fact('P1')
    if name in ('UP10','UP12'):cm['collections']['resources'].update(count=2,sha256='b'*64)
    if name in ('UP11','UP12'):cm['collections']['existing_access'].update(count=2,sha256='b'*64)
    if name=='UP13':old_material('P2')
    if name=='UP14':old_fact('P5')
    if name=='UP15':old_material('P5')
    if name=='UP16':b['P5']['sources']['resource_link_revision']=1
    if name=='UP17':c['P5']['local_lifecycle']={'cycle':2}
    if name=='UP18':b.pop('P3')
    if name=='UP19':c['P4']['PRIVATE_UNMAPPED_FIELD']={'value':'PRIVATE_UNMAPPED_VALUE'}
    if name=='UP20':cm['collections']['resources']['known']=False
    if name=='UP21':cm['version']=2
    if name=='UP22':c['P5'].pop('sources')
    if name=='UP23':c['P2']['resource_rules']=['PRIVATE_BAD_RULE_SHAPE']
    if name=='UP24':c['P1']['fact_clarification']['satisfied']=False
    cm['sha256']=sha({k:v for k,v in cm.items() if k!='sha256'})
    return p,plan,b,c,dm,cm


@pytest.mark.parametrize('oracle_id',list(LITERAL))
def test_frozen_literal_partitions_and_consumer_observation_seeds(oracle_id):
    args=scenario(oracle_id);plan=args[1];q=unified.build_v1(*args);ea,ep,unknown=LITERAL[oracle_id]
    ids={s['adapter_id']:s['id'] for s in plan['steps']}
    assert q['schema']==2 and q['scope']=='BOUNDED_MULTI_SOURCE_V1'
    assert q['affected']==[ids[a] for a in ea] and q['preserved']==[ids[a] for a in ep]
    assert q['unknown_scope']==unknown
    assert q['sha256']==sha({k:v for k,v in q.items() if k!='sha256'})
    assert not q['automatic_execution'] and not q['new_grants']
    assert 'PRIVATE_' not in json.dumps(q)
    assert len({n['id'] for n in q['nodes']})==len(q['nodes'])<=96
    assert len({o['id'] for o in q['observations']})==len(q['observations'])<=96
    assert len({e['id'] for e in q['edges']})==len(q['edges'])<=128
    if oracle_id in ('UP13','UP14','UP15','UP16'):
        facet={'UP13':'MATERIAL_PACKAGE','UP14':'FACT_PURPOSE_BINDING','UP15':'MATERIAL_PACKAGE','UP16':'RESOURCE_ASSOCIATION'}[oracle_id]
        n=next(n for n in q['nodes'] if n['facet']==facet)
        obs=[o for o in q['observations'] if o['source_node_id']==n['id']]
        changed=[o for o in obs if o['changed']]
        expected='P2' if oracle_id=='UP13' else 'P5'
        assert len(changed)==1 and changed[0]['step_id']==ids[expected]
        assert any(not o['changed'] and o['step_id']!=ids[expected] for o in obs)
        assert all(x['step_id']!=ids['P1'] for x in q['propagation_paths'])
        assert all(x['observation_id'] in {o['id'] for o in q['observations'] if o['changed']} for x in q['propagation_paths'])
        assert all(x['edge_ids'][0] in {e['id'] for e in q['edges'] if e.get('observation_id')==x['observation_id']} for x in q['propagation_paths'])
