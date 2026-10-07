"""Case-purpose selection of owner assertions, never fact authenticity verification.

Standalone candidate. Main line must register migration 025, redact generic
preparation reads, and bind actual REVIEW/CONFIRM/readiness/P1-P5 to descriptor.
No routes, seeds, grants or global assertion mutations are provided here.

API: read(store, token, preparation_id); declare/confirm(store, token,
preparation_id, key, data); gate/source_descriptor(store, connection, parent).
Caller of gate/descriptor must use a transaction and already hold its parent
row lock. Owner/field advisory locks are retained until that transaction ends,
serializing supported Store.save_fact and revocation operations with COMMIT.
public_status accepts a gate/read result, never a private ledger.
"""
from copy import deepcopy
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from psycopg.types.json import Jsonb

from . import preparation as prep
from .store import Conflict, Denied, digest

PROFILE = 'LOCAL_SERVICE_PREPARATION_FACTS_V1'
PURPOSE = 'SERVICE_PREPARATION'
FIELDS = ('region', 'employees', 'service_need')
LIMIT = 64


class Declare(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True, revalidate_instances='always')
    expected_preparation_revision: int = Field(ge=1, le=63)
    expected_clarification_revision: Literal[0] = 0
    profile: Literal['LOCAL_SERVICE_PREPARATION_FACTS_V1']
    purpose: Literal['SERVICE_PREPARATION']
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator('expected_clarification_revision', mode='before')
    @classmethod
    def reject_bool_revision(cls, value):
        if type(value) is not int:
            raise ValueError('integer revision required')
        return value


class Choice(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, revalidate_instances='always')
    field: Literal['region', 'employees', 'service_need']
    assertion_id: UUID = Field(strict=False)
    expected_assertion_revision: int = Field(ge=1)
    expected_assertion_fingerprint: str = Field(pattern=r'^[0-9a-f]{64}$')


class Confirm(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True, revalidate_instances='always')
    expected_preparation_revision: int = Field(ge=1, le=63)
    expected_clarification_revision: int = Field(ge=1, le=63)
    expected_source_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    choices: list[Choice] = Field(min_length=3, max_length=3)
    reason: str = Field(min_length=1, max_length=1000)

    @model_validator(mode='after')
    def exact_fields(self):
        if {item.field for item in self.choices} != set(FIELDS):
            raise ValueError('exactly three distinct purpose fields required')
        return self


def _normal(value):
    if isinstance(value, (UUID, datetime)):
        return str(value) if isinstance(value, UUID) else value.isoformat()
    if isinstance(value, dict):
        return {key: _normal(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normal(item) for item in value]
    return value


def _hash(value):
    return digest(prep.canonical(_normal(value)))


def _binding(parent):
    return _normal(dict(profile=PROFILE, purpose=PURPOSE, required_fields=list(FIELDS),
        preparation_id=parent['id'], case_id=parent['case_id'], run_id=parent['run_id'],
        owner_id=parent['owner_id'], park_id=parent['park_id'], org_id=parent['org_id'],
        namespace=parent['namespace'], service_id=parent['service_id'],
        service_version=parent['service_version'], goal=parent['goal'],
        request_intent=parent.get('request_intent')))


def _scope(store, c, p, parent, require_write=True):
    prep.grant(store, c, p, 'PREPARE')
    store.check_capability(c, p, 'EXECUTE')
    store.check_fields(c, p, list(FIELDS), 'READ')
    if require_write:
        store.check_fields(c, p, list(FIELDS), 'WRITE')
    if (parent['owner_id'], parent['park_id'], parent['org_id']) != (p['id'], p['park_id'], p['org_id']):
        raise Denied('current Case owner scope required')
    run = store.scoped_run(c, p, parent['run_id'])
    store.check_execution(c, p, run)
    case = c.execute('SELECT * FROM cases WHERE id=%s AND run_id=%s AND park_id=%s AND org_id=%s',
        (parent['case_id'], parent['run_id'], p['park_id'], p['org_id'])).fetchone()
    if (parent['namespace'] != 'SYNTHETIC' or parent['service_id'] != prep.SERVICE or
        parent['service_version'] != 1 or run['state'] != 'SUCCEEDED' or
        run['input'].get('action', 'case.create') != 'case.create' or
        not case or case['source'] != 'SYNTHETIC'):
        raise Denied('own bound synthetic-material-preparation@1 Case required')


def _field_locks(c, owner_id):
    # Exactly the existing Store.save_fact field lock namespace and stable order.
    for field in sorted(FIELDS):
        c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
            ('field:' + owner_id + ':' + field,))


