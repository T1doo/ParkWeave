import json,socket,sys,threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from copy import deepcopy
import httpx,pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tests'))
from conftest import pg,fixture
from test_preparation import preparation_fixture,headers,add
from test_bounded_planning import setup
from test_service_plan_candidates import path,adoption
from test_plan_preview import digest
from parkweave.api import create_app
from parkweave.intern_adapter import OfflineBudget,ModelBoundaryError
from parkweave.service_plan_planner import OfflineProposalPlanner
from parkweave.http_transport import InternHTTPTransport
from parkweave import service_plan_candidates as cand,controlled_plans as cp
GOAL='LOCAL_CASE_RECORD_RECHECK'

def body(f,p):
    current=f[3].get('/api/preparations/'+p['preparation_id']+'/planning-preview',headers=headers(f[2])).json()['current']
    return {'expected_preparation_revision':current['preparation_revision'],'expected_source_sha256':current['source_sha256']}

def responder(request):
    proposal=json.loads(json.loads(request.content)['messages'][1]['content'])['proposal']
    return httpx.Response(200,json={'id':'independent-fake-response','model':'intern-s2','choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(proposal)}}],'usage':{'prompt_tokens':20,'completion_tokens':10,'total_tokens':30}})

def test_real_socket_disabled_before_connect(monkeypatch):
    events=[]
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));listener.listen();listener.settimeout(.05)
        original=socket.socket.connect
        def spy(self,*a,**k):events.append(a);return original(self,*a,**k)
        monkeypatch.setattr(socket.socket,'connect',spy)
        budget=OfflineBudget()
        with pytest.raises(ModelBoundaryError,match='PROPOSAL_LIVE_TRANSPORT_DISABLED'):
            OfflineProposalPlanner(transport=InternHTTPTransport(),budget=budget)
        assert events==[] and budget.calls==0
        with pytest.raises(socket.timeout):listener.accept()
    # A real local listener was available; constructor gate made no connection.

def test_success_persists_v3_and_historical_source_trace(preparation_fixture,monkeypatch):
    f=preparation_fixture;p=setup(f,[GOAL]);planner=OfflineProposalPlanner(transport=httpx.MockTransport(responder));key=uuid4().hex;data=body(f,p)
    with TestClient(create_app(f[0],proposal_planner=planner)) as api:
        r=api.post(path(p),headers=headers(f[2],key=key),json=data);assert r.status_code==201,r.text;v=r.json();assert v['validator_version']==3
        assert api.post(path(p),headers=headers(f[2],key=key),json=data).json()['candidate_id']==v['candidate_id'];assert planner.budget.calls==1
        v=api.get(path(p)+'/'+v['candidate_id']+'/preview',headers=headers(f[2])).json();assert v['can_adopt']
        adoptdata=adoption(f,p,v);ak=uuid4().hex
        r=api.post('/api/preparations/'+p['preparation_id']+'/service-case-plan',headers=headers(f[2],key=ak),json=adoptdata);assert r.status_code==201,r.text
        window=v['validity'];monkeypatch.setattr(cand,'clock',lambda c:cand._time(window['expires_at']))
        before=digest(f)
        r=api.get('/api/preparations/'+p['preparation_id']+'/goal-results',headers=headers(f[2]));assert r.status_code==200,r.text
        assert r.json()['source_trace']['candidate']['producer']['origin']=='OFFLINE_JSON_PLANNER_PROPOSAL'
        r=api.get('/api/preparations/'+p['preparation_id']+'/service-case-plan/command-recovery',headers=headers(f[2],key=ak));assert r.status_code==200,r.text;assert r.json()['status']=='COMMITTED'
        assert digest(f)==before and planner.budget.calls==1

