"""Internal synthetic offers; never grants or external fulfillment."""
from typing import Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field
from psycopg.types.json import Jsonb
from . import preparation as prep, executor_receipts as receipts
from .store import Denied, Conflict, digest

SCOPE = 'SYNTHETIC_INTERNAL_DISPATCH_ONLY'


class Offer(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)
    expected_preparation_revision: int = Field(ge=1)
    expected_dispatch_revision: int = Field(ge=0, le=64)
    executor_id: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=1000)
    recovery_receipt_step_id: UUID | None = Field(default=None, strict=False)


class Command(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)
    action: Literal['ACCEPT', 'DECLINE', 'WITHDRAW']
    expected_revision: int = Field(ge=1, le=64)
    reason: str = Field(min_length=1, max_length=1000)


def _auth(store, c, token):
    c.execute("SET LOCAL lock_timeout='3s'")
    p = store.auth(c, token, lock=True)
    if p['role'] not in ('enterprise_operator', 'park_specialist', 'service_executor'):
        raise Denied('internal dispatch role required')
    store.check_capability(c, p, 'READ')
    return p


def _parent(store, c, p, id, write=False):
    # Reviewers use their existing preparation assignment, not Run assignment.
    if p['role'] != 'service_executor':
        return prep.scoped(store, c, p, id, write=write)
    row = c.execute('SELECT * FROM preparations WHERE id=%s AND park_id=%s AND org_id=%s ' +
                    ('FOR UPDATE' if write else 'FOR SHARE'), (id, p['park_id'], p['org_id'])).fetchone()
    if not row: raise Denied('dispatch unavailable')
    store.scoped_run(c, p, row['run_id'])
    if not c.execute('SELECT 1 FROM service_dispatch_offers o JOIN service_dispatches d ON d.id=o.dispatch_id WHERE d.preparation_id=%s AND o.executor_id=%s', (id, p['id'])).fetchone():
        raise Denied('own offered dispatch required')
    return row


def _root(c, parent, write=False):
    return c.execute('SELECT * FROM service_dispatches WHERE preparation_id=%s ' +
                     ('FOR UPDATE' if write else 'FOR SHARE'), (parent['id'],)).fetchone()


def _own_offer(c, p, root):
    if p['role'] != 'service_executor':
        return c.execute('SELECT * FROM service_dispatch_offers WHERE id=%s', (root['current_offer_id'],)).fetchone()
    return c.execute('SELECT o.* FROM service_dispatch_offers o JOIN service_dispatch_events e ON e.offer_id=o.id WHERE o.dispatch_id=%s AND o.executor_id=%s ORDER BY e.revision DESC LIMIT 1', (root['id'], p['id'])).fetchone()


def _fresh(parent, offer,c=None,store=None):
    return parent['state'] == 'LOCAL_CONFIRMED' and parent['revision'] == offer['preparation_revision'] and parent['review_sha256'] == offer['preparation_sha256'] and (c is None or receipts.material_current(c,parent,store))


def _latest_accepted(c,root):
    row=c.execute("""SELECT o.*,e.revision AS acceptance_revision,e.actor_id AS acceptance_actor,
      e.payload AS acceptance_payload FROM service_dispatch_offers o JOIN service_dispatch_events e
      ON e.offer_id=o.id AND e.dispatch_id=o.dispatch_id AND e.action='ACCEPT'
      WHERE o.dispatch_id=%s AND o.state='ACCEPTED' ORDER BY e.revision DESC LIMIT 1""",(root['id'],)).fetchone()
    if not row:return None
    expected=dict(dispatch_id=str(root['id']),offer_id=str(row['id']),receipt_step_id=str(row['receipt_step_id']),
                  revision=row['acceptance_revision'],action='ACCEPT',state='ACCEPTED',
                  actor_id=row['executor_id'],executor_id=row['executor_id'])
    if row['acceptance_actor']!=row['executor_id'] or row['acceptance_revision']>root['revision'] or any(row['acceptance_payload'].get(k)!=v for k,v in expected.items()):return None
    return row


