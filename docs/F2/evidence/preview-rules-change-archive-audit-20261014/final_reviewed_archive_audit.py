from pathlib import Path,PurePosixPath
import subprocess,tarfile,io,xml.etree.ElementTree as ET
import json,re,hashlib,datetime,sys
O=Path(__file__).parent
B=Path('/workspace/ParkWeave/docs/F2/evidence/preview-rules-change-20261014')
EXPECTED_SOURCE=sys.argv[1] if len(sys.argv)>1 else '1953cd95cd7174d76f0677406df948f81e0da518'
H=lambda b:hashlib.sha256(b).hexdigest();pattern=re.compile(rb'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])')
idx=(B/'export-index.json').read_bytes();d=json.loads(idx);errors=[];rows=[];paths=[];originals=[];opaque=[];auth=[];sensitive=[];failures=[];tokens={};candidates={}
# Independently confirmed actual fixture sessions: A explicit token traceback,
# UI fixture tuple shortened dict repr. Values read only from original traces;
# neither actual value is persisted or printed by this script.
EXPECTED_SESSIONS={'90e4c29de8de8b2ab4900d6964faa33e414b9126715d0608679bc9de730f20b0','82fcde5097dbeca2f15541243a44740a35698c8e05f882e62403e39e097b90d7'}
# Individually reviewed semantic identifier contexts in preliminary independent
# scan. Any additional value, even if word-like, requires independent review.
IDENTIFIERS={
'3549e75dc22e122ce2179f8b733040e2f0e34bf224ffd609bcb08395c3b4d9d2':'test module in source hash manifests',
'e0560946c372355952263eb6cd7ca49fde66d8dccaa325f5ea54039edea3a3df':'pytest readiness function name',
'ba70a28b17e176843ba851ceb0528d42c49f33c93a7c11338e3d77f17efa9a5b':'pytest resource alternative function name',
'68c60826337b405c328b9a4a45963dcfa7b2c0853e9cfff583897c43f53411fd':'pytest preview/rules/read-only UI function name',
'f925bbc79b48a2150bfb8a1174fac755c9f0aeb9d6b747bfd3746a5b1c252e3e':'fixed uppercase service metadata scope',
'82f34c5efd38bf2c7162d717b0aaa6dcea4153822122b00efad0cbbff9a454a5':'fixed uppercase cancellation reason identifier',
'c2505a39426457dc72e13cd096bb9925d03f32e7b2959f446491b01fa13aeb98':'pytest service selection function name',
'3e3e24a7731c51338b47593240fb46f57a4e905d13de6bed2fe6e9c4dee9321e':'pytest entry isolation parameter name'}
IDENTIFIERS.update({'155d5cfe5c3605cf5c5cdb5472a36bf016681b79588996ab31c5c7fd186b7b88':'remote refs/heads/dev branch basename','09e884039e4132393e1bdcb98217c2c8abfc3304c6e7859a7510a74ae02c9c59':'remote refs/heads/dev branch basename','1d34e7f18e4e21e5121c105c45430192d4d2d6cf448c6b21bec7094019409650':'review JSON boolean group key for baseline byte comparison'})
initial=(O/'final-archive-result.json').read_bytes()
initial_result=json.loads(initial)
if initial_result['errors']!=[['unreviewed opaque candidates',12]]:errors.append('unexpected first-run issue')
for e in d['entries']:
 raw=Path(e['original']).read_bytes()
 for m in pattern.finditer(raw):
  if H(m.group()) in EXPECTED_SESSIONS:tokens[H(m.group())]=m.group()
