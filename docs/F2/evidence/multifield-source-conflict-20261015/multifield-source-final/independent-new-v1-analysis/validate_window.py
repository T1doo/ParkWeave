"""Independent frozen evidence audit. Run once after the named52 window closes."""
from pathlib import Path
from collections import Counter
import hashlib,json,re,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'.runtime/multifield-source-final';NAME='independent-new-v1'
DEST=BASE/(NAME+'-analysis');ART=BASE/'artifacts'/NAME
SHA='6187ed2cb933a26cf3d59b846178682e4f119745'
record=json.loads((BASE/(NAME+'.json')).read_text())
collection=json.loads((BASE/(NAME+'-collection.json')).read_text())
results={}
for case in ET.parse(BASE/(NAME+'.xml')).iter('testcase'):
    if not case.get('name') or not case.get('classname'):continue
    parts=case.get('classname').split('.')
    i=next(i for i,x in enumerate(parts) if x.startswith('test_'))
    node='tests/'+parts[i]+'.py::'+'::'.join(parts[i+1:]+[case.get('name')])
    assert node not in results
    results[node]=dict(status='FAIL' if case.find('failure') is not None else 'ERROR' if case.find('error') is not None else 'SKIP' if case.find('skipped') is not None else 'PASS',seconds=float(case.get('time','0')))
module_counts={}
for module in record['modules']:
    chosen={k:v for k,v in results.items() if k.startswith(module+'::')}
    module_counts[module]=dict(collected=sum(n.startswith(module+'::') for n in collection),executed=len(chosen),counts=dict(Counter(v['status'] for v in chosen.values())))

def read_records(module):
    rows={}
    for source in (ART/module).rglob('*.jsonl'):
        if source.name.endswith('.stdout.jsonl') or source.name.endswith('.private.json'):continue
        kind=source.name.rsplit('-',1)[0]
        for number,line in enumerate(source.read_text().splitlines(),1):
            value=json.loads(line)
            if not value.get('run_id'):continue
            if source.parent!=(ART/module):continue
            rows.setdefault(kind,[]).append(dict(value,artifact=str(source.relative_to(BASE)),line=number))
    return rows
new=read_records('test_multifield_source_package_independent')
prior=read_records('test_note_template_carry_independent')
saved_package_events={};history_conflicts=[]
for row in new.get('package-previews',[]):
    for event in row['view']['history']:
        if event['id'] in saved_package_events and saved_package_events[event['id']]!=event:
            history_conflicts.append(dict(event_id=event['id'],artifact=row['artifact'],line=row['line']))
        saved_package_events[event['id']]=event
saved_event_layers=dict(distinct_observed_v3_events=len(saved_package_events),
    plan_note_versions=dict(Counter(str(v['plan_note']['version']) for v in saved_package_events.values())),
    command_schemas=dict(Counter(str(v['plan_note']['request']['schema']) for v in saved_package_events.values())),
    commands_confirm_strict_true=all(type(v['plan_note']['request']['confirm_package']) is bool and v['plan_note']['request']['confirm_package'] is True for v in saved_package_events.values()),
    repeated_history_event_body_conflicts=history_conflicts,
    meaning='Schema1 read DTO, schema2 strict command, saved plan_note proofversion3; repeated reads deduplicated by actual event UUID')
record_source_mismatches=[dict(module=label,artifact=row['artifact'],line=row['line'],source_sha=row.get('source_sha'))
    for label,values in [('new',new),('prior',prior)] for kind,items in values.items() for row in items if row.get('source_sha')!=SHA]
prior_oracle=prior.get('oracle',[])
prior_precision=dict(rows=len(prior_oracle),expected_affected=sum(len(v['expected_affected']) for v in prior_oracle),
    expected_preserved=sum(len(v['expected_preserved']) for v in prior_oracle),missed=sum(v['missed_count'] for v in prior_oracle),
    wrong=sum(v['wrong_count'] for v in prior_oracle),wrong_preserved=sum(v['wrong_preserved_count'] for v in prior_oracle),
    scope='PRIOR_CARRY_MODULE_ONLY_NEVER_ADDED_TO_NEW24_PRECISION')

