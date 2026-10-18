"""AT21 finite synthetic observations; no official rule approval or live model."""
from datetime import datetime, timezone
from hashlib import sha256
import itertools
import json
from uuid import UUID

from fastapi.testclient import TestClient
from parkweave.api import create_app
import pytest

from parkweave.domain import Rule
from parkweave import synthetic_rule_readiness as sr
from test_preparation import preparation_fixture, filled, headers
from test_synthetic_rule_readiness import simulation, engine, SCOPE, VALID
from test_case_fact_clarifications_integration import authority, business
from test_preview_rules_change_nodevm_actual import bridge


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def test_evaluate_and_or_reuses_independent_kleene_table(tmp_path):
    # Same independent table as test_foundation; never compute oracle via production helpers.
    values = ['TRUE', 'FALSE', 'UNKNOWN']
    expected = {
        'AND': ['TRUE', 'FALSE', 'UNKNOWN', 'FALSE', 'FALSE', 'FALSE', 'UNKNOWN', 'FALSE', 'UNKNOWN'],
        'OR': ['TRUE', 'TRUE', 'TRUE', 'TRUE', 'FALSE', 'UNKNOWN', 'TRUE', 'UNKNOWN', 'UNKNOWN'],
    }
    leaf = {
        'TRUE': dict(kind='EQ', field='employees', expected=17),
        'FALSE': dict(kind='EQ', field='employees', expected=3),
        # No service_need evidence at all: UNKNOWN must not become TRUE.
        'UNKNOWN': dict(kind='EXISTS', field='service_need'),
    }
    fact = dict(id='synthetic-employees', field_name='employees', value=17, unit='people',
                valid_from=VALID['valid_from'], valid_until=VALID['valid_until'], revision=1,
                fingerprint='a' * 64, source_ref=dict(id='synthetic-source', kind='SYNTHETIC', revision='1'))
    rows = []
    for operator, oracle in expected.items():
        for (left, right), want in zip(itertools.product(values, repeat=2), oracle):
            result = sr.evaluate(Rule(kind=operator, children=[leaf[left], leaf[right]]),
                {'sources': [fact]}, [dict(field='employees', assertion_id=fact['id'])],
                {fact['id']: True}, datetime.now(timezone.utc))
            assert result['synthetic_simulated_condition_truth'] == want
            assert [c['truth'] for c in result['conditions']] == [left, right]
            for value, condition in zip((left, right), result['conditions']):
                if value == 'UNKNOWN':
                    assert condition['reason'] == 'MISSING_EVIDENCE' and condition['evidence'] == []
            assert result['qualification_truth'] == 'UNKNOWN'
            assert result['qualification_decision'] == 'NOT_EVALUATED'
            assert result['formal_review'] is False and result['business_publication'] is False
            rows.append(dict(operator=operator, left=left, right=right, expected=want, result=result))
    save(tmp_path / 'at21-evaluate-table.json', dict(
        source_kind='SYNTHETIC_FIXTURE', execution_mode='NO_MODEL_PURE_EVALUATION',
        oracle_source='tests/test_foundation.py::test_independent_three_value_truth_table',
        observations=rows, real_model_calls=0,
        limitation='A proved alternative can make OR TRUE while a missing leaf remains UNKNOWN; no missing leaf itself passes.'))


