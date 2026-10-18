"""Static committed Git/AST/hash review only; never import or execute project code."""
import ast,copy,hashlib,json,subprocess
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path('/workspace/ParkWeave');OUT=ROOT/'.runtime/local-demo-case-step-chain-20261018/independent'
BASE='f16d9cf7895e31ad7aab7594494c90bb1e8fa7fb';INITIAL='3b559f9340f2b6b958ded600f2a161269d67cf5c';FINAL='3f5fd029f335d132d9baecb79165b86e2159761a'
CONTRACT='docs/F2/LocalDemoCaseStepChainContract-20261018.md'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def blob(rev,path):return git('show',rev+':'+path)
def sha(b):return hashlib.sha256(b).hexdigest()
def put(name,obj):
 p=OUT/name
 if p.exists():raise RuntimeError('Never overwrite stable evidence '+name)
 p.write_bytes(obj if isinstance(obj,bytes) else (json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode())
def dump(n):return ast.dump(n,include_attributes=False)
def node(body,name):return next(n for n in body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name)
def definitions(t):
 result={}
 for n in t.body:
  if isinstance(n,(ast.FunctionDef,ast.ClassDef)):
   result[n.name]=n
   if isinstance(n,ast.ClassDef):
    for m in n.body:
     if isinstance(m,ast.FunctionDef):result[n.name+'.'+m.name]=m
 return result

def inputs(rev,paths):
 values={};data=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(rev+':'+p for p in paths)+'\n').encode(),cwd=ROOT);at=0
 for p in paths:
  end=data.index(b'\n',at);h=data[at:end].decode().split();size=int(h[2]);at=end+1;raw=data[at:at+size];at+=size+1
  values[p]=dict(git_blob=h[0],bytes=len(raw),sha256=sha(raw))
 assert at==len(data)
 return dict(kind='STATIC_COMMITTED_GIT_BLOB_INPUTS_NO_EXECUTION',revision=rev,count=len(values),files=values)
freeze=json.loads((OUT/'freeze-manifest.json').read_bytes())
assert all(sha((OUT/p).read_bytes())==h for p,h in freeze['files'].items())
original=json.loads((OUT/'baseline-inputs.json').read_bytes());assert original['revision']==BASE
oracle=json.loads((OUT/'literal-oracle-plan.json').read_bytes());assert len(oracle['rows'])==10
changes=git('diff','--name-status',BASE,FINAL).decode().splitlines();changed={l.split('\t')[-1] for l in changes}
expected={CONTRACT,'docs/F2/LocalSyntheticDemo-20261017.md','scripts/ordinary_synthetic_demo.py','src/parkweave/api.py','src/parkweave/case_step_assignments.py','src/parkweave/local_synthetic_demo.py','tests/local_demo_case_step_chain_html.js','tests/test_local_demo_case_step_chain.py','tests/test_ordinary_synthetic_demo.py'}
assert changed==expected
paths=sorted(set(original['files'])|changed);assert len(paths)==815
maps={}
for rev,label in [(INITIAL,'initial-3b559-inputs.json'),(FINAL,'final-3f5fd029-inputs.json')]:
 maps[rev]=inputs(rev,paths);put(label,maps[rev])
assert blob(INITIAL,CONTRACT)==blob(FINAL,CONTRACT)
put('implementation-contract.md',blob(FINAL,CONTRACT))
put('baseline-to-initial.diff',git('diff','--no-ext-diff','--unified=8',BASE,INITIAL))
put('initial-to-final-fix.diff',git('diff','--no-ext-diff','--unified=12',INITIAL,FINAL))
put('baseline-to-final.diff',git('diff','--no-ext-diff','--unified=8',BASE,FINAL))
fix_paths=git('diff','--name-only',INITIAL,FINAL).decode().splitlines()
assert fix_paths==['src/parkweave/local_synthetic_demo.py','tests/test_local_demo_case_step_chain.py']

