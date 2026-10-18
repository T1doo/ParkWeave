"""Static review and historical evidence publication only; no product imports/tests."""
from pathlib import Path
import ast,copy,hashlib,json,re,subprocess,xml.etree.ElementTree as ET,datetime
BASE=Path(__file__).resolve().parent;ROOT=Path('/workspace/ParkWeave')
FINAL='9f8c51fe58f6693be9ca185d90c0dee3524fa000';INTERIM='ef99c40d862aeb086360ac77dc0f1e3de09179f0';OLD='b697718673e3902b2febc0efc3407b438a861831';ORIGINAL='0b7ee3544fa669e621c8b8ffd58714fa357264b3'
WINDOW=BASE/'frozen-b6977186-window1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_text())
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def source(rev,path):return git('show',rev+':'+path).decode()
def write(name,value):
 with (BASE/name).open('x') as f:json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2);f.write('\n')
def function(tree,klass,name):
 parent=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name==klass)
 return next(x for x in parent.body if isinstance(x,ast.FunctionDef) and x.name==name)
def dumped(tree):return ast.dump(tree,include_attributes=False)
path='src/parkweave/template_consumer.py';old=ast.parse(source(OLD,path));final=ast.parse(source(FINAL,path))
methods=['validate_fixture','_auth','_reviewer','_published','_stage_key','_available','catalog','consume','recover_creation','_unknown','read','resume']
checks={n:dumped(function(old,'TemplateConsumer',n))==dumped(function(final,'TemplateConsumer',n)) for n in methods};assert all(checks.values())
new=copy.deepcopy(function(final,'TemplateConsumer','_perform'))
# Erase only the new no-pin-inert marker/preflight and its dedicated catch.
new.body=[n for n in new.body if not (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='late_pin_check' for t in n.targets))]
for n in new.body:
 if isinstance(n,ast.Try) and n.handlers and isinstance(n.handlers[0].type,ast.Tuple):
  n.body=[x for x in n.body if not (isinstance(x,ast.If) and isinstance(x.test,ast.Name) and x.test.id=='late_pin_check') and not (isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='late_pin_check' for t in x.targets))]
  n.handlers[0].body=[x for x in n.handlers[0].body if not (isinstance(x,ast.If) and any(isinstance(y,ast.Name) and y.id=='late_pin_check' for y in ast.walk(x.test)))]
legacy_equal=dumped(new)==dumped(function(old,'TemplateConsumer','_perform'));assert legacy_equal
protected=['src/parkweave/template_candidate.py','src/parkweave/template_candidate_api.py','src/parkweave/template_isolated_app.py','src/parkweave/service_instance_consumer.py','src/parkweave/service_capability_catalog.py','src/parkweave/api.py','src/parkweave/case_step_assignments.py','src/parkweave/roles.sql','src/parkweave/schema.sql','tests/conftest.py']
protected_check={p:git('rev-parse',FINAL+':'+p)==git('rev-parse',ORIGINAL+':'+p) for p in protected};assert all(protected_check.values())
with (BASE/'static-final-source-diff.patch').open('xb') as f:f.write(git('diff',OLD,FINAL,'--',path))
write('static-final-code-checks.json',dict(source_sha=FINAL,compared_to=OLD,unchanged_AST_methods=checks,legacy_perform_AST_equal_after_erasing_only_pin_guard=True,protected_from_original_baseline=protected_check,product_imports_or_dynamic_execution=0))
# Historical executed input maps and origins are preserved and checked, never migrated.
control=load(WINDOW/'controller-result.json');runtime=load(WINDOW/'pytest-result.json');maps=[load(WINDOW/n) for n in ['shared-before.json','shared-after.json','mirror-before.json','mirror-after.json']]
assert control['source_sha']==OLD and control['exit_code']==1 and control['frozen_input_count']==823 and all(m==maps[0] for m in maps)
assert all(not control[k] for k in ['shared_drift','mirror_drift','shared_mirror_mismatch','independent_source_drift'])
ids=[x['nodeid'] if isinstance(x,dict) else x for x in load(WINDOW/'collection.json')];rows=[json.loads(l) for l in (WINDOW/'calls.jsonl').read_text().splitlines()]
assert len(ids)==len(set(ids))==6
xml=ET.parse(WINDOW/'results.xml').getroot();cases=list(xml.iter('testcase'))
jids=[v.get('classname').replace('.','/')+'.py::'+v.get('name') for v in cases];assert set(jids)==set(ids) and len(jids)==6
phases={}
for phase in ['setup','call','teardown']:
 actual=[r for r in rows if r['when']==phase];assert len(actual)==6 and {r['nodeid'] for r in actual}==set(ids)
 phases[phase]={o:sum(r['outcome']==o for r in actual) for o in ['passed','failed','skipped']}
