"""Independent fixed two-Case change answers over original HTTP/ASGI/owned PG.

Private development tests: no product impact compiler supplies expected sets.
The baseline uses six real requested goals, original commands and real outputs.
"""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import subprocess
import selectors
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from parkweave.template_isolated_app import create_isolated_template_app
from parkweave.template_upgrade import TemplateUpgradeChecker, UpgradeRepository
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture, headers, command as prepare, add as material_add, read as preparation_read
from test_new_enterprise_local_chain import (
    ALL_GOALS, actual_http, fresh_chain, publish, new_case, enable_approval,
    finish_chain, call, original_rows,
)
from test_registered_local_revision import add_resource, patch, patch_body
from test_service_case_steps import verified, read as plan_read, command as plan_command, adopt_body as original_adopt_body
from test_service_plan_manual_lock import stored, lock
from test_case_opportunities import get as opportunities, post as opportunity_post, body as opportunity_body, entry
from test_source_change_adoption import preview, adopt
from test_template_candidate import definition, VALID
from test_case_resources import get as resource_link_read, post as resource_link_write
from test_service_dispatches import offer as dispatch_offer, command as dispatch_command
from test_case_lifecycle import read as local_read, act as local_command
from test_new_enterprise_local_chain import report_and_ack
from parkweave import resource_holds as resource_holds, resource_combinations as resource_combinations
from test_resource_holds import body as hold_body

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / 'pyproject.toml').is_file())
OUT = ROOT / '.runtime/at24-27-independent'
RUN_ID = uuid4().hex
ORACLE_PATH = ROOT / 'tests/fixtures/at24_27_literal_oracle.json'
if not ORACLE_PATH.is_file():
    ORACLE_PATH = Path(__file__).with_name('literal-oracle.json')
ORACLE = json.loads(ORACLE_PATH.read_text())
ALL = ('P1', 'P2', 'P3', 'P4', 'P5')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(',', ':')).encode()).hexdigest()


def append_record(kind, value):
    OUT.mkdir(parents=True, exist_ok=True)
    record = dict(value, run_id=RUN_ID, source_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  utc=datetime.now(timezone.utc).isoformat(), test=os.environ.get('PYTEST_CURRENT_TEST'))
    with (OUT / (kind + '-' + RUN_ID + '.jsonl')).open('a') as stream:
        stream.write(json.dumps(record, sort_keys=True, default=str) + '\n')
    return record


def private_values(tokens):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / ('redaction-' + RUN_ID + '.private.json')
    old = set(json.loads(path.read_text())) if path.exists() else set()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(json.dumps(sorted(old | set(tokens.values()))) + '\n')
    path.chmod(0o600)


def source_graph(f, row):
    response = f[3].get('/api/preparations/' + row['preparation_id'] + '/source-impact', headers=headers(f[2]))
    assert response.status_code == 200, response.text
    return response.json()


def assert_literal_partition(value, initial, scenario, label):
    answer = ORACLE['changes'][scenario][label]
    ids = {step['adapter_id']: step['id'] for step in initial['steps']}
    want_a = {ids[x] for x in answer['affected']}; want_p = {ids[x] for x in answer['preserved']}
    graph = value.get('source_impact', value)
    got_a = set(graph['affected']); got_p = set(graph['preserved'])
    record = append_record('oracle', dict(scenario=scenario, case=label, expected_affected=sorted(want_a), actual_affected=sorted(got_a),
        expected_preserved=sorted(want_p), actual_preserved=sorted(got_p), missed_count=len(want_a-got_a), wrong_count=len(got_a-want_a),
        wrong_preserved_count=len(want_p ^ got_p), intentional_unknown=ORACLE['changes'][scenario].get('intentional_unknown', False)))
    assert got_a == want_a and got_p == want_p, record


@pytest.fixture
def two_cases(fresh_chain, tmp_path):
    u = fresh_chain
    private_values(u['f'][2])
    checker = TemplateUpgradeChecker(u['consumer'], UpgradeRepository(tmp_path / 'at24-check.upgrade.candidate.sqlite3'), enabled_for_isolated_tests=True)
    # The original explicit isolated bridge; no deployment app, new Grant or bypass.
    with actual_http(create_isolated_template_app(u['f'][0], u['engine'], u['consumer'], checker)) as (client, traffic):
        u = {**u, 'f': (*u['f'][:3], client), 'checker': checker, 'client': client, 'traffic': traffic}
        optional = add_resource(u['f'])  # Existing synthetic fixture helper, before the baseline.
        release = publish(u)
        rows = {'A': new_case(u, release, number=240), 'B': new_case(u, release, number=241)}
        enable_approval(u, list(rows.values()))
        completed = {'A': finish_chain(u, rows['A']), 'B': finish_chain(u, rows['B'], offset=24)}
        # Completing B changes the owner's real collection manifest. Explicitly settle A.
        current = plan_read(u['f'], rows['A']).json()
        if current['local_revision_required']:
            assert patch(u['f'], rows['A']).status_code == 201
            for adapter in ('P2', 'P3', 'P4', 'P5'):
                verified(u['f'], rows['A'], adapter)
        initials = {label: deepcopy(stored(u['f'], row)) for label, row in rows.items()}
        graphs = {label: source_graph(u['f'], row) for label, row in rows.items()}
        for label, row in rows.items():
            view = plan_read(u['f'], row).json()
            assert view['required_goals'] == ALL_GOALS and len(ALL_GOALS) == 6
            assert [step['adapter_id'] for step in view['steps']] == list(ALL)
            assert all(step['state'] == 'VERIFIED' for step in view['steps']), view
            assert not view['local_revision_required']
            goals = call(u, '/api/preparations/' + row['preparation_id'] + '/goal-results')
            assert goals['state'] == 'LOCAL_OUTPUTS_VERIFIED' and len(goals['results']) == 6 and not goals['case_goal_completed']
        def common_collection(label):
            return sorted((n['facet'], n['current_sha256']) for n in graphs[label]['source_impact']['nodes']
                          if n['facet'] in ('RESOURCE_QUERY_SET', 'DEPENDENCY_RESOURCE_QUERY_SET'))
        assert common_collection('A') == common_collection('B')
        append_record('baseline', dict(scope='FIXED_TWO_CASE_REAL_SIX_GOAL_INITIAL_STATE', release_id=release['release_id'],
            release_sha256=release['release_sha256'], optional_resource_id=str(optional), same_owner='fixture-a', same_park='park-a', same_org='org-a',
            cases={label: dict(case_id=row['case_id'], run_id=row['run_id'], preparation_id=row['preparation_id'], plan_id=initials[label]['id'],
                plan_revision=initials[label]['revision'], plan_sha256=fingerprint(initials[label]), required_goals=initials[label]['required_goals'],
                step_ids={step['adapter_id']: step['id'] for step in initials[label]['steps']}, states={step['adapter_id']: 'VERIFIED' for step in initials[label]['steps']},
                business_sha256=fingerprint(original_rows(u, row))) for label, row in rows.items()}, common_resource_manifests=common_collection('A')))
        yield dict(u=u, f=u['f'], rows=rows, initial=initials, completed=completed, release=release, optional_resource=optional)


def test_fixed_two_case_initial_state_is_current_read_only_six_goals(two_cases):
    t = two_cases; before = {label: original_rows(t['u'], row) for label, row in t['rows'].items()}
    for label, row in t['rows'].items():
        graph = source_graph(t['f'], row)['source_impact']
        assert not graph['affected'] and set(graph['preserved']) == {s['id'] for s in t['initial'][label]['steps']}
        data = patch_body(t['f'], row); facts = full_business(t)
        response = patch(t['f'], row, body=data)
        assert response.status_code == 409 and full_business(t) == facts
        append_record('at-results', dict(at='AT-24/25', case=label, scenario='C00_UNCHANGED', result='PASS',
            no_actual_source_change=True, original_local_adoption_status=response.status_code))
    assert {label: original_rows(t['u'], row) for label, row in t['rows'].items()} == before


