from pathlib import Path
from collections import Counter
import hashlib,json,subprocess,xml.etree.ElementTree as E
root=Path('/workspace/ParkWeave');r=root/'.runtime/receipt-submit-recovery-20261018'
freeze=json.loads((r/'frozen.json').read_text());result=json.loads((r/'final-v2-result.json').read_text())
assert result['source_sha']==freeze['source_sha'] and result['exit_code']==0 and result['input_count']==755 and not result['input_drift']
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==freeze['source_sha']
tree=E.parse(r/'final-v2.xml');cases=tree.findall('.//testcase');identity=lambda c:(c.get('classname').split('.')[-1],c.get('name'))
ids={identity(c) for c in cases};counts=Counter(c.get('classname').split('.')[-1] for c in cases)
assert len(cases)==len(ids) and not tree.findall('.//failure') and not tree.findall('.//error') and not tree.findall('.//skipped') and len(counts)==16
newcounts={'test_receipt_submit_recovery':38,'test_receipt_submit_recovery_offline':39,'test_receipt_submit_recovery_browser':11,'test_receipt_submit_recovery_frontier':1}
assert all(counts[k]==v for k,v in newcounts.items())
expected=json.loads((r/'frozen-inputs.json').read_text());assert len(expected)==755
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in expected.items())
ind=json.loads((r/'independent-final-review.json').read_text());assert ind['source_sha']==freeze['source_sha']
xmls=list((r/'independent').rglob('independent.xml'));assert len(xmls)==1
itree=E.parse(xmls[0]);icases=itree.findall('.//testcase');iids={identity(c) for c in icases}
assert len(icases)==len(iids)==89 and not itree.findall('.//failure') and not itree.findall('.//error') and not itree.findall('.//skipped') and iids<=ids
assert iids=={identity(c) for c in cases if c.get('classname').split('.')[-1] in newcounts}
accepted=dict(source_sha=freeze['source_sha'],source_tree=freeze['source_tree'],tests_tree=freeze['tests_tree'],passed=len(cases),unique=len(ids),failures=0,errors=0,skipped=0,complete_modules=len(counts),module_counts=dict(sorted(counts.items())),new_tests=89,independent_passed=89,independent_overlap=89,independent_all_in_main=True,counts_summed=False,input_count=755,input_drift=[],contract_sha256=freeze['contract_sha256'],outer_seconds=result['elapsed_seconds'],whole_repository_tested=False,Windows='NOT_RUN',formal_AT='NOT_RUN',actual_sources='owned explicit SYNTHETIC fixtures only; no real source/backend/approval consumption',junit_path=str(r/'final-v2.xml'),independent_xml=str(xmls[0]))
(r/'accepted-tests.json').write_text(json.dumps(accepted,indent=2)+'\n');print(json.dumps(accepted,indent=2))
