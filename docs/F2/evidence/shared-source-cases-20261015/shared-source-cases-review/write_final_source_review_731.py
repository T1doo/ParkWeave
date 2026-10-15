from pathlib import Path
import collections,datetime,hashlib,json,subprocess,xml.etree.ElementTree as ET
R=Path('/workspace/ParkWeave');D=R/'.runtime/shared-source-cases-review'
OLD='bc4f384fa32817ddf3b332f898d59b5b994bfe2f';NEW='731529bc409041f255742e11756ebc4084bb9319';J='tests/shared_source_cases_real_html.js'
def git(*a):return subprocess.check_output(['git',*a],cwd=R)
def read(p):return json.loads((R/p).read_text())
def sha(b):return hashlib.sha256(b).hexdigest()
def tree(s):
 o={}
 for row in git('ls-tree','-rz','--full-tree',s).split(b'\0'):
  if not row:continue
  meta,name=row.split(b'\t',1);mode,kind,h=meta.split();assert kind==b'blob'
  o[name.decode()]=(mode.decode(),h.decode())
 return o
assert git('rev-parse','HEAD').decode().strip()==NEW
assert not git('status','--porcelain','--untracked-files=no')
subprocess.run(['git','merge-base','--is-ancestor',OLD,NEW],cwd=R,check=True)
subprocess.run(['git','diff','--check',OLD,NEW],cwd=R,check=True)
oldtree=tree(OLD);newtree=tree(NEW);assert oldtree.keys()==newtree.keys()
diff=[p for p in oldtree if oldtree[p]!=newtree[p]];assert diff==[J],diff
rawdiff=git('diff',OLD,NEW,'--',J).decode();(D/'final-source-731529bc.patch').write_text(rawdiff)
files={};sizes={};blob_mismatches=[]
for p,(mode,blob) in newtree.items():
 q=R/p;b=q.read_bytes() if mode!='120000' else q.readlink().as_posix().encode()
 files[p]=sha(b);sizes[p]=len(b)
 if hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()!=blob:blob_mismatches.append(p)
assert not blob_mismatches,blob_mismatches
freeze=read('.runtime/shared-source-cases/freeze.json');final=read('.runtime/shared-source-cases/final-freeze.json')
a,b=freeze['hashes'],final['hashes'];assert len(a)==len(b)==595 and a.keys()==b.keys()
assert [p for p in a if a[p]!=b[p]]==[J]
assert all(files[p]==h for p,h in b.items())
assert files[J]=='38a0df30a7d598d42f06ea27220ebd095efb58046e1acaa3d124f19bdfbcfdd0'
assert sha(git('show',OLD+':'+J))=='58984c3236d4eb3e25d5e100bfc6d3a8ea539ca142596ea53716c02777f20eea'
oldsnap=read('.runtime/shared-source-cases-review/extra-bc4f384f-alltracked-before.json')['files']
assert [p for p in files if files[p]!=oldsnap[p]['sha256']]==[J]
full_manifest={'head':NEW,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'count':len(files),'bytes':sum(sizes.values()),'frozen_git_blob_mismatches':blob_mismatches,'files':files}
(D/'final-source-731529bc-alltracked.json').write_text(json.dumps(full_manifest,sort_keys=True,indent=2)+'\n')
(D/'final-source-731529bc-source595.json').write_text(json.dumps({'source_sha':NEW,'count':595,'hashes':{p:files[p] for p in b}},sort_keys=True,indent=2)+'\n')
def key(node):
 prefix,bracket,tail=node.partition('[');parts=prefix.split('::');return (parts[0][:-3].replace('/','.')+''.join('.'+x for x in parts[1:-1]),parts[-1]+(bracket+tail if bracket else ''))
