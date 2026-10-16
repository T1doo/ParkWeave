from pathlib import Path
root=Path(__file__).parent/'candidate/src/parkweave'
p=root/'case_resource_delivery.py';s=p.read_text();s=s.replace('class Deliver(rb.Bundle):','class PreviewBundle(rb.Bundle):\n    expected_link_revision: int | None = Field(default=None, ge=1, le=64)\n\n\nclass Deliver(PreviewBundle):')
pos=s.index('\ndef _candidate(')
helper='''
def _source_reapproval(store,c,p,parent,data,context,*,consumed=None,historical=False):
    """Exact previous association and original local ADOPT; no new authority."""
    revision=getattr(data,'expected_link_revision',None)
    if revision is None:return context
    approval=getattr(store,'_isolated_plan_approval',None)
    if not approval or not approval.enabled or not approval.source_reapproval_enabled:
        from .store import Denied
        raise Denied('isolated source reapproval disabled')
    approval._scope(c,p,parent)
    rows=cr._history(c,p,parent)
    anchors=[r for r in rows if r['revision']==revision]
    if len(anchors)!=1:raise Conflict('original reapproval link required')
    anchor=anchors[0];prior=anchor['snapshot'].get('delivery_binding');prior_approval=anchor['snapshot'].get('plan_approval')
    if not prior or not prior_approval:raise Conflict('original approved delivery anchor required')
    old_receipt=c.execute('SELECT payload FROM synthetic_resource_combination_receipts WHERE actor_id=%s AND request_key=%s',(p['id'],anchor['request_key'])).fetchone()
    if not old_receipt or old_receipt['payload'].get('delivery_binding')!=prior or old_receipt['payload'].get('plan_approval')!=prior_approval:
        raise Conflict('original approved delivery receipt required')
    from .service_plan_approval import verify_receipt
    verify_receipt(parent,old_receipt['payload'],prior_approval)
    if not historical and rows[-1]['id']!=anchor['id']:
        tail=rows[rows.index(anchor)+1:]
        if consumed is None or len(tail)!=1 or str(tail[0]['combination_id'])!=consumed:
            raise Conflict('latest original association changed')
        own=tail[0]['snapshot'].get('delivery_binding',{}).get('context',{}).get('source_reapproval',{})
        if own.get('link_id')!=str(anchor['id']):raise Conflict('delivery reapproval anchor changed')
    plan=parent['service_case_plan'];steps._recovery_proofs(parent)
    p2=next((s['id'] for s in plan['steps'] if s['adapter_id']=='P2'),None)
    approved=getattr(data,'expected_plan_revision',plan['revision'])
    events=[e for e in plan['events'] if e['action']=='ADOPT' and e['revision']<=approved]
    if not events:raise Conflict('explicit original source adoption required')
    event=events[-1];patch=event.get('local_revision') or {};change=patch.get('source_change')
    if (event['revision']<=prior['approved_plan_revision'] or not isinstance(change,dict)
        or p2 not in patch.get('affected',[]) or p2 not in change.get('affected',[])
        or patch.get('request',{}).get('opportunity_proof') is None):
        raise Conflict('new P2 original opportunity source adoption required')
    binding=dict(link_id=str(anchor['id']),link_revision=revision,snapshot_sha256=cp._hash(anchor['snapshot']),
        previous_delivery_context=prior['context'],previous_approved_plan_revision=prior['approved_plan_revision'],
        approved_plan_revision=approved,source_adoption_event_id=event['id'],source_adoption_revision=event['revision'],
        source_adoption_sha256=cp._hash(event),source_change_sha256=change['sha256'])
    return dict(context,source_reapproval=binding)

'''
s=s[:pos]+helper+s[pos:]
s=s.replace("    if cr._history(c, p, parent): raise Conflict('first Case resource delivery only; use existing rebind/substitution')", "    rows=cr._history(c,p,parent)\n    if rows and getattr(data,'expected_link_revision',None) is None:raise Conflict('first Case resource delivery only; explicit reapproval required')\n    if getattr(data,'expected_link_revision',None) is not None:\n        context=_source_reapproval(store,c,p,parent,data,context)")
s=s.replace("plan_revision=parent['service_case_plan']['revision'], link_revision=0))", "plan_revision=parent['service_case_plan']['revision'], link_revision=getattr(data,'expected_link_revision',None) or 0))")
s=s.replace("    if context != expected: issues.append('DELIVERY_SOURCE_CHANGED')", "    if 'source_reapproval' in expected:\n        historical=Deliver.model_validate(next(i['proposal']['request']['delivery'] for i in __import__('parkweave.service_plan_approval',fromlist=['_ledger'])._ledger(parent)[1].values() if i['id']==receipt['plan_approval']['id']))\n        context=_source_reapproval(store,c,p,parent,historical,context,consumed=str(gid),historical=True)\n        if parent['service_case_plan']['revision']!=proof['approved_plan_revision']:issues.append('DELIVERY_APPROVED_PLAN_REVISION_CHANGED')\n    if context != expected: issues.append('DELIVERY_SOURCE_CHANGED')")
s=s.replace("expected_link_revision=0,", "expected_link_revision=data.expected_link_revision or 0,")
p.write_text(s)
p=root/'service_plan_approval.py';s=p.read_text().replace("PURPOSE = 'CASE_RESOURCE_DELIVERY'", "PURPOSE = 'CASE_RESOURCE_DELIVERY'\nREAPPROVAL_PURPOSE = 'CASE_RESOURCE_REAPPROVAL'\n\n\ndef purpose(data):\n    return REAPPROVAL_PURPOSE if data.expected_link_revision is not None else PURPOSE")
s=s.replace("b.get('purpose') != PURPOSE", "b.get('purpose') != purpose(data.delivery)")
s=s.replace('enabled_for_isolated_tests=False):','enabled_for_isolated_tests=False, enabled_for_source_reapproval_tests=False):')
s=s.replace('        self.enabled = enabled_for_isolated_tests is True', "        self.enabled = enabled_for_isolated_tests is True\n        self.source_reapproval_enabled=enabled_for_source_reapproval_tests is True\n        if self.source_reapproval_enabled and not self.enabled:raise Denied('original isolated Approval must be enabled')")
s=s.replace("            if issues: raise Conflict('Approval prerequisite changed before commit')", "            if issues: raise Conflict('Approval prerequisite changed before commit')\n            if data.expected_link_revision is not None:\n                context=delivery._source_reapproval(store,c,p,parent,data,context,consumed=consumed)")
s=s.replace('return cp._normal(dict(scope=SCOPE,purpose=PURPOSE,context=context,','return cp._normal(dict(scope=SCOPE,purpose=purpose(data),context=context,')
s=s.replace("purpose=PURPOSE,plan_id=b['context']['plan_id']", "purpose=b['purpose'],plan_id=b['context']['plan_id']")
p.write_text(s)
p=root/'case_resources.py';s=p.read_text();needle="    if old:return _view(c,p,parent,rows,old,store=store)";replacement=needle+"\n    approval=getattr(store,'_isolated_plan_approval',None)\n    if rows and approval is not None and getattr(approval,'source_reapproval_enabled',False) and str(parent['id']) in approval.ids:\n        approval._scope(c,p,parent)\n        if delivery_binding is None or plan_approval is None:raise Conflict('explicit source reapproval delivery required')\n        from .service_plan_approval import verify_receipt\n        receipt=c.execute('SELECT payload FROM synthetic_resource_combination_receipts WHERE actor_id=%s AND request_key=%s',(p['id'],key)).fetchone()\n        if not receipt or receipt['payload'].get('delivery_binding')!=delivery_binding:raise Conflict('original reapproval delivery receipt required')\n        verify_receipt(parent,receipt['payload'],plan_approval)\n        anchor=delivery_binding.get('context',{}).get('source_reapproval',{})\n        if anchor.get('link_id')!=str(rows[-1]['id']) or anchor.get('link_revision')!=data.expected_link_revision:\n            raise Conflict('exact latest source reapproval anchor required')";assert needle in s;s=s.replace(needle,replacement);p.write_text(s)
p=root/'api.py';s=p.read_text().replace('def delivery_preview(preparation_id: UUID,data: bundles.Bundle,','def delivery_preview(preparation_id: UUID,data: delivery.PreviewBundle,');p.write_text(s)
