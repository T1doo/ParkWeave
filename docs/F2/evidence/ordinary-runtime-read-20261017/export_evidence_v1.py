"""Export only this slice; originals stay private. Never overwrite an archive."""
from pathlib import Path
from collections import Counter
import hashlib,json,re,subprocess,xml.etree.ElementTree as ET
root=Path('/workspace/ParkWeave');r=root/'.runtime/runtime-read'
target=root/'docs/F2/evidence/ordinary-runtime-read-20261017'
assert not target.exists()
f=json.loads((r/'freeze.json').read_text());pre=json.loads((r/'preflight.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==f['source_sha']
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in f['files'].items())
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in pre['baseline_evidence_files'].items())
inv=json.loads((r/'final-v3-invocation.json').read_text());assert 'exit_code' in inv
assert hashlib.sha256((r/'retry_runner_v3.py').read_bytes()).hexdigest()==inv['monitor_sha256']
xml=ET.parse(r/'final-v3.xml');cases=xml.findall('.//testcase')
groups={}
for c in cases:groups.setdefault((c.get('classname'),c.get('name')),[]).append(c)
assert len(groups)==427
failed=len(xml.findall('.//failure'));errors=len(xml.findall('.//error'));skipped=len(xml.findall('.//skipped'))
passed=sum(not any(c.findall(k) for c in reports for k in ('failure','error','skipped')) for reports in groups.values())
success=inv['exit_code']==0 and passed==427 and failed==errors==skipped==0
expected={x for x in (r/'final-collection.txt').read_text().splitlines() if x.startswith('tests/') and '::' in x}
executed={'tests/'+c.get('classname').split('.')[-1]+'.py::'+c.get('name') for c in cases}
assert expected==executed,dict(missing=sorted(expected-executed),extra=sorted(executed-expected))
pattern=re.compile(r'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])')
known=set()
for p in f['files']:
 try:known.update(pattern.findall((root/p).read_text()))
 except UnicodeDecodeError:pass
target.mkdir(parents=True);pairs=[]
def export(src,name):
 raw=src.read_bytes();count=0
 try:
  text=raw.decode('utf-8')
  def redact(m):
   nonlocal count
   if m[0] in known:return m[0]
   count+=1;return '[SYNTHETIC_SESSION_REDACTED]'
  data=pattern.sub(redact,text).encode()
  assert not set(pattern.findall(data.decode()))-known
 except UnicodeDecodeError:data=raw
 out=target/name;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(data)
 if out.suffix=='.json':json.loads(data)
 if out.suffix=='.xml':ET.fromstring(data)
 pairs.append(dict(original=str(src.relative_to(root)) if src.is_relative_to(root) else str(src),exported=str(out.relative_to(root)),original_sha256=hashlib.sha256(raw).hexdigest(),exported_sha256=hashlib.sha256(data).hexdigest(),original_bytes=len(raw),exported_bytes=len(data),synthetic_session_occurrences_redacted=count))
for name in ('dev-v1.log','dev-v1.xml','dev-v2.log','dev-v2.xml','dev-v3.log','dev-v3.xml',
 'final-v1.log','final-v1.xml','final-v2.log','final-v2.xml','final-v2-postgres.log','final-v2-invocation.json',
 'final-v3.log','final-v3.xml','final-v3-postgres.log','final-v3-invocation.json',
 'editable-install.log','build-backend-install.log','editable-install-v2.log','editable-profile.json','final-v3-packages.txt',
 'retry-runner.log','retry_runner.py','retry_runner_v3.py','freeze.json','final-collection.txt','failure-ledger.json','remote-before.txt','export_evidence.py'):
 export(r/name,name)
for window in ('final-v1-writer','final-v2-writer','final-v3-writer','final-v3-activation'):
 for p in sorted((r/window).rglob('*')):
  if p.is_file():export(p,'writer-evidence/'+window+'/'+str(p.relative_to(r/window)))
for window in ('final-v1','final-v2','final-v3'):
 base=Path('/tmp/parkweave-runtime-read-'+window)
 for p in sorted(base.rglob('*')):
  if p.is_file() and p.name in ('ordinary-api.log','source-entry-proof.json','source-entry.png','runtime-navigation.png','readonly-signed-history-host-binder-di.png','setup.log','state.json'):
   export(p,'process-evidence/'+window+'/'+str(p.relative_to(base)))
