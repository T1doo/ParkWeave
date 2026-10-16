from .business_frontier_types import BusinessFrontierFence,request as frontier_request,historical_fields
from .business_frontier import view as frontier_view,check_fence
"""Ordinary accepted manual Case cancellation before any historical receipt.

No effects are undone: every ACCEPT and its initial receipt step stay immutable.
The common parent lock serializes the full lineage with SUBMIT and reassignment.
"""
import json
from . import case_cancellation as cc, preparation as prep, service_dispatches as sd, executor_receipts as er
from .store import Conflict, Denied, digest

SCOPE='SYNTHETIC_CASE_CANCEL_AFTER_ACCEPT_BEFORE_FIRST_RECEIPT'
ACTION='CANCEL_BEFORE_RECEIPT'
Cancel=cc.Cancel


def _json(value):return json.loads(json.dumps(value,default=str,sort_keys=True))


def _head(value):
    """Bind dependency contents without exporting resource data under Case rights."""
    if value is None:return None
    data=_json(value)
    return dict(id=data.get('id'),revision=data.get('revision'),sha256=digest(prep.canonical(data)))


def _manual_lineage(store,c,parent,root,*,allow_manual_receipts=False):
    issues=[]
    if not sd._handoff_enabled(store,c):issues.append('ORDINARY_MANUAL_CASE_REQUIRED')
    if any(a.get('managed_access') is not None for a in c.execute('SELECT * FROM run_assignments WHERE run_id=%s',(parent['run_id'],)).fetchall()):
        issues.append('ISOLATED_RUN_ACCESS_NOT_SUPPORTED')
    steps=c.execute('SELECT * FROM service_receipt_steps WHERE preparation_id=%s OR case_id=%s ORDER BY id LIMIT 65',
                    (parent['id'],parent['case_id'])).fetchall()
    events=c.execute("""SELECT e.* FROM service_receipt_events e JOIN service_receipt_steps s ON s.id=e.step_id
        WHERE s.preparation_id=%s OR s.case_id=%s ORDER BY e.id LIMIT 65""",(parent['id'],parent['case_id'])).fetchall()
    submitted=c.execute('''SELECT 1 FROM service_step_receipts r JOIN service_receipt_steps s ON s.id=r.step_id
        WHERE s.preparation_id=%s OR s.case_id=%s LIMIT 1''',(parent['id'],parent['case_id'])).fetchone()
    if not allow_manual_receipts and (submitted or any(e['action']!='CREATE' for e in events)):issues.append('HISTORICAL_RECEIPT_SUBMISSION_NOT_SUPPORTED')
    offers=c.execute('SELECT * FROM service_dispatch_offers WHERE dispatch_id=%s ORDER BY id LIMIT 65',
                     (root['id'],)).fetchall() if root else []
    accepts=c.execute("SELECT * FROM service_dispatch_events WHERE dispatch_id=%s AND action='ACCEPT' ORDER BY revision LIMIT 65",
                      (root['id'],)).fetchall() if root else []
    if not accepts:issues.append('ACTUAL_ACCEPTANCE_REQUIRED')
    if any(len(rows)>64 for rows in (steps,events,offers,accepts)):issues.append('MANUAL_LINEAGE_LIMIT_REACHED')
    by_offer={o['id']:o for o in offers};by_step={s['id']:s for s in steps}
    bound=set();proofs=[]
    for e in accepts:
        o=by_offer.get(e['offer_id']);s=by_step.get(o['receipt_step_id']) if o else None
        try:
            if not o or not s or not root or o['state']!='ACCEPTED' or e['actor_id']!=o['executor_id'] or not isinstance(e['payload'],dict):
                raise ValueError()
            expected=dict(dispatch_id=str(root['id']),offer_id=str(o['id']),receipt_step_id=str(s['id']),
                revision=e['revision'],action='ACCEPT',state='ACCEPTED',actor_id=s['executor_id'],executor_id=s['executor_id'])
            if not sd._typed_fields_equal(e['payload'],expected) or e['revision']>root['revision']:
                raise ValueError()
            request=sd.Command(action='ACCEPT',expected_revision=e['revision']-1,reason=e['payload']['reason'],
                **historical_fields(e['payload']))
            fp=digest(prep.canonical(dict(dispatch_id=str(root['id']),**frontier_request(request))))
            creates=[x for x in events if x['step_id']==s['id'] and (not allow_manual_receipts or x['action']=='CREATE')]
            fields=('preparation_id','run_id','case_id','owner_id','park_id','org_id','service_id','service_version')
            if (s['id'] in bound or any(s[k]!=parent['id' if k=='preparation_id' else k] for k in fields)
                or s['namespace']!='SYNTHETIC'
                or (not allow_manual_receipts and (s['state']!='AWAITING_RECEIPT' or s['revision']!=1 or s['current_receipt_id'] is not None))
                or s['executor_id']!=o['executor_id']
                or s['preparation_revision']!=o['preparation_revision'] or s['preparation_sha256']!=o['preparation_sha256']
                or e['fingerprint']!=fp or len(creates)!=1):raise ValueError()
            create=creates[0]
            if not isinstance(create['payload'],dict):raise ValueError()
            expected_create=dict(step_id=str(s['id']),revision=1,state='AWAITING_RECEIPT',action='CREATE',
                actor_id=s['executor_id'],scope=er.SCOPE,dispatch_id=str(root['id']),offer_id=str(o['id']),reason=request.reason)
            if (create['action']!='CREATE' or create['revision']!=1 or create['actor_id']!=s['executor_id']
                or create['request_key']!='dispatch-accept:'+str(o['id']) or create['fingerprint']!=fp
                or not sd._typed_fields_equal(create['payload'],expected_create)):raise ValueError()
            if historical_fields(e['payload'])!=historical_fields(create['payload']):raise ValueError()
            extras={k:v for k,v in e['payload'].items() if k not in {*expected,'reason','expected_business_frontier'}}
            create_extras={k:v for k,v in create['payload'].items() if k not in {*expected_create,'expected_business_frontier'}}
            if prep.canonical(extras)!=prep.canonical(create_extras):raise ValueError()
            offered=c.execute("SELECT payload FROM service_dispatch_events WHERE offer_id=%s AND action IN ('OFFER','REOFFER') ORDER BY revision LIMIT 1",(o['id'],)).fetchone()
            if not offered or not isinstance(offered['payload'],dict):raise ValueError()
            historical_fields(offered['payload'])
            offered_extras={k:v for k,v in offered['payload'].items() if k not in {*expected,'reason','expected_business_frontier'}}
            if prep.canonical(extras)!=prep.canonical(offered_extras):raise ValueError()
            # A later acceptance cannot become an initial one by stripping the
            # same lineage fields from both ACCEPT and CREATE (or REOFFER).
            if e['id']!=accepts[0]['id'] and not extras:raise ValueError()
            if extras:
                predecessor=next((x for x in offers if str(x['id'])==extras.get('predecessor_offer_id')),None)
                previous=by_step.get(predecessor['receipt_step_id']) if predecessor else None
                previous_accepts=[x for x in accepts if predecessor and x['offer_id']==predecessor['id'] and x['revision']<e['revision']]
                if not previous or len(previous_accepts)!=1:raise ValueError()
                expected_extras=dict(predecessor_offer_id=str(predecessor['id']),predecessor_receipt_step_id=str(previous['id']),
                    previous_preparation_revision=predecessor['preparation_revision'],previous_preparation_sha256=predecessor['preparation_sha256'],
                    accepted_preparation_revision=o['preparation_revision'],accepted_preparation_sha256=o['preparation_sha256'])
                if extras.get('handoff_kind')=='PENDING_MANUAL_RECEIPT':
                    expected_extras.update(handoff_kind='PENDING_MANUAL_RECEIPT',predecessor_executor_id=predecessor['executor_id'],
                        predecessor_receipt_revision=1)
                    if predecessor['executor_id']==o['executor_id']:raise ValueError()
                elif predecessor['executor_id']!=o['executor_id'] or predecessor['preparation_revision']>=o['preparation_revision']:
                    raise ValueError()
                if set(extras)!=set(expected_extras) or not sd._typed_fields_equal(extras,expected_extras):raise ValueError()
                if not sd._typed_fields_equal(offered['payload'],expected_extras):raise ValueError()
            bound.add(s['id'])
            proofs.append(dict(accept_event_id=str(e['id']),accept_revision=e['revision'],accept_fingerprint=fp,
                accept_payload_sha256=digest(prep.canonical(e['payload'])),create_event_id=str(create['id']),
                create_payload_sha256=digest(prep.canonical(create['payload'])),offer_id=str(o['id']),step_id=str(s['id'])))
        except (KeyError,TypeError,ValueError):issues.append('EXACT_MANUAL_ACCEPTANCE_AND_CREATE_PROOF_REQUIRED')
    accepted_offers={e['offer_id'] for e in accepts}
    if bound!=set(by_step) or accepted_offers!={o['id'] for o in offers if o['state']=='ACCEPTED' or o['receipt_step_id'] is not None}:
        issues.append('ALL_MANUAL_GENERATIONS_MUST_HAVE_ACCEPTANCE_PROOF')
    if not root or root['current_offer_id'] not in by_offer:issues.append('CURRENT_DISPATCH_LINEAGE_REQUIRED')
    return dict(dispatch_id=str(root['id']) if root else None,current_offer_id=str(root['current_offer_id']) if root else None,
        steps=_json(steps),offers=_json(offers),acceptance_proofs=proofs),issues


