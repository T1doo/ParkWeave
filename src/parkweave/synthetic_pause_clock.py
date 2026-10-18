"""Explicit, finite LOCAL_SYNTHETIC fixture capability; never a real SLA grant."""
from contextlib import contextmanager
from datetime import timedelta
import json
import os
from pathlib import Path
import sqlite3
from types import MappingProxyType

from pydantic import Field
from typing import Literal

from . import handling_deadline as hd, preparation as prep
from .store import Conflict, Denied

SCOPE = 'LOCAL_SYNTHETIC_PAUSE_CLOCK'
REASON = 'AWAITING_SYNTHETIC_INPUT'
SCHEMA = {
    'fixture_meta': 'CREATE TABLE fixture_meta(binding TEXT NOT NULL)',
    'fixture_events': 'CREATE TABLE fixture_events(preparation TEXT,revision INTEGER,actor TEXT,key TEXT,fp TEXT,payload TEXT,PRIMARY KEY(preparation,revision),UNIQUE(actor,key))',
    'fixture_no_update': "CREATE TRIGGER fixture_no_update BEFORE UPDATE ON fixture_events BEGIN SELECT RAISE(ABORT,'immutable fixture event'); END",
    'fixture_no_delete': "CREATE TRIGGER fixture_no_delete BEFORE DELETE ON fixture_events BEGIN SELECT RAISE(ABORT,'immutable fixture event'); END",
}


class Capability(hd.Contract):
    actor_id: hd.ID
    valid_from: str
    valid_until: str


class Command(hd.Contract):
    action: Literal['PAUSE', 'RESUME']
    reason: Literal['AWAITING_SYNTHETIC_INPUT']
    note: str = Field(min_length=1, max_length=500, pattern=r'\S')
    expected_revision: int = Field(ge=0, le=32)
    expected_definition_sha256: hd.SHA


