"""Pure parser adversarial evidence: no provider, socket, database or gateway."""
from copy import deepcopy
import json

import pytest

from parkweave.planner_proposal import (
    MAX_BYTES, ProposalValidationError, validate_proposal,
)


@pytest.fixture
def document():
    adapters = ['preparation', 'case-resources', 'dispatch', 'executor-receipts', 'case-lifecycle']
    steps = []
    for index, adapter in enumerate(adapters):
        identifier = f'P{index + 1}'
        steps.append(dict(
            id=identifier, adapter=adapter, revision=1, adapter_ref=adapter, adapter_revision=1,
            depends_on=[f'P{index}'] if index else [],
            responsibility='企业经办人', preconditions='当前原授权与来源', output='本地预览', acceptance='原入口核对',
            request_service_ref='original-service', request_service_version=1,
            input='当前资料', actions=[dict(method='POST', path='/original/{preparation_id}', role='enterprise_operator', commands=['EXPLICIT'])],
            issues=[], correction='原入口补正', executable=False,
        ))
    return dict(
        schema_version=1, origin='SYNTHETIC_UNTRUSTED_CANDIDATE', provider_enabled=False,
        binding=dict(preparation_id='prep', case_id='case', run_id='run', preparation_revision=2,
                     request_revision=1, source_sha256='a' * 64, catalog_sha256='b' * 64, registry_sha256='c' * 64),
        required_goals=['LOCAL_CASE_RECORD_RECHECK', 'UNSUPPORTED_REAL_RESULT'],
        goal_coverage=[dict(goal='LOCAL_CASE_RECORD_RECHECK', status='UNKNOWN', steps=['P1', 'P2', 'P3', 'P4', 'P5']),
                       dict(goal='UNSUPPORTED_REAL_RESULT', status='UNSUPPORTED', steps=[])],
        steps=steps, constraints=dict(state='UNKNOWN', hard_conditions=[dict(description='禁止外部角色', satisfied=False)]),
        global_requirements=dict(requirements=['完整保留所有硬条件'], state='UNKNOWN'),
    )


