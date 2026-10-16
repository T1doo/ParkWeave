"""Explicit second full gate; preserve the first failed run and durable exit receipt."""
from pathlib import Path
import argparse,json,subprocess,sys
OWN=Path(__file__).resolve().parent;ROOT=Path('/workspace/ParkWeave')
parser=argparse.ArgumentParser();parser.add_argument('--ready',required=True);parser.add_argument('--run',choices=('gate-v2',),required=True);args=parser.parse_args()
assert json.loads((ROOT/args.ready).read_text())['status']=='ARCHIVE_READY'
assert json.loads((OWN/'gate-v1/final-gate.json').read_text())['status']=='FAIL'
assert not any((OWN/p).exists() for p in ('seal.json','seal-local.json','runner-gate-v2.log','runner-gate-v2.exit','gate-v2'))
with (OWN/'runner-gate-v2.log').open('x') as log:
    result=subprocess.run([sys.executable,str(OWN/'final_gate.py'),'--ready',args.ready,'--run',args.run],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
(OWN/'runner-gate-v2.exit').write_text(str(result.returncode)+'\n')
sys.exit(result.returncode if result.returncode>=0 else 128-result.returncode)
