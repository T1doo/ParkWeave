from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,tarfile,io,os,time,shutil

root=Path('/workspace/ParkWeave');run=root/'.runtime/fixed-acceptance-closeout-20261018'
prior=run/'frozen-7f02fe3f';out=run/'supplement-7f02fe3f';out.mkdir(exist_ok=False)
previous=json.loads((prior/'result.json').read_text());mirror=Path(previous['mirror']);head=previous['head']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
old=json.loads((prior/'shared-after.json').read_text())
assert all(sha(root/p)==sha(mirror/p)==value for p,value in old.items())
extra=subprocess.check_output(['git','ls-files','-z','docs/sources/V1'],cwd=root).decode().strip('\x00').split('\x00')
archive=subprocess.check_output(['git','archive',head,*extra],cwd=root)
with tarfile.open(fileobj=io.BytesIO(archive)) as tf:tf.extractall(mirror,filter='data')
paths=sorted(set(old)|set(extra));pre={p:sha(root/p) for p in paths};mpre={p:sha(mirror/p) for p in paths};assert pre==mpre
(out/'shared-before.json').write_text(json.dumps(pre,indent=2)+'\n');(out/'mirror-before.json').write_text(json.dumps(mpre,indent=2)+'\n')
env={k:v for k,v in os.environ.items() if not k.startswith('PARKWEAVE_')}
env.update(PYTHONPATH=str(mirror/'src')+':'+str(mirror/'tests')+':'+str(mirror),PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1')
commands=[];t=time.monotonic();started=datetime.now(timezone.utc).isoformat()
def execute(cmd,name,timeout):
    with (out/(name+'.stdout')).open('w') as stdout,(out/(name+'.stderr')).open('w') as stderr:
        p=subprocess.run(cmd,cwd=mirror,env=env,stdout=stdout,stderr=stderr,timeout=timeout)
    commands.append(dict(name=name,args=cmd,exit_code=p.returncode));return p.returncode
code=execute([str(root/'.venv/bin/python'),str(run/'stable-child.py'),str(out),'-q','-c',str(mirror/'pyproject.toml'),'--rootdir='+str(mirror),'-p','no:cacheprovider','tests/test_acceptance_runner.py::test_sources_archive_integrity','--junitxml='+str(out/'results.xml')],'document-node',30)
if code==0:
    code=execute([str(root/'.venv/bin/python'),'-B',str(run/'stable-observer.py'),str(out/'actual-source-verification.json'),head],'source-verification',30)
if code==0:
    code=execute([str(root/'.venv/bin/python'),'-B','scripts/run_acceptance.py','--ids','AT-13','--source-head',head,'--report',str(out/'original-runner-at13.json')],'original-runner-at13',120)
for p in (mirror/'.runtime').glob('pytest-*'):
    if p.is_file():
        target=out/'original-runner-artifacts'/p.name;target.parent.mkdir(exist_ok=True);shutil.copyfile(p,target)
post={p:sha(root/p) for p in paths};mpost={p:sha(mirror/p) for p in paths}
(out/'shared-after.json').write_text(json.dumps(post,indent=2)+'\n');(out/'mirror-after.json').write_text(json.dumps(mpost,indent=2)+'\n')
report=dict(head=head,commands=commands,exit_code=code,started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),outer_seconds=time.monotonic()-t,inputs=len(paths),four_maps_equal=pre==mpre==post==mpost,prior_809_input_hashes_unchanged=True,extra_document_inputs=extra,prior_successful_24_nodes_not_repeated=True,mirror=str(mirror),old_AT21_AT32_or_risk_windows_retried=False,full_regression=False,real_model_calls=0,independent_dynamic=0)
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
for name in ['document-node','source-verification','original-runner-at13']:
    p=out/(name+'.stdout')
    if p.exists():print(p.read_text()[-1800:])
raise SystemExit(code)
