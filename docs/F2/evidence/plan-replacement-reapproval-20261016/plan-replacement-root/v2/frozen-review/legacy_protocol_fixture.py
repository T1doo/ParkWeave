"""Pure original ledger/receipt invariant probes. No HTTP, browser, DB or authority."""
from copy import deepcopy
from uuid import uuid4
from parkweave import service_plan_approval as a, controlled_plans as cp
from parkweave.store import Conflict


def fixture():
    p={k:str(uuid4()) for k in ('id','case_id','run_id','owner_id','park_id','org_id')}
    p.update(candidate_plan_approvals=dict(namespace=a.SCOPE,version=1,revision=0,events=[]),candidate_plan_approval_head=None)
    return p


def append(p,action,aid,request,binding=None,receipt=None,event_id=None,key=None):
    value=p[a.COL];revision=len(value['events'])+1
    e=dict(id=event_id or str(uuid4()),revision=revision,approval_id=aid,action=action,actor_id=p['owner_id'],key=key or 'review_'+uuid4().hex,
        fingerprint=a._fingerprint(p['id'],request),request=request,binding=binding,receipt=receipt,at='2026-10-16T00:00:00+00:00',previous_sha256=value['events'][-1]['sha256'] if value['events'] else None)
    e['sha256']=cp._hash(e);value['events'].append(e);value['revision']=revision;p['candidate_plan_approval_head']=dict(revision=revision,sha256=e['sha256']);return e


def cycle(p,link=None,*,anchor_extra=False,first_anchor_null=False,consume=True):
    aid=str(uuid4());plan='11111111-1111-4111-8111-111111111111';rev=3 if link is not None else 1
    data=dict(members=[dict(hold_id=str(uuid4()),expected_revision=1) for _ in range(3)],expected_preparation_revision=1,expected_plan_revision=rev,expected_source_sha256='a'*64,valid_until='2099-01-01T00:00:00+00:00',reason='SYNTHETIC independent pure invariant')
    if link is not None:data['expected_link_revision']=link
    context={name:p[source] for source,name in [('id','preparation_id'),('case_id','case_id'),('run_id','run_id'),('owner_id','owner_id'),('park_id','park_id'),('org_id','org_id')]};context.update(preparation_revision=1,plan_id=plan)
    if link is not None:
        context['source_reapproval']=dict(link_id=str(uuid4()),link_revision=link,snapshot_sha256='b'*64,previous_delivery_context=dict(plan_id=plan),previous_approved_plan_revision=1,approved_plan_revision=rev,source_adoption_event_id=str(uuid4()),source_adoption_revision=2,source_adoption_sha256='c'*64,source_change_sha256='d'*64)
        if anchor_extra:context['source_reapproval']['invented']='not in original contract'
    if first_anchor_null:context['source_reapproval']=None
    binding=dict(scope=a.SCOPE,purpose=a.REAPPROVAL_PURPOSE if link is not None else a.PURPOSE,context=context,plan_revision=rev,execution_identity={},authority={},authority_sha256=cp._hash({}),materials=[],members=[dict(id=m['hold_id'],resource_revision=m['expected_revision']) for m in data['members']],resource_revisions=[],source_versions={},valid_until=data['valid_until'],contract_scope_ids=[p['id']])
    prop=append(p,'PROPOSE',aid,dict(action='PROPOSE',expected_revision=p[a.COL]['revision'],delivery=deepcopy(data)),binding=binding)
    approve=append(p,'APPROVE',aid,dict(action='APPROVE',approval_id=aid,expected_revision=p[a.COL]['revision'],expected_binding_sha256=cp._hash(binding),reason='SYNTHETIC original explicit approval'))
    eid=str(uuid4());key='original_effect_'+uuid4().hex;fp='e'*64
    proof=dict(scope=a.SCOPE,id=aid,approval_event_id=approve['id'],consumption_event_id=eid,binding_sha256=cp._hash(binding))
    actual=dict(combination_id=str(uuid4()),plan_approval=proof,delivery_binding=dict(request_key=key,fingerprint=fp))
    if consume:append(p,'CONSUME',aid,dict(action='CONSUME',delivery=dict(data,approval_id=aid)),receipt=dict(combination_id=actual['combination_id'],request_key=key,fingerprint=fp,receipt_sha256=cp._hash(actual)),event_id=eid,key=key)
    return actual


def run():
    results=[]
    def yes(name,fn):fn();results.append(dict(scenario=name,status='PASS',expected='ACCEPT'))
    def no(name,fn):
        try:fn()
        except Conflict:results.append(dict(scenario=name,status='PASS',expected='CONFLICT'));return
        raise AssertionError(name+' was accepted')
    p=fixture();first=cycle(p);yes('original_first_ledger_and_actual_link1',lambda:a.verify_receipt(p,first,link_revision=1))
    second=cycle(p,1);yes('original_then_reapproval_actual_link2',lambda:a.verify_receipt(p,second,link_revision=2))
    q=fixture();cycle(q,consume=False);last=cycle(q);yes('other_unconsumed_approved_candidate_does_not_block_first',lambda:a.verify_receipt(q,last,link_revision=1))
    q=deepcopy(p);last=cycle(q);no('second_first_purpose_consume_is_not_legacy',lambda:a.verify_receipt(q,last,link_revision=3))
    q=fixture();last=cycle(q,1);no('reapproval_requires_prior_consumption',lambda:a.verify_receipt(q,last,link_revision=2))
    no('first_purpose_cannot_bind_actual_link2',lambda:a.verify_receipt(p,first,link_revision=2))
    no('reapproval_cannot_claim_actual_self_anchor',lambda:a.verify_receipt(p,second,link_revision=1))
    no('missing_approval_cannot_be_actual_later_link',lambda:a.verify_receipt({},dict(combination_id=str(uuid4())),link_revision=2))
    no('boolean_is_not_actual_link_revision',lambda:a.verify_receipt(p,first,link_revision=True))
    q=fixture();last=cycle(q,first_anchor_null=True);no('first_purpose_cannot_keep_null_reapproval_anchor',lambda:a._ledger(q))
    q=fixture();cycle(q);cycle(q,1,anchor_extra=True);no('reapproval_anchor_extra_field_rejected',lambda:a._ledger(q))
    return dict(scope='PURE_ORIGINAL_LEDGER_AND_RECEIPT_VALIDATORS_NO_DB_HTTP_BROWSER',results=results)


if __name__=='__main__':
    import json
    print(json.dumps(run()))
