"""Static Git/AST/hash packaging only. Does not import or execute project code/tests."""
import ast, copy, hashlib, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path('/workspace/ParkWeave')
OUT=ROOT/'.runtime/at28-resource-observation-20261018/independent'
BASE='4c1aa1005d3e81dce5a240b3a9056627ff527f1b'
CONTRACT='48fd48f0dc8f39c60d32f25f8800cfd5a8f66f05'
FINAL='b379a61fe2fb17adde5de7a6f346f02db93505ee'
CONTRACT_PATH='docs/F2/AT28CurrentResourceObservationContract-20261018.md'

def sha(b): return hashlib.sha256(b).hexdigest()
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT)
def blob(rev,path): return git('show',rev+':'+path)
def save(name,obj):
    p=OUT/name
    if p.exists(): raise RuntimeError('Never overwrite evidence: '+name)
    p.write_bytes(obj if isinstance(obj,bytes) else (json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode())
def asttext(n): return ast.dump(n,include_attributes=False)
def source_node(t,name): return next(n for n in t.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name)
def metadata(rev,paths):
    result={}
    # Pure Git object reads; no working tree sources, imports, fixtures or subprocess tests.
    specs=[rev+':'+p for p in paths]
    batch=git('cat-file','--batch',) if not specs else subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(specs)+'\n').encode(),cwd=ROOT)
    at=0
    for p in paths:
        end=batch.index(b'\n',at);header=batch[at:end].decode().split();size=int(header[2]);at=end+1
        b=batch[at:at+size];at+=size+1
        result[p]={'git_blob':header[0],'bytes':len(b),'sha256':sha(b)}
    assert at==len(batch)
    return result

freeze=json.loads((OUT/'freeze-manifest.json').read_bytes())
assert all(sha((OUT/p).read_bytes())==h for p,h in freeze['files'].items())
oracle=json.loads((OUT/'literal-oracle-plan.json').read_bytes())
assert len(oracle['rows'])==8
assert blob(CONTRACT,CONTRACT_PATH)==blob(FINAL,CONTRACT_PATH)==(OUT/'contract-first-read.md').read_bytes()
base_map=json.loads((OUT/'baseline-inputs.json').read_bytes())
base_names=set(base_map['files'])
changes=git('diff','--name-status',BASE,FINAL).decode().splitlines()
changed_paths={line.split('\t')[-1] for line in changes}
expected_changes={CONTRACT_PATH,'docs/F1/ATBindings.json','src/parkweave/resource_holds.py','src/parkweave/web.html','tests/at28_resource_observation_html.js','tests/test_at28_resource_observation.py','tests/resource_alternative_times_offline.js'}
assert changed_paths==expected_changes
final_names=sorted(base_names|expected_changes)
final_map=metadata(FINAL,final_names)
changed_existing=[p for p in sorted(base_names) if base_map['files'][p]['sha256']!=final_map[p]['sha256']]
assert changed_existing==['docs/F1/ATBindings.json','src/parkweave/resource_holds.py','src/parkweave/web.html','tests/resource_alternative_times_offline.js']
assert len(final_names)==821
save('final-inputs.json',dict(kind='STATIC_EXACT_GIT_BLOB_INPUT_MAP',revision=FINAL,count=len(final_names),selection='818 original source-blind baseline paths plus unchanged committed contract and two new test source files; no shared/mirror execution maps are claimed',files=final_map))

resource='src/parkweave/resource_holds.py'
old=ast.parse(blob(BASE,resource));new=ast.parse(blob(FINAL,resource));normalized=copy.deepcopy(new)
preview=source_node(normalized,'preview')
ret=preview.body[0].body[-1]
assert isinstance(ret,ast.Return) and isinstance(ret.value,ast.Call)
new_keywords={k.arg:asttext(k.value) for k in ret.value.keywords if k.arg in {'resource_name','source','authority','timezone','external_availability','confirmation_required'}}
assert len(new_keywords)==6
for name in ['resource_name','source','authority','timezone']:
    key={'resource_name':'name'}.get(name,name)
    assert new_keywords[name]==asttext(ast.parse("r['"+key+"']",mode='eval').body)
assert new_keywords['external_availability']==asttext(ast.Constant('UNKNOWN'))
assert new_keywords['confirmation_required']==asttext(ast.Constant(True))
ret.value.keywords=[k for k in ret.value.keywords if k.arg not in new_keywords]
assert asttext(normalized)==asttext(old)
resource_functions={n.name:dict(byte_ast_unchanged=asttext(n)==asttext(source_node(new,n.name))) for n in old.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name!='preview'}
assert all(v['byte_ast_unchanged'] for v in resource_functions.values())

