"""Compact service references over the original strict offline HTTP boundary."""
from copy import deepcopy
import hashlib
import json
import os
import socket
import httpx
import pytest
from parkweave.service_selection_planner import OfflineSelectionPlanner,FAKE_TOKEN
from parkweave.intern_adapter import ModelBoundaryError,OfflineBudget
from parkweave.http_transport import InternHTTPTransport
from parkweave.quota import PersistentBudget

@pytest.fixture
def context():
    kinds=[('synthetic-material-preparation',['LOCAL_MATERIAL_PREPARATION']),('synthetic-resource-coordination',['LOCAL_INTERNAL_ACCEPTANCE']),('synthetic-local-record-recheck',['LOCAL_CASE_RECORD_RECHECK'])]
    services=[dict(service_id=kind,supported_goals=goals,ref=dict(release_id='release-'+str(i),revision=1,release_sha256=str(i+1)*64,instance_id='instance-'+str(i),config_revision=1,config_sha256=str(i+4)*64)) for i,(kind,goals) in enumerate(kinds)]
    return dict(binding=dict(case_id='case-synthetic',source_sha256='a'*64,catalog_sha256='b'*64),required_goals=[g for _,gs in kinds for g in gs],planning_constraints=dict(excluded_roles=[],additional_requirements=[]),available_services=services)

def selection(context):return dict(schema_version=1,binding=context['binding'],selections=[s['ref'] for s in context['available_services']])
def envelope(doc):return dict(id='synthetic-selection-call',model='Intern-S2',choices=[dict(index=0,finish_reason='stop',message=dict(role='assistant',content=json.dumps(doc)))],usage=dict(prompt_tokens=10,completion_tokens=5,total_tokens=15))
def planner_for(body,status=200,budget=None):return OfflineSelectionPlanner(transport=httpx.MockTransport(lambda r:httpx.Response(status,json=body)),budget=budget)

def test_compact_three_capabilities_are_references_not_expected_graph(context,monkeypatch):
    def forbidden(*a,**k):raise AssertionError('real socket or credential lookup')
    monkeypatch.setattr(socket,'create_connection',forbidden);monkeypatch.setattr(os,'getenv',forbidden)
    calls=[]
    def handler(request):
        calls.append(1);payload=json.loads(request.content);prompt=json.loads(payload['messages'][-1]['content'])
        assert set(prompt)=={'scope',*context} and prompt['available_services']==context['available_services']
        assert 'proposal' not in prompt and 'steps' not in prompt and 'tools' not in payload
        assert 'not execution' in payload['messages'][0]['content']
        assert request.headers['Authorization']=='Bearer '+FAKE_TOKEN
        return httpx.Response(200,json=envelope(selection(context)))
    planner=OfflineSelectionPlanner(transport=httpx.MockTransport(handler));result=planner.propose(context)
    assert result['selection']==selection(context) and len(result['selection']['selections'])==3
    assert result['producer']['version']==4 and result['producer']['origin']=='OFFLINE_SERVICE_SELECTION'
    assert result['producer']['provider_enabled'] is False and result['producer']['executed'] is False
    assert result['producer']['response_sha256']==hashlib.sha256(result['response_raw'].encode()).hexdigest()
    assert result['budget_record']['outcome']=='VALIDATED' and planner.budget.charged_tokens==15 and calls==[1]
    assert FAKE_TOKEN not in repr(result)

@pytest.mark.parametrize('change',['top_extra','choice_extra','bool_index','tool_empty','tool_finish','length','model','usage_extra','usage_bool','usage_sum','usage_overrun','duplicate_envelope','duplicate_selection','extra_selection','secret','binding','hash','unknown_ref','empty','steps'])
def test_strict_response_rejects_ambiguous_or_forged_selection(context,change):
    doc=selection(context);body=envelope(doc)
    if change=='top_extra':body['approved']=True
    elif change=='choice_extra':body['choices'][0]['approved']=True
    elif change=='bool_index':body['choices'][0]['index']=False
    elif change=='tool_empty':body['choices'][0]['message']['tool_calls']=[]
    elif change=='tool_finish':body['choices'][0]['finish_reason']='tool_calls'
    elif change=='length':body['choices'][0]['finish_reason']='length'
    elif change=='model':body['model']='intern-s2-preview'
    elif change=='usage_extra':body['usage']['cost']=0
    elif change=='usage_bool':body['usage']['completion_tokens']=True
    elif change=='usage_sum':body['usage']['total_tokens']=99
    elif change=='usage_overrun':body['usage']=dict(prompt_tokens=8192,completion_tokens=1,total_tokens=8193)
    elif change=='duplicate_selection':body['choices'][0]['message']['content']='{"schema_version":1,'+json.dumps(doc)[1:]
    elif change=='extra_selection':doc['execute']=True
    elif change=='secret':body['choices'][0]['message']['content']=FAKE_TOKEN
    elif change=='binding':doc['binding']={**doc['binding'],'catalog_sha256':'c'*64}
    elif change=='hash':doc['selections'][0]={**doc['selections'][0],'release_sha256':'f'*64}
    elif change=='unknown_ref':doc['selections'][0]={**doc['selections'][0],'instance_id':'other-instance'}
    elif change=='empty':doc['selections']=[]
    elif change=='steps':doc['steps']=[{'id':'P1'}]
    if change in ('extra_selection','binding','hash','unknown_ref','empty','steps'):body['choices'][0]['message']['content']=json.dumps(doc)
    raw=json.dumps(body)
    if change=='duplicate_envelope':raw='{"id":"ambiguous",'+raw[1:]
    calls=[]
    def handler(request):calls.append(1);return httpx.Response(200,content=raw)
    planner=OfflineSelectionPlanner(transport=httpx.MockTransport(handler))
    with pytest.raises(ModelBoundaryError):planner.propose(context)
    assert calls==[1] and planner.budget.records[0]['outcome']!='VALIDATED'
    if change in ('binding','hash','unknown_ref','empty','steps','extra_selection'):assert planner.budget.records[0]['outcome']=='INVALID_SERVICE_SELECTION'

