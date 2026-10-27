"""Independent current READ source for declared synthetic Case history.

Pure projection consumes server-read rows, never authorizes them. The adapter
uses existing READ checks only; neither function issues execution authority or
loads/enrolls persistent history trust. Raw sources never enter its result.
"""
from datetime import datetime, timezone
import re
from uuid import UUID

from pydantic import ValidationError

from . import case_fact_clarifications as facts, case_fact_bundle as bundle
from . import preparation as prep
from .store import Conflict, Denied

CONTRACT = 'SYNTHETIC_CASE_FACT_HISTORY_READ_V1'


def _same(left, right):
    """JSON equality with exact scalar types, including inside dicts/lists."""
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(_same(left[k], right[k]) for k in left)
    if type(left) in (list, tuple):
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    return left == right


def _utc(value):
    value = datetime.fromisoformat(value) if type(value) is str else value
    if (type(value) is not datetime or value.tzinfo is None or
            value.utcoffset() != timezone.utc.utcoffset(value)):
        raise ValueError('absolute UTC time required')
    return value


def _hash(value):
    if type(value) is not str or re.fullmatch('[a-f0-9]{64}', value) is None:
        raise ValueError('source integrity required')


def project(parent, principal, receipts, sources, applicable, now):
    """Bounded pure contract; caller must already have current scoped READ.

    Original persisted choices resolve conflicts only for this Case purpose.
    A missing selection, duplicate identity, or changed selected source denies;
    no newest-source/default inference and no restored execution decision.
    """
    try:
        now = _utc(now)
        if (principal['active'] is not True or principal['role'] != 'enterprise_operator' or
                any(parent[k] != principal[n] for k, n in
                    (('owner_id', 'id'), ('park_id', 'park_id'), ('org_id', 'org_id'))) or
                parent['namespace'] != 'SYNTHETIC' or parent['service_id'] != prep.SERVICE or
                type(parent['service_version']) is not int or parent['service_version'] != 1 or
                type(parent['revision']) is not int or not 1 <= parent['revision'] <= facts.LIMIT):
            raise ValueError()
        for key in ('id', 'case_id', 'run_id'):
            UUID(str(parent[key]))
        ledger = facts._ledger(parent)
        if (ledger is None or type(ledger['version']) is not int or ledger['version'] != 1 or
                type(receipts) not in (tuple, list) or len(receipts) != ledger['revision'] or
                type(sources) not in (tuple, list) or len(sources) > 60 or type(applicable) is not dict):
            raise ValueError()
        binding = facts._binding(parent)
        stable = {k: v for k, v in binding.items() if k not in ('goal', 'request_intent')}
        seen_events = set()
        seen_keys = set()
        previous_revision = 0
        for index, (event, receipt) in enumerate(zip(ledger['events'], receipts), 1):
            UUID(event['id'])
            snap = event['source_snapshot']
            snap_binding = snap['binding']
            if (type(event['revision']) is not int or event['revision'] != index or
                    event['id'] in seen_events or event['actor_id'] != principal['id'] or
                    type(event['preparation_revision']) is not int or
                    not previous_revision < event['preparation_revision'] <= parent['revision'] or
                    any(not _same(snap_binding.get(k), v) for k, v in stable.items()) or
                    event['source_sha256'] != facts._hash(snap) or
                    _utc(event['decided_at']) > now or
                    event['authenticity'] != 'USER_ASSERTED_UNVERIFIED'):
                raise ValueError()
            expected = dict(preparation_id=str(parent['id']), case_id=str(parent['case_id']),
                run_id=str(parent['run_id']), revision=event['preparation_revision'],
                action=event['action'], actor_id=principal['id'], decision_ref=event['id'],
                decision_sha256=event['decision_sha256'], required_fields=list(facts.FIELDS))
            prefix = dict(ledger, revision=index, events=ledger['events'][:index])
            expected['public_status'] = facts.public_status(facts._result(prefix,
                'CURRENT' if index > 1 else 'UNKNOWN',
                () if index > 1 else ('FACT_PURPOSE_SELECTION_REQUIRED',), event['source_sha256']))
            if index == 1:
                request = facts.Declare(expected_preparation_revision=event['preparation_revision'] - 1,
                    profile=facts.PROFILE, purpose=facts.PURPOSE, reason=event['reason'])
            else:
                request = facts.Confirm(expected_preparation_revision=event['preparation_revision'] - 1,
                    expected_clarification_revision=index - 1, expected_source_sha256=event['source_sha256'],
                    choices=event['choices'], reason=event['reason'])
            if (str(receipt['preparation_id']) != str(parent['id']) or
                    receipt['actor_id'] != principal['id'] or receipt['action'] != event['action'] or
                    type(receipt['revision']) is not int or receipt['revision'] != event['preparation_revision'] or
                    type(receipt['request_key']) is not str or not 1 <= len(receipt['request_key']) <= 200 or
                    not receipt['request_key'].strip() or receipt['request_key'] in seen_keys or
                    receipt['fingerprint'] != facts._hash(dict(preparation_id=str(parent['id']),
                        action=event['action'], **request.model_dump(mode='json'))) or
                    any(not _same(receipt['payload'].get(k), v)
                        for k, v in expected.items())):
                raise ValueError()
            if index == 1 and (event['choices'] != [] or event['selection'] != 'UNKNOWN'):
                raise ValueError()
            seen_events.add(event['id'])
            seen_keys.add(receipt['request_key'])
            previous_revision = event['preparation_revision']
        latest = ledger['events'][-1]
        current_binding = {k: v for k, v in latest['source_snapshot']['binding'].items()
                           if k not in ('authority', 'fact_bundle')}
        if (latest['action'] != 'CONFIRM_FACT_PURPOSE' or latest['selection'] != 'USER_SELECTED_FOR_CASE' or
                not _same(current_binding, binding) or type(latest['choices']) is not list or len(latest['choices']) != 3):
            raise ValueError()
        choices = [facts.Choice.model_validate(x) for x in latest['choices']]
        if {x.field for x in choices} != set(facts.FIELDS) or len({x.assertion_id for x in choices}) != 3:
            raise ValueError()
        current = {}
        original = {}
        for rows, target in ((sources, current), (latest['source_snapshot']['sources'], original)):
            if type(rows) not in (list, tuple) or len(rows) > 60:
                raise ValueError()
            for row in rows:
                id = str(row['id'])
                UUID(id)
                if id in target or row['field_name'] not in facts.FIELDS:
                    raise ValueError()
                target[id] = facts._normal(row)
        selected = []
        for choice in sorted(choices, key=lambda x: x.field):
            id = str(choice.assertion_id)
            row = current.get(id)
            if (row is None or not _same(row, original.get(id)) or row['field_name'] != choice.field or
                    type(row['revision']) is not int or row['revision'] != choice.expected_assertion_revision or
                    row['fingerprint'] != choice.expected_assertion_fingerprint or
                    row['confirmed_by'] != principal['id'] or
                    row['source_kind'] not in ('USER_ASSERTED_SYNTHETIC', 'DOCUMENT_EXTRACT_SYNTHETIC') or
                    type(row['source_ref']) is not dict or row['source_ref'].get('kind') != 'SYNTHETIC' or
                    not row['source_ref'].get('id') or not row['source_ref'].get('revision') or
                    applicable.get(id) is not True or latest['applicable'].get(id) is not True or
                    not _utc(row['valid_from']) <= now < _utc(row['valid_until'])):
                raise ValueError()
            _hash(row['fingerprint'])
            selected.append(row)
        return dict(contract=CONTRACT, purpose=facts.PURPOSE, fields=list(facts.FIELDS),
            source_sha256=facts._hash(dict(binding=binding, decision=latest['decision_sha256'], sources=selected)),
            read_only=True, execution_available=False, qualification='NOT_EVALUATED',
            authenticity='USER_ASSERTED_UNVERIFIED', proof_available=False)
    except (Conflict, ValidationError, ValueError, KeyError, TypeError, AttributeError, IndexError, OverflowError, RecursionError):
        raise Denied('current declared Case fact READ source required') from None


