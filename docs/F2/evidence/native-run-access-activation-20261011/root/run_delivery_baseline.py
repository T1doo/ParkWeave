"""Two independent PG lanes; every permitted module complete, every ID once."""
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,os,subprocess,time,xml.etree.ElementTree as ET
root=Path('.runtime/native-run-access-activation-20261011')
scope=json.loads((root/'delivery-baseline-scope.json').read_text())
manifest=json.loads((root/scope['source_manifest']).read_text());contracts=json.loads((root/'delivery-contracts.json').read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()
now=lambda:datetime.now(timezone.utc).isoformat()
def drift(items):return [p for p,h in items.items() if not Path(p).is_file() or sha(Path(p).read_bytes())!=h]
def identity(c):return c.get('classname','')+'::'+c.get('name','')
def outcomes(cases):return {identity(c):'FAIL' if c.find('failure') is not None else 'ERROR' if c.find('error') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS' for c in cases}
assert not drift(manifest) and not drift(contracts)
previous=ET.parse(root/'full-baseline.xml').getroot().findall('.//testcase')
weights=defaultdict(float)
for c in previous:
    if not c.get('classname'):
        assert c.find('skipped') is not None, identity(c)
        continue  # Preserve the original module-level collection SKIP separately.
    matches=[m for m in scope['modules'] if any(c.get('classname','')==key or c.get('classname','').startswith(key+'.') for key in [m[:-3].replace('/','.'),Path(m).stem])]
    assert len(matches)==1,(identity(c),matches)
    weights[matches[0]]+=float(c.get('time','0'))
lanes={x:dict(modules=[],weight=0) for x in ['a','b']}
for m in sorted(scope['modules'],key=lambda m:(-weights[m],m)):
    key=min(lanes,key=lambda x:lanes[x]['weight']);lanes[key]['modules'].append(m);lanes[key]['weight']+=weights[m]
for lane in lanes.values():lane['modules'].sort()
family=lambda x:x.split('[',1)[0]
expected=set(json.loads((root/'permitted-collection.json').read_text())['collected_ids'])
collected=set();start=now();clock=time.monotonic();children=[]
for key,lane in lanes.items():
    prefix='delivery-lane-'+key;log=root/(prefix+'-collection.log');assert not log.exists()
    with log.open('w') as out:result=subprocess.run(['.venv/bin/python','-m','pytest',*lane['modules'],'--collect-only','-q'],stdout=out,stderr=subprocess.STDOUT)
    ids=[x for x in log.read_text().splitlines() if x.startswith('tests/') and '::' in x]
    assert result.returncode==0 and len(ids)==len(set(ids)) and not collected.intersection(ids)
    collected.update(ids);lane.update(collected_ids=ids,collection_exit=result.returncode,collection_log_sha256=sha(log.read_bytes()))
assert Counter(map(family,collected))==Counter(map(family,expected)) and not drift(manifest) and not drift(contracts)
for key,lane in lanes.items():
    prefix='delivery-lane-'+key;env=os.environ.copy()
    env['PYTHONPATH']=str(root.resolve())
    env['PARKWEAVE_DELIVERY_COLLECTION_OUT']=str(root/(prefix+'-actual-collection.json'))
    for var,suffix in [('PARKWEAVE_T07_EVIDENCE_DIR','t07'),('PARKWEAVE_NATIVE_ACTIVATION_EVIDENCE_DIR','activation')]:
        p=root/(prefix+'-'+suffix);assert not p.exists();env[var]=str(p)
    xml=root/(prefix+'.xml');log=root/(prefix+'.log');assert not xml.exists() and not log.exists()
    out=log.open('w');argv=['.venv/bin/python','-m','pytest',*lane['modules'],'-p','delivery_collection_plugin','-q','--tb=short','--junitxml='+str(xml)]
    p=subprocess.Popen(argv,stdout=out,stderr=subprocess.STDOUT,env=env)
    lane.update(argv=argv,pid=p.pid,start_utc=now());children.append((key,p,out,xml,log,time.monotonic()))
(root/'delivery-baseline-running.json').write_text(json.dumps(dict(source_sha=scope['source_sha'],start_utc=start,expected_unique_ids=len(expected),lanes=lanes),indent=2)+'\n')
print(json.dumps(dict(source_sha=scope['source_sha'],complete_modules=len(scope['modules']),expected_unique_ids=len(expected),lanes={key:dict(pid=x['pid'],modules=len(x['modules']),collected=len(x['collected_ids'])) for key,x in lanes.items()})),flush=True)
all_outcomes={};all_collected=set();collection_skips=[]
def completed(child):
    key,p,out,xml,log,begun=child
    code=p.wait();out.close()
    return key,code,xml,log,now(),time.monotonic()-begun
with ThreadPoolExecutor(max_workers=2) as pool:
    done=[future.result() for future in as_completed([pool.submit(completed,child) for child in children])]
for key,code,xml,log,finished,elapsed in done:
    cases=ET.parse(xml).getroot().findall('.//testcase');results=outcomes(cases)
    actual=json.loads((root/('delivery-lane-'+key+'-actual-collection.json')).read_text())['collected']
    actual_ids={x['nodeid'] for x in actual}
    expected_cases={x['classname']+'::'+x['name'] for x in actual}
    extras=[c for c in cases if identity(c) not in expected_cases]
    assert len(results)==len(cases) and len(actual_ids)==len(actual) and not all_collected.intersection(actual_ids)
    assert expected_cases<=set(results) and all(not c.get('classname') and c.find('skipped') is not None for c in extras)
    assert len(actual)==len(lanes[key]['collected_ids']) and not set(results).intersection(all_outcomes)
    all_collected.update(actual_ids);collection_skips.extend(identity(c) for c in extras)
    all_outcomes.update(results);counts=dict(Counter(results.values()))
    lanes[key].update(exit_code=code,finish_utc=finished,elapsed_seconds=elapsed,counts=counts,junit_unique_ids=len(results),actual_collected_ids=sorted(actual_ids),collection_skip_ids=[identity(c) for c in extras],outcomes=results,failures=[dict(test_id=identity(c),detail=next(c.find(t).text for t in ['failure','error'] if c.find(t) is not None)) for c in cases if c.find('failure') is not None or c.find('error') is not None],skips=[dict(test_id=identity(c),reason=c.find('skipped').get('message')) for c in cases if c.find('skipped') is not None],raw_sha256={x.name:sha(x.read_bytes()) for x in [xml,log]})
    print(json.dumps(dict(lane=key,exit_code=code,counts=counts,unique_ids=len(results))),flush=True)
record=dict(source_sha=scope['source_sha'],source_manifest_sha256=scope['source_manifest_sha256'],invoked_modules=len(scope['modules']),unique_ids=len(all_outcomes),actual_collected_unique_ids=len(all_collected),collection_skip_ids=collection_skips,counts=dict(Counter(all_outcomes.values())),start_utc=start,finish_utc=now(),elapsed_seconds=time.monotonic()-clock,lanes=lanes,source_drift=drift(manifest),contract_drift=drift(contracts),browser_attempts=0,formal_AT35=False,one_pytest_invocation=False,all_permitted_modules_invoked=True,all_collected_ids_completed=True)
assert len(all_collected)==len(expected) and Counter(map(family,all_collected))==Counter(map(family,expected))
assert len(all_outcomes)==len(all_collected)+len(collection_skips)
(root/'delivery-baseline-run.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k!='lanes'},indent=2),flush=True)
raise SystemExit(1 if any(x['exit_code'] for x in lanes.values()) or record['source_drift'] or record['contract_drift'] else 0)
