"""Static Git/AST/hash packaging only; no verifier, runner or product imports/tests."""
import ast,copy,hashlib,json,re,subprocess
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path('/workspace/ParkWeave');OUT=ROOT/'.runtime/fixed-acceptance-closeout-20261018/independent'
BASE='e08f2f60f87ff54bdbb3a2e9f9bdd9b60dc46e03';FINAL='7f02fe3f463fb402eb497fb4342d93037b24cc18';CAP=4*1024*1024
CONTRACT='docs/F1/AcceptanceSourceBatchContract-20261018.md';SOURCE='scripts/windows_ci/source_bytes.py'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def blob(r,p):return git('show',r+':'+p)
def sha(b):return hashlib.sha256(b).hexdigest()
def put(n,obj):
 p=OUT/n
 if p.exists():raise RuntimeError('Never overwrite frozen evidence '+n)
 p.write_bytes(obj if isinstance(obj,bytes) else (json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode())
def dump(n):return ast.dump(n,include_attributes=False)
def function(t,name):return next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name==name)
freeze=json.loads((OUT/'freeze-manifest.json').read_bytes());assert all(sha((OUT/n).read_bytes())==h for n,h in freeze['files'].items())
oracle=json.loads((OUT/'literal-oracle-plan.json').read_bytes());assert len(oracle['rows'])==10
base_map=json.loads((OUT/'baseline-inputs.json').read_bytes());assert base_map['revision']==BASE
changes=git('diff','--name-status',BASE,FINAL).decode().splitlines();assert set(l.split('\t')[-1] for l in changes)=={SOURCE,'tests/test_source_bytes.py',CONTRACT}
put('baseline-to-final.diff',git('diff','--no-ext-diff','--unified=20',BASE,FINAL))
put('implementation-contract.md',blob(FINAL,CONTRACT))
paths=sorted(set(base_map['files'])|{CONTRACT});finalmap={}
for p in paths:
 raw=blob(FINAL,p);finalmap[p]=dict(bytes=len(raw),sha256=sha(raw),git_blob=git('rev-parse',FINAL+':'+p).decode().strip())
put('final-inputs.json',dict(kind='STATIC_EXPLICIT_COMMITTED_INPUTS',revision=FINAL,count=len(paths),files=finalmap,product_imports=0,execution_maps_not_claimed=True))
assert len(paths)==30
for p in base_map['files']:
 if p not in (SOURCE,'tests/test_source_bytes.py'):assert finalmap[p]['sha256']==base_map['files'][p]['sha256']

oldtree=ast.parse(blob(BASE,SOURCE));newtree=ast.parse(blob(FINAL,SOURCE));old=function(oldtree,'verify_head_test_sources');new=function(newtree,'verify_head_test_sources')
for name in ['_git','verify_head']:assert dump(function(oldtree,name))==dump(function(newtree,name))
normal=copy.deepcopy(newtree);i=next(i for i,n in enumerate(normal.body) if isinstance(n,ast.FunctionDef) and n.name=='verify_head_test_sources');normal.body[i]=copy.deepcopy(old)
assert dump(normal)==dump(oldtree)
oldcap=next(i for i,n in enumerate(old.body) if isinstance(n,ast.If) and 'sum(sizes)' in ast.unparse(n.test))
newcap=next(i for i,n in enumerate(new.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='limit' for t in n.targets))
assert [dump(n) for n in old.body[:oldcap]]==[dump(n) for n in new.body[:newcap]]
oldfor=next(n for n in old.body if isinstance(n,ast.For) and isinstance(n.target,ast.Tuple) and [x.id for x in n.target.elts]==['path','header','size'])
outer=next(n for n in new.body if isinstance(n,ast.While));inner=next(n for n in outer.body if isinstance(n,ast.While));newfor=next(n for n in outer.body if isinstance(n,ast.For))
assert [dump(n) for n in oldfor.body]==[dump(n) for n in newfor.body]
assert dump(oldfor.target)==dump(newfor.target)
assert isinstance(newfor.iter,ast.Call) and isinstance(newfor.iter.func,ast.Name) and newfor.iter.func.id=='zip' and len(newfor.iter.args)==3
for arg,name in zip(newfor.iter.args,['paths','checks','sizes']):
 assert isinstance(arg,ast.Subscript) and arg.value.id==name and isinstance(arg.slice,ast.Slice) and arg.slice.lower.id=='batch_start' and arg.slice.upper.id=='batch_end'
