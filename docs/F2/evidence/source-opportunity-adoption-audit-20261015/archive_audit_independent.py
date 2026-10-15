"""Independent read-only source-adoption archive and coverage verification."""
from pathlib import Path
from collections import Counter
import ast, hashlib, json, re, subprocess
import xml.etree.ElementTree as ET

ROOT=Path('/workspace/ParkWeave');OUT=ROOT/'docs/F2/evidence/source-opportunity-adoption-20261015'
index_path=OUT/'index.json';idx=json.loads(index_path.read_text());entries=idx['entries']
freeze='4c163fe23d8a841ece7b796e40e35511d70a0797';assert idx['source_sha']==freeze
private=set()
for name in ('template-migration-tests-20261014','template-structure-tests-20261015'):
 p=ROOT/'.runtime'/name/'redaction-values.private.json'
 if p.exists():private.update(x for x in json.loads(p.read_text()) if isinstance(x,str) and len(x)>=16)
private=sorted(private,key=len,reverse=True)
checks=Counter();redactions=Counter();seen=set();raw_seen=set();all_private_residuals=[];suspicious_tokens=[]
fixture=re.compile(r'^\s*\w+\s*=\s*[({].*Store object at 0x|^\s*(?:tokens|session_tokens)\s*=\s*\{')
def reconstructed(raw,suffix):
 count=Counter(exact_private_value=0,fixture_repr_line=0)
 def redact(s):
  for secret in private:
   n=s.count(secret);count['exact_private_value']+=n
   if n:s=s.replace(secret,'[REDACTED_SYNTHETIC_SESSION]')
  lines=[]
  for line in s.splitlines(keepends=True):
   if fixture.match(line):count['fixture_repr_line']+=1;line='[REDACTED_SYNTHETIC_FIXTURE_REPR]'+ ('\n' if line.endswith('\n') else '')
   lines.append(line)
  return ''.join(lines)
 def visit(x):
  if isinstance(x,str):return redact(x)
  if isinstance(x,list):return [visit(v) for v in x]
  if isinstance(x,dict):return {k:visit(v) for k,v in x.items()}
  return x
 text=raw.decode()
 if suffix=='.xml':
  tree=ET.fromstring(text)
  for node in tree.iter():
   if node.text:node.text=redact(node.text)
   if node.tail:node.tail=redact(node.tail)
   for k,v in list(node.attrib.items()):node.set(k,redact(v))
  result=ET.tostring(tree,encoding='utf-8',xml_declaration=True)
 elif suffix=='.json':result=(json.dumps(visit(json.loads(text)),ensure_ascii=False,indent=2)+'\n').encode()
 elif suffix=='.jsonl':result=''.join(json.dumps(visit(json.loads(line)),ensure_ascii=False)+'\n' for line in text.splitlines() if line.strip()).encode()
 else:result=redact(text).encode()
 return (result if any(count.values()) else raw),dict(count)
