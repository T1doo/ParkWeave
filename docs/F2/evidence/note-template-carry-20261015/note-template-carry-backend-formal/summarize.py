from pathlib import Path
from collections import defaultdict,Counter
import hashlib,json
ROOT=Path('/workspace/ParkWeave');OUT=ROOT/'.runtime/note-template-carry-backend-formal';ART=OUT/'artifacts/formal7'
result=json.loads((OUT/'result.json').read_text());SHA=result['source_sha']
def meta(p):return dict(path=str(p.relative_to(OUT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),size=p.stat().st_size)
expected={'test_typed_source_impact_independent':6,'test_shared_source_cases_independent':9,'test_service_release_preflight_independent':14,'test_at24_27_change_batch_independent':12}
html=[];bad=[];oracles=[];locks=[]
for group in expected:
 directory=ART/group
 for path in sorted(directory.glob('*.stdout.jsonl')):
  rows=[]
  for line_number,line in enumerate(path.read_text().splitlines(),1):
   if not line.strip():continue
   try:rows.append(json.loads(line))
   except ValueError:bad.append(dict(**meta(path),line=line_number,error='NON_JSON_STDOUT'))
  finals=[r for r in rows if isinstance(r,dict) and str(r.get('scope','')).startswith('FULL_ORIGINAL_HTML_')]
  if len(finals)!=1:bad.append(dict(**meta(path),error='FINAL_SCOPE_COUNT',count=len(finals)));continue
  final=finals[0];entry=dict(group=group,**meta(path),scope=final['scope'],mode=final.get('mode'),checks=final.get('checks'),http_call_records=len(final.get('calls',[])),negative_transport_fixture=final.get('negative_transport_fixture') is True,real_browser='NOT_RUN',http_methods=dict(Counter(c.get('method','UNKNOWN') for c in final.get('calls',[]))),http_statuses=dict(Counter(str(c.get('status','UNKNOWN')) for c in final.get('calls',[]))))
  entry['response_evidence']='CONTROLLED_CLIENT_NEGATIVE' if entry['negative_transport_fixture'] else 'REAL_BACKEND_COMMIT_WITH_CONTROLLED_RECEIPT_LOSS' if str(entry['mode']).startswith('lost') or str(entry['mode']).endswith('lost_adopt') else 'REAL_BACKEND_RESPONSE_SCENARIO'
  err=path.with_name(path.name.replace('.stdout.jsonl','.stderr.log'));entry['stderr']=meta(err) if err.exists() else None;html.append(entry)
 for path in sorted(directory.glob('oracle-*.jsonl')):
  for index,line in enumerate(path.read_text().splitlines(),1):
   if not line.strip():continue
   value=json.loads(line);a=set(value['expected_affected']);got=set(value['actual_affected']);p=set(value['expected_preserved']);kept=set(value['actual_preserved'])
   declared=bool(value.get('intentional_unknown') or value.get('intentional_unknown_expansion'))
   actual_unknown=bool(value.get('unknown_scope') or value.get('expected_classification')=='UNKNOWN' or value.get('expected_state') in ('UNKNOWN','NO_PLAN','NO_PREPARATION'))
   category='declared_unknown' if declared else 'additional_graph_unknown' if actual_unknown else 'known_partition_by_record'
   row=dict(group=group,raw=meta(path),line=index,source_sha=value.get('head',value.get('source_sha')),test=value.get('test'),scenario=value.get('scenario'),case=value.get('case',value.get('case_id')),category=category,declared_unknown=declared,unknown_scope=value.get('unknown_scope'),expected_state=value.get('expected_state'),actual_state=value.get('actual_state'),expected_classification=value.get('expected_classification'),actual_classification=value.get('actual_classification'),expected_affected_pairs=len(a),actual_affected_pairs=len(got),expected_preserved_pairs=len(p),missed=len(a-got),wrongly_affected=len(got-a),wrongly_preserved=len(kept-p),missing_preserved=len(p-kept),raw_wrong_preserved_count=value.get('wrong_preserved_count'),lock_comparison_recorded='expected_locked' in value)
   if 'expected_locked' in value:row.update(expected_locked_pairs=len(set(value['expected_locked'])),actual_locked_pairs=len(set(value['actual_locked'])),wrong_lock_pairs=len(set(value['expected_locked'])^set(value['actual_locked'])))
   oracles.append(row)
 for path in sorted(directory.glob('at-results-*.jsonl')):
  for index,line in enumerate(path.read_text().splitlines(),1):
   value=json.loads(line)
   if value.get('p1_lock_exact') is True:locks.append(dict(raw=meta(path),line=index,scenario=value.get('scenario'),case=value.get('case'),p1_lock_exact=True,all_six_local_outputs_verified=value.get('all_six_local_outputs_verified')))
summary={}
for group in expected:
 groups={}
 for category in ('known_partition_by_record','declared_unknown','additional_graph_unknown'):
  rows=[r for r in oracles if r['group']==group and r['category']==category]
  groups[category]=dict(records=len(rows),expected_affected_step_pairs=sum(r['expected_affected_pairs'] for r in rows),expected_preserved_step_pairs=sum(r['expected_preserved_pairs'] for r in rows),missed=sum(r['missed'] for r in rows),wrongly_affected=sum(r['wrongly_affected'] for r in rows),wrongly_preserved=sum(r['wrongly_preserved'] for r in rows),missing_preserved=sum(r['missing_preserved'] for r in rows),records_with_lock_fields=sum(r['lock_comparison_recorded'] for r in rows),wrong_lock_pairs=sum(r.get('wrong_lock_pairs',0) for r in rows))
 summary[group]=groups
html_result=dict(source_sha=SHA,expected_per_group=expected,actual_per_group={g:sum(r['group']==g for r in html) for g in expected},total=len(html),expected_total=41,exact_41=len(html)==41 and all(sum(r['group']==g for r in html)==n for g,n in expected.items()),trace_errors=bad,total_node_call_records=sum(r['http_call_records'] for r in html),negative_transport_fixture_traces=sum(r['negative_transport_fixture'] for r in html),backend_response_scenario_traces=sum(not r['negative_transport_fixture'] for r in html),response_evidence_categories=dict(Counter(r['response_evidence'] for r in html)),http_call_record_scope='Page driver fetch records after Python fixture initialization; excludes fixture/setup HTTP and control messages. Controlled response/transport fixture traces are listed separately and are not untouched-backend refusal evidence.',traces=html,real_browser='NOT_RUN',fixture_backend='Original HTML in Node VM/DOM shim → actual loopback HTTP/ASGI → owned PostgreSQL')
(OUT/'html-summary.json').write_text(json.dumps(html_result,ensure_ascii=False,indent=2)+'\n')
stats=dict(source_sha=SHA,groups=summary,rows=oracles,selected_capacity_p1_lock_preservation=locks,scope='Literal affected/preserved observations, not test-count or product-completion percentage',unknown_note='Classify only fields actually recorded. Reader current-availability UNKNOWN can coexist with a structurally comparable graph; absent availability fields are not evidence of current availability.',missing_lock_fields_note='No lock fields means not recorded, never a zero-lock-test claim')
(OUT/'oracle-statistics.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2)+'\n')
artifacts=[dict(**meta(p),private='private' in p.name) for directory in (ART,OUT/'artifact-legacy') for p in sorted(directory.rglob('*')) if p.is_file()]
(OUT/'artifacts-index.json').write_text(json.dumps(dict(source_sha=SHA,files=artifacts,count=len(artifacts)),indent=2)+'\n')
handoff=dict(source_sha=SHA,counts=result['counts'],collection=result['collected'],exact_node_match=result['collection_junit_exact_match'],unique_nodes=result['unique_collection_nodes'] and result['unique_junit_nodes'],source_count=result['source_count'],tracked_count=result['tracked_count'],source_drift=result['source_drift'],tracked_drift=result['tracked_drift'],status_after=result['status_after'],elapsed_seconds=result['elapsed_seconds'],html=html_result['actual_per_group'],total_html=len(html),raw_artifact_count=len(artifacts),legacy_artifact_files=sum(str(row['path']).startswith('artifact-legacy/') for row in artifacts),oracle_records=len(oracles),result_path=str(OUT/'result.json'),html_summary=str(OUT/'html-summary.json'),oracle_statistics=str(OUT/'oracle-statistics.json'),artifacts_index=str(OUT/'artifacts-index.json'),limits=['Seven complete affected modules, not whole repository','Linux synthetic engineering evidence; Windows, real browser, formal business AT, real model and production NOT_RUN','Raw private fixture registries remain private; root handles exact-value export redaction'])
(OUT/'final-handoff.json').write_text(json.dumps(handoff,ensure_ascii=False,indent=2)+'\n');print(json.dumps(handoff,ensure_ascii=False))
