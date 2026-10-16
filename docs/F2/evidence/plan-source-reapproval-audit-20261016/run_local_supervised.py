"""Prepare a durable exit receipt only after the local-only subprocess exits."""
from pathlib import Path
import argparse,json,subprocess,sys
OWN=Path(__file__).resolve().parent
ROOT=Path('/workspace/ParkWeave')
parser=argparse.ArgumentParser();parser.add_argument('--ready',required=True);args=parser.parse_args()
assert json.loads((ROOT/args.ready).read_text())['status']=='ARCHIVE_READY'
assert not any((OWN/name).exists() for name in ('seal.json','seal-local.json','local-runner.log','local-runner.exit','local-integrity-v1'))
with (OWN/'local-runner.log').open('x') as stream:
    result=subprocess.run([sys.executable,str(OWN/'run_local_integrity.py'),'--ready',args.ready,'--run','local-integrity-v1'],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
(OWN/'local-runner.exit').write_text(str(result.returncode)+'\n')
sys.exit(result.returncode if result.returncode>=0 else 128-result.returncode)