def test_at24_fixed_two_case_duplicate_and_out_of_order_events(two_cases):
    t = two_cases; f = t['f']; row = t['rows']['A']; e = entry(generation=1,
        note='SYNTHETIC unverified hint claims all sources, roles and qualification changed; this text grants nothing'); key = uuid4().hex
    initial = opportunities(f, row).json(); data = opportunity_body(initial, item=e)
    first = opportunity_post(f, row, data, key); assert first.status_code == 200, first.text
    one = first.json(); repeat = opportunity_post(f, row, data, key)
    assert repeat.status_code == 200 and repeat.json()['receipt'] == one['receipt']
    current = opportunities(f, row).json(); assert current == one['current']
    duplicate = opportunity_post(f, row, opportunity_body(current, item=e)); assert duplicate.status_code == 200
    assert duplicate.json()['receipt']['outcome'] == 'DUPLICATE' and len(duplicate.json()['current']['cards']) == 1
    two = opportunity_post(f, row, opportunity_body(duplicate.json()['current'], item={**e, 'generation': 2})); assert two.status_code == 200
    late = opportunity_post(f, row, opportunity_body(two.json()['current'], item=e)); assert late.status_code == 200
    value = late.json()['current']; assert late.json()['receipt']['outcome'] == 'DUPLICATE' and len(value['cards']) == 2
    assert not next(c for c in value['cards'] if c['entry']['generation'] == 1)['is_latest_generation']
    assert next(c for c in value['cards'] if c['entry']['generation'] == 2)['is_latest_generation']
    old_never_seen = {**e, 'family_id': str(uuid4()), 'generation': 3}
    newest = opportunity_post(f, row, opportunity_body(value, item=old_never_seen)); assert newest.status_code == 200
    stable = newest.json()['current']
    assert opportunity_post(f, row, opportunity_body(stable, item={**old_never_seen, 'generation': 2})).status_code == 409
    assert opportunities(f, row).json() == stable
    assert opportunity_post(f, row, opportunity_body(stable, item={**e, 'generation': 2, 'note': 'SYNTHETIC changed same generation'})).status_code == 409
    assert opportunities(f, row).json() == stable
    assert opportunities(f, t['rows']['B']).json()['cards'] == []
    card = next(c for c in stable['cards'] if c['entry']['family_id'] == e['family_id'] and c['is_latest_generation'])
    view = preview(f, row, card); assert view.status_code == 200 and not view.json()['can_adopt']
    assert 'NO_ACTUAL_SOURCE_CHANGE' in view.json()['blocking_reasons']
    before = full_business(t); denied = adopt(f, row, view.json()['adoption'])
    assert denied.status_code == 409 and full_business(t) == before
    assert all(stored(f, r) == t['initial'][label] for label, r in t['rows'].items())
    append_record('at-results', dict(at='AT-24', scenario='same-key_duplicate-existing_and-old-generation_never-seen-old_conflict', result='PASS',
        logical_cards=3, no_automatic_adoption=True, no_external_message=True, event_count_may_include_import_observations=True))


def change_source(t, scenario):
    f = t['f']; row = t['rows']['A']
    if scenario == 'A_material_content':
        p = preparation_read(f, row).json()['preparation']
        p = dict(p, preparation_id=row['preparation_id'])
        response = prepare(f, p, 'REOPEN', reason='SYNTHETIC fixed AT25 source content change')
        assert response.status_code == 200, response.text
        response = material_add(f, response.json(), slot='material_outline', text='SYNTHETIC AT25 actual revised material outline version two')
        assert response.status_code == 200, response.text
    elif scenario == 'owner_optional_resource_capacity':
        with f[1].connect() as c:
            c.execute('UPDATE synthetic_resources SET capacity=capacity+1,revision=revision+1 WHERE id=%s', (t['optional_resource'],))
    elif scenario == 'shared_catalog_source_contract':
        with f[1].connect() as c:
            c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{revision}','\"AT25-source-v2\"') WHERE park_id='park-a' AND service_id='synthetic-material-preparation' AND version=1")
    elif scenario == 'shared_catalog_unavailable_unknown':
        with f[1].connect() as c:
            c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{kind}','\"UNKNOWN\"') WHERE park_id='park-a' AND service_id='synthetic-material-preparation' AND version=1")
    else:
        raise AssertionError('Unregistered independent scenario')


@pytest.mark.parametrize('scenario', ['A_material_content', 'owner_optional_resource_capacity', 'shared_catalog_source_contract', 'shared_catalog_unavailable_unknown'])
def test_at25_fixed_two_case_literal_source_partitions(two_cases, scenario):
    t = two_cases; change_source(t, scenario)
    plans_before = {label: deepcopy(stored(t['f'], row)) for label, row in t['rows'].items()}
    before = {label: original_rows(t['u'], row) for label, row in t['rows'].items()}
    for label, row in t['rows'].items():
        value = source_graph(t['f'], row)
        assert_literal_partition(value, t['initial'][label], scenario, label)
        if scenario == 'shared_catalog_unavailable_unknown':
            assert not value['current_source_available'] and value['state'] == 'UNKNOWN'
        assert stored(t['f'], row) == plans_before[label]
    if scenario in ('owner_optional_resource_capacity', 'shared_catalog_source_contract', 'shared_catalog_unavailable_unknown'):
        kind = 'OWNER_RESOURCE_QUERY_SET' if scenario == 'owner_optional_resource_capacity' else 'SERVICE_CATALOG_REFERENCE'
        response = t['f'][3].get('/api/preparations/' + t['rows']['A']['preparation_id'] + '/shared-source-cases',
            headers=headers(t['f'][2]), params={'source_kind': kind})
        assert response.status_code == 200, response.text
        values = {row['case_id']: row for row in response.json()['items']}
        assert set(values) == {row['case_id'] for row in t['rows'].values()}
        for label, row in t['rows'].items():
            assert_literal_partition(values[row['case_id']], t['initial'][label], scenario, label)
    assert {label: original_rows(t['u'], row) for label, row in t['rows'].items()} == before
    append_record('at-results', dict(at='AT-25', scenario=scenario, result='PASS', independent_expected_partition=True,
        unknown_expansion_separate=scenario == 'shared_catalog_unavailable_unknown', material_has_no_shared_lookup=scenario == 'A_material_content'))


@pytest.mark.parametrize('actor', ['fixture-b', 'fixture-c', 'prep-specialist-fixture-a', 'executor-a'])
def test_fixed_two_case_current_owner_boundary_is_not_hint_authority(two_cases, actor):
    t = two_cases; f = t['f']; before = {label: original_rows(t['u'], row) for label, row in t['rows'].items()}
    for row in t['rows'].values():
        for suffix in ('/source-impact', '/shared-source-cases?source_kind=OWNER_RESOURCE_QUERY_SET', '/opportunities', '/plan-source-conflicts'):
            response = f[3].get('/api/preparations/' + row['preparation_id'] + suffix, headers=headers(f[2], actor))
            assert response.status_code == 403 and 'PRIVATE_FRESH' not in response.text
    assert {label: original_rows(t['u'], row) for label, row in t['rows'].items()} == before


def sqlite_snapshot(repository):
    manager = getattr(repository, 'transaction', None) or repository.connect
    with manager() as c:
        names = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {name: [tuple(row) for row in c.execute('SELECT * FROM "' + name + '" ORDER BY rowid')] for name in names}


