"""Independent oracle helpers. No old runtime fixture or output roots are used."""
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
import hashlib, importlib, json, os
from test_preparation import headers
from test_service_case_steps import verified
from test_service_plan_manual_lock import stored
from test_resource_bundles import bundle
from test_case_resource_delivery import quoted, submit, recover, effects
from test_plan_source_reapproval import approved
from test_service_plan_approval import ledger

TABLES=('service_dispatches','service_dispatch_offers','service_dispatch_events',
        'service_receipt_steps','service_step_receipts','service_receipt_events',
        'case_local_lifecycles','case_local_events')
QUALIFICATION_KEYS={'schema','profile','state','preparation_id','case_id','run_id',
 'previous_plan_id','birth','birth_sha256','protocol_sha256','epoch','ever_started',
 'collection_bound','collections','verified_prefix','tail'}

def output():
 p=Path(os.environ.get('FRONTIER_ORACLE_ARTIFACT_ROOT','.runtime/frontier-oracle/artifacts')).resolve()
 assert 'plan-replacement' not in str(p)
 p.mkdir(parents=True,exist_ok=True);return p

def record(kind,value):
 p=output()/(kind+'-'+uuid4().hex+'.json')
 p.write_text(json.dumps(value,indent=2,default=str)+'\n');return p

def verify_imports():
 expected=Path(os.environ['FRONTIER_TEST_SOURCE_ROOT']).resolve()
 result={}
 for name in ('business_frontier','business_frontier_types','case_resource_delivery',
              'service_plan_approval','plan_replacement_compatibility',
              'service_dispatches','executor_receipts','case_lifecycle'):
  m=importlib.import_module('parkweave.'+name);p=Path(m.__file__).resolve()
  assert p.parent==expected,(name,str(p),str(expected))
  result[name]={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
 manifest=os.environ.get('FRONTIER_TEST_SOURCE_MANIFEST')
 if manifest:
  expected_hashes=json.loads(Path(manifest).read_text())
  expected_hashes=expected_hashes.get('source_paths',expected_hashes)
  for name,row in result.items():
   rel='src/parkweave/'+name+'.py';assert row['sha256']==expected_hashes[rel]
 record('actual-imports',result)

def snapshot(f,p):
 with f[1].connect() as c:
  row=c.execute('SELECT candidate_frontier_birth,candidate_business_frontier FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
  counts={t:c.execute('SELECT count(*) n FROM '+t).fetchone()['n'] for t in TABLES}
 return dict(birth=deepcopy(row['candidate_frontier_birth']),marker=deepcopy(row['candidate_business_frontier']),counts=counts)

def quote(x):
 f,p=x['f'],x['p'];hs,b=bundle(f)
 data=quoted(f,p,{**b,'expected_link_revision':1,'expected_previous_plan_id':x['old']['id'],'replacement_frontier_profile':'KNOWN_NOT_STARTED_V1'})
 return hs,data

def commit(x):
 f,p=x['f'],x['p'];hs,data=quote(x);item,_=approved(f,p,data)
 key=uuid4().hex;body={**data,'approval_id':item['id']};r=submit(f,p,body,key)
 assert r.status_code==201,r.text
 return dict(holds=hs,data=data,item=item,key=key,body=body,result=r.json())

def qualification(value):
 report=value['context']['plan_replacement']['compatibility']
 assert report['schema']==2 and report['profile']=='ORIGINAL_V4_SERVICE_RELEASE_KNOWN_NOT_STARTED_V1'
 assert set(report)=={'schema','profile','classification','previous_candidate_id','replacement_candidate_id',
  'previous_candidate_sha256','replacement_candidate_sha256','frozen_registry_sha256','pairs','affected',
  'preserved','automatic_adoption','automatic_approval','automatic_release','qualification'}
 q=report['qualification'];assert set(q)==QUALIFICATION_KEYS
 assert type(q['schema']) is int and q['schema']==1
 assert q['state']=='KNOWN_NOT_STARTED' and type(q['epoch']) is int and q['epoch']==0
 assert q['ever_started'] is False
 assert {r['table'] for r in q['collections']}==set(TABLES) and len(q['collections'])==8
 assert all(r==dict(table=r['table'],count=0,complete=True,known=True,sha256=hashlib.sha256(b'[]').hexdigest()) for r in q['collections'])
 assert [p['adapter_id'] for p in q['verified_prefix']]==['P1','P2']
 return q


def dispatch_catalog_get(x,user='prep-specialist-fixture-a'):
 f,p=x['f'],x['p'];r=f[3].get('/api/service-dispatches/catalog',headers=headers(f[2],user),params={'preparation_id':p['preparation_id']})
 assert r.status_code==200,r.text;return r.json()

def offer_body(x):
 row=dispatch_catalog_get(x);fence=deepcopy(row['business_frontier'])
 assert set(fence)=={'generation','preparation_id','plan_id','plan_revision','epoch'}
 return dict(expected_preparation_revision=row['preparation_revision'],expected_dispatch_revision=row['dispatch_revision'],
  executor_id='executor-a',reason='SYNTHETIC independent explicit current-plan OFFER',expected_business_frontier=fence)


def offer_post(x,body,key=None,user='prep-specialist-fixture-a'):
 f,p=x['f'],x['p'];return f[3].post('/api/preparations/'+p['preparation_id']+'/dispatch',headers=headers(f[2],user,key or uuid4().hex),json=body)

def tail(x):
 from test_service_dispatches import command as dispatch_command
 from test_executor_receipts import act as receipt_action
 from test_case_lifecycle import read as local_read,act as local_action
 from test_case_goal_results import get as goals
 f,p=x['f'],x['p'];verified(f,p,'P2')
 r=offer_post(x,offer_body(x));assert r.status_code==201,r.text
 offered=r.json();r=dispatch_command(f,offered,'ACCEPT',expected_business_frontier=offered['business_frontier']);assert r.status_code==200,r.text
 accepted=r.json();verified(f,p,'P3')
 r=f[3].get('/api/executor-receipts/'+accepted['receipt_step_id'],headers=headers(f[2],'executor-a'));assert r.status_code==200,r.text
 row=r.json();r=receipt_action(f,row,'SUBMIT',expected_business_frontier=row['business_frontier']);assert r.status_code==200,r.text
 row=r.json();r=receipt_action(f,row,'ACKNOWLEDGE',expected_business_frontier=row['business_frontier']);assert r.status_code==200,r.text
 verified(f,p,'P4');r=local_read(f,p);assert r.status_code==200,r.text
 row=r.json();r=local_action(f,p,row,'REVALIDATE',expected_business_frontier=row['business_frontier']);assert r.status_code==200,r.text
 verified(f,p,'P5');g=goals(f,p);assert g.status_code==200,g.text
 record('full-goal-results',g.json())
 assert g.json()['state']=='LOCAL_OUTPUTS_VERIFIED' and len(g.json()['results'])==6
 assert all(row['state']=='LOCAL_OUTPUT_VERIFIED' for row in g.json()['results'])
 assert not g.json()['case_goal_completed']
 w=f[3].get('/api/cases/worklist',headers=headers(f[2]),params={'limit':1});assert w.status_code==200,w.text
 assert w.json()['read_only'] and w.json()['recorded_states_only']
 hit=next(row for row in w.json()['items'] if row['case_id']==p['case_id'])
 assert hit['preparation_id']==p['preparation_id'] and not hit['evidence_verified'] and not hit['case_goal_completed']
 return accepted
