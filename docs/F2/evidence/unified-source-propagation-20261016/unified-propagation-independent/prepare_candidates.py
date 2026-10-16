from pathlib import Path
r=Path('/workspace/ParkWeave'); dest=r/'.runtime/unified-propagation-independent/candidate/tests'
s=(r/'tests/test_employees_fact_provenance_independent.py').read_text()
# Keep the independently exercised original fixtures and helpers, without any old test bodies.
start=s.index('def test_exact_historical_selection_read_without_card_is_pure')
end=s.index('def html_controls(')
end2=s.index("@pytest.mark.parametrize('mode',['positive'")
s=s[:start]+s[end:end2]+"\n@pytest.mark.parametrize('mode',['positive','lost_ack','current_403','late_403'])\ndef test_full_original_html_unified_adoption_and_authority(facts_case,mode):run_html(facts_case,mode)\n"
s=s.replace("OUT=ROOT/'.runtime/fact-provenance-independent/artifacts'","OUT=ROOT/'.runtime/unified-propagation-independent/artifacts'")
s=s.replace("SCOPE='EMPLOYEES_USER_ASSERTION_V1'","SCOPE='BOUNDED_MULTI_SOURCE_V1'")
a=s.index('ORACLE=json.loads(');b=s.index('\n\n\ndef record',a)
s=s[:a]+"ORACLE=json.loads((ROOT/'.runtime/unified-propagation-oracle/literal-oracle.json').read_text())\nANSWERS={r['id']:r for r in ORACLE['rows']}"+s[b:]
s=s.replace("def endpoint(t):return '/api/preparations/'+t['p']['preparation_id']+'/employees-fact-impact'","def endpoint(t,card):return '/api/preparations/'+t['p']['preparation_id']+'/opportunities/'+card['id']+'/plan-revision'")
s=s.replace("get(endpoint(t),headers=headers(t['f'][2],user),params={'card_id':card['id']} if card else {})","get(endpoint(t,card),headers=headers(t['f'][2],user),params={'dependency_scope':SCOPE})")
s=s.replace('EMPLOYEES_FACT_PROVENANCE_PREVIEW','BOUNDED_MULTI_SOURCE_REVISION_PREVIEW').replace('fact_provenance_scope','dependency_scope')
s=s.replace("proof['version']==3 and proof['fact_provenance']","proof['version']==4 and proof['dependency_propagation']['schema']==2").replace('proof_version=3','proof_version=4')
s=s.replace("change['version']==3 and change['fact_provenance']['scope']==SCOPE","change['version']==4 and change['dependency_propagation']['scope']==SCOPE")
a=s.index('def assert_exact_projection(');b=s.index('def html_controls(',a);s=s[:a]+s[b:]
s=s.replace("change_fact=lambda:change_fact(t,refresh=False)","change_fact=lambda:mixed_change(t,refresh=False)")
s=s.replace("employees_fact_provenance_real_html.js","unified_dependency_propagation_real_html.js").replace('FULL_ORIGINAL_HTML_EMPLOYEES_PROVENANCE_ACTUAL_HTTP_ASGI_OWNED_PG','FULL_ORIGINAL_HTML_UNIFIED_PROPAGATION_ACTUAL_HTTP_ASGI_OWNED_PG')
# Add independent API scenarios; expected partitions are literal oracle rows.
s+='''

def change_receipt(t):
    id=t['completed']['A']['dispatch']['receipt_step_id']
    q=t['f'][3].get('/api/executor-receipts/'+id,headers=headers(t['f'][2])).json()
    r=receipt_act(t['f'],q,'REOPEN');assert r.status_code==200,r.text
    chain.report_and_ack(t['u'],t['p'],dict(receipt_step_id=id))


def mixed_change(t,refresh=True):
    change_fact(t,refresh=False)
    from test_preparation import add,command
    p=dict(prep_read(t['f'],t['p']).json()['preparation'],preparation_id=t['p']['preparation_id'])
    # Original confirmation already leaves preparation requiring material review.
    if p['state'] in ('REVIEWED','LOCAL_CONFIRMED'):
        r=command(t['f'],p,'REOPEN',reason='SYNTHETIC mixed source reopening');assert r.status_code==200,r.text;p=r.json()
    r=add(t['f'],p,slot='need_summary',text='SYNTHETIC independently changed source context');assert r.status_code==200,r.text
    add_resource(t['f']);change_receipt(t)
    return card(t) if refresh else None


def test_actual_mixed_material_fact_resource_receipt_explicit_adopt_verify(facts_case):
    t=facts_case;c=mixed_change(t);v=view(t,c);partition(t,v,'UP09')
    q=v['dependency_propagation'];assert q['schema']==2 and q['scope']==SCOPE
    assert v['source_impact']['schema']==1
    assert {n['type'] for n in q['nodes']} >= {'MATERIAL','FACT','RESOURCE','RECEIPT'}
    accepted(t,c);repair_material(t)


def test_receipt_change_retains_three_original_locked_steps(facts_case):
    t=facts_case
    for a in ('P1','P2','P3'):assert lock(t['f'],t['p'],a).status_code==200
    old=deepcopy(stored(t['f'],t['p']));change_receipt(t);c=card(t)
    partition(t,view(t,c),'UP25');accepted(t,c);repair_tail(t,('P4','P5'));final(t)
    assert stored(t['f'],t['p'])['steps'][:3]==old['steps'][:3]


def test_resource_change_affected_manual_lock_needs_original_unlock(facts_case):
    t=facts_case;assert lock(t['f'],t['p'],'P1').status_code==200;assert lock(t['f'],t['p'],'P3').status_code==200
    old=deepcopy(stored(t['f'],t['p']));add_resource(t['f']);c=card(t);v=view(t,c)
    partition(t,v,'UP26');assert not v['can_adopt'] and 'AFFECTED_LOCK_REQUIRES_EXPLICIT_UNLOCK' in v['blocking_reasons']
    assert plan_command(t['f'],t['p'],'P3','UNLOCK').status_code==200
    accepted(t,c);repair_tail(t,('P2','P3','P4','P5'));final(t)
    assert stored(t['f'],t['p'])['steps'][0]==old['steps'][0]


def test_same_key_altered_scope_and_actual_original_cold_get(facts_case):
    t=facts_case;c=mixed_change(t);b,key,r=accepted(t,c);before=full(t)
    q=recover(t['f'],t['p'],key);assert q.status_code==200 and q.json()['status']=='COMMITTED' and full(t)==before
    assert send(t,b,key).status_code==201 and full(t)==before
    assert send(t,{k:v for k,v in b.items() if k!='dependency_scope'},key).status_code==409 and full(t)==before
    repair_material(t)


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a'])
def test_original_owner_tenant_role_scope_refuses_graph_and_adopt(facts_case,user):
    t=facts_case;c=mixed_change(t);b=view(t,c)['adoption'];before=full(t)
    r=impact(t,c,user);assert r.status_code==403 and 'dependency_propagation' not in r.text
    assert send(t,b,user=user).status_code==403 and full(t)==before


def test_resource_row_a_b_a_refuses_preview_after_values_restore(facts_case):
    t=facts_case;add_resource(t['f']);c=card(t);b=view(t,c)['adoption']
    with t['f'][1].connect() as db:r=db.execute('SELECT id,capacity FROM synthetic_resources ORDER BY id LIMIT 1').fetchone()
    with t['f'][1].connect() as db:db.execute('UPDATE synthetic_resources SET capacity=capacity+1 WHERE id=%s',(r['id'],))
    with t['f'][1].connect() as db:db.execute('UPDATE synthetic_resources SET capacity=%s WHERE id=%s',(r['capacity'],r['id']))
    before=full(t);assert send(t,b).status_code==409 and full(t)==before


def test_unconfirmed_fact_selection_unknown_never_authorizes(facts_case):
    t=facts_case;post_fact(t['f'],'employees',99,'SYNTHETIC competing unselected fact')
    c=card(t);v=view(t,c);partition(t,v,'UP24')
    assert not v['can_adopt'] and v['adoption'] is None


def test_new_v4_then_original_default_v2_is_nonsticky(facts_case):
    from test_source_change_adoption import preview as original_preview
    t=facts_case;c=mixed_change(t);accepted(t,c);repair_material(t)
    old=deepcopy(stored(t['f'],t['p']));add_resource(t['f']);c=card(t);v=original_preview(t['f'],t['p'],c).json()
    assert v['scope']=='SOURCE_CHANGE_LOCAL_REVISION_PREVIEW' and 'dependency_scope' not in v['adoption']
    key=uuid4().hex;r=send(t,v['adoption'],key);assert r.status_code==201,r.text
    now=stored(t['f'],t['p']);change=now['events'][-1]['local_revision']['source_change']
    assert change['version']==2 and 'dependency_propagation' not in change and now['events'][:len(old['events'])]==old['events']
    assert recover(t['f'],t['p'],key).json()['status']=='COMMITTED'
    repair_tail(t,('P2','P3','P4','P5'));final(t)
'''
(dest/'test_unified_dependency_propagation_independent.py').write_text(s)
j=(r/'tests/employees_fact_provenance_real_html.js').read_text()
j=j.replace("path.includes('/employees-fact-impact')","path.includes('dependency_scope=BOUNDED_MULTI_SOURCE_V1')").replace("c.path.includes('/employees-fact-impact')","c.path.includes('dependency_scope=BOUNDED_MULTI_SOURCE_V1')")
j=j.replace('data-opp-fact-preview','data-opp-dependency-preview').replace('oppFactPreview','oppDependencyPreview').replace('fact_provenance','dependency_propagation').replace('EMPLOYEES_FACT_PROVENANCE_PREVIEW','BOUNDED_MULTI_SOURCE_REVISION_PREVIEW').replace('FULL_ORIGINAL_HTML_EMPLOYEES_PROVENANCE_ACTUAL_HTTP_ASGI_OWNED_PG','FULL_ORIGINAL_HTML_UNIFIED_PROPAGATION_ACTUAL_HTTP_ASGI_OWNED_PG')
j=j.replace("check(run('opportunityPlanView.dependency_propagation.authenticity')==='USER_ASSERTED_UNVERIFIED','selected assertion remains unverified user claim');","check(run('opportunityPlanView.dependency_propagation.schema')===2,'unified dependency propagation schema2');")
j=j.replace("run('opportunityPlanView.dependency_propagation.selected_changed')===true&&",'')
a=j.index(" const display=textOf($('opp-plan-impact')); ") if " const display=textOf($('opp-plan-impact')); " in j else j.index(" const display=textOf($('opp-plan-impact'));")
b=j.index("\n $('service-plan-reason')",a)
j=j[:a]+" const display=textOf($('opp-plan-impact'));check(display.length>0&&!display.includes('PRIVATE_FACT_EXCERPT_')&&!display.includes('PRIVATE_REGION_SELECTED'),'unified projection omits raw private source values');"+j[b:]
(dest/'unified_dependency_propagation_real_html.js').write_text(j)
print('prepared API and HTML candidates')
