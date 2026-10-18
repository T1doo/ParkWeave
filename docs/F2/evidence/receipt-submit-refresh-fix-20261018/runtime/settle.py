from pathlib import Path
from collections import Counter
import hashlib,json,subprocess,sys,xml.etree.ElementTree as E
root=Path('/workspace/ParkWeave');r=root/'.runtime/receipt-submit-refresh-fix-20261018'
freeze=json.loads((r/'freeze.json').read_text());first=json.loads((r/'final-result.json').read_text());diagnostic=json.loads((r/'diagnostic-one-result.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==freeze['source_sha']
for result in (first,diagnostic):
 assert result['source_sha']==freeze['source_sha'] and result['input_count']==756 and not result['input_drift']
assert first['exit_code']==1 and first['failures']==0 and first['errors']==2 and diagnostic['exit_code']==0

def load(p):
 tree=E.parse(p);cases=tree.findall('.//testcase');identity=lambda c:(c.get('classname').split('.')[-1],c.get('name'))
 ids={identity(c) for c in cases};assert len(cases)==len(ids)
 passed={identity(c) for c in cases if not any(c.findall(x) for x in ('failure','error','skipped'))}
 return tree,cases,ids,passed
_,cases,ids,passed=load(r/'final.xml');counts=Counter(c.get('classname').split('.')[-1] for c in cases)
assert len(ids)==382 and len(passed)==381 and len(counts)==17 and counts['test_f2_t07_full_chain']==10 and counts['test_receipt_submit_recovery_browser']==15
_,dcases,dids,dpassed=load(r/'diagnostic-one.xml');assert len(dids)==len(dpassed)==1 and dids==ids-passed
assert (passed|dpassed)==ids
expected=json.loads((r/'frozen-inputs.json').read_text());assert len(expected)==756
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in expected.items())
xml=Path(sys.argv[1]);review=Path(sys.argv[2]);ind=json.loads(review.read_text());assert ind['source_sha']==freeze['source_sha']
itree,icases,iids,ipassed=load(xml)
assert len(iids)==len(ipassed)==54 and not any(itree.findall('.//'+x) for x in ('failure','error','skipped')) and iids<=ids
assert iids=={(c.get('classname').split('.')[-1],c.get('name')) for c in cases if c.get('classname').split('.')[-1] in ('test_receipt_submit_recovery_browser','test_receipt_submit_recovery_offline')}
first_ind=r/'independent/pw-ind-refresh-5bd4aec-25pof7u6/independent-final-review.json';assert hashlib.sha256(first_ind.read_bytes()).hexdigest()=='d50603964bfc4bbcbe679b68103fe98786014a9245c425ac2479dc05a90a9265'
accepted=dict(source_sha=freeze['source_sha'],src_tree=freeze['src_tree'],tests_tree=freeze['tests_tree'],unique=len(ids),complete_modules=len(counts),module_counts=dict(sorted(counts.items())),main_first_window=dict(passed=381,failures=0,errored_unique=1,error_elements=2,skipped=0,exit_code=1,seconds=first['elapsed_seconds']),directed_diagnostic=dict(passed=1,failures=0,errors=0,skipped=0,exit_code=0,seconds=diagnostic['elapsed_seconds'],existing_observer=True,original_budgets_and_assertions=True),single_full_green_window=False,all_main_unique_ids_have_passed_in_separate_frozen_windows=True,new_regressions=4,independent_first_window=dict(passed=53,failures=1,errors=0,skipped=0),independent_confirmation=dict(passed=54,failures=0,errors=0,skipped=0),independent_overlap=54,independent_all_in_main=True,counts_summed=False,input_count=756,input_drift=[],contract_sha256=freeze['contract_sha256'],startup_and_cleanup_first_root_cause='UNKNOWN; confirmations do not explain or repair original failures',whole_repository_tested=False,Windows='NOT_RUN',formal_AT='NOT_RUN',actual_sources='owned explicit SYNTHETIC fixtures only; no real source/backend/approval consumption',junit_path=str(r/'final.xml'),diagnostic_xml=str(r/'diagnostic-one.xml'),independent_xml=str(xml),independent_review=str(review))
(r/'accepted-tests.json').write_text(json.dumps(accepted,indent=2)+'\n')
(r/'independent-final-review.json').write_bytes(review.read_bytes())
print(json.dumps(accepted,indent=2))