assert phases['setup']['passed']==phases['teardown']['passed']==6 and phases['call']['passed']==5 and phases['call']['failed']==1
origins=load(WINDOW/'module-origins.json');assert all(v['within_mirror'] and (v['matches_frozen'] or v['matches_independent_probe']) and sha(Path(v['path']))==v['sha256'] for v in origins)
private_before=load(WINDOW/'independent-source-before.json');assert private_before==load(WINDOW/'independent-source-after.json')
for name,h in private_before.items():assert sha(BASE/name)==h
assert sha(WINDOW/'mirror/tests/test_independent_ordinary_template_inputs.py')==private_before['test_independent_ordinary_template_inputs.py']
assert sha(WINDOW/'mirror/tests/independent_template_inputs_html.js')==private_before['independent_template_inputs_html.js']
write('historical-window-validation.json',dict(source_sha=OLD,control=control,collection=ids,phases=phases,JUnit=[x.attrib for x in xml.iter('testsuite')],module_origins_count=len(origins),frozen_origins=sum(x['matches_frozen'] for x in origins),private_origins=sum(x['matches_independent_probe'] for x in origins),all_actual_origin_hashes_match=True,all4_input_maps_equal=True,private_inputs_equal=True,migrated_to_final=False,pg_cleanup_record=load(WINDOW/'owned-pg-after-exit.json')))
# Reconstruct final static Git input hashes without importing/executing its product.
paths=sorted(maps[0]);meta=git('ls-tree','-rz',FINAL,'--',*paths);objects={}
for row in meta.split(b'\0'):
 if not row:continue
 header,name=row.split(b'\t');mode,typ,oid=header.decode().split();assert typ=='blob';objects[name.decode()]=oid
assert set(objects)==set(paths)
raw=subprocess.run(['git','cat-file','--batch'],cwd=ROOT,input=('\n'.join(objects[p] for p in paths)+'\n').encode(),capture_output=True,check=True).stdout
pos=0;final_map={}
for p in paths:
 end=raw.index(b'\n',pos);oid,typ,size=raw[pos:end].decode().split();size=int(size);pos=end+1;data=raw[pos:pos+size];pos+=size+1
 assert oid==objects[p] and typ=='blob';final_map[p]=hashlib.sha256(data).hexdigest()