def _recovery(c,parent,root,store=None):
    """Latest actual acceptance is the immutable predecessor of a newer preparation."""
    if not root or not receipts.material_current(c,parent,store):return None
    current=c.execute('SELECT state FROM service_dispatch_offers WHERE id=%s',(root['current_offer_id'],)).fetchone()
    if not current or current['state'] not in ('ACCEPTED','DECLINED','WITHDRAWN'):return None
    accepted=_latest_accepted(c,root)
    if not accepted or accepted['preparation_revision']>=parent['revision']:return None
    step=c.execute('SELECT * FROM service_receipt_steps WHERE id=%s AND preparation_id=%s',
                   (accepted['receipt_step_id'],parent['id'])).fetchone()
    if not step or step['executor_id']!=accepted['executor_id'] or step['preparation_revision']!=accepted['preparation_revision'] or step['preparation_sha256']!=accepted['preparation_sha256']:return None
    if c.execute('SELECT 1 FROM service_receipt_steps WHERE preparation_id=%s AND preparation_revision=%s',(parent['id'],parent['revision'])).fetchone():return None
    return accepted


def _recovery_flags(c,p,parent,root,store=None):
    predecessor=_recovery(c,parent,root,store)
    return dict(can_reoffer=bool(predecessor and p['role']=='park_specialist' and root['revision']<63),
                reoffer_kind='NEW_MATERIAL_ACCEPTANCE_REQUIRED' if predecessor else None,
                recovery_receipt_step_id=predecessor['receipt_step_id'] if predecessor else None)


def _party(store, c, parent, id, capability):
    store.lock_principal(c, id)
    p = c.execute('SELECT * FROM principals WHERE id=%s AND active AND park_id=%s AND org_id=%s', (id, parent['park_id'], parent['org_id'])).fetchone()
    if not p: raise Denied('current preparation participant required')
    prep.grant(store, c, p, capability)
    if capability == 'PREPARE': store.check_capability(c, p, 'EXECUTE')
    return p


def _key(c, p, key):
    c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('service-dispatch-key:' + p['id'] + ':' + key,))


def _replay(c, p, key, fp, root):
    old = c.execute('SELECT * FROM service_dispatch_events WHERE actor_id=%s AND request_key=%s', (p['id'], key)).fetchone()
    if old:
        if old['fingerprint'] != fp or not root or old['dispatch_id'] != root['id']:
            raise Conflict('dispatch request key fingerprint mismatch')
        return old['payload']


def _event(c, p, root, offer, key, fp, action, reason, **extra):
    payload = dict(dispatch_id=str(root['id']), offer_id=str(offer['id']), revision=root['revision'],
                   action=action, state=offer['state'], actor_id=p['id'], executor_id=offer['executor_id'],
                   reason=reason, receipt_step_id=str(offer['receipt_step_id']) if offer['receipt_step_id'] else None, **extra)
    event_id=uuid4()
    c.execute('INSERT INTO service_dispatch_events(id,dispatch_id,offer_id,actor_id,request_key,fingerprint,revision,action,payload) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',
              (event_id, root['id'], offer['id'], p['id'], key, fp, root['revision'], action, Jsonb(payload)))
    from .controlled_plans import invalidate
    invalidate(c,c.execute('SELECT preparation_id FROM service_dispatches WHERE id=%s',(root['id'],)).fetchone()['preparation_id'],3)
    from .dispatch_notices import enqueue
    enqueue(c,event_id)
    return payload


