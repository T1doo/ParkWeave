"""New archive only. Preserve every raw window and report actual complete results."""
from pathlib import Path
from collections import Counter
import hashlib,json,re,subprocess,xml.etree.ElementTree as ET
root=Path('/workspace/ParkWeave');r=root/'.runtime/runtime-read-diagnostics'
target=root/'docs/F2/evidence/owned-connection-diagnostics-20261017'
assert not target.exists()
f=json.loads((r/'freeze-v2.json').read_text());inherited=json.loads((r/'inherited-evidence.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==f['source_sha']
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in f['files'].items())
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in inherited['files'].items())
inv=json.loads((r/'full-v2-invocation.json').read_text());assert 'exit_code' in inv
assert hashlib.sha256((r/'run_full_v2.py').read_bytes()).hexdigest()==inv['helper_sha256']
xml=ET.parse(r/'full-v2.xml');cases=xml.findall('.//testcase');groups={}
for c in cases:groups.setdefault((c.get('classname'),c.get('name')),[]).append(c)
expected=[x for x in (r/'full-v2-collection.txt').read_text().splitlines() if x.startswith('tests/') and '::' in x]
actual=['tests/'+k[0].split('.')[-1]+'.py::'+k[1] for k in groups]
assert expected==actual and len(groups)==427
counts=dict(unique=len(groups),testcase_elements=len(cases),passed=sum(not any(c.findall(k) for c in cs for k in ('failure','error','skipped')) for cs in groups.values()),
 failed=len(xml.findall('.//failure')),errors=len(xml.findall('.//error')),skipped=len(xml.findall('.//skipped')),
 complete_modules=len(set(k[0] for k in groups)),by_module=dict(Counter(k[0] for k in groups)))
success=inv['exit_code']==0 and counts['passed']==427 and counts['failed']==counts['errors']==counts['skipped']==0
pattern=re.compile(r'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])')
known={'expected_service_id-SYNTHETIC-other-service'}
for p in f['files']:
 try:known.update(pattern.findall((root/p).read_text()))
 except UnicodeDecodeError:pass
sources=[]
for p in sorted(r.iterdir()):
 if p.is_file() and p.name not in ('inherited-evidence.json','continuation.json') and not (p.name.startswith('export') and p.suffix=='.log') and p.suffix in ('.json','.jsonl','.log','.xml','.txt','.py'):
  sources.append((p,p.name))
for name in ('target-v1-diagnostics','target-v2-diagnostics','target-v3-diagnostics','full-v1-diagnostics','full-v2-diagnostics','full-v1-writer','full-v2-writer','full-v1-activation','full-v2-activation'):
 for p in sorted((r/name).rglob('*')):
  if p.is_file():sources.append((p,name+'/'+str(p.relative_to(r/name))))
for name in ('full-v1','full-v2'):
 base=Path('/tmp/parkweave-connection-'+name)
 for p in sorted(base.rglob('*')):
  if p.is_file() and p.name in ('ordinary-api.log','source-entry-proof.json','source-entry.png','runtime-navigation.png','readonly-signed-history-host-binder-di.png','setup.log','state.json'):
   sources.append((p,'process-evidence/'+name+'/'+str(p.relative_to(base))))
assert len({name for _,name in sources})==len(sources)
target.mkdir(parents=True);pairs=[]
for src,name in sources:
 raw=src.read_bytes();redacted=0
 try:
  text=raw.decode()
  def redact(m):
   global redacted
   if m[0] in known:return m[0]
   redacted+=1;return '[SYNTHETIC_SESSION_REDACTED]'
  data=pattern.sub(redact,text).encode()
 except UnicodeDecodeError:data=raw
 out=target/name;out.parent.mkdir(parents=True,exist_ok=True);assert not out.exists();out.write_bytes(data)
 if out.suffix=='.json':json.loads(data)
 if out.suffix=='.jsonl':
  for line in data.splitlines():json.loads(line)
 if out.suffix=='.xml':ET.fromstring(data)
 if out.suffix=='.xml':
  nodes=lambda b:[(c.get('classname'),c.get('name')) for c in ET.fromstring(b).findall('.//testcase')]
  assert nodes(raw)==nodes(data),name
 pairs.append(dict(original=str(src.relative_to(root)) if src.is_relative_to(root) else str(src),exported=str(out.relative_to(root)),
  original_sha256=hashlib.sha256(raw).hexdigest(),exported_sha256=hashlib.sha256(data).hexdigest(),original_bytes=len(raw),exported_bytes=len(data),redacted_occurrences=redacted))
