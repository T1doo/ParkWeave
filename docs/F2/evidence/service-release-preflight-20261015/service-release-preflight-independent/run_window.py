"""Independent same-process frozen collection, test, traffic and source evidence."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

import httpx
import pytest

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'.runtime/service-release-preflight-independent'
EXPECTED=sys.argv[1]
PREFIX='freeze-'+EXPECTED[:7]+'-formal'
MODULES=json.loads((ROOT/'.runtime/service-release-preflight/independent-modules.json').read_text())
sys.path[:0]=[str(ROOT/'tests'),str(ROOT)]


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def now(): return datetime.now(timezone.utc).isoformat()
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT,text=True)
def save(name,value): (OUT/(PREFIX+'-'+name+'.json')).write_text(json.dumps(value,sort_keys=True,ensure_ascii=False,indent=2)+'\n')
def manifest():
    return {name:sha(ROOT/name) for name in git('ls-files','-z').split('\0') if name and (ROOT/name).is_file()}
def traces(directory):
    return {str(p.relative_to(ROOT)):sha(p) for p in directory.iterdir()
            if p.is_file() and (p.name.startswith('oracle-') or p.name.endswith(('.stdout.jsonl','.stderr.log')))}


class Capture:
    def __init__(self):
        self.items=[]; self.private=set(); self.traffic=[]; self.attached=set(); self.clients=[]
    def pytest_collection_finish(self,session):
        self.items=[dict(nodeid=item.nodeid,classname=item.nodeid.split('::')[0][:-3].replace('/','.'),name=item.name) for item in session.items]
        save('collection',dict(items=self.items,count=len(self.items)))
    def pytest_runtest_call(self,item):
        seen=set()
        def visit(value,depth=0):
            if depth>6 or id(value) in seen: return
            seen.add(id(value))
            if isinstance(value,httpx.Client) and value.base_url.host in {'127.0.0.1','localhost'} and id(value) not in self.attached:
                self.attached.add(id(value)); self.clients.append(value); label=item.nodeid
                value.event_hooks['request'].append(lambda request,label=label:self.traffic.append(dict(test=label,method=request.method,path=request.url.path,transport='ACTUAL_LOOPBACK_HTTP')))
            if isinstance(value,dict):
                if 'fixture-a' in value:
                    self.private.update(x for x in value.values() if isinstance(x,str) and 16<=len(x)<=256)
                for x in value.values(): visit(x,depth+1)
            elif isinstance(value,(list,tuple)):
                for x in value: visit(x,depth+1)
        visit(item.funcargs)
        private_path=OUT/(PREFIX+'-redaction-values.private.json')
        descriptor=os.open(private_path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(descriptor,'w') as output:output.write(json.dumps(sorted(self.private))+'\n')
        private_path.chmod(0o600)


os.chdir(ROOT); assert len(EXPECTED)==40 and git('rev-parse','HEAD').strip()==EXPECTED
assert not git('status','--porcelain','--untracked-files=no')
assert not (OUT/(PREFIX+'-result.json')).exists(), 'A frozen window must never be overwritten'
legacy_dirs=[ROOT/'.runtime/typed-source-impact-independent',ROOT/'.runtime/shared-source-cases-independent']
legacy_before={name:digest for directory in legacy_dirs for name,digest in traces(directory).items()}; own_before=traces(OUT)
before=manifest(); started=now(); save('before',dict(head=EXPECTED,utc=started,files=before))
runner_hash=sha(Path(__file__)); capture=Capture()
rc=pytest.main(['-q',*MODULES,'--basetemp=/tmp/pw-preflight-independent-'+EXPECTED[:7],
               '--junitxml='+str(OUT/(PREFIX+'-junit.xml'))],plugins=[capture])
ended=now(); after=manifest(); head_after=git('rev-parse','HEAD').strip(); status=git('status','--porcelain','--untracked-files=no')
save('after',dict(head=head_after,utc=ended,files=after))
save('http-traffic',dict(count=len(capture.traffic),requests=capture.traffic,headers_or_tokens_saved=False))
legacy_after={name:digest for directory in legacy_dirs for name,digest in traces(directory).items()}; inherited=[]
target=OUT/(PREFIX+'-inherited-traces'); target.mkdir(exist_ok=True)
for name,digest in legacy_after.items():
    if legacy_before.get(name)!=digest:
        source=ROOT/name; dest=target/source.parent.name/source.name; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(source,dest)
        inherited.append(dict(raw_path=name,copied_path=str(dest.relative_to(ROOT)),sha256=digest,source_sha=EXPECTED,new_or_changed='new' if name not in legacy_before else 'changed'))
save('inherited-traces',dict(count=len(inherited),records=inherited,historical_files_not_copied=True))
own_after=traces(OUT); own_new=[dict(path=name,sha256=digest) for name,digest in own_after.items() if own_before.get(name)!=digest]
save('own-new-traces',dict(count=len(own_new),records=own_new))
xml=ET.parse(OUT/(PREFIX+'-junit.xml')); suite=next(xml.iter('testsuite'))
expected=Counter((r['classname'],r['name']) for r in capture.items)
actual=Counter((r.attrib['classname'],r.attrib['name']) for r in xml.iter('testcase'))
changed=sorted(name for name in before.keys()|after.keys() if before.get(name)!=after.get(name))
oracles=[]
for record in own_new:
    if Path(record['path']).name.startswith('oracle-'):
        oracles.extend(json.loads(line) for line in (ROOT/record['path']).read_text().splitlines() if line)
oracle=dict(records=len(oracles),expected_pairs=sum(len(r['expected_affected']) for r in oracles),actual_pairs=sum(len(r['actual_affected']) for r in oracles),
    missed_count=sum(r['missed_count'] for r in oracles),wrong_count=sum(r['wrong_count'] for r in oracles),wrong_preserved_count=sum(r['wrong_preserved_count'] for r in oracles),wrong_locked_count=sum(r.get('wrong_locked_count',0) for r in oracles),
    intentional_unknown_records=sum(r['intentional_unknown'] for r in oracles),source_heads=sorted({r['head'] for r in oracles}))
save('oracle-validation',oracle)
result=dict(source_sha=EXPECTED,head_after=head_after,started_utc=started,ended_utc=ended,modules=MODULES,
    exit_code=int(rc),collected=len(capture.items),junit_tests=int(suite.attrib['tests']),failures=int(suite.attrib['failures']),errors=int(suite.attrib['errors']),skipped=int(suite.attrib['skipped']),junit_seconds=float(suite.attrib['time']),
    exact_collection_junit_match=expected==actual,duplicate_collection_count=sum(n-1 for n in expected.values() if n>1),duplicate_junit_count=sum(n-1 for n in actual.values() if n>1),
    all_tracked_count=len(before),tracked_changed=changed,tracked_status_after=status,runner_sha256=runner_hash,runner_unchanged=runner_hash==sha(Path(__file__)),
    inherited_trace_count=len(inherited),own_trace_count=len(own_new),oracle=oracle,models=0,Windows='NOT_RUN',browser='NOT_RUN',formal_AT='NOT_RUN',production='NOT_RUN')
save('result',result); print(json.dumps(result,sort_keys=True))
assert not changed and not status and head_after==EXPECTED and result['runner_unchanged']
assert expected==actual and len(capture.items)==result['junit_tests']
sys.exit(int(rc))
