import pytest
from pydantic import ValidationError
from parkweave.domain import ServicePlan


def plan():
    return {'schema_version':'parkweave-domain/0.1','required_goals':['g1'],
            'goal_coverage':{'g1':['s1']},'steps':[{'step_id':'s1','service_ref':'intake','revision':'1',
             'action':{},'depends_on':[],'responsible_role':'enterprise_operator','delivery':'LOCAL_CASE_RECORD'}]}


@pytest.mark.parametrize('change',[
    {'required_goals':['g1','g1']},
    {'required_goals':[' '],'goal_coverage':{' ':['s1']}},
    {'goal_coverage':{'g1':['s1','s1']}},
    {'goal_coverage':{'g1':['s1']*17}},
    {'required_goals':['x'*2001],'goal_coverage':{'x'*2001:['s1']}},
])
def test_plan_rejects_ambiguous_or_unbounded_goal_coverage(change):
    with pytest.raises(ValidationError):ServicePlan.model_validate(plan()|change)


def test_duplicate_dependency_and_non_identifier_ref_rejected():
    p=plan()
    second=dict(p['steps'][0],step_id='s2',depends_on=['s1','s1'])
    with pytest.raises(ValidationError):ServicePlan.model_validate(p|{'steps':p['steps']+[second]})
    bad=dict(p['steps'][0],service_ref='../../Windows/system.ini')
    with pytest.raises(ValidationError):ServicePlan.model_validate(p|{'steps':[bad]})
    good=dict(second,depends_on=['s1'])
    assert ServicePlan.model_validate(p|{'steps':p['steps']+[good]})