if set(tokens)!=EXPECTED_SESSIONS:errors.append(['actual session set not both observed',list(tokens)])
for n,e in enumerate(d['entries'],1):
 name=e['export'];paths.append(name);originals.append(e['original']);rel=PurePosixPath(name);p=B/name
 if rel.is_absolute() or '..' in rel.parts or str(rel)!=name or p.is_symlink() or not p.resolve().is_relative_to(B.resolve()):errors.append([name,'unsafe export'])
 raw=Path(e['original']).read_bytes();out=p.read_bytes();expected=raw;counts={}
 for h,v in sorted(tokens.items()):counts[h]=expected.count(v);expected=expected.replace(v,b'[REDACTED_SYNTHETIC_FIXTURE_SESSION]')
 replacements=sum(counts.values())
 checks={'raw_hash':H(raw)==e['raw_sha256'],'export_hash':H(out)==e['export_sha256'],'raw_length':len(raw)==e['raw_bytes'],'export_length':len(out)==e['export_bytes'],'exact_allowed_transform':expected==out,'replacement_count':replacements==e['redaction_occurrences'],'no_actual_session_residue':not any(v in out for v in tokens.values())}
 if not all(checks.values()):errors.append([name,checks])
 for side,data in [('raw',raw),('export',out)]:
  for m in pattern.finditer(data):
   v=m.group();h=H(v);line=data[:m.start()].count(b'\n')+1
   candidates.setdefault(h,{'sha256':h,'classification':'actual fixture session' if h in EXPECTED_SESSIONS else IDENTIFIERS.get(h,'UNKNOWN'),'occurrences':[]})['occurrences'].append({'export':name,'side':side,'line':line})
   if h not in EXPECTED_SESSIONS and h not in IDENTIFIERS:
    opaque.append({'export':name,'side':side,'line':line,'sha256':h,'masked_context':pattern.sub(b'<43CHAR_CANDIDATE>',data[max(0,m.start()-80):m.end()+80]).decode(errors='replace')})
   if side=='export' and h in EXPECTED_SESSIONS:errors.append([name,'actual session exported',h])
  for i,line in enumerate(data.splitlines(),1):
   if re.search(rb"(?:Bearer\s+|^token\s*=|[\"\'](?:session|session_token|session_value)[\"\']\s*[:=])",line,re.I):auth.append({'export':name,'side':side,'line':i,'context_sha256':H(line),'masked_context':pattern.sub(b'<43CHAR_CANDIDATE>',line).decode(errors='replace')[:500]})
  def walk(x,path=''):
   if isinstance(x,dict):
    for k,v in x.items():
     if re.fullmatch(r'(session|session_token|session_value|access_token|refresh_token|authorization|api_key|password)',k,re.I) and isinstance(v,str) and v:sensitive.append({'export':name,'side':side,'path':path+'/'+k,'value_sha256':H(v.encode()),'length':len(v)})
     walk(v,path+'/'+k)
   elif isinstance(x,list):
    for i,v in enumerate(x):walk(v,path+'/'+str(i))
  try:walk(json.loads(data))
  except (ValueError,UnicodeDecodeError):pass
 if name.endswith('.exit') and out.strip() not in (b'',b'0'):failures.append({'export':name,'exit':out.decode(errors='replace').strip()})
 rows.append({'export':name,'original':e['original'],'raw_sha256':H(raw),'export_sha256':H(out),'raw_bytes':len(raw),'export_bytes':len(out),'replacements':replacements,'session_replacement_counts':counts,'checks':checks});print(f'{n:03d} {name}: '+('PASS' if all(checks.values()) else 'FAIL'))
actual={str(p.relative_to(B)) for p in B.rglob('*') if p.is_file() and p.name!='export-index.json'}
if len(rows)!=d['exports'] or len(set(paths))!=len(rows) or len(set(originals))!=len(rows) or actual!=set(paths):errors.append(['count/path/directory mismatch'])
if d['source_sha']!=EXPECTED_SOURCE:errors.append(['wrong source',d['source_sha'],EXPECTED_SOURCE])
if d['session_values']!=len(tokens) or d['literal_replacements']!=sum(x['replacements'] for x in rows):errors.append(['session/replacement count mismatch'])
if opaque:errors.append(['unreviewed opaque candidates',len(opaque)])
if sensitive:errors.append(['sensitive JSON value clues require review',len(sensitive)])
if (B/'export-index.json').read_bytes()!=idx:errors.append(['index changed during audit'])
for e in d['entries']:
 if H(Path(e['original']).read_bytes())!=e['raw_sha256'] or H((B/e['export']).read_bytes())!=e['export_sha256']:errors.append([e['export'],'end stability failed'])

allowed_auth={"token = '<43CHAR_CANDIDATE>'", "token = '[REDACTED_SYNTHETIC_FIXTURE_SESSION]'", "                    assert message['type']=='request';options=message['options'];assert options['headers']['Authorization']=='Bearer SYNTHETIC_NODE_API_SESSION'", "                    h={**options['headers'],'Authorization':'Bearer '+f[2][actor]}"}
if {x['masked_context'] for x in auth}!=allowed_auth:errors.append('unknown authorization clue')
# Reconcile actual XML and separate source manifests, not sums across windows.
windows=[]
for prefix,expected in [('root/final',{'tests':659,'failures':0,'errors':0,'skipped':0}),('review/final5e339-frozen-related',{'tests':481,'failures':0,'errors':0,'skipped':0}),('root/source1953-first-final',{'tests':659,'failures':21,'errors':0,'skipped':0}),('root/collection-first-final',{'tests':6,'failures':0,'errors':6,'skipped':0})]:
 tree=ET.fromstring((B/(prefix+'.xml')).read_bytes());suites=list(tree.iter('testsuite'));counts={k:sum(int(t.attrib.get(k,0)) for t in suites) for k in expected}
 exitvalue=(B/(prefix+'.exit')).read_text().strip()
 windows.append({'prefix':prefix,'xml_counts':counts,'passed':counts['tests']-counts['failures']-counts['errors']-counts['skipped'],'exit':exitvalue})
 if counts!=expected:errors.append([prefix,'xml counts mismatch'])
 if exitvalue!=('0' if counts['errors']==counts['failures']==0 else '2' if counts['errors'] else '1'):errors.append([prefix,'exit mismatch'])