def sha(b):return hashlib.sha256(b).hexdigest()
for e in entries:
 rawpath=ROOT/e['raw_path'];target=ROOT/e['export_path']
 assert rawpath.resolve().is_relative_to(ROOT/'.runtime') and target.resolve().is_relative_to(OUT)
 assert target not in seen and rawpath not in raw_seen;seen.add(target);raw_seen.add(rawpath)
 assert '.private.' not in target.name and '__pycache__' not in target.parts
 raw=rawpath.read_bytes();data=target.read_bytes()
 assert (sha(raw),len(raw))==(e['raw_sha256'],e['raw_bytes'])
 assert (sha(data),len(data))==(e['export_sha256'],e['export_bytes'])
 expected,counts=reconstructed(raw,target.suffix);assert data==expected and counts==e['redactions']
 redactions.update(counts);checks['indexed_files']+=1;checks['export_bytes']+=len(data)
 if any(v.encode() in data for v in private):all_private_residuals.append(e['export_path'])
 if any(re.search(rb'[A-Z]',x) and re.search(rb'[a-z]',x) and re.search(rb'[0-9]',x) for x in re.findall(rb'[\"\']([A-Za-z0-9_-]{43})[\"\']',data)):suspicious_tokens.append(e['export_path'])
 if target.suffix=='.xml':
  a=ET.fromstring(raw);b=ET.fromstring(data)
  assert [(n.tag,sorted(n.attrib)) for n in a.iter()]==[(n.tag,sorted(n.attrib)) for n in b.iter()]
  assert Counter((t.attrib.get('classname'),t.attrib.get('name'),t.find('failure') is not None,t.find('error') is not None,t.find('skipped') is not None) for t in a.iter('testcase'))==Counter((t.attrib.get('classname'),t.attrib.get('name'),t.find('failure') is not None,t.find('error') is not None,t.find('skipped') is not None) for t in b.iter('testcase'))
  checks['xml']+=1
 elif target.suffix=='.json':json.loads(data);checks['json']+=1
 elif target.suffix=='.jsonl':
  for line in data.splitlines():json.loads(line)
  checks['jsonl']+=1
 elif target.suffix=='.py':ast.parse(data);compile(data,str(target),'exec');assert data==raw;checks['python']+=1
 elif target.suffix=='.js':
  assert data==raw;r=subprocess.run(['node','--check',str(target)],capture_output=True,text=True);assert r.returncode==0,r.stderr;checks['javascript']+=1
assert not all_private_residuals
extras=sorted(str(p.relative_to(OUT)) for p in OUT.rglob('*') if p.is_file() and p not in seen)
assert extras==['.gitattributes','README.md','audit.json','index.json'],extras
assert (OUT/'.gitattributes').read_text().splitlines()[-1]=='* -text'
assert 'metadata outside the indexed raw-export pairs' in (OUT/'README.md').read_text()

def junit(path):
 root=ET.parse(ROOT/path).getroot();res={}
 for t in root.iter('testcase'):
  key=t.attrib['classname'].replace('.','/')+'.py::'+t.attrib['name']
  assert key not in res
  res[key]='FAIL' if t.find('failure') is not None or t.find('error') is not None else 'SKIP' if t.find('skipped') is not None else 'PASS'
 return res