def _source(store,c,parent,root,case,local):
    source,issues=cc._source(c,parent,root,case,local,check_before_accept=False)
    if not c.execute('SELECT 1 FROM schema_version WHERE version=31').fetchone():issues.append('BEFORE_RECEIPT_CANCELLATION_INCREMENT_NOT_INSTALLED')
    lineage,manual_issues=_manual_lineage(store,c,parent,root)
    source.update(cancellation_scope=SCOPE,manual_lineage=lineage,
        controlled_plan=_head(c.execute('SELECT * FROM controlled_plans WHERE preparation_id=%s',(parent['id'],)).fetchone()),
        registered_plan=_head(parent.get('service_case_plan')),
        resource_links=[_head(x) for x in c.execute('SELECT * FROM case_resource_links WHERE case_id=%s ORDER BY revision',(parent['case_id'],)).fetchall()])
    return source,sorted(set(issues+manual_issues))


def _view(store,c,p,parent,root,case,local):
    source,issues=_source(store,c,parent,root,case,local)
    allowed=True
    try:store.check_capability(c,p,'EXECUTE')
    except Denied:allowed=False
    return dict(**frontier_view(c,parent),scope=SCOPE,actor_id=p['id'],preparation_id=str(parent['id']),case_id=str(parent['case_id']),
        case_state=case['state'],preparation_revision=parent['revision'],lifecycle_revision=local['revision'] if local else 0,
        source_sha256=digest(prep.canonical(source)),source=source,blockers=issues,can_cancel=allowed and not issues,
        resource_release_automatic=False,restore_supported=False,run_state=source['run_state'],case_goal_completed=False)