archive=subprocess.check_output(['git','archive',EXPECTED_SOURCE,'src','tests','scripts','pyproject.toml'],cwd='/workspace/ParkWeave')
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:commit_files={m.name:H(tar.extractfile(m).read()) for m in tar if m.isfile()}
manifest_checks=[]
for prefix,sep,count in [('root/final','-',566),('review/final5e339-frozen-related','.',567)]:
 before=json.loads((B/(prefix+sep+'before.json')).read_bytes());after=json.loads((B/(prefix+sep+'after.json')).read_bytes());drift=before!=after;bad=[k for k,v in before.items() if commit_files.get(k)!=v]
 manifest_checks.append({'prefix':prefix,'files':len(before),'expected_files':count,'before_after_equal':not drift,'different_from_commit':bad})
 if len(before)!=count or drift or bad:errors.append([prefix,'manifest failure'])
rootwindow=json.loads((B/'root/final-window.json').read_bytes());reviewwindow=json.loads((B/'review/final5e339-frozen-related.window.json').read_bytes())
if rootwindow['source_sha']!=EXPECTED_SOURCE or reviewwindow['source_sha']!=EXPECTED_SOURCE:errors.append('window source mismatch')
root_modules=[x for x in rootwindow['argv'] if x.startswith('tests/')]; review_modules=reviewwindow['modules']
if len(root_modules)!=30 or len(review_modules)!=24:errors.append('module count mismatch')
loaded=json.loads((B/'review/final5e339-loaded.json').read_bytes())['paths'];loaded_inside=all(str(x).startswith('/workspace/parkweave-preview-rules-review-20261014/src/parkweave/') for x in loaded.values())
if len(loaded)!=74 or not loaded_inside:errors.append('independent loaded module isolation mismatch')
report=Path('/workspace/ParkWeave/docs/F2/PreviewRulesChangeDelivery-20261014.md').read_text()
report_checks={'full_source':EXPECTED_SOURCE in report,'limited_AT':'未提升原AT状态' in report,'root659':'659 PASS' in report,'independent481':'481 PASS' in report,'red638_21':'638 PASS / 21 FAIL' in report,'collection6ERROR':'6 ERROR/exit2' in report,'old_windows_not_summed':'不相加' in report,'qualification_unknown':'qualification_truth始终UNKNOWN' in report,'formal_governance_false':'formal_review/business_publication均false' in report,'unverified_platforms':'Windows、浏览器、部署、生产迁移NOT RUN' in report}
if not all(report_checks.values()):errors.append(['report claims',report_checks])

r={'status':'FAIL' if errors else 'PASS','run_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_sha':d['source_sha'],'index_sha256':H(idx),'exports':len(rows),'unique_exports':len(set(paths)),'unique_originals':len(set(originals)),'exact_allowed_transform_count':sum(x['checks']['exact_allowed_transform'] for x in rows),'actual_fixture_sessions':len(tokens),'exact_replacements':sum(x['replacements'] for x in rows),'replacement_exports':[x['export'] for x in rows if x['replacements']],'unindexed_files':sorted(actual-set(paths)),'missing_files':sorted(set(paths)-actual),'all_43char_candidates':list(candidates.values()),'unreviewed_opaque_candidates':opaque,'sensitive_JSON_values':sensitive,'authorization_clues':auth,'retained_nonzero_exit_files':failures,'all_raw_export_end_hashes_rechecked':True,'prior_conservative_exit1_preserved_sha256':H(initial),'window_XML_reconciliation':windows,'source_manifest_checks':manifest_checks,'root_module_count':len(root_modules),'independent_module_count':len(review_modules),'independent_loaded_modules':len(loaded),'independent_loaded_inside_private_tree':loaded_inside,'report_scope_checks':report_checks,'limitations':'Archive byte/context audit only; not universal secret detection or rerun of product tests. Raw actual sessions are read only from traceback in memory and never persisted by this audit. Historical failure artifacts retained.','errors':errors,'entries':rows}
(O/'final-reviewed-archive-result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k not in ('entries','all_43char_candidates','authorization_clues')},ensure_ascii=False,indent=2));sys.exit(bool(errors))