precision={}
for group,unknown in [('known',False),('intentional_UNKNOWN',True)]:
    chosen=[v for v in new.get('oracle',[]) if v['intentional_unknown']==unknown]
    precision[group]=dict(rows=len(chosen),expected_affected=sum(len(v['expected_affected']) for v in chosen),
        actual_affected=sum(len(v['actual_affected']) for v in chosen),expected_preserved=sum(len(v['expected_preserved']) for v in chosen),
        actual_preserved=sum(len(v['actual_preserved']) for v in chosen),missed=sum(v['missed_count'] for v in chosen),
        wrong=sum(v['wrong_count'] for v in chosen),wrong_preserved=sum(v['wrong_preserved_count'] for v in chosen),
        scenarios=dict(Counter(v['scenario'] for v in chosen)),
        meaning='CONSERVATIVE_UNKNOWN_ENVELOPE_ONLY' if unknown else 'INDEPENDENT_LITERAL_ADAPTER_SETS')
phase_free=lambda s:s.rsplit(' (',1)[0]
baselines={phase_free(v['test']):v for v in new.get('baseline',[]) if 'cases' in v}
unknown_dtos=[];ineligible_dtos=[]
for row in new.get('package-previews',[]):
    view=row['view']
    if view.get('unknown_scope')!='THIS_CASE':continue
    test=phase_free(row['test'])
    item=dict(test=test,artifact=row['artifact'],line=row['line'],new_action_templates=len(view['action_requests']),
        unknown_scope=view['unknown_scope'],affected_count=len(view['affected']),preserved_count=len(view['preserved']))
    if test.endswith('::test_no_manual_note_does_not_offer_new_package_mode'):
        ineligible_dtos.append(item);continue
    expected=set(baselines[test]['cases'][row['label']]['step_ids'].values())
    actual=set(view['affected'])
    item.update(expected_affected=sorted(expected),actual_affected=sorted(actual),missed=len(expected-actual),wrong=len(actual-expected),wrong_preserved=len(view['preserved']))
    unknown_dtos.append(item)

def html_evidence(module,rows,scope):
    items=[]
    for row in rows.get('html-results',[]):
        record_file=BASE/row['artifact'];trace=record_file.parent/row['trace']
        values=[json.loads(line) for line in trace.read_text().splitlines()]
        outputs=[v for v in values if v.get('scope')==scope]
        assert len(outputs)==1
        value=outputs[0];calls=value['calls'];mode=value['mode']
        recovery=[v for v in calls if v['method']=='GET' and ('/recovery/' in v['path'] or '/apply-requests/' in v['path'])]
        package_posts=[v for v in calls if v['method']=='POST' and v['path'].endswith('/plan-material-package/commands')]
        package_calls=[v for v in calls if '/plan-material-package' in v['path']]
        items.append(dict(module=module,mode=mode,trace=str(trace.relative_to(BASE)),sha256=hashlib.sha256(trace.read_bytes()).hexdigest(),
            checks=value['checks'],calls=len(calls),methods=dict(Counter(v['method'] for v in calls)),statuses=dict(Counter(str(v['status']) for v in calls)),
            full_shipped_HTML_script=True,actual_loopback_HTTP_ASGI_owned_PG=True,browser='NOT_RUN_NODE_VM_WITH_DOM_MECHANICS_DOUBLE',
            fake_DTO=value.get('fake_dto',False),original_recovery_GETs=len(recovery),
            controlled_client_response_discard=value.get('controlled_committed_response_loss',False),
            manual_preserved=value.get('manual_preserved'),driver_six_goals_current=value.get('six_goals_current'),
            driver_stable_plan_and_history=value.get('stable_plan_and_history'),
            prior_title_all_steps_exact=module=='test_note_template_carry_independent' and mode=='title_locked',
            lost_ACK_evidence='Actual backend committed response then controlled client discards; cold original-key GET' if mode in ('dual_merge_lost_ack','source_changed') else 'NOT_THIS_MODE',
            current_backend403=any(v['status']==403 for v in calls),
            material_package_POSTs=len(package_posts),
            material_package_request_schemas=dict(Counter(str(v['body']['schema']) for v in package_posts)),
            material_package_request_actions=dict(Counter(v['body']['action'] for v in package_posts)),
            material_package_confirm_strict_true=all(type(v['body']['confirm_package']) is bool and v['body']['confirm_package'] is True for v in package_posts) if package_posts else None,
            material_package_DTO_schema_layers=dict(Counter(str(v.get('response_scope'))+'@'+str(v.get('response_schema')) for v in package_calls)),
            original_plan_ADOPT_POSTs=sum(v['method']=='POST' and v['path'].endswith('/service-case-plan/adopt') for v in calls),
            original_plan_VERIFY_POSTs=sum(v['method']=='POST' and (v.get('body') or {}).get('action')=='VERIFY' and '/service-case-plan/' in v['path'] for v in calls),
            goal_results_GETs=sum(v['method']=='GET' and v['path'].endswith('/goal-results') for v in calls),
            worklist_GETs=sum(v['method']=='GET' and v['path'].startswith('/api/cases/worklist') for v in calls),
            six_goal_worklist_closure=module=='test_multifield_source_package_independent' and mode in ('summary_keep','dual_merge_lost_ack')))
    return items