def _view(c, p, parent, root, event=None,store=None):
    result = dict(scope=SCOPE, role=p['role'], preparation_id=parent['id'], goal=parent['goal'],
                  service_id=parent['service_id'], service_version=parent['service_version'],
                  preparation_revision=parent['revision'], dispatch_id=root['id'] if root else None,
                  revision=root['revision'] if root else 0, current_offer=None, offers=[], history=[], event=event,
                  dependency='CURRENT', receipt_step_id=None, is_current_offer=False,
                  current_receipt_step_id=None,can_reoffer=False,reoffer_kind=None,recovery_receipt_step_id=None,
                  qualification='NOT_EVALUATED', external_acceptance='NOT_SUBMITTED',
                  offline_fulfillment='NO_EVIDENCE', case_goal_completed=False)
    if not root: return result
    offer = _own_offer(c, p, root)
    if not offer: raise Denied('own offered dispatch required')
    executor = p['role'] == 'service_executor'
    clause = ' AND o.executor_id=%s' if executor else ''
    params = (root['id'], p['id']) if executor else (root['id'],)
    result.update(current_offer=offer, is_current_offer=offer['id'] == root['current_offer_id'],
                  dependency='CURRENT' if _fresh(parent, offer,c,store) else 'DEPENDENCY_CHANGED',
                  receipt_step_id=offer['receipt_step_id'],
                  offers=c.execute('SELECT o.* FROM service_dispatch_offers o WHERE o.dispatch_id=%s' + clause + ' ORDER BY o.created_at,o.id', params).fetchall(),
                  history=c.execute('SELECT e.revision,e.action,e.payload,e.created_at FROM service_dispatch_events e JOIN service_dispatch_offers o ON o.id=e.offer_id WHERE e.dispatch_id=%s' + clause + ' ORDER BY e.revision', params).fetchall())
    # Executor projection continues to expose only its own offer lineage.
    if offer['id']==root['current_offer_id']:
        result.update(current_receipt_step_id=offer['receipt_step_id'] if offer['state']=='ACCEPTED' else None,
                      **_recovery_flags(c,p,parent,root,store))
    return result


@receipts.bounded
def catalog(store, token, id):
    with store.connect() as c:
        p = _auth(store, c, token)
        if p['role'] != 'park_specialist': raise Denied('assigned preparation reviewer required')
        parent = _parent(store, c, p, id)
        root = _root(c, parent)
        existing = bool(c.execute('SELECT 1 FROM service_receipt_steps WHERE preparation_id=%s', (id,)).fetchone())
        rows = store.assigned_executors(c,parent['run_id'],p['park_id'],p['org_id'])
        current = _own_offer(c, p, root) if root else None
        recovery=_recovery(c,parent,root,store)
        limited = bool(root and root['revision'] >= 63)
        ready = receipts.material_current(c,parent,store) and not limited and ((not existing and (not current or current['state'] in ('DECLINED', 'WITHDRAWN'))) or bool(recovery))
        if recovery:rows=[r for r in rows if r['id']==recovery['executor_id']]
        return dict(scope=SCOPE, preparation_revision=parent['revision'], dispatch_revision=root['revision'] if root else 0,
                    ready=ready and bool(rows), executors=rows, has_receipt_step=existing, history_limit_reached=limited,
                    **_recovery_flags(c,p,parent,root,store))


@receipts.bounded
def read_preparation(store, token, id):
    with store.connect() as c:
        p = _auth(store, c, token); parent = _parent(store, c, p, id)
        return _view(c, p, parent, _root(c, parent),store=store)


@receipts.bounded
def read(store, token, id):
    with store.connect() as c:
        p = _auth(store, c, token)
        root = c.execute('SELECT preparation_id FROM service_dispatches WHERE id=%s', (id,)).fetchone()
        if not root: raise Denied('dispatch unavailable')
        parent = _parent(store, c, p, root['preparation_id'])
        return _view(c, p, parent, _root(c, parent),store=store)