rootrun=junit('.runtime/source-adoption/root-final.xml');hold=junit('.runtime/source-adoption/hold-recheck.xml');delta=junit('.runtime/source-adoption/delta-4c163fe.xml')
assert Counter(rootrun.values())=={'PASS':1661,'FAIL':27};assert Counter(hold.values())=={'PASS':7};assert Counter(delta.values())=={'PASS':297,'SKIP':8}
col=json.loads((ROOT/'.runtime/source-adoption/root-collection.json').read_text())['nodes']
def normalized_root(k):return re.sub(r'(tests/test_template_candidate.py::test_old_identity_material_and_result_fields_are_forbidden\[case_id-)[0-9a-f-]{36}(\])',r'\1<import-uuid>\2',k)
assert Counter(map(normalized_root,col))==Counter(map(normalized_root,rootrun))
same=json.loads((ROOT/'.runtime/source-adoption/delta-4c163fe-same-run-collection.json').read_text());assert Counter(same)==Counter(delta.keys())
merged={**rootrun,**hold,**delta};modules=set(json.loads((ROOT/'.runtime/source-adoption/root-collection.json').read_text())['modules'])
current52={k:v for k,v in merged.items() if k.split('::',1)[0] in modules}
assert len(modules)==52 and Counter(current52.values())=={'PASS':1689},Counter(current52.values())
assert Counter(merged.values())=={'PASS':1926,'SKIP':8}
failures={k for k,v in rootrun.items() if v=='FAIL'};assert all(merged[k]=='PASS' for k in failures)
coverage=json.loads((ROOT/'.runtime/source-adoption/final-coverage.json').read_text());assert coverage['current_52_module_test_set_outcomes_across_windows']==dict(Counter(current52.values())) and coverage['expanded_unique_outcomes_across_windows']==dict(Counter(merged.values()))
assert coverage['source_sha']==freeze and coverage['business_execution_sha'].startswith('6b8da028')
ind=json.loads((ROOT/'.runtime/source-adoption-independent/freeze-4c163fe-result.json').read_text());assert ind['tested_sha']==freeze and ind['tests']==20 and ind['failures']==ind['errors']==ind['skipped']==0 and ind['junit_seconds']==105.64
assert Counter(junit('.runtime/source-adoption-independent/freeze-4c163fe-junit.xml').values())=={'PASS':20}
tracked=subprocess.check_output(['git','ls-files','src','tests','scripts','pyproject.toml'],cwd=ROOT,text=True).splitlines()
current_source_drift=[p for p in tracked if (ROOT/p).read_bytes()!=subprocess.check_output(['git','show',freeze+':'+p],cwd=ROOT)]
assert len(tracked)==587 and not current_source_drift
report={'status':'PASS','scope':'Independent read-only archive, redaction, source identity, and cross-window coverage audit; bounded Linux engineering evidence only','source_sha':freeze,'index_sha256':sha(index_path.read_bytes()),'checks':dict(checks),'redactions':dict(redactions),'raw_hash_and_size_matches':214,'export_hash_and_size_matches':214,'independently_reconstructed_exports':214,'original_export_structures_and_testcase_statuses_preserved':True,'known_private_session_residuals':all_private_residuals,'suspicious_exact_43_character_token_files':suspicious_tokens,'unindexed_supplemental_files':extras,'root_first_window':dict(Counter(rootrun.values())),'root_first_window_total':len(rootrun),'root_uuid_normalization':'Only original template_candidate forbidden case_id import UUID; full parameters otherwise preserved','root_diagnostic_same_invocation_collection_exact':True,'hold_followup':dict(Counter(hold.values())),'final_diagnostic_followup':dict(Counter(delta.values())),'current_52_modules_multiwindow_outcomes':dict(Counter(current52.values())),'expanded_multiwindow_outcomes':dict(Counter(merged.values())),'single_window_all_pass_claim':False,'all_27_original_failed_nodes_have_separate_pass_outcome':True,'final_independent_tests':{'PASS':20,'junit_seconds':105.64},'tracked_source_paths':587,'current_source_byte_drift':current_source_drift,'shared_runtime_note':'Inherited private redaction sets and compatibility/UI/HOLD latest snapshots are not exclusive per-window evidence. Private sets excluded; original test windows and failures retained.','limitations':['Windows/native PowerShell and real browser not executed','Formal AT/general F3 and real models/production not signed off','Cross-window 1689 coverage is not a single 1689-PASS run','This audit does not claim every historical artifact was executed on final reference SHA'],'remaining_blockers':[], 'audit_self_check_retries': [{'path':'.runtime/source-adoption-review/archive-independent-audit-first.log','classification':'AUDITOR_ASSUMED_CLASSNAME_ON_EVERY_HISTORICAL_TESTCASE; switched to optional-attribute equality without weakening XML structure/status checks'}, {'path':'.runtime/source-adoption-review/archive-independent-audit-metadata-update.log','classification':'README_AND_GITATTRIBUTES_ADDED_DURING_AUDIT; independently checked metadata declaration and exact -text attribute then accepted explicit supplemental paths'}, {'path':'.runtime/source-adoption-review/archive-independent-audit-counter-oracle.log','classification':'AUDITOR_USED_COUNTER_ON_DICT_VALUES_INSTEAD_OF_TEST_KEYS; direct independent comparison already showed zero missing/extra; corrected key multiset comparison'}]}
for retry in report['audit_self_check_retries']:
 data=(ROOT/retry['path']).read_bytes();retry.update(sha256=sha(data),bytes=len(data))
(ROOT/'.runtime/source-adoption-review/archive-independent-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('limitations','shared_runtime_note')},ensure_ascii=False,indent=2))
