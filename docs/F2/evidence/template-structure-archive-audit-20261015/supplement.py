from pathlib import Path
import hashlib,json,re,subprocess,xml.etree.ElementTree as E
root=Path('/workspace/ParkWeave');base=root/'docs/F2/evidence/template-structure-migration-20261015';out=Path(__file__).parent;sha='60ed07b10c854c25ec575c5769c5ad539f7a6ba9'
h=lambda b:hashlib.sha256(b).hexdigest();read=lambda p:json.loads((base/p).read_text())
gitfiles={f:h(subprocess.check_output(['git','show',f'{sha}:{f}'],cwd=root)) for f in subprocess.check_output(['git','ls-tree','-r','--name-only',sha,'--','src','tests','scripts','pyproject.toml'],cwd=root,text=True).splitlines()}
def window(rel,exitrel):
 p=base/rel;s=E.parse(p).getroot().find('testsuite');stats={k:int(s.get(k,'0')) for k in ['tests','failures','errors','skipped']};stats['passed']=stats['tests']-sum(stats[k] for k in ['failures','errors','skipped']);stats['xml_seconds']=float(s.get('time'));stats['exit']=json.loads((base/exitrel).read_text())['exit_code'] if exitrel.endswith('.json') else int((base/exitrel).read_text());stats['xml']=rel;return stats
rootwin=window('root/final.xml','root/final.exit');indwin=window('independent/final60-81.xml','independent/final60-81.exit');revwin=window('review/final60-related.xml','review/final60-related.exit')
assert [x['passed'] for x in [rootwin,indwin,revwin]]==[1430,81,302]
assert all(x['failures']==x['errors']==x['skipped']==x['exit']==0 for x in [rootwin,indwin,revwin])
b=read('independent/final60-81-source-before.json');a=read('independent/final60-81-source-after.json');rb=read('review/final60-before.json');rr=read('review/final60-run.json')
assert all(x['source_sha']==sha for x in [b,a,rb,rr,read('root/final-window.json')])
assert b['files']==a['source_files']=={k:v for k,v in gitfiles.items() if k.startswith('src/parkweave/')}
assert b['test_files']==a['test_files'] and a['drift_count']==0
assert not rr['source_drift'] and not rr['source_path_deviations']
assert all(rb['files'].get(k)==v for k,v in gitfiles.items())
assert read('root/final-before.json')==read('root/final-after.json')==gitfiles
name='test_old_identity_material_and_result_fields_are_forbidden';pat=re.compile(r'(?<=\[case_id-)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?=\])')
def ids(p):
 d={};normalized=[]
 for t in E.parse(p).iter('testcase'):
  key=t.get('classname'),t.get('name')
  if key[0]=='tests.test_template_candidate' and key[1].startswith(name+'[case_id-'):
   value,n=pat.subn('<runtime-case-id>',key[1]);assert n==1;normalized.append(key);key=key[0],value
  assert key not in d;d[key]='FAIL' if t.find('failure') is not None else 'ERROR' if t.find('error') is not None else 'SKIP' if t.find('skipped') is not None else 'PASS'
 return d,normalized
old=root/'.runtime/template-local-migration-20261014/final.xml';oldpublic=root/'docs/F2/evidence/template-local-migration-20261014/root/final.xml'
assert old.read_bytes()==oldpublic.read_bytes()
orig,oldnorm=ids(old);final,newnorm=ids(base/'root/final.xml');assert len(orig)==1355 and len(final)==1430 and not(orig.keys()-final.keys());assert all(final[k]=='PASS' for k in orig);assert len(final.keys()-orig.keys())==75
assert gitfiles['tests/test_template_candidate.py']=='64b56c0c2fdbfc3b9fb5fb4fd14ccb656d6bd955d433fc2630acfb8a5f4f4e83'
for p,expected in read('root/original-spec-preservation.json').items():assert h((root/p).read_bytes())==expected
impl=window('impl/window3-backend-precise-audit.xml','impl/window3-backend-precise-audit-exit.json');assert impl['tests']==86 and impl['failures']==3 and impl['passed']==83 and impl['exit']==1
failures=[]
for t in E.parse(base/'impl/window3-backend-precise-audit.xml').iter('testcase'):
 f=t.find('failure')
 if f is not None:
  assert "'recorded_at'" in f.get('message') and "Extra items in the left set" in f.get('message')
  failures.append({'case':t.get('name'),'actual_failure_message':f.get('message'),'classification':'Private oracle expected audit row keys omit legitimate recorded_at column. Original FAIL retained; only existing XML read. No denied diagnostic/test-line command retried.'})
nonzero=[]
for p in base.rglob('*.exit'):
 code=int(p.read_text())
 if code:nonzero.append({'export':str(p.relative_to(base)),'actual_exit':code})
report={'status':'PASS','source_sha':sha,'final_windows':{'root':rootwin,'independent':indwin,'review':revwin},'root_manifest':{'files':len(gitfiles),'before_after_git_exact':True},'independent_manifest':{'source_files':len(b['files']),'test_files':len(b['test_files']),'before_after_exact':True,'git_package_exact':True,'loaded_path_scope':'Private explicit PYTHONPATH; post-run module probe as qualified in original'},'review_manifest':{'tracked_files':len(gitfiles),'before_git_exact':True,'original_run_source_drift':rr['source_drift'],'original_run_path_deviations':rr['source_path_deviations']},'scope_preservation':{'baseline_cases':len(orig),'final_cases':len(final),'missing':[],'old_nonpass':[],'new_cases':75,'normalization':'Only one original case_id UUID param under the unchanged exact source hash','old_normalized':oldnorm,'new_normalized':newnorm,'baseline_raw_archive_bytes_exact':True},'original_spec_hashes_preserved':read('root/original-spec-preservation.json'),'impl_private_86_window':{**impl,'failures':failures,'promoted_to_pass':False,'inspection':'Only existing XML/exit, no test-line diagnostics or test rerun'},'nonzero_exit_windows':nonzero,'historical_interrupt':{'sourceb8_partial':window('root/sourceb8-final.xml','root/sourceb8-final.exit'),'classification':'Superseded interrupted run; 82 prior passes are not full acceptance'},'refusals_preserved':['root/sourceb8-process-cwd-denial.log','root/impl-exec-transport-disconnection.txt'],'raw_export_source_mutation':False}
(out/'supplement.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':report['status'],'root':rootwin,'independent':indwin,'review':revwin,'impl86':{k:v for k,v in impl.items() if k!='xml'}}))
