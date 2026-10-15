"""Inspect frozen evidence only; execute no application action or test."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
NAME,SOURCE=sys.argv[1:3]


def load(suffix):return json.loads((BASE/(NAME+suffix)).read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(suffix,value):(BASE/(NAME+suffix)).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


r=load('.json')
assert r['source_sha']==r['head_after']==SOURCE
assert r['exit_code']==0 and r['counts']==dict(PASS=33,FAIL=0,ERROR=0,SKIP=0)
assert r['tracked_source_paths']==len(load('-before.json')) and r['all_tracked_paths']==len(load('-all-tracked-before.json'))
assert not r['source_drift'] and not r['all_tracked_drift'] and not r['source_status_after']
assert r['runner_unchanged'] and r['plugin_unchanged']
assert load('-before.json')==load('-after.json')
assert load('-all-tracked-before.json')==load('-all-tracked-after.json')
collection=load('-collection.json');assert len(collection)==len(set(collection))==33
passed=set()
for case in ET.parse(BASE/(NAME+'.xml')).iter('testcase'):
    assert case.find('failure') is None and case.find('error') is None and case.find('skipped') is None
    parts=case.attrib['classname'].split('.');index=next(i for i,s in enumerate(parts) if s.startswith('test_'))
    passed.add('tests/'+parts[index]+'.py::'+'::'.join(parts[index+1:]+[case.attrib['name']]))
assert set(collection)==passed and r['collection_junit_exact_match'] and r['unique_junit_nodes']
coverage=json.loads((BASE/'coverage-design.json').read_text())
oracle=ROOT/'docs/F2/ManualContentContinuationOracles-20261015.json'
assert sha(oracle)==coverage['oracle_sha256']=='9455b88d9c83771b9e627094aa5f249b6e0bc434c4bbe862561e9cc62b9221e5'
assert len(coverage['mappings'])==46 and {x['id'] for x in coverage['mappings']}=={x['id'] for x in json.loads(oracle.read_text())['cases']}
for row in coverage['mappings']:
    assert all(node in passed for node in row['test_nodes'])
    row['execution_status']='PASS_ONLY_FOR_DESCRIBED_SCOPE' if row['test_nodes'] else 'NOT_RUN_IN_THIS_MODULE'
save('-design-coverage.json',coverage)

records=load('-related-traces.json')['records']+load('-own-traces.json')['records']
assert len({x['path'] for x in records})==len(records)
oracles=[];flows=[];baseline=[];original_baseline=[];closures=[];refusals=[]
for item in records:
    p=ROOT/item['path'];assert '.private.' not in p.name and item['source_sha']==SOURCE and sha(p)==item['sha256']
    if p.suffix!='.jsonl':continue
    rows=[json.loads(line) for line in p.read_text().splitlines() if line]
    if p.name.startswith('oracle-'):oracles.extend(rows)
    elif p.name.startswith('baseline-'):
        (original_baseline if p.parent.name=='baseline' else baseline).extend(rows)
    elif p.name.startswith('closures-'):closures.extend(rows)
    elif p.name.startswith('refusals-'):refusals.extend(rows)
    elif p.name.endswith('.stdout.jsonl'):
        final=[x for x in rows if 'scope' in x];assert len(final)==1
        value=final[0];assert value['scope']=='FULL_ORIGINAL_HTML_MANUAL_CONTINUATION_REAL_HTTP_ASGI_OWNED_PG'
        value.update(trace=item['path'],trace_sha256=item['sha256']);flows.append(value)
assert len(baseline)==len(original_baseline)==33
for row in baseline:
    assert row['source_sha']==SOURCE and row['original_source']['version']==1
    assert row['original_source']['text']==json.loads(oracle.read_text())['three_versions']['B']['text']
    assert all(len(case['required_goals'])==6 for case in row['cases'].values())
for row in original_baseline:
    assert row['source_sha']==SOURCE and all(set(case['states'].values())=={'VERIFIED'} and len(case['required_goals'])==6 for case in row['cases'].values())
stats=dict(records=len(oracles),expected_affected_pairs=0,actual_affected_pairs=0,missed_count=0,wrong_count=0,wrong_preserved_count=0)
for row in oracles:
    assert row['source_sha']==SOURCE and not row['intentional_unknown']
    expected=set(row['expected_affected']);actual=set(row['actual_affected'])
    stats['expected_affected_pairs']+=len(expected);stats['actual_affected_pairs']+=len(actual)
    stats['missed_count']+=len(expected-actual);stats['wrong_count']+=len(actual-expected)
    stats['wrong_preserved_count']+=len(set(row['expected_preserved'])^set(row['actual_preserved']))
assert not stats['missed_count'] and not stats['wrong_count'] and not stats['wrong_preserved_count']
assert len(flows)==8 and {x['mode'] for x in flows}=={'keep_edit','accept','merge','defer_unknown','lost_choice','lost_adopt','current_403','late_403'}
assert len(closures)==5 and all(x['six_goals_current'] and x['original_ids_contract_history'] and x['unaffected_B_exact'] for x in closures)
assert Counter(x['manual_or_explicit_source'] for x in closures)==dict(MANUAL=4,SOURCE=1)
assert all(x['source_sha']==SOURCE and x['no_business_write'] for x in refusals)
denials=[x for x in refusals if x.get('scenario')=='ACTUAL_NOTE_GET_403_DIRECT_BEFORE_AFTER'];assert len(denials)==2
schema_samples=[]
for flow in flows:
    for call in flow['calls']:
        if call.get('continuation'):
            c=call['continuation'];assert c['schema']==1 and c['scope']=='OWNER_NOTE_EXACT_LINE_CONTINUATION'
            schema_samples.append(c)
        if call.get('response_scope')=='OWNER_PLAN_SOURCE_CONFLICT':assert call['response_schema']==1
unknown_nodes=[node for node in collection if 'condition_bound' in node and '[129]' in node or 'test_unknown_actual_baseline' in node or 'actual_six_goal_evidence[defer_unknown]' in node]
assert len(unknown_nodes)==4 and set(unknown_nodes)<=passed
private=BASE/('redaction-'+NAME+'.private.json');assert stat.S_IMODE(private.stat().st_mode)==0o600
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==SOURCE
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True)
summary=dict(source_sha=SOURCE,counts=r['counts'],elapsed_seconds=r['elapsed_seconds'],source_paths=r['tracked_source_paths'],all_tracked_paths=r['all_tracked_paths'],drift=[],
    collection_junit_exact=True,design_kind_counts=dict(Counter(x['coverage_kind'] for x in coverage['mappings'])),design_count_is_not_executed_count=True,
    known_impact_oracle=stats,unknown_impact_oracle_records=0,unknown_impact_precision='NOT_MEASURED_IN_THIS_MODULE',continuation_unknown_refusal_nodes=unknown_nodes,
    full_html_flows=8,successful_six_goal_closures=5,manual_closures=4,explicit_source_accept_closures=1,
    actual_html_http_requests=sum(len(x['calls']) for x in flows),captured_python_test_body_http=load('-http-traffic.json')['count'],
    controlled_committed_response_loss_modes=['lost_choice','lost_adopt'],controlled_dto_or_fake_server_response_modes=[],
    actual_note_get403_direct_no_business_write=2,whole_authority_flow_no_write='NOT_CLAIMED; original observe reads may invalidate old evidence',
    locked_p1_new_action_refusal_nodes=[x for x in collection if 'test_original_p1_unlock' in x],lock_precision_pairs='NOT_RECORDED_AS_ORACLE_ROWS',
    source_dto_schema=1,continuation_dto_schema=1,actual_continuation_schema_samples=len(schema_samples),proof_version_2='Original live history validation exercised; exact version assertions belong to backend/review windows',
    private_mode='0600',private_values=len(json.loads(private.read_text())),private_values_exported=False,
    real_model_calls=0,real_browser='NOT_RUN',Windows='NOT_RUN',formal_AT_signoff='NOT_RUN',production='NOT_RUN',
    validator_sha256=sha(Path(__file__)),coverage_input_sha256=sha(BASE/'coverage-design.json'))
save('-validation.json',summary)
save('-html-summary.json',dict(source_sha=SOURCE,flows=[{k:v for k,v in x.items() if k!='calls'}|dict(requests=len(x['calls']),posts=sum(c['method']=='POST' for c in x['calls'])) for x in flows]))
save('-oracle-statistics.json',dict(source_sha=SOURCE,known=stats,unknown_impact='NOT_MEASURED',continuation_unknown_refusal_nodes=unknown_nodes))
print(json.dumps(summary,sort_keys=True))
