from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
from collections import Counter
import json,os,subprocess,time,xml.etree.ElementTree as ET

ROOT=Path('/workspace/ParkWeave')
OUT=Path(__file__).resolve().parent
SHA='6187ed2cb933a26cf3d59b846178682e4f119745'
FREEZE=ROOT/'.runtime/multifield-source-root/freeze.json'
def dump(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
def run_text(args):return subprocess.check_output(args,cwd=ROOT,text=True).strip()
def snapshot(name):
    head=run_text(['git','rev-parse','HEAD'])
    status=run_text(['git','status','--porcelain=v1'])
    paths=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')[:-1]
    values={p:sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    value=dict(source_sha=head,tracked_count=len(values),all_tracked_sha256=values,git_status=status,utc=datetime.now(timezone.utc).isoformat())
    dump(name,value)
    assert head==SHA and not status,(head,status)
    frozen=json.loads(FREEZE.read_text())
    assert values==frozen['all_tracked_sha256'],'all tracked freeze differs'
    return value

started=time.monotonic();before=snapshot('alltracked-before.json')
freeze=json.loads(FREEZE.read_text())
dump('probe-hashes-before.json',{str(f.relative_to(OUT)):sha256(f.read_bytes()).hexdigest() for f in sorted(OUT.rglob('*')) if f.is_file() and f.suffix in ('.py','.js')})
env=dict(os.environ,PYTHONPATH=str(ROOT/'tests')+':'+str(OUT),
         MULTIFIELD_REVIEW_PROBE_OUT=str(OUT),XDG_CACHE_HOME=str(ROOT/'.runtime/xdg-cache'))
node_start=time.monotonic()
with (OUT/'vm-29.log').open('wb') as stream:
    node=subprocess.run(['node',str(OUT/'vm-29/probe.js')],cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
node_elapsed=time.monotonic()-node_start
args=[str(ROOT/'.venv/bin/python'),'-m','pytest',
      str(OUT/'test_v3_history_review.py'),str(OUT/'test_final_unknown.py'),str(OUT/'test_v3_carry_history.py'),str(OUT/'test_budget_contract.py'),
      '-p','multifield_frozen_review_capture_6187ed2','-p','no:cacheprovider',
      '--basetemp=/tmp/parkweave-multifield-frozen-6187ed2-review-v1',
      '--junitxml='+str(OUT/'supplement.xml'),'-q','-r','fE']
dump('command.json',dict(source_sha=SHA,args=args,custom_plugin_module='multifield_frozen_review_capture_6187ed2',
    custom_plugin_file=str(OUT/'multifield_frozen_review_capture_6187ed2.py'),
    custom_plugin_sha256=sha256((OUT/'multifield_frozen_review_capture_6187ed2.py').read_bytes()).hexdigest(),
    environment_keys=list(env.keys()-os.environ.keys()),scope='supplemental; excluded from 98 complete-module union'))
pytest_start=time.monotonic()
with (OUT/'supplement.log').open('wb') as stream:
    process=subprocess.run(args,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
pytest_elapsed=time.monotonic()-pytest_start
after=snapshot('alltracked-after.json')
probe_before=json.loads((OUT/'probe-hashes-before.json').read_text())
probe_after={str(f.relative_to(OUT)):sha256(f.read_bytes()).hexdigest() for f in sorted(OUT.rglob('*')) if f.is_file() and f.suffix in ('.py','.js')}
dump('probe-hashes-after.json',probe_after)
root=ET.parse(OUT/'supplement.xml').getroot();cases=list(root.iter('testcase'))
counts=Counter('ERROR' if c.find('error') is not None else 'FAIL' if c.find('failure') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS' for c in cases)
collection=json.loads((OUT/'pytest-collection.json').read_text())['nodeids']
actual=[c.attrib['classname'].replace('.','/')+'.py::'+c.attrib['name'] for c in cases]
collected_names=[n.rsplit('::',1)[-1] for n in collection]
same=Counter(collected_names)==Counter(c.attrib['name'] for c in cases)
vm=json.loads((OUT/'vm-29/probe-result.json').read_text())
matrix=json.loads((OUT/'history-matrix-result.json').read_text()) if (OUT/'history-matrix-result.json').exists() else None
budget=json.loads((OUT/'budget-six-checks.json').read_text()) if (OUT/'budget-six-checks.json').exists() else None
imports=json.loads((OUT/'execution-source-resolution.json').read_text())
validation=dict(source_sha=SHA,scope='Linux synthetic supplemental window; not complete-module regression union',
    pytest_exit=process.returncode,pytest_counts=dict(counts),pytest_elapsed_seconds=pytest_elapsed,vm_exit=node.returncode,
    vm_elapsed_seconds=node_elapsed,vm_units=vm['units'],vm_result_label=vm['status'],
    mutation_checks=matrix['units'] if matrix else None,all37_mutations_rejected=bool(matrix and all(r['actual_rejected'] for r in matrix['results'])),
    budget_checks=budget['units'] if budget else None,budget_is_pure_known_basis_stub=True,
    collection_count=len(collection),junit_count=len(cases),raw_collection_and_junit_names_exact=same,
    source_path_count=len(freeze['source_paths']),tracked_count=before['tracked_count'],
    all_tracked_before_after_equal=before['all_tracked_sha256']==after['all_tracked_sha256'],
    actual_imported_products_unchanged=imports['unchanged'],plugin_path=imports['plugin_path'],plugin_sha256=imports['plugin_sha256'],
    probe_bytes_unchanged=probe_before==probe_after,total_elapsed_seconds=time.monotonic()-started,
    real_browser=False,real_expiry_test=False,six_goal_main_acceptance=False)
validation['status']='PASS' if (process.returncode==node.returncode==0 and counts=={'PASS':4} and same and len(collection)==len(cases)==4 and vm['units']==29 and vm['status']=='PASS_WIP_VM_ONLY_NOT_FROZEN' and validation['all37_mutations_rejected'] and budget['units']==6 and validation['all_tracked_before_after_equal'] and imports['unchanged'] and probe_before==probe_after) else 'FAIL'
dump('validation.json',validation)
print(json.dumps(validation,ensure_ascii=False))
assert validation['status']=='PASS'
