"""Independent WIP history probes: one owned PG/HTTP origin, pure mutations.

This supplements, and is not part of, any frozen complete-module denominator.
The original five-goal fixture is used only to obtain an actual note receipt.
"""
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
import json

from parkweave import material_package_continuation as package
from parkweave import plan_source_conflicts as notes, case_opportunities as op
from parkweave import service_case_steps as service
from test_plan_source_conflicts import http_f, link_fixture, receipt_fixture, preparation_fixture
from test_plan_source_conflicts import complete, edit
from test_case_opportunities import imported
from test_preparation import headers, add, command as prepare

OUT = Path(__file__).parent


def get(f,p,card):
    return f[3].get('/api/preparations/'+p['preparation_id']+'/plan-material-package',
                    params={'card_id':card['id']},headers=headers(f[2]))


def send(f,p,v,key):
    body=deepcopy(v['action_requests']['KEEP_AND_CONTINUE'])
    body['reason']='SYNTHETIC independent package history review'
    return f[3].post('/api/preparations/'+p['preparation_id']+'/plan-material-package/commands',
                    headers=headers(f[2],key=key),json=body)


def cold(f,p,key):
    return f[3].get('/api/preparations/'+p['preparation_id']+'/plan-material-package/recovery/'+key,
                   headers=headers(f[2]))


def reseal(parent):
    """Recompute only this new event; the old card/B/M prefix is unchanged."""
    event=parent['service_case_plan']['events'][-1]
    proof=event['plan_note'];basis=proof['preview_basis']
    change=basis['source_change']
    change['sha256']=notes.sha({k:v for k,v in change.items() if k!='sha256'})
    proof['preview_sha256']=notes.sha(basis)
    proof['request']['expected_preview_sha256']=proof['preview_sha256']
    event['fingerprint']=notes.sha(dict(preparation_id=str(parent['id']),**proof['request']))
    proof['sha256']=notes.sha({k:v for k,v in proof.items() if k!='sha256'})
    counterpart=next(e for e in parent['opportunities']['events'] if e['id']==proof['op_event_id'])
    counterpart['fingerprint']=event['fingerprint']
    counterpart['payload']['plan_event']=deepcopy(event)
    counterpart['sha256']=op.sha({k:v for k,v in counterpart.items() if k!='sha256'})


