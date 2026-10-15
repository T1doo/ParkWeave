from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path('/workspace/ParkWeave')
OUT = ROOT / '.runtime/at24-27-review'
PREFIX = 'resource-gate-wip-02'


def manifest():
    paths = subprocess.check_output(['git', 'ls-files', 'src', 'tests', 'scripts', 'pyproject.toml'], cwd=ROOT, text=True).splitlines()
    paths += ['src/parkweave/plan_source_conflicts.py', 'tests/test_plan_source_conflicts.py']
    return dict(head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        hashes={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sorted(set(paths)) if (ROOT / name).is_file()})


before = manifest()
(OUT / (PREFIX + '-before.json')).write_text(json.dumps(before, indent=2) + '\n')
env = {**os.environ, 'PYTHONPATH': str(ROOT / 'tests') + ':' + str(ROOT / 'src'),
    'XDG_CACHE_HOME': str(ROOT / '.runtime/xdg-cache')}
command = [str(ROOT / '.venv/bin/python'), '-m', 'pytest', '-p', 'conftest',
    str(OUT / 'test_registered_resource_gate_probe_v2.py'), '-k', 'authority or actual_unknown_catalog', '-q', '--tb=short',
    '--basetemp=/tmp/parkweave-at24-review-resource-gate-wip-02',
    '--junitxml=' + str(OUT / (PREFIX + '.xml'))]
start = time.monotonic()
with (OUT / (PREFIX + '.log')).open('w') as log:
    completed = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
after = manifest()
(OUT / (PREFIX + '-after.json')).write_text(json.dumps(after, indent=2) + '\n')
drift = [path for path in sorted(set(before['hashes']) | set(after['hashes'])) if before['hashes'].get(path) != after['hashes'].get(path)]
summary = dict(status='UNFROZEN_WIP_RUNTIME_PROBE_ONLY', exit_code=completed.returncode,
    elapsed_seconds=time.monotonic() - start, utc=datetime.now(timezone.utc).isoformat(),
    source_before=before['head'], source_after=after['head'], source_hash_drift=drift,
    command=command, not_formal_regression=True, environment='LINUX_SYNTHETIC_OWNED_PG_ACTUAL_HTTP_ASGI')
(OUT / (PREFIX + '-summary.json')).write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary))
raise SystemExit(completed.returncode)
