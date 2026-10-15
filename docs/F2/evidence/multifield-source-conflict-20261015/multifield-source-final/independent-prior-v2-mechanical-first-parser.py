"""Mechanical accounting of this window only; no expected product logic copied."""
from pathlib import Path
from collections import Counter
import datetime
import hashlib
import json
import re
import sys

ROOT = Path('/workspace/ParkWeave')
BASE = ROOT / '.runtime/multifield-source-final'
NAME = 'independent-prior-v2'
OUT = BASE / 'artifacts' / NAME / 'test_manual_content_continuation_independent'
ANALYSIS = BASE / (NAME + '-analysis')
EXPECTED_SHA = '30e8a60f8bffeb5f0b41bd3abb222526127c5433'
MODES = {'keep_edit', 'accept', 'merge', 'defer_unknown', 'lost_choice', 'lost_adopt', 'current_403', 'late_403'}
POSITIVES = {'keep_edit', 'accept', 'merge', 'lost_choice', 'lost_adopt'}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def rows(kind):
    result = []
    for path in sorted(OUT.glob(kind + '-*.jsonl')):
        result.extend(json.loads(line) for line in path.read_text().splitlines() if line)
    return result

def is_adopt(call):
    return call['method'] == 'POST' and call['path'].split('?', 1)[0].endswith('/service-case-plan')

def is_verify(call):
    return call['method'] == 'POST' and call['path'].split('?', 1)[0].endswith('/service-case-plan/commands') and call.get('body', {}).get('action') == 'VERIFY'

closure_path = BASE / (NAME + '-independent-closure.json')
closure = json.loads(closure_path.read_text())
assert closure['status'] == 'PASS' and closure['source_sha'] == EXPECTED_SHA and closure['named_junit_pass'] == 33
assert closure['source_alltracked_helpers_drift'] == 0
for relative, digest in closure['outputs'].items():
    assert sha(ROOT / relative) == digest
collection = set(json.loads((BASE / (NAME + '-collection.json')).read_text()))
records = {}
for path in sorted(OUT.glob('*.jsonl')):
    if path.name.endswith('.stdout.jsonl'):
        continue
    for line in path.read_text().splitlines():
        value = json.loads(line)
        assert value['source_sha'] == EXPECTED_SHA
        assert value['test'].rsplit(' (', 1)[0] in collection
        records.setdefault(path.name.split('-', 1)[0], 0)
        records[path.name.split('-', 1)[0]] += 1
