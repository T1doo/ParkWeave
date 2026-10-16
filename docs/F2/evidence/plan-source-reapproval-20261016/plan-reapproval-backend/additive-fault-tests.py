@pytest.mark.parametrize('fault',['STRIP_PROFILE','SELF_ANCHOR'])
def test_rehashed_owned_fixture_profile_downgrade_and_self_reference_are_conflicts(link_fixture,fault):
    from psycopg.types.json import Jsonb
    from parkweave import controlled_plans as cp,service_plan_approval as a,preparation as prep
    from parkweave.store import digest
    f=link_fixture;p,old,bridge=first(f);source_adopt(f,p);hs,data=quote_second(f,p)
    item,_=approved(f,p,data);key=uuid4().hex;result=submit(f,p,{**data,'approval_id':item['id']},key)
    assert result.status_code==201,result.text
    value=result.json();receipt=deepcopy(value['receipt']);events=deepcopy(ledger(f,p));proposal,approval,consume=events['events'][3:]
    context=proposal['binding']['context']
    for command in (proposal['request']['delivery'],consume['request']['delivery']):
        if fault=='STRIP_PROFILE':command.pop('expected_link_revision')
        else:command['expected_link_revision']=2
    if fault=='STRIP_PROFILE':
        context.pop('source_reapproval');proposal['binding']['purpose']='CASE_RESOURCE_DELIVERY'
        receipt['delivery_binding']['context'].pop('source_reapproval')
    else:
        for current in (context['source_reapproval'],receipt['delivery_binding']['context']['source_reapproval']):
            current.update(link_id=value['link']['id'],link_revision=2,snapshot_sha256='a'*64)
    new_binding_sha=cp._hash(proposal['binding'])
    approval['request']['expected_binding_sha256']=new_binding_sha
    receipt['plan_approval']['binding_sha256']=new_binding_sha
    fp=digest(prep.canonical(dict(preparation_id=p['preparation_id'],action='CASE_RESOURCE_DELIVERY',**consume['request']['delivery'])))
    receipt['delivery_binding']['fingerprint']=fp
    consume['receipt'].update(fingerprint=fp,receipt_sha256=cp._hash(receipt))
    previous=None
    for event in events['events']:
        event['previous_sha256']=previous;event['fingerprint']=a._fingerprint(p['preparation_id'],event['request'])
        event['sha256']=cp._hash({k:v for k,v in event.items() if k!='sha256'});previous=event['sha256']
    snapshot=deepcopy(value['link']['snapshot']);snapshot['delivery_binding']=receipt['delivery_binding'];snapshot['plan_approval']=receipt['plan_approval']
    with f[1].connect() as c:
        c.execute('ALTER TABLE preparations DISABLE TRIGGER candidate_plan_approval_prefix')
        c.execute('UPDATE preparations SET candidate_plan_approvals=%s,candidate_plan_approval_head=%s WHERE id=%s',
            (Jsonb(events),Jsonb(dict(revision=events['revision'],sha256=previous)),p['preparation_id']))
        c.execute('ALTER TABLE preparations ENABLE TRIGGER candidate_plan_approval_prefix')
        c.execute('UPDATE synthetic_resource_combination_receipts SET payload=%s,fingerprint=%s WHERE actor_id=%s AND request_key=%s',(Jsonb(receipt),fp,'fixture-a',key))
        c.execute('UPDATE case_resource_links SET snapshot=%s,fingerprint=%s WHERE id=%s',(Jsonb(snapshot),fp,value['link']['id']))
    response=recover(f,p,key);assert response.status_code==409,response.text
    if fault=='STRIP_PROFILE':assert 'first delivery proof' in response.text
    else:assert 'original source reapproval association profile required' in response.text
