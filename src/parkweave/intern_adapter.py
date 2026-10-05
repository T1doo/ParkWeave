"""Official HTTP wire boundary, exercised only through explicit offline transport.
No environment lookup or tool execution; live dispatch needs explicit persistent authorization.
"""
from dataclasses import dataclass, field
import json
import re
import threading
from typing import Literal
import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr

ENDPOINT='https://chat.intern-ai.org.cn/api/v1/chat/completions'
MODEL='intern-s2'
TOOL={'type':'function','function':{'name':'case_create','description':'Propose a synthetic local case; requires current gateway authorization.',
      'parameters':{'type':'object','properties':{'goal':{'type':'string','minLength':1,'maxLength':2000}},'required':['goal'],'additionalProperties':False}}}


class ModelBoundaryError(Exception):
    def __init__(self,code):self.code=code;super().__init__(code)


class ToolArguments(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    goal:str=Field(min_length=1,max_length=2000)


@dataclass
class OfflineBudget:
    """Conservative local attempt ledger. NOT shared account coordination or money cost."""
    max_calls:int=3
    max_tokens:int=24576
    reserve_per_call:int=8192
    calls:int=0
    charged_tokens:int=0
    records:list=field(default_factory=list)
    _lock:threading.Lock=field(default_factory=threading.Lock,repr=False)

    def reserve(self):
        with self._lock:
            if not (1<=self.max_calls<=3 and 1<=self.reserve_per_call<=8192 and self.max_tokens>=0):
                raise ModelBoundaryError('INVALID_BUDGET')
            if self.calls>=self.max_calls or self.charged_tokens+self.reserve_per_call>self.max_tokens:
                raise ModelBoundaryError('BUDGET_EXHAUSTED')
            self.calls+=1;self.charged_tokens+=self.reserve_per_call
            record={'attempt':self.calls,'kind':'OFFLINE_HTTP_FIXTURE','outcome':'PENDING','usage':'UNKNOWN','reserved_tokens':self.reserve_per_call}
            self.records.append(record);return record

    def finish(self,record,outcome,usage=None):
        with self._lock:
            record['outcome']=outcome
            if usage is not None:
                self.charged_tokens+=usage['total_tokens']-self.reserve_per_call
                record['usage']=dict(usage)
                if usage['total_tokens']>self.reserve_per_call:record['reservation_overrun']=True
            # Missing usage, timeout and errors retain conservative reservation.


def safe_id(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',value):raise ModelBoundaryError('INVALID_ID')
    return value


def strict_json(raw):
    def object_pairs(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('duplicate key')
            result[key]=value
        return result
    def bad_constant(value):raise ValueError('nonfinite JSON constant')
    return json.loads(raw,object_pairs_hook=object_pairs,parse_constant=bad_constant)


def validate_call(call):
    try:
        if set(call)!={'id','type','function'} or call['type']!='function':raise ValueError()
        safe_id(call['id']);function=call['function']
        if set(function)!={'name','arguments'} or function['name']!='case_create':raise ValueError()
        raw=function['arguments']
        if not isinstance(raw,str) or len(raw.encode())>4096:raise ValueError()
        args=ToolArguments.model_validate(strict_json(raw))
        if not args.goal.strip():raise ValueError()
        return {'id':call['id'],'action':'case.create','arguments':args.model_dump()}
    except Exception as exc:raise ModelBoundaryError('INVALID_TOOL_PROPOSAL') from None


def validated_messages(messages):
    if not isinstance(messages,list) or not 1<=len(messages)<=8:raise ModelBoundaryError('MESSAGE_LIMIT')
    pending=set();seen=set();clean=[]
    for message in messages:
        if not isinstance(message,dict):raise ModelBoundaryError('INVALID_MESSAGE')
        role=message.get('role')
        if role not in ('system','user','assistant','tool'):raise ModelBoundaryError('INVALID_MESSAGE')
        allowed={'role','content'}|({'tool_calls'} if role=='assistant' else {'tool_call_id'} if role=='tool' else set())
        if set(message)-allowed:raise ModelBoundaryError('INVALID_MESSAGE')
        content=message.get('content')
        if content is not None and (not isinstance(content,str) or len(content.encode())>8192):raise ModelBoundaryError('MESSAGE_LIMIT')
        if role in ('user','system','tool') and (not content or not content.strip()):raise ModelBoundaryError('INVALID_MESSAGE')
        if role=='tool':
            call_id=message.get('tool_call_id')
            if call_id not in pending:raise ModelBoundaryError('UNMATCHED_TOOL_FEEDBACK')
            pending.remove(call_id)
        elif pending:raise ModelBoundaryError('MISSING_TOOL_FEEDBACK')
        if role=='assistant' and not content and 'tool_calls' not in message:raise ModelBoundaryError('INVALID_MESSAGE')
        if role=='assistant' and 'tool_calls' in message:
            calls=message['tool_calls']
            if not isinstance(calls,list) or len(calls)!=1:raise ModelBoundaryError('TOOL_LIMIT')
            proposal=validate_call(calls[0]);call_id=proposal['id']
            if call_id in seen:raise ModelBoundaryError('DUPLICATE_TOOL_ID')
            seen.add(call_id);pending.add(call_id)
        clean.append(message)
    if pending:raise ModelBoundaryError('MISSING_TOOL_FEEDBACK')
    # Explicit bounded payload; text is data. Tools are supplied by trusted code only.
    if len(json.dumps(clean,ensure_ascii=False).encode())>16384:raise ModelBoundaryError('MESSAGE_LIMIT')
    return clean


class InternChatAdapter:
    def __init__(self,*,transport,token:SecretStr,budget=None,timeout=30,before_dispatch=None,live_safety=None):
        from .http_transport import InternHTTPTransport
        if type(transport) is httpx.MockTransport:
            transport=InternHTTPTransport(transport)
        elif type(transport) is not InternHTTPTransport:
            raise ModelBoundaryError('LIVE_TRANSPORT_DISABLED')
        if transport.transport is None:
            from .quota import PersistentBudget
            from .live_safety import LiveSafety
            if type(live_safety) is not LiveSafety:raise ModelBoundaryError('LIVE_SAFETY_BLOCKED')
            live_safety.require()
            if type(budget) is not PersistentBudget or budget.kind!='LIVE':
                raise ModelBoundaryError('LIVE_BLOCKED_NO_AUTHORIZED_PARK_BUDGET')
        if not isinstance(token,SecretStr) or not token.get_secret_value().strip():raise ModelBoundaryError('TOKEN_REQUIRED')
        if type(timeout) not in (int,float) or not 0<timeout<=120:raise ModelBoundaryError('TIMEOUT_LIMIT')
        self.transport,self.token,self.budget,self.timeout=transport,token,budget or OfflineBudget(),timeout
        self.before_dispatch=before_dispatch
        self.live_safety=live_safety

    def live_complete(self,*args,**kwargs):
        raise ModelBoundaryError('LIVE_BLOCKED_NO_AUTHORIZED_PARK_BUDGET')

    def complete(self,messages,*,max_tokens=512):
        if self.transport.transport is None:
            from .live_safety import LiveSafety
            from .quota import PersistentBudget
            if type(self.live_safety) is not LiveSafety or type(self.budget) is not PersistentBudget or self.budget.kind!='LIVE':
                raise ModelBoundaryError('LIVE_SAFETY_BLOCKED')
            self.live_safety.require()
        if type(max_tokens) is not int or not 1<=max_tokens<=1024:raise ModelBoundaryError('OUTPUT_LIMIT')
        payload={'model':MODEL,'messages':validated_messages(messages),'tools':[TOOL],'stream':False,
                 'n':1,'max_tokens':max_tokens,'thinking_mode':True}
        if self.token.get_secret_value() in json.dumps(payload,ensure_ascii=False):raise ModelBoundaryError('SECRET_INPUT_REJECTED')
        record=self.budget.reserve();usage=None
        try:
            if self.before_dispatch:self.before_dispatch()
        except Exception:
            if hasattr(self.budget,'release'):self.budget.release(record)
            raise ModelBoundaryError('DISPATCH_AUTHORIZATION_CHANGED') from None
        if hasattr(self.budget,'dispatch'):self.budget.dispatch(record)
        try:
            status,raw=self.transport.post(payload,self.token.get_secret_value(),self.timeout)
            if status==429:raise ModelBoundaryError('RATE_LIMIT_NO_RETRY')
            if status in (401,403):raise ModelBoundaryError('AUTHORIZATION_FAILED')
            if status!=200:raise ModelBoundaryError('HTTP_ERROR_NO_RETRY')
            body=strict_json(raw)
            if self.token.get_secret_value() in json.dumps(body,ensure_ascii=False):raise ModelBoundaryError('SECRET_OUTPUT_REJECTED')
            raw_usage=body.get('usage')
            if raw_usage is not None:
                keys=('prompt_tokens','completion_tokens','total_tokens')
                if not isinstance(raw_usage,dict) or any(type(raw_usage.get(k)) is not int or not 0<=raw_usage[k]<=2**63-1 for k in keys):
                    raise ModelBoundaryError('INVALID_USAGE')
                candidate={k:raw_usage[k] for k in keys}
                if candidate['prompt_tokens']+candidate['completion_tokens']!=candidate['total_tokens']:raise ModelBoundaryError('INVALID_USAGE')
                usage=candidate
            if not isinstance(body.get('model'),str) or not body['model'].isascii() or body['model'].casefold()!=MODEL:
                raise ModelBoundaryError('MODEL_IDENTITY_MISMATCH')
            call_id=safe_id(body.get('id'));choices=body.get('choices')
            if not isinstance(choices,list) or len(choices)!=1 or choices[0].get('index')!=0:raise ModelBoundaryError('INVALID_CHOICES')
            choice=choices[0];reason=choice.get('finish_reason')
            if reason=='length':raise ModelBoundaryError('TRUNCATED_NO_TOOL_EXECUTION')
            if reason not in ('stop','tool_calls'):raise ModelBoundaryError('INCOMPLETE_RESPONSE')
            message=choice.get('message')
            if not isinstance(message,dict) or message.get('role')!='assistant':raise ModelBoundaryError('INVALID_RESPONSE')
            content=message.get('content')
            if content is not None and (not isinstance(content,str) or len(content.encode())>16384):raise ModelBoundaryError('RESPONSE_LIMIT')
            calls=message.get('tool_calls') or []
            if reason=='tool_calls':
                if not isinstance(calls,list) or len(calls)!=1:raise ModelBoundaryError('TOOL_LIMIT')
                proposal=validate_call(calls[0])
            else:
                if calls or not content or not content.strip():raise ModelBoundaryError('INVALID_RESPONSE')
                proposal=None
            result={'call_id':call_id,'model':MODEL,'returned_model':body['model'],'finish_reason':reason,
                    'content':content,'tool_proposal':proposal,'usage':usage if usage is not None else 'UNKNOWN',
                    'mode':'OFFLINE_HTTP_FIXTURE' if self.transport.transport is not None else 'LIVE_HTTP','executed':False}
            if usage and usage['total_tokens']>self.budget.reserve_per_call:raise ModelBoundaryError('USAGE_RESERVATION_EXCEEDED')
            self.budget.finish(record,'VALIDATED',usage);return result
        except httpx.TimeoutException:
            self.budget.finish(record,'TIMEOUT_OUTCOME_UNKNOWN');raise ModelBoundaryError('TIMEOUT_OUTCOME_UNKNOWN') from None
        except httpx.TransportError:
            self.budget.finish(record,'TRANSPORT_OUTCOME_UNKNOWN');raise ModelBoundaryError('TRANSPORT_OUTCOME_UNKNOWN') from None
        except ModelBoundaryError as exc:
            self.budget.finish(record,exc.code,usage);raise
        except Exception:
            self.budget.finish(record,'INVALID_RESPONSE',usage);raise ModelBoundaryError('INVALID_RESPONSE') from None
