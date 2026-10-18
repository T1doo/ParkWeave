"""Minimal synthetic platform notices; current Case authority is never cached."""
from uuid import UUID
from typing import Literal
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from contextlib import contextmanager
import re
import secrets
from pydantic import BaseModel,ConfigDict,Field
from . import service_dispatches as sd, preparation as prep
from .executor_receipts import bounded
from .store import Denied,Conflict
from psycopg.errors import LockNotAvailable

SCOPE='SYNTHETIC_INTERNAL_DISPATCH_NOTICES_ONLY'
SCAN_LIMIT=20
LIST_SCAN_LIMIT=100
LIST_RETURN_LIMIT=20
NAVIGATION_CAPACITY=256
NAVIGATION_TTL_SECONDS=300
_navigation_creation_lock=Lock()


@dataclass(frozen=True)
class _Position:
    binding: tuple
    high_water: tuple
    after: tuple
    expires: float


class Navigation:
    """Process-local bounded positions, never cached permission or notice data.

    A handle can be replayed, but every replay rechecks current authority. Child
    positions retain the original expiry/high-water; restart or eviction requires
    refresh. Only opaque randomness crosses the API, never filtered row keys.
    """
    def __init__(self, *, capacity=NAVIGATION_CAPACITY, ttl=NAVIGATION_TTL_SECONDS, clock=monotonic):
        if type(capacity) is not int or not 1 <= capacity <= NAVIGATION_CAPACITY:
            raise ValueError('bounded navigation capacity required')
        if type(ttl) is not int or not 1 <= ttl <= NAVIGATION_TTL_SECONDS:
            raise ValueError('bounded navigation expiry required')
        self._capacity,self._ttl,self._clock=capacity,ttl,clock
        self._positions=OrderedDict()
        self._lock=Lock()

    def _purge(self, now):
        for key in tuple(self._positions):
            if self._positions[key].expires <= now:
                del self._positions[key]

    def resolve(self, handle, binding):
        if type(handle) is not str or re.fullmatch(r'[A-Za-z0-9_-]{43}',handle) is None:
            raise Denied('notice navigation unavailable; refresh required')
        with self._lock:
            now=self._clock();self._purge(now)
            position=self._positions.get(handle)
            if position is None or position.binding != binding:
                raise Denied('notice navigation unavailable; refresh required')
            return position

    def issue(self, binding, high_water, after, expires):
        with self._lock:
            now=self._clock();self._purge(now)
            if now >= expires:
                raise Denied('notice navigation unavailable; refresh required')
            while len(self._positions) >= self._capacity:
                self._positions.popitem(last=False)
            for _ in range(8):
                handle=secrets.token_urlsafe(32)
                if handle not in self._positions:break
            else:
                raise Conflict('notice navigation busy; refresh required')
            self._positions[handle]=_Position(binding,high_water,after,expires)
            return handle

