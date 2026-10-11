"""Capture an independent bounded test window and immutable source manifests."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def manifest():
    paths = subprocess.check_output(['rg', '--files', 'src', 'tests', 'scripts'], cwd=ROOT, text=True).splitlines()
    paths += ['pyproject.toml', 'requirements-linux-evidence.txt']
    return {p: sha((ROOT / p).read_bytes()) for p in sorted(set(paths))
            if not p.endswith('.pyc') and '__pycache__' not in p}

name = sys.argv[1]
out = BASE / name
out.mkdir(exist_ok=False)
pre = manifest()
inputs={}
for arg in sys.argv[2:]:
    path=ROOT / arg.split('::')[0]
    if path.is_file() and '.runtime/' in arg:
        data=path.read_bytes(); name=path.name+'.txt'
        (out/name).write_bytes(data); inputs[str(path.relative_to(ROOT))]=sha(data)
(out / 'source-before.json').write_text(json.dumps(pre, indent=2, sort_keys=True) + '\n')
argv = [str(ROOT / '.venv/bin/python'), '-m', 'pytest', *sys.argv[2:],
        '--junitxml=' + str(out / 'results.xml'), '-q']
started = datetime.now(timezone.utc).isoformat()
t = time.monotonic()
with (out / 'stdout.log').open('wb') as log:
    env = dict(os.environ, PARKWEAVE_INDEPENDENT_NATIVE_OBSERVATIONS=str(out), PARKWEAVE_NATIVE_ACTIVATION_EVIDENCE_DIR=str(out / 'activation-observations'))
    proc = subprocess.Popen(argv, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=env)
    rc = proc.wait()
post = manifest()
(out / 'source-after.json').write_text(json.dumps(post, indent=2, sort_keys=True) + '\n')
record = dict(argv=argv, pid=proc.pid, started_at=started,
              ended_at=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.monotonic()-t,
              exit_code=rc, runtime_probe_input_sha256=inputs, source_count=len(pre), drift_paths=sorted(p for p in set(pre) | set(post) if pre.get(p) != post.get(p)),
              source_before_sha256=sha((out / 'source-before.json').read_bytes()),
              source_after_sha256=sha((out / 'source-after.json').read_bytes()),
              browser_attempts=0, production_authority_or_assignment_changes=False, owned_synthetic_activation_assignment_writes=True,
              scope='independent owned fixture PG/ASGI/offline Node; explicit issued native activation; no production policy or authority changes')
(out / 'run.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
print(json.dumps(record))
sys.exit(rc)
