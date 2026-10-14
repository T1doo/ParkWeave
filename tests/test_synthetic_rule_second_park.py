"""Actual second park rule simulation: new source governance, facts and Case.

Only existing fixture-c authority is used. Mock candidate review permits are
explicit development configuration, never PostgreSQL grants or formal review.
"""
from copy import deepcopy
from datetime import datetime,timezone
from uuid import UUID,uuid4
import pytest
from parkweave import preparation as prep, synthetic_rule_readiness as sr
from parkweave.rule_publication_candidate import CandidateConfig,CandidatePermit,MockPrincipal,CandidateRepository,CandidateEngine,Scope,Command,Draft
from parkweave.store import Denied
from test_synthetic_rule_readiness import simulation,read as a_read,assess as a_assess,VALID
from test_preparation import preparation_fixture,create,command as prep_command,headers
from test_case_fact_clarifications_integration import post_fact,declare,authority
from test_v1_contracts import service

B_SCOPE=Scope(park_id='park-b',org_id='org-c',service_id=prep.SERVICE)

def b_rule_source(path):
    persons=[('fixture-c','enterprise_operator',['READ','SAVE','SUBMIT']),('rule-specialist-b','park_specialist',['READ','REVIEW']),('rule-publisher-b','resource_admin',['READ','PUBLISH','WITHDRAW'])]
    config=CandidateConfig(enabled_for_isolated_tests=True,principals=[MockPrincipal(id=actor,role=role) for actor,role,actions in persons],permits=[CandidatePermit(id='explicit-b-'+actor,principal_id=actor,scope=B_SCOPE,actions=actions,validity=VALID) for actor,role,actions in persons])
    return CandidateEngine(config,CandidateRepository(path/'b-source.candidate.sqlite3'))

def publish(e,version,expected):
    spec=service();spec.update(service_id=prep.SERVICE,owner_org_id='org-c',revision=str(version),publication='DRAFT',reviewer_id=None,validity=VALID,eligibility=dict(kind='EQ',field='employees',expected=expected))
    spec['handling_policy']['accepting_org_id']='org-c';spec['source_refs'][0].update(id='b-reviewed-source',revision=str(version))
    draft=Draft(spec=spec,sources=[dict(ref=spec['source_refs'][0],text='SYNTHETIC B explicitly reviewed employee comparison '+str(expected),validity=VALID)])
    for action,actor in [('SAVE','fixture-c'),('SUBMIT','fixture-c'),('REVIEW','rule-specialist-b'),('PUBLISH','rule-publisher-b')]:
        current=e.read(actor,B_SCOPE)
        e.command(actor,B_SCOPE,uuid4().hex,Command(action=action,expected_revision=current['revision'],expected_content_sha256=current['content_sha256'],reason='SYNTHETIC B explicit '+action,draft=draft if action=='SAVE' else None,publish_validity=VALID if action=='PUBLISH' else None))
    return e.read('fixture-c',B_SCOPE)['releases'][-1]

def a_history(f,p):
    with f[1].connect() as c:
        return dict(preparations=c.execute('SELECT * FROM preparations WHERE id=%s',(UUID(p['preparation_id']),)).fetchall(),events=c.execute('SELECT * FROM preparation_events WHERE preparation_id=%s ORDER BY revision,id',(UUID(p['preparation_id']),)).fetchall(),materials=c.execute('SELECT * FROM preparation_evidence WHERE preparation_id=%s ORDER BY id',(UUID(p['preparation_id']),)).fetchall(),case=c.execute('SELECT * FROM cases WHERE id=%s',(UUID(p['case_id']),)).fetchall(),facts=c.execute("SELECT * FROM fact_assertions WHERE principal_id='fixture-a' ORDER BY id").fetchall())

