"""Original scoped readiness explained as a read-only synthetic review candidate."""
import pytest
from test_preparation import preparation_fixture, create, filled, add, command
from test_readiness import read, rows, assess
from test_material_preparation_drafts import draft_fixture


def checklist(f,p,user='fixture-a'):
    r=read(f,p,user); assert r.status_code==200,r.text
    return r.json()['material_checklist']


def test_missing_and_actual_evidence_read_only_without_policy_invention(preparation_fixture):
    f=preparation_fixture;p,_,_=create(f);before=rows(f)
    x=checklist(f,p);assert rows(f)==before
    assert [r['status'] for r in x['requirements']]==['MISSING','MISSING']
    assert all(r['evidence'] is None and r['truth']=='UNKNOWN' for r in x['requirements'])
    assert x['policy_requirements']==dict(status='NOT_PROVIDED',truth='UNKNOWN',reason='REVIEWED_REAL_POLICY_SOURCE_REQUIRED',requirements_generated=False)
    p=add(f,p,text='PRIVATE actual owner excerpt').json();before=rows(f);x=checklist(f,p)
    assert rows(f)==before and x['preparation_revision']==p['revision']
    r=x['requirements'][0];assert r['status']=='PROVIDED_UNVERIFIED' and r['evidence']['text']=='PRIVATE actual owner excerpt'
    assert r['evidence']['version']==1 and r['evidence']['authenticity']=='UNVERIFIED'
    assert x['conditions'][0]['evidence'][0]['evidence']==r['evidence']
    assert x['qualification_decision']=='NOT_EVALUATED' and not x['case_goal_completed'] and not x['business_publication']


def test_targeted_correction_wait_review_and_replacement_are_distinct(preparation_fixture):
    f=preparation_fixture;p=filled(f)
    p=command(f,p,'REQUEST_CHANGES','prep-specialist-fixture-a',reason='Synthetic actual directory gap',correction_slots=['material_outline']).json()
    x=checklist(f,p);a,b=x['requirements'];assert a['status']=='PROVIDED_UNVERIFIED' and a['truth']=='UNKNOWN'
    assert b['status']=='CORRECTION_REQUIRED' and b['correction_requests'][0]['reason']=='Synthetic actual directory gap'
    assert b['correction_requests'][0]['base_version']==1
    p=add(f,p,'material_outline','Synthetic corrected actual text').json();x=checklist(f,p)
    assert x['requirements'][1]['status']=='AWAITING_REVIEW' and x['requirements'][1]['evidence']['version']==2
    p=command(f,p,'REVIEW','prep-specialist-fixture-a',reason='Synthetic reviewed exact current pack').json();x=checklist(f,p)
    assert all(r['status']=='CURRENT_PACK_REVIEWED' for r in x['requirements'])
    assert x['conditions'][1]['manual_decision']['reason']=='Synthetic reviewed exact current pack'
    assess(f,p);p=add(f,p,'material_outline','Synthetic later content').json();v=read(f,p).json()
    assert v['state']=='STALE' and v['current_truth']=='UNKNOWN'
    assert all(r['status']=='PROVIDED_UNVERIFIED' for r in v['material_checklist']['requirements'])
    assert v['material_checklist']['conditions'][1]['truth']=='UNKNOWN'
    assert v['material_checklist']['requirements'][1]['evidence']['version']==3


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-b'])
def test_other_identity_cannot_read_checklist_or_private_body(preparation_fixture,user):
    f=preparation_fixture;p=filled(f);before=rows(f);r=read(f,p,user)
    assert r.status_code==403 and 'SYNTHETIC material list' not in r.text and rows(f)==before


def test_current_reviewer_revocation_does_not_reuse_historical_true(preparation_fixture):
    f=preparation_fixture;p=filled(f);p=command(f,p,'REVIEW','prep-specialist-fixture-a',reason='Synthetic check').json()
    assert checklist(f,p)['conditions'][1]['truth']=='TRUE'
    with f[1].connect() as c:c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='prep-specialist-fixture-a'")
    x=checklist(f,p);assert x['conditions'][1]['truth']=='UNKNOWN'
    assert all(r['status']=='PROVIDED_UNVERIFIED' for r in x['requirements'])
    assert read(f,p,'prep-specialist-fixture-a').status_code==403


def test_service_source_missing_blocks_candidate_without_erasing_evidence(preparation_fixture):
    f=preparation_fixture;p=filled(f)
    with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{kind}','\"UNVERIFIED\"') WHERE park_id='park-a'")
    x=checklist(f,p);assert not x['source_available']
    assert all(r['evidence'] and r['truth']=='UNKNOWN' for r in x['requirements'])
    assert x['policy_requirements']['truth']=='UNKNOWN'


def test_fact_source_change_does_not_upgrade_old_shared_brief_or_leak_private_sources(draft_fixture):
    from test_material_preparation_drafts import preview, save, body
    from test_case_fact_clarifications_integration import post_fact, current_parent
    f,p,_=draft_fixture;x=preview(f,p).json();assert save(f,p,body(x)).status_code==201
    p=current_parent(f,p);before=rows(f);x=checklist(f,p,'prep-specialist-fixture-a')
    assert rows(f)==before
    fact=next(c for c in x['conditions'] if c['id']=='current_fact_purpose_confirmation')
    assert fact['truth']=='TRUE' and fact['fact_basis']['satisfied']
    assert 'PRIVATE_CONFLICTING_REGION' not in str(x) and 'PRIVATE_FACT_EXCERPT_' not in str(x)
    post_fact(f,'service_need','Synthetic new intended need','checklist-new-need')
    x=checklist(f,p,'prep-specialist-fixture-a');fact=next(c for c in x['conditions'] if c['id']=='current_fact_purpose_confirmation')
    assert fact['truth']=='UNKNOWN' and not fact['fact_basis']['satisfied']
    assert fact['reason']=='CURRENT_GENERATED_MATERIAL_SOURCE_REQUIRED'
    assert x['policy_requirements']['truth']=='UNKNOWN'
