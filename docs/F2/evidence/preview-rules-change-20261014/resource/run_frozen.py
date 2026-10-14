import hashlib,json,pathlib,subprocess,time
base=pathlib.Path('.runtime/resource-change-20261014')
files=sorted(p for directory in ('src','tests','scripts') for p in pathlib.Path(directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
def manifest():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
before=manifest();(base/'final-before.json').write_text(json.dumps(before,indent=2)+'\n')
modules=['tests/test_service_resource_change_replay.py','tests/test_resource_plan_binding.py','tests/test_registered_local_revision.py','tests/test_case_resources.py','tests/test_resource_alternative_times.py','tests/test_service_selection_replay_acceptance.py']
start=time.monotonic()
with (base/'final.log').open('w') as log:
    code=subprocess.run(['/workspace/ParkWeave/.venv/bin/python','-m','pytest',*modules,'-q','--junitxml='+str(base/'final.xml')],stdout=log,stderr=subprocess.STDOUT).returncode
elapsed=time.monotonic()-start;after=manifest()
(base/'final-after.json').write_text(json.dumps(after,indent=2)+'\n');(base/'final.exit').write_text(str(code)+'\n')
report=dict(modules=modules,exit_code=code,elapsed_seconds=elapsed,source_files=len(before),changed=[p for p in before if before[p]!=after[p]])
(base/'final-window.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));print((base/'final.log').read_text()[-6000:])
