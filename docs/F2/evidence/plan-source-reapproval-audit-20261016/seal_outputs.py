"""Seal an explicit completed full remote-required gate, preserving earlier failures."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json
ROOT=Path('/workspace/ParkWeave');OWN=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
parser=argparse.ArgumentParser();parser.add_argument('--run',choices=('gate-v1','gate-v2'),default='gate-v1');parser.add_argument('--runner');args=parser.parse_args()
assert not (OWN/'seal.json').exists() and not (OWN/'seal-local.json').exists(),'sealed audit is immutable'
runner=args.runner or ('runner.log' if args.run=='gate-v1' else 'runner-gate-v2.log')
assert runner==('runner.log' if args.run=='gate-v1' else 'runner-gate-v2.log')
run=OWN/args.run;gate=read(run/'final-gate.json');execution=read(run/'execution-input.json');binding=read(run/'ready-binding.json')
assert gate['status']==gate['archive_integrity_status']=='PASS' and gate['remote_status']=='VERIFIED'
assert gate['baseline_remote_refs_unchanged']==81 and binding['source_sha']==gate['source_sha']==execution['ready']['source_sha']
for key,name in [('script_sha256','final_gate.py'),('transform_sha256','independent_transform.py'),('inventory_sha256','inventory_rules.py'),('profile_gap_sha256','profile_gap.py'),('t07_retry_sha256','t07_retry.py')]:assert execution[key]==sha(OWN/name)
config=read(OWN/'audit-config-prepared.json');assert execution['config']==config
ready=read(ROOT/execution['ready_path']);assert ready==execution['ready'] and ready['status']=='ARCHIVE_READY'
assert sha(ROOT/execution['ready_path'])==execution['ready_sha256']==binding['ready_sha256'] and binding['ready_path']==execution['ready_path']
assert ready['primary_producers_stopped'] is binding['primary_producers_stopped'] is True
assert binding['status']=='BOUND_TO_ACTUAL_READY_AND_SEALED_PRIMARY'
primary=read(ROOT/binding['primary_seal_path']);assert primary['status']==binding['primary_seal_status']=='SEALED_NO_FURTHER_PRIMARY_WRITES'
assert primary['source_sha']==gate['source_sha'] and sha(ROOT/binding['primary_seal_path'])==ready['primary_seal_sha256']==binding['primary_seal_sha256']
assert sha(ROOT/config['report'])==ready['report_sha256']==binding['report_sha256']==gate['report_sha256']
assert sha(ROOT/config['archive']/'index.json')==ready['archive_index_sha256']==binding['archive_index_sha256']==gate['archive_index_sha256']
lines=[line for line in (OWN/runner).read_text().splitlines() if line.strip()]
assert lines and json.loads(lines[-1])==gate,'wait until gate process and runner.log finish'
if args.run=='gate-v2':
    assert (OWN/'runner-gate-v2.exit').read_bytes()==b'0\n'
    preservation=read(OWN/'gate-v1-preservation.json');assert preservation['status']=='ORIGINAL_GATE_V1_FAILURE_PRESERVED' and preservation['original_exit_code']==1
    assert read(OWN/'gate-v1/final-gate.json')['status']=='FAIL'
    assert all(sha(OWN/p)==h for p,h in preservation['public_sha256'].items())
manifest={}
for path in sorted(OWN.rglob('*')):
    if not path.is_file() or '__pycache__' in path.parts or '.private.' in path.name or path.name.endswith('private.json') or path.name in ('seal.json','seal-local.json'):continue
    assert not path.is_symlink(),path
    assert path.suffix in ('.py','.json','.log','.patch','.txt','.md','.exit'),path
    manifest[str(path.relative_to(OWN))]=sha(path)
assert args.run+'/final-gate.json' in manifest and runner in manifest and args.run+'/ready-binding.json' in manifest
result=dict(status='SEALED',source_sha=gate['source_sha'],utc=datetime.now(timezone.utc).isoformat(),run=args.run,runner=runner,public_sha256=manifest,seal_self_hash_included=False,primary_raw_modified=False,all_tests_run_by_gate=False,full_remote_verification=True,prior_failed_gate_preserved=args.run=='gate-v2')
(OWN/'seal.json').write_text(json.dumps(result,indent=2)+'\n')
assert all(sha(OWN/path)==h for path,h in manifest.items())
print(json.dumps(dict(status='SEALED',source_sha=gate['source_sha'],public_files=len(manifest),gate_status=gate['status'],run=args.run)))