@er.bounded
def read(store,token,id):
    with store.connect() as c:
        p,parent=cc._context(store,c,token,id)
        return _view(store,c,p,parent,*cc._locks(c,parent))


@er.bounded
def recover(store,token,id,key):
    with store.connect() as c:
        p,parent=cc._context(store,c,token,id)
        c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('case-local-key:'+p['id']+':'+key,))
        root,case,local=cc._locks(c,parent)
        old=cc._original(c,p,parent,key,scope=SCOPE,action=ACTION)
        if old:cc._committed_state(case,local,old)
        result=cc._result(old) if old else dict(scope=SCOPE,status='NOT_OBSERVED',event=None,event_id=None,historical_only=True,automatically_replayed=False)
        return dict(**result,current=_view(store,c,p,parent,root,case,local))


@er.bounded
def cancel(store,token,id,key,data):
    fp=digest(prep.canonical(dict(preparation_id=str(id),**frontier_request(data))))
    with store.connect() as c:
        p,parent=cc._context(store,c,token,id,True)
        c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('case-local-key:'+p['id']+':'+key,))
        root,case,local=cc._locks(c,parent,True)
        old=cc._original(c,p,parent,key,scope=SCOPE,action=ACTION)
        if old:
            if old['fingerprint']!=fp:raise Conflict('cancellation key fingerprint mismatch')
            cc._committed_state(case,local,old)
            return cc._result(old)
        check_fence(c,parent,data)
        source,issues=_source(store,c,parent,root,case,local)
        if issues:raise Conflict(';'.join(issues))
        if (data.case_id!=parent['case_id'] or data.expected_preparation_revision!=parent['revision']
            or data.expected_lifecycle_revision!=(local['revision'] if local else 0)
            or data.expected_source_sha256!=digest(prep.canonical(source))):
            raise Conflict('exact accepted manual Case and material source version required; refresh and explicitly confirm')
        return cc._commit(c,p,parent,local,key,data,fp,source,scope=SCOPE,action=ACTION)