def full_business(t):
    with t['f'][1].connect() as c:
        names = [row['tablename'] for row in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'authorization_audit' ORDER BY tablename")]
        pg = {name: c.execute('SELECT * FROM "' + name + '" ORDER BY to_jsonb("' + name + '")::text').fetchall() for name in names}
    return dict(pg=pg, consumer=sqlite_snapshot(t['u']['consumer'].repository))


def template_action(t, action, actor, **fields):
    f = t['f']; path = '/api/template-candidate/park-a/' + t['u']['scope'].template_id
    h = {'X-Isolated-Template-Actor': actor, 'Idempotency-Key': uuid4().hex}
    current = f[3].get(path, headers=h); assert current.status_code == 200, current.text
    view = current.json()
    return f[3].post(path + '/commands', headers=h, json=dict(action=action, expected_revision=view['revision'],
        expected_definition_sha256=view['definition_sha256'], reason='SYNTHETIC AT27 explicit original ' + action, **fields))


def breaking_target(t):
    f = t['f']; candidate_before = sqlite_snapshot(t['u']['engine'].repository); business_before = full_business(t)
    broken = definition(ALL_GOALS).model_dump(mode='json'); broken['steps'] = []
    response = template_action(t, 'SAVE_DRAFT', 'template-author', draft=broken)
    assert response.status_code == 422, response.text
    assert sqlite_snapshot(t['u']['engine'].repository) == candidate_before and full_business(t) == business_before
    append_record('at-results', dict(at='AT-27', scenario='invalid_registered_dependency_definition', result='PASS',
        action='SAVE_DRAFT', status=response.status_code, response=response.json(), validator='ORIGINAL_TYPED_DEFINITION_VALIDATOR', no_publication=True))
    assert template_action(t, 'RETURN_DRAFT', 'template-author').status_code == 200
    # This legal new definition removes the original coordination required goal.
    # Publication is allowed after review; its application to either old Case is not.
    assert template_action(t, 'SAVE_DRAFT', 'template-author', draft=definition(ALL_GOALS[:-1], '2').model_dump(mode='json')).status_code == 200
    assert template_action(t, 'SUBMIT', 'template-author').status_code == 200
    submitted = sqlite_snapshot(t['u']['engine'].repository)
    response = template_action(t, 'CANDIDATE_PUBLISH', 'template-publisher', validity=VALID)
    assert response.status_code == 409, response.text
    assert sqlite_snapshot(t['u']['engine'].repository) == submitted and full_business(t) == business_before
    append_record('at-results', dict(at='AT-27', scenario='unreviewed_current_draft_publication', result='PASS',
        action='CANDIDATE_PUBLISH', status=response.status_code, response=response.json(), validator='ORIGINAL_INDEPENDENT_REVIEW_GUARD'))
    assert template_action(t, 'REVIEW', 'template-reviewer').status_code == 200
    response = template_action(t, 'CANDIDATE_PUBLISH', 'template-publisher', validity=VALID)
    assert response.status_code == 200, response.text
    target = call(t['u'], '/api/template-consumer/catalog')['templates'][0]
    assert target['release_id'] != t['release']['release_id'] and full_business(t) == business_before
    return target


def test_at27_same_two_cases_real_publication_guards_breaking_apply_and_rollback_denial(two_cases):
    t = two_cases; f = t['f']; target = breaking_target(t); before = full_business(t)
    for label, row in t['rows'].items():
        path = '/api/template-upgrade/' + row['instance_id']
        query = dict(target_release_id=target['release_id'], target_sha256=target['release_sha256'])
        response = f[3].get(path + '/check', headers=headers(f[2]), params=query)
        assert response.status_code == 200, response.text
        value = response.json(); assert value['check']['classification'] == 'BREAKING_REJECTED'
        assert value['check']['allowed_choices'] == ['KEEP_CURRENT'] and not value['application']['eligible']
        body = dict(target_release_id=target['release_id'], expected_target_sha256=target['release_sha256'],
            expected_check_sha256=value['check_sha256'], expected_revision=value['revision'], choice='REQUEST_RECHECK',
            reason='SYNTHETIC AT27 explicit refused incompatible old Case recheck')
        before_journal = sqlite_snapshot(t['u']['checker'].repository)
        recheck = f[3].post(path + '/choices', headers=headers(f[2], key=uuid4().hex), json=body)
        assert recheck.status_code == 409, recheck.text
        migration_choice = f[3].post(path + '/choices', headers=headers(f[2], key=uuid4().hex), json={**body, 'choice': 'MIGRATE'})
        assert migration_choice.status_code == 422, migration_choice.text
        assert sqlite_snapshot(t['u']['checker'].repository) == before_journal
        keep = f[3].post(path + '/choices', headers=headers(f[2], key=uuid4().hex), json={**body, 'choice': 'KEEP_CURRENT'})
        assert keep.status_code == 200, keep.text
        value = f[3].get(path + '/check', headers=headers(f[2]), params=query).json()
        event = keep.json()['event']; current = preparation_read(f, row).json()['preparation']
        apply_body = dict(expected_instance_id=row['instance_id'], target_release_id=target['release_id'],
            expected_target_sha256=target['release_sha256'], expected_check_sha256=value['check_sha256'],
            expected_choice_revision=event['revision'], expected_choice_event_sha256=event['event_sha256'],
            expected_plan_id=t['initial'][label]['id'], expected_plan_revision=t['initial'][label]['revision'],
            expected_preparation_revision=current['revision'], expected_source_sha256=value['check']['case_state_sha256'],
            reason='SYNTHETIC AT27 current complete request attempts rejected breaking application')
        journal_now = sqlite_snapshot(t['u']['checker'].repository)
        application = f[3].post(path + '/apply', headers=headers(f[2], key=uuid4().hex), json=apply_body)
        assert application.status_code == 409, application.text
        rollback = f[3].get(path + '/check', headers=headers(f[2]), params=dict(target_release_id=t['release']['release_id'], target_sha256=t['release']['release_sha256']))
        assert rollback.status_code == 403, rollback.text
        assert sqlite_snapshot(t['u']['checker'].repository) == journal_now
        assert full_business(t) == before and stored(f, row) == t['initial'][label]
        append_record('at-results', dict(at='AT-27', case=label, scenario='breaking_release_old_case_migration_and_rollback', result='PASS',
            target_release_id=target['release_id'], classification=value['check']['classification'], breaking_recheck_status=recheck.status_code,
            unsupported_migrate_choice_status=migration_choice.status_code, unsupported_choice_is_not_execution_proof=True,
            complete_application_status=application.status_code, complete_application_response=application.json(), rollback_status=rollback.status_code,
            old_case_uuid_goals_text_reservations_receipts_consumer_and_history_unchanged=True))


def run_html(t, mode, controls=None, **extra):
    f = t['f']; controls = controls or {}; attempt = mode + '-' + uuid4().hex[:8]
    driver = ROOT / 'tests/at24_27_change_batch_real_html.js'
    if not driver.is_file():
        driver = Path(__file__).with_name('at24_27_real_html.js')
    OUT.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(['node', str(driver)], cwd=ROOT, stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    selector = selectors.DefaultSelector(); selector.register(process.stdout, selectors.EVENT_READ)
    lines = []; result = None; error = ''
    try:
        config = dict(base=str(f[3].base_url).rstrip('/'), token=f[2]['fixture-a'], mode=mode,
            A=t['rows']['A'], B=t['rows']['B'], **extra)
        process.stdin.write(json.dumps(config) + '\n'); process.stdin.flush()
        while True:
            assert selector.select(timeout=45), 'Original complete HTML made no progress for 45 seconds'
            line = process.stdout.readline()
            if not line:
                break
            lines.append(line); message = json.loads(line)
            if 'control' in message:
                controls[message['control']](); process.stdin.write('{}\n'); process.stdin.flush()
            else:
                result = message; break
        code = process.wait(timeout=10); error = process.stderr.read()
        assert code == 0, error
        assert result and result['scope'] == 'FULL_ORIGINAL_HTML_AT24_27_FIXED_TWO_CASE_REAL_HTTP_ASGI_OWNED_PG'
        append_record('html-results', dict(mode=mode, result='PASS', trace=attempt + '.stdout.jsonl',
            checks=result['checks'], http_requests=len(result['calls']), actual_http=True, real_browser='NOT_RUN'))
        return result
    finally:
        selector.close()
        if process.poll() is None:
            process.terminate(); process.wait(timeout=5)
        (OUT / (attempt + '.stdout.jsonl')).write_text(''.join(lines))
        (OUT / (attempt + '.stderr.log')).write_text(error + process.stderr.read())


def test_at27_original_upgrade_html_rejects_same_two_case_breaking_target(two_cases):
    t = two_cases; target = breaking_target(t); before = full_business(t)
    result = run_html(t, 'at27', page='upgrade', target=target)
    assert all(call['method'] == 'GET' for call in result['calls']) and full_business(t) == before


def material_controls(t):
    f = t['f']; u = t['u']; row = t['rows']['A']; path = '/api/preparations/' + row['preparation_id']
    state = {}
    def change(scenario):
        state['source_plan'] = deepcopy(stored(f, row)); change_source(t, scenario)
        for label, parent in t['rows'].items():
            assert_literal_partition(source_graph(f, parent), t['initial'][label], scenario, label)
    def unresolved():
        data = patch_body(f, row)
        before = full_business(t); plan_before = deepcopy(stored(f, row))
        # The original proofless entry must not bypass the new note gate.
        response = patch(f, row, body=data)
        assert response.status_code == 409, response.text
        assert full_business(t) == before and stored(f, row) == plan_before
        append_record('at-results', dict(at='AT-26', scenario='proofless_original_local_adopt_cannot_bypass_manual_conflict', result='PASS',
            status=response.status_code, response=response.json()))
    def before_adopt(label='A'):
        state['before_adopt_' + label] = full_business(t)
        state['plan_before_adopt_' + label] = deepcopy(stored(f, t['rows'][label]))
    def after_adopt(label='A'):
        current = stored(f, t['rows'][label]); old = state['plan_before_adopt_' + label]
        assert current['id'] == old['id'] and current['required_goals'] == ALL_GOALS
        assert [s['id'] for s in current['steps']] == [s['id'] for s in old['steps']]
        assert [s['contract'] for s in current['steps']] == [s['contract'] for s in old['steps']]
        assert current['events'][:-1] == old['events'] and current['history'] == old['history']
        assert current['events'][-1]['action'] == 'ADOPT'
        affected = set(current['events'][-1]['local_revision']['affected'])
        want = ALL if state['scenario'] == 'A_material_content' else ('P2', 'P3', 'P4', 'P5')
        assert affected == {s['id'] for s in old['steps'] if s['adapter_id'] in want}
        assert [s['verified_sources'] for s in current['steps']] == [s['verified_sources'] for s in old['steps']]
        if state['scenario'] == 'owner_optional_resource_capacity':
            assert current['steps'][0] == old['steps'][0]
        old_facts = deepcopy(state['before_adopt_' + label]); new_facts = full_business(t)
        for data in (old_facts, new_facts):
            for prep in data['pg']['preparations']:
                prep.pop('service_case_plan')
        assert new_facts == old_facts
    def review_material():
        p = dict(preparation_read(f, row).json()['preparation'], preparation_id=row['preparation_id'])
        reviewed = prepare(f, p, 'REVIEW', 'prep-specialist-fixture-a', reason='SYNTHETIC independent changed material review')
        assert reviewed.status_code == 200, reviewed.text
        confirmed = prepare(f, reviewed.json(), 'CONFIRM', reason='SYNTHETIC owner confirms revised actual source')
        assert confirmed.status_code == 200, confirmed.text
    def relink_resources():
        value = resource_link_read(f, row).json(); old = value['current']['record']
        p = dict(preparation_read(f, row).json()['preparation'], preparation_id=row['preparation_id'])
        response = resource_link_write(f, p, dict(id=old['combination_id']), revision=value['link_revision'])
        assert response.status_code == 201, response.text
    def reoffer_accept():
        p = dict(preparation_read(f, row).json()['preparation'], preparation_id=row['preparation_id'])
        dispatch_id = t['completed']['A']['dispatch']['dispatch_id']
        value = f[3].get('/api/service-dispatches/' + dispatch_id, headers=headers(f[2], 'prep-specialist-fixture-a')).json()
        assert value['can_reoffer']
        response = dispatch_offer(f, p, revision=value['revision'], recovery_receipt_step_id=value['recovery_receipt_step_id'])[0]
        assert response.status_code == 201, response.text
        accepted = dispatch_command(f, response.json(), 'ACCEPT'); assert accepted.status_code == 200, accepted.text
        state['new_dispatch'] = accepted.json()
    def new_report_ack():
        state['new_receipt'] = report_and_ack(u, row, state['new_dispatch'])
    def revalidate_local():
        response = local_command(f, row, local_read(f, row).json(), 'REVALIDATE')
        assert response.status_code == 200, response.text
    def final():
        for label, parent in t['rows'].items():
            current = stored(f, parent); initial = t['initial'][label]
            assert current['required_goals'] == ALL_GOALS and current['id'] == initial['id']
            assert [s['id'] for s in current['steps']] == [s['id'] for s in initial['steps']]
            assert current['events'][:len(initial['events'])] == initial['events'] and current['history'] == initial['history']
            result = call(u, '/api/preparations/' + parent['preparation_id'] + '/goal-results')
            assert result['state'] == 'LOCAL_OUTPUTS_VERIFIED' and len(result['results']) == 6 and not result['case_goal_completed']
        if state['scenario'] == 'A_material_content':
            assert stored(f, t['rows']['B']) == t['initial']['B']
        append_record('at-results', dict(at='AT-25/26', scenario=state['scenario'], result='PASS',
            original_six_goals_stable_ids_full_history=True, actual_outputs_verified=True, automatic_case_completion=False))
    def unknown_history():
        data = patch_body(f, row)
        before = full_business(t); response = patch(f, row, body=data)
        assert response.status_code == 409 and full_business(t) == before
        assert stored(f, t['rows']['B']) == t['initial']['B']
    def source_change(scenario):
        state['scenario'] = scenario; change(scenario)
    return {'change_material': lambda: source_change('A_material_content'), 'change_capacity': lambda: source_change('owner_optional_resource_capacity'),
        'assert_unresolved': unresolved, 'before_adopt': before_adopt, 'after_adopt': after_adopt,
        'before_adopt_B': lambda: before_adopt('B'), 'after_adopt_B': lambda: after_adopt('B'),
        'review_material': review_material, 'relink_resources': relink_resources, 'reoffer_accept': reoffer_accept,
        'new_report_ack': new_report_ack, 'revalidate_local': revalidate_local, 'final_evidence': final,
        'make_unknown': lambda: change_source(t, 'shared_catalog_unavailable_unknown'), 'assert_unknown_history': unknown_history}


@pytest.mark.parametrize('mode', ['accept', 'lost_note', 'capacity', 'capacity_lost_adopt', 'lost_note_unknown', 'lost_note_bad_unknown'])
def test_at24_26_original_html_fixed_two_case_explicit_change_loop(two_cases, mode):
    t = two_cases; run_html(t, mode, material_controls(t))


@pytest.mark.parametrize('mode', ['current_403', 'late_aba', 'late_403', 'late_json_reject', 'late_transport_reject'])
def test_original_html_current_note_denial_and_late_identity_case_aba(two_cases, mode):
    t = two_cases; f = t['f']; before = full_business(t)
    authority_state = {}
    def authority(active):
        with f[1].connect() as c:
            f[1].lock_principal(c, 'fixture-a', exclusive=True)
            c.execute("UPDATE capability_grants SET active=%s,revision=revision+1 WHERE principal_id='fixture-a' AND capability='READ'", (active,))
        if not active:
            authority_state['denial_before'] = full_business(t)
    def denied_read():
        assert full_business(t) == authority_state['denial_before']
        append_record('at-results', dict(at='AT-24/26', scenario='actual_new_note_GET_403_before_after_no_business_write',
            mode=mode, result='PASS', response_status=403, original_plan_observation_separate=True))
    result = run_html(t, mode, {'revoke': lambda: authority(False), 'restore': lambda: authority(True), 'assert_denied_read_no_write': denied_read})
    assert all(call['method'] == 'GET' for call in result['calls'])
    # Revocation is an explicitly declared source mutation, never a runtime grant.
    after = full_business(t)
    for item in (before, after):
        item['pg'].pop('capability_grants')
    observed_invalidations = []
    for old in before['pg']['preparations']:
        current = next(p for p in after['pg']['preparations'] if p['id'] == old['id'])
        old_plan = old.get('service_case_plan'); current_plan = current.get('service_case_plan')
        if not old_plan or old_plan == current_plan:
            continue
        # The original loadplan observer records source invalidation after an
        # actual READ-grant revision changes. Only false/absent -> true may vary;
        # current notes, IDs, text, verification evidence and all events may not.
        for prior_step in old_plan['steps']:
            next_step = next(s for s in current_plan['steps'] if s['id'] == prior_step['id'])
            if next_step.get('invalidated') != prior_step.get('invalidated'):
                assert prior_step.get('invalidated', False) is False and next_step.get('invalidated') is True
                observed_invalidations.append(dict(preparation_id=str(old['id']), step_id=prior_step['id']))
                if 'invalidated' in prior_step:
                    next_step['invalidated'] = prior_step['invalidated']
                else:
                    next_step.pop('invalidated')
    append_record('read-observations', dict(mode=mode, original_observe_true_invalidation_only=observed_invalidations,
        remaining_changed_tables=[name for name in before['pg'] if before['pg'][name] != after['pg'][name]]))
    assert after == before


def conflict_view(t, label='A', card=None, actor='fixture-a'):
    row = t['rows'][label]
    return t['f'][3].get('/api/preparations/' + row['preparation_id'] + '/plan-source-conflicts',
        params={'card_id': card['id']} if card else {}, headers=headers(t['f'][2], actor))


def conflict_body(value, action, *, text=None, reason='SYNTHETIC AT26 explicit independent content choice'):
    return dict(schema=1, action=action, expected_plan_id=value['plan_id'], expected_plan_revision=value['plan_revision'],
        expected_note_revision=value['note']['revision'] if value['note'] else 0, expected_ledger_revision=value['opportunity_revision'],
        expected_preview_sha256=value['preview_sha256'], card_id=value['card_id'], text=text, reason=reason)


def conflict_write(t, body, label='A', key=None, actor='fixture-a'):
    return t['f'][3].post('/api/preparations/' + t['rows'][label]['preparation_id'] + '/plan-source-conflicts/commands',
        headers=headers(t['f'][2], actor, key or uuid4().hex), json=body)


def create_manual_conflict(t, *, locked=True):
    f = t['f']; row = t['rows']['A']; first = conflict_view(t)
    assert first.status_code == 200, first.text
    edited = conflict_write(t, conflict_body(first.json(), 'EDIT_NOTE', text='SYNTHETIC AT26 original human coordination content'))
    assert edited.status_code == 200, edited.text
    if locked:
        assert lock(f, row, 'P1').status_code == 200
    response = opportunity_post(f, row, opportunity_body(opportunities(f, row).json(), item=entry()))
    assert response.status_code == 200, response.text
    card = response.json()['current']['cards'][0]
    change_source(t, 'A_material_content')
    refreshed = opportunity_post(f, row, opportunity_body(opportunities(f, row).json(), 'REFRESH'))
    assert refreshed.status_code == 200, refreshed.text
    card = refreshed.json()['current']['cards'][0]
    response = conflict_view(t, card=card); assert response.status_code == 200, response.text
    value = response.json(); assert value['state'] == 'CONFLICT' and value['note']['origin'] == 'MANUAL'
    assert value['note']['text'] == 'SYNTHETIC AT26 original human coordination content'
    assert value['source']['text'] == 'SYNTHETIC AT25 actual revised material outline version two'
    assert value['source']['slot'] == 'material_outline'
    assert any(d['slot'] == 'material_outline' and d['changed'] is True and d['before'] and d['current'] for d in value['material_diffs'])
    return card, value


def test_at26_real_note_keep_defer_original_unlock_and_bound_source_accept(two_cases):
    t = two_cases; f = t['f']; row = t['rows']['A']; card, value = create_manual_conflict(t)
    old = deepcopy(stored(f, row)); text = value['note']['text']
    for action in ('EDIT_NOTE', 'ACCEPT_SOURCE'):
        before = full_business(t)
        response = conflict_write(t, conflict_body(value, action, text='SYNTHETIC forbidden locked overwrite' if action == 'EDIT_NOTE' else None))
        assert response.status_code == 409, response.text
        assert full_business(t) == before
    kept = conflict_write(t, conflict_body(value, 'KEEP_MANUAL')); assert kept.status_code == 200, kept.text
    current = kept.json()['current']; assert current['state'] == 'KEPT_MANUAL' and current['note']['text'] == text
    assert stored(f, row)['steps'][0]['manual_lock'] == old['steps'][0]['manual_lock']
    assert plan_command(f, row, 'P1', 'UNLOCK').status_code == 200
    current = conflict_view(t, card=card).json()
    data = patch_body(f, row)
    before = full_business(t); response = patch(f, row, body=data)
    assert response.status_code == 409 and full_business(t) == before
    assert 'LOCK_CONFLICT' not in response.text.upper() and 'AFFECTED_LOCK' not in response.text.upper()
    assert 'note' in response.text.lower() or 'manual' in response.text.lower(), 'The unlocked proofless adoption must fail on the unresolved manual note'
    # patch_body used the original observe=True plan reader. Even an unchanged
    # invalidation value can advance the parent epoch, so choices re-read it.
    current = conflict_view(t, card=card).json()
    deferred = conflict_write(t, conflict_body(current, 'DEFER')); assert deferred.status_code == 200, deferred.text
    current = deferred.json()['current']; assert current['state'] == 'DEFERRED' and current['note']['text'] == text
    data = patch_body(f, row)
    before = full_business(t); assert patch(f, row, body=data).status_code == 409 and full_business(t) == before
    current = conflict_view(t, card=card).json()
    key = uuid4().hex; data = conflict_body(current, 'ACCEPT_SOURCE')
    accepted = conflict_write(t, data, key=key); assert accepted.status_code == 200, accepted.text
    now = accepted.json()['current']; assert now['state'] == 'ACCEPTED_AWAITING_RECHECK'
    assert now['note']['origin'] == 'SOURCE' and now['note']['text'] == current['source']['text']
    before = full_business(t); replay = conflict_write(t, data, key=key)
    assert replay.status_code == 200 and replay.json()['receipt'] == accepted.json()['receipt'] and full_business(t) == before
    assert conflict_write(t, {**data, 'reason': 'SYNTHETIC same key conflicting parameters'}, key=key).status_code == 409
    recovery = f[3].get('/api/preparations/' + row['preparation_id'] + '/plan-source-conflicts/recovery/' + key, headers=headers(f[2]))
    assert recovery.status_code == 200 and recovery.json()['status'] == 'COMMITTED' and recovery.json()['historical_only'] is True
    assert full_business(t) == before
    value = preview(f, row, card); assert value.status_code == 200 and value.json()['can_adopt'], value.text
    assert_literal_partition(value.json(), t['initial']['A'], 'A_material_content', 'A')
    assert stored(f, t['rows']['B']) == t['initial']['B']
    append_record('at-results', dict(at='AT-26', scenario='original_content_keep_defer_unlock_accept_idempotency_and_cold_get', result='PASS',
        exact_actual_source_text=True, original_six_goals_and_uuids_preserved=True, adoption_and_verify_remain_explicit=True))


def test_at26_fixed_both_locked_full_text_history_and_explicit_business_recheck(two_cases):
    """One current execution of the fixed C26 sequence, not formal AT-26 PASS."""
    t = two_cases; f = t['f']; row = t['rows']['A']
    n0 = 'SYNTHETIC AT26 人工原文第一行\n第二行：保留全部内容、标点与方法决定。\n'
    for label, parent in t['rows'].items():
        value = conflict_view(t, label).json()
        response = conflict_write(t, conflict_body(value, 'EDIT_NOTE', text=n0), label)
        assert response.status_code == 200, response.text
        assert response.json()['current']['note']['text'] == n0
        assert lock(f, parent, 'P1').status_code == 200
    # This slice's frozen initial state includes BOTH explicit notes and locks.
    # The generic fixture's earlier baseline remains separately recorded.
    t['initial'] = {label: deepcopy(stored(f, parent)) for label, parent in t['rows'].items()}
    m0 = {label: conflict_view(t, label).json()['source'] for label in t['rows']}
    frozen_consumer = full_business(t)['consumer']
    frozen_template = sqlite_snapshot(t['u']['engine'].repository)
    change_traffic_start = len(t['traffic'])
    controls = material_controls(t)

    def stage(name):
        views = {label: plan_read(f, parent).json() for label, parent in t['rows'].items()}
        plans = {label: deepcopy(stored(f, parent)) for label, parent in t['rows'].items()}
        notes = {label: conflict_view(t, label).json()['note'] for label in t['rows']}
        for label, plan in plans.items():
            initial = t['initial'][label]
            assert plan['id'] == initial['id'] and plan['required_goals'] == initial['required_goals']
            assert [s['id'] for s in plan['steps']] == [s['id'] for s in initial['steps']]
            assert plan['events'][:len(initial['events'])] == initial['events']
            assert plan['history'] == initial['history']
        assert plans['B'] == t['initial']['B'] and notes['B']['text'] == n0
        assert all(s['state'] == 'VERIFIED' for s in views['B']['steps'])
        assert full_business(t)['consumer'] == frozen_consumer
        assert sqlite_snapshot(t['u']['engine'].repository) == frozen_template
        goals = {label: call(t['u'], '/api/preparations/' + parent['preparation_id'] + '/goal-results')
                 for label, parent in t['rows'].items()}
        append_record('at26-fixed-stages', dict(stage=name, scope='LINUX_SYNTHETIC_HTTP_ASGI_ENGINEERING_ONLY',
            formal_at26='NOT_RUN', n0=n0, m0=m0, notes=notes,
            goals=goals, no_automatic_publication=True, template_sha256=fingerprint(frozen_template),
            current={label: dict(state=v['state'], steps=v['steps']) for label, v in views.items()},
            historical={label: dict(events=p['events'], history=p['history'],
                stored_step_verified_sources={s['adapter_id']: s.get('verified_sources') for s in p['steps']}) for label, p in plans.items()}))
        return views

    def denied(name, request):
        before = full_business(t)
        response = request()
        assert response.status_code == 409, response.text
        assert full_business(t) == before, name
        append_record('at26-fixed-denials', dict(action=name, status=response.status_code, response=response.json(), no_write=True))

    stage('both_manual_notes_and_locks_frozen')
    imported = opportunity_post(f, row, opportunity_body(opportunities(f, row).json(), item=entry()))
    assert imported.status_code == 200, imported.text
    controls['change_material']()
    refreshed = opportunity_post(f, row, opportunity_body(opportunities(f, row).json(), 'REFRESH'))
    assert refreshed.status_code == 200, refreshed.text
    card = refreshed.json()['current']['cards'][0]
    views = stage('A_source_changed_old_success_and_current_conflict_separate')
    assert views['A']['steps'][0]['state'] == 'LOCK_CONFLICT'
    assert views['A']['steps'][0]['verified_sha256'] != views['A']['steps'][0]['source_sha256']
    assert call(t['u'], '/api/preparations/' + row['preparation_id'] + '/goal-results')['state'] != 'LOCAL_OUTPUTS_VERIFIED'
    assert conflict_view(t, card=card).json()['note']['text'] == n0
    assert [s['verified_sources'] for s in stored(f, row)['steps']] == [s['verified_sources'] for s in t['initial']['A']['steps']]
    for action in ('EDIT_NOTE', 'ACCEPT_SOURCE'):
        value = conflict_view(t, card=card).json()
        data = conflict_body(value, action, text='SYNTHETIC forbidden replacement' if action == 'EDIT_NOTE' else None)
        denied(action + '_WHILE_LOCKED', lambda: conflict_write(t, data))
    current_plan = plan_read(f, row).json()
    denied('VERIFY_WHILE_LOCKED', lambda: plan_command(f, row, 'P1', row=current_plan))
    for action in ('KEEP_MANUAL', 'DEFER'):
        value = conflict_view(t, card=card).json()
        result = conflict_write(t, conflict_body(value, action))
        assert result.status_code == 200, result.text
        assert result.json()['current']['state'] == {'KEEP_MANUAL': 'KEPT_MANUAL', 'DEFER': 'DEFERRED'}[action]
        assert result.json()['current']['note']['text'] == n0
        view = stage(action + '_does_not_resolve_lock_or_adopt')
        assert view['A']['steps'][0]['state'] == 'LOCK_CONFLICT'
        assert stored(f, row)['steps'][0]['manual_lock'] == t['initial']['A']['steps'][0]['manual_lock']
        proposal = preview(f, row, card).json()
        assert not proposal['can_adopt']
        denied(action + '_BOUND_ADOPT', lambda: adopt(f, row, proposal['adoption']))
        data = patch_body(f, row)
        denied(action + '_PROOFLESS_ADOPT', lambda: patch(f, row, body=data))

    response = plan_command(f, row, 'P1', 'UNLOCK')
    assert response.status_code == 200, response.text
    assert response.json()['steps'][0]['state'] == 'NEEDS_RECHECK'
    stage('explicit_UNLOCK_is_not_content_resolution_or_verification')
    data = patch_body(f, row)
    denied('UNLOCKED_UNRESOLVED_PROOFLESS_ADOPT', lambda: patch(f, row, body=data))
    current_plan = plan_read(f, row).json()
    denied('UNLOCKED_UNREPAIRED_VERIFY', lambda: plan_command(f, row, 'P1', row=current_plan))
    value = conflict_view(t, card=card).json()
    assert value['note']['text'] == n0 and value['source']['text'] == 'SYNTHETIC AT25 actual revised material outline version two'
    accepted = conflict_write(t, conflict_body(value, 'ACCEPT_SOURCE'))
    assert accepted.status_code == 200, accepted.text
    current = accepted.json()['current']
    assert current['state'] == 'ACCEPTED_AWAITING_RECHECK'
    assert current['note']['origin'] == 'SOURCE' and current['note']['text'] == value['source']['text']
    assert current['note']['text_sha256'] == hashlib.sha256(value['source']['text'].encode()).hexdigest()
    stage('explicit_ACCEPT_SOURCE_is_not_fact_verification')
    proposal = preview(f, row, card).json()
    assert proposal['can_adopt']
    controls['before_adopt']()
    response = adopt(f, row, proposal['adoption'])
    assert response.status_code == 201, response.text
    controls['after_adopt']()
    stage('explicit_ADOPT_retains_old_verified_sources_until_business_recheck')
    current_plan = plan_read(f, row).json()
    denied('ADOPTED_UNREPAIRED_VERIFY', lambda: plan_command(f, row, 'P1', row=current_plan))
    for adapter, correction in zip(ALL, ('review_material', 'relink_resources', 'reoffer_accept', 'new_report_ack', 'revalidate_local')):
        controls[correction]()
        stage('actual_business_' + correction + '_before_VERIFY')
        verified(f, row, adapter)
        stage('explicit_' + adapter + '_VERIFY')
    controls['final_evidence']()
    final = stage('six_local_outputs_verified_business_case_not_auto_completed')
    assert all(s['state'] == 'VERIFIED' for s in final['A']['steps'])
    actions = [e['action'] for e in stored(f, row)['events'][len(t['initial']['A']['events']):]]
    assert actions.count('UNLOCK') == 1 and actions.count('ADOPT') == 1 and actions.count('VERIFY') == 5
    traffic = t['traffic'][change_traffic_start:]
    assert not any(r['method'] != 'GET' and '/template-' in r['path'] for r in traffic)
    append_record('at26-fixed-http', dict(requests=traffic, no_automatic_template_publication=True))
    append_record('at-results', dict(at='AT-26', scenario='C26_BOTH_LOCKED_SINGLE_CURRENT_EXECUTION', result='PASS',
        formal_at26='NOT_RUN', explicit_actions=actions, exact_full_manual_text=n0,
        historical_success_separate_from_current_validity=True, real_browser='NOT_RUN', windows='NOT_RUN', real_model_calls=0))


@pytest.mark.parametrize('action', ['ACCEPT_SOURCE', 'KEEP_MANUAL', 'DEFER'])
def test_note_actual_material_a_b_a_rejects_old_choice_without_writes(two_cases, action):
    t = two_cases; f = t['f']; card, value = create_manual_conflict(t, locked=False)
    row = t['rows']['A']; current = dict(preparation_read(f, row).json()['preparation'], preparation_id=row['preparation_id'])
    # New immutable source generations, with final bytes equal to the saved preview.
    first = material_add(f, current, slot='material_outline', text='SYNTHETIC intermediate actual source bytes'); assert first.status_code == 200
    second = material_add(f, first.json(), slot='material_outline', text=value['source']['text']); assert second.status_code == 200
    before = full_business(t)
    response = conflict_write(t, conflict_body(value, action))
    assert response.status_code == 409 and full_business(t) == before
    assert stored(f, row)['steps'][0]['verified_sources'] == t['initial']['A']['steps'][0]['verified_sources']


@pytest.mark.parametrize('capability', ['READ', 'PREPARE', 'EXECUTE', 'ACTIVE'])
def test_new_note_command_current_authority_precedes_same_key_receipt(two_cases, capability):
    t = two_cases; f = t['f']; view = conflict_view(t); assert view.status_code == 200, view.text
    key = uuid4().hex; body = conflict_body(view.json(), 'EDIT_NOTE', text='SYNTHETIC original explicit manual note')
    response = conflict_write(t, body, key=key); assert response.status_code == 200, response.text
    with f[1].connect() as c:
        f[1].lock_principal(c, 'fixture-a', exclusive=True)
        if capability == 'ACTIVE':
            c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
        elif capability == 'PREPARE':
            c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
        else:
            c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability=%s", (capability,))
    before = full_business(t); response = conflict_write(t, body, key=key)
    assert response.status_code == 403 and full_business(t) == before


def test_unknown_current_source_does_not_become_adoptable_from_hint_or_refresh(two_cases):
    t = two_cases; f = t['f']; row = t['rows']['A']
    response = opportunity_post(f, row, opportunity_body(opportunities(f, row).json(), item=entry()))
    assert response.status_code == 200; card = response.json()['current']['cards'][0]
    change_source(t, 'shared_catalog_unavailable_unknown')
    current = opportunities(f, row).json(); refreshed = opportunity_post(f, row, opportunity_body(current, 'REFRESH'))
    assert refreshed.status_code == 200
    card = next(c for c in refreshed.json()['current']['cards'] if c['id'] == card['id'])
    response = preview(f, row, card)
    assert response.status_code == 409 or response.status_code == 200 and response.json()['can_adopt'] is False
    data = patch_body(f, row); before = full_business(t)
    assert patch(f, row, body=data).status_code == 409 and full_business(t) == before
    for label, parent in t['rows'].items():
        assert_literal_partition(source_graph(f, parent), t['initial'][label], 'shared_catalog_unavailable_unknown', label)


def test_at25_changed_catalog_contract_requires_explicit_replacement_not_local_adopt(two_cases):
    t = two_cases; f = t['f']; change_source(t, 'shared_catalog_source_contract')
    for label, row in t['rows'].items():
        assert_literal_partition(source_graph(f, row), t['initial'][label], 'shared_catalog_source_contract', label)
        body = patch_body(f, row); before = full_business(t)
        response = patch(f, row, body=body)
        assert response.status_code == 409 and full_business(t) == before
        assert stored(f, row)['required_goals'] == ALL_GOALS
        assert [s['id'] for s in stored(f, row)['steps']] == [s['id'] for s in t['initial'][label]['steps']]
        append_record('at-results', dict(at='AT-25', case=label, scenario='catalog_contract_change_is_not_local_source_adoption',
            result='PASS', status=response.status_code, response=response.json(), actual_affected=list(ALL), local_adoption_refused=True))


def test_at25_selected_capacity_two_case_old_reservations_preserved_and_explicit_rebind(two_cases):
    t = two_cases; f = t['f']; u = t['u']
    for row in t['rows'].values():
        assert lock(f, row, 'P1').status_code == 200
    locked = {label: deepcopy(stored(f, row)['steps'][0]) for label, row in t['rows'].items()}
    with f[1].connect() as c:
        old_reservations = {table: c.execute('SELECT * FROM ' + table + ' ORDER BY to_jsonb(' + table + ')::text').fetchall() for table in (
            'synthetic_resource_holds', 'synthetic_resource_combinations', 'synthetic_resource_combination_members',
            'synthetic_resource_combination_receipts', 'resource_case_claims', 'case_resource_links')}
        c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('synthetic-resource:' + str(resource_holds.RESOURCE_ID),))
        c.execute('UPDATE synthetic_resources SET capacity=capacity+1,revision=revision+1 WHERE id=%s', (resource_holds.RESOURCE_ID,))
    for label, row in t['rows'].items():
        assert_literal_partition(source_graph(f, row), t['initial'][label], 'selected_resource_capacity_and_revision', label)
        view = plan_read(f, row).json(); before = full_business(t)
        refused = plan_command(f, row, 'P2', row=view)
        assert refused.status_code == 409 and full_business(t) == before
        data = patch_body(f, row); adoption = patch(f, row, body=data)
        assert adoption.status_code == 201, adoption.text
        assert stored(f, row)['steps'][0] == locked[label]
        assert set(stored(f, row)['events'][-1]['local_revision']['affected']) == {s['id'] for s in t['initial'][label]['steps'] if s['adapter_id'] != 'P1'}
    # Existing first-delivery Approval is immutable historical evidence. Original
    # repeat delivery is deliberately closed; use its documented rebind path.
    for number, (label, row) in enumerate(t['rows'].items()):
        resources = call(u, '/api/synthetic-resources')['items']; revisions = {x['id']: x['revision'] for x in resources}
        base = hold_body(f, ttl=300); start = datetime.fromisoformat(base['starts_at']) + timedelta(hours=48 + number * 24)
        hs = []
        for index, resource in enumerate((resource_holds.RESOURCE_ID, resource_combinations.SECOND_RESOURCE_ID, resource_holds.RESOURCE_ID)):
            body = dict(base, starts_at=(start + timedelta(hours=index * 3)).isoformat(), ends_at=(start + timedelta(hours=index * 3 + 1)).isoformat(),
                expected_revision=revisions[str(resource)], purpose='SYNTHETIC explicit current replacement resource for fixed Case ' + label)
            hs.append(call(u, '/api/synthetic-resources/' + str(resource) + '/holds', data=body, expected=201)['hold'])
        bundle = call(u, '/api/resource-bundles', data=dict(members=[dict(hold_id=h['id'], expected_revision=h['resource_revision']) for h in hs]), expected=201)
        path = '/api/preparations/' + row['preparation_id']
        comparison = call(u, path + '/resource-plan-binding?candidate_combination_id=' + bundle['combination']['id'])
        append_record('selected-capacity-progress', dict(case=label, stage='CURRENT_REGISTERED_SIX_GOAL_REBIND_COMPARISON',
            can_confirm=comparison['comparison']['can_confirm'], blockers=comparison['comparison']['blockers'],
            candidate_issues=comparison['candidate']['issues'], p1_issues=comparison['checkpoints']['P1']['issues'],
            p1_state=comparison['checkpoints']['P1']['state'], original_source_adoption_passed=True, new_original_holds_and_bundle_passed=True))
        assert comparison['candidate']['explicit_association_required'] is True and comparison['comparison']['can_confirm']
        current = preparation_read(f, row).json()['preparation']
        body = dict(combination_id=bundle['combination']['id'], expected_preparation_revision=current['revision'],
            expected_link_revision=comparison['comparison']['link_revision'], expected_comparison_sha256=comparison['comparison']['sha256'],
            reason='SYNTHETIC owner explicitly confirms current replacement after source capacity and rule change')
        binding = call(u, path + '/resource-link', data=body, expected=201)
        assert binding['current']['status'] == 'CURRENT'
        for adapter in ('P2', 'P3', 'P4'):
            verified(f, row, adapter)
        local = local_read(f, row).json(); result = local_command(f, row, local, 'REVALIDATE')
        assert result.status_code == 200, result.text
        verified(f, row, 'P5')
        goals = call(u, path + '/goal-results')
        assert goals['state'] == 'LOCAL_OUTPUTS_VERIFIED' and len(goals['results']) == 6
        assert stored(f, row)['steps'][0] == locked[label]
        append_record('at-results', dict(at='AT-25', scenario='selected_capacity_actual_rule_and_current_rebind', case=label, result='PASS',
            old_verify_status=refused.status_code, actual_source_rule_revision_changed=True, new_hold_count=3, original_first_delivery_approval_preserved=True,
            replacement_entry='ORIGINAL_RESOURCE_PLAN_BINDING_COMPARISON_AND_RESOURCE_LINK', replacement_formal_approval='NOT_IMPLEMENTED',
            literal_affected=['P2','P3','P4','P5'], literal_preserved=['P1'], p1_lock_exact=True, all_six_local_outputs_verified=True))
    with f[1].connect() as c:
        for table, original in old_reservations.items():
            current = c.execute('SELECT * FROM ' + table).fetchall()
            assert all(old in current for old in original), 'Original reservation/history row was changed: ' + table


def test_at25_real_row_bound_unknown_expands_both_cases_and_refuses_source_adoption(two_cases):
    t = two_cases; f = t['f']
    # Actual distinct owned fixture resources and already permitted fixture grants;
    # the original 256 joined-row limit and original epoch bounds are unchanged.
    for _ in range(130):
        add_resource(f)
    for label, row in t['rows'].items():
        response = plan_read(f, row); assert response.status_code == 200, response.text
        view = response.json(); impact = view['change_impact']
        initial = t['initial'][label]; ids = {s['id'] for s in initial['steps']}
        assert set(impact['affected']) == ids and not impact['preserved'] and impact['unknown_scope'] == 'THIS_CASE'
        append_record('oracle', dict(scenario='C25_UNKNOWN_REAL_BOUND', case=label, expected_affected=sorted(ids), actual_affected=sorted(impact['affected']),
            expected_preserved=[], actual_preserved=impact['preserved'], missed_count=len(ids-set(impact['affected'])), wrong_count=len(set(impact['affected'])-ids),
            wrong_preserved_count=len(impact['preserved']), intentional_unknown=True, original_joined_row_limit_unmodified=256, added_actual_fixture_resources=130))
        assert not view['can_adopt']
        note = conflict_view(t, label=label); assert note.status_code == 200, note.text
        assert note.json()['state'] == 'UNKNOWN' and not note.json()['can_edit'] and not note.json()['can_resolve']
        data = patch_body(f, row); before = full_business(t)
        denied = patch(f, row, body=data); assert denied.status_code == 409 and full_business(t) == before
        append_record('at-results', dict(at='AT-25', case=label, scenario='C25_UNKNOWN_REAL_BOUND', result='PASS',
            plan_read_status=response.status_code, unknown_scope='THIS_CASE', note_read_status=note.status_code, adoption_status=denied.status_code,
            known_precision_group=False, unknown_conservative_expansion=True))


def test_at26_mixed_material_and_optional_capacity_cannot_bypass_kept_manual_note(two_cases):
    t = two_cases; f = t['f']; row = t['rows']['A']; card, value = create_manual_conflict(t, locked=False)
    kept = conflict_write(t, conflict_body(value, 'KEEP_MANUAL')); assert kept.status_code == 200, kept.text
    change_source(t, 'owner_optional_resource_capacity')
    current = conflict_view(t, card=card); assert current.status_code == 200, current.text
    assert current.json()['state'] == 'KEPT_MANUAL'
    plan = plan_read(f, row).json(); assert not plan['can_adopt']
    data = patch_body(f, row); before = full_business(t)
    denied = patch(f, row, body=data); assert denied.status_code == 409 and full_business(t) == before
    assert stored(f, row)['owner_amendments'][value['step_id']] == kept.json()['current']['note']
    append_record('at-results', dict(at='AT-25/26', scenario='C26_MIXED_BYPASS', result='PASS', material_actual_version_changed=True,
        shared_optional_capacity_and_revision_changed=True, request_opportunity_proof_omitted='opportunity_proof' not in data,
        status=denied.status_code, response=denied.json(), original_plan_and_opportunity_events_unchanged=True))


def test_at26_current_catalog_replacement_cannot_drop_unresolved_manual_annotation(two_cases):
    t = two_cases; f = t['f']; row = t['rows']['A']; card, value = create_manual_conflict(t, locked=False)
    kept = conflict_write(t, conflict_body(value, 'KEEP_MANUAL')); assert kept.status_code == 200, kept.text
    change_source(t, 'shared_catalog_source_contract')
    current = dict(preparation_read(f, row).json()['preparation'], preparation_id=row['preparation_id'])
    data = original_adopt_body(f, current)
    data['expected_plan_revision'] = stored(f, row)['revision']
    assert not data.get('local_revision')
    before = full_business(t); old = deepcopy(stored(f, row))
    denied = adopt(f, row, data); assert denied.status_code == 409 and full_business(t) == before
    assert stored(f, row) == old and old['owner_amendments']
    append_record('at-results', dict(at='AT-26/27', scenario='C26_REPLACEMENT_BYPASS', result='PASS', status=denied.status_code,
        response=denied.json(), exact_manual_note_and_current_plan_history_preserved=True, replacement_is_not_migration=True))
