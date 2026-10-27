"""Explicit offline compact service selection; no execution or provider authority.

The original strict HTTP/usage boundary is retained. Only bounded trusted refs
and capability goals enter the prompt; the server independently rebuilds later.
"""
from copy import deepcopy
import hashlib
import json
import httpx
from .intern_adapter import ModelBoundaryError, MODEL, strict_json, safe_id, validated_usage
from .service_plan_planner import OfflineProposalPlanner, FAKE_TOKEN
from .service_selection import parse_selection, SelectionError, MAX_RELEASES
from .planning_constraints import Constraints
from .service_capability_contract import SERVICE_GOALS

ORIGIN = 'OFFLINE_SERVICE_SELECTION'


def compact_context(context):
    """Reject accidental parent/material/identity fields rather than forwarding."""
    try:
        if type(context) is not dict or set(context) != {'binding','required_goals','planning_constraints','available_services'}:
            raise ValueError()
        goals=context['required_goals']
        if type(goals) is not list or not 1<=len(goals)<=16 or any(type(g) is not str or not 0<len(g)<=160 for g in goals) or len(set(goals))!=len(goals):raise ValueError()
        constraints=Constraints.model_validate(context['planning_constraints']).model_dump()
        if constraints!=context['planning_constraints']:raise ValueError()
        services=context['available_services']
        if type(services) is not list or not 1<=len(services)<=MAX_RELEASES:raise ValueError()
        refs=[]
        for service in services:
            if type(service) is not dict or set(service)!={'ref','service_id','supported_goals'}:raise ValueError()
            kind=service['service_id'];supported=service['supported_goals']
            if kind not in SERVICE_GOALS or type(supported) is not list or not supported or any(type(g) is not str or g not in SERVICE_GOALS[kind] for g in supported) or len(set(supported))!=len(supported):raise ValueError()
            ref=service['ref']
            parse_selection(json.dumps(dict(schema_version=1,binding=context['binding'],selections=[ref]),allow_nan=False),context['binding'])
            if ref in refs:raise ValueError()
            refs.append(deepcopy(ref))
        return deepcopy(context),refs
    except ModelBoundaryError:raise
    except Exception:raise SelectionError() from None


class OfflineSelectionPlanner(OfflineProposalPlanner):
    def __init__(self,*,transport=None,budget=None,timeout=30):
        # No default transport: explicit exact MockTransport is the sole enablement.
        super().__init__(transport=transport,budget=budget,timeout=timeout)

    def propose(self,context,*,before_dispatch=None):
        self.require()
        context,available_refs=compact_context(context)
        content=json.dumps(dict(scope='SYNTHETIC_SERVICE_SELECTION_ONLY',**context),ensure_ascii=False,separators=(',',':'),allow_nan=False)
        if len(content.encode())>65536:raise ModelBoundaryError('MESSAGE_LIMIT')
        if FAKE_TOKEN in content:raise ModelBoundaryError('SECRET_INPUT_REJECTED')
        payload=dict(model=MODEL,messages=[dict(role='system',content='Return only compact JSON with schema_version 1, the exact binding, and selections containing exact available service refs. Select capabilities for all requested goals and declared constraints. These are references only, not execution. Do not return steps, actions, scripts, tools, materials or authority. The server independently checks satisfiability and rebuilds registered steps.'),dict(role='user',content=content)],stream=False,n=1,max_tokens=1024,thinking_mode=True)
        if before_dispatch:before_dispatch()
        record=self.budget.reserve();usage=None
        try:
            self.require()
            status,raw=self.transport.post(payload,FAKE_TOKEN,self.timeout)
            if status==429:raise ModelBoundaryError('RATE_LIMIT_NO_RETRY')
            if status in (401,403):raise ModelBoundaryError('AUTHORIZATION_FAILED')
            if status!=200:raise ModelBoundaryError('HTTP_ERROR_NO_RETRY')
            raw_text=raw.decode('utf-8')
            body=strict_json(raw_text)
            if type(body) is not dict or set(body)-{'id','model','choices','usage'}:raise ModelBoundaryError('INVALID_RESPONSE')
            if FAKE_TOKEN in json.dumps(body,ensure_ascii=False):raise ModelBoundaryError('SECRET_OUTPUT_REJECTED')
            if body.get('usage') is not None and (type(body['usage']) is not dict or set(body['usage'])!={'prompt_tokens','completion_tokens','total_tokens'}):raise ModelBoundaryError('INVALID_USAGE')
            usage=validated_usage(body.get('usage'))
            if type(body.get('model')) is not str or not body['model'].isascii() or body['model'].casefold()!=MODEL:raise ModelBoundaryError('MODEL_IDENTITY_MISMATCH')
            call_id=safe_id(body.get('id'));choices=body.get('choices')
            if type(choices) is not list or len(choices)!=1 or type(choices[0]) is not dict or set(choices[0])!={'index','message','finish_reason'}:raise ModelBoundaryError('INVALID_CHOICES')
            choice=choices[0]
            if type(choice['index']) is not int or choice['index']!=0:raise ModelBoundaryError('INVALID_CHOICES')
            if choice['finish_reason']=='length':raise ModelBoundaryError('TRUNCATED_NO_TOOL_EXECUTION')
            if choice['finish_reason']!='stop':raise ModelBoundaryError('PROPOSAL_TOOL_OR_INCOMPLETE_RESPONSE')
            message=choice['message']
            if type(message) is not dict or set(message)!={'role','content'} or message['role']!='assistant' or type(message['content']) is not str:raise ModelBoundaryError('INVALID_RESPONSE')
            selection=parse_selection(message['content'],context['binding'])
            if any(ref not in available_refs for ref in selection['selections']):raise SelectionError()
            if usage and usage['total_tokens']>self.budget.reserve_per_call:raise ModelBoundaryError('USAGE_RESERVATION_EXCEEDED')
            self.budget.finish(record,'VALIDATED',usage)
            from .controlled_plans import _hash
            return dict(selection=selection,selection_raw=message['content'],response_raw=raw_text,producer=dict(version=4,origin=ORIGIN,model=MODEL,returned_model=body['model'],call_id=call_id,usage=usage or 'UNKNOWN',mode='OFFLINE_HTTP_FIXTURE',provider_enabled=False,executed=False,selection_sha256=_hash(selection),response_sha256=hashlib.sha256(raw).hexdigest()),budget_record=deepcopy(record))
        except httpx.TimeoutException:
            self.budget.finish(record,'TIMEOUT_OUTCOME_UNKNOWN');raise ModelBoundaryError('TIMEOUT_OUTCOME_UNKNOWN') from None
        except httpx.TransportError:
            self.budget.finish(record,'TRANSPORT_OUTCOME_UNKNOWN');raise ModelBoundaryError('TRANSPORT_OUTCOME_UNKNOWN') from None
        except ModelBoundaryError as e:
            self.budget.finish(record,e.code,usage);raise
        except Exception:
            self.budget.finish(record,'INVALID_RESPONSE',usage);raise ModelBoundaryError('INVALID_RESPONSE') from None
