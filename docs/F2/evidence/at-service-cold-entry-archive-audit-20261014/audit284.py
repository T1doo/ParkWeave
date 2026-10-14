import pathlib,json,re,hashlib,sys,datetime,collections
B=pathlib.Path('/workspace/ParkWeave/docs/F2/evidence/at-service-cold-entry-20261014');O=pathlib.Path(__file__).parent;H=lambda b:hashlib.sha256(b).hexdigest();index=(B/'export-index.json').read_bytes();d=json.loads(index);errors=[];rows=[];paths=[];originals=[];candidates={};auth=[];sensitive=[];failures=[]
pattern=re.compile(rb'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])')
# Metadata hashes, trace test identifiers and source snippets are reviewed by
# context; no opaque 43-character value is accepted merely for being in a log.
for n,e in enumerate(d['entries'],1):
 name=e['export'];paths.append(name);originals.append(e['original']);p=B/name;r=pathlib.PurePosixPath(name)
 if r.is_absolute() or '..' in r.parts or str(r)!=name or p.is_symlink() or not p.resolve().is_relative_to(B.resolve()):errors.append([name,'unsafe path'])
 try:raw=pathlib.Path(e['original']).read_bytes();out=p.read_bytes()
 except OSError as ex:errors.append([name,str(ex)]);continue
 checks={'raw_sha':H(raw)==e['raw_sha256'],'export_sha':H(out)==e['export_sha256'],'raw_bytes':len(raw)==e['raw_bytes'],'export_bytes':len(out)==e['export_bytes'],'byte_equal':raw==out,'zero_replacements':e['redaction_occurrences']==0}
 if not all(checks.values()):errors.append([name,checks])
 for side,data in [('raw',raw),('export',out)]:
  for m in pattern.finditer(data):
   value=m.group();key=H(value);rec=candidates.setdefault(key,{'sha256':key,'is_plain_test_identifier':bool(value.startswith(b'test_') and re.fullmatch(rb'[a-z_]+',value)),'length':len(value),'locations':[]})
   start=data.rfind(b'\n',0,m.start())+1;line=data[start:data.find(b'\n',m.end()) if b'\n' in data[m.end():] else len(data)]
   # Full context is hashed, candidate itself never emitted. Plain identifiers
   # can be displayed only once confirmed, preventing accidental secret logging.
   rec['locations'].append({'file':name,'side':side,'line':data[:m.start()].count(b'\n')+1,'context_sha256':H(line),'filename_or_test_context':bool(re.search(rb'(?:tests/|tests\.|name=|testcase|\.py)',line))})
  for i,line in enumerate(data.splitlines(),1):
   if re.search(rb"(?:Bearer\s+|[\"\'](?:session|session_token|session_value)[\"\']\s*[:=]|^token\s*=)",line,re.I):auth.append({'file':name,'side':side,'line':i,'line_sha256':H(line),'masked_context':pattern.sub(b'<43CHAR_VALUE>',line).decode(errors='replace')[:500]})
  def walk(x,path=''):
   if isinstance(x,dict):
    for k,v in x.items():
     if re.fullmatch(r'(session|session_token|session_value|access_token|refresh_token|authorization|api_key|password)',k,re.I) and isinstance(v,str) and v:sensitive.append({'file':name,'side':side,'path':path+'/'+k,'value_sha256':H(v.encode()),'length':len(v)})
     walk(v,path+'/'+k)
   elif isinstance(x,list):
    for i,v in enumerate(x):walk(v,path+'/'+str(i))
  try:walk(json.loads(data))
  except (ValueError,UnicodeDecodeError):pass
 if name.endswith('.exit') and out.strip() not in (b'0',b''):failures.append({'file':name,'exit':out.decode(errors='replace').strip()})
 rows.append({'export':name,'raw_sha256':H(raw),'export_sha256':H(out),'bytes':len(out),'checks':checks});print(f'{n:03d} {name}: '+('PASS' if all(checks.values()) else 'FAIL'))
unknown=[x for x in candidates.values() if not (x['is_plain_test_identifier'] and all(y['filename_or_test_context'] for y in x['locations']))]
actual_files={str(p.relative_to(B)) for p in B.rglob('*') if p.is_file() and p.name!='export-index.json'}
if len(paths)!=284 or len(set(paths))!=284 or len(set(originals))!=284 or actual_files!=set(paths):errors.append(['directory/unique count mismatch'])
if d['exports']!=284 or d['session_values']!=0 or d['literal_replacements']!=0:errors.append(['index totals mismatch'])
if unknown or sensitive:errors.append(['unreviewed session clues',len(unknown),len(sensitive)])
if (B/'export-index.json').read_bytes()!=index:errors.append(['index changed'])
for e in d['entries']:
 if H(pathlib.Path(e['original']).read_bytes())!=e['raw_sha256'] or H((B/e['export']).read_bytes())!=e['export_sha256']:errors.append([e['export'],'end stability failed'])
r={'status':'FAIL' if errors else 'PASS','run_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_sha':d['source_sha'],'index_sha256':H(index),'exports':len(rows),'unique_export_paths':len(set(paths)),'unique_original_paths':len(set(originals)),'raw_export_byte_equality':sum(x['checks']['byte_equal'] for x in rows),'unindexed_files':sorted(actual_files-set(paths)),'missing_files':sorted(set(paths)-actual_files),'actual_session_candidates':unknown,'sensitive_json_values':sensitive,'all_43char_candidates':list(candidates.values()),'authorization_clues_for_context_review':auth,'retained_nonzero_exit_files':failures,'literal_replacements':sum(e['redaction_occurrences'] for e in d['entries']),'errors':errors,'entries':rows}
(O/'audit284-result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n'); print(json.dumps({k:v for k,v in r.items() if k not in ('entries','all_43char_candidates')},ensure_ascii=False,indent=2));sys.exit(bool(errors))
