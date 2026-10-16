from pathlib import Path
p=Path(__file__).parent/'candidate/src/parkweave/case_resource_delivery.py'
s=p.read_text();begin=s.index("    checked=_verify(store,c,p,parent,old_receipt['payload'])");end=s.index("    p2=next(",begin)
replacement="""    # Prove a strictly descending immutable link before recursively checking
    # its previous approved delivery. A forged self-reference fails here.
    own_links=[r for r in rows if consumed is not None and str(r['combination_id'])==consumed]
    if historical and len(own_links)!=1:raise Conflict('unique original reapproval association required')
    if own_links:
        if len(own_links)!=1:raise Conflict('ambiguous reapproval association')
        own_link=own_links[0];own_proof=own_link['snapshot'].get('delivery_binding') or {}
        own=own_proof.get('context',{}).get('source_reapproval',{})
        actual=c.execute('SELECT payload,fingerprint FROM synthetic_resource_combination_receipts WHERE combination_id=%s AND actor_id=%s AND request_key=%s',(own_link['combination_id'],p['id'],own_link['request_key'])).fetchone()
        if (own_link['revision']!=revision+1 or own_link['actor_id']!=p['id']
            or own_link['fingerprint']!=own_proof.get('fingerprint') or own_link['request_key']!=own_proof.get('request_key')
            or own.get('link_id')!=str(anchor['id']) or own.get('link_revision')!=revision
            or not actual or actual['fingerprint']!=own_link['fingerprint']
            or actual['payload'].get('delivery_binding')!=own_proof
            or actual['payload'].get('plan_approval')!=own_link['snapshot'].get('plan_approval')):
            raise Conflict('delivery reapproval anchor changed')
        verify_receipt(parent,actual['payload'],own_link['snapshot']['plan_approval'])
    if not historical and rows[-1]['id']!=anchor['id']:
        tail=rows[rows.index(anchor)+1:]
        if len(tail)!=1 or len(own_links)!=1 or tail[0]['id']!=own_links[0]['id']:
            raise Conflict('latest original association changed')
    checked=_verify(store,c,p,parent,old_receipt['payload'])
    if checked['link']!=anchor or old_receipt['payload']['delivery_binding']!=prior:
        raise Conflict('exact original approved association required')
    current_plan=parent['service_case_plan'];plan=current_plan
    if historical:
        matches=[x for x in [current_plan,*current_plan.get('history',[])] if x['id']==prior['context'].get('plan_id')]
        if len(matches)!=1:raise Conflict('unique original reapproval plan required')
        plan=matches[0]
    elif plan['id']!=prior['context'].get('plan_id'):raise Conflict('original same plan reapproval required')
"""
s=s[:begin]+replacement+s[end:];s=s.replace("    if not prior or not prior_approval:raise Conflict('original approved delivery anchor required')","    if not isinstance(prior,dict) or not isinstance(prior_approval,dict) or not isinstance(prior.get('context'),dict):raise Conflict('original approved delivery anchor required')")
p.write_text(s)
