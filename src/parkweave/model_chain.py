"""Bounded planning -> currently authorized trusted Case -> actual receipt feedback.
Only explicit synthetic worker fixture is wired here. Live activation is separate.
No generated code, eligibility, external acceptance or fulfillment from model text.
"""
import json
import httpx
from psycopg.types.json import Jsonb
from pydantic import SecretStr
from .intern_adapter import InternChatAdapter,ModelBoundaryError
from .http_transport import InternHTTPTransport
from .quota import PersistentBudget
from .gateway import ExecutionGateway
from .store import Conflict,Denied,digest
from .domain import Intake

FAKE_TOKEN='synthetic-worker-token-not-a-credential'

def synthetic_transport(scenario='good'):
    def handler(request):
        payload=json.loads(request.content);feedback=payload['messages'][-1]['role']=='tool'
        goal=payload['messages'][0]['content']
        call={'id':'fixture-tool','type':'function','function':{'name':'case_create','arguments':json.dumps({'goal':goal})}}
        message={'role':'assistant','content':'SYNTHETIC local receipt acknowledged'} if feedback else {'role':'assistant','content':None,'tool_calls':[call]}
        reason='stop' if feedback else 'tool_calls'
        if scenario=='timeout':raise httpx.ReadTimeout('synthetic timeout',request=request)
        if scenario=='bad-args':call['function']['arguments']='{}'
        if scenario=='truncated':reason='length'
        if scenario=='secret-echo':message['content']=FAKE_TOKEN
        if scenario=='feedback-error' and feedback:reason='length'
        return httpx.Response(200,json={'id':'fixture-response','model':'wrong' if scenario=='wrong-model' else 'Intern-S2',
            'choices':[{'index':0,'message':message,'finish_reason':reason}],
            'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}})
    return InternHTTPTransport(httpx.MockTransport(handler))

class ModelChain:
    def __init__(self,store,*,quota_dsn,account,product='parkweave',transport,token,kind='SYNTHETIC'):
        self.store,self.quota_dsn,self.account,self.product=store,quota_dsn,account,product
        self.transport,self.token,self.kind=transport,token,kind
    def authority(self,claim):
        with self.store.connect() as c:
            p,r,op=self.store.locked_execution(c,claim)
            self.store.check_execution(c,p,r)
            if r['control_intent']!='CONTINUE' or op['action']!='case.create':raise Conflict('model scope denied')
            if digest(json.dumps(r['input'],sort_keys=True,ensure_ascii=False))!=r['fingerprint']:raise Conflict('intent changed')
            Intake.model_validate(r['input'])
            return r,op
    def step(self,claim,phase,messages):
        self.authority(claim)
        with self.store.connect() as c:
            self.store.locked_execution(c,claim)
            row=c.execute('SELECT * FROM model_steps WHERE run_id=%s AND phase=%s',(claim['id'],phase)).fetchone()
            if row and row['state']=='VALIDATED':return row['result']
            if row and row['state']=='FAILED':raise ModelBoundaryError(row['outcome'])
            c.execute("INSERT INTO model_steps VALUES(%s,%s,'STARTED',NULL,NULL) ON CONFLICT DO NOTHING",(claim['id'],phase))
        budget=PersistentBudget(self.quota_dsn,account=self.account,product=self.product,work=f"{claim['id']}:{phase}",kind=self.kind)
        adapter=InternChatAdapter(transport=self.transport,token=self.token,budget=budget,before_dispatch=lambda:self.authority(claim))
        result=adapter.complete(messages)
        self.authority(claim)
        with self.store.connect() as c:
            self.store.locked_execution(c,claim)
            c.execute("UPDATE model_steps SET state='VALIDATED',result=%s WHERE run_id=%s AND phase=%s",(Jsonb(result),claim['id'],phase))
        return result
    def execute(self,claim):
        phase='PLAN'
        try:
            r,op=self.authority(claim)
            messages=[{'role':'user','content':r['input']['goal']}]
            plan=self.step(claim,phase,messages)
            proposal=plan['tool_proposal']
            if plan['finish_reason']!='tool_calls' or not proposal or proposal['arguments']!={'goal':r['input']['goal']}:
                raise ModelBoundaryError('INTENT_PROPOSAL_MISMATCH')
            r,op=self.authority(claim)
            if op['state']=='PREPARED':ExecutionGateway(self.store).execute(claim,defer_completion=True)
            r,op=self.authority(claim)
            if op['state']!='VERIFIED':raise Conflict('no verified local effect')
            phase='FEEDBACK'
            call={'id':proposal['id'],'type':'function','function':{'name':'case_create','arguments':json.dumps(proposal['arguments'])}}
            # Feedback derives from committed gateway receipt and Case fields, not model claims.
            with self.store.connect() as c:
                case=c.execute('SELECT state,external_acceptance,offline_fulfillment FROM cases WHERE run_id=%s',(claim['id'],)).fetchone()
            messages += [{'role':'assistant','content':None,'tool_calls':[call]},
                         {'role':'tool','tool_call_id':proposal['id'],'content':json.dumps(op['receipt']|case)}]
            final=self.step(claim,phase,messages)
            if final['finish_reason']!='stop' or final['tool_proposal']:raise ModelBoundaryError('FEEDBACK_TOOL_REJECTED')
            with self.store.connect() as c:
                p,r,op=self.store.locked_execution(c,claim);self.store.check_execution(c,p,r)
                if r['control_intent']!='CONTINUE':raise Conflict('control changed')
                c.execute("UPDATE runs SET state='SUCCEEDED',lease_until=NULL,revision=revision+1 WHERE id=%s",(claim['id'],))
                self.store.event(c,claim['id'])
        except (ModelBoundaryError,Denied) as exc:
            code=exc.code if isinstance(exc,ModelBoundaryError) else 'AUTHORIZATION_REVOKED'
            self.fail(claim,phase,code)
    def fail(self,claim,phase,code):
        fail_model_run(self.store,claim,phase,code)

def fail_model_run(store,claim,phase,code):
    with store.connect() as c:
        p,r,op=store.locked_execution(c,claim)
        c.execute("INSERT INTO model_steps VALUES(%s,%s,'FAILED',NULL,%s) "
                  "ON CONFLICT(run_id,phase) DO UPDATE SET state='FAILED',result=NULL,outcome=excluded.outcome",
                  (claim['id'],phase,code))
        if op['state']=='VERIFIED':
            # Known local effect survives feedback failure/withdrawal. Never mark FAILED_SAFE.
            c.execute("UPDATE runs SET state='FAILED',lease_until=NULL,revision=revision+1 WHERE id=%s",(claim['id'],))
            store.event(c,claim['id'])
        else:store.safe_failure(c,r,op,code)
