from pathlib import Path
import ast
root=Path('/workspace/ParkWeave');src=(root/'tests/test_unified_dependency_propagation_independent.py').read_text();tree=ast.parse(src)
keep={'record','private_tokens','create_declared_case','facts_case','full','card','change_fact','repair_tail','final','literal_sha'}
parts=[src[:src.index('ROOT=')],"ROOT=next(p for p in Path(__file__).resolve().parents if (p/'pyproject.toml').is_file())\nOUT=ROOT/'.runtime/plan-reapproval-independent/artifacts'\nALL=('P1','P2','P3','P4','P5')\nRUN_ID=uuid4().hex\n"]
lines=src.splitlines(keepends=True)
for node in tree.body:
 if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in keep:
  first=min([node.lineno]+[d.lineno for d in node.decorator_list]);parts.append(''.join(lines[first-1:node.end_lineno])+'\n\n')
s=''.join(parts)
s=s.replace("    yield t\n","    from parkweave.service_plan_approval import IsolatedPlanApproval\n    t['bridge']=IsolatedPlanApproval(f[1],f[1]._case_fact_fixture_receipt,preparation_ids=[row['preparation_id']],enabled_for_isolated_tests=True,enabled_for_source_reapproval_tests=True)\n    t['bridge'].attach_store(f[0])\n    yield t\n")
s+='''
from test_case_resource_delivery import preview as delivery_preview,submit as commit,recover as delivery_recover,effects
from test_service_plan_approval import read as approval_read,propose,decide,ledger
from test_resource_bundles import states
from test_preparation import command as prepare,add as add_material
from parkweave.resource_holds import RESOURCE_ID


def original_rows(t):
    with t['f'][1].connect() as db:
        return {table:db.execute('SELECT * FROM '+table+' ORDER BY to_jsonb('+table+')::text').fetchall() for table in ('case_resource_links','synthetic_resource_combinations','synthetic_resource_combination_members','synthetic_resource_combination_receipts','resource_case_claims')}


def assert_prefix_preserved(before,after):
    for table,rows in before.items():
        assert all(row in after[table] for row in rows),table


def source_adopt(t,kind='material_fact'):
    f,p=t['f'],t['p'];old=deepcopy(stored(f,p))
    if kind=='resource':add_resource(f)
    else:
        change_fact(t,refresh=False)
        current=dict(prep_read(f,p).json()['preparation'],preparation_id=p['preparation_id'])
        if current['state'] in ('REVIEWED','LOCAL_CONFIRMED'):
            r=prepare(f,current,'REOPEN',reason='SYNTHETIC explicit source reapproval input');assert r.status_code==200,r.text;current=r.json()
        r=add_material(f,current,slot='need_summary',text='SYNTHETIC actual source reapproval context v2');assert r.status_code==200,r.text
    c=card(t)
    from test_source_change_adoption import preview
    q=preview(f,p,c);assert q.status_code==200,q.text;v=q.json()
    ids={s['adapter_id']:s['id'] for s in old['steps']};wanted=ALL if kind!='resource' else ('P2','P3','P4','P5')
    assert v['affected']==[ids[a] for a in wanted]
    assert v['preserved']==([] if kind!='resource' else [ids['P1']]) and v['unknown_scope'] is None
    r=adopt(f,p,v['adoption']);assert r.status_code==201,r.text
    if kind!='resource':
        chain.material_decision(t['u'],p,'REVIEW');chain.material_decision(t['u'],p,'CONFIRM');verified(f,p,'P1')
    now=stored(f,p);assert now['id']==old['id'] and now['events'][:len(old['events'])]==old['events']
    record('source-adopt',kind=kind,affected=list(wanted),preserved=[] if kind!='resource' else ['P1'],original_source_change=True,original_p1_verify=True)
    return now


def fresh_holds(t):
    hs,data=chain.holds(t['u'],offset=12)
    assert states(t['f'],hs)==['HELD']*3
    return hs,data


def quote(t,data,revision=None,user='fixture-a'):
    if revision is None:revision=link_read(t['f'],t['p']).json()['link_revision']
    q=delivery_preview(t['f'],t['p'],{**data,'expected_link_revision':revision},user)
    assert q.status_code==200,q.text;q=q.json();assert q['expected_link_revision']==revision
    return {**data,'expected_link_revision':revision,'expected_preparation_revision':q['expected_preparation_revision'],'expected_plan_revision':q['expected_plan_revision'],'expected_source_sha256':q['source_sha256'],'valid_until':q['valid_until'],'reason':'SYNTHETIC explicit new source same-Case reapproval delivery'},q


def approved(t,data):
    f,p=t['f'],t['p'];q=approval_read(f,p);assert q.status_code==200,q.text
    r=propose(f,p,data,revision=q.json()['revision']);assert r.status_code==201,r.text
    q=r.json();item=q['items'][-1];r=decide(f,p,item,q['revision']);assert r.status_code==200,r.text
    item=r.json()['items'][-1];assert item['state']=='APPROVED' and item['current_available']
    return item


def finish_new_link(t):
    f,p=t['f'],t['p'];verified(f,p,'P2')
    id=t['completed']['A']['dispatch']['dispatch_id'];current=dict(prep_read(f,p).json()['preparation'],preparation_id=p['preparation_id'])
    q=f[3].get('/api/service-dispatches/'+id,headers=headers(f[2],'prep-specialist-fixture-a')).json()
    r=offer(f,current,revision=q['revision'],recovery_receipt_step_id=q['recovery_receipt_step_id'])[0];assert r.status_code==201,r.text
    r=dispatch_act(f,r.json(),'ACCEPT');assert r.status_code==200,r.text;verified(f,p,'P3')
    chain.report_and_ack(t['u'],p,r.json());verified(f,p,'P4');repair_tail(t,('P5',));final(t)


def prepared_reapproval(t,kind='material_fact'):
    source_adopt(t,kind);hs,data=fresh_holds(t);data,q=quote(t,data);item=approved(t,data)
    return hs,{**data,'approval_id':item['id']},q,item


def no_effect(t,data,expected=409,key=None,user='fixture-a'):
    before=full(t);r=commit(t['f'],t['p'],data,key,user);assert r.status_code==expected,r.text
    assert full(t)==before
    record('refusals',status=r.status_code,no_business_writes=True)
    return r


@pytest.mark.parametrize('kind',['material_fact','resource'])
def test_actual_explicit_original_reapproval_and_partial_verify_to_six_goals(facts_case,kind):
    t=facts_case;f,p=t['f'],t['p']
    if kind=='resource':assert lock(f,p,'P1').status_code==200
    oldplan=deepcopy(stored(f,p));old=original_rows(t);oldledger=deepcopy(ledger(f,p));oldlink=link_read(f,p).json()['link_revision']
    hs,data,q,item=prepared_reapproval(t,kind)
    key=uuid4().hex;r=commit(f,p,data,key);assert r.status_code==201,r.text;x=r.json()
    assert x['independent_check']['status']=='CURRENT' and x['independent_check']['plan_p2_automatically_verified'] is False
    assert x['link']['revision']==oldlink+1 and states(f,hs)==['CONFIRMED']*3
    assert effects(f)==[2,6,2,2,2]
    assert_prefix_preserved(old,original_rows(t));assert ledger(f,p)['events'][:len(oldledger['events'])]==oldledger['events']
    assert ledger(f,p)['revision']==oldledger['revision']+3
    before=full(t);assert commit(f,p,data,key).json()['receipt']==x['receipt'];assert full(t)==before
    recovered=delivery_recover(f,p,key);assert recovered.status_code==200 and recovered.json()['receipt']==x['receipt'] and full(t)==before
    if kind=='resource':assert stored(f,p)['steps'][0]==oldplan['steps'][0]
    finish_new_link(t);assert_prefix_preserved(old,original_rows(t))
    r=delivery_recover(f,p,t['completed']['A']['delivery_key']);assert r.status_code==200 and r.json()['independent_check']['status']=='NEEDS_RECHECK'
    record('closure',kind=kind,six_goals=True,new_link_revision=oldlink+1,old_occupancy_preserved=True,old_receipt_cold_get=True)


def test_original_default_first_delivery_and_unapproved_reapproval_refuse(facts_case):
    t=facts_case;source_adopt(t);hs,data=fresh_holds(t)
    before=full(t);r=delivery_preview(t['f'],t['p'],data);assert r.status_code==409 and full(t)==before
    b,_=quote(t,data);before=full(t);r=propose(t['f'],t['p'],b,revision=approval_read(t['f'],t['p']).json()['revision']);assert r.status_code==201,r.text
    item=r.json()['items'][-1];no_effect(t,{**b,'approval_id':item['id']});assert states(t['f'],hs)==['HELD']*3


def test_consumed_old_approval_cannot_authorize_new_source_delivery(facts_case):
    t=facts_case;old=ledger(t['f'],t['p']);oldid=approval_read(t['f'],t['p']).json()['items'][-1]['id']
    source_adopt(t);hs,data=fresh_holds(t);b,_=quote(t,data)
    no_effect(t,{**b,'approval_id':oldid});assert ledger(t['f'],t['p'])==old and states(t['f'],hs)==['HELD']*3


@pytest.mark.parametrize('actor',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a'])
def test_original_tenant_owner_and_role_cannot_read_or_commit_new_approval(facts_case,actor):
    t=facts_case;hs,b,q,item=prepared_reapproval(t)
    no_effect(t,b,expected=403,user=actor)
    before=full(t);assert approval_read(t['f'],t['p'],actor).status_code==403
    assert delivery_recover(t['f'],t['p'],uuid4().hex,actor).status_code==403 and full(t)==before


@pytest.mark.parametrize('damage',['resource_revision','resource_aba','plan_revision','authority_aba','preparation_revision'])
def test_approved_new_object_never_revives_after_original_source_change(facts_case,damage):
    t=facts_case;f,p=t['f'],t['p'];hs,b,q,item=prepared_reapproval(t)
    if damage=='plan_revision':assert lock(f,p,'P1').status_code==200
    elif damage=='preparation_revision':
        current=dict(prep_read(f,p).json()['preparation'],preparation_id=p['preparation_id']);r=prepare(f,current,'REOPEN',reason='SYNTHETIC after-approval source change');assert r.status_code==200,r.text
    elif damage=='authority_aba':
        with f[1].connect() as db:db.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='EXECUTE'")
        with f[1].connect() as db:db.execute("UPDATE capability_grants SET active=true,revision=revision+1 WHERE principal_id='fixture-a' AND capability='EXECUTE'")
    else:
        with f[1].connect() as db:row=db.execute('SELECT capacity FROM synthetic_resources WHERE id=%s',(hs[0]['resource_id'],)).fetchone();db.execute('UPDATE synthetic_resources SET capacity=capacity+1 WHERE id=%s',(hs[0]['resource_id'],))
        if damage=='resource_aba':
            with f[1].connect() as db:db.execute('UPDATE synthetic_resources SET capacity=%s WHERE id=%s',(row['capacity'],hs[0]['resource_id']))
    no_effect(t,b);assert states(f,hs)==['HELD']*3


@pytest.mark.parametrize('field',['reason','expected_link_revision','approval_id','valid_until'])
def test_exact_old_key_replay_rejects_changed_reapproval_parameters(facts_case,field):
    t=facts_case;hs,b,q,item=prepared_reapproval(t);key=uuid4().hex;r=commit(t['f'],t['p'],b,key);assert r.status_code==201,r.text
    changed=deepcopy(b)
    if field=='reason':changed[field]+=' changed'
    elif field=='expected_link_revision':changed[field]+=1
    elif field=='approval_id':changed[field]=str(uuid4())
    else:changed[field]='2099-01-01T00:00:00Z'
    no_effect(t,changed,key=key)


def test_unknown_original_key_get_never_executes_reapproval(facts_case):
    t=facts_case;source_adopt(t);hs,data=fresh_holds(t);before=full(t)
    r=delivery_recover(t['f'],t['p'],uuid4().hex);assert r.status_code==200 and r.json()['status']=='NOT_OBSERVED' and full(t)==before
    assert states(t['f'],hs)==['HELD']*3
'''
(root/'.runtime/plan-reapproval-independent/candidate/tests/test_plan_source_reapproval_independent.py').write_text(s)
print('prepared independent API candidate')
