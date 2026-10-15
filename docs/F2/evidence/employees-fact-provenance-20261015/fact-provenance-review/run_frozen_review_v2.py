"""Independent frozen-source pure review runner; no PG or network calls."""
from pathlib import Path
from datetime import datetime,timezone
import ast,hashlib,json,subprocess,sys,time,xml.etree.ElementTree as ET
ROOT=Path.cwd()
OUT=ROOT/'.runtime/fact-provenance-review/frozen-8fe3e6c-v2'
OUT.mkdir(parents=True,exist_ok=False)
freeze=json.loads((ROOT/'.runtime/fact-assertion-provenance-root/freeze-v2.json').read_text())
EXPECTED='8fe3e6c6ebdb14366dd80032c953c79e746e3fd1'
BASE='6dad1e3d6220f4b1a0711afd851ccd8e8b95343d'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def save(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,ensure_ascii=True)+'\n')
def snapshot():
    tracked={p:sha((ROOT/p).read_bytes()) for p in freeze['all_tracked_sha256']}
    return dict(head=git('rev-parse','HEAD').decode().strip(),status=git('status','--porcelain').decode(),
        source={p:tracked[p] for p in freeze['source_paths']},tracked=tracked,
        runners={p:sha((ROOT/p).read_bytes()) for p in freeze['runner_paths']})
before=snapshot();save('before.json',before)
assert before['head']==EXPECTED==freeze['source_sha'] and before['status']==''
assert before['tracked']==freeze['all_tracked_sha256'] and before['source']==freeze['source_paths']
assert before['runners']==freeze['runner_paths']
modules=['tests/test_employees_fact_provenance.py','tests/test_employees_fact_provenance_review.py','tests/test_employees_fact_client_probes.py']
env=__import__('os').environ.copy();env['PYTHONPATH']='src:tests'
base=[str(ROOT/'.venv/bin/python'),'-m','pytest','-p','no:cacheprovider']
collection=subprocess.run(base+['--collect-only','-q',*modules],cwd=ROOT,env=env,text=True,capture_output=True)
(OUT/'collection.log').write_text(collection.stdout+collection.stderr)
nodes=[l for l in collection.stdout.splitlines() if l.startswith('tests/') and '::' in l]
assert collection.returncode==0 and len(nodes)==len(set(nodes))==38
start=time.monotonic()
run=subprocess.run(base+['-q',*modules,'--junitxml='+str(OUT/'junit.xml')],cwd=ROOT,env=env,text=True,capture_output=True)
(OUT/'pytest.log').write_text(run.stdout+run.stderr)
elapsed=time.monotonic()-start
cases=list(ET.parse(OUT/'junit.xml').getroot().iter('testcase'))
def identity(c):
    cls=c.attrib['classname'].split('.')
    return '/'.join(cls)+'.py::'+c.attrib['name']
junit_nodes=[identity(c) for c in cases]
assert run.returncode==0 and len(cases)==38 and len(set(junit_nodes))==38 and set(junit_nodes)==set(nodes)
assert all(c.find('failure') is None and c.find('error') is None and c.find('skipped') is None for c in cases)
probe=subprocess.run(['node','tests/employees_fact_client_probes.js'],cwd=ROOT,text=True,capture_output=True)
(OUT/'client-probes.log').write_text(probe.stdout+probe.stderr)
assert probe.returncode==0
client=json.loads(probe.stdout)
assert len(client['results'])==6 and all(r['status']=='PASS' for r in client['results'])
save('client-probes.json',client)
legacy_files=['src/parkweave/typed_source_impact.py','src/parkweave/registered_dependencies.py','src/parkweave/plan_source_conflicts.py','src/parkweave/material_package_continuation.py','src/parkweave/case_fact_clarifications.py','src/parkweave/fact_history_read_source.py','src/parkweave/template_migration.py']
legacy=[]
for p in legacy_files:
    try:old=git('show',BASE+':'+p)
    except subprocess.CalledProcessError:
        # A nonexistent name is not passed as a compatibility assertion.
        continue
    current=(ROOT/p).read_bytes()
    legacy.append(dict(path=p,baseline_sha256=sha(old),current_sha256=sha(current),equal=current==old))
assert all(r['equal'] for r in legacy)
after=snapshot();save('after.json',after)
assert after==before
save('collection-junit.json',dict(collection=nodes,junit=junit_nodes,exact_match=True))
save('legacy-compatibility.json',legacy)
result=dict(status='PASS',source_sha=EXPECTED,utc=datetime.now(timezone.utc).isoformat(),
    evidence_kind='FROZEN_STATIC_REVIEW_AND_PURE_TESTS',pytest=dict(passed=38,elapsed_seconds=elapsed,modules=modules),
    controlled_client_probes=6,source_paths=len(before['source']),tracked_paths=len(before['tracked']),
    head_before_after_equal=True,source_before_after_equal=True,tracked_before_after_equal=True,runner_before_after_equal=True,
    clean_before_after=True,collection_junit_exact_unique=True,
    findings=[],boundaries=['No PostgreSQL, ASGI, HTTP or real-browser tests in this review window',
    '103-module full affected regression pending separately',
    '26 design tamper rows are not 26 executions; actual independent pure cases are in collection-junit.json',
    'Fact capture digest is commit-time actual-row/epoch binding, not an administrator signature',
    'Only explicit employees USER_ASSERTED_SYNTHETIC; MANUAL/package/template composition rejected for new scope',
    'Windows, formal AT, human semantics, actual models and production NOT_RUN'])
save('review.json',result)
print(json.dumps({k:v for k,v in result.items() if k not in ('boundaries','pytest')}))