def test_actual_v3_pure_history_matrix_and_later_current_epoch_change(http_f):
    f=http_f;p,_,_,_=complete(f,local=True)
    original=edit(f,p,'  SYNTHETIC original manual text  ')
    _,cards,_=imported(f,p);card=cards['cards'][0]
    v=get(f,p,card);assert v.status_code==200,v.text
    key=uuid4().hex;posted=send(f,p,v.json(),key);assert posted.status_code==200,posted.text
    receipt=posted.json()['receipt']
    with f[1].connect() as c:parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
    service._recovery_proofs(parent)
    results=[]
    def damage(name,change,expected_rejected=True):
        value=deepcopy(parent);e=value['service_case_plan']['events'][-1];proof=e['plan_note'];basis=proof['preview_basis'];q=basis['package_confirmation']
        change(value,e,proof,basis,q);reseal(value)
        try:service._recovery_proofs(value);rejected=False
        except Exception as error:
            from parkweave.store import Conflict
            if not isinstance(error,(Conflict,ValueError)):raise
            rejected=True
        results.append(dict(name=name,expected_rejected=expected_rejected,actual_rejected=rejected,
                            result='PASS' if rejected==expected_rejected else 'UNEXPECTED_ACCEPTANCE'))
    for value in (True,3.0,4):damage('proof_version_'+repr(value),lambda p,e,x,b,q,v=value:x.update(version=v))
    for value in (True,2.0,1):damage('request_schema_'+repr(value),lambda p,e,x,b,q,v=value:x['request'].update(schema=v))
    for value in (1,1.0,'true',False):damage('request_confirmation_'+repr(value),lambda p,e,x,b,q,v=value:x['request'].update(confirm_package=v))
    for field in ('baseline','current'):
        for value in (True,1.0):damage('epoch_'+field+'_version_'+repr(value),lambda p,e,x,b,q,f=field,v=value:q['epochs'][f][0].update(version=v))
    for value in (True,3.0,2):damage('basis_schema_'+repr(value),lambda p,e,x,b,q,v=value:b.update(schema=v))
    damage('core_schema_bool',lambda p,e,x,b,q:q.update(schema=True))
    damage('core_policy_claim_summary_carriage',lambda p,e,x,b,q:q['policy'].update(need_summary='COPY_INTO_NOTE'))
    damage('core_first_confirmation_claims_active',lambda p,e,x,b,q:q.update(active=True,mode='PACKAGE_V3'))
    damage('core_changes_sticky_required',lambda p,e,x,b,q:q.update(outline_carriage_required=True))
    damage('core_manual_text',lambda p,e,x,b,q:q['manual'].update(text='SYNTHETIC forged manual'))
    damage('core_baseline_full_object',lambda p,e,x,b,q:q['baseline_package'][0].update(source_label='SYNTHETIC changed capture'))
    damage('epoch_current_nondecimal',lambda p,e,x,b,q:q['epochs']['current'][0].update(row_epoch='1e3'))
    damage('epoch_case_extra_field',lambda p,e,x,b,q:q['epochs']['case_versions'].update(unexpected=True))
    damage('epoch_grant_not_bool',lambda p,e,x,b,q:q['epochs']['case_versions']['action_grant_epochs'][0].update(active=1))
    damage('epoch_source_hash_differs_outer',lambda p,e,x,b,q:q['epochs']['case_versions'].update(source_epochs_sha256='f'*64))
    damage('current_package_missing_slot',lambda p,e,x,b,q:b['materials'].pop())
    damage('current_package_duplicate_slot',lambda p,e,x,b,q:b['materials'].__setitem__(0,deepcopy(b['materials'][1])))
    damage('keep_changes_after_manual',lambda p,e,x,b,q:x['after_note'].update(text='SYNTHETIC not kept',text_sha256=notes.digest('SYNTHETIC not kept')))
    # This preview is a record, not ADOPT authority. Redundant saved metadata
    # still must be closed and agree with its outer immutable ledger binding.
    damage('source_change_extra_key',lambda p,e,x,b,q:b['source_change'].update(unexpected=True))
    damage('source_change_binding_foreign',lambda p,e,x,b,q:b['source_change']['binding'].update(org_id='SYNTHETIC foreign org'))
    damage('source_change_ledger_revision_bool',lambda p,e,x,b,q:b['source_change'].update(ledger_revision=True))
    damage('source_change_ledger_prefix_wrong',lambda p,e,x,b,q:b['source_change'].update(ledger_sha256='f'*64))
    damage('source_change_epoch_hash_wrong',lambda p,e,x,b,q:b['source_change'].update(source_epochs_sha256='f'*64))
    damage('source_change_typed_schema_bool',lambda p,e,x,b,q:b['source_change']['source_impact'].update(schema=True))
    damage('source_change_typed_schema_unknown',lambda p,e,x,b,q:b['source_change']['source_impact'].update(schema=9))
    path=OUT/'history-matrix-result.json'
    path.write_text(json.dumps(dict(scope='WIP owned-PG/HTTP origin plus pure history mutation matrix; old five-goal fixture, not six-goal acceptance',
         units=len(results),results=results,real_origin_HTTP=True,owned_PG=True,pure_mutations_persisted=False),indent=2)+'\n')
    # Legitimate later current epochs may alter availability, not the old receipt.
    changed=add(f,p,slot='need_summary',text='SYNTHETIC later real summary').json()
    changed=prepare(f,changed,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC real later review').json()
    changed=prepare(f,changed,'CONFIRM',reason='SYNTHETIC real later confirmation').json()
    recovered=cold(f,p,key);assert recovered.status_code==200,recovered.text
    assert recovered.json()['status']=='COMMITTED' and recovered.json()['receipt']==receipt
    assert recovered.json()['current']['action_requests']=={}
    with f[1].connect() as c:current=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
    assert current['service_case_plan']['events'][:len(parent['service_case_plan']['events'])]==parent['service_case_plan']['events']
    service._recovery_proofs(current)
    (OUT/'historical-cold-result.json').write_text(json.dumps(dict(status='PASS',old_event_byte_equal=True,
      legitimate_later_actions=['ADD_need_summary','REVIEW','CONFIRM'],actual_HTTP=True,owned_PG=True,
      original_old_note_event_preserved=original['receipt'] in recovered.json()['current'].get('history',[]),
      note='Package history intentionally lists v3 only; old v1 remains in original endpoint and ledger.'),indent=2)+'\n')
    assert all(r['result']=='PASS' for r in results),[r['name'] for r in results if r['result']!='PASS']