class Command(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    action: Literal['OPEN','MARK_READ']
    expected_revision: int=Field(ge=1,le=64)


def _source(c,event_id):
    row=c.execute('''SELECT e.id event_id,e.dispatch_id,e.offer_id,e.actor_id,e.revision,e.action,e.created_at,
       d.preparation_id,o.executor_id FROM service_dispatch_events e
       JOIN service_dispatches d ON d.id=e.dispatch_id JOIN service_dispatch_offers o ON o.id=e.offer_id
       WHERE e.id=%s''',(event_id,)).fetchone()
    if not row:raise Denied('notice unavailable')
    return row


def enqueue(c,event_id):
    source=_source(c,event_id)
    parent=c.execute('SELECT * FROM preparations WHERE id=%s',(source['preparation_id'],)).fetchone()
    if parent['namespace']!='SYNTHETIC':raise Conflict('synthetic notices only')
    recipient=source['executor_id'] if source['action'] in ('OFFER','REOFFER','WITHDRAW') else parent['reviewer_id']
    for id in sorted({parent['owner_id'],recipient}-{source['actor_id']}):
        c.execute('INSERT INTO dispatch_notice_outbox(event_id,recipient_id) VALUES(%s,%s)',(event_id,id))


def _authority(store,c,p,source,case_step_assignments=None):
    if not p or not p['active'] or p['role'] not in ('enterprise_operator','park_specialist','service_executor'):
        raise Denied('notice recipient unavailable')
    store.check_capability(c,p,'READ')
    if case_step_assignments is not None:
        return case_step_assignments.notice_authority(c,p,source)
    parent=sd._parent(store,c,p,source['preparation_id'])
    root=sd._root(c,parent)
    if parent['namespace']!='SYNTHETIC' or not root or root['id']!=source['dispatch_id']:
        raise Denied('notice source unavailable')
    # Assignment alone never exposes another executor's offer notification.
    expected=source['executor_id'] if p['role']=='service_executor' else parent['owner_id'] if p['role']=='enterprise_operator' else parent['reviewer_id']
    if p['id']!=expected:raise Denied('notice participant scope required')
    return parent,root


@contextmanager
def _connection(store,scope,token=None):
    if scope is None:
        with store.connect() as c:yield c
    else:
        from .case_step_assignments import IsolatedCaseStepAssignments
        if type(scope) is not IsolatedCaseStepAssignments:raise Denied('exact explicit CaseStep dependency required')
        with scope._connection(store) as c:
            if token is not None:scope._checks[c].append(lambda:_recipient(store,c,token))
            yield c


def _queue_matches(c,source,scope):
    from .case_step_assignments import has_marker
    marked=has_marker(c,source['preparation_id'])
    # A marker is a queue discriminator, never a permission. Unknown/damaged
    # markers stay quarantined; no ordinary consumer may suppress their intent.
    return not marked if scope is None else marked and scope.owns_notice(c,source)


def _pending(c,scope,cursor):
    from .case_step_assignments import MARKER,CONTRACT
    source='SELECT 1 FROM service_dispatch_events e JOIN service_dispatch_events m ON m.dispatch_id=e.dispatch_id WHERE e.id=q.event_id AND m.payload ? %s'
    parameters=[MARKER]
    if scope is None:
        lane='NOT EXISTS ('+source+')'
    else:
        lane='EXISTS ('+source+" AND m.action='OFFER' AND m.payload->%s->'binding'->>'contract'=%s AND m.payload->%s->'binding'->>'contract_id'=%s)"
        parameters.extend([MARKER,CONTRACT,MARKER,scope.contract_id])
    # Route before LIMIT so another lane cannot hide this worker's pending
    # work on every cold --once invocation. This SQL grants no access.
    return c.execute("SELECT q.event_id,q.recipient_id FROM dispatch_notice_outbox q WHERE q.state='PENDING' AND "+lane+
        ' AND (%s::uuid IS NULL OR (q.event_id,q.recipient_id)>(%s::uuid,%s)) ORDER BY q.event_id,q.recipient_id LIMIT %s',
        (*parameters,cursor[0] if cursor else None,cursor[0] if cursor else None,cursor[1] if cursor else '',SCAN_LIMIT)).fetchall()


@bounded
def consume(store,*,crash_before_ack=False,case_step_assignments=None):
    """Bounded progress, not a certificate of queue exhaustion.

    Unknown scoped proof stays pending; only proven own revoked scope suppresses.
    """
    with _connection(store,case_step_assignments) as c:
        c.execute("SET LOCAL lock_timeout='3s'")
        # This cursor only rotates a bounded scan; PG remains the durable queue.
        # Restarting or racing cursors can repeat scans, never lose pending intent.
        cursor=getattr(store,'_notice_scan_cursor',None)
        candidates=_pending(c,case_step_assignments,cursor)
        if not candidates:
            store._notice_scan_cursor=None
            candidates=_pending(c,case_step_assignments,None)
        for candidate in candidates:
            checkpoint=len(case_step_assignments._checks[c]) if case_step_assignments is not None else None
            store._notice_scan_cursor=(candidate['event_id'],candidate['recipient_id'])
            try:
                with c.transaction():
                    # A busy source or identity must not starve unrelated Cases.
                    # Roll back just this candidate, retaining all pending intent.
                    c.execute("SET LOCAL lock_timeout='50ms'")
                    store.lock_principal(c,candidate['recipient_id'])
                    p=c.execute('SELECT * FROM principals WHERE id=%s',(candidate['recipient_id'],)).fetchone()
                    source=_source(c,candidate['event_id'])
                    if not _queue_matches(c,source,case_step_assignments):continue
                    if case_step_assignments is not None:
                        try:case_step_assignments.notice_source(c,source)
                        except Denied:continue
                    try:
                        parent,_=_authority(store,c,p,source,case_step_assignments);allowed=not sd.prep.case_write_blocked(c,parent)
                    except Denied:allowed=False
                    row=c.execute("SELECT * FROM dispatch_notice_outbox WHERE event_id=%s AND recipient_id=%s AND state='PENDING' FOR UPDATE SKIP LOCKED",(candidate['event_id'],candidate['recipient_id'])).fetchone()
                    if not row:
                        if checkpoint is not None:del case_step_assignments._checks[c][checkpoint:]
                        continue
                    source=_source(c,candidate['event_id'])
                    if not _queue_matches(c,source,case_step_assignments):
                        if checkpoint is not None:del case_step_assignments._checks[c][checkpoint:]
                        continue
                    if case_step_assignments is not None:
                        try:case_step_assignments.notice_source(c,source)
                        except Denied:
                            del case_step_assignments._checks[c][checkpoint:]
                            continue
                        case_step_assignments._checks[c].append(lambda source=source:case_step_assignments.notice_source(c,source))
                    if allowed:_authority(store,c,p,source,case_step_assignments)
                    if allowed:
                        c.execute('INSERT INTO dispatch_notices(event_id,recipient_id) VALUES(%s,%s) ON CONFLICT DO NOTHING',(row['event_id'],row['recipient_id']))
                    if crash_before_ack:
                        if store.mode!='FAULT_INJECTION':raise Conflict('explicit synthetic fault mode required')
                        # Real process termination aborts the same open PG transaction.
                        import os
                        os._exit(75)
                    c.execute('UPDATE dispatch_notice_outbox SET state=%s,consumed_at=clock_timestamp() WHERE event_id=%s AND recipient_id=%s',('DELIVERED' if allowed else 'SUPPRESSED',row['event_id'],row['recipient_id']))
                    return True
            except LockNotAvailable:
                if checkpoint is not None:del case_step_assignments._checks[c][checkpoint:]
                continue
        return False


def _item(source,row,root,*,cancelled=False,reconciling=False):
    return dict(event_id=source['event_id'],preparation_id=source['preparation_id'],dispatch_id=source['dispatch_id'],
                revision=source['revision'],action=source['action'],created_at=source['created_at'],
                delivered_at=row['delivered_at'],open_requested_at=row['seen_at'],read_at=row['read_at'],
                case_cancelled=cancelled,case_reconciling=reconciling,case_write_blocked=cancelled or reconciling,actionable=not (cancelled or reconciling) and source['offer_id']==root['current_offer_id'] and source['action'] in ('OFFER','REOFFER'),
                historical=cancelled or reconciling or source['revision']!=root['revision'] or source['offer_id']!=root['current_offer_id'])


def _project(c,p,parent,root,source,row,scope):
    item=_item(source,row,root,cancelled=prep.case_cancelled(c,parent),reconciling=prep.case_state(c,parent)=='RECONCILING')
    return item if scope is None else scope.notice_item(c,p,parent,root,source,item)


def _recipient(store,c,token):
    p=sd._auth(store,c,token)
    if p['role']!='service_executor':prep.grant(store,c,p,'PREPARE' if p['role']=='enterprise_operator' else 'REVIEW_ASSIGNED')
    return p


@bounded
def list_items(store,token,*,cursor=None,navigation=None,case_step_assignments=None):
    # API owns one cache per app instance. Direct callers keep positions only
    # on their Store instance. Neither cache is a persistent authority/registry.
    if navigation is None:
        with _navigation_creation_lock:
            navigation=getattr(store,'_notice_navigation',None)
            if navigation is None:
                navigation=Navigation();store._notice_navigation=navigation
    with _connection(store,case_step_assignments,token) as c:
        p=_recipient(store,c,token)
        binding=(SCOPE,p['id'],p['park_id'],p['org_id'],p['role'],p['token_hash'])
        if case_step_assignments is not None:binding+=(case_step_assignments.contract_id,)
        if cursor is None:
            expires=navigation._clock()+navigation._ttl
            rows=c.execute('SELECT * FROM dispatch_notices WHERE recipient_id=%s ORDER BY delivered_at DESC,event_id DESC LIMIT %s',
                           (p['id'],LIST_SCAN_LIMIT)).fetchall()
            high_water=(rows[0]['delivered_at'],rows[0]['event_id']) if rows else None
        else:
            position=navigation.resolve(cursor,binding)
            expires=position.expires;high_water=position.high_water
            rows=c.execute('''SELECT * FROM dispatch_notices WHERE recipient_id=%s
                AND (delivered_at,event_id)<= (%s,%s) AND (delivered_at,event_id)< (%s,%s)
                ORDER BY delivered_at DESC,event_id DESC LIMIT %s''',
                (p['id'],*high_water,*position.after,LIST_SCAN_LIMIT)).fetchall()
        items=[]
        examined=0
        for row in rows:
            examined+=1
            try:
                source=_source(c,row['event_id'])
                parent,root=_authority(store,c,p,source,case_step_assignments)
            except Denied:continue
            items.append(_project(c,p,parent,root,source,row,case_step_assignments))
            if len(items)==LIST_RETURN_LIMIT:break
        # Reaching either bound means "continue scanning", not a disclosed total
        # or a guarantee that the next page contains authorized notices. Advance
        # past *examined* rows only, including denied ones; never skip fetched rows.
        next_cursor=None
        if navigation._clock() >= expires:
            raise Denied('notice navigation unavailable; refresh required')
        if examined and (examined==LIST_SCAN_LIMIT or len(items)==LIST_RETURN_LIMIT):
            last=rows[examined-1]
            next_cursor=navigation.issue(binding,high_water,(last['delivered_at'],last['event_id']),expires)
        return dict(scope=SCOPE,items=items,check_limit=LIST_SCAN_LIMIT,page_limit=LIST_RETURN_LIMIT,
                    next_cursor=next_cursor,external_send=False,case_goal_completed=False)


def _get(store,c,token,id,scope=None):
    p=_recipient(store,c,token);source=_source(c,id);parent,root=_authority(store,c,p,source,scope)
    row=c.execute('SELECT * FROM dispatch_notices WHERE event_id=%s AND recipient_id=%s',(id,p['id'])).fetchone()
    if not row:raise Denied('notice unavailable')
    return p,source,root,row,parent


@bounded
def read(store,token,id,*,case_step_assignments=None):
    with _connection(store,case_step_assignments,token) as c:
        p,source,root,row,parent=_get(store,c,token,id,case_step_assignments)
        return dict(scope=SCOPE,notice=_project(c,p,parent,root,source,row,case_step_assignments),external_send=False,case_goal_completed=False)


@bounded
def command(store,token,id,data,*,case_step_assignments=None):
    with _connection(store,case_step_assignments,token) as c:
        p,source,root,row,parent=_get(store,c,token,id,case_step_assignments)
        if data.expected_revision!=source['revision']:raise Conflict('notice source revision changed')
        row=c.execute('SELECT * FROM dispatch_notices WHERE event_id=%s AND recipient_id=%s FOR UPDATE',(id,p['id'])).fetchone()
        if data.action=='OPEN':
            row=c.execute('UPDATE dispatch_notices SET seen_at=coalesce(seen_at,clock_timestamp()) WHERE event_id=%s AND recipient_id=%s RETURNING *',(id,p['id'])).fetchone()
        else:
            if row['seen_at'] is None:raise Conflict('request to open notice required before marking read')
            row=c.execute('UPDATE dispatch_notices SET read_at=coalesce(read_at,clock_timestamp()) WHERE event_id=%s AND recipient_id=%s RETURNING *',(id,p['id'])).fetchone()
        return dict(scope=SCOPE,notice=_project(c,p,parent,root,source,row,case_step_assignments),external_send=False,case_goal_completed=False)