# Compare syntax trees only. No project imports, evaluation, tests or fixtures.
allowed_methods={
 'src/parkweave/case_step_assignments.py':['_CaseStepTransactions._unmixed','OrdinaryCaseStepAssignments.__init__','OrdinaryCaseStepAssignments._connection','OrdinaryCaseStepAssignments._context','from_environment'],
 'src/parkweave/local_synthetic_demo.py':['LocalDemoCatalog.connection'],
 'scripts/ordinary_synthetic_demo.py':['serve','main'],
}
proof={};source_refs={}
for path,allowed in allowed_methods.items():
 oldtree=ast.parse(blob(BASE,path));newtree=ast.parse(blob(FINAL,path));olddefs=definitions(oldtree);newdefs=definitions(newtree);normalized=copy.deepcopy(newtree)
 oldmap={k:dump(n) for k,n in olddefs.items()};newmap={k:dump(n) for k,n in newdefs.items()}
 changed_defs=[k for k in oldmap if newmap.get(k)!=oldmap[k]]
 non_container=[k for k in changed_defs if not isinstance(olddefs[k],ast.ClassDef)]
 assert set(non_container)==set(allowed)
 new_names=set(newdefs)-set(olddefs)
 expected_new={'local_demo_pair'} if path.endswith('case_step_assignments.py') else {'existing_local_demo_config'} if path.startswith('scripts/') else set()
 assert new_names==expected_new
 # Restore only the explicit admission/configuration additions to prove original remainder.
 for key in allowed:
  if '.' in key:
   cls,name=key.split('.');parent=node(normalized.body,cls)
   idx=next(i for i,n in enumerate(parent.body) if isinstance(n,ast.FunctionDef) and n.name==name)
   parent.body[idx]=copy.deepcopy(olddefs[key])
  else:
   idx=next(i for i,n in enumerate(normalized.body) if isinstance(n,ast.FunctionDef) and n.name==key)
   normalized.body[idx]=copy.deepcopy(olddefs[key])
 normalized.body=[n for n in normalized.body if not (isinstance(n,ast.FunctionDef) and n.name in expected_new)]
 if path.endswith('case_step_assignments.py'):
  normalized.body=[n for n in normalized.body if not (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='LOCAL_DEMO_MODE' for t in n.targets))]
 if path.startswith('scripts/'):
  normalized.body=[n for n in normalized.body if not (isinstance(n,ast.Import) and len(n.names)==1 and n.names[0].name=='stat')]
 assert dump(normalized)==dump(oldtree)
 proof[path]=dict(allowed_changed_definitions=allowed,new_definitions=sorted(new_names),all_other_module_AST_identical=True,unchanged_existing_definitions=[k for k in oldmap if oldmap[k]==newmap.get(k)])
 source_refs[path]={k:dict(line=n.lineno,end_line=n.end_lineno) for k,n in newdefs.items()}

api='src/parkweave/api.py';oldtree=ast.parse(blob(BASE,api));newtree=ast.parse(blob(FINAL,api));normal=copy.deepcopy(newtree)
oldcreate=node(oldtree.body,'create_app');newcreate=node(newtree.body,'create_app')
assert len(oldcreate.body)==len(newcreate.body)
assert all(dump(a)==dump(b) for a,b in zip(oldcreate.body[1:],newcreate.body[1:]))
node(normal.body,'create_app').body[0]=copy.deepcopy(oldcreate.body[0])
idx=next(i for i,n in enumerate(normal.body) if isinstance(n,ast.FunctionDef) and n.name=='configured_app');normal.body[idx]=copy.deepcopy(node(oldtree.body,'configured_app'))
assert dump(normal)==dump(oldtree)
oldroutes={n.name:dump(n) for n in oldcreate.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))};newroutes={n.name:dump(n) for n in newcreate.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))};assert oldroutes==newroutes
proof[api]=dict(allowed_changed_definitions=['create_app first admission block','configured_app dependency reuse'],all_other_module_AST_identical=True,all_original_inner_functions_unchanged=True,original_inner_function_count=len(oldroutes))

# Inspect the exact self-identity fix as syntax, not as a runtime test.
local='src/parkweave/local_synthetic_demo.py';oldconn=definitions(ast.parse(blob(INITIAL,local)))['LocalDemoCatalog.connection'];newconn=definitions(ast.parse(blob(FINAL,local)))['LocalDemoCatalog.connection']
initial_condition=oldconn.body[3].test;fixed_condition=newconn.body[3].test
assert isinstance(fixed_condition,ast.BoolOp) and isinstance(fixed_condition.op,ast.And)
assert any(isinstance(n,ast.Compare) and any(isinstance(op,ast.IsNot) for op in n.ops) and isinstance(n.comparators[0],ast.Name) and n.comparators[0].id=='self' and ast.unparse(n.left)=='service.local_synthetic_demo.catalog' for n in ast.walk(fixed_condition))
restored=copy.deepcopy(newconn);restored.body[3].test=copy.deepcopy(initial_condition);assert dump(restored)==dump(oldconn)
proof['catalog_self_identity_fix']=dict(initial_sha=INITIAL,final_sha=FINAL,condition_adds_exact_self_identity=True,remaining_connection_AST_unchanged_from_initial=True,initial_problem='local_demo_pair proved serviceA/demoA/catalogA but did not prove self is catalogA; another exact same-Store catalogB could enter using serviceA managed connection.',final_rejection='service.local_synthetic_demo.catalog is not self rejects catalogB before transaction selection.',authority_claim='No dynamic exploit or unauthorized write was performed or inferred.')