changed=[p for p in paths if final_map[p]!=maps[0][p]];assert changed==['src/parkweave/template_consumer.py','tests/test_ordinary_template_inputs.py']
write('final-static-source-inputs.json',dict(source_sha=FINAL,kind='STATIC_GIT_BLOB_INPUT_HASHES_NOT_EXECUTED_MIRROR',count=len(final_map),changed_from_executed_b697=changed,files=final_map))
write('static-final-review.json',dict(kind='STATIC_ONLY_FINAL_FIX_REVIEW',source_sha=FINAL,reviewed_git_objects_only=True,dynamic_product_imports_DB_HTTP_lock_or_test_count=0,open_P1=[],open_P2=[],conclusion='LIMITED_STATIC_FIX_ACCEPTANCE; NO_FINAL_SHA_INDEPENDENT_DYNAMIC_PASS',findings=[dict(id='JOURNAL_WAIT_CATALOG_PIN',prior='Dynamically saved historical red window only; not repeated here',static_fix='After original journal/body waits, the pinned-only late block reauthenticates, checks immutable instance/scope/database, current release+catalog pin and reviewer, before original send.',lines=[342,344,347,348,349,350,352],closure='STATIC_ONLY'),dict(id='LATE_REFUSAL_UNKNOWN_ERASURE',prior='ef99 static P2 retained in static-ef99-review.json',static_fix='late_pin_check stays true only during the new preflight and is cleared before send. A late Denied/Conflict on nonfresh persisted STARTED/UNKNOWN runs original _unknown and raises before REFUSED/BLOCKED. Fresh/ADMITTED first-send refusal retains original path.',lines=[342,351,353,354,356,357],closure='STATIC_ONLY')],preserved={'original_isolated_and_CURRENT_provider_guards':protected_check,'no_pin_legacy_control_flow_AST_equal':legacy_equal,'unchanged_consumer_methods_AST':checks,'old_fingerprint_GET_and_journal_semantics':True,'no_new_source_Grant_role_permit_or_backend':True},limitations=['A check immediately before send is not a claim of cross-database commit atomicity.','Final9f8 has no independent dynamic rerun by explicit parent instruction. Parent final tests belong to parent evidence, not this reviewer count.','Ordinary configured startup still has no formal template source/approval/subject mapping and cannot create a formal template instance; isolated fixture positive is separate.','Historical original HTTP timeout remains UNKNOWN.'],interruption_record={'source':'parent task notification','prior_final_report_interrupted_by_platform_risk_flag':True,'interrupted_dynamic_operation_or_report_retried':False,'new_authorization':'Only static Git-object review and existing-evidence canonical organization','direct_auto_review_tool_denial_observed_in_this_static_task':False}))
report=dict(schema=1,scope='ORDINARY_TEMPLATE_INPUT_UI_CATALOG_PIN_AND_CREATION_GET__FINAL_STATIC_REVIEW',source_sha=FINAL,baseline=ORIGINAL,conclusion='LIMITED_STATIC_REVIEW_ACCEPTANCE',open_P1=[],open_P2=[],final_independent_dynamic_nodes=0,final_independent_dynamic_PASS=0,final_combined_unique_PASS=None,final_root_test_status='Recorded separately by parent; not imported as independent execution',static_review='static-final-review.json',code_checks='static-final-code-checks.json',source_input_map='final-static-source-inputs.json',source_oracle={'path':'literal-oracle-plan.json','rows':14,'sha256':sha(BASE/'literal-oracle-plan.json'),'unchanged':True},formal_minimum_map={'path':'formal-minimum-object-authority-map.json','sha256':sha(BASE/'formal-minimum-object-authority-map.json'),'ordinary_formal_success':False},historical_window={'path':WINDOW.name,'source_sha':OLD,'collection':6,'phases':phases,'call_PASS':5,'call_FAIL':1,'pytest_seconds':runtime['pytest_main_seconds'],'outer_seconds':control['outer_seconds'],'no_rerun_or_retry':True,'four_maps_zero_drift':True,'input_count':823,'origins':len(origins),'counts_not_migrated_to_final':True,'raw_failures_preserved':True},ef99_static_review='static-ef99-review.json',final_static_reviews_close_saved_findings_without_retesting=True,evidence_limits=['No claim that historical5PASS or root b697/ef99 windows test final9f8. No aggregate across these SHAs.','No actual business/HTTP/DB/lock operation after the separately authorized static-only boundary; only Git/files/AST/hash/XML processing.','Previous platform interruption and original failure remain preserved; no retry of interrupted activity.','The existing owned test fixture teardown reports dead zombie PG child awaiting reaping and removed temporary data under its original lifecycle. This static review neither stops nor deletes any process/lock/data.','Original full HTML NodeVM is not a real browser; no Windows/model/third custom scope/fullP1-P5 or actual identity/Grant/publication/credential/production operation.'],publication_list='publication-files.json',raw_public_map='raw-public-redaction-map.json',raw_evidence_manifest='raw-evidence-manifest.json')
write('independent-final-review.json',report)
with (BASE/'active-review-path.txt').open('x') as f:f.write(str(BASE)+'\n')
# Only own captured fixture values; never consult parent inventories.
tokens=set(load(WINDOW/'fixture-token-values.private.json'));assert len(tokens)==42
selected=[p for p in BASE.iterdir() if p.is_file() and '.private.' not in p.name]
selected += [p for p in WINDOW.iterdir() if p.is_file() and '.private.' not in p.name]
for child in ['scenarios','root-overlap-evidence','original-process-evidence','owned-state-logs']:
 if (WINDOW/child).exists():selected += [p for p in (WINDOW/child).rglob('*') if p.is_file()]
