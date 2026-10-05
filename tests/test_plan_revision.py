"""Independent behavioral oracle reads API/PG; never calls revision constructors/validator.
All provider responses self-authored MockTransport. No actual model or native Windows.
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import time
import httpx
import psycopg
import pytest
from parkweave.store import Conflict
from parkweave.model_chain import ModelChain,synthetic_transport
from parkweave.http_transport import InternHTTPTransport
from parkweave.process_env import minimal_environment
from test_model_chain import provision,submit,chain,rows,budget,no_provider_sockets


def sha(doc):return hashlib.sha256(json.dumps(doc,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def get(fixture,run,user='fixture-a'):
    return fixture[3].get('/api/runs/'+run+'/plan-revisions',headers={'Authorization':'Bearer '+fixture[2][user]})


def oracle(fixture,run):
    response=get(fixture,run);assert response.status_code==200;revisions=response.json()['revisions']
    assert len(revisions)==2
    first,last=revisions;before,after=first['document'],last['document']
    r,op,case=rows(fixture[1],run)
    assert before=={'schema_version':'parkweave/local-plan-revision/1','revision':1,'goal':'SYNTHETIC local goal',
        'operation_id':str(op['id']),'tool_call_id':'fixture-tool','step':{'action':'case.create','state':'PENDING_ACTION'},
        'case_state':'NOT_CREATED','next_step':'EXECUTE_TRUSTED_LOCAL_ACTION','external_acceptance':'NOT_SUBMITTED','offline_fulfillment':'NO_EVIDENCE'}
    assert after=={'schema_version':'parkweave/local-plan-revision/1','revision':2,'previous_sha256':sha(before),
        'goal':'SYNTHETIC local goal','operation_id':str(op['id']),'tool_call_id':'fixture-tool','receipt_sha256':sha(op['receipt']),
        'step':{'action':'case.create','state':'LOCAL_RECORD_CREATED','case_id':str(case['id'])},'case_state':'NEEDS_INPUT',
        'next_step':'REQUEST_MISSING_INPUT','success_scope':'LOCAL_CASE_CREATED','external_acceptance':'NOT_SUBMITTED','offline_fulfillment':'NO_EVIDENCE'}
    assert first['sha256']==sha(before) and last['sha256']==sha(after)
    assert [first['provider_call_id'],last['provider_call_id']]==['fixture-plan-response','fixture-feedback-response']
    assert first['tool_call_id']==last['tool_call_id']=='fixture-tool'
    assert r['state']=='SUCCEEDED' and case['state']=='NEEDS_INPUT' and op['state']=='VERIFIED'
    return revisions


def test_normal_cli_worker_persists_actual_revision_and_independent_oracle(fixture):
    store,owner,*_=fixture;provision(owner);run=submit(fixture)
    assert get(fixture,run).json()=={'revisions':[]}
    proc=subprocess.run([sys.executable,'-m','parkweave.worker','--once','--model-fixture','good'],
        env=minimal_environment(os.environ,PARKWEAVE_DSN=store.dsn),capture_output=True,text=True,timeout=10)
    assert proc.returncode==0,(proc.stdout,proc.stderr)
    revisions=oracle(fixture,run)
    owner.migrate();owner.migrate();assert get(fixture,run).json()['revisions']==revisions
    with owner.connect() as c:
        phases=c.execute('SELECT phase,result FROM model_steps WHERE run_id=%s ORDER BY phase',(run,)).fetchall()
        assert all(p['result']['mode']=='OFFLINE_HTTP_FIXTURE' for p in phases)


@pytest.mark.parametrize('mutation',['goal','case-id','operation','previous-hash','receipt-hash','tool-id','external-accepted','fulfilled','pending-step','new-tool','truncated-json','duplicate','fractional-revision'])
def test_invalid_revision_keeps_known_effect_without_publishing_artifact(fixture,mutation):
    store,owner,*_=fixture;provision(owner);run=submit(fixture);base=synthetic_transport()
    def handler(request):
        response=base.transport.handle_request(request);body=response.json()
        if json.loads(request.content)['messages'][-1]['role']=='tool':
            document=json.loads(body['choices'][0]['message']['content'])
            if mutation=='goal':document['goal']='dropped original requirement'
            elif mutation=='case-id':document['step']['case_id']='11111111-2222-4333-8444-555555555555'
            elif mutation=='operation':document['operation_id']='11111111-2222-4333-8444-555555555555'
            elif mutation=='previous-hash':document['previous_sha256']='0'*64
            elif mutation=='receipt-hash':document['receipt_sha256']='0'*64
            elif mutation=='tool-id':document['tool_call_id']='foreign-tool'
            elif mutation=='external-accepted':document['external_acceptance']='ACCEPTED'
            elif mutation=='fulfilled':document['offline_fulfillment']='FULFILLED'
            elif mutation=='pending-step':document['step']['state']='PENDING_ACTION'
            elif mutation=='new-tool':document['execute']={'action':'case.close'}
            elif mutation=='fractional-revision':document['revision']=2.0
            raw=json.dumps(document)
            if mutation=='truncated-json':raw=raw[:-1]
            if mutation=='duplicate':raw=raw[:-1]+',"goal":"different"}'
            body['choices'][0]['message']['content']=raw
        return httpx.Response(200,json=body)
    chain(store,InternHTTPTransport(httpx.MockTransport(handler))).execute(store.claim('worker'))
    r,op,case=rows(owner,run)
    assert r['state']=='FAILED' and op['state']=='VERIFIED' and case['state']=='NEEDS_INPUT'
    assert r['success_scope']=='LOCAL_CASE_CREATED'
    assert [p['revision'] for p in get(fixture,run).json()['revisions']]==[1]
    with owner.connect() as c:
        assert c.execute("SELECT outcome FROM model_steps WHERE run_id=%s AND phase='FEEDBACK'",(run,)).fetchone()['outcome']=='INVALID_PLAN_REVISION'
        assert c.execute('SELECT count(*) n FROM cases WHERE run_id=%s',(run,)).fetchone()['n']==1


def test_before_artifact_visible_before_trusted_action_and_immutable(fixture,monkeypatch):
    from parkweave.gateway import ExecutionGateway
    store,owner,*_=fixture;provision(owner);run=submit(fixture)
    execute=ExecutionGateway.execute
    def observed(gateway,claim,**kwargs):
        r,op,case=rows(owner,run);assert op['state']=='PREPARED' and case is None
        revision=get(fixture,run).json()['revisions'];assert len(revision)==1 and revision[0]['document']['step']['state']=='PENDING_ACTION'
        return execute(gateway,claim,**kwargs)
    monkeypatch.setattr(ExecutionGateway,'execute',observed)
    chain(store).execute(store.claim('worker'));oracle(fixture,run)
    for sql in ('UPDATE model_plans SET sha256=sha256','DELETE FROM model_plans'):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with store.connect() as c:c.execute(sql)


def test_after_artifact_and_terminal_run_outbox_atomic_recovery_no_new_call(fixture,monkeypatch):
    store,owner,*_=fixture;provision(owner);run=submit(fixture);ch=chain(store);old=ch.insert_artifact
    def crash(c,claim,document,call_id):
        old(c,claim,document,call_id)
        if document['revision']==2:raise RuntimeError('SYNTHETIC transaction interruption')
    monkeypatch.setattr(ch,'insert_artifact',crash)
    with pytest.raises(RuntimeError):ch.execute(store.claim('lost'))
    r,op,case=rows(owner,run);assert r['state']=='RUNNING' and op['state']=='VERIFIED'
    before=get(fixture,run).json()['revisions'];assert len(before)==1
    with owner.connect() as c:
        assert c.execute('SELECT count(*) n FROM shared_model_quota.reservations').fetchone()['n']==2
        assert not c.execute("SELECT 1 FROM outbox WHERE run_id=%s AND payload->>'state'='SUCCEEDED'",(run,)).fetchone()
        c.execute("UPDATE runs SET lease_until=clock_timestamp()-interval '1 second' WHERE id=%s",(run,))
    chain(store).execute(store.claim('replacement'));oracle(fixture,run)
    with owner.connect() as c:assert c.execute('SELECT count(*) n FROM shared_model_quota.reservations').fetchone()['n']==2


def test_current_authority_and_cross_scope_no_revision_leak(fixture):
    store,owner,tokens,_=fixture;provision(owner);run=submit(fixture);chain(store).execute(store.claim('worker'))
    oracle(fixture,run)
    for user in ('fixture-b','fixture-c'):
        response=get(fixture,run,user);assert response.status_code==403 and 'SYNTHETIC local goal' not in response.text
    owner.revoke('fixture-a');assert get(fixture,run).status_code==403


def test_old_known_effect_never_gets_fabricated_pre_effect_history(fixture):
    store,owner,*_=fixture;provision(owner);run=submit(fixture);claim=store.claim('worker')
    base=chain(store);base.step(claim,'PLAN',[{'role':'user','content':'SYNTHETIC local goal'}])
    store.finish(claim,defer_completion=True)  # Explicit legacy ENG007 known effect, no artifact.
    base.execute(claim)
    r,op,case=rows(owner,run);assert r['state']=='FAILED' and op['state']=='VERIFIED' and case is not None
    assert get(fixture,run).json()=={'revisions':[]}
    with owner.connect() as c:assert c.execute("SELECT outcome FROM model_steps WHERE run_id=%s AND phase='PLAN'",(run,)).fetchone()['outcome']=='PRE_EFFECT_PLAN_MISSING'


def test_fixed_long_window_admits_31_in_minute_known_normative_gap(fixture):
    # This is a reproduced FAILURE of the frozen product §10 30RPM rule, not AT30 PASS.
    store,owner,*_=fixture;provision(owner,calls=64,tokens=64*8192)
    started=time.monotonic()
    for i in range(31):
        b=budget(store,'SYNTHETIC-RATE-GAP:'+str(i));r=b.reserve();b.dispatch(r)
    elapsed=time.monotonic()-started;assert elapsed<60
    with owner.connect() as c:
        admitted=c.execute("SELECT count(*) n FROM shared_model_quota.reservations WHERE state='DISPATCHED'").fetchone()['n']
    assert admitted==31
    report={'status':'KNOWN_IMPLEMENTATION_GAP_NOT_AT_PASS','source':'V1 product design section10 default30RPM',
            'synthetic_dispatch_admissions_in_less_than_60_seconds':admitted,'elapsed_seconds':round(elapsed,3),
            'required_default_ceiling':30,'provider_requests':0,'real_budget':0,
            'next_finite_task':'R2 account-level pre-send rate gate using DB time; no reset/refund of dispatched attempts'}
    private=Path('.runtime');private.mkdir(exist_ok=True);(private/'eng009-rate-gap.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')

def test_assigned_status_role_never_receives_plan_documents(fixture):
    from test_authorization_files import add_role
    store,owner,tokens,client=fixture;provision(owner);run=submit(fixture);chain(store).execute(store.claim('worker'))
    user=add_role(owner,tokens,'park_specialist');owner.assign_status(user,run)
    headers={'Authorization':'Bearer '+tokens[user]}
    assert client.get('/api/runs/'+run,headers=headers).status_code==200
    response=client.get('/api/runs/'+run+'/plan-revisions',headers=headers)
    assert response.status_code==403 and 'SYNTHETIC local goal' not in response.text
