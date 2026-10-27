"""Offline-only proposal wire: no real provider, credential or LIVE quota."""
from copy import deepcopy
import json
import socket
import httpx
import pytest
from test_planner_proposal import document
from parkweave.service_plan_planner import OfflineProposalPlanner,FAKE_TOKEN
from parkweave.intern_adapter import ModelBoundaryError,OfflineBudget
from parkweave.http_transport import InternHTTPTransport
from parkweave.quota import PersistentBudget

def envelope(document):return dict(id='synthetic-proposal-call',model='Intern-S2',choices=[dict(index=0,finish_reason='stop',message=dict(role='assistant',content=json.dumps(document,ensure_ascii=False)))],usage=dict(prompt_tokens=10,completion_tokens=5,total_tokens=15))

def test_proposal_only_wire_and_local_ledger(document,monkeypatch):
    def forbidden(*a,**k):raise AssertionError('real socket or credential lookup forbidden')
    monkeypatch.setattr(socket,'create_connection',forbidden);monkeypatch.setattr(__import__('os'),'getenv',forbidden)
    calls=[]
    def handler(request):
        calls.append(1);payload=json.loads(request.content)
        assert 'tools' not in payload and payload['messages'][-1]['role']=='user' and json.loads(payload['messages'][-1]['content'])['proposal']==document
        assert request.headers['Authorization']=='Bearer '+FAKE_TOKEN
        return httpx.Response(200,json=envelope(document))
    planner=OfflineProposalPlanner(transport=httpx.MockTransport(handler));x=planner.propose(document)
    assert x['proposal']==document and x['producer']['mode']=='OFFLINE_HTTP_FIXTURE' and x['producer']['provider_enabled'] is False and x['producer']['executed'] is False
    assert len(calls)==1 and planner.budget.charged_tokens==15 and planner.budget.records[0]['outcome']=='VALIDATED'
    assert FAKE_TOKEN not in repr(x)

@pytest.mark.parametrize('change',['top_extra','choice_extra','bool_index','tool_empty','tool_finish','length','model','usage_extra','usage_bool','usage_sum','usage_overrun','duplicate_envelope','duplicate_document','extra_document','secret'])
def test_strict_wire_rejects_ambiguous_or_executable_response(document,change):
    body=envelope(document)
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
    elif change=='duplicate_document':body['choices'][0]['message']['content']='{"schema_version":1,'+json.dumps(document)[1:]
    elif change=='extra_document':body['choices'][0]['message']['content']=json.dumps({**document,'execute':True})
    elif change=='secret':body['choices'][0]['message']['content']=FAKE_TOKEN
    raw=json.dumps(body)
    if change=='duplicate_envelope':raw='{"id":"ambiguous",'+raw[1:]
    calls=[]
    def handler(request):calls.append(1);return httpx.Response(200,content=raw)
    planner=OfflineProposalPlanner(transport=httpx.MockTransport(handler))
    with pytest.raises(ModelBoundaryError):planner.propose(document)
    assert calls==[1] and planner.budget.records[0]['outcome']!='VALIDATED'
    assert FAKE_TOKEN not in repr(planner.budget.records)

@pytest.mark.parametrize('status',[302,401,403,429,500])
def test_http_error_has_no_retry_and_conservative_reservation(document,status):
    calls=[]
    def handler(request):calls.append(1);return httpx.Response(status,json={'error':FAKE_TOKEN})
    planner=OfflineProposalPlanner(transport=httpx.MockTransport(handler))
    with pytest.raises(ModelBoundaryError):planner.propose(document)
    assert calls==[1] and planner.budget.charged_tokens==8192

@pytest.mark.parametrize('failure',['timeout','socket_refused','missing_usage'])
def test_unknown_usage_and_actual_loopback_socket_failure_are_conservative(document,failure):
    calls=[];local_socket_attempts=[]
    def handler(request):
        calls.append(1)
        if failure=='timeout':raise httpx.ReadTimeout('SYNTHETIC timeout',request=request)
        if failure=='socket_refused':
            # Real local socket failure within the fake transport. No alternate
            # provider endpoint or HTTP provider request is made.
            with socket.socket() as probe:probe.bind(('127.0.0.1',0));address=probe.getsockname()
            local_socket_attempts.append(address[1])
            try:socket.create_connection(address,timeout=.2)
            except OSError:raise httpx.ConnectError('SYNTHETIC loopback connection refused',request=request) from None
            raise AssertionError('expected actual owned loopback socket refusal')
        body=envelope(document);body.pop('usage');return httpx.Response(200,json=body)
    planner=OfflineProposalPlanner(transport=httpx.MockTransport(handler))
    if failure=='missing_usage':assert planner.propose(document)['producer']['usage']=='UNKNOWN'
    else:
        with pytest.raises(ModelBoundaryError):planner.propose(document)
    assert calls==[1] and planner.budget.charged_tokens==8192
    if failure=='socket_refused':assert len(local_socket_attempts)==1 and planner.budget.records[0]['outcome']=='TRANSPORT_OUTCOME_UNKNOWN'

def test_live_transport_and_budget_reject_before_any_io(document,monkeypatch):
    calls=[]
    def forbidden(*a,**k):calls.append(1);raise AssertionError('unauthorized IO')
    monkeypatch.setattr(socket,'socket',forbidden);monkeypatch.setattr(InternHTTPTransport,'post',forbidden);monkeypatch.setattr(PersistentBudget,'reserve',forbidden)
    with pytest.raises(ModelBoundaryError):OfflineProposalPlanner(transport=InternHTTPTransport())
    with pytest.raises(ModelBoundaryError):OfflineProposalPlanner(transport=httpx.MockTransport(lambda r:None),budget=PersistentBudget('not-used',account='not-used',product='parkweave',work='not-used',kind='LIVE'))
    assert calls==[]

def test_mutated_runtime_transport_or_boolean_budget_cannot_dispatch(document):
    planner=OfflineProposalPlanner(transport=httpx.MockTransport(lambda r:None));planner.transport=InternHTTPTransport()
    with pytest.raises(ModelBoundaryError):planner.propose(document)
    assert planner.budget.calls==0
    planner=OfflineProposalPlanner(transport=httpx.MockTransport(lambda r:None));planner.budget.max_calls=True
    with pytest.raises(ModelBoundaryError):planner.propose(document)
    assert planner.budget.calls==0

def test_before_dispatch_authority_failure_does_not_send_or_reserve(document):
    calls=[];planner=OfflineProposalPlanner(transport=httpx.MockTransport(lambda r:calls.append(1)))
    def denied():raise RuntimeError('SYNTHETIC original authority changed')
    with pytest.raises(RuntimeError):planner.propose(document,before_dispatch=denied)
    assert calls==[] and planner.budget.calls==0

def test_non_utf8_envelope_is_rejected_without_double_settlement(document):
    planner=OfflineProposalPlanner(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=json.dumps(envelope(document)).encode('utf-16'))))
    with pytest.raises(ModelBoundaryError):planner.propose(document)
    assert planner.budget.charged_tokens==8192 and planner.budget.records[0]['outcome']=='INVALID_RESPONSE'
