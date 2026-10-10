"""Dormant, read-only synthetic business-clock calculation; no pause authority.

Calendar dates are explicit source data, never inferred holidays or a real SLA.
The host-only registry contains immutable copied bytes and no PG writes.
"""
from datetime import date, datetime, timedelta, timezone
import json
import os
import re
from types import MappingProxyType
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from . import preparation as prep, request_intents, case_fact_clarifications as facts
from .store import Denied, digest

UTC = timezone.utc
ID = Annotated[str, Field(min_length=1, max_length=80, pattern=r'^[A-Za-z0-9_.:-]+$')]
SHA = Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Source(Contract):
    kind: Literal['SYNTHETIC']
    id: ID
    revision: int = Field(ge=1, le=1000000)
    text: str = Field(min_length=1, max_length=2000)
    sha256: SHA
    valid_from: str
    valid_until: str
    service_id: ID
    service_version: int = Field(ge=1)
    accepting_org_id: ID


class Reference(Contract):
    id: ID
    revision: int = Field(ge=1, le=1000000)
    sha256: SHA


class Window(Contract):
    start: str
    end: str


class CalendarDay(Contract):
    date: str
    kind: Literal['WORKING', 'CLOSED']
    windows: list[Window] = Field(max_length=2)


class Calendar(Contract):
    id: ID
    revision: int = Field(ge=1, le=1000000)
    source_ref: Reference
    timezone: str = Field(min_length=1, max_length=80)
    first_date: str
    last_date: str
    days: list[CalendarDay] = Field(min_length=1, max_length=366)


class Policy(Contract):
    source_ref: Reference
    calendar_ref: Reference
    timezone: str = Field(min_length=1, max_length=80)
    target_seconds: int = Field(ge=1, le=31536000)
    start_basis: Literal['SYNTHETIC_PREPARATION_CREATE']


class Definition(Contract):
    source: Source
    calendar: Calendar
    policy: Policy
    pauses: list[dict] = Field(max_length=16)


class Unknown(ValueError):
    pass


def fingerprint(value):
    return digest(prep.canonical(value))


def instant(value):
    if not isinstance(value, str) or not re.fullmatch(
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})', value):
        raise Unknown('TIMESTAMP_INVALID')
    try:
        result = datetime.fromisoformat(value)
        return result.astimezone(UTC)
    except (ValueError, OverflowError):
        raise Unknown('TIMESTAMP_INVALID') from None


def local_endpoint(value, zone):
    utc = instant(value)
    declared = datetime.fromisoformat(value)
    naive = declared.replace(tzinfo=None)
    if naive.microsecond:
        raise Unknown('CALENDAR_WINDOW_INVALID')
    # A supplied offset alone does not authorize guessing a DST fold.
    candidates = {naive.replace(tzinfo=zone, fold=f).astimezone(UTC)
                  for f in (0, 1)
                  if naive.replace(tzinfo=zone, fold=f).astimezone(UTC)
                  .astimezone(zone).replace(tzinfo=None) == naive}
    if not candidates:
        raise Unknown('NONEXISTENT_LOCAL_TIME')
    if len(candidates) != 1:
        raise Unknown('AMBIGUOUS_LOCAL_TIME')
    if utc not in candidates or declared.utcoffset() != utc.astimezone(zone).utcoffset():
        raise Unknown('TIMEZONE_OFFSET_MISMATCH')
    return utc, naive


