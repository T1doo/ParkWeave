from pathlib import Path
import hashlib,json,re,xml.etree.ElementTree as ET
import parkweave.template_migration as migration
import parkweave.template_upgrade as upgrade
import parkweave.service_case_steps as steps

root=Path.cwd(); runtime=root/'.runtime/template-structure-tests-20261015'
before=json.loads((runtime/'final60-81-source-before.json').read_text())
files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'src').rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
assert files==before['files']
tests={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in before['test_files']}
assert tests==before['test_files']
loaded={m.__name__:m.__file__ for m in (migration,upgrade,steps)}
assert all(str(root/'src') in p for p in loaded.values())
suite=ET.parse(runtime/'final60-81.xml').getroot().find('testsuite')
statistics={k:int(suite.attrib[k]) for k in ('tests','errors','failures','skipped')}
statistics['seconds']=float(suite.attrib['time'])
statistics['passed']=statistics['tests']-statistics['errors']-statistics['failures']-statistics['skipped']
assert statistics['tests']==81 and statistics['passed']==81
assert (runtime/'final60-81.exit').read_text().strip()=='0'
result=dict(source_sha=before['source_sha'],scope='Linux owned PostgreSQL + original process-internal ASGI, no browser or real model',statistics=statistics,source_files=files,test_files=tests,loaded_modules=loaded,module_path_probe='post-run same venv and explicit PYTHONPATH as native pytest command',drift_count=0,source_file_count=len(files),acceptance_eligible=True)
(runtime/'final60-81-source-after.json').write_text(json.dumps(result,indent=2)+'\n')
classifications={
'baseline-red':'TEST_INPUT_ERROR_catalog_snapshot_key',
'baseline-scope-red':'REJECTED_UNSAFE_INITIAL_SCOPE_ORACLE_no_original_Case_goal',
'six-goal-baseline-red':'REAL_SUPPORTED_SCOPE_FEATURE_GAP',
'actual-oracle-baseline':'REAL_SUPPORTED_SCOPE_FEATURE_GAP',
'even-fixture':'TEST_FIXTURE_PREREQUISITE_ERROR_missing_original_local_adoption',
'even-fixture-corrected':'DEVELOPMENT_FIXTURE_PASS',
'window1':'TEST_ORACLE_ERROR_original_DENIED_audit_contract',
'window2':'DEVELOPMENT_PASS',
'window2-proof-types':'DEVELOPMENT_PASS',
'final-78':'SUPERSEDED_b8_76_actual_tests_not_78_filename',
'final60-81':'FINAL_SAME_SOURCE_ACCEPTANCE_CANDIDATE'}
ledger=[]
for xml in sorted(runtime.glob('*.xml')):
    parsed=ET.parse(xml).getroot().find('testsuite')
    counts={k:int(parsed.attrib[k]) for k in ('tests','errors','failures','skipped')}
    counts['passed']=counts['tests']-counts['errors']-counts['failures']-counts['skipped']
    ledger.append(dict(name=xml.stem,classification=classifications.get(xml.stem,'UNCLASSIFIED'),statistics=counts,seconds=float(parsed.attrib['time']),exit_code=int(xml.with_suffix('.exit').read_text().strip())))
(runtime/'outcome-ledger.json').write_text(json.dumps(dict(windows=ledger,do_not_sum_windows=True,system_python_manifest_error='post-window2-manifest-error.log; CLI exit1, not pytest product result'),indent=2)+'\n')
pools=list((root/'.runtime').glob('*/redaction-values.private.json'));values=set()
for path in pools:values.update(json.loads(path.read_text()))
seen=set()
for path in runtime.glob('*.log'):seen.update(re.findall(r"['\"]([A-Za-z0-9_-]{43})['\"]",path.read_text()))
coverage=dict(candidate_exact_session_literals=len(seen),verified_pool_matches=len(seen&values),unmatched_candidates=len(seen-values),pool_paths=[str(p.relative_to(root)) for p in pools],not_a_replacement_for_independent_semantic_archive_audit=True)
(runtime/'private-pool-coverage-final.json').write_text(json.dumps(coverage,indent=2)+'\n')
print(json.dumps(dict(source_sha=result['source_sha'],statistics=statistics,source_file_count=len(files),drift_count=0,loaded_modules=loaded,private_literal_coverage=coverage),indent=2))
