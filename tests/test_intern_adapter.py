"""Self-authored official-shaped fixtures; never a real provider response."""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
import httpx
import pytest
from pydantic import SecretStr
from parkweave.intern_adapter import InternChatAdapter,ModelBoundaryError,OfflineBudget,ENDPOINT

TOKEN='fake-offline-token-never-a-real-key'

def response(**changes):
    return {'id':'synthetic-completion-1','model':'Intern-S2','choices':[{'index':0,'message':{'role':'assistant','content':'合成回填已核对'},'finish_reason':'stop'}],
            'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}}|changes


def adapter(handler,budget=None):
    return InternChatAdapter(transport=httpx.MockTransport(handler),token=SecretStr(TOKEN),budget=budget)


def test_offline_tool_feedback_and_known_model_case_identity():
    requests=[]
    call={'id':'synthetic-call-1','type':'function','function':{'name':'case_create','arguments':json.dumps({'goal':'合成本地待补件'})}}
    def handler(request):
        requests.append(request)
        assert str(request.url)==ENDPOINT and request.method=='POST'
        assert request.headers['authorization']=='Bearer '+TOKEN
        payload=json.loads(request.content)
        assert payload['stream'] is False and payload['n']==1 and payload['model']=='intern-s2' and payload['thinking_mode'] is True
        assert set(payload['tools'][0]['function']['parameters']['properties'])=={'goal'}
        if len(requests)==1:
            return httpx.Response(200,json=response(choices=[{'index':0,'message':{'role':'assistant','content':None,'tool_calls':[call]},'finish_reason':'tool_calls'}]))
        assert payload['messages'][-1]['tool_call_id']=='synthetic-call-1'
        return httpx.Response(200,json=response())
    client=adapter(handler)
    messages=[{'role':'user','content':'合成诉求'}]
    result=client.complete(messages)
    assert result['tool_proposal']['action']=='case.create' and result['executed'] is False
    # Deterministic synthetic feedback, NOT a fabricated real Case/receipt.
    messages += [{'role':'assistant','content':None,'tool_calls':[call]}, {'role':'tool','tool_call_id':call['id'],'content':'{"scope":"SYNTHETIC_FEEDBACK_ONLY","external_acceptance":"NOT_SUBMITTED"}'}]
    final=client.complete(messages)
    assert final['returned_model']=='Intern-S2' and final['model']=='intern-s2' and final['mode']=='OFFLINE_HTTP_FIXTURE'
    assert client.budget.calls==2 and client.budget.charged_tokens==30
    assert TOKEN not in repr(client.budget.records)
    with pytest.raises(ModelBoundaryError,match='LIVE_BLOCKED'):client.live_complete(messages)
    assert len(requests)==2


@pytest.mark.parametrize('change',[{'model':'intern-s2-preview'},{'model':'intern-latest'},{'model':'other'},{'model':'intern-s2 '},{'model':'intern-ſ2'},
 {'choices':[{'index':0,'message':{'role':'assistant','content':'x','tool_calls':[{'id':'c','type':'function','function':{'name':'shell','arguments':'{}'}}]},'finish_reason':'tool_calls'}]},
 {'choices':[{'index':0,'message':{'role':'assistant','tool_calls':[{'id':'c','type':'function','function':{'name':'case_create','arguments':"{'goal':'x'}"}}]},'finish_reason':'tool_calls'}]},
 {'choices':[{'index':0,'message':{'role':'assistant','tool_calls':[{'id':'c','type':'function','function':{'name':'case_create','arguments':'{"goal":"x","script":"bad"}'}}]},'finish_reason':'tool_calls'}]}])
def test_invalid_proposal_is_rejected_before_any_execution(change):
    client=adapter(lambda _:httpx.Response(200,json=response(**change)))
    with pytest.raises(ModelBoundaryError):client.complete([{'role':'user','content':'合成'}])
    assert client.budget.calls==1 and client.budget.records[0]['outcome']!='VALIDATED'
    assert TOKEN not in repr(client.budget.records)


@pytest.mark.parametrize('case,expected',[('429','RATE_LIMIT_NO_RETRY'),('auth','AUTHORIZATION_FAILED'),('server','HTTP_ERROR_NO_RETRY'),
 ('redirect','HTTP_ERROR_NO_RETRY'),('timeout','TIMEOUT_OUTCOME_UNKNOWN'),('transport','TRANSPORT_OUTCOME_UNKNOWN'),
 ('length','TRUNCATED_NO_TOOL_EXECUTION'),('unfinished','INCOMPLETE_RESPONSE'),('bad_usage','INVALID_USAGE'),('html','SECRET_OUTPUT_REJECTED'),('overrun','USAGE_RESERVATION_EXCEEDED')])
def test_errors_timeout_truncation_usage_and_no_automatic_retry(case,expected):
    attempts=[]
    def handler(request):
        attempts.append(1)
        if case=='timeout':raise httpx.ReadTimeout('echo '+TOKEN,request=request)
        if case=='transport':raise httpx.ConnectError('echo '+TOKEN,request=request)
        if case in ('429','auth','server','redirect'):
            return httpx.Response({'429':429,'auth':401,'server':500,'redirect':302}[case],json={'error':TOKEN},headers={'Location':'https://example.invalid'})
        if case=='html':return httpx.Response(200,text='<html>'+TOKEN)
        body=response()
        if case in ('length','unfinished'):body['choices'][0]['finish_reason']='length' if case=='length' else None
        if case=='bad_usage':body['usage']={'prompt_tokens':True,'completion_tokens':0,'total_tokens':1}
        if case=='overrun':body['usage']={'prompt_tokens':9000,'completion_tokens':1,'total_tokens':9001}
        return httpx.Response(200,json=body)
    client=adapter(handler)
    with pytest.raises(ModelBoundaryError) as error:client.complete([{'role':'user','content':'合成'}])
    assert error.value.code==expected and len(attempts)==1 and client.budget.calls==1
    assert TOKEN not in str(error.value) and TOKEN not in repr(client.budget.records)


def test_atomic_offline_attempt_budget_and_unknown_usage():
    budget=OfflineBudget(max_calls=3,max_tokens=16384)
    client=adapter(lambda _:httpx.Response(200,json={k:v for k,v in response().items() if k!='usage'}),budget)
    def run():
        try:return client.complete([{'role':'user','content':'合成'}])['usage']
        except ModelBoundaryError as exc:return exc.code
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(lambda _:run(),range(8)))
    assert results.count('UNKNOWN')==2 and results.count('BUDGET_EXHAUSTED')==6
    assert budget.calls==2 and budget.charged_tokens==16384


