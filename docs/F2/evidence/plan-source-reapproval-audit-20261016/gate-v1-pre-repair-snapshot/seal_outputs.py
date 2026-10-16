"""Seal public read-only audit outputs only after the complete gate has exited."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
OWN=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
assert not (OWN/'seal.json').exists(),'sealed audit is immutable'
gate=read(OWN/'gate-v1/final-gate.json');execution=read(OWN/'gate-v1/execution-input.json');binding=read(OWN/'gate-v1/ready-binding.json')
assert gate['status']=='PASS' and binding['source_sha']==gate['source_sha']==execution['ready']['source_sha']
assert execution['script_sha256']==sha(OWN/'final_gate.py') and execution['transform_sha256']==sha(OWN/'independent_transform.py')
assert execution['inventory_sha256']==sha(OWN/'inventory_rules.py')
assert execution['profile_gap_sha256']==sha(OWN/'profile_gap.py')
assert execution['t07_retry_sha256']==sha(OWN/'t07_retry.py')
assert execution['config']==read(OWN/'audit-config-prepared.json')
lines=[line for line in (OWN/'runner.log').read_text().splitlines() if line.strip()]
assert lines and json.loads(lines[-1])==gate,'wait until gate process and runner.log finish'
manifest={}
for path in sorted(OWN.rglob('*')):
    if not path.is_file() or '__pycache__' in path.parts or '.private.' in path.name or path.name=='seal.json':continue
    assert path.suffix in ('.py','.json','.log','.patch','.txt','.md'),path
    manifest[str(path.relative_to(OWN))]=sha(path)
assert 'gate-v1/final-gate.json' in manifest and 'runner.log' in manifest and 'gate-v1/ready-binding.json' in manifest
result=dict(status='SEALED',source_sha=gate['source_sha'],utc=datetime.now(timezone.utc).isoformat(),run='gate-v1',public_sha256=manifest,seal_self_hash_included=False,primary_raw_modified=False,all_tests_run_by_gate=False)
(OWN/'seal.json').write_text(json.dumps(result,indent=2)+'\n')
assert all(sha(OWN/path)==h for path,h in manifest.items())
print(json.dumps(dict(status='SEALED',source_sha=gate['source_sha'],public_files=len(manifest),gate_status=gate['status'])))