def calendar_windows(calendar):
    try:
        zone = ZoneInfo(calendar.timezone)
    except (ValueError, ZoneInfoNotFoundError):
        raise Unknown('TIMEZONE_UNAVAILABLE') from None
    try:
        first = date.fromisoformat(calendar.first_date)
        last = date.fromisoformat(calendar.last_date)
        dates = [date.fromisoformat(d.date) for d in calendar.days]
    except ValueError:
        raise Unknown('CALENDAR_DATE_INVALID') from None
    if (last < first or (last-first).days >= 366 or dates !=
            [first+timedelta(days=i) for i in range((last-first).days+1)]):
        raise Unknown('CALENDAR_COVERAGE_INCOMPLETE')
    windows = []
    for day, current in zip(calendar.days, dates):
        if ((day.kind == 'CLOSED' and day.windows) or
                (day.kind == 'WORKING' and not day.windows)):
            raise Unknown('CALENDAR_DAY_INVALID')
        for window in day.windows:
            start, local_start = local_endpoint(window.start, zone)
            end, local_end = local_endpoint(window.end, zone)
            midnight_next = datetime.combine(current+timedelta(days=1), datetime.min.time())
            if (local_start.date() != current or
                    (local_end.date() != current and local_end != midnight_next) or
                    end <= start or (windows and start < windows[-1][1])):
                raise Unknown('CALENDAR_WINDOW_INVALID')
            windows.append((start, end))
    # Coverage boundaries must themselves be unambiguous local instants.
    boundaries = []
    for d in (first, last+timedelta(days=1)):
        local = datetime.combine(d, datetime.min.time()).replace(tzinfo=zone)
        boundary, _ = local_endpoint(local.isoformat(), zone)
        boundaries.append(boundary)
    return zone, boundaries, windows


def calculate(raw, started, observed, *, service_id, service_version, org_id):
    """Pure reference computation. Unknowns never receive invented deadlines."""
    base = dict(state='UNKNOWN', issues=[], deadline_utc=None, deadline_local=None,
                elapsed_work_seconds=None, target_work_seconds=None, timezone=None,
                source_ref=None, calendar_ref=None, legal_pause_decision='NOT_EVALUATED')
    try:
        try:
            definition = Definition.model_validate(raw)
        except ValidationError:
            raise Unknown('SOURCE_CONTRACT_INCOMPLETE_OR_INVALID') from None
        s, cal, policy = definition.source, definition.calendar, definition.policy
        source_ref = dict(id=s.id, revision=s.revision, sha256=s.sha256)
        calendar_ref = dict(id=cal.id, revision=cal.revision,
                            sha256=fingerprint(cal.model_dump()))
        if s.sha256 != digest(s.text):
            raise Unknown('SOURCE_HASH_MISMATCH')
        if (policy.source_ref.model_dump() != source_ref or
                cal.source_ref.model_dump() != source_ref or
                policy.calendar_ref.model_dump() != calendar_ref):
            raise Unknown('SOURCE_REFERENCE_MISMATCH')
        if (s.service_id, s.service_version, s.accepting_org_id) != (service_id, service_version, org_id):
            raise Unknown('SOURCE_NOT_APPLICABLE')
        if (not isinstance(started, datetime) or started.tzinfo is None or
                not isinstance(observed, datetime) or observed.tzinfo is None):
            raise Unknown('START_OR_OBSERVATION_MISSING')
        started, observed = started.astimezone(UTC), observed.astimezone(UTC)
        valid_from, valid_until = instant(s.valid_from), instant(s.valid_until)
        if not valid_from <= started <= observed < valid_until:
            raise Unknown('SOURCE_NOT_CURRENT_OR_TIME_INVALID')
        if policy.timezone != cal.timezone:
            raise Unknown('TIMEZONE_REFERENCE_MISMATCH')
        if definition.pauses:
            raise Unknown('PAUSE_AUTHORITY_UNAVAILABLE')
        zone, (first, end), windows = calendar_windows(cal)
        if not first <= started <= observed < end:
            raise Unknown('CALENDAR_COVERAGE_INCOMPLETE')
        remaining = policy.target_seconds
        deadline = None
        elapsed = 0.0
        for start, finish in windows:
            start = max(start, started)
            if finish <= start:
                continue
            elapsed += max(0, (min(observed, finish)-start).total_seconds())
            if deadline is None:
                seconds = (finish-start).total_seconds()
                if remaining <= seconds:
                    deadline = start+timedelta(seconds=remaining)
                else:
                    remaining -= seconds
        if deadline is None:
            raise Unknown('CALENDAR_TARGET_OUT_OF_COVERAGE')
        if deadline >= valid_until:
            raise Unknown('SOURCE_VALIDITY_DOES_NOT_COVER_DEADLINE')
        base.update(state='SYNTHETIC_CALCULATED', deadline_utc=deadline.isoformat(),
                    deadline_local=deadline.astimezone(zone).isoformat(),
                    elapsed_work_seconds=round(elapsed, 6), target_work_seconds=policy.target_seconds,
                    timezone=cal.timezone, source_ref=source_ref, calendar_ref=calendar_ref)
    except Unknown as exc:
        base['issues'] = [str(exc)]
    except (OverflowError, UnicodeError):
        base['issues'] = ['TIME_RANGE_OR_SOURCE_ENCODING_INVALID']
    return base


