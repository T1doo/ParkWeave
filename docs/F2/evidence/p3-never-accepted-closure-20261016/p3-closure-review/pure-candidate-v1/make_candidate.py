from pathlib import Path
import json,hashlib
base=Path('.runtime/p3-closure-review/pure-candidate-v1');records=[];provenance=[]
for p in sorted(Path('.runtime/p3-closure-root/dev/core01/p3-fixture').glob('positive-closed-history-original-tail-cold-get-*.json')):
 v=json.loads(p.read_text());context=v['new_receipt']['delivery_binding']['context'];records.append(dict(action=v['action'],qualification=v['qualification'],context={k:context[k] for k in ('preparation_id','case_id','run_id','owner_id','park_id','org_id')}));provenance.append(dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),action=v['action']))
header='''"""Independent pure strict-profile mutations of actual owned-PG proofs.

The two positive documents were captured by the parent core01 window. Their
embedded copy is a structural validation fixture only, not reusable PG evidence.
No DB, HTTP, credentials, grants, business writes or source monkeypatches.
"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID
import json
import pytest
from parkweave import p3_never_accepted_closure as closure, controlled_plans as cp
'''
body='''

FIELDS=[('birth','generation'),('verified_prefix',0,'step_id'),('verified_prefix',0,'event_id'),('verified_prefix',1,'step_id'),('verified_prefix',1,'event_id'),('dispatch','id'),('dispatch','current_offer_id'),('dispatch','events',0,'id'),('dispatch','events',0,'offer_id')]


def baseline():
 value=deepcopy(BASELINES[0]);q=value['qualification']
 return q,SimpleNamespace(expected_previous_plan_id=UUID(q['previous_plan_id'])),value['context']


def set_identifier(q,path,value):
 node=q
 for key in path[:-1]:node=node[key]
 node[path[-1]]=value
 if path==('birth','generation'):
  q['birth_sha256']=cp._hash(q['birth'])
  for event in q['dispatch']['events']:event['business_frontier']['generation']=value
 if path in (('dispatch','current_offer_id'),('dispatch','events',0,'offer_id')):
  q['dispatch']['current_offer_id']=value
  for event in q['dispatch']['events']:event['offer_id']=value


@pytest.mark.parametrize('index',[0,1],ids=['first-original-terminal','second-original-terminal'])
def test_actual_original_terminal_document_structure_is_accepted(index):
 value=deepcopy(BASELINES[index]);q=value['qualification']
 closure.validate_qualification(q,SimpleNamespace(expected_previous_plan_id=UUID(q['previous_plan_id'])),value['context'])


@pytest.mark.parametrize('path',FIELDS,ids=['birth-generation','p1-step','p1-event','p2-step','p2-event','dispatch-id','current-offer','event-id','offer-id'])
@pytest.mark.parametrize('mutation',['bool','float','none','list','dict','uppercase','hex','braced','urn'])
def test_nested_identifiers_require_exact_canonical_string(path,mutation):
 q,data,context=baseline();original=q
 for key in path:original=original[key]
 values=dict(bool=True,float=1.5,none=None,list=[original],dict={'id':original},uppercase=original.upper(),hex=UUID(original).hex,braced='{'+original+'}',urn='urn:uuid:'+original)
 assert values[mutation]!=original
 set_identifier(q,path,values[mutation])
 with pytest.raises(ValueError):closure.validate_qualification(q,data,context)


@pytest.mark.parametrize('mutation',['unknown','extra','schema-bool','epoch-bool','epoch-zero','ever-false','revision-bool','count-bool','missing-table','offered','accept'])
def test_closed_profile_cannot_downgrade_or_infer_unknown(mutation):
 q,data,context=baseline()
 if mutation=='unknown':q['state']='UNKNOWN'
 elif mutation=='extra':q['inferred_authority']=True
 elif mutation=='schema-bool':q['schema']=True
 elif mutation=='epoch-bool':q['epoch']=True
 elif mutation=='epoch-zero':q['epoch']=0;q['ever_started']=False
 elif mutation=='ever-false':q['ever_started']=False
 elif mutation=='revision-bool':q['dispatch']['revision']=True
 elif mutation=='count-bool':q['collections'][0]['count']=True
 elif mutation=='missing-table':q['collections'].pop()
 elif mutation=='offered':q['closure_state']='OFFERED'
 elif mutation=='accept':q['dispatch']['events'][-1]['action']='ACCEPT'
 with pytest.raises(ValueError):closure.validate_qualification(q,data,context)


def test_actual_product_module_loads_selected_source():
 root=Path(__file__).resolve()
 while not (root/'src/parkweave').is_dir():
  assert root!=root.parent
  root=root.parent
 assert Path(closure.__file__).resolve()==root/'src/parkweave/p3_never_accepted_closure.py'
'''
p=base/'test_p3_closure_review_pure.py';p.write_text(header+'\nBASELINES=json.loads('+repr(json.dumps(records,sort_keys=True))+')\n'+body)
(base/'provenance.json').write_text(json.dumps(dict(scope='PURE_STRUCTURE_FIXTURE_ONLY_NO_PG_SCORE_TRANSFER',sources=provenance),indent=2)+'\n')
rows=[dict(path=str(f),sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for f in sorted(base.glob('*')) if f.is_file()]
(base/'manifest.json').write_text(json.dumps(dict(status='IMMUTABLE_PURE_CANDIDATE_EXPECTS_STRICT_V3_VALIDATOR',test_count=95,files=rows),indent=2)+'\n');print(hashlib.sha256((base/'manifest.json').read_bytes()).hexdigest())