def test_input_limits_tool_feedback_pairing_and_real_transport_fail_closed():
    attempts=[];client=adapter(lambda request:attempts.append(request))
    for messages in [[{'role':'user','content':'x'*20000}], [{'role':'tool','tool_call_id':'unknown','content':'x'}],
                     [{'role':'user','content':'x','tool':'shell'}]]:
        with pytest.raises(ModelBoundaryError):client.complete(messages)
    for n in (0,2048,True):
        with pytest.raises(ModelBoundaryError):client.complete([{'role':'user','content':'合成'}],max_tokens=n)
    assert attempts==[] and client.budget.calls==0
    with pytest.raises(ModelBoundaryError,match='LIVE_TRANSPORT_DISABLED'):
        InternChatAdapter(transport=None,token=SecretStr(TOKEN))


def test_duplicate_json_keys_and_empty_assistant_do_not_form_partial_proposal():
    raw=b'{"id":"synthetic","model":"other","model":"Intern-S2","choices":[]}'
    client=adapter(lambda _:httpx.Response(200,content=raw))
    with pytest.raises(ModelBoundaryError,match='INVALID_RESPONSE'):client.complete([{'role':'user','content':'合成'}])
    call={'id':'c','type':'function','function':{'name':'case_create','arguments':'{"goal":"safe","goal":"ambiguous"}'}}
    client=adapter(lambda _:httpx.Response(200,json=response(choices=[{'index':0,'message':{'role':'assistant','tool_calls':[call]},'finish_reason':'tool_calls'}])))
    with pytest.raises(ModelBoundaryError,match='INVALID_TOOL_PROPOSAL'):client.complete([{'role':'user','content':'合成'}])
    with pytest.raises(ModelBoundaryError,match='INVALID_MESSAGE'):client.complete([{'role':'assistant','content':None}])