def binding(c, parent):
    """Opaque binding only, never a public material or request projection."""
    catalog = c.execute('SELECT *,xmin::text row_version FROM preparation_catalog WHERE park_id=%s AND service_id=%s AND version=%s',
                        (parent['park_id'], parent['service_id'], parent['service_version'])).fetchone()
    event = c.execute("SELECT * FROM preparation_events WHERE preparation_id=%s AND revision=1 AND action='CREATE'",
                      (parent['id'],)).fetchone()
    if not catalog or not event or (event['actor_id'] != parent['owner_id'] or
            event['payload'].get('preparation_id') != str(parent['id']) or
            event['payload'].get('case_id') != str(parent['case_id']) or
            event['payload'].get('run_id') != str(parent['run_id']) or
            event['created_at'] < parent['created_at']):
        raise Unknown('ORIGINAL_START_EVIDENCE_UNAVAILABLE')
    request = request_intents.view(parent)
    return dict(park_id=parent['park_id'], org_id=parent['org_id'], owner_id=parent['owner_id'],
                reviewer_id=parent['reviewer_id'], preparation_id=str(parent['id']),
                case_id=str(parent['case_id']), run_id=str(parent['run_id']),
                preparation_revision=parent['revision'], request_revision=request['revision'],
                request_sha256=fingerprint(request), service_id=parent['service_id'],
                service_version=parent['service_version'], catalog_sha256=fingerprint(catalog),
                materials_sha256=prep.snapshot(parent, prep.latest(c, parent['id'])),
                start_event_id=str(event['id']), start_sha256=fingerprint(event['payload']),
                preparation_created_at=parent['created_at'].astimezone(UTC).isoformat(),
                started_at=event['created_at'].astimezone(UTC).isoformat())