def test_second_park_b_new_authorized_rules_facts_true_false_unknown_a_untouched(simulation,tmp_path):
    f,a_parent,a_engine,a_consumer,a_context=simulation
    a_record,_=a_assess(simulation,'A-before-B');a_view=a_read(simulation);a_before=a_history(f,a_parent);authority_before=authority(f)
    b_parent,_,_=create(f,user='fixture-c',goal='SYNTHETIC NEW_B explicit service preparation')
    for slot,text in [('need_summary','SYNTHETIC B_REGION service need'),('material_outline','SYNTHETIC B new source materials')]:
        response=prep_command(f,b_parent,'ADD_EVIDENCE',user='fixture-c',slot=slot,text=text,source_kind='DOCUMENT_EXCERPT',source_label='SYNTHETIC B separately submitted document');assert response.status_code==200,response.text;b_parent=response.json()
    response=declare(f,b_parent,user='fixture-c');assert response.status_code==200,response.text;b_parent=response.json()
    selected={field:post_fact(f,field,value,'b-owned-'+field,user='fixture-c') for field,value in [('region','B_REGION'),('employees',23),('service_need','B_NEED')]}
    path='/api/preparations/'+b_parent['preparation_id']+'/fact-clarifications'
    current=f[3].get(path,headers=headers(f[2],'fixture-c')).json();by_id={x['id']:x for x in current['sources']}
    body=dict(expected_preparation_revision=current['preparation_revision'],expected_clarification_revision=current['revision'],expected_source_sha256=current['source_sha256'],choices=[dict(field=field,assertion_id=id,expected_assertion_revision=by_id[id]['revision'],expected_assertion_fingerprint=by_id[id]['fingerprint']) for field,id in selected.items()],reason='SYNTHETIC B owner explicitly selects its own new facts')
    response=f[3].post(path+'/confirm',headers=headers(f[2],'fixture-c',uuid4().hex),json=body);assert response.status_code==200,response.text;b_parent=response.json()
    e=b_rule_source(tmp_path);first=publish(e,1,23)
    binding=sr.RuleBinding(binding_id='second-park-b-rule',scope=B_SCOPE,release_id=first['id'],content_sha256=first['content_sha256'],region='B_REGION',epoch=1)
    consumer=sr.SyntheticRuleReadiness(f[0],f[1],e,sr.SimulationJournal(tmp_path/'b-results.synthetic-readiness.sqlite3'),bindings=[binding],enabled_for_isolated_tests=True)
    context=sr.Context(binding_id=binding.binding_id,as_of=datetime.now(timezone.utc).isoformat());id=UUID(b_parent['preparation_id'])
    def view():return consumer.read(f[2]['fixture-c'],id,context)
    def assess(key):
        v=view();data=sr.Assess(context=context,expected_preparation_revision=v['preparation_revision'],expected_source_sha256=v['source_sha256'],reason='SYNTHETIC B own explicit assessment '+key)
        return consumer.assess(f[2]['fixture-c'],id,key,data)
    true=assess('b-true');assert true['result']['synthetic_simulated_condition_truth']=='TRUE'
    assert true['sources']['binding']['scope']==B_SCOPE.model_dump() and true['sources']['binding']['region']=='B_REGION'
    assert {x['assertion_id'] for x in true['sources']['selected_facts']}==set(selected.values())
    assert all(x['confirmed_by']=='fixture-c' for x in true['sources']['facts']['sources'])
    second=publish(e,2,24);assert second['id']!=first['id']
    consumer.bindings=(binding.model_copy(update={'release_id':second['id'],'content_sha256':second['content_sha256'],'epoch':2}),)
    false=assess('b-false');assert false['result']['synthetic_simulated_condition_truth']=='FALSE'
    post_fact(f,'employees',24,'b-conflicting-authorized-evidence',user='fixture-c')
    unknown=assess('b-unknown');assert unknown['result']['synthetic_simulated_condition_truth']=='UNKNOWN'
    assert unknown['sources']['current_block']=='CONFLICTING_EVIDENCE'
    current=view();assert len(current['history'])==3 and [x['result']['synthetic_simulated_condition_truth'] for x in current['history']]==['TRUE','FALSE','UNKNOWN']
    assert current['history'][0]['current_truth']=='UNKNOWN' and current['history'][1]['current_truth']=='UNKNOWN'
    recovered=consumer.recover(f[2]['fixture-c'],id,'b-true',context);assert recovered['receipt']['id']==true['id'] and recovered['receipt']['result']==true['result'] and not recovered['automatically_replayed']
    assert b_parent['case_id']!=a_parent['case_id'] and b_parent['run_id']!=a_parent['run_id'] and b_parent['preparation_id']!=a_parent['preparation_id']
    assert first['id']!=a_consumer.bindings[0].release_id and second['draft']['sources'][0]['ref']['revision']=='2'
    for actor in ('fixture-a','fixture-b'):
        with pytest.raises(Denied):consumer.read(f[2][actor],id,context)
    with pytest.raises(Denied):a_consumer.read(f[2]['fixture-c'],UUID(a_parent['preparation_id']),a_context)
    assert a_history(f,a_parent)==a_before and a_read(simulation)==a_view
    assert authority(f)==authority_before
    for record in (true,false,unknown):
        assert record['governance']=='DEVELOPMENT_SIMULATION' and not record['formal_review'] and not record['business_publication']
        assert record['fact_authenticity']=='USER_ASSERTED_UNVERIFIED' and record['qualification_truth']=='UNKNOWN' and record['qualification_decision']=='NOT_EVALUATED'