webpath='src/parkweave/web.html';oldweb=blob(BASE,webpath).decode();newweb=blob(FINAL,webpath).decode()
oldlines=oldweb.splitlines(keepends=True);newlines=newweb.splitlines(keepends=True)
helper_start=next(i for i,l in enumerate(newlines) if l.startswith('function resourceObservationText('))
helper_end=next(i for i in range(helper_start,len(newlines)) if newlines[i].rstrip() == '}')
helper=''.join(newlines[helper_start:helper_end+1])
assert helper_end-helper_start+1==5
normalized_web=newlines[:helper_start]+newlines[helper_end+1:]
handler_prefixes=["$('resource-catalog').onclick=", "$('resource-preview').onclick="]
for prefix in handler_prefixes:
    oldline=next(l for l in oldlines if l.startswith(prefix))
    indexes=[i for i,l in enumerate(normalized_web) if l.startswith(prefix)]
    assert len(indexes)==1
    normalized_web[indexes[0]]=oldline
assert ''.join(normalized_web)==oldweb
final_handler=next(l for l in newlines if l.startswith(handler_prefixes[1]))
assert final_handler.index('resourcePreview=null')<final_handler.index('const x=await resourceCall')<final_handler.index('const observation=resourceObservationText')<final_handler.index('resourcePreview={view:x,context:c}')<final_handler.index("$('resource-hold').disabled=!x.available")
assert "$('resource-hold').disabled=true" in final_handler
assert "$('resource-preview-result').textContent=" in final_handler
assert '.innerHTML' not in helper+final_handler
assert "function textElement(tag,text){const el=document.createElement(tag);el.textContent=text;return el;}" in newweb

before_bind=json.loads(blob(BASE,'docs/F1/ATBindings.json'));after_bind=json.loads(blob(FINAL,'docs/F1/ATBindings.json'))
assert len(before_bind['cases'])==len(after_bind['cases'])==42
before_by={x['id']:x for x in before_bind['cases']};after_by={x['id']:x for x in after_bind['cases']}
assert before_by.keys()==after_by.keys()
assert all(before_by[k]['whole_status']==after_by[k]['whole_status'] for k in before_by)
assert all(before_by[k]==after_by[k] for k in before_by if k!='AT-28')
normalized_binding=copy.deepcopy(after_bind)
for x in normalized_binding['cases']:
    if x['id']=='AT-28':
        assert set(k for k in x if x[k]!=before_by['AT-28'].get(k))=={'engineering_selectors','gate'}
        x['engineering_selectors']=before_by['AT-28']['engineering_selectors'];x['gate']=before_by['AT-28']['gate']
assert normalized_binding==before_bind
assert blob(BASE,'docs/验收规格.json')==blob(FINAL,'docs/验收规格.json')

all_base=git('ls-tree','-r','--name-only',BASE).decode().splitlines()
code_names=[p for p in all_base if p.startswith(('src/','tests/','scripts/')) or p in ('pyproject.toml','README.md')]
assert len(code_names)==801
protected_unchanged=[p for p in code_names if p not in changed_existing]
assert len(protected_unchanged)==798
assert all(base_map['files'][p]['sha256']==final_map[p]['sha256'] for p in protected_unchanged)
src_names=[p for p in all_base if p.startswith('src/')]
assert set(p for p in src_names if base_map['files'][p]['sha256']!=final_map[p]['sha256'])=={resource,webpath}
protected_groups={
 'all_other_src': [p for p in src_names if p not in (resource,webpath)],
 'template_named_sources': [p for p in src_names if 'template' in p.lower() or 'catalog' in p.lower()],
 'schema_roles_migrations': [p for p in code_names if any(k in p.lower() for k in ['schema','roles.sql','migration'])],
 'conftest': [p for p in code_names if p.endswith('conftest.py')],
 'all_scripts': [p for p in code_names if p.startswith('scripts/')],
}
proof=dict(kind='STATIC_BYTE_AST_SCOPE_PROOF',baseline=BASE,final=FINAL,baseline_code_readme_count=801,unchanged_original_code_readme_count=798,changed_existing_code=[p for p in changed_existing if p!='docs/F1/ATBindings.json'],src_total=len(src_names),unchanged_other_src_count=len(src_names)-2,resource_module_after_removing_only_six_return_keywords_AST_identical=True,new_preview_return_keywords=new_keywords,resource_other_definitions=resource_functions,web_after_removing_only_five_line_helper_and_restoring_two_handlers_byte_identical=True,web_validate_before_cache_enable_order=True,web_original_context_auth_aba_late_error_hold_expected_revision_unchanged=True,old_success_display_note='On a new invalid metadata response, actionable cache is null and HOLD remains disabled; original prior successful result text may remain alongside an explicit current unverified error. Invalid metadata is never assigned as current actionable preview. Contract does not require deleting all historical result text.',ATBindings=dict(total_cases=42,all_42_whole_status_unchanged=True,other_41_case_records_unchanged=True,AT28_changed_keys=['engineering_selectors','gate'],fixed_spec_byte_unchanged=True),protected_groups={k:{'count':len(v),'all_byte_identical':all(base_map['files'][p]['sha256']==final_map[p]['sha256'] for p in v),'paths':v} for k,v in protected_groups.items()})
save('protection-verification.json',proof)