by_module=dict(Counter(key[0] for key in groups));assert len(by_module)==13
summary=dict(base_sha=pre['base_sha'],source_sha=f['source_sha'],branch=pre['branch'],
 result='PASS_FINAL_V3_WITH_PRIOR_FAILURES_AND_UNVERIFIED_BOUNDARIES' if success else 'FINAL_V3_HAS_FAILURES_NOT_ADMITTED',
 latest_invocation='final-v3',latest_exit_code=inv['exit_code'],accepted_invocation='final-v3' if success else None,
 tests=dict(unique=427,testcase_elements=len(cases),passed=passed,failed=failed,errors=errors,skipped=skipped,complete_modules=13,by_module=by_module),
 junit_seconds=sum(float(s.get('time','0')) for s in xml.findall('.//testsuite')),
 new_tests=36,new_tests_included=True,
 new_tests_passed=sum(key[0] in ('tests.test_ordinary_runtime_read','tests.test_ordinary_runtime_read_browser') and not any(c.findall(k) for c in reports for k in ('failure','error','skipped')) for key,reports in groups.items()),
 failing_cases=[dict(classname=key[0],name=key[1],failed=sum(len(c.findall('failure')) for c in reports),errors=sum(len(c.findall('error')) for c in reports)) for key,reports in groups.items() if any(c.findall(k) for c in reports for k in ('failure','error'))],
 prior_and_development_passes_not_added=True,
 first_formal_window=dict(invocation='final-v1',source_sha=f['source_sha'],completed=False,passed=125,failed=1,teardown_errors=1,
 cause='NOT_ESTABLISHED; original owner connection handshake connect_timeout=2 expired during snapshot, then original DROP DB ObjectInUse; earlier UI checks passed',controlled_sigint=True),
 second_formal_window=dict(invocation='final-v2',source_sha=f['source_sha'],completed=True,unique=427,passed=424,failed=2,errors=2,
 errors_are_setup_and_teardown_of_one_item=True,worker_failure_cause='README required editable install missing; original minimal child environment correctly excludes PYTHONPATH',
 fixture_error_cause='NOT_ESTABLISHED; unchanged connect_timeout=2 owner handshake timeout then original DROP DATABASE ObjectInUse'),
 failure_ledger='failure-ledger.json',final_profile=inv['development_profile'],final_evidence_environment=inv['evidence_env'],
 retry=dict(same_source=True,same_complete_modules=True,same_test_set=True,assertions_or_time_budgets_changed=False,documented_editable_development_profile_corrected=True,additional_observer='file-only owned PG log copy, no DB connection or lifecycle ref',observer_sha256=inv['monitor_sha256']),
 frozen_files=len(f['files']),frozen_drift=0,baseline_evidence_files=len(pre['baseline_evidence_files']),baseline_evidence_drift=0,
 original_algorithms_and_roles_unchanged=pre['original_algorithms_and_roles_unchanged'],
 independent_review='NOT_RUN for this new slice; self-review only',
 verification_layers=dict(factory_with_host_binder_DI_and_real_owned_PG_signed_IPC=True,actual_default_configured_app_subprocess_Chromium=True,actual_unprotected_binding_refusal=True,actual_protected_production_binding_positive=False),
 actual_new_ordinary_authority_created=False,real_product_model_calls=0,
 remaining_real_inputs=['current legitimate sessions/READ/PREPARE or REVIEW_ASSIGNED and original Case/Run/preparation','pre-existing approved protected public host binding and exact catalog/version/hash/xmin config','existing safe API/writer roles, physical DB, original native storage and ACL','live pinned verifier, original signed approval and already activated assignment/current authority generations','ordinary resource-plan Approval read/execution contract remains unavailable'],
 not_run=['actual protected production installation/independent UID success','Windows/Win11 native','formal AT/AT35','real business identities/source/approval','real model','deployment','full repository regression'],
 ci='NOT_QUERIED_THIS_SLICE; preceding GitHub API403 stop respected, no alternate path',complete_project=False,
 unknown_lock_or_process_removed=False,unknown_lock_preserved=pre['unknown_lock_preserved'],
 public_pairs=len(pairs),redacted_occurrences=sum(x['synthetic_session_occurrences_redacted'] for x in pairs),
 redaction='43-character candidates absent from frozen source literals replaced; private originals retained; JSON/XML parsed',
 pg_log_observation='periodic copy of this owned file, not guaranteed final shutdown tail; no PG connection or lifecycle reference')
(target/'gate.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
(target/'public-pairs.json').write_text(json.dumps(pairs,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:summary[k] for k in ('result','source_sha','tests','junit_seconds','public_pairs','redacted_occurrences')},ensure_ascii=False))
