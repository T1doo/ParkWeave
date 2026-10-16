"""First same-Case local capacity delivery; no formal Release or Approval."""
from datetime import timedelta, timezone
from uuid import UUID

from pydantic import AwareDatetime, Field, field_validator

from . import resource_bundles as rb, resource_combinations as rc, resource_holds as rh
from . import case_resources as cr, preparation as prep, controlled_plans as cp
from . import service_case_steps as steps, resource_plan_binding as binding
from .executor_receipts import bounded, material_current
from .store import Conflict, digest

SCOPE = 'SYNTHETIC_FIRST_CASE_RESOURCE_DELIVERY_ONLY'


def _boundary(**extra):
    return {**rh._boundary(case_goal_completed=False), 'scope': SCOPE, **extra}


class PreviewBundle(rb.Bundle):
    expected_link_revision: int | None = Field(default=None, ge=1, le=64)


class Deliver(PreviewBundle):
    approval_id: UUID | None = Field(default=None, strict=False)
    expected_preparation_revision: int = Field(ge=1, le=64)
    expected_plan_revision: int = Field(ge=1, le=64)
    expected_source_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    valid_until: AwareDatetime = Field(strict=False)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator('reason')
    @classmethod
    def explicit_reason(cls, value):
        if not value.strip(): raise ValueError('explicit nonblank delivery reason required')
        return value

    @field_validator('valid_until')
    @classmethod
    def utc(cls, value):
        return value.astimezone(timezone.utc)


def _definition(plan):
    return cp._hash({k: plan[k] for k in ('id', 'required_goals', 'goal_coverage', 'binding')} |
        {'steps': [{k: s[k] for k in ('id', 'adapter_id', 'adapter', 'adapter_revision', 'depends_on', 'contract')} for s in plan['steps']]})


def _context(store, c, p, parent):
    plan = parent.get('service_case_plan')
    issues = []
    definition = None
    if not plan or not any(s['adapter_id'] == 'P2' for s in plan['steps']):
        issues.append('ADOPTED_RESOURCE_PLAN_REQUIRED')
    else:
        definition = _definition(plan)
        changed, prerequisites, sources, actual, states, bad = steps._inspect(store, c, parent, plan, observe=False)
        if changed or states['P1'] != 'VERIFIED': issues.append('CURRENT_PLAN_P1_REQUIRED')
    if not material_current(c, parent, store): issues.append('CURRENT_CONFIRMED_MATERIALS_REQUIRED')
    catalog = steps._catalog(c, parent)
    if not cp.binding_catalog_known(catalog): issues.append('KNOWN_SYNTHETIC_SERVICE_SOURCE_REQUIRED')
    if parent['namespace'] != 'SYNTHETIC' or parent['service_id'] != prep.SERVICE or parent['service_version'] != 1:
        issues.append('EXISTING_SYNTHETIC_SERVICE_CONTRACT_REQUIRED')
    snapshot = {k: parent[v] for k, v in (('preparation_id','id'), ('case_id','case_id'), ('run_id','run_id'),
        ('service_id','service_id'), ('service_version','service_version'), ('preparation_revision','revision'),
        ('preparation_sha256','review_sha256'))}
    p1 = cp.binding_p1(c, parent, snapshot, store=store)
    context = cp._normal(dict(scope=SCOPE, preparation_id=parent['id'], case_id=parent['case_id'], run_id=parent['run_id'],
        owner_id=parent['owner_id'], park_id=parent['park_id'], org_id=parent['org_id'],
        preparation_revision=parent['revision'], preparation_sha256=parent['review_sha256'],
        service_id=parent['service_id'], service_version=parent['service_version'], catalog_sha256=cp._hash(catalog),
        plan_id=plan['id'] if plan else None, plan_definition_sha256=definition, p1_source_sha256=cp._hash(p1)))
    return context, sorted(set(issues))


