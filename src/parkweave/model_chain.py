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
from .plan_revision import initial,fingerprint,validate_revision

FAKE_TOKEN='synthetic-worker-token-not-a-credential'
REVISION_INSTRUCTIONS=("Return only JSON with schema_version=parkweave/local-plan-revision/1, revision=2, "
    "previous_sha256=plan_before_sha256, goal=exact original user goal, operation_id and tool_call_id from feedback, "
    "receipt_sha256 from feedback, step={action:case.create,state:LOCAL_RECORD_CREATED,case_id:feedback.case_id}, "
    "case_state=NEEDS_INPUT,next_step=REQUEST_MISSING_INPUT,success_scope=LOCAL_CASE_CREATED, "
    "external_acceptance=NOT_SUBMITTED,offline_fulfillment=NO_EVIDENCE. No extra fields or new actions. "
    "Local record creation means waiting for missing input, not eligibility, external acceptance or fulfillment.")

def synthetic_transport(scenario='good'):
    def handler(request):
        payload=json.loads(request.content);feedback=payload['messages'][-1]['role']=='tool'
        goal=payload['messages'][0]['content']
        call={'id':'fixture-tool','type':'function','function':{'name':'case_create','arguments':json.dumps({'goal':goal})}}
        if feedback:
            data=json.loads(payload['messages'][-1]['content'])
            document={'schema_version':'parkweave/local-plan-revision/1','revision':2,
                      'previous_sha256':data['plan_before_sha256'],'goal':goal,
                      'operation_id':data['operation_id'],'tool_call_id':data['tool_call_id'],
                      'receipt_sha256':data['receipt_sha256'],
                      'step':{'action':'case.create','state':'LOCAL_RECORD_CREATED','case_id':data['case_id']},
                      'case_state':data['state'],'next_step':'REQUEST_MISSING_INPUT','success_scope':'LOCAL_CASE_CREATED',
                      'external_acceptance':data['external_acceptance'],'offline_fulfillment':data['offline_fulfillment']}
            message={'role':'assistant','content':json.dumps(document,ensure_ascii=False)}
        else:message={'role':'assistant','content':None,'tool_calls':[call]}
        reason='stop' if feedback else 'tool_calls'
        if scenario=='timeout':raise httpx.ReadTimeout('synthetic timeout',request=request)
        if scenario=='bad-args':call['function']['arguments']='{}'
        if scenario=='truncated':reason='length'
        if scenario=='secret-echo':message['content']=FAKE_TOKEN
        if scenario=='feedback-error' and feedback:reason='length'
        return httpx.Response(200,json={'id':'fixture-feedback-response' if feedback else 'fixture-plan-response','model':'wrong' if scenario=='wrong-model' else 'Intern-S2',
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
            before=self.save_before(claim,plan)
            r,op=self.authority(claim)
            if op['state']=='PREPARED':ExecutionGateway(self.store).execute(claim,defer_completion=True)
            r,op=self.authority(claim)
            if op['state']!='VERIFIED':raise Conflict('no verified local effect')
            phase='FEEDBACK'
            call={'id':proposal['id'],'type':'function','function':{'name':'case_create','arguments':json.dumps(proposal['arguments'])}}
            # Feedback derives from committed gateway receipt and Case fields, not model claims.
            with self.store.connect() as c:
                case=c.execute('SELECT id,state,external_acceptance,offline_fulfillment FROM cases WHERE run_id=%s',(claim['id'],)).fetchone()
            feedback=op['receipt']|{k:v for k,v in case.items() if k!='id'}|{
                'plan_before_sha256':fingerprint(before),'operation_id':str(op['id']),
                'tool_call_id':proposal['id'],'receipt_sha256':fingerprint(op['receipt']),
                'revision_instructions':REVISION_INSTRUCTIONS}
            messages += [{'role':'assistant','content':None,'tool_calls':[call]},
                         {'role':'tool','tool_call_id':proposal['id'],'content':json.dumps(feedback)}]
            final=self.step(claim,phase,messages)
            if final['finish_reason']!='stop' or final['tool_proposal']:raise ModelBoundaryError('FEEDBACK_TOOL_REJECTED')
            self.complete_revision(claim,final)
        except (ModelBoundaryError,Denied) as exc:
            code=exc.code if isinstance(exc,ModelBoundaryError) else 'AUTHORIZATION_REVOKED'
            self.fail(claim,phase,code)
    def insert_artifact(self,c,claim,document,provider_call_id):
        sha=fingerprint(document)
        c.execute("INSERT INTO model_plans(run_id,revision,document,sha256,provider_call_id,tool_call_id) "
                  "VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                  (claim['id'],document['revision'],Jsonb(document),sha,provider_call_id,document['tool_call_id']))
        row=c.execute('SELECT * FROM model_plans WHERE run_id=%s AND revision=%s',
                      (claim['id'],document['revision'])).fetchone()
        if row['document']!=document or row['sha256']!=sha or row['provider_call_id']!=provider_call_id:
            raise ModelBoundaryError('PLAN_ARTIFACT_CONFLICT')
    def save_before(self,claim,plan):
        with self.store.connect() as c:
            p,r,op=self.store.locked_execution(c,claim);self.store.check_execution(c,p,r)
            if r['control_intent']!='CONTINUE':raise Conflict('control changed')
            document=initial(r['input']['goal'],op['id'],plan['tool_proposal']['id'])
            row=c.execute('SELECT * FROM model_plans WHERE run_id=%s AND revision=1',(claim['id'],)).fetchone()
            if row is None and op['state']!='PREPARED':raise ModelBoundaryError('PRE_EFFECT_PLAN_MISSING')
            self.insert_artifact(c,claim,document,plan['call_id'])
            return document
    def complete_revision(self,claim,final):
        with self.store.connect() as c:
            p,r,op=self.store.locked_execution(c,claim);self.store.check_execution(c,p,r)
            if r['control_intent']!='CONTINUE' or op['state']!='VERIFIED':raise Conflict('known effect required')
            before=c.execute('SELECT * FROM model_plans WHERE run_id=%s AND revision=1',(claim['id'],)).fetchone()
            case=c.execute('SELECT * FROM cases WHERE run_id=%s',(claim['id'],)).fetchone()
            if not before or before['sha256']!=fingerprint(before['document']):raise ModelBoundaryError('PRE_EFFECT_PLAN_MISSING')
            document=validate_revision(final['content'],before['document'],op['receipt'],case)
            self.insert_artifact(c,claim,document,final['call_id'])
            # Accepted artifact and terminal Run/outbox are a single transaction.
            c.execute("UPDATE runs SET state='SUCCEEDED',lease_until=NULL,revision=revision+1 WHERE id=%s",(claim['id'],))
            self.store.event(c,claim['id'])
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