def window(prefix,kind):
 d=read(prefix+'.json' if kind=='root' else prefix+'-result.json')
 nodes=read(prefix+'-collection.json');nodes=nodes if isinstance(nodes,list) else nodes['items']
 expected=[key(n if isinstance(n,str) else n['nodeid']) for n in nodes]
 ts=list(ET.parse(R/(prefix+'.xml')).iter('testcase'));actual=[(t.get('classname'),t.get('name')) for t in ts]
 assert collections.Counter(expected)==collections.Counter(actual) and len(actual)==len(set(actual))
 counts={'PASS':0,'FAIL':0,'ERROR':0,'SKIP':0}
 for t in ts:
  k='ERROR' if t.find('error') is not None else 'FAIL' if t.find('failure') is not None else 'SKIP' if t.find('skipped') is not None else 'PASS';counts[k]+=1
 assert d['exit_code']==0 and counts['PASS']==len(actual) and d['source_sha']==OLD
 if kind=='root':
  before=read(prefix+'-before.json');after=read(prefix+'-after.json');assert before==after==a
 else:
  before=read(prefix+'-source-before.json');after=read(prefix+'-source-after.json');assert before==after and len(before)==600 and {p:before[p] for p in a}==a
 return {'execution_sha':OLD,'result_path':prefix+('.json' if kind=='root' else '-result.json'),'complete_modules':d['modules'],'counts_independently_recounted':counts,'collection_junit_exact':True,'unique_testcases':len(actual),'runner_seconds':d['elapsed_seconds'],'source595_before_after_equal_frozen':True,'final_source_unchanged_for_loaded_product_and_test_dependencies':True,'not_reexecuted_at_final_sha':True}
w=[window('.runtime/shared-source-cases/root-1-v1','root'),window('.runtime/shared-source-cases/root-2-v1','root'),window('.runtime/shared-source-cases-review/extra-bc4f384f','review')]
mods=[p for z in w for p in z['complete_modules']];assert len(mods)==len(set(mods))==60
consumers=[]
for p in b:
 if p!=J and J.encode() in (R/p).read_bytes():consumers.append(p)
assert consumers==['tests/test_shared_source_cases_independent.py'] and consumers[0] not in mods
# No imports/references route from the old complete windows to the unique new helper caller.
for p in [*mods,'tests/conftest.py']:
 if not (R/p).exists():continue
 data=(R/p).read_text()
 assert 'shared_source_cases_real_html' not in data and 'test_shared_source_cases_independent' not in data,p
