"""Independent current-source/actual-row helpers; only new P3 closure outputs."""
from pathlib import Path
from uuid import uuid4
from copy import deepcopy
import hashlib,importlib,json,os
from test_preparation import headers

PROFILE='P3_NEVER_ACCEPTED_CLOSED_V1'
TABLES=('service_dispatches','service_dispatch_offers','service_dispatch_events','service_receipt_steps',
        'service_step_receipts','service_receipt_events','case_local_lifecycles','case_local_events')
QKEYS={'schema','profile','state','preparation_id','case_id','run_id','previous_plan_id','birth',
 'birth_sha256','protocol_sha256','epoch','ever_started','collection_bound','collections','verified_prefix',
 'tail','closure_state','dispatch','marker_sha256'}
DKEYS={'id','revision','current_offer_id','state','offers_count','events_count','history_sha256','events'}
EKEYS={'id','revision','action','offer_id','actor_id','request_key','fingerprint','payload_sha256','transaction','business_frontier'}

def out():
 p=Path(os.environ.get('P3_CLOSURE_ORACLE_ARTIFACT_ROOT','.runtime/p3-closure-oracle/artifacts')).resolve()
 assert not any(n in str(p) for n in ('plan-replacement','frontier-oracle'))
 p.mkdir(parents=True,exist_ok=True);return p

def record(kind,value):
 p=out()/(kind+'-'+uuid4().hex+'.json');p.write_text(json.dumps(value,indent=2,default=str)+'\n');return p