class IsolatedDeadlineSources:
    """Same-process, issued temporary database proof; no DDL or business write."""
    def __init__(self, owner=None, proof=None, *, definitions=None, enabled_for_isolated_tests=False):
        self.enabled = enabled_for_isolated_tests is True
        self.owner, self.proof, self.pid = owner, proof, os.getpid()
        self.entries = MappingProxyType({})
        if not self.enabled:
            return
        if owner is None or owner.mode != 'LOCAL' or not isinstance(definitions, dict) or not 1 <= len(definitions) <= 16:
            raise Denied('bounded original synthetic deadline scope required')
        entries = {}
        with owner.connect() as c:
            self._owner_proof(c)
            self.endpoint = (c.info.host, c.info.port)
            for id, raw in definitions.items():
                id = UUID(str(id))
                parent = c.execute('SELECT * FROM preparations WHERE id=%s FOR SHARE', (id,)).fetchone()
                if not parent or parent['namespace'] != 'SYNTHETIC':
                    raise Denied('original synthetic preparation required')
                p = c.execute('SELECT * FROM principals WHERE id=%s AND active', (parent['owner_id'],)).fetchone()
                if not p:
                    raise Denied('existing synthetic owner required')
                prep.grant(owner, c, p, 'PREPARE')
                try:
                    bound = binding(c, parent)
                    data = prep.canonical(dict(binding=bound, definition=raw))
                except (Unknown, TypeError, ValueError):
                    raise Denied('explicit deadline binding required') from None
                if len(data.encode()) > 262144:
                    raise Denied('bounded deadline source required')
                entries[str(id)] = (data, digest(data))
        self.entries = MappingProxyType(entries)

    def _issued(self):
        p = self.proof
        if (not self.enabled or self.pid != os.getpid() or type(p) is not facts.FixtureDatabaseEvidence or
                facts._fixture_databases.get(p.nonce) is not p or
                facts._fixture_clusters.get(p.cluster.nonce) is not p.cluster or
                set(dict(p.cluster.initial_databases)) != {'postgres', 'template0', 'template1'} or
                p.database_name in dict(p.cluster.initial_databases)):
            raise Denied('issued temporary deadline fixture required')
        return p

    def _owner_proof(self, c):
        p = self._issued()
        actual = facts._migration_identity(c)
        facts._same_cluster(p.cluster, actual)
        if (actual['database_oid'] != p.database_oid or actual['database_name'] != p.database_name or
                actual['owner_name'] != p.cluster.owner or actual['session_name'] != p.cluster.owner):
            raise Denied('deadline fixture owner mismatch')

    def _connection(self, c):
        p = self._issued()
        row = c.execute('SELECT oid,datname,pg_postmaster_start_time() started FROM pg_database WHERE datname=current_database()').fetchone()
        if ((c.info.host, c.info.port) != self.endpoint or row['oid'] != p.database_oid or
                row['datname'] != p.database_name or row['started'] != p.cluster.postmaster_start):
            raise Denied('deadline fixture connection mismatch')

    def attach_store(self, store):
        if not self.enabled or store.mode != 'LOCAL':
            raise Denied('isolated deadline sources disabled')
        with self.owner.connect() as c:
            self._owner_proof(c)
        with store.connect() as c:
            self._connection(c)
        store._isolated_deadline_sources = self
        return store


def read(store, token, id):
    with store.connect() as c:
        c.execute("SET LOCAL lock_timeout='3s'")
        p = store.auth(c, token, lock=True)
        parent = prep.scoped(store, c, p, id)
        base = dict(preparation_id=str(id), case_id=str(parent['case_id']), run_id=str(parent['run_id']),
                    preparation_revision=parent['revision'], enabled=False, read_only=True,
                    scope='SYNTHETIC_HANDLING_DEADLINE_READ_ONLY', formal_sla=False,
                    pause_write_enabled=False, case_goal_completed=False, legal_pause_decision='NOT_EVALUATED',
                    state='UNKNOWN', issues=['DEADLINE_SOURCE_DISABLED'], started_at=None,
                    observed_at=None, deadline_utc=None, deadline_local=None, timezone=None,
                    elapsed_work_seconds=None, target_work_seconds=None, source_ref=None, calendar_ref=None,
                    binding_sha256=None, definition_sha256=None)
        registry = getattr(store, '_isolated_deadline_sources', None)
        if type(registry) is not IsolatedDeadlineSources or not registry.enabled:
            return base
        registry._connection(c)
        base['enabled'] = True
        entry = registry.entries.get(str(id))
        if entry is None:
            base['issues'] = ['DEADLINE_SOURCE_MISSING']
            return base
        data, sha = entry
        if digest(data) != sha:
            base['issues'] = ['DEADLINE_SOURCE_HASH_MISMATCH']
            return base
        source = json.loads(data)
        try:
            current = binding(c, parent)
        except Unknown as exc:
            base['issues'] = [str(exc)]
            return base
        if current != source['binding']:
            base['issues'] = ['DEADLINE_BINDING_CHANGED']
            return base
        # Obtain the observation after current identity/preparation locks and binding reads.
        now = c.execute('SELECT clock_timestamp() now').fetchone()['now']
        base.update(started_at=current['started_at'], observed_at=now.astimezone(UTC).isoformat(),
                    binding_sha256=fingerprint(current), definition_sha256=fingerprint(source['definition']))
        base.update(calculate(source['definition'], instant(current['started_at']), now,
                              service_id=parent['service_id'], service_version=parent['service_version'],
                              org_id=parent['org_id']))
        return base