def source_descriptor(store, c, principal, parent):
    """Already authenticated owner; current field READ before any private source.

    Supported fact writes share these field advisory locks. Parent/bundle and
    noncooperating writers are covered by history reader's before/after checks;
    this is deliberately not an all-source atomicity claim.
    """
    store.check_fields(c, principal, list(facts.FIELDS), 'READ')
    facts._field_locks(c, principal['id'])
    store.check_fields(c, principal, list(facts.FIELDS), 'READ')
    try:
        rows = list(store.facts_query(c, principal, list(facts.FIELDS)))
        extra, extra_applicable, _ = bundle.source_state(c, parent)
        rows += extra
        document_ids = [row['evidence_id'] for row in extra]
        if document_ids:
            actors = c.execute('SELECT id,actor_id FROM preparation_evidence WHERE preparation_id=%s AND id=ANY(%s)',
                (parent['id'], [UUID(str(id)) for id in document_ids])).fetchall()
            if ({str(row['id']) for row in actors} != {str(id) for id in document_ids} or
                    any(row['actor_id'] != principal['id'] for row in actors)):
                raise ValueError()
        now = c.execute('SELECT clock_timestamp() now').fetchone()['now']
        applicable = {str(row['id']): _utc(row['valid_from']) <= now < _utc(row['valid_until']) for row in rows}
        applicable.update(extra_applicable)
        receipts = c.execute("SELECT preparation_id,actor_id,revision,action,payload,request_key,fingerprint FROM preparation_events WHERE preparation_id=%s AND action IN ('DECLARE_FACT_PURPOSE','CONFIRM_FACT_PURPOSE') ORDER BY revision,id LIMIT 65", (parent['id'],)).fetchall()
        project(parent, principal, receipts, rows, applicable, now)
        bundle.enforce_locks(c, parent, parent['fact_clarifications']['events'][-1]['choices'], facts._normal(rows))
        store.check_fields(c, principal, list(facts.FIELDS), 'READ')
        return project(parent, principal, receipts, rows, applicable,
            c.execute('SELECT clock_timestamp() now').fetchone()['now'])
    except (Conflict, ValidationError, ValueError, KeyError, TypeError, AttributeError, IndexError, OverflowError, RecursionError):
        raise Denied('current declared Case fact READ source required') from None