def _owner(store, c, parent):
    store.lock_principal(c, parent['owner_id'])
    p = c.execute('SELECT * FROM principals WHERE id=%s AND active', (parent['owner_id'],)).fetchone()
    if not p:
        raise Denied('current owner unavailable')
    _field_locks(c, p['id'])
    _scope(store, c, p, parent)  # recheck timed grants after lock waits
    return p


def _ledger(parent):
    value = parent.get('fact_clarifications')
    if value is None:
        return None
    if (not isinstance(value, dict) or value.get('version') != 1 or
        value.get('profile') != PROFILE or value.get('purpose') != PURPOSE or
        value.get('required_fields') != list(FIELDS) or
        type(value.get('revision')) is not int or not 1 <= value['revision'] <= LIMIT or
        not isinstance(value.get('events'), list) or len(value['events']) != value['revision']):
        raise Conflict('fact purpose ledger unavailable')
    for index, event in enumerate(value['events'], 1):
        if (not isinstance(event, dict) or event.get('revision') != index or
            event.get('action') != ('DECLARE_FACT_PURPOSE' if index == 1 else 'CONFIRM_FACT_PURPOSE') or
            event.get('decision_sha256') != _hash({key: item for key, item in event.items() if key != 'decision_sha256'})):
            raise Conflict('fact purpose history binding changed')
    return value


def _stored_ledger(c, parent):
    value = _ledger(parent)
    if value is None and c.execute("SELECT 1 FROM preparation_events WHERE preparation_id=%s AND action='DECLARE_FACT_PURPOSE'", (parent['id'],)).fetchone():
        raise Conflict('declared fact purpose cannot be removed or downgraded to legacy')
    return value


def _authority(c, p):
    """Stable prerequisite rows, never bearer/token hashes or observation time.

    A restored existing grant has a new revision. It cannot revive a decision
    committed against the previous authority generation. Only relevant rows
    enter this binding; unrelated capability changes do not stale this Case.
    Tables without a revision retain their actual active/scope row snapshot;
    unobserved direct administrator toggles of those rows are not an audit log.
    """
    scope = (p['id'], p['park_id'], p['org_id'])
    return _normal(dict(
        principal={key: p[key] for key in ('id', 'park_id', 'org_id', 'role', 'active')},
        capabilities=c.execute("SELECT principal_id,park_id,org_id,capability,active,revision FROM capability_grants WHERE principal_id=%s AND park_id=%s AND org_id=%s AND capability IN ('READ','EXECUTE') ORDER BY capability", scope).fetchall(),
        fields=c.execute("SELECT principal_id,park_id,org_id,field_name,purpose,capability,active,revision,valid_until FROM field_grants WHERE principal_id=%s AND park_id=%s AND org_id=%s AND purpose=%s AND field_name=ANY(%s) ORDER BY field_name,capability", (*scope, PURPOSE, list(FIELDS))).fetchall(),
        preparation=c.execute("SELECT principal_id,park_id,org_id,capability,active FROM preparation_grants WHERE principal_id=%s AND park_id=%s AND org_id=%s AND capability='PREPARE'", scope).fetchall(),
        action=c.execute("SELECT principal_id,park_id,org_id,action,active FROM action_grants WHERE principal_id=%s AND park_id=%s AND org_id=%s AND action='case.create'", scope).fetchall()))