@pytest.mark.parametrize('corruption',['call_id','usage_bool','budget_attempt_bool','remove_producer'])
def test_corrupt_v3_provenance_conflict_not_500(preparation_fixture,corruption):
    f=preparation_fixture;p=setup(f,[GOAL]);planner=OfflineProposalPlanner(transport=httpx.MockTransport(responder))
    with TestClient(create_app(f[0],proposal_planner=planner)) as api:
        r=api.post(path(p),headers=headers(f[2],key=uuid4().hex),json=body(f,p));assert r.status_code==201,r.text;v=r.json()
        with f[1].connect() as c:
            records=c.execute('SELECT planning_previews FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['planning_previews'];h=records[0]
            if corruption=='call_id':h['producer']['call_id']='space bad'
            elif corruption=='usage_bool':h['producer']['usage']['total_tokens']=True
            elif corruption=='budget_attempt_bool':h['budget_record']['attempt']=True
            else:h.pop('producer')
            if corruption in ('call_id','usage_bool'):
                h['document']['candidate_producer']=deepcopy(h['producer']);h['planner_attempt']['producer_sha256']=cp._hash(h['producer']);h['budget_record']['usage']=deepcopy(h['producer']['usage'])
            c.execute('UPDATE preparations SET planning_previews=%s WHERE id=%s',(Jsonb(records),p['preparation_id']))
        before=digest(f);r=api.get(path(p)+'/'+v['candidate_id']+'/preview',headers=headers(f[2]));assert r.status_code==409,r.text;assert digest(f)==before

@pytest.mark.parametrize('change',['material','revoke'])
def test_provider_wait_has_no_case_lock_pending_no_resend(preparation_fixture,change):
    f=preparation_fixture;p=setup(f,[GOAL]);data=body(f,p);key=uuid4().hex;entered=threading.Event();release=threading.Event();requests=[]
    def blocked(request):
        requests.append(request);entered.set();assert release.wait(12);return responder(request)
    planner=OfflineProposalPlanner(transport=httpx.MockTransport(blocked))
    with TestClient(create_app(f[0],proposal_planner=planner)) as api,ThreadPoolExecutor(max_workers=3) as pool:
        pending=pool.submit(api.post,path(p),headers=headers(f[2],key=key),json=data)
        try:
            assert entered.wait(8)
            duplicate=pool.submit(api.post,path(p),headers=headers(f[2],key=key),json=data).result(4);assert duplicate.status_code==201,duplicate.text;assert duplicate.json()['status']=='PENDING'
            assert api.post(path(p),headers=headers(f[2],key=key),json={**data,'expected_source_sha256':'0'*64}).status_code==409
            before=digest(f);recovery=api.get(path(p)+'/recovery',headers=headers(f[2],key=key));assert recovery.status_code==200 and recovery.json()['status']=='PENDING';assert digest(f)==before
            if change=='material':
                material=pool.submit(add,f,p).result(4);assert material.status_code==200,material.text
            else:
                with f[1].connect() as c:
                    c.execute("SET LOCAL lock_timeout='3s'");c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
            release.set();out=pending.result(8);assert out.status_code==(409 if change=='material' else 403),out.text
            recovery=api.get(path(p)+'/recovery',headers=headers(f[2],key=key));assert recovery.status_code==200,recovery.text
            assert recovery.json()['status']==('FAILED_SAFE' if change=='material' else 'PENDING')
            assert len(requests)==1 and planner.budget.calls==1
            with f[1].connect() as c:
                parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone();assert parent['service_case_plan'] is None;assert 'candidate' not in parent['planning_previews'][0]
        finally:release.set()

def test_transport_unknown_never_resend(preparation_fixture):
    f=preparation_fixture;p=setup(f,[GOAL]);requests=[]
    def failed(req):requests.append(req);raise httpx.ConnectError('SYNTHETIC unavailable',request=req)
    planner=OfflineProposalPlanner(transport=httpx.MockTransport(failed));data=body(f,p);key=uuid4().hex
    with TestClient(create_app(f[0],proposal_planner=planner)) as api:
        r=api.post(path(p),headers=headers(f[2],key=key),json=data);assert r.status_code==409,r.text
        before=digest(f);r=api.get(path(p)+'/recovery',headers=headers(f[2],key=key));assert r.status_code==200,r.text;assert r.json()['status']=='OUTCOME_UNKNOWN';assert digest(f)==before
        r=api.post(path(p),headers=headers(f[2],key=key),json=data);assert r.status_code==201 and r.json()['status']=='OUTCOME_UNKNOWN';assert len(requests)==1 and planner.budget.calls==1