html = rows('html-results')
assert len(html) == 8 and {r['mode'] for r in html} == MODES
assert len({r['mode'] for r in html}) == len(html)
native_calls, controls, per_mode = [], {}, {}
trace_paths = []
for row in html:
    assert row['result'] == 'PASS' and row['actual_http'] is True and row['real_browser'] == 'NOT_RUN'
    trace = OUT / row['trace']
    trace_paths.append(trace)
    lines = [json.loads(line) for line in trace.read_text().splitlines()]
    final = lines[-1]
    assert final['scope'] == 'FULL_ORIGINAL_HTML_MANUAL_CONTINUATION_REAL_HTTP_ASGI_OWNED_PG'
    assert final['mode'] == row['mode'] and final['checks'] == row['checks'] and final['real_browser'] == 'NOT_RUN'
    assert final['negative_transport_fixture'] is False
    calls = final['calls']
    assert len(calls) == row['requests']
    assert all(c['method'] in {'GET', 'POST'} and isinstance(c['status'], int) for c in calls)
    native_calls.extend(calls)
    events = [r['control'] for r in lines if 'control' in r]
    controls[row['mode']] = events
    adoptions, verifies = [c for c in calls if is_adopt(c)], [c for c in calls if is_verify(c)]
    if row['mode'] in POSITIVES:
        assert len(adoptions) == 1 and len(verifies) == 5
        assert adoptions[0]['status'] == 201 and all(c['status'] == 200 for c in verifies)
        assert adoptions[0]['body']['local_revision'] is True and adoptions[0]['body']['opportunity_proof']
        assert 'final_evidence' in events
        assert any(c['method'] == 'GET' and '/goal-results' in c['path'] for c in calls)
        assert any(c['method'] == 'GET' and '/api/cases/worklist' in c['path'] for c in calls)
        assert final.get('actual_source_accept') is (row['mode'] == 'accept')
        assert final.get('manual_preserved') is (row['mode'] != 'accept')
    else:
        assert adoptions == [] and verifies == []
    if row['mode'] in {'current_403', 'late_403'}:
        assert all(c['method'] == 'GET' for c in calls)
        assert any(c['status'] == 403 and '/plan-source-conflicts' in c['path'] for c in calls)
        assert 'revoke' in events and 'assert_denied_read_no_write' in events
        if row['mode'] == 'late_403':
            assert 'restore' in events
    if row['mode'] == 'defer_unknown':
        assert final['unknown_actual_source'] is True
        assert events.count('assert_unresolved') == 2 and 'make_unknown' in events
    recoveries = [c for c in calls if c['method'] == 'GET' and ('/recovery/' in c['path'] or '/command-recovery/' in c['path'])]
    cold = None
    if row['mode'] in {'lost_choice', 'lost_adopt'}:
        suffix = '/plan-source-conflicts/commands' if row['mode'] == 'lost_choice' else '/service-case-plan'
        dropped = [i for i,c in enumerate(calls) if c['method'] == 'POST' and c['path'].endswith(suffix)]
        index = dropped[-1]
        committed = calls[index]
        assert committed['status'] == (200 if row['mode'] == 'lost_choice' else 201) and committed['request_key']
        matches = [(i,c) for i,c in enumerate(calls) if i > index and c['method'] == 'GET' and c['path'].endswith('/' + committed['request_key'])]
        assert matches
        recovery_index, recovered = matches[0]
        assert recovered['status'] == 200 and all(c['method'] == 'GET' for c in calls[index + 1:recovery_index + 1])
        assert len([c for c in calls if c['method'] == 'POST' and c.get('request_key') == committed['request_key']]) == 1
        cold = dict(backend_commit_status=committed['status'], same_original_key_get_status=200,
                    auto_post_retries=0, classification='ACTUAL_BACKEND_COMMIT_THEN_CONTROLLED_CLIENT_RESPONSE_DISCARD')
    per_mode[row['mode']] = dict(native_requests=len(calls), methods=dict(Counter(c['method'] for c in calls)),
        statuses=dict(Counter(str(c['status']) for c in calls)), checks=row['checks'],
        original_plan_post_adopt=len(adoptions), original_opportunity_proof_adopt=sum(bool(c['body'].get('opportunity_proof')) for c in adoptions),
        plan_commands_action_adopt=sum(c['method']=='POST' and c['path'].endswith('/service-case-plan/commands') and c.get('body',{}).get('action')=='ADOPT' for c in calls),
        named_source_change_adoptions_route=sum('/source-change-adoptions' in c['path'] for c in calls),
        original_verify=len(verifies), note_actions=dict(Counter(c['body']['action'] for c in calls if c['method']=='POST' and c['path'].endswith('/plan-source-conflicts/commands'))),
        cold_recovery=cold, trace=str(trace.relative_to(ROOT)), trace_sha256=sha(trace))

oracle = rows('oracle')
assert oracle and all(r['missed_count'] == r['wrong_count'] == r['wrong_preserved_count'] == 0 for r in oracle)
known, conservative = [r for r in oracle if not r['intentional_unknown']], [r for r in oracle if r['intentional_unknown']]
partitions = {}
for label, observations in [('known', known), ('intentional_unknown', conservative)]:
    partitions[label] = dict(observations=len(observations), expected_affected=sum(len(r['expected_affected']) for r in observations),
        actual_affected=sum(len(r['actual_affected']) for r in observations), expected_preserved=sum(len(r['expected_preserved']) for r in observations),
        actual_preserved=sum(len(r['actual_preserved']) for r in observations), missed=0, wrong=0, wrong_preserved=0,
        unique_step_uuid_count=len({x for r in observations for x in r['expected_affected'] + r['expected_preserved']}),
        interpretation='REPEATED_LITERAL_OBSERVATIONS_NOT_UNIQUE_STEPS_OR_CASES')
closures = rows('closures')
assert len(closures) == 5
assert all(r['six_goals_current'] and r['original_ids_contract_history'] and r['unaffected_B_exact'] for r in closures)
assert Counter(r['manual_or_explicit_source'] for r in closures) == Counter(MANUAL=4, SOURCE=1)
refusals = rows('refusals')
assert all(r['no_business_write'] is True and r['status'] in (403, 409) for r in refusals)
aba = rows('aba-fault-injections')
assert len(aba) == 2 and {r['kind'] for r in aba} == {'OWNED_PG_SOURCE_ROW_ABA', 'OWNED_PG_PLAN_ROW_ABA'}
assert all(r['business_command'] is False and r['epoch_changed'] for r in aba)
assert len(rows('baseline')) == 33

