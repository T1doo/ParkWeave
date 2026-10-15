"""Independent frozen runner; only writes its own runtime evidence."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
import pytest
import httpx

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'.runtime/typed-source-impact-independent'
EXPECTED='a5d9da251c223e3a64e20d3d47987d5b58fcdb6f'
sys.path[:0]=[str(ROOT/'tests'),str(ROOT)]
window=sys.argv[1];prefix='freeze-a5d9da2-'+window
modules=['tests/test_typed_source_impact_independent.py','tests/test_typed_source_impact.py'] if window=='formal' else ['.runtime/typed-source-impact-independent/test_mixed_probes.py']


def manifest():
    files=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    return {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in files if name and (ROOT/name).is_file()}


def now():return datetime.now(timezone.utc).isoformat()
def save(name,value):(OUT/(prefix+'-'+name+'.json')).write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n')


class Capture:
    def __init__(self):self.ids=[];self.private=set();self.traffic=[];self.attached=set()
    def pytest_collection_finish(self,session):
        self.ids=[item.nodeid for item in session.items];save('collection',{'nodeids':self.ids,'count':len(self.ids)})
    def pytest_runtest_call(self,item):
        seen=set()
        def visit(value,depth=0):
            if depth>5 or id(value) in seen:return
            seen.add(id(value))
            if isinstance(value,httpx.Client) and value.base_url.host in {'127.0.0.1','localhost'} and id(value) not in self.attached:
                self.attached.add(id(value));label=item.nodeid
                value.event_hooks['request'].append(lambda request,label=label:self.traffic.append({'test':label,'method':request.method,'path':request.url.path,'transport':'ACTUAL_LOOPBACK_HTTP'}))
            if isinstance(value,dict):
                if 'fixture-a' in value and all(isinstance(k,str) for k in value):
                    self.private.update(x for x in value.values() if isinstance(x,str) and 16<=len(x)<=256)
                for x in value.values():visit(x,depth+1)
            elif isinstance(value,(tuple,list)):
                for x in value:visit(x,depth+1)
        visit(item.funcargs)
        (OUT/(prefix+'-redaction-values.private.json')).write_text(json.dumps(sorted(self.private))+'\n')


os.chdir(ROOT);head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert head==EXPECTED
status=subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True);assert not status
before=manifest();started=now();save('before',{'head':head,'utc':started,'files':before})
probe=ROOT/'.runtime/typed-source-impact-independent/test_mixed_probes.py'
probe_hash=hashlib.sha256(probe.read_bytes()).hexdigest();runner_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
capture=Capture();rc=pytest.main(['-q',*modules,'--basetemp=/tmp/parkweave-typed-independent-a5-'+window,'--junitxml='+str(OUT/(prefix+'-junit.xml'))],plugins=[capture])
after=manifest();ended=now();head_after=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();status_after=subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True)
save('after',{'head':head_after,'utc':ended,'files':after});save('http-traffic',{'requests':capture.traffic,'count':len(capture.traffic),'headers_or_tokens_saved':False})
xml=ET.parse(OUT/(prefix+'-junit.xml')).getroot();suite=xml.find('testsuite') if xml.tag=='testsuites' else xml
changed=sorted(name for name in set(before)|set(after) if before.get(name)!=after.get(name))
result={'source_sha':head,'head_after':head_after,'started_utc':started,'ended_utc':ended,'modules':modules,'exit_code':int(rc),'collected':len(capture.ids),'tests':int(suite.attrib['tests']),'failures':int(suite.attrib['failures']),'errors':int(suite.attrib['errors']),'skipped':int(suite.attrib['skipped']),'junit_seconds':float(suite.attrib['time']),'all_tracked_count':len(before),'tracked_changed':changed,'tracked_status_after':status_after,'runner_sha256':runner_hash,'runtime_probe_sha256':probe_hash if window=='mixed' else None,'runtime_probe_unchanged':hashlib.sha256(probe.read_bytes()).hexdigest()==probe_hash,'browser':'NOT_RUN','Windows':'NOT_RUN','formal_AT':'NOT_RUN','models':0,'production':'NOT_RUN'}
save('result',result);print(json.dumps(result,ensure_ascii=False))
assert not changed and not status_after and head_after==EXPECTED and result['runtime_probe_unchanged']
assert len(capture.ids)==result['tests']
sys.exit(int(rc))