finalfiles=maps[FINAL]['files'];originalfiles=original['files']
changed_existing=[p for p in sorted(originalfiles) if originalfiles[p]['sha256']!=finalfiles[p]['sha256']]
code_names=git('ls-tree','-r','--name-only',BASE,'src','tests','scripts','pyproject.toml','README.md').decode().splitlines();assert len(code_names)==804
code_changed=[p for p in code_names if originalfiles[p]['sha256']!=finalfiles[p]['sha256']];assert len(code_changed)==5
src=[p for p in code_names if p.startswith('src/')];src_changed=[p for p in src if originalfiles[p]['sha256']!=finalfiles[p]['sha256']]
assert set(src_changed)=={'src/parkweave/api.py','src/parkweave/case_step_assignments.py','src/parkweave/local_synthetic_demo.py'}
protected=[p for p in code_names if p not in code_changed]
assert all(originalfiles[p]['sha256']==finalfiles[p]['sha256'] for p in protected)
protected_specific=['src/parkweave/local_demo_selections.py','src/parkweave/ordinary_plan_sources.py','src/parkweave/worker.py','src/parkweave/bounded_planning.py','src/parkweave/service_case_steps.py','src/parkweave/controlled_plans.py','src/parkweave/case_lifecycle.py','src/parkweave/case_goal_results.py','src/parkweave/dispatch_notices.py','src/parkweave/service_capability_catalog.py','src/parkweave/service_selection.py','src/parkweave/service_selection_candidates.py','src/parkweave/schema.sql','src/parkweave/roles.sql','src/parkweave/migration-032.sql','src/parkweave/migration-033.sql','tests/conftest.py','src/parkweave/web.html','docs/验收规格.json','docs/F1/ATBindings.json']
assert all(originalfiles[p]['sha256']==finalfiles[p]['sha256'] for p in protected_specific)
contracts=['docs/F2/LocalSyntheticDemoContract-20261017.md','docs/F2/OrdinarySyntheticDemoContract-20261018.md','docs/F2/OrdinaryCaseRecordRecheckContract-20261018.md'];assert all(originalfiles[p]['sha256']==finalfiles[p]['sha256'] for p in contracts)
proof['scope']=dict(baseline_code_readme=804,original_code_readme_unchanged=799,changed_original_code=sorted(code_changed),src_count=len(src),unchanged_src=len(src)-3,protected_specific={p:finalfiles[p]['sha256'] for p in protected_specific},old_three_contracts_byte_unchanged=True,fixed_AT_spec_and_bindings_byte_unchanged=True,README_byte_unchanged=True)
put('static-protection-verification.json',proof)
put('final-source-definition-refs.json',source_refs)