def wire(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def reject(raw, expected):
    with pytest.raises(ProposalValidationError) as caught:
        validate_proposal(raw, expected)
    assert caught.value.code == 'INVALID_PLANNER_PROPOSAL'
    assert str(caught.value) == 'INVALID_PLANNER_PROPOSAL'


@pytest.mark.parametrize('bytes_input', [False, True])
def test_exact_unknown_unsupported_preserved_and_detached(document, bytes_input):
    raw = wire(document)
    result = validate_proposal(raw.encode() if bytes_input else raw, document)
    assert result == document
    assert result is not document
    assert result['goal_coverage'][0]['status'] == 'UNKNOWN'
    assert result['goal_coverage'][1]['status'] == 'UNSUPPORTED'
    result['steps'][0]['actions'][0]['commands'].append('NOT_EXECUTED')
    assert document['steps'][0]['actions'][0]['commands'] == ['EXPLICIT']


def test_object_key_order_is_not_authority(document):
    reordered = dict(reversed(list(document.items())))
    assert validate_proposal(wire(reordered), document) == document


@pytest.mark.parametrize('mutation', [
    lambda d: d.update(extra='execute'),
    lambda d: d['binding'].update(extra='grant'),
    lambda d: d['binding'].update(source_sha256='d' * 64),
    lambda d: d['binding'].update(catalog_sha256='d' * 64),
    lambda d: d['binding'].update(registry_sha256='d' * 64),
    lambda d: d['binding'].update(case_id='another-case'),
    lambda d: d['binding'].update(run_id='another-run'),
    lambda d: d['binding'].update(request_revision=2),
    lambda d: d.update(schema_version=True),
    lambda d: d['binding'].update(request_revision=True),
    lambda d: d['binding'].update(request_revision=1.0),
    lambda d: d.update(provider_enabled=0),
    lambda d: d.update(provider_enabled=True),
    lambda d: d['required_goals'].pop(),
    lambda d: d['required_goals'].reverse(),
    lambda d: d['goal_coverage'].pop(),
    lambda d: d['goal_coverage'][0].update(status='SUPPORTED_PREVIEW'),
    lambda d: d['goal_coverage'][1].update(status='SUPPORTED_PREVIEW'),
    lambda d: d['steps'][0].update(id='P6'),
    lambda d: d['steps'][0].update(adapter='gateway'),
    lambda d: d['steps'][0].update(revision=2),
    lambda d: d['steps'][0].update(revision=True),
    lambda d: d['steps'][0].update(adapter_revision=1.0),
    lambda d: d['steps'][0].update(adapter_ref='provider'),
    lambda d: d['steps'][0]['actions'][0].update(path='/new-grant'),
    lambda d: d['steps'][0]['actions'][0].update(role='admin'),
    lambda d: d['steps'][0].update(executable=True),
    lambda d: d['steps'][0].update(output='business completed'),
    lambda d: d['steps'][0].update(extra='execute'),
    lambda d: d['steps'][4].update(depends_on=[]),
    lambda d: d['steps'][4].update(depends_on=['P99']),
    lambda d: d['steps'][4].update(depends_on=['P4', 'P4']),
    lambda d: d['steps'][4].update(depends_on=[4]),
    lambda d: d['steps'][0].update(depends_on=['P5']),
    lambda d: d['steps'].append(deepcopy(d['steps'][0])),
    lambda d: d['steps'].pop(0),
    lambda d: d['constraints']['hard_conditions'].clear(),
    lambda d: d['constraints']['hard_conditions'][0].update(satisfied=True),
    lambda d: d['global_requirements']['requirements'].clear(),
])
def test_adversarial_contract_changes_fail_closed(document, mutation):
    changed = deepcopy(document)
    mutation(changed)
    reject(wire(changed), document)


@pytest.mark.parametrize('raw', [
    '', '[]', 'null', '{}', '{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}',
    '{"x":-Infinity}', '{"x":1e999}', '{"x":', '```json\n{}\n```',
    b'\xff', '\ufeff{}', {'not': 'raw'}, bytearray(b'{}'),
    '{"x":"\\ud800"}', '[' * 2000 + '0' + ']' * 2000,
])
def test_invalid_wire_failures_do_not_echo_output(document, raw):
    reject(raw, document)


def test_duplicate_nested_key_even_equal_value_is_rejected(document):
    raw = wire(document).replace('"source_sha256":', '"source_sha256":"' + 'a' * 64 + '","source_sha256":', 1)
    reject(raw, document)


def test_duplicate_root_key_even_equal_value_is_rejected(document):
    reject('{"schema_version":1,' + wire(document)[1:], document)


@pytest.mark.parametrize('mode', ['oversize', 'utf8_bytes', 'depth', 'nodes'])
def test_limits_are_measured_and_enforced(document, mode):
    if mode == 'oversize':
        reject(' ' * (MAX_BYTES + 1), document)
    elif mode == 'utf8_bytes':
        raw = '"' + '企' * (MAX_BYTES // 2) + '"'
        assert len(raw) < MAX_BYTES < len(raw.encode())
        reject(raw, document)
    else:
        changed = deepcopy(document)
        if mode == 'depth':
            child = []
            for _ in range(34):
                child = [child]
            changed['constraints'] = child
        else:
            changed['constraints'] = [0] * 4097
        # Even a caller accidentally supplying the same overlarge tree is rejected.
        reject(wire(changed), changed)


@pytest.mark.parametrize('mode', ['cycle', 'missing', 'duplicate', 'unsupported'])
def test_graph_validation_independent_of_contract_equality(document, mode):
    changed = deepcopy(document)
    if mode == 'cycle':
        changed['steps'][0]['depends_on'] = ['P5']
    elif mode == 'missing':
        changed['steps'][4]['depends_on'] = ['P99']
    elif mode == 'duplicate':
        changed['steps'][1]['id'] = 'P1'
    else:
        changed['steps'][0]['revision'] = 2
    reject(wire(changed), changed)


def test_empty_unsupported_graph_is_preserved(document):
    document['steps'] = []
    document['required_goals'] = ['UNSUPPORTED_REAL_RESULT']
    document['goal_coverage'] = [dict(goal='UNSUPPORTED_REAL_RESULT', status='UNSUPPORTED', steps=[])]
    assert validate_proposal(wire(document), document) == document


def test_validator_does_not_read_credentials_or_issue_http_or_socket(document, monkeypatch):
    import os
    import socket
    import httpx

    def forbidden(*args, **kwargs):
        pytest.fail('pure proposal validation attempted external IO')

    monkeypatch.setattr(os, 'getenv', forbidden)
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(httpx.Client, 'request', forbidden)
    assert validate_proposal(wire(document), document) == document
    changed = deepcopy(document)
    changed['steps'][0]['actions'][0]['path'] = '/execute-now'
    reject(wire(changed), document)


def test_all_original_registered_adapter_contracts_accept_when_fresh(document):
    # Reuse the actual local registered compile contract, never an API/PG write.
    from parkweave import bounded_planning as bp
    coverage, steps = bp.compile(['LOCAL_CASE_RECORD_RECHECK'])
    for step in steps:
        step.update(adapter_ref=step['adapter'], adapter_revision=step['revision'],
                    actions=deepcopy(bp.ACTIONS[step['id']]), executable=False)
    document.update(required_goals=['LOCAL_CASE_RECORD_RECHECK'], goal_coverage=coverage, steps=steps)
    assert validate_proposal(wire(document), document) == document