selected=sorted(set(selected));assert not any('token' in p.name.lower() or p.name in ['sessions.json','state.json','creation-observation.json'] for p in selected)
def scrub(value):
 result=value;count=0
 for token in sorted(tokens,key=len,reverse=True):
  n=result.count(token);result=result.replace(token,'SYNTHETIC_SESSION_REDACTED');count+=n
 for token in sorted(tokens,key=len,reverse=True):
  for n in range(len(token)-1,7,-1):
   for fragment in [token[:n],token[-n:]]:
    hits=result.count(fragment);result=result.replace(fragment,'SYNTHETIC_SESSION_FRAGMENT_REDACTED');count+=hits
 return result,count
mapping=[];publication=[]
for p in selected:
 relative=str(p.relative_to(BASE));raw=p.read_bytes()
 if p.suffix=='.xml':
  original=ET.parse(p).getroot();safe=copy.deepcopy(original);count=0
  for element in safe.iter():
   if element.text is not None:element.text,n=scrub(element.text);count+=n
   if element.tail is not None:element.tail,n=scrub(element.tail);count+=n
   for key,v in tuple(element.attrib.items()):element.attrib[key],n=scrub(v);count+=n
  encoded=ET.tostring(safe,encoding='utf-8',xml_declaration=True) if count else raw;parsed=ET.fromstring(encoded)
  assert [x.attrib for x in parsed.iter('testcase')]==[x.attrib for x in original.iter('testcase')]
  assert [x.tag for x in parsed.iter()]==[x.tag for x in original.iter()]
 else:
  safe,count=scrub(raw.decode());encoded=safe.encode()
 if count:
  dest=BASE/'public'/relative;dest.parent.mkdir(parents=True,exist_ok=True)
  with dest.open('xb') as f:f.write(encoded)
  public=str(dest.relative_to(BASE))
 else:public=relative
 publication.append(public);mapping.append(dict(raw=relative,public=public,raw_sha256=sha(p),public_sha256=hashlib.sha256(encoded).hexdigest(),replacement_count=count))
write('raw-public-redaction-map.json',dict(schema=1,files=mapping,replacement_count=sum(x['replacement_count'] for x in mapping),captured_own_fixture_session_values=len(tokens),policy='Only own prior window fixture tokens;42 full values and captured prefix/suffix fragments scrubbed once. XML text/tail/attributes serialized and parsed preserving exact testcase/outcome shape. No parent token inventory. Raw retained; canonical copied byte-for-byte without further redaction.'))
publication += ['publication-files.json','raw-public-redaction-map.json','raw-evidence-manifest.json'];publication=sorted(publication);assert len(publication)==len(set(publication))
write('publication-files.json',publication)
write('raw-evidence-manifest.json',dict(schema=1,source_sha=FINAL,historical_dynamic_source_sha=OLD,self_hash_excluded=True,excludes=['mirror','PGdata','private fixture token inventory','configuration/credential/state/session files'],files=[dict(path=n,sha256=sha(BASE/n),bytes=(BASE/n).stat().st_size) for n in publication if n!='raw-evidence-manifest.json']))
for n in publication:
 s=(BASE/n).read_text();assert not any(t in s or t[:8] in s or t[-8:] in s for t in tokens),n
 if n.endswith('.xml'):ET.parse(BASE/n)
for row in mapping:assert sha(BASE/row['raw'])==row['raw_sha256'] and sha(BASE/row['public'])==row['public_sha256']
print(json.dumps(dict(source_sha=FINAL,static_only=True,final_independent_dynamic_nodes=0,historical_PASS=5,historical_FAIL=1,publication_files=len(publication),replacement_count=sum(x['replacement_count'] for x in mapping),report_sha256=sha(BASE/'independent-final-review.json'),publication_sha256=sha(BASE/'publication-files.json'),map_sha256=sha(BASE/'raw-public-redaction-map.json'),manifest_sha256=sha(BASE/'raw-evidence-manifest.json'))))