@pytest.mark.parametrize('status,code',[(302,'HTTP_ERROR_NO_RETRY'),(401,'AUTHORIZATION_FAILED'),(403,'AUTHORIZATION_FAILED'),(429,'RATE_LIMIT_NO_RETRY'),(500,'HTTP_ERROR_NO_RETRY')])
def test_http_error_no_retry(context,status,code):
    planner=planner_for({'error':FAKE_TOKEN},status)
    with pytest.raises(ModelBoundaryError) as error:planner.propose(context)
    assert error.value.code==code and planner.budget.calls==1 and planner.budget.charged_tokens==8192

@pytest.mark.parametrize('failure',['timeout','transport','missing_usage','non_utf8','response_limit'])
def test_conservative_unknown_and_bounded_response(context,failure):
    def handler(request):
        if failure=='timeout':raise httpx.ReadTimeout('synthetic timeout',request=request)
        if failure=='transport':raise httpx.ConnectError('synthetic unavailable',request=request)
        if failure=='non_utf8':return httpx.Response(200,content=b'\xff')
        if failure=='response_limit':return httpx.Response(200,content=b' '*65537)
        body=envelope(selection(context));body.pop('usage');return httpx.Response(200,json=body)
    planner=OfflineSelectionPlanner(transport=httpx.MockTransport(handler))
    if failure=='missing_usage':assert planner.propose(context)['producer']['usage']=='UNKNOWN'
    else:
        with pytest.raises(ModelBoundaryError) as error:planner.propose(context)
        assert error.value.code==dict(timeout='TIMEOUT_OUTCOME_UNKNOWN',transport='TRANSPORT_OUTCOME_UNKNOWN',non_utf8='INVALID_RESPONSE',response_limit='RESPONSE_LIMIT')[failure]
    assert planner.budget.calls==1 and planner.budget.charged_tokens==8192

@pytest.mark.parametrize('change',['parent','materials','service','actions','constraints','duplicate_refs','bad_ref','secret','empty_goals','boolean_revision'])
def test_untrusted_context_rejected_before_dispatch(context,change):
    if change=='parent':context['parent']={'owner_id':'private'}
    elif change=='materials':context['available_services'][0]['materials']='private'
    elif change=='service':context['available_services'][0]['service_id']='arbitrary-script'
    elif change=='actions':context['available_services'][0]['actions']=['EXECUTE']
    elif change=='constraints':context['planning_constraints']['authority']=True
    elif change=='duplicate_refs':context['available_services'].append(deepcopy(context['available_services'][0]))
    elif change=='bad_ref':context['available_services'][0]['ref']['release_sha256']='invalid'
    elif change=='secret':context['planning_constraints']['additional_requirements']=[FAKE_TOKEN]
    elif change=='empty_goals':context['required_goals']=[]
    elif change=='boolean_revision':context['available_services'][0]['ref']['revision']=True
    calls=[];planner=OfflineSelectionPlanner(transport=httpx.MockTransport(lambda r:calls.append(1)))
    with pytest.raises(ModelBoundaryError):planner.propose(context)
    assert calls==[] and planner.budget.calls==0

def test_budget_and_live_rejected_before_io(context,monkeypatch):
    calls=[]
    def forbidden(*a,**k):calls.append(1);raise AssertionError('unauthorized IO')
    monkeypatch.setattr(InternHTTPTransport,'post',forbidden)
    with pytest.raises(ModelBoundaryError):OfflineSelectionPlanner()
    with pytest.raises(ModelBoundaryError):OfflineSelectionPlanner(transport=InternHTTPTransport())
    with pytest.raises(ModelBoundaryError):OfflineSelectionPlanner(transport=httpx.MockTransport(lambda r:None),budget=PersistentBudget('unused',account='unused',product='parkweave',work='unused',kind='LIVE'))
    planner=OfflineSelectionPlanner(transport=httpx.MockTransport(lambda r:None),budget=OfflineBudget(max_calls=1,max_tokens=0))
    with pytest.raises(ModelBoundaryError) as error:planner.propose(context)
    assert error.value.code=='BUDGET_EXHAUSTED' and calls==[]

def test_before_dispatch_guard_and_runtime_mutation(context):
    calls=[];planner=OfflineSelectionPlanner(transport=httpx.MockTransport(lambda r:calls.append(1)))
    def denied():raise ModelBoundaryError('AUTHORIZATION_CHANGED')
    with pytest.raises(ModelBoundaryError):planner.propose(context,before_dispatch=denied)
    assert calls==[] and planner.budget.calls==0
    planner.transport=InternHTTPTransport()
    with pytest.raises(ModelBoundaryError):planner.propose(context)
    assert planner.budget.calls==0

def test_unknown_required_goal_preserved_and_no_false_satisfiability_claim(context):
    context['required_goals'].append('SYNTHETIC_UNKNOWN_GOAL')
    result=planner_for(envelope(selection(context))).propose(context)
    assert result['producer']['executed'] is False
    assert 'satisfiable' not in result and 'steps' not in result['selection']
