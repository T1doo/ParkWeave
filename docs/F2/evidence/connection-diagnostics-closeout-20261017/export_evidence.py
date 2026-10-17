"""Explicit closed-file archive; never snapshot this exporter's active log."""
from pathlib import Path
import hashlib,json,re,subprocess,xml.etree.ElementTree as ET
root=Path('/workspace/ParkWeave');r=root/'.runtime/runtime-diagnostic-closeout'
target=root/'docs/F2/evidence/connection-diagnostics-closeout-20261017';assert not target.exists()
f=json.loads((r/'freeze.json').read_text());assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in f['files'].items())
six=json.loads((r/'six-no-diagnostics-invocation.json').read_text());smoke=json.loads((r/'sigint-verification.json').read_text());controller=json.loads((r/'sigint-controller.json').read_text());child=json.loads((r/'sigint-pytest-invocation.json').read_text())
assert six['exit_code']==0 and six['node_order_exact'] and six['sessionstart_diagnostics_disabled'] and six['sessionfinish_diagnostics_disabled']
for name,meta in [('run_no_diagnostics.py',six),('control_sigint.py',controller),('run_sigint_pytest.py',child)]:
 assert hashlib.sha256((r/name).read_bytes()).hexdigest()==meta['helper_sha256']
assert smoke['result']=='EXPECTED_INTERRUPT_CLEANUP_PROVED' and controller['exit_code']==child['exit_code']==2
t=ET.parse(r/'six-no-diagnostics.xml');cases=t.findall('.//testcase');assert len(cases)==6
assert not any(t.findall('.//'+k) for k in ('failure','error','skipped'))
actual=['tests/'+c.get('classname').split('.')[-1]+'.py::'+c.get('name') for c in cases]
assert actual==json.loads((r/'target-nodes.json').read_text())
names=['preflight.json','freeze.json','target-nodes.json','run_no_diagnostics.py','six-no-diagnostics-invocation.json',
 'six-no-diagnostics.log','six-no-diagnostics.xml','sigint-case/test_owned_interrupt.py','run_sigint_pytest.py','control_sigint.py',
 'sigint-controller.json','sigint-ready.json','sigint-control.log','sigint-smoke.log','sigint-smoke.xml',
 'sigint-pytest-invocation.json','sigint-verification.json','preservation-check.json','export_evidence.py',
 'sigint-diagnostics/connections.jsonl','sigint-diagnostics/postgres.log']
assert all((r/name).is_file() for name in names)
pattern=re.compile(r'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])');known={'expected_service_id-SYNTHETIC-other-service'}
for path in f['files']:
 try:known.update(pattern.findall((root/path).read_text()))
 except UnicodeDecodeError:pass
for name in names:
 if name.endswith('.py'):known.update(pattern.findall((r/name).read_text()))
target.mkdir(parents=True);pairs=[]
for name in names:
 src=r/name;raw=src.read_bytes();redacted=0
 def redact(m):
  global redacted
  if m[0] in known:return m[0]
  redacted+=1;return '[SYNTHETIC_SESSION_REDACTED]'
 data=pattern.sub(redact,raw.decode()).encode();out=target/name;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(data)
 if out.suffix=='.json':json.loads(data)
 if out.suffix=='.jsonl':
  for line in data.splitlines():json.loads(line)
 if out.suffix=='.xml':
  ET.fromstring(data)
  nodes=lambda b:[(c.get('classname'),c.get('name')) for c in ET.fromstring(b).findall('.//testcase')]
  assert nodes(raw)==nodes(data)
 pairs.append(dict(original=str(src.relative_to(root)),exported=str(out.relative_to(root)),original_sha256=hashlib.sha256(raw).hexdigest(),exported_sha256=hashlib.sha256(data).hexdigest(),original_bytes=len(raw),exported_bytes=len(data),redacted_occurrences=redacted))
preserved=json.loads((r/'preservation-check.json').read_text())
gate=dict(base_sha='f26a09ecab71b6a277e9fee87f92f501ebf8e7a6',source_sha=f['source_sha'],branch='dev/f3-runtime-diagnostics-closeout-20261017',
 result='CLOSEOUT_CHECKS_PASSED_HISTORICAL_TIMEOUT_UNKNOWN',
 six_tests=dict(unique=6,passed=6,failed=0,errors=0,skipped=0,seconds=sum(float(s.get('time','0')) for s in t.findall('.//testsuite')),diagnostics_disabled=True,original_node_order=True,runs=1,fully_overlaps_preceding427=True),
 smoke=smoke,smoke_is_not_a_seventh_pytest_pass=True,full427_rerun=False,full427_status='preceding instrumented427 admitted by parent independent review; not added or re-executed',
 source_files=f['files'].__len__(),source_drift=0,product_and_original_tests_unchanged=True,
 inherited_archive_git_blobs=preserved['inherited_archive_git_blobs_checked'],inherited_archive_drift=0,
 public_pairs=len(pairs),redacted_occurrences=sum(x['redacted_occurrences'] for x in pairs),
 original_raw_evidence_retained=True,all_junit_node_sequences_preserved=True,
 scope='connection diagnostics disabled in original6; independent smoke enables frozen diagnostic plugin solely to verify its sessionfinish cleanup, at a main-thread waiting point with one original app connection and an original owned reference writer',
 historical_timeout_cause='UNKNOWN; neither window is a natural timeout reproduction; failure sampling path not triggered or validated',
 not_run=['SIGINT during handshake/blocked SQL or active browser work','double interruption/kill/crash recovery','Windows/formalAT/real business/protected production positive'],
 real_runtime_missing_inputs='unchanged from prior reports, including ordinary resource-plan Approval contract',
 independent_review='pending for closeout evidence; preceding427 already admitted by parent',
 Actions_queries=0,unknown_processes_locks_sessions_removed=False,real_authority_credentials_security_permissions_changed=False,complete_project=False,
 diagnostic_work_closed=True)
(target/'gate.json').write_text(json.dumps(gate,indent=2,ensure_ascii=False)+'\n');(target/'public-pairs.json').write_text(json.dumps(pairs,indent=2)+'\n')
print(json.dumps({k:gate[k] for k in ('result','source_sha','six_tests','public_pairs','redacted_occurrences')},ensure_ascii=False))