def _source_reapproval(store,c,p,parent,data,context,*,consumed=None,historical=False):
    """Exact previous association and original local ADOPT; no new authority."""
    revision=getattr(data,'expected_link_revision',None)
    if revision is None:return context
    approval=getattr(store,'_isolated_plan_approval',None)
    if not historical and (not approval or not approval.enabled or not approval.source_reapproval_enabled):
        from .store import Denied
        raise Denied('isolated source reapproval disabled')
    if not historical:approval._scope(c,p,parent)
    steps._recovery_proofs(parent)
    rows=cr._history(c,p,parent)
    anchors=[r for r in rows if r['revision']==revision]
    if len(anchors)!=1:raise Conflict('original reapproval link required')
    anchor=anchors[0];prior=anchor['snapshot'].get('delivery_binding');prior_approval=anchor['snapshot'].get('plan_approval')
    if not isinstance(prior,dict) or not isinstance(prior_approval,dict) or not isinstance(prior.get('context'),dict):raise Conflict('original approved delivery anchor required')
    old_receipt=c.execute('SELECT payload FROM synthetic_resource_combination_receipts WHERE actor_id=%s AND request_key=%s',(p['id'],anchor['request_key'])).fetchone()
    if not old_receipt or old_receipt['payload'].get('delivery_binding')!=prior or old_receipt['payload'].get('plan_approval')!=prior_approval:
        raise Conflict('original approved delivery receipt required')
    from .service_plan_approval import verify_receipt
    verify_receipt(parent,old_receipt['payload'],prior_approval)
    # Prove a strictly descending immutable link before recursively checking
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
    p2=next((s['id'] for s in plan['steps'] if s['adapter_id']=='P2'),None)
    approved=getattr(data,'expected_plan_revision',plan['revision'])
    events=[e for e in plan['events'] if e['action']=='ADOPT' and (not historical or e['revision']<=approved)]
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


def _candidate(store, c, p, parent, data, *, observe=True):
    hs = [rh._own(c, p, m.hold_id) for m in data.members]
    rules = rc._scope_lock(c, p, hs, write=True)
    hs = [rh._own(c, p, m.hold_id, lock=True) for m in data.members]
    context, issues = _context(store, c, p, parent)
    if issues: raise Conflict(';'.join(issues))
    cp.gate(store, c, parent, 1, observe=observe)
    rows=cr._history(c,p,parent)
    if rows and getattr(data,'expected_link_revision',None) is None:raise Conflict('first Case resource delivery only; explicit reapproval required')
    if getattr(data,'expected_link_revision',None) is not None:
        context=_source_reapproval(store,c,p,parent,data,context)
    now = rh._now(c)
    for h, m in zip(hs, data.members):
        r = rules[h['resource_id']]
        if h.get('combination_id') or h['state'] != 'HELD' or h['expires_at'] <= now:
            raise Conflict('current unconfirmed holds required')
        if m.expected_revision != h['resource_revision'] or h['resource_revision'] != r['revision']:
            raise Conflict('resource revision changed')
        lo, hi = rh._window(r, rh.Preview(starts_at=h['starts_at'], ends_at=h['ends_at'], quantity=h['quantity']), now)
        if rh._peak(c, h['resource_id'], lo, hi, now, exclude=h['id']) + h['quantity'] > r['capacity']:
            raise Conflict('resource capacity conflict')
    source = cp._normal(dict(context=context, members=hs, rules=[rules[k] for k in sorted(rules, key=str)],
        grants=cp.binding_p2(c, parent, {}, hs, rules)['resource_grants'],
        plan_revision=parent['service_case_plan']['revision'], link_revision=getattr(data,'expected_link_revision',None) or 0))
    return context, cp._hash(source), hs, now


@bounded
def preview(store, token, id, data):
    with store.connect() as c:
        p, parent = cr._parent(store, c, token, id, write=True)
        context, sha, hs, now = _candidate(store, c, p, parent, data)
        expiry = min(now+timedelta(seconds=120), *[h['expires_at'] for h in hs])
        return _boundary(actor_id=p['id'], context=context,
            expected_preparation_revision=parent['revision'], expected_plan_revision=parent['service_case_plan']['revision'],
            source_sha256=cp._hash(dict(source=sha,valid_until=expiry.isoformat())), valid_until=expiry,
            members=[rh._public(h, now) for h in hs], formal_approval='NOT_IMPLEMENTED', formal_release=False,
            synthetic_plan_approval_required=getattr(store,'_isolated_plan_approval',None) is not None,
            **({'expected_link_revision':data.expected_link_revision} if getattr(data,'expected_link_revision',None) is not None else {}))


