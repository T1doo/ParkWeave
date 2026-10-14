import collections, datetime, hashlib, json, pathlib, re, sys
BASE=pathlib.Path('/workspace/ParkWeave/docs/F2/evidence/service-capability-selection-20261014')
OLD=pathlib.Path('/workspace/ParkWeave/docs/F2/ServiceCapabilitySelectionArchiveAudit-20261014.json')
OUT=pathlib.Path(__file__).parent
sha=lambda b:hashlib.sha256(b).hexdigest()
index_before=(BASE/'export-index.json').read_bytes(); old_before=OLD.read_bytes(); d=json.loads(index_before)
errors=[]; entries=[]; names=[]; originals=[]; token43=collections.Counter(); auth_clues=[]; sensitive_values=[]; total_bytes=0
# Fixture secrets use token_urlsafe(32), producing 43 URL-safe characters. Scan all
# bytes independently of the exporter's claimed zero values; keep only identifiers
# and source placeholders as classified false positives, never print secret values.
pattern=re.compile(rb'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])')
sensitive_key=re.compile(r'^(?:session|session_token|session_value|access_token|refresh_token|authorization|api_key|password)$',re.I)
def walk(v, path, file):
 if isinstance(v,dict):
  for k,x in v.items():
   if sensitive_key.fullmatch(k) and isinstance(x,str) and x:
    sensitive_values.append({'file':file,'json_path':path+'/'+k,'length':len(x),'sha256':sha(x.encode())})
   walk(x,path+'/'+k,file)
 elif isinstance(v,list):
  for i,x in enumerate(v):walk(x,path+'/'+str(i),file)
for number,e in enumerate(d['entries'],1):
 name=e['export']; names.append(name); originals.append(e['original']); rel=pathlib.PurePosixPath(name)
 if rel.is_absolute() or '..' in rel.parts or str(rel)!=name: errors.append([name,'unsafe path'])
 target=BASE/name
 if target.is_symlink() or not target.resolve().is_relative_to(BASE.resolve()):errors.append([name,'symlink/escape'])
 try: raw=pathlib.Path(e['original']).read_bytes(); exported=target.read_bytes()
 except OSError as ex:errors.append([name,'read failed',str(ex)]);continue
 checks={'raw_sha256':sha(raw)==e['raw_sha256'],'export_sha256':sha(exported)==e['export_sha256'],'raw_bytes':len(raw)==e['raw_bytes'],'export_bytes':len(exported)==e['export_bytes'],'byte_equal':raw==exported,'zero_replacements':e['redaction_occurrences']==0}
 if not all(checks.values()): errors.append([name,checks])
 # Both sides separately scanned; identical bytes do not establish absence of leaks.
 for label,data in [('raw',raw),('export',exported)]:
  for m in pattern.finditer(data):token43[m.group().decode()]+=1
  for i,line in enumerate(data.splitlines(),1):
   if re.search(rb'Bearer\s+|[\"\']session(?:_token|_value)?[\"\']\s*[:=]',line,re.I):
    # Do not store candidate secret text. These findings require source-context review.
    auth_clues.append({'file':name,'side':label,'line':i,'line_sha256':sha(line)})
  try:walk(json.loads(data),'',name+':'+label)
  except (ValueError,UnicodeDecodeError):pass
 total_bytes+=len(exported)
 entries.append({'export':name,'sha256':sha(exported),'bytes':len(exported),'checks':checks})
 print(f'{number:03d} {name}: '+('PASS' if all(checks.values()) else 'FAIL'))
# Observed 43-character matches are only test/module filenames. No secret-shaped
# opaque value is whitelisted; new/unclassified candidates fail closed.
classified=[]; unclassified=[]
for value,count in sorted(token43.items()):
 is_identifier=value.startswith(('test_','service_')) and bool(re.fullmatch('[a-z_]+',value))
 (classified if is_identifier else unclassified).append({'identifier':value if is_identifier else None,'sha256':sha(value.encode()),'occurrences_both_sides':count})
actual_files={str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_file() and p.name!='export-index.json'}
unindexed=sorted(actual_files-set(names)); missing=sorted(set(names)-actual_files)
if len(names)!=518 or d['exports']!=518:errors.append(['count',len(names),d['exports']])
if len(set(names))!=518 or len(set(originals))!=518:errors.append(['duplicate paths'])
if unindexed or missing:errors.append(['directory set mismatch',unindexed,missing])
if d['session_values']!=0 or d['literal_replacements']!=0 or sensitive_values or unclassified:errors.append(['session/redaction claim not independently clean'])
# Four clues (raw+export twice) are literal source snippets in the retained failing
# actual NodeVM log/XML: SYNTHETIC_NODE_API_SESSION placeholder and runtime fixture
# reference concatenation; neither contains an actual session value.
expected_clues={('actual/nodevm-final-historical-recovery.log',37),('actual/nodevm-final-historical-recovery.log',38),('actual/nodevm-final-historical-recovery.xml',33),('actual/nodevm-final-historical-recovery.xml',34)}
if {(x['file'],x['line']) for x in auth_clues}!=expected_clues or len(auth_clues)!=8:errors.append(['unreviewed authorization clues',auth_clues])
if OLD.read_bytes()!=old_before:errors.append(['old NOT RUN file changed'])
if (BASE/'export-index.json').read_bytes()!=index_before:errors.append(['index changed during audit'])
# Re-read every raw/export to detect a live changing file while audited.
for e in d['entries']:
 try:
  if sha(pathlib.Path(e['original']).read_bytes())!=e['raw_sha256'] or sha((BASE/e['export']).read_bytes())!=e['export_sha256']:errors.append([e['export'],'end stability failed'])
 except OSError as ex:errors.append([e['export'],'end reread failed',str(ex)])
r={'status':'FAIL' if errors else 'PASS','run_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'audit_kind':'new independent read-only audit; historical NOT RUN unchanged','index_sha256':sha(index_before),'previous_audit_sha256':sha(old_before),'previous_independent_status':json.loads(old_before)['independent_archive_audit']['status'],'exports':len(entries),'raw_export_byte_equality':sum(x['checks']['byte_equal'] for x in entries),'total_export_bytes':total_bytes,'unique_export_paths':len(set(names)),'unique_original_paths':len(set(originals)),'unindexed_files':unindexed,'missing_files':missing,'detected_actual_session_values':len(sensitive_values)+len(unclassified),'literal_replacements':sum(e['redaction_occurrences'] for e in d['entries']),'sensitive_json_values':sensitive_values,'unclassified_43char_values':unclassified,'classified_identifier_43char_values':classified,'authorization_source_clues':auth_clues,'authorization_review':'Only literal SYNTHETIC_NODE_API_SESSION placeholder and f[2][fixture-c] runtime variable concatenation in retained failing source trace, no actual session values. Both raw and export scanned. Token shape scan plus sensitive JSON keys and Bearer/session literal patterns; not a universal secret detector.','old_record_byte_unchanged':OLD.read_bytes()==old_before,'index_byte_unchanged':(BASE/'export-index.json').read_bytes()==index_before,'end_stability_check':not any('end ' in str(x) for x in errors),'errors':errors,'entries':entries}
(OUT/'audit518-result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in r.items() if k not in ('entries','classified_identifier_43char_values','authorization_source_clues')},ensure_ascii=False,indent=2))
sys.exit(bool(errors))
