"""Actual original finite event capacity; no direct plan/event edits."""
from pathlib import Path
from copy import deepcopy
from uuid import uuid4
import json
import pytest
from test_template_upgrade import upgrade_case,publication,headers,plan_read,plan_command
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture
import template_migration_test_helpers as helper
from template_migration_test_helpers import private_fixture_sessions,stored,facts,admit,apply,ALL

@pytest.mark.parametrize('pre_revision',[58,62])
def test_original_capacity_should_allow_complete_upgrade_or_reject_before_adoption(upgrade_case,monkeypatch,pre_revision):
    u=upgrade_case
    # Original legal in-flight Case with real resource/ACCEPT/receipt/lifecycle
    # output, P1–P4 verified and P5 still awaiting owner's first VERIFY.
    real_verified=helper.verified
    with monkeypatch.context() as m:
        m.setattr(helper,'verified',lambda f,p,a:plan_read(f,p).json() if a=='P5' else real_verified(f,p,a))
        row,old_release,p=helper.full(u)
    current=plan_read(u['f'],p).json();assert current['revision']==6,current
    assert current['steps'][-1]['state']!='VERIFIED'
    for _ in range((pre_revision-current['revision'])//2):
        view=plan_read(u['f'],p).json();s=view['steps'][0]
        locked=plan_command(u['f'],p,'P1','LOCK',row=view,expected_source_sha256=s['source_sha256']);assert locked.status_code==200,locked.text
        unlocked=plan_command(u['f'],p,'P1','UNLOCK',row=locked.json());assert unlocked.status_code==200,unlocked.text
    before=deepcopy(stored(u,row));business=facts(u)
    assert before['revision']==pre_revision and not any(s.get('manual_lock') for s in before['steps'])
    target=publication(u,[__import__('test_template_upgrade').GOALS[-1]],source='2');view,data=admit(u,row,target)
    result=apply(u,row,data,'capacity-'+str(pre_revision))
    evidence=dict(pre_revision=pre_revision,initial_base_revision=6,actual_original_lock_unlock_commands=pre_revision-6,affected_count=len(view['application']['affected']),application_eligible=view['application']['eligible'],apply_http=result.status_code)
    if pre_revision==58:
        assert result.status_code==200,result.text
        for adapter in ALL:real_verified(u['f'],p,adapter)
        after=plan_read(u['f'],p).json();assert after['state']=='VERIFIED' and after['revision']==64,after
        evidence.update(final_state=after['state'],final_revision=after['revision'],status='PASS_EXACT_5_VERIFY_CAPACITY')
    elif result.status_code==200:
        first=plan_command(u['f'],p,'P1');assert first.status_code==200,first.text
        second=plan_command(u['f'],p,'P2');assert second.status_code in (409,422),second.text
        evidence.update(first_verify_http=first.status_code,revision_after_first_verify=first.json()['revision'],second_verify_http=second.status_code,second_verify_error=second.json(),status='PRODUCT_FAIL_ACCEPTED_UNFINISHABLE_MIGRATION')
    else:
        assert result.status_code==409,result.text
        assert stored(u,row)==before
        evidence.update(status='PASS_REJECTED_BEFORE_ADOPTION')
    assert facts(u)==business
    out=Path('.runtime/template-migration-review-20261014');(out/('capacity-'+str(pre_revision)+'-actual.json')).write_text(json.dumps(evidence,indent=2)+'\n')
    assert pre_revision==58 or result.status_code==409,evidence