# Archive exact committed differences and line-labelled original context for human inspection.
save('git-final.diff',git('diff','--no-ext-diff','--unified=12',BASE,FINAL))
source_excerpt=[]
for path,lo,hi in [(resource,65,170),(webpath,1069,1106),('tests/test_at28_resource_observation.py',1,200)]:
    source_excerpt.append('\nFILE '+FINAL+':'+path+'\n')
    for line_no,line in enumerate(blob(FINAL,path).decode().splitlines(),1):
        if lo<=line_no<=hi:source_excerpt.append(str(line_no)+': '+line+'\n')
save('committed-source-excerpts.txt',''.join(source_excerpt).encode())
commit_lines=git('show','-s','--format=%H%n%T%n%P%n%s',FINAL).decode().splitlines()
save('static-git-evidence.json',dict(final_commit=commit_lines[0],final_tree=commit_lines[1],parent=commit_lines[2],subject=commit_lines[3],explicit_git_reads_only=True,working_tree_product_read=False,changes=changes,changed_existing_inputs=changed_existing,new_selected_inputs=sorted(set(final_names)-base_names),contract_byte_identical_to_first_commit=True,initial_freeze_manifest_all_files_unchanged=True,local_skill_directories_present=False))
findings=[
 ('AT28-OBS-01','STATIC_SATISFIED','resource_holds.py:152-161', 'All six new kwargs are either r post-lock fields or constants; resource module is original AST after removing exactly those six keywords.'),
 ('AT28-OBS-02','STATIC_SATISFIED','resource_holds.py:137-138,159-161;web.html:1101-1102','Existing SYNTHETIC/NOT_CONFIRMED/NOT_SUBMITTED/NO_EVIDENCE preserved; UNKNOWN and explicit confirmation are unconditional, including locally available=true.'),
 ('AT28-OBS-03','STATIC_SATISFIED','web.html:1100-1102','Resource revision and source revision are separate fields; original post-lock clock_timestamp remains server_time; UI calls it database observation UTC and explicitly not upstream update time.'),
 ('AT28-OBS-04','STATIC_SATISFIED','web.html:1098,1102,1104','Catalog read time and old catalog source remain separate from latest preview name/resource revision/source fields/local capacity and explicit hold/confirm. No cache rewrite or automatic write added.'),
 ('AT28-OBS-05','STATIC_SATISFIED_WITH_DISPLAY_NOTE','web.html:1100-1105','Validation precedes cache and HOLD enable; invalid metadata leaves cache null and HOLD disabled with unverified error. Prior successful display may remain, but is not made actionable; no fallback metadata is created.'),
 ('AT28-OBS-06','STATIC_SATISFIED','web.html:385,1069-1078,1097,1104-1105','Original generation/token/id/draft/current/fetch/error/ABA guards and HOLD submission remain byte identical; new metadata uses textContent. No new browser persistence or recovery.'),
 ('AT28-OBS-07','STATIC_SATISFIED','protection-verification.json','Original resource AST preserved after six return additions; 798/801 original code+README files byte identical, including all other source, templates, schema/roles/migrations/scripts/conftest. No SQL/write/endpoint/provider change.'),
 ('AT28-OBS-08','STATIC_SATISFIED_NOT_DYNAMIC_EXECUTION','docs/F1/ATBindings.json;fixed docs/验收规格.json','Only AT28 selectors/gate changed; all 42 whole statuses and fixed spec unchanged. Current slice reviewed static only; old template risk operation and HTTP UNKNOWN untouched.')]