assert ast.unparse(outer.test)=='batch_start < len(paths)'
assert ast.unparse(inner.test)=='batch_end < len(paths) and batch_bytes + sizes[batch_end] <= limit'
assert [ast.unparse(n) for n in inner.body]==['batch_bytes += sizes[batch_end]','batch_end += 1']
assert ast.unparse(outer.body[-1])=='batch_start = batch_end'
assert dump(old.body[-1])==dump(outer.body[-2])
assert ast.unparse(new.body[newcap])=='limit = 4 * 1024 * 1024'
assert ast.unparse(new.body[newcap+1].test)=='any((size > limit for size in sizes))'
assert isinstance(new.body[newcap+1].body[0],ast.Raise)
assert ast.unparse(new.body[newcap+1].body[0])=="raise SourceBytesRefused('GIT_BLOB_UNAVAILABLE')"
# No early return/partial-success branch was introduced.
assert not any(isinstance(n,ast.Return) for n in ast.walk(new))
new_source=blob(FINAL,SOURCE).decode();assert 'timeout=5' in new_source

allpaths=git('ls-tree','-r','--name-only',FINAL,'tests').decode().splitlines();testpaths=sorted(p for p in allpaths if re.fullmatch(r'tests/test_[A-Za-z0-9_]+\.py',p))
checks=subprocess.check_output(['git','cat-file','--batch-check'],input=('\n'.join(FINAL+':'+p for p in testpaths)+'\n').encode(),cwd=ROOT).splitlines()
metadata=[]
for p,h in zip(testpaths,checks):
 m=re.fullmatch(rb'([0-9a-f]{40}) blob ([0-9]{1,10})',h);assert m
 metadata.append(dict(path=p,git_blob=m[1].decode(),bytes=int(m[2])))
assert len(metadata)==381 and max(x['bytes'] for x in metadata)<=CAP
put('final-test-blob-metadata.json',dict(kind='STATIC_GIT_METADATA_NOT_VERIFIER_EXECUTION',revision=FINAL,count=len(metadata),total_blob_bytes=sum(x['bytes'] for x in metadata),max_file_bytes=max(x['bytes'] for x in metadata),files=metadata,note='Committed metadata only; no working-tree verifier, runner or dynamic test was called.'))