def _sources(store, c, parent, p):
    rows = store.facts_query(c, p, list(FIELDS))
    if any(sum(row['field_name'] == field for row in rows) > 16 for field in FIELDS):
        raise Conflict('bounded field source history exceeded')
    sources = sorted((_normal(row) for row in rows), key=lambda row: (row['field_name'], row['id']))
    binding = dict(_binding(parent), authority=_authority(c, p))
    now = c.execute('SELECT clock_timestamp() now').fetchone()['now']
    applicable = {str(row['id']): row['valid_from'] <= now < row['valid_until'] for row in rows}
    return dict(binding=binding, sources=sources), _hash(dict(binding=binding, sources=sources)), applicable


def public_status(result):
    """Only allowlisted status/hash fields; no assertion IDs, values or excerpts."""
    keys = ('enabled', 'state', 'satisfied', 'issues', 'revision', 'decision_ref',
            'decision_sha256', 'source_sha256', 'profile', 'purpose', 'required_fields',
            'qualification', 'authenticity')
    return deepcopy({key: result[key] for key in keys if key in result})


def _result(ledger=None, state='NOT_DECLARED', issues=(), sha=None):
    current = ledger['events'][-1] if ledger else None
    return dict(enabled=ledger is not None, state=state,
        satisfied=state in ('NOT_DECLARED', 'CURRENT'), issues=sorted(set(issues)),
        revision=ledger['revision'] if ledger else 0,
        decision_ref=current['id'] if current else None,
        decision_sha256=current['decision_sha256'] if current else None,
        source_sha256=sha, profile=ledger['profile'] if ledger else None,
        purpose=ledger['purpose'] if ledger else None,
        required_fields=list(FIELDS) if ledger else [],
        qualification='NOT_EVALUATED', authenticity='USER_ASSERTED_UNVERIFIED')


def _evaluate(parent, ledger, snapshot, sha, applicable):
    latest = ledger['events'][-1]
    issues = []
    if latest['source_sha256'] != sha:
        issues.append('FACT_SOURCES_OR_REQUEST_CHANGED')
        if latest.get('source_snapshot', {}).get('binding', {}).get('authority') != snapshot['binding']['authority']:
            issues.append('FACT_AUTHORITY_GENERATION_CHANGED')
    if latest['action'] == 'DECLARE_FACT_PURPOSE':
        issues.append('FACT_PURPOSE_SELECTION_REQUIRED')
    else:
        if latest['applicable'] != applicable:
            issues.append('FACT_SOURCE_VALIDITY_CHANGED')
        selected = {choice['assertion_id'] for choice in latest['choices']}
        if not all(applicable.get(id, False) for id in selected):
            issues.append('SELECTED_FACT_NOT_CURRENT')
    state = 'STALE' if any(issue != 'FACT_PURPOSE_SELECTION_REQUIRED' for issue in issues) else 'UNKNOWN' if issues else 'CURRENT'
    return _result(ledger, state, issues, sha)


def gate(store, c, parent):
    """Private trusted dependency check. Returns no raw sources; never writes GET metadata."""
    try:
        ledger = _stored_ledger(c, parent)
    except Conflict:
        return dict(_result(state='STALE', issues=['FACT_PURPOSE_LEDGER_INVALID']), enabled=True, satisfied=False)
    if ledger is None:
        return _result()
    try:
        p = _owner(store, c, parent)
        snapshot, sha, applicable = _sources(store, c, parent, p)
    except (Denied, Conflict):
        return _result(ledger, 'STALE', ['FACT_PURPOSE_AUTHORITY_OR_SOURCE_UNAVAILABLE'])
    return _evaluate(parent, ledger, snapshot, sha, applicable)


def source_descriptor(store, c, parent):
    """Opaque current binding for material snapshots; no values/IDs/excerpts."""
    status = public_status(gate(store, c, parent))
    return dict(status, descriptor_sha256=_hash(status))


