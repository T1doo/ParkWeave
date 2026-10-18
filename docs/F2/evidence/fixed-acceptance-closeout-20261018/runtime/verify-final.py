from pathlib import Path
import hashlib,json,xml.etree.ElementTree as ET

root=Path('/workspace/ParkWeave');run=root/'.runtime/fixed-acceptance-closeout-20261018'
prior=run/'frozen-7f02fe3f';sup=run/'supplement-7f02fe3f';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def maps(folder):
    values=[json.loads((folder/name).read_text()) for name in ['shared-before.json','mirror-before.json','shared-after.json','mirror-after.json']]
    assert all(v==values[0] for v in values)
    assert all(sha(root/path)==value for path,value in values[0].items())
    return values[0]
a=maps(prior);b=maps(sup);assert len(a)==809 and len(b)==812 and all(b[p]==v for p,v in a.items())
phase=[json.loads(line) for line in (prior/'calls.jsonl').read_text().splitlines()]
calls=[p for p in phase if p['when']=='call'];assert len(calls)==25
passed={p['nodeid'] for p in calls if p['outcome']=='passed'};failed={p['nodeid'] for p in calls if p['outcome']=='failed'}
target='tests/test_acceptance_runner.py::test_sources_archive_integrity'
assert len(passed)==24 and failed=={target} and all(p['outcome']=='passed' for p in phase if p['when']!='call')
later=[json.loads(line) for line in (sup/'calls.jsonl').read_text().splitlines()];assert len(later)==3 and all(p['outcome']=='passed' and p['nodeid']==target for p in later)
for folder in [prior,sup]:
    origins=json.loads((folder/'module-origins.json').read_text());assert origins and all(v['within_mirror'] and sha(Path(v['path']))==v['sha256'] for v in origins.values())
observed=json.loads((sup/'actual-source-verification.json').read_text());assert observed['files']==381 and observed['aggregate_bytes']==4772466 and observed['source_binding_passed']
batches=[c for c in observed['calls'] if c['args']==['cat-file','--batch']]
assert len(batches)==2 and [c['body_bytes'] for c in batches]==[4174562,597904]
assert [p for batch in batches for p in batch['paths']]==sorted(observed['hashes'])
runner=json.loads((sup/'original-runner-at13.json').read_text());assert runner['whole_AT_EX']=='NOT_RUN' and runner['execution_exit_code']==0 and not runner['full_regression']
assert runner['source_binding']==dict(state='AVAILABLE',head_sha='7f02fe3f463fb402eb497fb4342d93037b24cc18')
assert runner['engineering_total_counts']==dict(PASS=1,FAIL=0,SKIP=0)
assert runner['cases'][0]['id']=='AT-13' and runner['cases'][0]['whole_status']=='NOT_RUN' and runner['cases'][0]['engineering_subset']=='PARTIAL_PASS'
for p,value in runner['tested_source_sha256'].items():assert sha(root/p)==value
junit=list((sup/'original-runner-artifacts').glob('*.xml'));assert len(junit)==1
cases=ET.parse(junit[0]).findall('.//testcase');assert len(cases)==1 and cases[0].get('name')=='test_api_worker_process_restart_and_business_separation' and cases[0].find('failure') is None and cases[0].find('error') is None
audit=json.loads((root/'docs/F2/FixedAcceptanceCloseout-20261018.json').read_text());assert len(audit['rows'])==42 and all(row['original_status']==row['binding_whole_status']=='NOT_RUN' and row['new_whole_PASS'] is False for row in audit['rows'])
result=dict(tested_sha='7f02fe3f463fb402eb497fb4342d93037b24cc18',frozen_unit_window=dict(PASS=24,FAIL=1,ERROR=0,SKIP=0,junit_seconds=4.120,failure='Frozen mirror omitted original V1 document dependencies; product/test bytes unchanged'),document_supplement=dict(PASS=1,FAIL=0,junit_seconds=0.257,previous_24_not_repeated=True),original_AT13_runner=dict(engineering_PASS=1,whole_status='NOT_RUN',engineering_subset='PARTIAL_PASS',junit_seconds=8.131,actual_worker=True,new_owned_synthetic_PG=True),effective_unique_passed_nodes=26,single_window_26_PASS_claim=False,prior_809_four_maps_equal=True,supplement_812_four_maps_equal=True,all_prior_inputs_unchanged=True,all_current_381_sources_verified=True,total_test_blob_bytes=4772466,batch_bodies=[4174562,597904],original_fixed_definitions_and_whole_status_unchanged=True,full_regression=False,independent_dynamic=0,independent_static_rows=10,old_AT21_AT32_risk_and_HTTP_unknown_windows_not_retried=True,historical_HTTP_timeout='UNKNOWN_OPEN',API_worker_per_module_import_origins_not_instrumented=True)
(run/'root-verification-7f02fe3f.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