# Original business source tree and caller semantics must stay exactly unchanged.
src_base=git('rev-parse',BASE+':src').decode().strip();src_final=git('rev-parse',FINAL+':src').decode().strip();assert src_base==src_final
caller_paths=['scripts/run_acceptance.py','scripts/windows_ci/regression_shards.py','tests/test_acceptance_runner.py','tests/test_foundation.py','docs/验收规格.json','docs/F1/ATBindings.json']
assert all(blob(BASE,p)==blob(FINAL,p) for p in caller_paths)
oldtests=ast.parse(blob(BASE,'tests/test_source_bytes.py'));newtests=ast.parse(blob(FINAL,'tests/test_source_bytes.py'))
oldnodes={n.name:dump(n) for n in oldtests.body if isinstance(n,ast.FunctionDef)};newnodes={n.name:dump(n) for n in newtests.body if isinstance(n,ast.FunctionDef)}
assert all(newnodes[n]==v for n,v in oldnodes.items())
new_names=sorted(set(newnodes)-set(oldnodes));assert len(new_names)==6 # five tests plus local fixture builder
proof=dict(kind='STATIC_AST_AND_BYTE_PROTECTION',baseline=BASE,final=FINAL,scope_changes=changes,source_module_only_one_function_changed=True,_git_AST_identical=True,verify_head_AST_identical=True,all_prelude_HEAD_path_hash_batchcheck_checks_AST_identical=True,per_file_parse_compare_body_AST_identical=True,per_batch_header_size_LF_tail_checks_AST_identical=True,global_oversize_reject_before_body=True,parallel_slices_same_batch_bounds=True,sorted_greedy_condition_and_progress_verified=True,no_partial_return=True,caller_and_spec_bindings_unchanged={p:sha(blob(FINAL,p)) for p in caller_paths},all_src_tree_identical=True,src_tree=src_final,all_original_test_functions_AST_identical=True,new_test_source_function_names=new_names,resource_envelope=dict(per_file_blob_body_cap=CAP,per_batch_blob_body_cap=CAP,max_paths=1024,max_nonempty_body_batches=1024,max_cumulative_blob_bodies_bytes=1024*CAP,Git_framing_overhead_excluded_from_blob_body_cap=True,per_Git_command_timeout_seconds=5,total_function_5second_timeout_claimed=False,no_accumulation_of_all_body_batches_in_collection=True,strict_peak_process_memory_4MiB_claimed=False))
put('static-protection-verification.json',proof)
refs={}
for p in [SOURCE,'scripts/run_acceptance.py','tests/test_source_bytes.py']:
 t=ast.parse(blob(FINAL,p));refs[p]={n.name:dict(line=n.lineno,end_line=n.end_lineno) for n in t.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
put('final-definition-refs.json',refs)

findings=[
 ('SB-01','STATIC_SATISFIED','Original dictionary/path/hash prelude and both runner callers byte/AST identical; all381 test roots remain selected by existing caller.'),
 ('SB-02','STATIC_SATISFIED','Explicit individual size>limit rejects before any body; <=limit inner condition permits exactcap and allocates contiguous batches. No all-body aggregation.'),
 ('SB-03','STATIC_SATISFIED','Every per-file body is exact original AST, including raw SHA and work==blob checks. Same checks apply to every later batch.'),
 ('SB-04','STATIC_SATISFIED','Original batch-check count/header regex/type/hash/size parsing remains AST identical; zipped slices use the same start/end; no truncating metadata branch.'),
 ('SB-05','STATIC_SATISFIED','Original per-file header/length/LF parser and final cursor!=len(raw) rejection moved verbatim inside each batch. Later tails cannot be ignored.'),
 ('SB-06','STATIC_SATISFIED','Original HEAD/path/hash/untracked/symlink/root containment/work-size/read failure code and fixed reasons preserved.'),
 ('SB-07','STATIC_SATISFIED','_git and verify_head AST/behavior unchanged; timeout=5 and sanitized read-only environment remain on every body command. No retry or cumulative5s claim.'),
 ('SB-08','STATIC_SATISFIED','Sorted contiguous slices advance end by1 and start=end; prior individual oversize gate guarantees progress. Contract discloses cumulative body/call growth and framing distinction; no process-memory4MiB claim.'),
 ('SB-09','STATIC_SATISFIED_NOT_EXECUTED','run_acceptance.py, original AT13 selector, fixed spec and bindings are byte unchanged. No whole PASS logic modification. Parent AT13 operation is separate from this review.'),
 ('SB-10','STATIC_SATISFIED','Historical AT21/32 rejection report source bytes and sourceblind freeze unchanged. No verifier/runner/pytest or old platform-window replay performed by reviewer.')]
put('oracle-static-findings.json',dict(final_sha=FINAL,oracle_sha256=sha((OUT/'literal-oracle-plan.json').read_bytes()),rows=[dict(id=i,status=s,reason=r) for i,s,r in findings],open_P1=[],open_P2=[],independent_dynamic=0))
commit=git('show','-s','--format=%H%n%T%n%P%n%s',FINAL).decode().splitlines()
put('static-git-evidence.json',dict(baseline=BASE,final_sha=FINAL,final_tree=commit[1],parent=commit[2],subject=commit[3],changes=changes,source_blind_freeze_unchanged=True,explicit_Git_SHA_only=True,working_tree_implementation_reads=0,product_imports=0))
report=dict(kind='INDEPENDENT_STATIC_ONLY_SOURCE_BATCH_FINAL_REVIEW',baseline=BASE,final_sha=FINAL,final_tree=commit[1],created_at_utc=datetime.now(timezone.utc).isoformat(),conclusion='LIMITED_STATIC_ACCEPTANCE_NO_OPEN_P1_P2',oracle_rows=10,open_P1=[],open_P2=[],engineering_repair_only=True,new_business_feature_claimed=False,static_proofs=['Only existing source verifier, its tests and bounded batch contract change.','Original _git/HEAD/path/hash/metadata and per-file compare/framing logic preserved; original tail validation is inside every batch.','Original full381 path scope, source tree, run_acceptance callers, all original tests/spec/bindings preserved.','Singlefile and eachbatch cap4MiB/path<=1024/perGit5s; cumulativeI/O/bodycommands increase is deliberate and disclosed.'],final_metadata=dict(root_test_blobs=len(metadata),blob_bytes=sum(x['bytes'] for x in metadata),max_file_bytes=max(x['bytes'] for x in metadata),kind='COMMITTED_METADATA_NOT_RUNTIME_VERIFICATION'),independent_execution=dict(product_imports=0,dynamic_tests=0,verifier_calls=0,runner_calls=0,DB_HTTP_lock_browser_model_Windows=0,old_window_retries=0,nodeIDs=[],collection=None,phases=None,JUnit=None,pytest_seconds=None,module_origins=None,shared_mirror_execution_maps=None),parent_execution=dict(status='SEPARATE_NOT_INDEPENDENTLY_EXECUTED_OR_CLAIMED',planned_final_pure_nodes=25,planned_new_AT13_runner_selector='tests/test_foundation.py::test_api_worker_process_restart_and_business_separation',old_AT21_AT32_not_selected=True),limitations=['Static approval does not claim root dynamic test outcomes, current working-tree source verification, AT13 completion or whole acceptance.','Per-batch content cap excludes Git framing; total function bytes/commandcount/worst-case elapsed grow, and strict4MiB process memory or total5s are not claimed.','Old AT21/32 SOURCE_BINDING/GIT_BLOB_UNAVAILABLE0tests reports stay historical; finite already-covered AT21/32 instances remain separate.','AT29 legal-pause business function remains absent pending minimal local authority/reason/event semantics; independent approver/signature/head are later design choices, not universal original hard prerequisites.','AT33 B/C second-scope coverage remains unconfirmed; no algorithm defect was established by the scoped static review. Reviewed SYNTHETIC sources can be valid technical fixtures.','Old platform/HTTP UNKNOWN not retried or closed. Windows/LIVE/C0/real business/formal totalAT/project completion remain separate.'],artifacts=dict(oracle='literal-oracle-plan.json',findings='oracle-static-findings.json',protection='static-protection-verification.json',gap_analysis='remaining-gap-classification.json',final_inputs='final-inputs.json',final_metadata='final-test-blob-metadata.json',diff='baseline-to-final.diff'))
put('independent-final-review.json',report)
core=sorted([*freeze['files'],'freeze-manifest.json','finalize_static_review.py','baseline-to-final.diff','implementation-contract.md','final-inputs.json','final-test-blob-metadata.json','static-protection-verification.json','final-definition-refs.json','oracle-static-findings.json','static-git-evidence.json','independent-final-review.json'])
assert len(core)==len(set(core))
put('raw-public-redaction-map.json',dict(kind='STATIC_IDENTITY_PUBLICATION_MAP',entries=[dict(raw=n,public=n,raw_sha256=sha((OUT/n).read_bytes()),public_sha256=sha((OUT/n).read_bytes()),replacement_count=0,mode='IDENTITY_STATIC_NO_RUNTIME_SESSION_VALUES') for n in core],fixture_tokens_read_or_created=0,total_replacements=0,notes='Canonical static source/hash/oracle reports; raw/public paths intentionally identical. No fixture tokens/credentials/mirror/PGdata selected. Byte-copy, no second redaction.'))
put('raw-evidence-manifest.json',dict(kind='STATIC_CANONICAL_MANIFEST',final_sha=FINAL,files={n:dict(bytes=(OUT/n).stat().st_size,sha256=sha((OUT/n).read_bytes())) for n in core+['raw-public-redaction-map.json']},independent_dynamic=0))
publication=sorted(core+['raw-public-redaction-map.json','raw-evidence-manifest.json']);put('publication-files.json',publication)
print(json.dumps(dict(final=FINAL,oracle_rows=10,open_P1=0,open_P2=0,independent_dynamic=0,canonical_files=len(publication),map_entries=len(core),replacement_count=0,final_test_blob_count=len(metadata),final_test_blob_bytes=sum(x['bytes'] for x in metadata),hashes={n:sha((OUT/n).read_bytes()) for n in ['independent-final-review.json','publication-files.json','raw-public-redaction-map.json','raw-evidence-manifest.json']}),indent=2))