historical=dict(kind='HISTORICAL_INITIAL_SHA_STATIC_FINDING',reviewed_sha=INITIAL,oracle_ids=['LC-CS-02','LC-CS-04'],classification='P2_EXACT_OBJECT_ROUTING_CONTRACT_GAP',finding=proof['catalog_self_identity_fix']['initial_problem'],literal_counterexample=['Existing exact serviceA has demoA/catalogA bound to StoreS and local_demo_pair(serviceA,S,demoA)==true.','Another exact same-Store LocalDemoCatalog B exists, with B is not catalogA. B.connection obtains serviceA from ordinary.selected(StoreS).','The initial check tests only local_demo_pair(serviceA,S,demoA), which is true, so it enters serviceA._connection and B.validate/yield. No comparison relates B to catalogA.'],runtime_counterexample_executed=False,unauthorized_write_claimed=False,status='RESOLVED_BY_FINAL_STATIC_SELF_IDENTITY_CHECK',final_sha=FINAL,parent_initial_dynamic_reported=dict(nodes=13,PASS=13,pytest_seconds=84.75,not_independent=True,not_transferred_to_final=True),other_static_findings='No other definite P1/P2 identified. Original business algorithms/proofs unchanged by AST/bytes.',prior_platform_window_not_retried=True)
put('static-initial-3b559-review.json',historical)
rows=[
 ('LC-CS-01','STATIC_SATISFIED','case_step_assignments.from_environment;api.configured_app','New mode is explicit and requires existing profile/config. Original CURRENT_PREPARATION branch remains literal/AST preserved, no old denial fallback.'),
 ('LC-CS-02','STATIC_SATISFIED_AFTER_FIX','case_step_assignments.local_demo_pair/_unmixed;api.create_app;LocalDemoCatalog.connection','Exact classes and same Store/catalog identity are checked, including final catalog self identity. Initial exact-object P2 is retained separately as history.'),
 ('LC-CS-03','STATIC_SATISFIED','LocalDemoCatalog.validate;OrdinaryCaseStepAssignments._connection;launcher existing_local_demo_config','Original file/pack/journal/db/catalog/schema32/validity validation unchanged and runs before/after ordinary managed transaction. New config file reader is bounded, regular, read-only and no setup data generation is added.'),
 ('LC-CS-04','STATIC_SATISFIED','LocalDemoCatalog.connection;OrdinaryCaseStepAssignments._connection/_context;ordinary_plan_sources.guard_current','Catalog connection enters exactly paired ordinary managed transaction, which only calls catalog.validate rather than connection: no recursion. _checks are shared by source/current consumers. Parent callback uses validate(c,parent), original _parent final callback reloads/locks current parent and matches captured context owner/reviewer/park/org.'),
 ('LC-CS-05','STATIC_SATISFIED','OrdinaryCaseStepAssignments._context;original _parent/_binding/_live;service_capability_catalog;service_case_steps.current_sources','New context pins parent to demo mapping, filters/offers only original pack executor; original successful synthetic Case/current rights/Native/any Run assignment guards preserved. Original selection mapping and actual accepted executor/resource output comparisons unchanged.'),
 ('LC-CS-06','STATIC_SATISFIED','original _CaseStepTransactions methods;_OrdinaryCaseStep;ordinary_plan_sources;service_case_steps','All original business commands, marker/provenance/generation, one-offer, first deadline<=300s, 3s locks, receipt/recovery and source verifier algorithms are unchanged by AST/bytes.'),
 ('LC-CS-07','STATIC_SATISFIED','OrdinaryCaseStepAssignments._context/_connection;unchanged _parent/dispatch_command/receipt_command/P5 code','New global/context checks use catalog.validate only, not full snapshot or EXECUTE/current action checks. Parent final auth, owner history READ/PREPARE/resource READ, stopping WITHDRAW and original target/action checks stay in original algorithms.'),
 ('LC-CS-08','STATIC_SATISFIED','unchanged local_demo_selections.py/service_selection.py/LocalDemoSelector/contracts','Original UNIQUE NO_MODEL selection, provenance, request hashes/key, explicit ADOPT, publication=false/new_grants=false and registry reconstruction unchanged.'),
 ('LC-CS-09','STATIC_SATISFIED_NOT_EXECUTED','unchanged service_case_steps/case_lifecycle/case_goal_results/controlled_plans/ordinary_plan_sources/web','No P1-P5 workflow/proof/output/VIEW code changed. Manual VERIFY and source checks, original closing/reopening/TXT conservative semantics and executor whole-plan denial remain.'),
 ('LC-CS-10','STATIC_SATISFIED_NOT_EXECUTED','launcher serve/main;case_step_assignments.from_environment;unchanged worker.py;api.configured_app','Launcher passes same explicit JSON/mode/profile to both children and performs read-only preflight; API reuses same service demo instance, worker recreates its own same-Store graph via shared factory. No nonce/expiry reissue/seed path or runtime algorithm change; actual cold behavior is not independently executed.')]
