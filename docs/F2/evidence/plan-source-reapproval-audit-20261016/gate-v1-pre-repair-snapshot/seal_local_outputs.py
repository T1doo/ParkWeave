"""Seal an exited local-only integrity run. This never asserts full-gate PASS."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
ROOT=Path('/workspace/ParkWeave')
OWN=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
assert not (OWN/'seal.json').exists() and not (OWN/'seal-local.json').exists(),'sealed audit is immutable'
RUN='local-integrity-v1';run=OWN/RUN
result=read(run/'local-integrity.json');execution=read(run/'execution-input.json');binding=read(run/'ready-binding.json');remote=read(run/'remote-current.json')
assert result['status']==result['archive_integrity_status']=='LOCAL_INTEGRITY_ONLY'
assert result['final_gate_pass'] is False and result['remote_verification_complete'] is False
assert result['remote_status']=='NOT_VERIFIED_AUTH_BLOCKED' and result['baseline_remote_refs_unchanged'] is None
assert result['baseline_remote_refs_requiring_verification']==81
assert result['delivery_or_push_performed'] is False
assert result['source_sha']==binding['source_sha']==execution['ready']['source_sha']
assert execution['verification_mode']=='LOCAL_INTEGRITY_ONLY'
for key,name in [('script_sha256','final_gate.py'),('local_runner_sha256','run_local_integrity.py'),('transform_sha256','independent_transform.py'),('inventory_sha256','inventory_rules.py'),('profile_gap_sha256','profile_gap.py'),('t07_retry_sha256','t07_retry.py')]:
    assert execution[key]==sha(OWN/name),(key,name)
config=read(OWN/'audit-config-prepared.json');assert execution['config']==config
ready_path=ROOT/execution['ready_path'];ready_raw=ready_path.read_bytes();ready=json.loads(ready_raw)
assert ready==execution['ready'] and ready['status']=='ARCHIVE_READY'
assert sha(ready_path)==execution['ready_sha256']==binding['ready_sha256'] and binding['ready_path']==execution['ready_path']
assert ready['primary_producers_stopped'] is binding['primary_producers_stopped'] is True
assert binding['status']=='BOUND_TO_ACTUAL_READY_AND_SEALED_PRIMARY'
primary_path=ROOT/binding['primary_seal_path'];primary=read(primary_path)
assert primary['status']==binding['primary_seal_status']=='SEALED_NO_FURTHER_PRIMARY_WRITES'
assert primary['source_sha']==result['source_sha'] and sha(primary_path)==ready['primary_seal_sha256']==binding['primary_seal_sha256']
assert sha(ROOT/config['report'])==ready['report_sha256']==binding['report_sha256']==result['report_sha256']
assert sha(ROOT/config['archive']/'index.json')==ready['archive_index_sha256']==binding['archive_index_sha256']==result['archive_index_sha256']
assert remote['status']=='NOT_VERIFIED' and remote['reason']=='EXISTING_GITHUB_CONNECTION_AUTHENTICATION_BLOCKED'
assert remote['network_calls_attempted_by_this_runner']==0 and remote['baseline_ref_count']==81 and remote['baseline_refs_unchanged'] is None
assert remote['original_failure_path']==execution['remote_auth_failure_log']==config['remote_auth_failure_log']
assert remote['original_failure_sha256']==execution['remote_auth_failure_sha256']==sha(ROOT/config['remote_auth_failure_log'])
assert (OWN/'local-runner.exit').read_bytes()==b'0\n','explicit completed subprocess exit receipt required'
lines=[line for line in (OWN/'local-runner.log').read_text().splitlines() if line.strip()]
assert lines and json.loads(lines[-1])==result,'wait for the local runner and log to finish'
assert not (OWN/'local-integrity.json').exists(),'public alias must not overwrite earlier output'
(OWN/'local-integrity.json').write_bytes((run/'local-integrity.json').read_bytes())
manifest={}
for path in sorted(OWN.rglob('*')):
    if not path.is_file() or '__pycache__' in path.parts or '.private.' in path.name or path.name.endswith('private.json') or path.name in ('seal.json','seal-local.json'):continue
    assert not path.is_symlink(),path
    assert path.suffix in ('.py','.json','.log','.patch','.txt','.md','.exit'),path
    manifest[str(path.relative_to(OWN))]=sha(path)
for name in ('local-integrity.json','local-runner.log','local-runner.exit',RUN+'/execution-input.json',RUN+'/ready-binding.json',RUN+'/local-integrity.json',RUN+'/remote-current.json','final_gate.py','seal_outputs.py','seal_local_outputs.py'):
    assert name in manifest,name
seal=dict(status='SEALED_LOCAL_INTEGRITY_ONLY',verification_status='LOCAL_INTEGRITY_ONLY',source_sha=result['source_sha'],utc=datetime.now(timezone.utc).isoformat(),run=RUN,public_sha256=manifest,public_result='local-integrity.json',final_gate_pass=False,remote_verification_complete=False,remote_status='NOT_VERIFIED_AUTH_BLOCKED',seal_self_hash_included=False,primary_raw_modified=False,all_tests_run_by_gate=False,delivery_or_push_performed=False)
(OWN/'seal-local.json').write_text(json.dumps(seal,indent=2)+'\n')
assert all(sha(OWN/path)==h for path,h in manifest.items())
print(json.dumps(dict(status=seal['status'],source_sha=seal['source_sha'],public_files=len(manifest),final_gate_pass=False,remote_verification_complete=False)))
