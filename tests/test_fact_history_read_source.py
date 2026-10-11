"""Pure declared-source contract: persisted evidence, never execution proof."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import json
import pytest

from parkweave import fact_history_read_source as read, case_fact_clarifications as facts, preparation as prep
from parkweave.store import Denied


def sample():
    now = datetime(2026, 10, 11, tzinfo=timezone.utc)
    principal = dict(id='SYNTHETIC-owner', park_id='park-a', org_id='org-a', role='enterprise_operator', active=True)
    parent = dict(id=uuid4(), case_id=uuid4(), run_id=uuid4(), owner_id=principal['id'],
        park_id=principal['park_id'], org_id=principal['org_id'], namespace='SYNTHETIC',
        service_id=prep.SERVICE, service_version=1, revision=3, goal='SYNTHETIC Case', request_intent=None)
    sources = [dict(id=str(uuid4()), evidence_id=str(uuid4()), field_name=field,
        value=17 if field == 'employees' else 'PRIVATE_VALUE_' + field,
        unit='people' if field == 'employees' else 'text',
        source_ref=dict(id='PRIVATE_SOURCE_' + field, kind='SYNTHETIC', revision='1'),
        source_kind='USER_ASSERTED_SYNTHETIC', source_excerpt='PRIVATE_EXCERPT_' + field,
        valid_from=(now-timedelta(hours=1)).isoformat(), valid_until=(now+timedelta(hours=1)).isoformat(),
        revision=1, fingerprint=facts._hash(field), confirmed_by=principal['id']) for field in facts.FIELDS]
    applicable = {row['id']: True for row in sources}
    snapshot = dict(binding=dict(facts._binding(parent), authority={'OLD_EXECUTE': True}), sources=deepcopy(sources))
    ledger = dict(version=1, profile=facts.PROFILE, purpose=facts.PURPOSE, required_fields=list(facts.FIELDS), revision=2, events=[])
    receipts = []
    for i in (1, 2):
        choices = [] if i == 1 else [dict(field=row['field_name'], assertion_id=row['id'],
            expected_assertion_revision=row['revision'], expected_assertion_fingerprint=row['fingerprint']) for row in sources]
        event = dict(id=str(uuid4()), revision=i, preparation_revision=i+1, actor_id=principal['id'],
            action='DECLARE_FACT_PURPOSE' if i == 1 else 'CONFIRM_FACT_PURPOSE', reason='SYNTHETIC explicit owner selection',
            decided_at=(now-timedelta(minutes=1)).isoformat(), source_snapshot=deepcopy(snapshot),
            source_sha256=facts._hash(snapshot), applicable=deepcopy(applicable), choices=choices,
            selection='UNKNOWN' if i == 1 else 'USER_SELECTED_FOR_CASE', authenticity='USER_ASSERTED_UNVERIFIED')
        event['decision_sha256'] = facts._hash(event)
        ledger['events'].append(event)
        request = facts.Declare(expected_preparation_revision=i, profile=facts.PROFILE, purpose=facts.PURPOSE, reason=event['reason']) if i == 1 else facts.Confirm(expected_preparation_revision=i, expected_clarification_revision=1, expected_source_sha256=event['source_sha256'], choices=choices, reason=event['reason'])
        receipts.append(dict(preparation_id=parent['id'], actor_id=principal['id'], revision=i+1, action=event['action'],
            request_key='synthetic-' + str(i), fingerprint=facts._hash(dict(preparation_id=str(parent['id']), action=event['action'], **request.model_dump(mode='json'))),
            payload=dict(preparation_id=str(parent['id']), case_id=str(parent['case_id']), run_id=str(parent['run_id']),
                revision=i+1, actor_id=principal['id'], action=event['action'], decision_ref=event['id'], decision_sha256=event['decision_sha256'],
                required_fields=list(facts.FIELDS), public_status=facts.public_status(facts._result(dict(ledger, revision=i),
                    'UNKNOWN' if i == 1 else 'CURRENT', ('FACT_PURPOSE_SELECTION_REQUIRED',) if i == 1 else (), event['source_sha256'])))))
    parent['fact_clarifications'] = ledger
    return parent, principal, receipts, sources, applicable, now


def test_exact_projection_no_values_or_proof_and_no_input_mutation():
    args = sample()
    before = deepcopy(args)
    result = read.project(*args)
    assert result == dict(contract=read.CONTRACT, purpose=facts.PURPOSE, fields=list(facts.FIELDS),
        source_sha256=result['source_sha256'], read_only=True, execution_available=False,
        qualification='NOT_EVALUATED', authenticity='USER_ASSERTED_UNVERIFIED', proof_available=False)
    raw = json.dumps(result)
    for row in args[3]:
        for secret in (row['id'], row['evidence_id'], row['source_excerpt'], row['source_ref']['id'], str(row['value'])):
            assert secret not in raw
    assert args == before


@pytest.mark.parametrize('change', ['owner','park','org','case','run','inactive','role','purpose','fields','bool_version',
    'missing_ledger','declared_only','receipt_missing','receipt_extra','receipt_case','receipt_actor','receipt_revision',
    'receipt_decision','receipt_status','receipt_fingerprint','receipt_key','ledger_rehash','duplicate_event',
    'duplicate_choice','choice_missing','unknown_field','wrong_source','source_missing','source_duplicate','value',
    'excerpt','source_ref','fingerprint','revision','bool_revision','confirmed_by','assumption','unknown_kind',
    'expired','future','naive','nonutc','revoked','snapshot_hash','source_binding','selection','event_time','request_changed'])
def test_missing_conflicting_or_changed_contract_denies(change):
    parent, p, receipts, sources, applicable, now = args = sample()
    ledger = parent['fact_clarifications'];event = ledger['events'][-1]
    if change in ('owner','park','org'):p[{'owner':'id','park':'park_id','org':'org_id'}[change]] = 'other'
    elif change in ('case','run'):parent[change + '_id'] = uuid4()
    elif change == 'inactive':p['active'] = False
    elif change == 'role':p['role'] = 'park_specialist'
    elif change == 'purpose':ledger['purpose'] = 'OTHER'
    elif change == 'fields':ledger['required_fields'] = ['region']
    elif change == 'bool_version':ledger['version'] = True
    elif change == 'missing_ledger':parent['fact_clarifications'] = None
    elif change == 'declared_only':ledger['events'].pop();ledger['revision'] = 1;receipts.pop()
    elif change == 'receipt_missing':receipts.pop()
    elif change == 'receipt_extra':receipts.append(deepcopy(receipts[-1]))
    elif change.startswith('receipt_'):
        key = change.removeprefix('receipt_')
        if key == 'case':receipts[-1]['payload']['case_id'] = str(uuid4())
        elif key == 'actor':receipts[-1]['actor_id'] = 'other'
        elif key == 'revision':receipts[-1]['revision'] = 42
        elif key == 'decision':receipts[-1]['payload']['decision_sha256'] = '0'*64
        elif key == 'status':receipts[-1]['payload']['public_status']['state'] = 'UNKNOWN'
        elif key == 'fingerprint':receipts[-1]['fingerprint'] = '0'*64
        elif key == 'key':receipts[-1]['request_key'] = receipts[0]['request_key']
    elif change == 'ledger_rehash':
        event['reason'] = 'SYNTHETIC forged replacement';event['decision_sha256'] = facts._hash({k:v for k,v in event.items() if k != 'decision_sha256'})
    elif change == 'duplicate_event':event['id'] = ledger['events'][0]['id']
    elif change == 'duplicate_choice':event['choices'][1] = deepcopy(event['choices'][0])
    elif change == 'choice_missing':event['choices'].pop()
    elif change == 'unknown_field':event['choices'][0]['field'] = 'private_salary'
    elif change == 'wrong_source':event['choices'][0]['assertion_id'] = str(uuid4())
    elif change == 'source_missing':sources.pop()
    elif change == 'source_duplicate':sources.append(deepcopy(sources[0]))
    elif change in ('value','excerpt','source_ref','fingerprint','revision','bool_revision','confirmed_by','assumption','unknown_kind'):
        key = {'excerpt':'source_excerpt','bool_revision':'revision','assumption':'source_kind','unknown_kind':'source_kind'}.get(change, change)
        sources[0][key] = {'source_ref':dict(id='other',kind='SYNTHETIC',revision='2'), 'revision':2,
            'bool_revision':True,'assumption':'ASSUMPTION_SYNTHETIC','unknown_kind':'REAL_FACT'}.get(change, 'changed')
    elif change in ('expired','future','naive','nonutc'):
        sources[0]['valid_until' if change == 'expired' else 'valid_from'] = {
            'expired':now.isoformat(),'future':(now+timedelta(minutes=1)).isoformat(),
            'naive':now.replace(tzinfo=None).isoformat(),'nonutc':'2026-10-10T00:00:00+01:00'}[change]
    elif change == 'revoked':applicable[sources[0]['id']] = False
    elif change == 'snapshot_hash':event['source_sha256'] = '0'*64
    elif change == 'source_binding':event['source_snapshot']['binding']['owner_id'] = 'other'
    elif change == 'selection':event['selection'] = 'AUTOMATIC'
    elif change == 'event_time':event['decided_at'] = (now+timedelta(minutes=1)).isoformat()
    elif change == 'request_changed':parent['goal'] = 'SYNTHETIC new request'
    with pytest.raises(Denied):read.project(*args)


def test_explicit_choice_resolves_competing_sources_only_for_this_case():
    args = sample()
    extra = deepcopy(args[3][0]);extra['id'] = str(uuid4());extra['value'] = 'SYNTHETIC competitor'
    args[3].append(extra);args[4][extra['id']] = True
    assert read.project(*args)['execution_available'] is False


def test_absolute_expiry_with_intact_rows_and_unchanged_hash():
    args = list(sample());args[-1] += timedelta(hours=1)
    with pytest.raises(Denied):read.project(*args)


@pytest.mark.parametrize('key,value', [('enabled',1),('satisfied',0),('revision',True)])
def test_receipt_nested_types_are_exact(key, value):
    args = sample();args[2][0]['payload']['public_status'][key] = value
    with pytest.raises(Denied):read.project(*args)


def test_selected_integer_value_cannot_be_replaced_by_equal_float():
    args = sample()
    next(row for row in args[3] if row['field_name'] == 'employees')['value'] = 17.0
    with pytest.raises(Denied):read.project(*args)
