"""Independent original workflow anchors and authorized-unverified fact oracles."""
import json
from uuid import UUID,uuid4
import pytest
from parkweave.rule_publication_candidate import sha
from parkweave.store import Conflict
from test_synthetic_rule_readiness import simulation,read,assess,preparation_fixture
from test_case_fact_clarifications_integration import post_fact,confirm_body,fact_read,business,authority
from test_preparation import headers


def test_review_release_and_currentrow_rehashed_together_cannot_change_reviewed_rule(simulation):
    f,p,e,a,context=simulation
    with e.repository.connect(write=True) as c:
        row=c.execute('SELECT * FROM candidate_rules').fetchone();draft=json.loads(row['draft'])
        draft['spec']['eligibility']['expected']=999;changed=sha(draft)
        c.execute('UPDATE candidate_rules SET draft=?,content_sha=?',(json.dumps(draft),changed))
        row=c.execute('SELECT * FROM candidate_releases').fetchone();release=json.loads(row['payload'])
        release['draft']=draft;release['content_sha256']=changed
        c.execute('UPDATE candidate_releases SET payload=?',(json.dumps(release),))
    # Rebind the trusted configuration too: original immutable review remains
    # the independent authority and must reject this content substitution.
    a.bindings=(a.bindings[0].model_copy(update={'content_sha256':changed,'epoch':2}),)
    before=business(f);old=authority(f)
    with pytest.raises(Conflict):read(simulation)
    assert business(f)==before and authority(f)==old
    with a.journal.connect() as c:assert c.execute('SELECT count(*) FROM simulation_assessments').fetchone()[0]==0


def test_review_selected_region_cannot_hide_other_current_conflict(simulation):
    f,p,e,a,context=simulation;original,data=assess(simulation,'review-original')
    post_fact(f,'region','REGION_B','independent-region-conflict')
    v=fact_read(f,p).json();selected={x['field_name']:x['id'] for x in v['sources'] if x['value'] in ('REGION_A',17,'NEED_A')}
    response=f[3].post('/api/preparations/'+p['preparation_id']+'/fact-clarifications/confirm',headers=headers(f[2],key=uuid4().hex),json=confirm_body(f,p,selected))
    assert response.status_code==200,response.text
    before=business(f);journal=a.journal.path.read_bytes();current=read(simulation)
    assert current['sources']['purpose_status']['state']=='CURRENT'
    assert current['result']['synthetic_simulated_condition_truth']=='UNKNOWN'
    assert current['sources']['current_block']=='CONFLICTING_EVIDENCE'
    recovered=a.recover(f[2]['fixture-a'],UUID(p['preparation_id']),'review-original',context)
    assert recovered['status']=='COMMITTED' and recovered['receipt']['result']==original['result']
    assert recovered['receipt']['current_truth']=='UNKNOWN'
    assert recovered['receipt']['result']['fact_authenticity']=='USER_ASSERTED_UNVERIFIED'
    assert recovered['qualification_truth']=='UNKNOWN' and recovered['qualification_decision']=='NOT_EVALUATED'
    assert a.journal.path.read_bytes()==journal and business(f)==before


def test_review_unavailable_current_release_preserves_saved_readonly_receipt(simulation):
    f,p,e,a,context=simulation;original,_=assess(simulation,'saved-before-unavailable')
    with e.repository.connect(write=True) as c:c.execute('DELETE FROM candidate_releases')
    before=business(f);journal=a.journal.path.read_bytes()
    recovered=a.recover(f[2]['fixture-a'],UUID(p['preparation_id']),'saved-before-unavailable',context)
    assert recovered['status']=='COMMITTED'
    assert recovered['receipt']['receipt_sha256']==original['receipt_sha256']
    assert recovered['receipt']['current_truth']=='UNKNOWN'
    assert recovered['receipt']['result']['synthetic_simulated_condition_truth']=='TRUE'
    assert a.journal.path.read_bytes()==journal and business(f)==before
