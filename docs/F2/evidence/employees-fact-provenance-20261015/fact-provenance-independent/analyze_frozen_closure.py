"""Independent mechanical receipt/trace validation. No product import or business test."""
import hashlib,json
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path('/workspace/ParkWeave')
BASE=ROOT/'.runtime/fact-provenance-independent'
WINDOW=ROOT/'.runtime/fact-provenance-final-v2/new'
TARGET='8fe3e6c6ebdb14366dd80032c953c79e746e3fd1'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stage_free(s):return s.rsplit(' (',1)[0]
def main():
 out=BASE/'final-8fe';receipt=json.loads(WINDOW.with_suffix('.json').read_text())
 assert receipt['source_sha']==TARGET and receipt['exit_code']==0 and receipt['counts']==dict(PASS=61,FAIL=0,ERROR=0,SKIP=0)
 for k in ('source_drift','all_tracked_drift','runner_drift'):assert not receipt[k]
 assert receipt['collection_junit_exact_match'] and receipt['unique_junit_nodes']
 cases=ET.parse(WINDOW.with_suffix('.xml')).getroot().findall('.//testcase')
 independent=[c for c in cases if c.get('classname')=='tests.test_employees_fact_provenance_independent']
 assert len(independent)==23 and all(c.find('failure') is None and c.find('error') is None and c.find('skipped') is None for c in independent)
 a=ROOT/'.runtime/fact-provenance-final-v2/artifacts/new/test_employees_fact_provenance_independent'
 def records(kind):
  values=[]
  for p in a.glob(kind+'-*.jsonl'):values.extend(json.loads(x) for x in p.read_text().splitlines() if x.strip())
  return values
 baseline={stage_free(r['test']):r for r in records('baseline')};assert len(baseline)==23
 oracle_path=ROOT/'docs/F2/EmployeesFactProvenanceOracle-20261015.json';oracle={r['id']:r['expected'] for r in json.loads(oracle_path.read_text())['rows']}
 literal=records('oracle');unknown=0
 for r in literal:
  b=baseline[stage_free(r['test'])];expected=oracle[r['oracle_id']];ids=b['step_ids']
  assert r['actual_affected']==[ids[x] for x in expected['affected']]
  assert r['actual_preserved']==[ids[x] for x in expected['preserved']]
  assert r['unknown_scope']==expected['unknown_scope']
  unknown+=r['unknown_scope']=='THIS_CASE'
 assert literal and unknown==3
 exact=records('exact-provenance')
 assert exact and all(r['original_row_hashes_dates_match'] and r['no_raw_values_in_projection'] for r in exact)
 closures=records('closures');assert closures and all(r['six_goals_current'] and r['stable_ids_history'] and r['worklist_complete'] and r['worklist_recorded_only'] for r in closures)
 compatibility=records('compatibility')
 assert any(r.get('enhanced_v3_then_legacy_v2') and r.get('scope_not_sticky') and r.get('original_cold_get') for r in compatibility)
 assert {r.get('unsupported_combination') for r in compatibility if r.get('enhanced_rejected') and r.get('legacy_preview_unchanged')}=={'MANUAL','MATERIAL_PACKAGE'}
 html=json.loads((out/'html.json').read_text());coverage=json.loads((out/'coverage.json').read_text())
 assert html['source_sha']==coverage['source_sha']==TARGET
 candidates=json.loads((BASE/'candidate-v3.json').read_text())
 for path,meta in candidates['files'].items():assert sha(ROOT/path)==meta['sha256']
 # Exact row statuses remain in coverage.json; this gate never rebrands variants.
 result=dict(status='LIMITED_PASS',source_sha=TARGET,
  scope='USER_ASSERTED_SYNTHETIC_EMPLOYEES_ORIGINAL_CASE_PURPOSE_REGISTERED_HISTORY',
  new_complete_modules=4,new_window_counts=receipt['counts'],independent_test_items=23,
  other_new_items=dict(pure_history_receipt_schema_tests=37,client_wrapper_pytest_items=1,controlled_client_branches=6),
  html_modes=4,html_native_fetches=html['actual_native_fetches'],literal_actual_checks=len(literal),intentional_unknown_checks=unknown,
  exact_registered_projection_checks=len(exact),six_goal_and_worklist_closure_records=len(closures),
  manual_and_package_incompatibility_explicit=True,enhanced_scope_not_sticky_default_v2_compatible=True,
  original_backend_post_and_get_receipts=True,lost_ack_exact_idempotency_header_recorded=True,
  source_drift=[],tracked_drift=[],helper_drift=[],collection_junit_exact_match=True,
  coverage_counts=coverage['counts'],
  evidence=dict(runner=str(WINDOW.with_suffix('.json')),runner_sha256=sha(WINDOW.with_suffix('.json')),
     junit=str(WINDOW.with_suffix('.xml')),junit_sha256=sha(WINDOW.with_suffix('.xml')),
     coverage=str(out/'coverage.json'),coverage_sha256=sha(out/'coverage.json'),html=str(out/'html.json'),html_sha256=sha(out/'html.json')),
  limitations=['Only the frozen bounded employees source scope. No arbitrary graph or semantic truth inference.',
    'Pure rejection and design variants are not full HTTP literal partition tests; NOT_RUN rows remain explicit.',
    'HTML counts are native fetch only. Python control original API calls additional; combined total NOT_RECORDED.',
    'Node mechanical DOM is not a real browser. Windows, formal AT, real models and production NOT_RUN.',
    'This new61 module gate does not substitute for root complete103 regression, independent final archive audit or remote verification.'])
 (out/'closure.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:result[k] for k in ('status','source_sha','independent_test_items','html_native_fetches','literal_actual_checks','intentional_unknown_checks','coverage_counts')}))
if __name__=='__main__':main()
