"""Independent browser view oracle, with an actual conflict-card screenshot."""
from pathlib import Path
from test_service_plan_manual_lock import (link_fixture,receipt_fixture,preparation_fixture,start,
    lock,save,GOALS,snapshot,read)
from test_service_plan_recovery_browser import goal_page,open_case
OUT=Path('.runtime/independent-service-plan-manual-lock-review/browser-extra')

def test_owner_conflict_actual_card_visible_and_goal_consumer_not_broken(goal_page):
    f,page,errors=goal_page;p=start(f,GOALS[1]);assert lock(f,p).status_code==200
    assert save(f,p,goals=[GOALS[0]],text='SYNTHETIC independent changed request').status_code==200
    read(f,p)  # original observation before GET-only browser assertion
    before=snapshot(f);open_case(page,f,p)
    assert page.evaluate('servicePlanView.steps[0].state')=='LOCK_CONFLICT'
    card=page.locator('#service-plan-steps');card.scroll_into_view_if_needed()
    OUT.mkdir(parents=True,exist_ok=True)
    for width in (390,320):
        page.set_viewport_size({'width':width,'height':1000});card.scroll_into_view_if_needed()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(OUT/('independent-conflict-card-'+str(width)+'.png')),full_page=True)
    assert card.locator('[data-service-action="UNLOCK"]').count()==1
    assert card.locator('[data-service-action="VERIFY"]').count()==0
    assert snapshot(f)==before and not errors
