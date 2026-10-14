import hashlib,json,pathlib,re
B=pathlib.Path('/workspace/ParkWeave/docs/F2/evidence/service-capability-selection-20261014'); O=pathlib.Path(__file__).parent
D=json.loads((B/'export-index.json').read_bytes()); found=[]; values=set()
for e in D['entries']:
 for side,p in [('raw',pathlib.Path(e['original'])),('export',B/e['export'])]:
  t=p.read_text(errors='replace')
  for i,line in enumerate(t.splitlines(),1):
   m=re.fullmatch(r"token = '([A-Za-z0-9_-]{43})'",line)
   if m:
    value=m.group(1);values.add(value);found.append({'export':e['export'],'original':e['original'],'side':side,'line':i,'value_sha256':hashlib.sha256(value.encode()).hexdigest()})
assert len(values)==8
assert len(found)==32
assert {x['export'] for x in found}=={'candidates/first.log','candidates/first.xml'}
r={'status':'FAIL','finding':'Eight actual ephemeral SYNTHETIC fixture authentication session values in retained first failing candidate pytest traceback; export zero-session claim false. No source/test failure evidence should be deleted. Original raw files must remain intact; any future sanitized exports require exact-value replacement and new manifest recording actual 8 values / 16 exported occurrences.','confirmed_by_context':"tests/test_service_selection_candidates.py:42 passes f[2]['fixture-a'] as second sc.generate argument; traceback renders token argument in generate(store,token,id,key,data,*,catalog,planner).",'distinct_actual_fixture_session_values':len(values),'occurrences_export':sum(x['side']=='export' for x in found),'occurrences_raw':sum(x['side']=='raw' for x in found),'locations':found,'actual_values_not_in_report':True,'old_NOT_RUN_untouched':True}
(O/'confirmed-session-findings.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(r,ensure_ascii=False,indent=2))
raise SystemExit(1)
