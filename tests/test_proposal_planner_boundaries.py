"""Persistent original-key, profile downgrade and original-clock boundaries."""
from uuid import uuid4
from datetime import timedelta
import json,threading
from concurrent.futures import ThreadPoolExecutor
import httpx,pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from test_preparation import preparation_fixture,headers
from test_bounded_planning import setup
from test_service_plan_candidates import GOAL,path,generate
from test_proposal_planner_offline import echo_handler,request_body,post_candidate,exact_recovery
from parkweave.api import create_app
from parkweave.service_plan_planner import OfflineProposalPlanner
from parkweave import service_plan_candidates as candidates
from test_plan_preview import digest

def test_old_v2_cached_key_and_new_v3_default_app_read_do_not_dispatch_again(preparation_fixture):
    f=preparation_fixture;p=setup(f,[GOAL]);body,_=request_body(f,p);oldkey=uuid4().hex;old=generate(f,p,oldkey,body).json();calls=[];planner=OfflineProposalPlanner(transport=httpx.MockTransport(echo_handler(calls)))
    with TestClient(create_app(f[0],proposal_planner=planner)) as api:
        r=post_candidate(api,f,p,body,oldkey);assert r.status_code==201 and r.json()['candidate_id']==old['candidate_id'] and r.json()['validator_version']==2;assert calls==[]
        key=uuid4().hex;v=post_candidate(api,f,p,body,key).json();assert v['validator_version']==3
    before=digest(f);r=generate(f,p,key,body);assert r.status_code==201 and r.json()['candidate_id']==v['candidate_id'] and r.json()['validator_version']==3
    assert f[3].get(path(p)+'/recovery',headers=headers(f[2],key=key)).json()['status']=='COMMITTED';assert len(calls)==1 and digest(f)==before


@pytest.mark.parametrize('damage',['all_model_fields_removed','raw_envelope','legal_budget_change'])
def test_v3_cannot_downgrade_or_rewrite_original_response_and_ledger(preparation_fixture,damage):
    f=preparation_fixture;p=setup(f,[GOAL]);body,_=request_body(f,p);calls=[];planner=OfflineProposalPlanner(transport=httpx.MockTransport(echo_handler(calls)))
    with TestClient(create_app(f[0],proposal_planner=planner)) as api:
        key=uuid4().hex;v=post_candidate(api,f,p,body,key).json()
        with f[1].connect() as c:
            records=c.execute('SELECT planning_previews FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['planning_previews'];record=records[0]
            if damage=='all_model_fields_removed':
                for field in ('producer','planner_attempt','proposal_raw','response_raw','budget_record'):record.pop(field)
                record['document'].pop('candidate_producer')
            elif damage=='raw_envelope':record['response_raw']=' '+record['response_raw']
            else:record['budget_record']['reserved_tokens']=1024
            c.execute('UPDATE preparations SET planning_previews=%s WHERE id=%s',(Jsonb(records),p['preparation_id']))
        before=digest(f);reply=api.get(path(p)+'/'+v['candidate_id']+'/preview',headers=headers(f[2]));assert reply.status_code==409;recovered=exact_recovery(api,f,p,key);assert recovered.status_code==409;assert digest(f)==before


def test_two_apps_persist_one_original_key_while_provider_waits(preparation_fixture):
    f=preparation_fixture;p=setup(f,[GOAL]);body,_=request_body(f,p);entered=threading.Event();release=threading.Event();calls=[];second_calls=[]
    def blocked(request):entered.set();assert release.wait(10);return echo_handler(calls)(request)
    first=OfflineProposalPlanner(transport=httpx.MockTransport(blocked));second=OfflineProposalPlanner(transport=httpx.MockTransport(echo_handler(second_calls)));key=uuid4().hex
    with TestClient(create_app(f[0],proposal_planner=first)) as a,TestClient(create_app(f[0],proposal_planner=second)) as b,ThreadPoolExecutor(2) as pool:
        pending=pool.submit(post_candidate,a,f,p,body,key)
        try:
            assert entered.wait(5);r=post_candidate(b,f,p,body,key);assert r.status_code==201 and r.json()['status']=='PENDING' and second.budget.calls==0
            assert generate(f,p,key,body).json()['status']=='PENDING'
            release.set();v=pending.result(timeout=8).json();assert v['validator_version']==3
            r=post_candidate(b,f,p,body,key);assert r.json()['candidate_id']==v['candidate_id'] and second.budget.calls==0
            assert len(calls)==1 and second_calls==[]
        finally:release.set()


@pytest.mark.parametrize('stage',['before_dispatch','before_save'])
def test_first_attempt_database_deadline_does_not_renew(preparation_fixture,stage,monkeypatch):
    f=preparation_fixture;p=setup(f,[GOAL]);body,_=request_body(f,p);calls=[];original=candidates.clock;clock_calls=0
    def clock(c):
        nonlocal clock_calls
        clock_calls+=1
        now=original(c)
        return now+timedelta(seconds=900) if stage=='before_dispatch' and clock_calls>=2 or stage=='before_save' and clock_calls>=3 else now
    monkeypatch.setattr(candidates,'clock',clock);planner=OfflineProposalPlanner(transport=httpx.MockTransport(echo_handler(calls)))
    with TestClient(create_app(f[0],proposal_planner=planner)) as api:
        key=uuid4().hex;r=post_candidate(api,f,p,body,key);assert r.status_code==409
        recovered=exact_recovery(api,f,p,key).json();assert recovered['status']=='FAILED_SAFE' and recovered['items']==[]
        window=recovered['attempts'][0]['validity'];count=len(calls);assert count==(0 if stage=='before_dispatch' else 1)
        repeated=post_candidate(api,f,p,body,key);assert repeated.status_code==201 and repeated.json()['status']=='FAILED_SAFE' and repeated.json()['validity']==window
        assert len(calls)==count and planner.budget.calls==count