@pytest.mark.parametrize('want', ['FALSE', 'UNKNOWN'])
def test_original_html_real_asgi_output_has_no_official_approval(request, tmp_path, want):
    if want == 'FALSE':
        f, p, _, _, _ = request.getfixturevalue('simulation')
    else:
        f = request.getfixturevalue('preparation_fixture')
        p = filled(f)
    source_path = tmp_path / 'at21-rule-source'
    source_path.mkdir()
    candidate = engine(source_path, dict(kind='EQ', field='employees', expected=3 if want == 'FALSE' else 17))
    release = candidate.read('fixture-a', SCOPE)['releases'][0]
    binding = sr.RuleBinding(binding_id='at21-' + want.lower(), scope=SCOPE,
        release_id=release['id'], content_sha256=release['content_sha256'], region='REGION_A', epoch=1)
    adapter = sr.SyntheticRuleReadiness(f[0], f[1], candidate,
        sr.SimulationJournal(tmp_path / 'at21.synthetic-readiness.sqlite3'),
        bindings=[binding], enabled_for_isolated_tests=True)
    context = sr.Context(binding_id=binding.binding_id, as_of=datetime.now(timezone.utc).isoformat())
    path = '/api/preparations/' + p['preparation_id'] + '/synthetic-rule-readiness'
    with TestClient(create_app(f[0], synthetic_rule_readiness=adapter)) as api:
        current = api.get(path, params=context.model_dump(), headers=headers(f[2]))
        assert current.status_code == 200, current.text
        value = current.json()
        assert value['result']['synthetic_simulated_condition_truth'] == want
        if want == 'UNKNOWN':
            assert value['sources']['purpose_status']['state'] == 'NOT_DECLARED'
            assert all(c['truth'] == 'UNKNOWN' and c['reason'] == 'MISSING_EVIDENCE'
                       and c['evidence'] == [] for c in value['result']['conditions'])
        before_business, before_authority = business(f), authority(f)
        journal = adapter.journal.path.read_bytes()
        with f[1].connect() as c:
            initial_counts = {table: c.execute('SELECT count(*) n FROM ' + table).fetchone()['n']
                              for table in ('runs', 'cases', 'preparations', 'fact_assertions', 'run_assignments')}
        params = dict(mode='b_at21_' + want.lower(), preparation_id=p['preparation_id'],
            binding_id=context.binding_id,
            as_of=datetime.fromisoformat(context.as_of).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M'),
            expected_truth=want, expected_purpose_status=value['sources']['purpose_status']['state'])
        evidence = bridge(api, f, p, params, 'fixture-a')
        output = evidence['result']
        assert output['statusText'] == '仅开发模拟，SYNTHETIC_REVIEWED不代表正式审核。'
        assert '开发模拟条件：' + want + '；资格 UNKNOWN / NOT_EVALUATED' in output['visibleText']
        assert '未经真实性核验' in output['visibleText']
        assert all(t['method'] == 'GET' for t in evidence['traffic'])
        actual = [t['body'] for t in evidence['traffic'] if '/synthetic-rule-readiness?' in t['path']]
        assert len(actual) == 1
        for item in (actual[0], actual[0]['result']):
            assert item['formal_review'] is False and item['business_publication'] is False
            assert item['qualification_truth'] == 'UNKNOWN' and item['qualification_decision'] == 'NOT_EVALUATED'
            assert item['case_goal_completed'] is False
        assert actual[0]['result']['synthetic_simulated_condition_truth'] == want
        if want == 'UNKNOWN':
            assert all(c['reason'] == 'MISSING_EVIDENCE' and c['truth'] == 'UNKNOWN'
                       for c in actual[0]['result']['conditions'])
        assert business(f) == before_business and authority(f) == before_authority
        assert adapter.journal.path.read_bytes() == journal
        run = api.get('/api/runs/' + p['run_id'], headers=headers(f[2])).json()
        assert run['model_mode'] == 'MODEL_MOCK'
        assert run['case']['external_acceptance'] == 'NOT_SUBMITTED'
        save(tmp_path / 'at21-original-html-output.json', dict(
            source_kind='SYNTHETIC_FIXTURE', execution_mode='OWNED_LINUX_PG_ASGI_AND_NODEVM_DOM_SUBSTITUTE',
            model_mode=run['model_mode'], real_model_calls=0,
            mock_review_publication='Original isolated CandidateEngine; not actual rule-review or catalog authority',
            fixture_initial_counts=initial_counts, fixture_setup_outside_observed_read_window=True,
            expected_truth=want, evidence=evidence, read_only_business_unchanged=True,
            read_only_seven_authority_tables_unchanged=True,
            simulation_journal_unchanged_sha256=sha256(journal).hexdigest(),
            browser='NOT_RUN', native_windows='NOT_RUN', real_business='NOT_RUN'))
