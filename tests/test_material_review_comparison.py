"""Ordinary assigned specialist reads exact existing REVIEW/material provenance."""
import hashlib,json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from parkweave import material_review_comparison as comparison
from parkweave import preparation as prep
from test_preparation import preparation_fixture,create,add,command,read,headers
from test_material_corrections import fresh,checked,request,authority
from test_native_preparation_entry import ordinary,snapshot

REVIEWER='prep-specialist-fixture-a'


def old_review(f):
    p=fresh(f,label='SPECIALIST_COMPARE')
    old=checked(read(f,p));p=checked(command(f,p,'REVIEW',REVIEWER,reason='SYNTHETIC original complete pack review'))
    p=checked(command(f,p,'CONFIRM',reason='SYNTHETIC original enterprise confirmation'))
    return p,old


def correction_pending(f):
    p,old=old_review(f);p=checked(command(f,p,'REOPEN',reason='SYNTHETIC needs material changes'))
    p=checked(add(f,p,'material_outline',text='SYNTHETIC unreviewed v2 outline'))
    p=checked(request(f,p,['material_outline'],reason='SYNTHETIC correct current v2 outline'))
    return p,old


def get(api,f,p,actor=REVIEWER):
    return api.get('/api/preparations/'+p['preparation_id']+'/material-review-comparison',headers=headers(f[2],actor))