private_paths = list(OUT.rglob('*.private.json')) + [BASE / ('redaction-' + NAME + '.private.json')]
private_paths = [p for p in private_paths if p.is_file()]
assert private_paths
tokens = set()
for path in private_paths:
    assert path.stat().st_mode & 0o777 == 0o600
    tokens.update(json.loads(path.read_text()))
assert tokens and all(isinstance(v, str) and len(v) >= 16 for v in tokens)
pattern = re.compile(b'|'.join(re.escape(value[:16].encode()) for value in sorted(tokens)))
public_paths = [p for p in OUT.rglob('*') if p.is_file() and '.private.' not in p.name]
public_paths.extend(BASE / (NAME + suffix) for suffix in ['.log', '.xml', '.json', '-collection.json', '-runner.log'])
leaks = [str(path.relative_to(ROOT)) for path in public_paths if pattern.search(path.read_bytes())]
assert not leaks, {'known_private_prefix_leak_paths': leaks}

summary = dict(status='PASS', source_sha=EXPECTED_SHA, window=NAME,
    utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), scope='ONE_COMPLETE_PRIOR_MANUAL_CONTINUATION_INDEPENDENT_MODULE',
    collected_and_named_pass=33, complete_original_html_flows=8, html_per_mode=per_mode,
    actual_native_http_requests=len(native_calls), native_method_counts=dict(Counter(c['method'] for c in native_calls)),
    original_plan_post_adopt=sum(is_adopt(c) for c in native_calls), original_verify=sum(is_verify(c) for c in native_calls),
    actual_six_goal_closure_observations=len(closures), preserved_manual_closures=4, explicit_source_accept_closures=1,
    current_403_actual_backend=True, late_403_actual_backend_identity_aba=True,
    response_loss='ACTUAL_BACKEND_COMMIT_THEN_CONTROLLED_CLIENT_DISCARD; FRESH_VM_ORIGINAL_KEY_GET; NOT_REAL_NETWORK_PACKET_LOSS',
    known_unknown_partitions=partitions, recorded_refusal_observations=len(refusals), aba_fault_injections=aba,
    private_scan=dict(registries=len(private_paths), known_value_count=len(tokens), public_files=len(public_paths), full_or_16char_prefix_matches=0, exported=False),
    evidence_transport='FULL_SHIPPED_HTML_SCRIPT_NODE_VM_DOM_DOUBLE_NATIVE_FETCH_LOOPBACK_HTTP_ASGI_OWNED_POSTGRESQL',
    python_api_request_count='NOT_RECORDED_BY_FROZEN_CAPTURE_PLUGIN', design46='NOT_AN_EXECUTED_DENOMINATOR_NO_BLANKET_DESIGN_PASS',
    real_browser='NOT_RUN', windows='NOT_RUN', formal_AT='NOT_RUN', real_model='NOT_RUN', production='NOT_RUN',
    closure_receipt=str(closure_path.relative_to(ROOT)), closure_receipt_sha256=sha(closure_path),
    record_counts={kind:len(rows(kind)) for kind in ['baseline','oracle','closures','refusals','aba-fault-injections','html-results']},
    previous_window_scores_reused=False)
ANALYSIS.mkdir(exist_ok=True)
summary_path = ANALYSIS / 'mechanical-summary.json'
with summary_path.open('x') as stream:
    stream.write(json.dumps(summary, indent=2) + '\n')
receipt = dict(status='PASS', source_sha=EXPECTED_SHA, validator_sha256=sha(Path(__file__).resolve()),
    mechanical_summary_sha256=sha(summary_path), closure_receipt_sha256=sha(closure_path))
with (ANALYSIS / 'success.json').open('x') as stream:
    stream.write(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({k:summary[k] for k in ['status','source_sha','collected_and_named_pass','complete_original_html_flows','actual_native_http_requests','original_plan_post_adopt','original_verify','actual_six_goal_closure_observations','record_counts','known_unknown_partitions','private_scan']},indent=2))