def verify_imports():
 root=Path(os.environ['P3_CLOSURE_TEST_SOURCE_ROOT']).resolve();items={}
 for name in ('p3_never_accepted_closure','business_frontier','business_frontier_types','service_dispatches',
              'executor_receipts','case_resource_delivery','plan_replacement_compatibility','service_plan_approval'):
  module=importlib.import_module('parkweave.'+name);path=Path(module.__file__).resolve()
  assert path.parent==root,(name,str(path),str(root))
  items[name]={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
 manifest=os.environ.get('P3_CLOSURE_TEST_SOURCE_MANIFEST')
 if manifest:
  expected=json.loads(Path(manifest).read_text());expected=expected.get('source_paths',expected)
  for name,row in items.items():assert row['sha256']==expected['src/parkweave/'+name+'.py']
 record('actual-imports',items)

def snapshot(t):
 f,p=t['f'],t['p']
 with f[1].connect() as c:
  parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
  values={table:c.execute('SELECT to_jsonb(x) row FROM '+table+' x ORDER BY to_jsonb(x)::text').fetchall()
   for table in (*TABLES,'dispatch_notice_outbox','case_resource_links','resource_case_claims',
    'synthetic_resource_holds','synthetic_resource_combinations','synthetic_resource_combination_receipts')}
 return dict(parent=parent,tables=values)

def qualify_old(t):
 with t['f'][1].connect() as c:
  parent=c.execute('SELECT * FROM preparations WHERE id=%s FOR UPDATE',(t['p']['preparation_id'],)).fetchone()
  return t['protocol'].qualify(c,parent,t['old'])

def check_qualification(q,t,closure_state=None):
 assert set(q)==QKEYS and type(q['schema']) is int and q['schema']==1
 assert q['profile']==PROFILE and q['state']=='CLOSED_WITHOUT_ACCEPTANCE'
 assert type(q['epoch']) is int and q['epoch']>0 and q['ever_started'] is True
 assert q['preparation_id']==t['p']['preparation_id'] and q['previous_plan_id']==t['old']['id']
 assert q['closure_state'] in ('DECLINED','WITHDRAWN')
 if closure_state:assert q['closure_state']==closure_state
 d=q['dispatch'];assert set(d)==DKEYS and d['state']==q['closure_state']
 assert type(d['revision']) is int and 2<=d['revision']<=62 and d['revision']%2==0
 assert d['offers_count']*2==d['events_count']==d['revision']==len(d['events'])
 assert [e['revision'] for e in d['events']]==list(range(1,d['revision']+1))
 for i,e in enumerate(d['events'],1):
  assert set(e)==EKEYS
  assert e['action']==('OFFER' if i==1 else 'REOFFER') if i%2 else e['action'] in ('DECLINE','WITHDRAW')
  assert type(e['business_frontier']) is dict and set(e['business_frontier'])=={'generation','preparation_id','plan_id','plan_revision','epoch'}
 assert [x['table'] for x in q['collections']]==list(TABLES)
 assert [x['count'] for x in q['collections'][:3]]==[1,d['offers_count'],d['events_count']]
 assert all(x['known'] is True and x['complete'] is True and type(x['count']) is int for x in q['collections'])
 assert all(x['count']==0 for x in q['collections'][3:])
 assert [e['adapter_id'] for e in q['verified_prefix']]==['P1','P2']
 return q


def quote(t):
 from test_resource_bundles import bundle
 from test_case_resource_delivery import quoted
 f,p=t['f'],t['p'];hs,body=bundle(f)
 return hs,quoted(f,p,{**body,'expected_link_revision':1,'expected_previous_plan_id':t['old']['id'],
  'replacement_frontier_profile':PROFILE})


def current_offer_body(t):
 f,p=t['f'],t['p'];r=f[3].get('/api/service-dispatches/catalog',params={'preparation_id':p['preparation_id']},headers=headers(f[2],'prep-specialist-fixture-a'))
 assert r.status_code==200,r.text;v=r.json()
 return dict(expected_preparation_revision=v['preparation_revision'],expected_dispatch_revision=v['dispatch_revision'],
  executor_id='executor-a',reason='SYNTHETIC explicit current P3 intent',expected_business_frontier=deepcopy(v['business_frontier']))


def post_offer(t,body,key=None):
 f,p=t['f'],t['p'];return f[3].post('/api/preparations/'+p['preparation_id']+'/dispatch',
  headers=headers(f[2],'prep-specialist-fixture-a',key or uuid4().hex),json=body)


def commit(t):
 from test_plan_source_reapproval import approved
 from test_case_resource_delivery import submit
 f,p=t['f'],t['p'];hs,data=quote(t);item,_=approved(f,p,data)
 assert item['purpose']=='CASE_RESOURCE_PLAN_REPLACEMENT'
 report=item['context']['plan_replacement']['compatibility']
 assert set(item['context']['plan_replacement'])=={'link_id','link_revision','snapshot_sha256','previous_delivery_context','previous_approved_plan_revision','approved_plan_revision','previous_plan_id','replacement_plan_id','previous_definition_sha256','replacement_definition_sha256','replacement_adoption_event_id','replacement_adoption_sha256','compatibility','compatibility_sha256'}
 assert report['schema']==3 and len(report)==15
 q=check_qualification(report['qualification'],t,{'DECLINE':'DECLINED','WITHDRAW':'WITHDRAWN'}[t['closure_action']])
 key=uuid4().hex;body={**data,'approval_id':item['id']};r=submit(f,p,body,key);assert r.status_code==201,r.text
 return dict(holds=hs,data=data,item=item,qualification=q,key=key,body=body,result=r.json())


def new_business_tail(t):
 from test_service_case_steps import verified
 from test_service_dispatches import command as dispatch_command
 from test_executor_receipts import act as receipt_action
 from test_case_lifecycle import read as local_read,act as local_action
 f,p=t['f'],t['p'];verified(f,p,'P2')
 r=post_offer(t,current_offer_body(t));assert r.status_code==201,r.text
 offered=r.json();assert offered['event']['action']=='REOFFER'
 r=dispatch_command(f,offered,'ACCEPT',expected_business_frontier=offered['business_frontier']);assert r.status_code==200,r.text
 accepted=r.json();verified(f,p,'P3')
 r=f[3].get('/api/executor-receipts/'+accepted['receipt_step_id'],headers=headers(f[2],'executor-a'));assert r.status_code==200,r.text
 row=r.json();r=receipt_action(f,row,'SUBMIT',expected_business_frontier=row['business_frontier']);assert r.status_code==200,r.text
 row=r.json();r=receipt_action(f,row,'ACKNOWLEDGE',expected_business_frontier=row['business_frontier']);assert r.status_code==200,r.text
 verified(f,p,'P4');r=local_read(f,p);assert r.status_code==200,r.text
 row=r.json();r=local_action(f,p,row,'REVALIDATE',expected_business_frontier=row['business_frontier']);assert r.status_code==200,r.text
 verified(f,p,'P5');g=f[3].get('/api/preparations/'+p['preparation_id']+'/goal-results',headers=headers(f[2]));assert g.status_code==200,g.text
 record('new-six-local-goal-results',g.json());assert g.json()['state']=='LOCAL_OUTPUTS_VERIFIED' and len(g.json()['results'])==6
 assert all(row['state']=='LOCAL_OUTPUT_VERIFIED' for row in g.json()['results']) and not g.json()['case_goal_completed']
 w=f[3].get('/api/cases/worklist',headers=headers(f[2]),params={'limit':1});assert w.status_code==200,w.text
 assert w.json()['read_only'] and w.json()['recorded_states_only']
 item=next(row for row in w.json()['items'] if row['case_id']==p['case_id'])
 assert not item['evidence_verified'] and not item['case_goal_completed']
 return accepted
