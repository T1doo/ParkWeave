"""Independent read-only source binding and owned-fixture pytest capture."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path('/workspace/ParkWeave')
OWN = ROOT / '.runtime/native-run-access-writer-review-20261012'
EXPECTED = '77e8e98b98bd1ad6d6aebc5e684f450ce2b56b5a'

def put(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')

def capture():
    head = subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip()
    status = subprocess.check_output(['git','status','--porcelain=v1'], cwd=ROOT, text=True)
    tree = subprocess.check_output(['git','ls-tree','-r','--format=%(objectname) %(path)','HEAD'], cwd=ROOT, text=True)
    objects = dict(line.split(' ',1)[::-1] for line in tree.splitlines())
    paths = sorted(p for p in objects if p.startswith(('src/','tests/','scripts/','.github/workflows/')) or p == 'pyproject.toml')
    paths += ['docs/F2/NativeRunAccessWriterContract.md','docs/F2/NativeRunAccessWriterInstallationPlan.md']
    files = {}
    mismatch = []
    for p in paths:
        data = (ROOT/p).read_bytes()
        files[p] = hashlib.sha256(data).hexdigest()
        oid = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        if oid != objects.get(p): mismatch.append(p)
    assert head == EXPECTED, head
    assert not status, status
    assert not mismatch, mismatch
    return dict(source_head=head, git_status=status, file_count=len(files), files=files, commit_byte_mismatch=mismatch)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('window')
    parser.add_argument('modules', nargs='+')
    args=parser.parse_args()
    out=OWN/args.window
    out.mkdir(exist_ok=False)
    before=capture(); put(out/'source-before.json',before)
    argv=[str(ROOT/'.venv/bin/python'),'-m','pytest','-q','-ra',*args.modules,
          '--basetemp='+str(out/'pytest-tmp'),'--junitxml='+str(out/'results.xml')]
    environment=dict(os.environ)
    environment['PYTHONPATH']=str(ROOT/'src')+os.pathsep+str(ROOT/'tests')
    environment['PYTHONDONTWRITEBYTECODE']='1'
    environment['PARKWEAVE_WRITER_EVIDENCE_DIR']=str(out/'observations')
    start=datetime.now(timezone.utc).isoformat(); clock=time.monotonic()
    with (out/'stdout.log').open('wb') as stdout, (out/'stderr.log').open('wb') as stderr:
        process=subprocess.Popen(argv,cwd=ROOT,env=environment,stdout=stdout,stderr=stderr)
        put(out/'running.json',dict(argv=argv,pid=process.pid,started_utc=start,source_head=EXPECTED,
            scope='OWNED_SYNTHETIC_REFERENCE_ONLY', browser_attempts=0))
        code=process.wait()
    elapsed=time.monotonic()-clock
    after=capture();put(out/'source-after.json',after)
    changed=sorted(p for p in before['files'] if before['files'][p] != after['files'].get(p))
    cases=[]
    if (out/'results.xml').exists():
        for element in ET.parse(out/'results.xml').getroot().iter('testcase'):
            status='ERROR' if element.find('error') is not None else 'FAIL' if element.find('failure') is not None else 'SKIP' if element.find('skipped') is not None else 'PASS'
            cases.append(dict(classname=element.get('classname'),name=element.get('name'),time=element.get('time'),outcome=status))
    ids=[(c['classname'],c['name']) for c in cases]
    counts={state:sum(c['outcome']==state for c in cases) for state in ['PASS','FAIL','ERROR','SKIP']}
    record=dict(argv=argv,pid=process.pid,started_utc=start,ended_utc=datetime.now(timezone.utc).isoformat(),
        elapsed_seconds=elapsed,exit_code=code,source_head=EXPECTED,source_file_count=before['file_count'],
        source_manifest_sha256=hashlib.sha256((out/'source-before.json').read_bytes()).hexdigest(),
        source_changed=changed,unique_test_ids=len(set(ids)),testcase_count=len(cases),counts=counts,cases=cases,
        browser_attempts=0,production_installation='NOT_RUN',real_permission_changes='NOT_RUN',formal_AT35='NOT_RUN',
        hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()})
    put(out/'run.json',record)
    print(json.dumps({k:record[k] for k in ['exit_code','counts','unique_test_ids','elapsed_seconds','source_changed','source_file_count']}))
    assert len(ids)==len(set(ids)), 'duplicate testcase IDs'
    assert not changed, changed
    return code

if __name__=='__main__':sys.exit(main())