analysis=json.loads((r/'full-v2-analysis.json').read_text())
gate=dict(base_sha=f['base_sha'],source_sha=f['source_sha'],branch='dev/f3-runtime-connection-diagnostics-20261017',
 result='PASS_COMPLETE_427_HISTORICAL_TIMEOUT_CAUSE_UNESTABLISHED' if success else 'COMPLETE_427_HAS_FAILURES_NOT_ADMITTED',
 latest_invocation='full-v2',exit_code=inv['exit_code'],tests=counts,junit_seconds=sum(float(s.get('time','0')) for s in xml.findall('.//testsuite')),
 frozen_files=len(f['files']),frozen_drift=0,inherited_evidence_files=len(inherited['files']),inherited_evidence_drift=0,
 inherited_manifest_private_sha256=hashlib.sha256((r/'inherited-evidence.json').read_bytes()).hexdigest(),
 product_src_unchanged=True,[SYNTHETIC_SESSION_REDACTED]=True,original_node_order_unchanged=True,
 target_nodes=json.loads((r/'target-nodes.json').read_text()),target_windows='three developmental6-pass windows retained with exact file hashes; not added to427; target-v3 changed-file hashes equal final frozen files',
 incomplete_full_v1='32 testcases PASS before verified owned SIGINT for static diagnostic compatibility issue; introduced BadFD teardown after early diagnostic finish preserved, process exit1; not a complete427 pass',
 diagnostic_corrections=f['diagnostic_corrections'],historical_timeout_cause='NOT_ESTABLISHED; successful new runs cannot causally explain or fix prior timeouts',
 no_speculative_product_connection_lifecycle_fix=True,
 diagnostics={k:analysis[k] for k in ('attempts','connected','connect_failed','close_ends','correlated_authorized_and_disconnected','unmatched_pg_records','failure_activity_samples','sample_attempts','max_connect_ms','diagnostic_finished','final_unclosed_metadata')},
 failure_sample_scope='at most one short maintenance attempt per failing owned fixture DB, bounded connect2/statement1/lock0.5 seconds, whitelisted pg_stat_activity fields,64 rows; original exception re-raised; returned observer close explicitly recorded',
 no_resident_observer_connection=True,writer_lifecycle_timestamps='raw JSONL monotonic+UTC process/thread phase events and server-side connection/disconnection application_name logs',
 prior_failures_retained=True,independent_review='NOT_RUN for this diagnostic slice; parent previously admitted original36/read wiring only, original427 blocked',
 not_run=['causal reproduction/explanation of historical timeouts unless actual diagnostics establish it','post-correction SIGINT teardown re-execution','actual protected production host/independent UID positive','Windows native','formal AT/AT35','real business/source/approval/model','deployment','full repository regression'],
 ci='NO_ACTIONS_QUERY; original API403 stop respected',complete_project=False,unknown_lock_process_session_removed=False,
 public_pairs=len(pairs),redacted_occurrences=sum(x['redacted_occurrences'] for x in pairs),
 redaction='43-character candidates except frozen source literals or reviewed historical synthetic parameter composite; raw originals retained; all XML node sequences preserved; JSON/JSONL parsed')
(target/'gate.json').write_text(json.dumps(gate,indent=2,ensure_ascii=False)+'\n')
(target/'public-pairs.json').write_text(json.dumps(pairs,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:gate[k] for k in ('result','source_sha','tests','diagnostics','public_pairs','redacted_occurrences')},ensure_ascii=False))