def _transaction(store, c, token, id, key=None):
    c.execute("SET LOCAL lock_timeout='3s'")
    p = store.auth(c, token, lock=True)
    if key is not None:
        if type(key) is not str or not 1 <= len(key) <= 200 or not key.strip():
            raise Conflict('bounded nonblank idempotency key required')
        prep.key_lock(c, p, key)
    parent = prep.scoped(store, c, p, id, write=key is not None)
    _field_locks(c, p['id'])
    _scope(store, c, p, parent, require_write=key is not None)
    return p, parent


def read(store, token, preparation_id):
    with store.connect() as c:
        p, parent = _transaction(store, c, token, preparation_id)
        ledger = _stored_ledger(c, parent)
        snapshot, sha, applicable = _sources(store, c, parent, p)
        # READ permits private history even if WRITE has been withdrawn; the
        # current business gate separately rechecks all mutation authority.
        result = gate(store, c, parent) if ledger else _result(sha=sha)
        questions = []
        for field in FIELDS:
            entries = [row for row in snapshot['sources'] if row['field_name'] == field]
            valid = [row for row in entries if applicable[row['id']]]
            reason = 'MISSING_EVIDENCE' if not entries else 'EXPIRED_OR_NOT_YET_VALID' if not valid else 'CONFLICTING_EVIDENCE' if len({_hash([row['value'], row['unit']]) for row in valid}) > 1 else 'CASE_PURPOSE_SELECTION_REQUIRED'
            questions.append(dict(field=field, state='USER_SELECTED_FOR_CASE' if result['state'] == 'CURRENT' else 'UNKNOWN',
                reason='USER_ASSERTED_UNVERIFIED' if result['state'] == 'CURRENT' else reason,
                evidence=entries, applicable_assertion_ids=[row['id'] for row in valid]))
        return dict(result, preparation_id=str(parent['id']), case_id=str(parent['case_id']), run_id=str(parent['run_id']),
            preparation_revision=parent['revision'], profile=PROFILE, purpose=PURPOSE,
            required_fields=list(FIELDS), source_sha256=sha, sources=snapshot['sources'],
            necessary_questions=questions, history=deepcopy(ledger['events']) if ledger else [])


def _replay(c, p, parent, key, fp):
    old = c.execute('SELECT * FROM preparation_events WHERE actor_id=%s AND request_key=%s', (p['id'], key)).fetchone()
    if old:
        if old['fingerprint'] != fp or old['preparation_id'] != parent['id']:
            raise Conflict('fact purpose idempotency fingerprint mismatch')
        if old['action'] not in ('DECLARE_FACT_PURPOSE', 'CONFIRM_FACT_PURPOSE'):
            raise Conflict('fact purpose event action mismatch')
        return dict(deepcopy(old['payload']), recovery='HISTORICAL_COMMITTED_EVENT', current_decision_restored=False)
    return None