class Event(hd.Contract):
    scope: Literal['LOCAL_SYNTHETIC_PAUSE_CLOCK']
    preparation_id: str
    actor_id: hd.ID
    action: Literal['PAUSE', 'RESUME']
    reason: Literal['AWAITING_SYNTHETIC_INPUT']
    note: str = Field(min_length=1, max_length=500, pattern=r'\S')
    revision: int = Field(ge=1, le=32)
    occurred_at: str
    request_key: str = Field(min_length=1, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')
    request_sha256: hd.SHA
    definition_sha256: hd.SHA
    binding_sha256: hd.SHA
    previous_sha256: hd.SHA | None
    formal_sla: bool
    legal_pause_decision: Literal['NOT_EVALUATED']
    sha256: hd.SHA


class IsolatedPauseClock:
    def __init__(self, store, registry, path, *, capabilities, enabled_for_isolated_tests=False):
        if (enabled_for_isolated_tests is not True or store.mode != 'LOCAL' or
                type(registry) is not hd.IsolatedDeadlineSources or
                getattr(store, '_isolated_deadline_sources', None) is not registry or
                not isinstance(capabilities, dict) or not 1 <= len(capabilities) <= 16 or
                getattr(store, '_synthetic_pause_clock', None) is not None):
            raise Denied('explicit original owned synthetic clock fixture required')
        self.store, self.registry = store, registry
        entries = {}
        with registry.owner.connect() as c:
            registry._owner_proof(c)
            now = c.execute('SELECT clock_timestamp() now').fetchone()['now']
            for id, raw in capabilities.items():
                entry = registry.entries.get(str(id))
                if entry is None or hd.digest(entry[0]) != entry[1]:
                    raise Denied('original bound deadline source required')
                source = json.loads(entry[0])
                cap = Capability.model_validate(raw)
                if cap.actor_id != source['binding']['reviewer_id']:
                    raise Denied('existing bound synthetic reviewer required')
                actor = c.execute('SELECT * FROM principals WHERE id=%s AND active', (cap.actor_id,)).fetchone()
                if not actor:
                    raise Denied('current existing reviewer required')
                prep.grant(registry.owner, c, actor, 'REVIEW_ASSIGNED')
                first, end = hd.instant(cap.valid_from), hd.instant(cap.valid_until)
                definition = source['definition']
                result = hd.calculate(definition, hd.instant(source['binding']['started_at']), now,
                    service_id=source['binding']['service_id'], service_version=source['binding']['service_version'],
                    org_id=source['binding']['org_id'])
                if (result['state'] != 'SYNTHETIC_CALCULATED' or
                        not hd.instant(definition['source']['valid_from']) <= first <= now < end <=
                        hd.instant(definition['source']['valid_until']) or end-first > timedelta(hours=24)):
                    raise Denied('current bounded synthetic pause capability required')
                entries[str(id)] = prep.canonical(dict(capability=cap.model_dump(), source_sha256=entry[1]))
        self.capabilities = MappingProxyType(entries)
        self.path = Path(path)
        if (not self.path.is_absolute() or self.path.parent.resolve() != self.path.parent or
                not self.path.name.endswith('.synthetic-pause.sqlite3')):
            raise Denied('fresh dedicated fixture journal path required')
        self.metadata = prep.canonical(dict(scope=SCOPE, pid=os.getpid(),
            proof_nonce=str(registry.proof.nonce), entries=entries))
        # Exclusive creation: never inspect/repair/overwrite an existing journal.
        fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        st = self.path.stat()
        self.identity = st.st_dev, st.st_ino
        with sqlite3.connect(self.path) as db:
            for sql in SCHEMA.values():
                db.execute(sql)
            db.execute('INSERT INTO fixture_meta VALUES(?)', (self.metadata,))
        registry._synthetic_pause_clock_ids = frozenset(entries) | getattr(registry, '_synthetic_pause_clock_ids', frozenset())
        store._synthetic_pause_clock = self

    @contextmanager
    def journal(self, write=False):
        st = self.path.lstat()
        if self.path.is_symlink() or (st.st_dev, st.st_ino) != self.identity:
            raise Conflict('fixture journal identity changed')
        db = sqlite3.connect(self.path.as_uri()+'?mode=rw', uri=True, timeout=3)
        db.row_factory = sqlite3.Row
        try:
            db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            objects = {r['name']: r['sql'] for r in db.execute("SELECT name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}
            if objects != SCHEMA or [r[0] for r in db.execute('SELECT binding FROM fixture_meta')] != [self.metadata]:
                raise Conflict('fixture journal contract changed')
            yield db
            db.commit()
        except sqlite3.Error as exc:
            db.rollback()
            raise Conflict('fixture journal unavailable; read original key') from exc
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def context(self, c, token, id, *, write=False):
        if getattr(self.store, '_synthetic_pause_clock', None) is not self:
            raise Denied('current exact fixture service required')
        self.registry._connection(c)
        if getattr(self.store, '_isolated_deadline_sources', None) is not self.registry:
            raise Denied('original clock source registry required')
        actor = self.store.auth(c, token, lock=True)
        parent = prep.scoped(self.store, c, actor, id, write=write)
        cap_bytes = self.capabilities.get(str(id))
        entry = self.registry.entries.get(str(id))
        if cap_bytes is None or entry is None or hd.digest(entry[0]) != entry[1]:
            raise Denied('explicit fixture clock scope required')
        cap = json.loads(cap_bytes)
        if cap['source_sha256'] != entry[1]:
            raise Conflict('fixture source changed')
        source = json.loads(entry[0])
        try:
            current = hd.binding(c, parent)
        except hd.Unknown as exc:
            raise Conflict('original clock binding unavailable') from exc
        if current != source['binding'] or parent['namespace'] != 'SYNTHETIC':
            raise Conflict('fixture clock binding changed')
        now = c.execute('SELECT clock_timestamp() now').fetchone()['now']
        if write:
            if actor['id'] != cap['capability']['actor_id'] or actor['role'] != 'park_specialist':
                raise Denied('explicit fixture reviewer capability required')
            if not hd.instant(cap['capability']['valid_from']) <= now < hd.instant(cap['capability']['valid_until']):
                raise Denied('synthetic pause capability not current')
            prep.case_write_guard(c, parent)
        return actor, parent, source, now

    def events(self, db, id, source):
        rows = db.execute('SELECT * FROM fixture_events WHERE preparation=? ORDER BY revision LIMIT 33', (str(id),)).fetchall()
        if len(rows) > 32:
            raise Conflict('bounded fixture journal exceeded')
        events, previous, instant = [], None, hd.instant(source['binding']['started_at'])
        cap = json.loads(self.capabilities[str(id)])
        try:
            for revision, row in enumerate(rows, 1):
                event = Event.model_validate_json(row['payload']).model_dump()
                sha = event.pop('sha256')
                when = hd.instant(event['occurred_at'])
                body = dict(action=event['action'], reason=event['reason'], note=event['note'],
                            expected_revision=revision-1, expected_definition_sha256=event['definition_sha256'])
                if (hd.fingerprint(event) != sha or event['previous_sha256'] != previous or
                        event['revision'] != revision or row['revision'] != revision or
                        event['actor_id'] != cap['capability']['actor_id'] or row['actor'] != event['actor_id'] or
                        event['preparation_id'] != str(id) or event['scope'] != SCOPE or
                        event['definition_sha256'] != hd.fingerprint(source['definition']) or
                        event['binding_sha256'] != hd.fingerprint(source['binding']) or
                        event['reason'] != REASON or event['action'] != ('PAUSE' if revision % 2 else 'RESUME') or
                        event['request_key'] != row['key'] or event['request_sha256'] != row['fp'] or
                        event['request_sha256'] != hd.fingerprint(dict(preparation_id=str(id), **body)) or
                        event['formal_sla'] is not False or not event['occurred_at'].endswith('+00:00') or
                        when < instant or not hd.instant(cap['capability']['valid_from']) <= when < hd.instant(cap['capability']['valid_until'])):
                    raise ValueError('event mismatch')
                previous, instant = sha, when
                events.append(dict(event, sha256=sha))
        except (KeyError, ValueError, TypeError) as exc:
            raise Conflict('fixture event chain invalid') from exc
        return events

    @staticmethod
    def projection(source, now, events):
        """Pure projection, not an authority or a journal import interface."""
        start = hd.instant(source['binding']['started_at'])
        previous = start
        if now < start:
            raise Conflict('clock observation precedes original start')
        for event in events:
            when = hd.instant(event['occurred_at'])
            if not previous <= when <= now:
                raise Conflict('clock observation or fixture event order uncertain')
            previous = when
        intervals = []
        bound = source['binding']
        for i, event in enumerate(events):
            when = hd.instant(event['occurred_at'])
            if i % 2 == 0:
                past = hd._calculate(source['definition'], start, when,
                    service_id=bound['service_id'], service_version=bound['service_version'], org_id=bound['org_id'],
                    excluded=intervals, elapsed_only=True)
                if (past['state'] != 'SYNTHETIC_ELAPSED' or
                        past['elapsed_work_seconds'] >= past['target_work_seconds']):
                    raise Conflict('historical pause after completed or unknown working-time target')
            else:
                left = hd.instant(events[i-1]['occurred_at'])
                if when > left:
                    intervals.append((left, when))
        paused = bool(len(events) % 2)
        if paused:
            left = hd.instant(events[-1]['occurred_at'])
            if now > left:
                intervals.append((left, now))
        result = hd._calculate(source['definition'], start, now,
            service_id=bound['service_id'], service_version=bound['service_version'], org_id=bound['org_id'],
            excluded=intervals, elapsed_only=paused)
        if paused and result['state'] == 'SYNTHETIC_ELAPSED':
            result.update(state='SYNTHETIC_PAUSED', deadline_utc=None, deadline_local=None,
                          issues=['RESUME_TIME_NOT_KNOWN'])
        return dict(result, scope=SCOPE, formal_sla=False, case_goal_completed=False,
                    legal_pause_decision='NOT_EVALUATED', read_only=True,
                    started_at=bound['started_at'], observed_at=now.astimezone(hd.UTC).isoformat(),
                    preparation_id=bound['preparation_id'], case_id=bound['case_id'], run_id=bound['run_id'],
                    revision=len(events), paused=paused, events=events,
                    binding_sha256=hd.fingerprint(bound), definition_sha256=hd.fingerprint(source['definition']))


def service(store):
    obj = getattr(store, '_synthetic_pause_clock', None)
    if type(obj) is not IsolatedPauseClock or obj.store is not store:
        raise Denied('LOCAL_SYNTHETIC pause fixture disabled')
    return obj


def read(store, token, id, key=None):
    clock = service(store)
    with store.connect() as c:
        c.execute("SET LOCAL lock_timeout='3s'")
        clock.context(c, token, id)
        with clock.journal() as db:
            actor, parent, source, now = clock.context(c, token, id)
            events = clock.events(db, id, source)
            result = clock.projection(source, now, events)
            cap = json.loads(clock.capabilities[str(id)])['capability']
            result['fixture_capability_current'] = hd.instant(cap['valid_from']) <= now < hd.instant(cap['valid_until'])
            result['fixture_write_enabled'] = result['fixture_capability_current'] and actor['id'] == cap['actor_id']
            if key is not None:
                event = next((e for e in events if e['actor_id'] == actor['id'] and e['request_key'] == key), None)
                result.update(recovery_status='COMMITTED' if event else 'NOT_OBSERVED',
                              recovered_event=event, automatically_replayed=False)
            return result


def command(store, token, id, key, data):
    clock = service(store)
    fp = hd.fingerprint(dict(preparation_id=str(id), **data.model_dump()))
    with store.connect() as c:
        c.execute("SET LOCAL lock_timeout='3s'")
        clock.context(c, token, id, write=True)
        with clock.journal(write=True) as db:
            # The SQLite writer lock can wait. All mutable checks and DB time
            # are obtained again while holding it and the original PG locks.
            actor, parent, source, now = clock.context(c, token, id, write=True)
            events = clock.events(db, id, source)
            previous = db.execute('SELECT * FROM fixture_events WHERE actor=? AND key=?', (actor['id'], key)).fetchone()
            if previous:
                if previous['preparation'] != str(id) or previous['fp'] != fp:
                    raise Conflict('original fixture key fingerprint mismatch')
                return json.loads(previous['payload'])
            view = clock.projection(source, now, events)
            if (data.expected_revision != len(events) or
                    data.expected_definition_sha256 != view['definition_sha256'] or len(events) >= 32):
                raise Conflict('stale or bounded fixture clock; read current state')
            if view['state'] not in ('SYNTHETIC_CALCULATED', 'SYNTHETIC_PAUSED'):
                raise Conflict('current complete clock source required')
            if (data.action == 'PAUSE') == view['paused']:
                raise Conflict('explicit alternating PAUSE/RESUME required')
            if view['elapsed_work_seconds'] >= view['target_work_seconds']:
                raise Conflict('completed working-time target cannot be paused')
            # Catalog is SELECT-only for the original application role. Do not
            # add SQL privileges merely to obtain a catalog row lock. Recheck
            # its xmin-bound source immediately before the journal insertion.
            actor, parent, current_source, now = clock.context(c, token, id, write=True)
            if current_source != source:
                raise Conflict('fixture source changed before append')
            view = clock.projection(source, now, events)
            if (view['state'] not in ('SYNTHETIC_CALCULATED', 'SYNTHETIC_PAUSED') or
                    view['elapsed_work_seconds'] >= view['target_work_seconds']):
                raise Conflict('current incomplete working-time target required')
            event = dict(scope=SCOPE, preparation_id=str(id), actor_id=actor['id'],
                action=data.action, reason=data.reason, note=data.note, revision=len(events)+1,
                occurred_at=now.astimezone(hd.UTC).isoformat(), request_key=key, request_sha256=fp,
                definition_sha256=view['definition_sha256'], binding_sha256=view['binding_sha256'],
                previous_sha256=events[-1]['sha256'] if events else None,
                formal_sla=False, legal_pause_decision='NOT_EVALUATED')
            event['sha256'] = hd.fingerprint(event)
            db.execute('INSERT INTO fixture_events VALUES(?,?,?,?,?,?)',
                       (str(id), event['revision'], actor['id'], key, fp, prep.canonical(event)))
            # No PostgreSQL DML: the one durable write is this separate fixture journal.
            return event