new_html=html_evidence('test_multifield_source_package_independent',new,'FULL_ORIGINAL_HTML_MULTIFIELD_PACKAGE_ACTUAL_HTTP_ASGI_OWNED_PG')
prior_html=html_evidence('test_note_template_carry_independent',prior,'FULL_ORIGINAL_HTML_NOTE_TEMPLATE_CARRY_ACTUAL_HTTP_ASGI_OWNED_PG')

plan=json.loads((DEST/'mapping-input.json').read_text())
coverage=[]
for rule in plan['mapping']:
    chosen={k:v['status'] for k,v in results.items() if k.startswith('tests/test_multifield_source_package_independent.py::') and any(k.split('::',1)[1]==a or k.split('::',1)[1].startswith(a+'[') for a in rule['nodes'])}
    status=rule['planned_scope']
    if chosen and set(chosen.values())!={'PASS'}:status='FAIL'
    elif rule['nodes'] and not chosen:status='NOT_RUN'
    coverage.append(dict(rule,status=status,window=NAME,source_sha=SHA,actual_named_tests=chosen))
coverage_report=dict(kind='ACTUAL_FROZEN_BOUNDED_DESIGN_MAPPING',source_sha=SHA,oracle=plan['oracle'],oracle_sha256=plan['oracle_sha256'],
    design_denominator=40,pytest_new_module_denominator=24,scope_status_counts=dict(Counter(v['status'] for v in coverage)),
    status_policy=plan['status_policy'],rows=coverage)
(DEST/'design40-actual-mapping.json').write_text(json.dumps(coverage_report,indent=2,ensure_ascii=False)+'\n')

private_files=[BASE/('redaction-'+NAME+'.private.json'),*(ART.rglob('*.private.json')),*((BASE/NAME).rglob('*.private.json'))]
values=set()
def find_values(x):
    if isinstance(x,str) and re.fullmatch('[A-Za-z0-9_-]{32,128}',x):values.add(x)
    elif isinstance(x,list):
        for item in x:find_values(item)
    elif isinstance(x,dict):
        for item in x.values():find_values(item)
for source in private_files:
    if source.exists():find_values(json.loads(source.read_text()))
needles={v for v in values}|{v[:16] for v in values}
needle=re.compile('|'.join(re.escape(v) for v in sorted(needles,key=len,reverse=True))) if needles else None
matches=[]
public_artifacts=[p for p in ART.rglob('*') if p.is_file() and not p.name.endswith('.private.json')]
for source in [BASE/(NAME+'.log'),BASE/(NAME+'.xml'),*public_artifacts]:
    count=len(needle.findall(source.read_text(errors='replace'))) if needle else 0
    if count:matches.append(dict(path=str(source.relative_to(BASE)),known_synthetic_full_or_prefix16_matches=count))
index=[]
for source in [BASE/(NAME+'.json'),BASE/(NAME+'.log'),BASE/(NAME+'.xml'),BASE/(NAME+'-collection.json'),BASE/(NAME+'-before.json'),BASE/(NAME+'-after.json'),BASE/(NAME+'-all-tracked-before.json'),BASE/(NAME+'-all-tracked-after.json'),*public_artifacts]:
    index.append(dict(path=str(source.relative_to(BASE)),bytes=source.stat().st_size,sha256=hashlib.sha256(source.read_bytes()).hexdigest(),private=False))