@receipts.bounded
def offer(store, token, id, key, data):
    body=data.model_dump(mode='json')
    if data.recovery_receipt_step_id is None:body.pop('recovery_receipt_step_id')
    fp = digest(prep.canonical(dict(preparation_id=str(id), **body)))
    with store.connect() as c:
        p = _auth(store, c, token)
        if p['role'] != 'park_specialist': raise Denied('assigned preparation reviewer required')
        _key(c, p, key); parent = _parent(store, c, p, id, write=True); root = _root(c, parent, write=True)
        receipts._executor(store, c, data.executor_id, parent['run_id'])
        _party(store, c, parent, parent['owner_id'], 'PREPARE')
        old = _replay(c, p, key, fp, root)
        if old: return _view(c, p, parent, root, old,store)
        from .controlled_plans import gate
        gate(store,c,parent,2)
        if not receipts.material_current(c,parent,store) or parent['revision'] != data.expected_preparation_revision:
            raise Conflict('current locally confirmed preparation required')
        if (root['revision'] if root else 0) != data.expected_dispatch_revision:
            raise Conflict('stale dispatch revision; refresh required')
        existing=bool(c.execute('SELECT 1 FROM service_receipt_steps WHERE preparation_id=%s', (id,)).fetchone())
        recovery=_recovery(c,parent,root,store)
        if existing:
            if not recovery or data.recovery_receipt_step_id!=recovery['receipt_step_id']:
                raise Conflict('new preparation acceptance requires the exact historical receipt generation')
            if data.executor_id!=recovery['executor_id']:raise Conflict('new material acceptance must retain the original executor')
        elif data.recovery_receipt_step_id is not None:raise Conflict('no accepted receipt generation to recover')
        if root:
            current = _own_offer(c, p, root)
            if current['state'] not in ('DECLINED', 'WITHDRAWN') and not recovery: raise Conflict('resolve current offer before reoffering')
            if root['revision'] >= 63: raise Conflict('dispatch history limit reached')
        oid = uuid4(); action = 'REOFFER' if root else 'OFFER'
        if root:
            root = c.execute('UPDATE service_dispatches SET revision=revision+1,current_offer_id=%s WHERE id=%s RETURNING *', (oid, root['id'])).fetchone()
        else:
            root = c.execute('INSERT INTO service_dispatches(id,preparation_id,revision,current_offer_id) VALUES(%s,%s,1,%s) RETURNING *', (uuid4(), id, oid)).fetchone()
        offered = c.execute("INSERT INTO service_dispatch_offers(id,dispatch_id,executor_id,preparation_revision,preparation_sha256,reason,state) VALUES(%s,%s,%s,%s,%s,%s,'OFFERED') RETURNING *", (oid, root['id'], data.executor_id, parent['revision'], parent['review_sha256'], data.reason)).fetchone()
        lineage=dict(predecessor_offer_id=str(recovery['id']),predecessor_receipt_step_id=str(recovery['receipt_step_id']),
                     previous_preparation_revision=recovery['preparation_revision'],previous_preparation_sha256=recovery['preparation_sha256'],
                     accepted_preparation_revision=parent['revision'],accepted_preparation_sha256=parent['review_sha256']) if recovery else {}
        return _view(c, p, parent, root, _event(c, p, root, offered, key, fp, action, data.reason,**lineage),store)