def _verify(store, c, p, parent, receipt):
    from .service_plan_approval import verify_receipt
    verify_receipt(parent, receipt)
    proof = receipt.get('delivery_binding')
    if not isinstance(proof, dict) or proof.get('scope') != SCOPE: raise Conflict('original delivery proof required')
    expected = proof.get('context')
    required={'scope','context','approved_plan_revision','preview_source_sha256','valid_until','request_key','fingerprint'}
    if set(proof)!=required or not isinstance(expected,dict) or not isinstance(proof['request_key'],str):
        raise Conflict('delivery proof shape mismatch')
    try:
        gid=UUID(receipt['combination_id'])
        for name in ('preparation_id','case_id','run_id'):UUID(expected[name])
        if receipt.get('scope')!=rb.SCOPE or receipt.get('action')!='CONFIRM':raise ValueError()
        actual=c.execute('SELECT * FROM synthetic_resource_combination_receipts WHERE combination_id=%s AND actor_id=%s AND request_key=%s',
            (gid,p['id'],proof['request_key'])).fetchone()
        if not actual or actual['payload']!=receipt or actual['fingerprint']!=proof['fingerprint']:raise ValueError()
    except (KeyError,ValueError,TypeError,AttributeError):raise Conflict('delivery original event proof mismatch')
    keys=('preparation_id','case_id','run_id','owner_id','park_id','org_id')
    if not all(isinstance(expected.get(k),str) for k in keys):raise Conflict('delivery context shape mismatch')
    if any(str(parent[k]) != expected[v] for k,v in (('id','preparation_id'), ('case_id','case_id'), ('run_id','run_id'),
            ('owner_id','owner_id'), ('park_id','park_id'), ('org_id','org_id'))): raise Conflict('delivery Case scope mismatch')
    gid = UUID(receipt['combination_id'])
    group = rc._group(c, p, gid); rb.require_kind(c, gid)
    hs = rc._members(c, p, gid); rc._scope_lock(c, p, hs)
    group = rc._group(c, p, gid); hs = rc._members(c, p, gid)
    rb.validate_manifest(receipt, hs)
    rows = cr._history(c, p, parent)
    matches = [r for r in rows if r['request_key'] == proof['request_key'] and r['actor_id'] == p['id']]
    if len(matches) != 1: raise Conflict('delivery immutable association missing')
    link = matches[0]
    if (link['combination_id'] != gid or link['fingerprint'] != proof['fingerprint'] or
        link['snapshot'].get('delivery_binding') != proof or
        link['snapshot'].get('plan_approval') != receipt.get('plan_approval')): raise Conflict('delivery association proof mismatch')
    anchor=expected.get('source_reapproval')
    if anchor is None:
        if link['revision']!=1:raise Conflict('first delivery proof cannot authorize a later association')
    else:
        from .service_plan_approval import _ledger, REAPPROVAL_PURPOSE
        item=_ledger(parent)[1].get(receipt.get('plan_approval',{}).get('id'))
        if (not isinstance(anchor,dict) or type(anchor.get('link_revision')) is not int
            or link['revision']!=anchor['link_revision']+1 or not item
            or item['proposal']['binding']['purpose']!=REAPPROVAL_PURPOSE):
            raise Conflict('original source reapproval association profile required')
    claim = c.execute('SELECT * FROM resource_case_claims WHERE combination_id=%s',(gid,)).fetchone()
    if not claim or any(claim[k] != link[k] for k in ('case_id','owner_id','park_id','org_id')):
        raise Conflict('delivery Case claim mismatch')
    context, issues = _context(store, c, p, parent)
    if 'source_reapproval' in expected:
        from .service_plan_approval import _ledger
        historical=Deliver.model_validate(_ledger(parent)[1][receipt['plan_approval']['id']]['proposal']['request']['delivery'])
        context=_source_reapproval(store,c,p,parent,historical,context,consumed=str(gid),historical=True)
        if parent['service_case_plan']['id']!=expected['plan_id'] or any(e['action']=='ADOPT' and e['revision']>proof['approved_plan_revision'] for e in parent['service_case_plan']['events']):issues.append('DELIVERY_APPROVED_PLAN_ADOPTION_CHANGED')
    if context != expected: issues.append('DELIVERY_SOURCE_CHANGED')
    association = cr._view(c, p, parent, rows, store=store)
    item = next(x for x in association['history'] if x['record']['id'] == link['id'])
    issues += item['reasons']
    if rows[-1]['id'] != link['id']: issues.append('DELIVERY_ASSOCIATION_SUPERSEDED')
    return _boundary(actor_id=p['id'], status='COMMITTED', historical_only=True,
        automatically_replayed=False, receipt=receipt, delivery_binding=proof, combination=rc._view(group,hs,rh._now(c)),
        link=link, independent_check=dict(status='CURRENT' if not issues else 'NEEDS_RECHECK', issues=sorted(set(issues)),
        checked_actual_members=len(hs), plan_p2_automatically_verified=False), formal_approval='NOT_IMPLEMENTED', formal_release=False)