def test_ordinary_factory_exact_last_review_v1_not_request_v2_matches_current_v3_and_restarts(preparation_fixture,monkeypatch):
    f=preparation_fixture;p,old=correction_pending(f);p=checked(add(f,p,'material_outline',text='SYNTHETIC corrected v3 outline'));auth=authority(f);before=snapshot(f[1]);results=[]
    for _ in range(2):
        with TestClient(ordinary(f,monkeypatch)) as api:results.append(checked(get(api,f,p)))
    x=results[0];assert results[0]==results[1] and snapshot(f[1])==before and authority(f)==auth
    assert x['baseline_state']=='MATCHED' and x['reviewer_id']==REVIEWER and x['read_only'] and not x['review_performed'] and not x['facts_adopted'] and x['correction_sufficiency']=='NOT_EVALUATED'
    baseline=[r['baseline'] for r in x['slots']];assert sorted(baseline,key=lambda m:m['slot'])==[{k:str(v) if k=='id' else v for k,v in m.items()} for m in old['current_materials']]
    outline=next(r for r in x['slots'] if r['slot']=='material_outline');assert outline['baseline']['version']==1 and outline['current']['version']==3
    assert x['review_event']['snapshot_sha256']==old['snapshot_sha256'] and x['current_snapshot_sha256']==checked(read(f,p))['snapshot_sha256']
    projection={k:v for k,v in x.items() if k!='comparison_sha256'};assert hashlib.sha256(json.dumps(projection,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()==x['comparison_sha256']
    assert not {'authority_sha256','catalog_epoch_sha256','delivery_review_source','fact_clarification','request_intent'}&set(x)


@pytest.mark.parametrize('slots',[0,1,2])
def test_no_previous_review_never_invents_old_materials(preparation_fixture,slots):
    f=preparation_fixture;p,_,_=create(f)
    for slot in prep.SLOTS[:slots]:p=checked(add(f,p,slot))
    before=snapshot(f[1]);x=checked(get(f[3],f,p));assert x['baseline_state']=='NO_PREVIOUS_REVIEW' and x['review_event'] is None and all(r['baseline'] is None for r in x['slots']) and sum(r['current'] is not None for r in x['slots'])==slots and snapshot(f[1])==before


@pytest.mark.parametrize('after_new_review',[False,True])
def test_latest_review_is_selected_and_current_review_is_only_historical_read(preparation_fixture,after_new_review):
    f=preparation_fixture;p,old=correction_pending(f);p=checked(add(f,p,'material_outline',text='SYNTHETIC second reviewed pack'))
    if after_new_review:p=checked(command(f,p,'REVIEW',REVIEWER,reason='SYNTHETIC second actual review'))
    x=checked(get(f[3],f,p));outline=next(r for r in x['slots'] if r['slot']=='material_outline');assert outline['baseline']['version']==(3 if after_new_review else 1) and outline['current']['version']==3
    assert x['review_event']['revision']==(p['revision'] if after_new_review else 4)
    assert not x['review_performed'] and x['case_goal_completed'] is False


@pytest.mark.parametrize('damage',['hash','actor','case','revision','material_label'])
def test_bad_latest_review_never_falls_back_to_an_earlier_good_review(preparation_fixture,damage):
    f=preparation_fixture;p,old=correction_pending(f);p=checked(add(f,p,'material_outline',text='SYNTHETIC v3 for latest review'));p=checked(command(f,p,'REVIEW',REVIEWER,reason='SYNTHETIC latest actual review'));p=checked(command(f,p,'REOPEN',reason='SYNTHETIC keep last review historical'));p=checked(add(f,p,'material_outline',text='SYNTHETIC v4 current'))
    with f[1].connect() as c:
        if damage=='material_label':c.execute("UPDATE preparation_evidence SET source_label='SYNTHETIC damaged v3 source' WHERE preparation_id=%s AND slot='material_outline' AND version=3",(p['preparation_id'],))
        else:
            row=c.execute("SELECT id,payload FROM preparation_events WHERE preparation_id=%s AND action='REVIEW' ORDER BY revision DESC LIMIT 1",(p['preparation_id'],)).fetchone();payload=dict(row['payload']);payload[{'hash':'snapshot_sha256','actor':'actor_id','case':'case_id','revision':'revision'}[damage]]={'hash':'f'*64,'actor':'SYNTHETIC wrong historical actor','case':str(uuid4()),'revision':999}[damage]
            from psycopg.types.json import Jsonb
            c.execute('UPDATE preparation_events SET payload=%s WHERE id=%s',(Jsonb(payload),row['id']))
    before=snapshot(f[1]);x=checked(get(f[3],f,p));assert x['baseline_state']=='UNVERIFIED' and all(r['baseline'] is None for r in x['slots']) and next(r for r in x['slots'] if r['slot']=='material_outline')['current']['version']==4 and snapshot(f[1])==before


@pytest.mark.parametrize('change',['same','source','CRLF'])
def test_old_UUID_version_and_body_bytes_disambiguate_identical_text_versions(preparation_fixture,change):
    f=preparation_fixture;p,old=old_review(f);p=checked(command(f,p,'REOPEN',reason='SYNTHETIC explicit new material'));m=next(m for m in old['current_materials'] if m['slot']=='material_outline');text='SYNTHETIC A\r\nB\rC\n字面\\r😀' if change=='CRLF' else m['text'];label='SYNTHETIC new metadata' if change=='source' else m['source_label']
    p=checked(command(f,p,'ADD_EVIDENCE',slot=m['slot'],text=text,source_kind=m['source_kind'],source_label=label));x=checked(get(f[3],f,p));r=next(r for r in x['slots'] if r['slot']==m['slot'])
    assert x['baseline_state']=='MATCHED' and r['baseline']['id']==m['id'] and r['baseline']['version']==1 and r['current']['id']!=m['id'] and r['current']['version']==2 and r['current']['text']==text
    assert r['current']['source_sha256']==hashlib.sha256(text.encode()).hexdigest() and r['current']['source_label']==label


@pytest.mark.parametrize('actor',['fixture-a','fixture-b','fixture-c','prep-specialist-fixture-b','prep-specialist-fixture-c'])
def test_owner_or_other_scope_is_not_current_assigned_specialist(preparation_fixture,actor):
    f=preparation_fixture;p,old=old_review(f);before=snapshot(f[1]);r=get(f[3],f,p,actor);assert r.status_code==403 and r.json()['detail']=='record unavailable or authorization denied' and snapshot(f[1])==before


@pytest.mark.parametrize('damage',['READ','REVIEW_ASSIGNED','inactive','reassigned','catalog'])
def test_current_original_entry_revocation_reassignment_and_source_stay_refused(preparation_fixture,damage):
    f=preparation_fixture;p,old=old_review(f)
    with f[1].connect() as c:
        if damage=='READ':c.execute("UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability='READ'",(REVIEWER,))
        elif damage=='REVIEW_ASSIGNED':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id=%s AND capability='REVIEW_ASSIGNED'",(REVIEWER,))
        elif damage=='inactive':c.execute('UPDATE principals SET active=false WHERE id=%s',(REVIEWER,))
        elif damage=='reassigned':c.execute("UPDATE preparations SET reviewer_id='prep-specialist-fixture-b' WHERE id=%s",(p['preparation_id'],))
        else:c.execute("UPDATE preparation_catalog SET source='{}'::jsonb WHERE park_id='park-a'")
    before=snapshot(f[1]);r=get(f[3],f,p);assert r.status_code==(409 if damage=='catalog' else 403) and snapshot(f[1])==before


def test_no_caller_selected_baseline_and_no_current_material_digest_forgery(preparation_fixture):
    f=preparation_fixture;p,old=old_review(f);before=snapshot(f[1]);r=f[3].get('/api/preparations/'+p['preparation_id']+'/material-review-comparison?baseline=1',headers=headers(f[2],REVIEWER));assert r.status_code==422 and snapshot(f[1])==before
    with f[1].connect() as c:c.execute("UPDATE preparation_evidence SET source_sha256=%s WHERE preparation_id=%s AND slot='material_outline'",('f'*64,p['preparation_id']))
    before=snapshot(f[1]);assert get(f[3],f,p).status_code==409 and snapshot(f[1])==before


def test_restore_bounds_and_ambiguity_refuse_without_selecting_a_candidate():
    parent={'id':uuid4(),'case_id':uuid4(),'run_id':uuid4(),'revision':9,'service_id':prep.SERVICE,'service_version':1};items=[{'id':uuid4(),'slot':slot,'version':1,'text':'SYNTHETIC '+slot,'source_kind':'USER_STATEMENT','source_label':'SYNTHETIC','source_sha256':prep.digest('SYNTHETIC '+slot),'authenticity':'UNVERIFIED'} for slot in sorted(prep.SLOTS)]
    payload={'preparation_id':str(parent['id']),'case_id':str(parent['case_id']),'run_id':str(parent['run_id']),'revision':4,'actor_id':REVIEWER,'action':'REVIEW','state':'REVIEWED','scope':'SYNTHETIC_LOCAL_PREPARATION_ONLY','snapshot_sha256':prep.snapshot(parent,items)};review={'revision':4,'actor_id':REVIEWER,'payload':payload}
    assert comparison.restore(parent,items,review)[0]=='MATCHED'
    assert comparison.restore(parent,items+[items[0]],review)==('UNVERIFIED',None)
    assert comparison.restore(parent,items*33,review)==('UNVERIFIED',None)
    assert comparison.restore(dict(parent,service_version=2),items,review)==('UNVERIFIED',None)


def same_value_reader_ABA(f,p,kind):
    """Isolated synthetic fault injection; no production authority is created."""
    with f[1].connect() as c:
        if kind=='READ':
            for active in (False,True):c.execute("UPDATE capability_grants SET active=%s WHERE principal_id=%s AND capability='READ'",(active,REVIEWER))
        elif kind=='REVIEW_ASSIGNED':
            for active in (False,True):c.execute("UPDATE preparation_grants SET active=%s WHERE principal_id=%s AND capability='REVIEW_ASSIGNED'",(active,REVIEWER))
        elif kind=='assignment':
            for actor in ('prep-specialist-fixture-b',REVIEWER):c.execute('UPDATE preparations SET reviewer_id=%s WHERE id=%s',(actor,p['preparation_id']))
        else:c.execute("UPDATE preparation_catalog SET source=source WHERE park_id='park-a'")


@pytest.mark.parametrize('kind',['READ','REVIEW_ASSIGNED','assignment','catalog'])
def test_same_value_reader_ABA_changes_opaque_source_without_changing_material_or_authority_values(preparation_fixture,kind):
    f=preparation_fixture;p,old=old_review(f);before=checked(get(f[3],f,p));auth=authority(f)
    same_value_reader_ABA(f,p,kind);after_fault=snapshot(f[1]);after=checked(get(f[3],f,p))
    assert before['reader_source_sha256']!=after['reader_source_sha256'] and before['comparison_sha256']!=after['comparison_sha256']
    assert {k:v for k,v in before.items() if k not in ('reader_source_sha256','comparison_sha256')}=={k:v for k,v in after.items() if k not in ('reader_source_sha256','comparison_sha256')}
    assert authority(f)==auth and snapshot(f[1])==after_fault
