"""One exact pure boundary:96 accepted,97 refused; no fixture or authority."""
from copy import deepcopy
from hashlib import sha256
import json
from uuid import UUID
import pytest
from parkweave import resource_query_graph as product,dependency_graph

def digest(value):return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def make(n):
    rules=[dict(id=str(UUID(int=10000+i)),revision=1,source={'kind':'SYNTHETIC','id':'independent-boundary'},capacity=2,buffer_seconds=0,open_from='2026-01-01T00:00:00+00:00',open_until='2099-01-01T00:00:00+00:00',enabled=True,namespace='SYNTHETIC',authority='LOCAL_AUTHORITY') for i in range(n)]
    fields=('id','revision','source','capacity','buffer_seconds','open_from','open_until','enabled')
    rows=sorted([{**{k:r[k] for k in fields},'capability':cap,'active':True} for r in rules for cap in ('READ','HOLD')],key=lambda r:(r['id'],r['capability']))
    stamp=dict(known=True,count=len(rows),sha256=digest(rows))
    old=dict(resource_rules=rules,resource_grants=[dict(resource_id=r['id'],capability=cap,active=True) for r in rules for cap in ('READ','HOLD')],resource_collection=stamp)
    return old,rows,stamp

def test_exact_96_member_acceptance_then_97_rejection_without_partial_result():
    parent=dict(owner_id='owner',park_id='park',org_id='org',case_id='case')
    plan=dict(id='plan',steps=[dict(id='P1',adapter_id='P1',depends_on=[]),dict(id='P2',adapter_id='P2',depends_on=['P1'])])
    old,current,stamp=make(96);saved=deepcopy((old,current,stamp))
    value=product.preview(parent,plan,old,current,stamp,{'independent':'boundary-only'},[])
    assert value['before_basis']['complete'] is value['current_basis']['complete'] is True
    assert value['before_basis']['member_count']==value['current_basis']['member_count']==96
    assert value['membership']['state']=='KNOWN' and value['impact']['affected']==[]
    assert len([n for n in value['current']['nodes'] if n['type']=='RESOURCE'])==96
    assert (old,current,stamp)==saved
    _,overflow,overflow_stamp=make(97)
    with pytest.raises(dependency_graph.GraphError):product.preview(parent,plan,old,overflow,overflow_stamp,{},[])