save('oracle-static-findings.json',dict(oracle_sha256=sha((OUT/'literal-oracle-plan.json').read_bytes()),final=FINAL,rows=[dict(id=i,status=s,evidence=e,reason=r) for i,s,e,r in findings],open_P1=[],open_P2=[],dynamic_cases_executed=0))
report=dict(kind='INDEPENDENT_STATIC_ONLY_FINAL_REVIEW',baseline=BASE,contract_commit=CONTRACT,final_sha=FINAL,final_tree=commit_lines[1],recorded_at_utc=datetime.now(timezone.utc).isoformat(),conclusion='LIMITED_STATIC_ACCEPTANCE_NO_OPEN_P1_P2',genuine_increment=True,oracle_rows=8,open_P1=[],open_P2=[],static_proofs=dict(baseline_selected_inputs=818,final_selected_inputs=821,baseline_code_readme=801,original_code_readme_unchanged=798,src_files=len(src_names),other_src_unchanged=len(src_names)-2,resource_six_return_keywords_only=True,remaining_resource_module_AST_identical=True,remaining_web_byte_identical_after_two_handlers_and_helper=True,all_42_AT_status_unchanged=True,fixed_AT_spec_unchanged=True,contract_unchanged=True),independent_execution=dict(product_imports=0,dynamic_tests=0,DB_HTTP_lock_browser_tests=0,nodeIDs=[],elapsed_pytest_seconds=None,collection=None,setup=None,call=None,teardown=None,JUnit=None,module_origins=None,shared_mirror_execution_maps=None),parent_dynamic_results=dict(status='NOT_INDEPENDENTLY_EXECUTED_OR_CLAIMED',planned_nodes_as_reported=7,results_not_used_for_static_conclusion=True),scope_notes=['This fills current post-lock resource preview source disclosure and local observation presentation; no whole AT28 acceptance.','Source kind/id/revision/statement are existing database fields, not new source authority or proof of upstream freshness. LOCAL_AUTHORITY applies only to the synthetic local ledger.','Preview does not hold or confirm. Original HOLD expected_revision/current grants/locks/window/buffer/capacity/replay/TTL and original single/combination confirmation remain unchanged.','Validation rejects unverified current metadata before actionable cache/HOLD; previous successful display text may remain with the new explicit error, preserving original error presentation.','Parent test source statically includes one read-only API source-change check and three full-page NodeVM modes (positive/missing-source/invalid-time). Reviewer did not execute, collect or claim those nodes.','New test uses original owned fixture; only its synthetic row source/revision/capacity/name are changed. No role/schema/conftest/real identity or Grant changes appear in the committed diff.'],remaining_blockers=['Formal whole AT28 remains NOT_RUN; real external resource availability, source authority, booking and fulfillment not verified.','Windows/actual browser/formal AT/real identity/Grant/approval/model/production not executed.','AT29 legal stop/calendar/source authority remains separate and absent; this slice does not create it.','Historical template platform-marked dynamic window was not retried; historical HTTP timeout root cause remains UNKNOWN.'],artifact_refs=dict(oracle='literal-oracle-plan.json',oracle_findings='oracle-static-findings.json',protection='protection-verification.json',baseline_inputs='baseline-inputs.json',final_inputs='final-inputs.json',diff='git-final.diff',git='static-git-evidence.json'))
save('independent-final-review.json',report)

# Static source text only: no fixtures were run and no session values were created/read.
core=sorted([*freeze['files'].keys(),'freeze-manifest.json','finalize_static_review.py','final-inputs.json','protection-verification.json','git-final.diff','committed-source-excerpts.txt','static-git-evidence.json','oracle-static-findings.json','independent-final-review.json'])
assert len(core)==len(set(core))
entries=[]
for name in core:
    b=(OUT/name).read_bytes();h=sha(b)
    entries.append(dict(raw=name,public=name,raw_sha256=h,public_sha256=h,replacement_count=0,mode='IDENTITY_STATIC_PUBLIC_BYTES_NO_TOKEN_VALUES'))
save('raw-public-redaction-map.json',dict(kind='STATIC_IDENTITY_PUBLICATION_MAP',fixture_tokens_read_or_generated=0,total_replacements=0,entries=entries,notes='Raw/public paths are identical for this static-only source/oracle/hash material. No raw logs, fixture sessions, runtime mirror, PGdata, credentials, or private token registries are selected. No second redaction is permitted.'))
manifest_paths=core+['raw-public-redaction-map.json']
save('raw-evidence-manifest.json',dict(kind='STATIC_CANONICAL_EVIDENCE_MANIFEST',final_sha=FINAL,files={p:dict(bytes=(OUT/p).stat().st_size,sha256=sha((OUT/p).read_bytes())) for p in manifest_paths},dynamic_tests=0))
publication=sorted(core+['raw-public-redaction-map.json','raw-evidence-manifest.json'])
save('publication-files.json',publication)
print(json.dumps(dict(final=FINAL,oracle_rows=8,open_P1=0,open_P2=0,independent_dynamic=0,baseline_inputs=818,final_inputs=821,unchanged_original_code_readme=798,src_total=len(src_names),unchanged_other_src=len(src_names)-2,publication_count=len(publication),identity_map_entries=len(entries),replacements=0,hashes={p:sha((OUT/p).read_bytes()) for p in ['independent-final-review.json','publication-files.json','raw-public-redaction-map.json','raw-evidence-manifest.json']}),indent=2))
