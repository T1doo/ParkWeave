"""Literal scoped query fingerprints and original dependency partitions."""
from copy import deepcopy
import hashlib
import json
import pytest
from parkweave import service_catalog_dependencies as query, registered_dependencies as deps
from parkweave.store import Conflict

def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def row(n=1):return dict(park_id='park-a',service_id='service-a',version=n,name='SYNTHETIC '+str(n),
    source=dict(kind='SYNTHETIC',id='source-a',revision=str(n)),namespace='SYNTHETIC',qualification='NOT_EVALUATED')
class Connection:
    def __init__(self,rows):self.rows=rows;self.calls=[]
    def execute(self,sql,args):self.calls.append((sql,args));return self
    def fetchall(self):return deepcopy(self.rows)
def collect(rows):
    c=Connection(rows);v=query.collection(c,dict(park_id='park-a',service_id='service-a'))
    assert len(c.calls)==1 and c.calls[0][1]==('park-a','service-a')
    assert 'ORDER BY version LIMIT 33' in c.calls[0][0] and 'FOR ' not in c.calls[0][0]
    return v
def values(catalog):return dict(resources=dict(known=True,count=0,sha256='a'*64),existing_access=dict(known=True,count=0,sha256='b'*64),service_catalog=catalog)
STEPS=[dict(id='one',adapter_id='P1',depends_on=[]),dict(id='two',adapter_id='P2',depends_on=['P1']),dict(id='three',adapter_id='P3',depends_on=[])]

def test_exact_literal_original_query_and_existing_namespace_filter():
    original=row();excluded=row(3);excluded['namespace']='REAL'
    want=[dict(service_id='service-a',version=1,name='SYNTHETIC 1',source_sha256=digest(original['source']),publication_head=None)]
    assert collect([original,excluded])==dict(known=True,count=1,sha256=digest(want))

@pytest.mark.parametrize('change',['insert','remove','source'])
def test_unmatched_query_version_changes_original_p1_closure_only(change):
    before=[row()] if change=='insert' else [row(),row(2)];after=deepcopy(before)
    if change=='insert':after.append(row(2))
    elif change=='remove':after.pop()
    else:after[-1]['source']['revision']='3'
    a=deps.manifest(STEPS,values(collect(before)));b=deps.manifest(STEPS,values(collect(after)))
    assert a['version']==b['version']==2
    assert deps.impact_between(STEPS,a,b)==({'P1','P2'},False)
    assert deps.inspect(dict(steps=STEPS,dependency_manifest=a),values(collect(before)))[1:]==(set(),False)

def test_32_complete_33_unknown_and_damaged_publication_never_known():
    assert collect([row(n) for n in range(1,33)])['known']
    x=collect([row(n) for n in range(1,34)]);assert x['known'] is False and x['count']==33
    v=deps.manifest(STEPS,values(x));deps.validate(v)
    assert deps.impact_between(STEPS,deps.manifest(STEPS,values(collect([row()]))),v)==({'P1','P2','P3'},True)
    for count in (34,True):
        bad=deepcopy(v);bad['collections']['service_catalog']['count']=count;bad['sha256']=digest({k:v for k,v in bad.items() if k!='sha256'})
        with pytest.raises(Conflict):deps.validate(bad)
    bad=row();bad['candidate_catalog_head']={'state':'WITHDRAWN'}
    with pytest.raises(Conflict):collect([bad])

def test_original_v1_manifest_bytes_and_unknown_v2_registration_boundary():
    original=values(collect([row()]));original.pop('service_catalog')
    v1=deps.manifest(STEPS,original)
    literal=dict(version=1,declarations={a:deepcopy(deps.DECLARATIONS_V1[a]) for a in ('P1','P2','P3')},
        edges=[dict(upstream='P1',downstream='P2',kind='PRECEDES',provenance='COMPILED_REGISTERED_ADAPTER')],collections=original)
    assert v1==dict(**literal,sha256=digest(literal));deps.validate(v1)
    v2=deps.manifest(STEPS,values(collect([row()])));assert deps.impact_between(STEPS,v1,v2)==({'P1','P2','P3'},True)
    bad=deepcopy(v2);bad['collections'].pop('service_catalog');bad['sha256']=digest({k:v for k,v in bad.items() if k!='sha256'})
    with pytest.raises(Conflict):deps.validate(bad)
