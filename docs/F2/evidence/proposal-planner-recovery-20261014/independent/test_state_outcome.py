import sys
from pathlib import Path
from uuid import uuid4
import httpx
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tests'))
from conftest import pg,fixture
from test_preparation import preparation_fixture,headers
from test_bounded_planning import setup
from parkweave.api import create_app
from parkweave.service_plan_planner import OfflineProposalPlanner

def test_unknown_attempt_state_only_damage_must_not_be_safe(preparation_fixture):
 f=preparation_fixture;p=setup(f,['LOCAL_CASE_RECORD_RECHECK']);key=uuid4().hex
 def fail(req):raise httpx.ConnectError('SYNTHETIC unknown transport result',request=req)
 planner=OfflineProposalPlanner(transport=httpx.MockTransport(fail));path='/api/preparations/'+p['preparation_id']+'/service-plan-candidates'
 current=f[3].get('/api/preparations/'+p['preparation_id']+'/planning-preview',headers=headers(f[2])).json()['current'];data={'expected_preparation_revision':current['preparation_revision'],'expected_source_sha256':current['source_sha256']}
 with TestClient(create_app(f[0],proposal_planner=planner)) as api:
  assert api.post(path,headers=headers(f[2],key=key),json=data).status_code==409
  original=api.get(path+'/recovery',headers=headers(f[2],key=key));assert original.status_code==200 and original.json()['status']=='OUTCOME_UNKNOWN'
  with f[1].connect() as c:
   history=c.execute('SELECT planning_previews FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['planning_previews'];h=history[0];assert h['planner_attempt']['outcome']=='TRANSPORT_OUTCOME_UNKNOWN';h['planner_attempt']['state']='FAILED_SAFE';c.execute('UPDATE preparations SET planning_previews=%s WHERE id=%s',(Jsonb(history),p['preparation_id']))
  r=api.get(path+'/recovery',headers=headers(f[2],key=key));assert r.status_code==409,{'status':r.status_code,'body':r.json()}

import pytest,json
from test_plan_preview import digest
from test_service_plan_candidates import adoption

def response(req):
 expected=json.loads(json.loads(req.content)['messages'][1]['content'])['proposal']
 return httpx.Response(200,json={'id':'recovery-independent-fake','model':'intern-s2','choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(expected)}}],'usage':{'prompt_tokens':2,'completion_tokens':3,'total_tokens':5}})

@pytest.mark.parametrize('state,outcome,extra',[
 ('STARTED','TRANSPORT_OUTCOME_UNKNOWN',False),('OUTCOME_UNKNOWN','INVALID_RESPONSE',False),('FAILED_SAFE',None,False),('FAILED_SAFE','UNREVIEWED_NEW_CODE',False),('OUTCOME_UNKNOWN',None,False),('OUTCOME_UNKNOWN','TRANSPORT_OUTCOME_UNKNOWN',True),('STARTED',None,True)])
def test_bad_attempt_state_outcome_and_keys_keep_history(preparation_fixture,state,outcome,extra):
 f=preparation_fixture;p=setup(f,['LOCAL_CASE_RECORD_RECHECK']);key=uuid4().hex
 def fail(req):raise httpx.ConnectError('SYNTHETIC unknown',request=req)
 planner=OfflineProposalPlanner(transport=httpx.MockTransport(fail));path='/api/preparations/'+p['preparation_id']+'/service-plan-candidates'
 current=f[3].get('/api/preparations/'+p['preparation_id']+'/planning-preview',headers=headers(f[2])).json()['current'];data={'expected_preparation_revision':current['preparation_revision'],'expected_source_sha256':current['source_sha256']}
 with TestClient(create_app(f[0],proposal_planner=planner)) as api:
  assert api.post(path,headers=headers(f[2],key=key),json=data).status_code==409
  with f[1].connect() as c:
   history=c.execute('SELECT planning_previews FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['planning_previews'];h=history[0];h['planner_attempt'].update(state=state,outcome=outcome)
   if extra:h['planner_attempt']['invented_authority']=True
   c.execute('UPDATE preparations SET planning_previews=%s WHERE id=%s',(Jsonb(history),p['preparation_id']))
  before=digest(f)
  assert api.get(path+'/recovery',headers=headers(f[2],key=key)).status_code==409
  assert api.get(path,headers=headers(f[2])).status_code==409
  assert digest(f)==before


def test_committed_attempt_extra_fields_rejected_all_consumers(preparation_fixture):
 f=preparation_fixture;p=setup(f,['LOCAL_CASE_RECORD_RECHECK']);key=uuid4().hex;planner=OfflineProposalPlanner(transport=httpx.MockTransport(response));path='/api/preparations/'+p['preparation_id']+'/service-plan-candidates'
 current=f[3].get('/api/preparations/'+p['preparation_id']+'/planning-preview',headers=headers(f[2])).json()['current'];data={'expected_preparation_revision':current['preparation_revision'],'expected_source_sha256':current['source_sha256']}
 with TestClient(create_app(f[0],proposal_planner=planner)) as api:
  r=api.post(path,headers=headers(f[2],key=key),json=data);assert r.status_code==201,r.text;v=r.json();adoptdata=adoption(f,p,v)
  with f[1].connect() as c:
   history=c.execute('SELECT planning_previews FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['planning_previews'];history[0]['planner_attempt']['invented_authority']=True;c.execute('UPDATE preparations SET planning_previews=%s WHERE id=%s',(Jsonb(history),p['preparation_id']))
  before=digest(f)
  assert api.get(path+'/recovery',headers=headers(f[2],key=key)).status_code==409
  r=api.get(path+'/'+v['candidate_id']+'/preview',headers=headers(f[2]));assert r.status_code==409,{'status':r.status_code}
  r=api.post('/api/preparations/'+p['preparation_id']+'/service-case-plan',headers=headers(f[2],key=uuid4().hex),json=adoptdata);assert r.status_code==409,r.text
  assert digest(f)==before


def test_unreviewed_model_error_stays_unknown_not_safe(preparation_fixture):
 from parkweave.intern_adapter import ModelBoundaryError
 f=preparation_fixture;p=setup(f,['LOCAL_CASE_RECORD_RECHECK']);key=uuid4().hex;calls=[]
 def fail(req):calls.append(req);raise ModelBoundaryError('UNREVIEWED_NEW_CODE')
 planner=OfflineProposalPlanner(transport=httpx.MockTransport(fail));path='/api/preparations/'+p['preparation_id']+'/service-plan-candidates'
 current=f[3].get('/api/preparations/'+p['preparation_id']+'/planning-preview',headers=headers(f[2])).json()['current'];data={'expected_preparation_revision':current['preparation_revision'],'expected_source_sha256':current['source_sha256']}
 with TestClient(create_app(f[0],proposal_planner=planner)) as api:
  assert api.post(path,headers=headers(f[2],key=key),json=data).status_code==409
  before=digest(f);r=api.get(path+'/recovery',headers=headers(f[2],key=key));assert r.status_code==200,r.text;assert r.json()['status']=='OUTCOME_UNKNOWN' and r.json()['attempts'][0]['outcome']=='PLANNER_OUTCOME_UNKNOWN';assert digest(f)==before
  r=api.post(path,headers=headers(f[2],key=key),json=data);assert r.status_code==201 and r.json()['status']=='OUTCOME_UNKNOWN' and len(calls)==1