@receipts.bounded
def command(store, token, id, key, data):
    fp = digest(prep.canonical(dict(dispatch_id=str(id), **data.model_dump(mode='json'))))
    with store.connect() as c:
        p = _auth(store, c, token)
        if p['role'] != ('park_specialist' if data.action == 'WITHDRAW' else 'service_executor'):
            raise Denied('own dispatch decision role required')
        _key(c, p, key)
        base = c.execute('SELECT preparation_id FROM service_dispatches WHERE id=%s', (id,)).fetchone()
        if not base: raise Denied('dispatch unavailable')
        parent = _parent(store, c, p, base['preparation_id'], write=True); root = _root(c, parent, write=True)
        own = _own_offer(c, p, root)
        if data.action == 'ACCEPT':
            _party(store, c, parent, parent['reviewer_id'], 'REVIEW_ASSIGNED')
            _party(store, c, parent, parent['owner_id'], 'PREPARE')
        old = _replay(c, p, key, fp, root)
        if old: return _view(c, p, parent, root, old,store)
        if own['id'] != root['current_offer_id'] or own['state'] != 'OFFERED':
            raise Conflict('current offered dispatch required')
        if root['revision'] != data.expected_revision: raise Conflict('stale dispatch revision; refresh required')
        if root['revision'] >= 64: raise Conflict('dispatch history limit reached')
        # Decline/withdraw may resolve stale offers without reviving revoked grants.
        step_id = None
        lineage = {}
        if data.action == 'ACCEPT':
            from .controlled_plans import gate
            gate(store,c,parent,2)
            if not _fresh(parent, own,c,store): raise Conflict('dispatch preparation dependency changed')
            existing=c.execute('SELECT 1 FROM service_receipt_steps WHERE preparation_id=%s', (parent['id'],)).fetchone()
            offered_event=c.execute("SELECT payload FROM service_dispatch_events WHERE offer_id=%s AND action IN ('OFFER','REOFFER') ORDER BY revision LIMIT 1",(own['id'],)).fetchone()
            predecessor_id=(offered_event['payload'].get('predecessor_receipt_step_id') if offered_event else None)
            if existing:
                predecessor=c.execute('SELECT * FROM service_receipt_steps WHERE id=%s AND preparation_id=%s',(predecessor_id,parent['id'])).fetchone() if predecessor_id else None
                payload=offered_event['payload'] if offered_event else {}
                predecessor_offer=_latest_accepted(c,root)
                expected=dict(predecessor_offer_id=str(predecessor_offer['id']),
                              predecessor_receipt_step_id=str(predecessor_offer['receipt_step_id']),
                              previous_preparation_revision=predecessor_offer['preparation_revision'],
                              previous_preparation_sha256=predecessor_offer['preparation_sha256'],
                              accepted_preparation_revision=own['preparation_revision'],
                              accepted_preparation_sha256=own['preparation_sha256']) if predecessor_offer else {}
                if not predecessor or not predecessor_offer or not expected or any(payload.get(k)!=v for k,v in expected.items()) or predecessor_offer['executor_id']!=p['id'] or predecessor['executor_id']!=p['id'] or predecessor['preparation_revision']!=predecessor_offer['preparation_revision'] or predecessor['preparation_sha256']!=predecessor_offer['preparation_sha256'] or predecessor['preparation_revision']>=parent['revision']:
                    raise Conflict('preparation already has receipt step; explicit new material offer required')
                if c.execute('SELECT 1 FROM service_receipt_steps WHERE preparation_id=%s AND preparation_revision=%s',(parent['id'],parent['revision'])).fetchone():
                    raise Conflict('current preparation already has receipt generation')
                lineage=expected
            step = receipts._insert_step(c, parent, p['id']); step_id = step['id']
            receipts._event(c, p, step, 'dispatch-accept:' + str(own['id']), fp, 'CREATE', dispatch_id=str(root['id']), offer_id=str(own['id']), reason=data.reason,**lineage)
        states = {'ACCEPT':'ACCEPTED', 'DECLINE':'DECLINED', 'WITHDRAW':'WITHDRAWN'}
        own = c.execute('UPDATE service_dispatch_offers SET state=%s,receipt_step_id=%s WHERE id=%s RETURNING *', (states[data.action], step_id, own['id'])).fetchone()
        root = c.execute('UPDATE service_dispatches SET revision=revision+1 WHERE id=%s RETURNING *', (id,)).fetchone()
        return _view(c, p, parent, root, _event(c, p, root, own, key, fp, data.action, data.reason,**lineage),store)


@receipts.bounded
def list_items(store, token):
    with store.connect() as c:
        p = _auth(store, c, token)
        if p['role'] != 'service_executor': prep.grant(store, c, p, 'PREPARE' if p['role']=='enterprise_operator' else 'REVIEW_ASSIGNED')
        column = 'owner_id' if p['role']=='enterprise_operator' else 'reviewer_id'
        condition = 'p.' + column + '=%s' if p['role']!='service_executor' else "EXISTS(SELECT 1 FROM service_dispatch_offers o WHERE o.dispatch_id=d.id AND o.executor_id=%s) AND EXISTS(SELECT 1 FROM run_assignments a WHERE a.run_id=p.run_id AND a.principal_id=%s AND a.park_id=p.park_id AND a.org_id=p.org_id AND a.active)"
        params = (p['park_id'],p['org_id'],p['id'],p['id']) if p['role']=='service_executor' else (p['park_id'],p['org_id'],p['id'])
        rows = c.execute('SELECT d.id,p.id preparation_id,p.goal,p.run_id FROM service_dispatches d JOIN preparations p ON p.id=d.preparation_id WHERE p.park_id=%s AND p.org_id=%s AND ' + condition + ' ORDER BY d.created_at DESC,d.id DESC LIMIT 101', params).fetchall()
        raw_more=len(rows)>100
        scanned=len(rows)
        if p['role']=='service_executor':
            rows=[r for r in rows if store.assignment_allowed(c,p,r['run_id'])]
        for row in rows:
            row.pop('run_id',None)
        return dict(scope=SCOPE, role=p['role'], items=rows[:100], has_older_records=raw_more, access_filtered=scanned-len(rows))