core=['src/parkweave/typed_source_impact.py','src/parkweave/source_change_adoption.py','src/parkweave/registered_dependencies.py','src/parkweave/service_case_steps.py']
assert all(git('show',OLD+':'+p)==(R/p).read_bytes() for p in core)
assert all(oldtree[p]==newtree[p] for p in oldtree if p.startswith(('src/','scripts/')) or p=='pyproject.toml' or p.endswith('.py'))
prepared=read('.runtime/shared-source-cases-independent/prepared/overflow-second-page-result.json')
assert prepared['runtime_driver_sha256']==files[J] and prepared['anchor_rank']==33 and prepared['original_worklist_pages']==2 and prepared['business_writes_during_html']==0
schema=read('.runtime/shared-source-cases-review/schema-bc4f384f-result.json');assert schema['exit_code']==0 and schema['counts']['PASS']==3
previous=read('.runtime/shared-source-cases-review/review-bc4f384f.json')
report={'status':'FINAL_SOURCE_STATIC_PASS_OLD60_WINDOW_CONTINUITY_PROVED_FINAL4_AND_ARCHIVE_PENDING','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'final_source_sha':NEW,'business_execution_sha':OLD,'new_blockers':[],'tracked_worktree_clean':True,'alltracked_paths':len(files),'alltracked_bytes':sum(sizes.values()),'alltracked_matches_final_git_blobs':True,'tracked_source_paths':595,'source_paths_unchanged_from_old':594,'only_changed_path':J,'only_changed_path_sha256':files[J],'git_numstat':git('diff','--numstat',OLD,NEW).decode().strip(),'old_windows':w,'old60_unique_passes':sum(z['counts_independently_recounted']['PASS'] for z in w),'unique_direct_helper_consumers':consumers,'old60_direct_or_import_references_to_changed_helper_or_its_caller':[],'diagnostics_dependency':'The allowlist check reads test_*.py AST function definitions; no JavaScript bytes are consumed by that assertion. All Python and diagnostics/allowlist bytes are unchanged.','patch_assessment':'Bounded traversal through the original worklist next handler before the same anchor lookup. Existing first-action order, graph click, binding/impact assertions and GET-only checks remain. No UUID mutation, business write or forged graph.','prepared_runtime_probe':{'scope':prepared['scope'],'execution_sha':prepared['source_sha'],'anchor_rank':33,'original_worklist_pages':2,'business_writes_during_html':0,'not_substituted_for_final_formal_window':True},'schema_negative_probes':{'execution_sha':OLD,'pass':3,'separate_from_formal_modules':True,'product_dependencies_unchanged_to_final':True},'inherited_static_conclusions':previous['static_conclusions'],'admin_corruption_boundary':{'classification':'UNSUPPORTED_TRUSTED_ADMIN_STRUCTURAL_CORRUPTION_FAIL_CLOSED','observation':'A trusted direct SQL edit retaining valid plan id/revision while deleting steps yields original-reader generic 500; no response items/history writes. Supported public commands cannot produce that structure.','claim_limit':'Malformed plan -> per-Case UNKNOWN applies to invalid headers or handled original reader validation conflicts; it does not claim arbitrary trusted administrator corruption repair.','evidence':'.runtime/shared-source-cases-review/admin-corruption-boundary-assessment.json','delivery_blocker':False},'pending':['Final four complete modules at final SHA, including sole helper consumer; old 122PASS/1FAIL retained as historical harness failure.','Explicit parent archive-ready signal, independent raw/export reconstruction and final coverage audit.'],'scope':previous['limitations'],'reviewer_nonproduct_receipt':{'path':'.runtime/shared-source-cases-review/final-source-review-731529bc-first-setup-error.log','classification':'Reviewer snapshot-shape assertion stop: alltracked values are records with sha256, not plain hashes; no product execution or product failure.','original_script':'.runtime/shared-source-cases-review/write_final_source_review_731.pre-manifest-shape-fix.py'},'writes':'New runtime reviewer reports only; no product, tests, scripts, Git or old evidence modified.'}
assert report['old60_unique_passes']==1951
(D/'final-source-review-731529bc.json').write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
md=f'''# Final source review\n\nFinal static source review: PASS for `{NEW}`. The only change from `{OLD}` is the bounded original-worklist pagination fix in `{J}` (7 insertions, 1 deletion; SHA256 `{files[J]}`). All 595 tracked source paths match final Git blobs; 594 match the business freeze. All source, scripts, pyproject and Python test bytes are identical. Full tracked snapshot: {len(files)} paths, {sum(sizes.values())} bytes, zero drift.\n\nThe old 52+8 complete modules ran at **{OLD}**, with independently recounted results **900 + 789 + 262 = 1951 PASS** and exact, unique same-window collection/JUnit identities. They were **not rerun at the final SHA**. Their source manifests match the old 595-path freeze. The sole direct JS consumer is `tests/test_shared_source_cases_independent.py`, outside those 60 modules; no old-window module or conftest references that caller/helper. The diagnostic list assertion parses Python AST only. This byte/dependency proof preserves those results for the final source without relabeling the execution SHA. Runner times: 958.755728, 1088.298456 and 197.708197 seconds.\n\nThree negative graph-schema runtime probes remain a separate **3 PASS** window executed at the old SHA; the product dependencies are unchanged. The prepared second-page runtime check used the exact final JS bytes and an existing rank-33 anchor across two original pages without Case-ID edits or business writes; it does not replace the final four-module run.\n\nNo new supported-flow blocker found. Original historical compiler, ADOPT/VERIFY/UNLOCK, six-goal/P1–P5 and unaffected lock/history cores are unchanged. Scope remains two finite current-owner source identities with bounded conservative UNKNOWN handling, not an arbitrary shared-source graph. A trusted direct-SQL damaged plan body with a valid header can still fail closed with generic 500; invalid-header UNKNOWN coverage must not be described as arbitrary structural corruption repair. See the existing admin-corruption addendum.\n\n**Pending:** the final four complete modules at `{NEW}` and independent archive reconstruction after the parent's explicit archive-ready signal. The historical 122 PASS / 1 FAIL harness window and setup receipts remain preserved. Linux synthetic HTTP/ASGI/owned PostgreSQL scope only; Windows, actual browser, formal AT, real model, production and remote CI remain unexecuted.\n'''
(D/'final-source-review-731529bc.md').write_text(md)
assert git('rev-parse','HEAD').decode().strip()==NEW and not git('status','--porcelain','--untracked-files=no')
print(json.dumps({k:report[k] for k in ['status','final_source_sha','alltracked_paths','alltracked_bytes','tracked_source_paths','source_paths_unchanged_from_old','old60_unique_passes','unique_direct_helper_consumers']}))