put('oracle-static-findings.json',dict(final_sha=FINAL,oracle_sha256=sha((OUT/'literal-oracle-plan.json').read_bytes()),rows=[dict(id=i,status=s,evidence=e,reason=r) for i,s,e,r in rows],open_P1=[],open_P2=[],dynamic_execution=0))
commit=git('show','-s','--format=%H%n%T%n%P%n%s',FINAL).decode().splitlines()
put('static-git-evidence.json',dict(baseline=BASE,initial_sha=INITIAL,final_sha=FINAL,final_tree=commit[1],final_parent=commit[2],subject=commit[3],changes=changes,initial_to_final_changed_paths=fix_paths,selected_input_count=815,original_source_blind_hashes_unchanged=True,explicit_committed_git_only=True,working_tree_implementation_reads=0,product_imports=0))
report=dict(kind='INDEPENDENT_FINAL_STATIC_ONLY_REVIEW',baseline=BASE,initial_review_sha=INITIAL,final_sha=FINAL,final_tree=commit[1],created_at_utc=datetime.now(timezone.utc).isoformat(),conclusion='LIMITED_STATIC_ACCEPTANCE_NO_OPEN_P1_P2',oracle_rows=10,open_P1=[],open_P2=[],historical_findings=[dict(sha=INITIAL,id='P2_EXACT_OBJECT_ROUTING_CONTRACT_GAP',status='RESOLVED_IN_FINAL',detail='static-initial-3b559-review.json')],static_inputs=dict(baseline=811,initial=815,final=815,code_readme_baseline=804,original_code_readme_unchanged=799,src_total=len(src),other_src_unchanged=len(src)-3),independent_execution=dict(product_imports=0,dynamic_tests=0,DB_HTTP_lock_browser_tests=0,nodeIDs=[],pytest_seconds=None,collection=None,setup=None,call=None,teardown=None,JUnit=None,module_origins=None,shared_mirror_execution_maps=None),parent_execution=dict(final_status='NOT_INDEPENDENTLY_EXECUTED_OR_CLAIMED',planned_final_nodes=13,initial_parent_reported_nodes=13,initial_parent_reported_PASS=13,initial_parent_reported_seconds=84.75,initial_not_transferred_to_final=True),limitations=['Static review proves code wiring/guard/protection relationships only, not runtime concurrency, physical PostgreSQL/API/worker recovery or NodeVM/browser operation.','Pack/journal remain existing SYNTHETIC input anchors, not publication/approval/Grant/Native permit. No real authority or Run assignment issuance is added.','Original CURRENT_PREPARATION/local-demo-only behavior and Native/isolated/formal mutual exclusions remain; only the new exact pair is a routing exception.','Historical old HTTP timeout cause remains UNKNOWN; prior platform-marked dynamic window was not retried.','Formal sources/real business/real model/production install/actual browser/Windows/formal AT35/project completion remain unverified.','Original recovery/REOPEN optional SHA limitations are retained; no new signature, commit-atomicity or upstream authority claim.'],artifacts=dict(oracle='literal-oracle-plan.json',findings='oracle-static-findings.json',protection='static-protection-verification.json',history='static-initial-3b559-review.json',initial_map='initial-3b559-inputs.json',final_map='final-3f5fd029-inputs.json',fix_diff='initial-to-final-fix.diff',git='static-git-evidence.json'))
put('independent-final-review.json',report)
core=sorted([*freeze['files'],'freeze-manifest.json','finalize_static_review.py','initial-3b559-inputs.json','final-3f5fd029-inputs.json','implementation-contract.md','baseline-to-initial.diff','initial-to-final-fix.diff','baseline-to-final.diff','static-protection-verification.json','final-source-definition-refs.json','static-initial-3b559-review.json','oracle-static-findings.json','static-git-evidence.json','independent-final-review.json'])
assert len(core)==len(set(core))
entries=[dict(raw=n,public=n,raw_sha256=sha((OUT/n).read_bytes()),public_sha256=sha((OUT/n).read_bytes()),replacement_count=0,mode='IDENTITY_STATIC_PUBLIC_BYTES_NO_RUNTIME_SESSION_VALUES') for n in core]
put('raw-public-redaction-map.json',dict(kind='STATIC_IDENTITY_PUBLICATION_MAP',fixture_tokens_read_or_generated=0,total_replacements=0,entries=entries,notes='Identical raw/public paths are deliberate: static committed source/oracle/hash artifacts have no runtime session values. No mirror/PGdata/private token registries selected; byte-copy canonical originals, no second redaction.'))
put('raw-evidence-manifest.json',dict(kind='STATIC_CANONICAL_EVIDENCE_MANIFEST',final_sha=FINAL,dynamic_tests=0,files={n:dict(bytes=(OUT/n).stat().st_size,sha256=sha((OUT/n).read_bytes())) for n in core+['raw-public-redaction-map.json']}))
publication=sorted(core+['raw-public-redaction-map.json','raw-evidence-manifest.json']);put('publication-files.json',publication)
print(json.dumps(dict(final=FINAL,oracle_rows=10,open_P1=0,open_P2=0,independent_dynamic=0,baseline_inputs=811,final_inputs=815,protected_original_code_readme=799,unchanged_src=len(src)-3,publication_count=len(publication),identity_map_entries=len(entries),replacements=0,hashes={n:sha((OUT/n).read_bytes()) for n in ['independent-final-review.json','publication-files.json','raw-public-redaction-map.json','raw-evidence-manifest.json']}),indent=2))
