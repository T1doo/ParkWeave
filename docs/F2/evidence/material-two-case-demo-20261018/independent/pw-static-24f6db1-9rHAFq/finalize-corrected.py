from pathlib import Path
from hashlib import sha256
import json,subprocess
ROOT=Path('/workspace/ParkWeave')
R=ROOT/'.runtime/material-two-case-demo-20261018'
OUT=Path(__file__).parent
source='24f6db12490b7ba7f01099d311af97e926eeddd0'
def sha(b):return sha256(b).hexdigest()
def dump(name,x):(OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def strict(p):
 def pairs(v):
  d={}
  for k,x in v:
   if k in d:raise ValueError('duplicate JSON member')
   d[k]=x
  return d
 def bad(v):raise ValueError('non-finite JSON')
 return json.loads(p.read_text(),object_pairs_hook=pairs,parse_constant=bad)
report=strict(OUT/'audit-result-draft.json')
prior=strict(OUT/'inputs-pre.json')
extra=[R/'text-generator-source-binding.json',R/'original-material-text-snippet.js',ROOT/'deliverables/material-only-demo-20261018/material-A.txt',ROOT/'deliverables/material-only-demo-20261018/material-B.txt']
pre={**prior,**{str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in extra}}
assert all(sha((ROOT/k).read_bytes())==v for k,v in prior.items())
dump('final-inputs-pre.json',pre)
checks=[]
def check(name,result):
 assert result,name
 checks.append(name)
blob=git('show',source+':src/parkweave/web.html')
html=blob.decode()
check('full_HTML_actual_bytes_equal_frozen_Git_blob',blob==(ROOT/'src/parkweave/web.html').read_bytes())
truth=next(line for line in html.splitlines() if line.startswith('const readinessTruth='))
reasons=next(line for line in html.splitlines() if line.startswith('const readinessReasons='))
a=html.index('function materialPackText(x){');b=html.index('async function materialPackAction',a)
expected=(truth+'\n'+reasons+'\n'+html[a:b]).encode()
bind=strict(R/'text-generator-source-binding.json')
check('public_JS_snippet_matches_independent_frozen_blob_extraction',expected==(R/'original-material-text-snippet.js').read_bytes())
check('4242_byte_snippet_SHA256_exact',len(expected)==bind['snippet_bytes']==4242 and sha(expected)==bind['snippet_sha256']=='eae5ebba1f53241613e41fe41ef6445b0ac8b701c857b37fd74f065278a0645b')
check('snippet_binding_full_HTML_SHA256_correct',bind['source_commit']==source and sha(blob)==bind['original_html_sha256'])
exports=[]
for label in ('A','B'):
 p=ROOT/f'deliverables/material-only-demo-20261018/material-{label}.txt'
 raw=p.read_bytes();text=raw.decode('utf-8')
 e=strict(R/f'export-{label}.json');er=strict(R/f'export-{label}-restart.json')
 readiness=strict(R/f'readiness-{label}.json')
 check(label+'_public_TXT_actual_size_hash_matches_both_parent_export_metadata',len(raw)==e['bytes']==er['bytes'] and sha(raw)==e['sha256']==er['sha256'])
 check(label+'_export_source_hash_is_exact_snippet_not_whole_HTML',e['source_js_sha256']==er['source_js_sha256']==sha(expected))
 check(label+'_public_TXT_subject_materials_and_limits_present',readiness['case_id'] in text and readiness['preparation_id'] in text and readiness['source_sha256'] in text and all(m['id'] in text and m['source_sha256'] in text and m['text'] in text for m in readiness['sources']['materials']) and 'Case目标未完成' in text and 'NOT_SUBMITTED' in text and '真实性与资格：未核验' in text)
 exports.append(dict(label=label,public_path=str(p.relative_to(ROOT)),bytes=len(raw),sha256=sha(raw),matches_initial_and_restart_export_metadata=True,private_original_bytes_read=False))
post={k:sha((ROOT/k).read_bytes()) for k in pre}
dump('final-inputs-post.json',post)
check('all_35_final_review_inputs_zero_drift',post==pre and len(pre)==35)
check('shared_HEAD_still_exact_frozen_source',git('rev-parse','HEAD').decode().strip()==source)
report['checks']+=checks
report['check_count']=len(report['checks'])
report['input_count']=len(pre)
report['input_manifest_pre']='final-inputs-pre.json'
report['input_manifest_post']='final-inputs-post.json'
report['evidence_count']=23
report['public_export_files_actual_hash_checks']=exports
report['pure_JS_snippet_binding']=dict(bytes=len(expected),sha256=sha(expected),independently_extracted_from_frozen_Git_blob=True,JS_execution_performed=False,whole_HTML_sha256=sha(blob))
report['limits'][2]='Public A/B TXT copies were read and hashed against the initial/restart export metadata; private original/restart TXT bytes were not read, so their direct byte equality remains parent-reported. Parent NodeVM runs are not browser downloads.'
report['evidence_sources_scope']='23 parent-authored redacted JSON records, one original sandbox error log, a public pure-JS source snippet and two public synthetic TXT copies; 8 reviewed source/helper files. Source/helper files were read, not executed.'
report['harness_history']=[dict(stage='initial_static_public_evidence_audit',exit_code=0,checks=61),dict(stage='first_finalization',exit_code=1,reason='reviewer hardcoded 36 inputs but deduplicated set had 35',actual_prepost_inputs=35,actual_input_drift=0,source='finalize.py',failure_record='finalization-first-failure.json'),dict(stage='corrected_finalization',exit_code=0,source='finalize-corrected.py',product_changes=False,business_execution=False)]
report['verification_exit_code']=0
report['findings_status']='No open P1/P2 within this static and evidence-review scope. No independent business-test PASS is asserted.'
report['report_path']=str(OUT/'independent-final-review.json')
dump('independent-final-review.json',report)
result=dict(source_sha=source,src_tree=report['src_tree'],status='PASS_STATIC_AND_PUBLIC_EVIDENCE_REVIEW',P1=0,P2=0,blockers=0,checks=report['check_count'],reviewed_inputs=35,input_drift=0,independent_business_tests=0,JS_snippet_bytes=len(expected),public_TXT_files_hashed=2,report=str(OUT/'independent-final-review.json'),report_sha256=sha((OUT/'independent-final-review.json').read_bytes()))
dump('finalization-result.json',result)
print(json.dumps(result,ensure_ascii=False))