@bounded
def deliver(store, token, id, key, data):
    fp = digest(prep.canonical(dict(preparation_id=str(id), action='CASE_RESOURCE_DELIVERY', **data.model_dump(mode='json', exclude_none=True))))
    with store.connect() as c:
        p, parent = cr._parent(store, c, token, id, write=True)
        for m in data.members: rh._scope(c, p, rh._own(c,p,m.hold_id)['resource_id'], write=True)
        rh._key(c, p, key)
        prior = rh._replay(c, p, key, fp)
        if prior: return _verify(store, c, p, parent, prior)
        approval = getattr(store, '_isolated_plan_approval', None)
        if approval is None and data.approval_id is not None:
            from .store import Denied
            raise Denied('isolated plan Approval disabled')
        publication=getattr(approval,'_catalog_publication',None)
        if publication is not None:publication.acquire(c,parent)
        elif approval is not None:
            from .catalog_publication import lock,key_of
            lock(c,key_of(parent))
        context, sha, hs, now = _candidate(store, c, p, parent, data)
        if (parent['revision'] != data.expected_preparation_revision or parent['service_case_plan']['revision'] != data.expected_plan_revision
            or cp._hash(dict(source=sha,valid_until=data.valid_until.isoformat())) != data.expected_source_sha256
            or not now < data.valid_until <= now+timedelta(seconds=120)
            or any(data.valid_until > h['expires_at'] for h in hs)):
            raise Conflict('delivery preview expired or source/revision changed')
        proof = dict(scope=SCOPE, context=context, approved_plan_revision=data.expected_plan_revision,
            preview_source_sha256=data.expected_source_sha256, valid_until=data.valid_until.isoformat(), request_key=key, fingerprint=fp)
        approval_proof = approval.before_delivery(store,c,p,parent,key,data,fp) if approval else None
        extra = {'delivery_binding':proof}
        if approval_proof: extra['plan_approval'] = approval_proof
        result = rc._confirm_locked(store,c,p,key,data,fp,rb.SCOPE,bundle=True,receipt_extra=extra)
        if approval:
            parent = approval.consume(store,c,p,parent,key,data,fp,approval_proof,result['receipt'])
        gid = result['combination']['id']
        comparison = binding.proposal(store,c,p,parent,gid,delivery_plan=True)['comparison']
        if not comparison['can_confirm']: raise Conflict(';'.join(comparison['blockers']))
        link_data = cr.Bind(combination_id=gid,expected_preparation_revision=parent['revision'],expected_link_revision=data.expected_link_revision or 0,
            reason=data.reason,expected_comparison_sha256=comparison['sha256'])
        # Existing binder owns claim, strict catalogue decision and immutable link.
        cr._bind_locked(store,c,p,parent,id,key,link_data,fp,delivery_binding=proof,plan_approval=approval_proof)
        # Snapshot is INSERT-only: the binder receives the proof before insertion.
        # Its comparison evidence is independently checked together with actual rows.
        current = _verify(store,c,p,parent,result['receipt'])
        if current['independent_check']['status'] != 'CURRENT': raise Conflict('delivery changed before commit')
        # Binding can wait for the final Case row upgrade after confirming the
        # holds. This is still a first write: expired consent must roll it all
        # back. Historical replay and GET returned above deliberately retain
        # their original event, rather than re-executing an expired hold.
        if rh._now(c) >= data.valid_until:
            raise Conflict('delivery preview expired during final Case binding; refresh required')
        return current


@bounded
def recover(store, token, id, key):
    with store.connect() as c:
        p, parent = cr._parent(store,c,token,id)
        rh._key(c,p,key)
        row = c.execute('SELECT payload FROM synthetic_resource_combination_receipts WHERE actor_id=%s AND request_key=%s',
            (p['id'],key)).fetchone()
        if row: return _verify(store,c,p,parent,row['payload'])
        if c.execute('SELECT 1 FROM synthetic_resource_receipts WHERE actor_id=%s AND request_key=%s',(p['id'],key)).fetchone():
            raise Conflict('original delivery request contract mismatch')
        return _boundary(actor_id=p['id'],status='NOT_OBSERVED',historical_only=True,automatically_replayed=False)
