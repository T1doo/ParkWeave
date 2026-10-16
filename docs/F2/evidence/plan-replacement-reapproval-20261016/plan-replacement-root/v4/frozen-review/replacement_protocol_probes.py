"""Independent finite protocol probes: no DB, HTTP, browser, or authority."""
from copy import deepcopy
from uuid import uuid4
import json
from parkweave import service_plan_approval as a, controlled_plans as cp
from parkweave.store import Conflict
from legacy_protocol_fixture import fixture, append, cycle


def replacement(p,prior,mutate=None):
    aid=str(uuid4());old=prior['plan_approval']['id']
    _,items=a._ledger(p);old_context=deepcopy(items[old]['proposal']['binding']['context'])
    old_context['plan_definition_sha256']='1'*64
    old_id=old_context['plan_id'];new_id=str(uuid4())
    data=dict(members=[dict(hold_id=str(uuid4()),expected_revision=1) for _ in range(3)],expected_preparation_revision=1,expected_plan_revision=2,expected_source_sha256='a'*64,valid_until='2099-01-01T00:00:00+00:00',reason='SYNTHETIC pure replacement protocol probe',expected_link_revision=1,expected_previous_plan_id=old_id)
    ref=lambda n:dict(release_id='synthetic-release-'+str(n),revision=1,release_sha256='2'*64,instance_id='synthetic-instance-'+str(n),config_revision=1,config_sha256='3'*64)
    pairs=[dict(original_ref=ref(n),target_ref={**ref(n),'revision':2,'release_sha256':'4'*64},original_source_sha256='5'*64,target_source_sha256='6'*64,comparison=dict(classification='COMPATIBLE',differences=[],affected=[],blocking_reasons=[])) for n in range(3)]
    comp=dict(schema=1,profile='ORIGINAL_V4_SERVICE_RELEASE_PLAN_REPLACEMENT_V1',classification='NEEDS_RECHECK',previous_candidate_id=str(uuid4()),replacement_candidate_id=str(uuid4()),previous_candidate_sha256='7'*64,replacement_candidate_sha256='8'*64,frozen_registry_sha256='9'*64,pairs=pairs,affected=[str(uuid4()) for _ in range(5)],preserved=[],automatic_adoption=False,automatic_approval=False,automatic_release=False)
    proof=dict(link_id=str(uuid4()),link_revision=1,snapshot_sha256='a'*64,previous_delivery_context=old_context,previous_approved_plan_revision=1,approved_plan_revision=2,previous_plan_id=old_id,replacement_plan_id=new_id,previous_definition_sha256='1'*64,replacement_definition_sha256='b'*64,replacement_adoption_event_id=str(uuid4()),replacement_adoption_sha256='c'*64,compatibility=comp,compatibility_sha256=cp._hash(comp))
    context={**old_context,'plan_id':new_id,'plan_definition_sha256':'b'*64,'plan_replacement':proof}
    b=dict(scope=a.SCOPE,purpose=a.REPLACEMENT_PURPOSE,context=context,plan_revision=2,execution_identity={},authority={},authority_sha256=cp._hash({}),materials=[],members=[dict(id=m['hold_id'],resource_revision=1) for m in data['members']],resource_revisions=[],source_versions={},valid_until=data['valid_until'],contract_scope_ids=[p['id']])
    if mutate:mutate(data,b)
    prop=append(p,'PROPOSE',aid,dict(action='PROPOSE',expected_revision=p[a.COL]['revision'],delivery=deepcopy(data)),binding=b)
    approve=append(p,'APPROVE',aid,dict(action='APPROVE',approval_id=aid,expected_revision=p[a.COL]['revision'],expected_binding_sha256=cp._hash(b),reason='SYNTHETIC explicit pure approval'))
    eid=str(uuid4());key='replacement_'+uuid4().hex;fp='d'*64
    receipt=dict(combination_id=str(uuid4()),plan_approval=dict(scope=a.SCOPE,id=aid,approval_event_id=approve['id'],consumption_event_id=eid,binding_sha256=cp._hash(b)),delivery_binding=dict(request_key=key,fingerprint=fp))
    append(p,'CONSUME',aid,dict(action='CONSUME',delivery={**data,'approval_id':aid}),receipt=dict(combination_id=receipt['combination_id'],request_key=key,fingerprint=fp,receipt_sha256=cp._hash(receipt)),event_id=eid,key=key)
    return receipt


def run():
    results=[]
    def case(name,mutation=None,revision=2,reject=True):
        p=fixture();prior=cycle(p)
        try:
            receipt=replacement(p,prior,mutation);a.verify_receipt(p,receipt,link_revision=revision)
        except (Conflict,ValueError):
            if not reject:raise
            results.append(dict(scenario=name,status='PASS',expected='REJECT'));return
        if reject:raise AssertionError(name+' accepted')
        results.append(dict(scenario=name,status='PASS',expected='ACCEPT'))
    def profile(b):return b['context']['plan_replacement']
    def comp_mut(fn):
        def mut(d,b):
            fn(profile(b)['compatibility']);profile(b)['compatibility_sha256']=cp._hash(profile(b)['compatibility'])
        return mut
    case('first_then_replacement_original_link2',reject=False)
    case('replacement_purpose_downgrade',lambda d,b:b.update(purpose=a.REAPPROVAL_PURPOSE))
    case('strip_previous_plan_request',lambda d,b:d.pop('expected_previous_plan_id'))
    case('strip_replacement_profile',lambda d,b:b['context'].pop('plan_replacement'))
    case('null_replacement_profile',lambda d,b:b['context'].update(plan_replacement=None))
    case('extra_profile_field',lambda d,b:profile(b).update(invented=True))
    case('replacement_definition_does_not_match_context',lambda d,b:profile(b).update(replacement_definition_sha256='e'*64))
    case('previous_definition_does_not_match_context',lambda d,b:profile(b).update(previous_definition_sha256='f'*64))
    case('compatibility_unknown_nested_field',comp_mut(lambda v:v.update(invented=True)))
    case('compatibility_empty_pairs',comp_mut(lambda v:v.update(pairs=[])))
    case('compatibility_breaking_pair',comp_mut(lambda v:v['pairs'][0]['comparison'].update(classification='BREAKING_REJECTED')))
    case('compatibility_unknown_pair_field',comp_mut(lambda v:v['pairs'][0].update(invented=True)))
    case('compatibility_removed_goal_unstated_profile',comp_mut(lambda v:v.update(classification='UNKNOWN')))
    case('actual_link_self_anchor',revision=1)
    case('actual_link_skips_revision',revision=3)
    return dict(scope='PURE_FINITE_LEDGER_RECEIPT_NO_DATABASE_HTTP_BROWSER',results=results)

if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))
