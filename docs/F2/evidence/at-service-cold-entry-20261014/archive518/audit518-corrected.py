import collections,hashlib,json,pathlib,re,sys,datetime
B=pathlib.Path('/workspace/ParkWeave/docs/F2/evidence/service-capability-selection-20261014'); O=pathlib.Path(__file__).parent; OLD=pathlib.Path('/workspace/ParkWeave/docs/F2/ServiceCapabilitySelectionArchiveAudit-20261014.json')
H=lambda x:hashlib.sha256(x).hexdigest()
idx=(B/'export-index.json').read_bytes(); d=json.loads(idx); old=OLD.read_bytes(); prior=json.loads((O/'audit518-result.json').read_bytes()); confirmed=json.loads((O/'confirmed-session-findings.json').read_bytes()); allowed={x['value_sha256'] for x in confirmed['locations']}; errors=[]; sessions=set(); rows=[]; total=0; paths=[]; originals=[]; opaque=[]
for e in d['entries']:
 if e['export'] in {'candidates/first.log','candidates/first.xml'}:
  for m in re.finditer(rb"(?m)^token = '([A-Za-z0-9_-]{43})'$",pathlib.Path(e['original']).read_bytes()):
   value=m.group(1)
   if H(value) not in allowed:errors.append([e['export'],'unrecognized raw session hash'])
   sessions.add(value)
if len(sessions)!=8 or {H(v) for v in sessions}!=allowed:errors.append(['session set mismatch'])
prior_entries={e['export']:e for e in prior['entries']}
for n,e in enumerate(d['entries'],1):
 name=e['export']; paths.append(name); originals.append(e['original']); p=pathlib.PurePosixPath(name); export_path=B/name
 if p.is_absolute() or '..' in p.parts or str(p)!=name or export_path.is_symlink() or not export_path.resolve().is_relative_to(B.resolve()):errors.append([name,'unsafe export'])
 try:raw=pathlib.Path(e['original']).read_bytes(); out=export_path.read_bytes()
 except OSError as ex:errors.append([name,str(ex)]);continue
 expected=raw; occurrences=0
 for v in sorted(sessions):
  occurrences+=expected.count(v); expected=expected.replace(v,b'[REDACTED_SYNTHETIC_FIXTURE_SESSION]')
 total+=occurrences
 checks={'raw_sha':H(raw)==e['raw_sha256'],'export_sha':H(out)==e['export_sha256'],'raw_length':len(raw)==e['raw_bytes'],'export_length':len(out)==e['export_bytes'],'exact_allowed_transform':expected==out,'replacement_count':occurrences==e['redaction_occurrences'],'raw_same_as_original_audit':H(raw)==prior_entries[name]['sha256'],'no_actual_session_residue':not any(v in out for v in sessions)}
 if occurrences and name not in {'candidates/first.log','candidates/first.xml'}:errors.append([name,'unexpected session location'])
 if not all(checks.values()):errors.append([name,checks])
 for m in re.finditer(rb'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])',out):
  v=m.group()
  if not (v.startswith(b'test_') and re.fullmatch(rb'[a-z_]+',v)):opaque.append({'file':name,'sha256':H(v)})
 rows.append({'export':name,'raw_sha256':H(raw),'export_sha256':H(out),'raw_bytes':len(raw),'export_bytes':len(out),'replacements':occurrences,'checks':checks})
 print(f'{n:03} {name}: '+('PASS' if all(checks.values()) else 'FAIL'))
actual={str(p.relative_to(B)) for p in B.rglob('*') if p.is_file() and p.name!='export-index.json'}
if len(paths)!=518 or len(set(paths))!=518 or len(set(originals))!=518 or actual!=set(paths):errors.append(['518 unique/full directory mismatch'])
if d['exports']!=518 or d['session_values']!=8 or d['literal_replacements']!=16 or total!=16:errors.append(['8/16 count mismatch'])
if opaque:errors.append(['unclassified exported token-shaped values',opaque])
# Original audit record remains exactly the same as at the original failed run.
if H(old)!=prior['previous_audit_sha256'] or OLD.read_bytes()!=old:errors.append(['historical NOT RUN modified'])
if (B/'export-index.json').read_bytes()!=idx:errors.append(['index changed during audit'])
for e in d['entries']:
 if H(pathlib.Path(e['original']).read_bytes())!=e['raw_sha256'] or H((B/e['export']).read_bytes())!=e['export_sha256']:errors.append([e['export'],'end stability failed'])
r={'status':'FAIL' if errors else 'PASS','run_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'index_sha256':H(idx),'original_failed_audit_preserved':(O/'audit518.exit').read_text().strip()=='1','historical_NOT_RUN_sha256':H(old),'historical_NOT_RUN_unchanged':H(old)==prior['previous_audit_sha256'],'exports':len(rows),'unique_export_paths':len(set(paths)),'unique_original_paths':len(set(originals)),'raw_hashes_unchanged_from_first_independent_audit':sum(x['checks']['raw_same_as_original_audit'] for x in rows),'exact_allowed_transform_pass':sum(x['checks']['exact_allowed_transform'] for x in rows),'actual_session_values':len(sessions),'exact_export_replacements':total,'changed_exports':[x['export'] for x in rows if x['replacements']],'residual_actual_sessions':sum(not x['checks']['no_actual_session_residue'] for x in rows),'unclassified_43char_values':opaque,'errors':errors,'entries':rows}
(O/'audit518-corrected-result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='entries'},ensure_ascii=False,indent=2));sys.exit(bool(errors))