(DEST/'evidence-index.json').write_text(json.dumps(index,indent=2)+'\n')
report=dict(kind='INDEPENDENT_FROZEN_COMPLETE_WINDOW_VALIDATION',source_sha=SHA,window=NAME,exit_code=record['exit_code'],elapsed_seconds=record['elapsed_seconds'],
    validator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    mapping_input_sha256=hashlib.sha256((DEST/'mapping-input.json').read_bytes()).hexdigest(),
    counts=record['counts'],modules=module_counts,collected=len(collection),named_executed=len(results),collection_junit_exact=set(collection)==set(results),
    paths_compared=dict(source=record['tracked_source_paths'],all_tracked=record['all_tracked_paths']),
    drift=dict(source=record['source_drift'],all_tracked=record['all_tracked_drift'],runner_helpers=record['runner_drift']),
    capture_plugin_provenance=record['capture_plugin_provenance'],literal_precision=precision,
    observed_package_history_schema_layers=saved_event_layers,
    saved_record_source_mismatches=record_source_mismatches,
    prior_carry_literal_precision=prior_precision,
    source_UNKNOWN_DTO_envelopes=unknown_dtos,ineligible_no_MANUAL_envelopes=ineligible_dtos,
    new_HTML=new_html,prior_HTML=prior_html,
    new_closure_observations=len(new.get('closures',[])),new_distinct_named_closure_tests=len({phase_free(v['test']) for v in new.get('closures',[])}),
    new_closures_six_goals_current=sum(bool(v.get('six_goals_current')) for v in new.get('closures',[])),
    new_closures_B_original_plan_byte_exact=sum(bool(v.get('unaffected_B_exact')) for v in new.get('closures',[])),
    new_preserved_lock_objects_exact=dict(receipt_only_P1_P2_P3=3 if results.get('tests/test_multifield_source_package_independent.py::test_real_six_goal_receipt_only_keeps_all_unaffected_locks',{}).get('status')=='PASS' else None,
        capacity_receipt_union_A_B_P1=2 if results.get('tests/test_multifield_source_package_independent.py::test_selected_capacity_and_actual_adapter_receipt_union_cannot_hide_missed_source',{}).get('status')=='PASS' else None,
        meaning='Five whole step objects compared with original manual lock and verified evidence; affected locks explicitly unlocked are separate guard coverage'),
    new_record_counts={k:len(v) for k,v in new.items()},prior_record_counts={k:len(v) for k,v in prior.items()},
    design40_scope_counts=coverage_report['scope_status_counts'],Python_API_request_total='NOT_RECORDED_BY_FROZEN_CAPTURE_PLUGIN',
    HTTP_claim='Full Node native-fetch trace exact requests; API tests use original actual loopback client/ASGI/ownedPG and saved response/evidence; no transfer of development HTTP counts',
    private_registries=sum(p.exists() for p in private_files),known_synthetic_values=len(values),public_raw_or_structured_known_full_or_prefix16_matches=matches,
    development_scores_migrated=False,NOT_RUN=['real browser','Windows','formal AT','real model','production','deployment'])
(DEST/'validation.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:report[k] for k in ['source_sha','counts','modules','collected','named_executed','collection_junit_exact','paths_compared','drift','literal_precision','new_record_counts','design40_scope_counts','private_registries','known_synthetic_values','public_raw_or_structured_known_full_or_prefix16_matches']},indent=2))
assert record['source_sha']==SHA and record['exit_code']==0 and record['counts']==dict(PASS=52,FAIL=0,ERROR=0,SKIP=0)
assert len(results)==len(collection)==52 and set(results)==set(collection)
assert record['tracked_source_paths']==617 and record['all_tracked_paths']==15418
assert not record['source_drift'] and not record['all_tracked_drift'] and not record['runner_drift']
assert not record_source_mismatches
assert saved_event_layers['plan_note_versions']=={'3':len(saved_package_events)} and saved_event_layers['command_schemas']=={'2':len(saved_package_events)} and saved_event_layers['commands_confirm_strict_true']
assert not history_conflicts
assert all(not v['missed'] and not v['wrong'] and not v['wrong_preserved'] for v in precision.values())
assert all(not v['missed'] and not v['wrong'] and not v['wrong_preserved'] and not v['new_action_templates'] for v in unknown_dtos)
assert not matches
assert len(new_html)==4 and len(prior_html)==2 and all(not v['fake_DTO'] for v in new_html)