def _persist(store, c, p, parent, ledger, key, fp, action, reason, snapshot, sha, applicable, choices):
    from .controlled_plans import invalidate
    value = deepcopy(ledger) if ledger else dict(version=1, profile=PROFILE, purpose=PURPOSE, required_fields=list(FIELDS), revision=0, events=[])
    value['revision'] += 1
    event = _normal(dict(id=uuid4(), action=action, revision=value['revision'],
        preparation_revision=parent['revision'] + 1, actor_id=p['id'], reason=reason,
        decided_at=c.execute('SELECT clock_timestamp() now').fetchone()['now'],
        source_sha256=sha, source_snapshot=snapshot, applicable=applicable, choices=choices,
        selection='USER_SELECTED_FOR_CASE' if choices else 'UNKNOWN', authenticity='USER_ASSERTED_UNVERIFIED'))
    event['decision_sha256'] = _hash(event)
    value['events'].append(event)
    updated = c.execute("UPDATE preparations SET fact_clarifications=%s,revision=revision+1,state='IN_PREPARATION',review_sha256=NULL WHERE id=%s AND revision=%s RETURNING *",
        (Jsonb(value), parent['id'], parent['revision'])).fetchone()
    if not updated:
        raise Conflict('preparation CAS changed')
    invalidate(c, parent['id'], 1)
    # Recheck after any plan lock wait; rollback all effects if timed authority
    # or source applicability changed during this transaction. Supported source
    # writers remain serialized by the field locks until COMMIT.
    _scope(store, c, p, parent)
    if _authority(c, p) != snapshot['binding']['authority']:
        raise Conflict('fact authority generation changed during confirmation; refresh required')
    now = c.execute('SELECT clock_timestamp() now').fetchone()['now']
    late_applicable = {row['id']: datetime.fromisoformat(row['valid_from']) <= now < datetime.fromisoformat(row['valid_until'])
        for row in snapshot['sources']}
    if choices and (late_applicable != applicable or not all(late_applicable.get(item['assertion_id'], False) for item in choices)):
        raise Conflict('fact source validity changed during confirmation; refresh required')
    result = _result(value, 'CURRENT' if choices else 'UNKNOWN', () if choices else ('FACT_PURPOSE_SELECTION_REQUIRED',), sha)
    return prep.event(c, p, updated, key, fp, action, reason=reason,
        decision_ref=event['id'], decision_sha256=event['decision_sha256'],
        public_status=public_status(result), required_fields=list(FIELDS))


def declare(store, token, preparation_id, key, data: Declare):
    data = Declare.model_validate(data)
    fp = _hash(dict(preparation_id=str(preparation_id), action='DECLARE_FACT_PURPOSE', **data.model_dump(mode='json')))
    with store.connect() as c:
        p, parent = _transaction(store, c, token, preparation_id, key)
        old = _replay(c, p, parent, key, fp)
        if old:
            return old
        if _stored_ledger(c, parent) is not None:
            raise Conflict('Case fact purpose already declared and cannot be removed')
        if parent['revision'] != data.expected_preparation_revision or parent['revision'] >= LIMIT:
            raise Conflict('preparation revision changed or history limit reached')
        snapshot, sha, applicable = _sources(store, c, parent, p)
        return _persist(store, c, p, parent, None, key, fp, 'DECLARE_FACT_PURPOSE', data.reason, snapshot, sha, applicable, [])


def confirm(store, token, preparation_id, key, data: Confirm):
    data = Confirm.model_validate(data)
    fp = _hash(dict(preparation_id=str(preparation_id), action='CONFIRM_FACT_PURPOSE', **data.model_dump(mode='json')))
    with store.connect() as c:
        p, parent = _transaction(store, c, token, preparation_id, key)
        old = _replay(c, p, parent, key, fp)
        if old:
            return old
        ledger = _stored_ledger(c, parent)
        if not ledger:
            raise Conflict('explicit Case fact purpose declaration required')
        if (parent['revision'] != data.expected_preparation_revision or ledger['revision'] != data.expected_clarification_revision or
            parent['revision'] >= LIMIT or ledger['revision'] >= LIMIT):
            raise Conflict('fact purpose dual revision changed or history limit reached')
        snapshot, sha, applicable = _sources(store, c, parent, p)
        if data.expected_source_sha256 != sha:
            raise Conflict('fact purpose sources changed; refresh required')
        by_id = {row['id']: row for row in snapshot['sources']}
        for choice in data.choices:
            row = by_id.get(str(choice.assertion_id))
            if (not row or row['field_name'] != choice.field or not applicable[row['id']] or
                row['revision'] != choice.expected_assertion_revision or row['fingerprint'] != choice.expected_assertion_fingerprint):
                raise Conflict('current owner assertion choice binding required')
        choices = [choice.model_dump(mode='json') for choice in data.choices]
        return _persist(store, c, p, parent, ledger, key, fp, 'CONFIRM_FACT_PURPOSE', data.reason, snapshot, sha, applicable, choices)
