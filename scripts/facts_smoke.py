"""Self-authored synthetic HTTP facts trace; requires the local fixture harness."""
import json
import hashlib
import time
import uuid
from pathlib import Path
import httpx

root=Path.cwd();tokens=json.loads((root/'.runtime/synthetic-sessions.json').read_text())
headers={'Authorization':'Bearer '+tokens['fixture-a']}
inputs=[];ids=[]
with httpx.Client(base_url='http://127.0.0.1:8765',timeout=5) as api:
    for source,value in [('synthetic-fact-doc-a','甲合成地区'),('synthetic-fact-doc-b','乙合成地区')]:
        body={'schema_version':'parkweave-domain/1.0-draft','field':'region','value':value,'unit':'text',
              'source_ref':{'id':source,'kind':'SYNTHETIC','revision':'1'},'source_excerpt':value,
              'validity':{'valid_from':'2026-01-01T00:00:00+00:00','valid_until':'2099-01-01T00:00:00+00:00','timezone':'UTC'}}
        r=api.post('/api/facts',headers=headers|{'Idempotency-Key':uuid.uuid4().hex},json=body)
        assert r.status_code==201,r.text;ids.append(r.json()['fact_id']);inputs.append(body)
    create=api.post('/api/runs',headers=headers|{'Idempotency-Key':uuid.uuid4().hex},json={
        'goal':'合成：检查冲突与缺证据','action':'facts.assess','fact_fields':['region','employees']})
    assert create.status_code==202;run=create.json()['run_id']
    for _ in range(100):
        result=api.get('/api/runs/'+run,headers=headers).json()
        if result['state']=='SUCCEEDED':break
        time.sleep(.05)
    receipt=result['operation']['receipt'];states={r['field']:r for r in receipt['results']}
    assert states['region']['state']=='UNKNOWN' and states['region']['reason']=='CONFLICTING_EVIDENCE'
    assert states['employees']['state']=='UNKNOWN' and states['employees']['reason']=='MISSING_EVIDENCE'
    denied=api.get('/api/facts/'+ids[0],headers={'Authorization':'Bearer '+tokens['fixture-c']})
    assert denied.status_code==403
    report={'status':'PASS','type':'SYNTHETIC_LOCAL_ENGINEERING','environment':'Linux HTTP + independent worker + PostgreSQL16.2',
            'input_sha256':hashlib.sha256(json.dumps(inputs,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
            'fact_ids':ids,'cross_park_status':403,'run':result,'model_calls':0,
            'target_windows':'Windows11 user-confirmed family only; native tests BLOCKED',
            'processes':json.loads((root/'.runtime/smoke-environment.json').read_text())}
    (root/'docs/F1/evidence/eng004-facts-smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
