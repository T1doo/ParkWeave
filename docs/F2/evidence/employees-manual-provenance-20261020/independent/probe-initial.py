"""Independent frozen-scope fault oracles; only owned ephemeral synthetic PG."""
from copy import deepcopy
from uuid import UUID,uuid4
import hashlib,json
import pytest
from psycopg.types.json import Jsonb
from parkweave import controlled_plans as cp
from parkweave.store import Store
from parkweave.service_case_steps import recover as cold_recover
from test_plan_source_conflicts import edit
from test_preparation import headers
from test_service_case_steps import read as plan_read
from test_service_plan_manual_lock import stored
from service_release_acceptance_support import authority_snapshot
import test_employees_fact_provenance_independent as fp


def hashed(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()
def snapshot(t):return hashed(fp.full(t))
def authority(t):return hashed(authority_snapshot(t['f'][1]))
def write_plan(t,plan):
    with t['f'][1].connect() as c:c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),t['p']['preparation_id']))
def prepared_manual(t):
    edit(t['f'],t['p'],'  SYNTHETIC independent MANUAL\n preserve exact whitespace  ')
    c=fp.change_fact(t)
    old=fp.view(t,c)
    assert old['adoption'] is None and 'FACT_PROVENANCE_COMBINATION_UNSUPPORTED' in old['blocking_reasons']
    v=fp.manual_view(t,c)
    assert v['can_adopt'] and v['adoption']['fact_provenance_scope']==fp.MANUAL_SCOPE
    return c,v

def adopted(t):
    c,v=prepared_manual(t);key=uuid4().hex
    response=fp.send(t,v['adoption'],key)
    assert response.status_code==201
    plan=deepcopy(stored(t['f'],t['p']))
    assert plan['events'][-1]['local_revision']['source_change']['version']==5
    return c,v,key,plan

def rehash(event,t):
    patch=event['local_revision'];change=patch['source_change']
    if 'manual_provenance' in change:
        m=change['manual_provenance']
        m['note']['text_sha256']=fp.er.digest(m['note']['text']) if hasattr(fp,'er') else __import__('parkweave.store',fromlist=['digest']).digest(m['note']['text'])
        m['note_sha256']=cp._hash(m['note']);m['sha256']=cp._hash({k:v for k,v in m.items() if k!='sha256'})
    change['sha256']=cp._hash({k:v for k,v in change.items() if k!='sha256'})
    patch['request']['opportunity_proof']['expected_preview_sha256']=change['sha256']
    event['fingerprint']=cp._hash(dict(preparation_id=t['p']['preparation_id'],action='ADOPT',**patch['request']))


def test_later_edit_does_not_replace_old_v5_manual_in_cold_history(facts_case):
    t=facts_case;auth=authority(t);_,v,key,original=adopted(t)
    oldchange=deepcopy(original['events'][-1]['local_revision']['source_change'])
    assert fp.send(t,v['adoption'],key).status_code==201
    fp.repair_material(t)
    edit(t['f'],t['p'],'SYNTHETIC later independently edited MANUAL')
    assert next(iter(stored(t['f'],t['p'])['owner_amendments'].values()))['text']!=oldchange['manual_provenance']['note']['text']
    before=snapshot(t)
    recovered=cold_recover(Store(t['f'][0].dsn),t['f'][2]['fixture-a'],UUID(t['p']['preparation_id']),key)
    assert recovered['status']=='COMMITTED'
    current=stored(t['f'],t['p'])
    saved=next(e for e in current['events'] if e['request_key']==key)['local_revision']['source_change']
    assert hashed(saved)==hashed(oldchange)
    assert snapshot(t)==before and authority(t)==auth


@pytest.mark.parametrize('damage',['manual_text','latest_decision'])
def test_rehashed_manual_extension_cannot_replace_original_note_proof(facts_case,damage):
    t=facts_case;auth=authority(t);_,_,_,plan=adopted(t)
    event=plan['events'][-1];m=event['local_revision']['source_change']['manual_provenance']
    if damage=='manual_text':m['note']['text']='SYNTHETIC attacker replacement of historical M'
    else:m['latest_decision']['id']=str(uuid4())
    rehash(event,t);write_plan(t,plan)
    before=snapshot(t)
    response=plan_read(t['f'],t['p'])
    assert response.status_code in (403,409)
    assert snapshot(t)==before and authority(t)==auth


def test_saved_scope_version_and_extra_fields_do_not_cross_protocols(facts_case):
    t=facts_case;auth=authority(t);_,_,_,original=adopted(t)
    for shape in ('oldscope_v5','newscope_v3','extra_key','float_version'):
        plan=deepcopy(original);event=plan['events'][-1];patch=event['local_revision'];change=patch['source_change']
        if shape=='oldscope_v5':patch['request']['fact_provenance_scope']=fp.SCOPE
        elif shape=='newscope_v3':change['version']=3
        elif shape=='extra_key':change['unapproved_extension']={}
        else:change['version']=5.0
        rehash(event,t);write_plan(t,plan);before=snapshot(t)
        response=plan_read(t['f'],t['p'])
        assert response.status_code in (403,409),shape
        assert snapshot(t)==before and authority(t)==auth
        write_plan(t,original)
    # Refusal must be selective: the exact original V5 event remains readable.
    assert plan_read(t['f'],t['p']).status_code==200


def test_missing_original_fact_receipt_yields_unknown_without_adoption(facts_case):
    t=facts_case;auth=authority(t);card,v=prepared_manual(t)
    old_ref=v['fact_provenance']['before']['decision_ref']
    with t['f'][1].connect() as c:
        result=c.execute("DELETE FROM preparation_events WHERE preparation_id=%s AND payload->>'decision_ref'=%s",(t['p']['preparation_id'],old_ref))
        assert result.rowcount==1
    before=snapshot(t)
    result=t['f'][3].get(fp.endpoint(t),headers=headers(t['f'][2]),params=dict(card_id=card['id'],fact_provenance_scope=fp.MANUAL_SCOPE))
    assert result.status_code==200
    preview=result.json()
    assert preview['unknown_scope']=='THIS_CASE' and not preview['can_adopt'] and preview['preserved']==[]
    assert preview['adoption'] is None and preview['manual_provenance'] is None and preview['fact_provenance'] is None
    assert snapshot(t)==before and authority(t)==auth
